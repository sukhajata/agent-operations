# Runbook — Agent Operations

## Initial Deployment

### Prerequisites

1. AWS account with Lambda and EventBridge access
2. OpenRouter API key
3. Langfuse account (free tier: https://cloud.langfuse.com)
4. AWS credentials configured locally

### Deploy from scratch

```bash
# 1. Build and push Docker image to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker build -t agent-operations:latest .
docker tag agent-operations:latest <account>.dkr.ecr.us-east-1.amazonaws.com/agent-operations:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/agent-operations:latest

# 2. Deploy Lambda functions via SAM/CloudFormation
cd infra/lambda
sam deploy --guided

# 3. Run schema migrations
aws lambda invoke --function-name agent-operations-migrate --payload '{}' response.json

# 4. Verify functions are deployed
aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `agent-operations`)]'
```

The deployment creates: Lambda functions for orchestration, verification, exploratory agents, and approval UI. EventBridge rules trigger functions on schedule.

## Required Secrets

| Variable | Function | Description |
|----------|---------|-------------|
| `ARCADEDB_URL` | All | ArcadeDB service URL |
| `ARCADEDB_USER` | All | ArcadeDB username |
| `ARCADEDB_PASSWORD` | All | ArcadeDB root password |
| `OPENROUTER_API_KEY` | Agents | OpenRouter API key |
| `LANGFUSE_PUBLIC_KEY` | Agents | Langfuse public key |
| `LANGFUSE_SECRET_KEY` | Agents | Langfuse secret key |
| `LLM_API_KEY` | Coding agent | LLM API key (OpenRouter) |
| `UI_USERNAME` | Approval UI | UI basic auth username |
| `UI_PASSWORD` | Approval UI | UI basic auth password |
| `CODING_AGENT_ID` | Orchestration | Bedrock coding agent ID |
| `POSTGRES_URL` | All | PostgreSQL URL (LangGraph checkpoints) |

## Running Schema Migrations

Migrations are idempotent — safe to run against an existing database.

```bash
cd langgraph-agents
uv run python -m schema.migrate
```

In production, invoke the migration Lambda function:
```bash
aws lambda invoke --function-name agent-operations-migrate --payload '{}' response.json
```

## Monitoring

### Langfuse Traces

All LLM calls are traced to Langfuse Cloud. Navigate to https://cloud.langfuse.com and select your project. Each trace includes:
- Model, input/output tokens, estimated cost, latency
- Agent type, agent ID, focus ID, MTP version

### CloudWatch Logs

```bash
aws logs tail /aws/lambda/agent-operations-orchestrate --follow
aws logs tail /aws/lambda/agent-operations-verify --follow
aws logs tail /aws/lambda/agent-operations-explore --follow
aws logs tail /aws/lambda/agent-operations-ui --follow
```

### Approval UI

The approval UI at the Lambda function URL shows:
- Pending commitments with plan previews
- Approve/reject/defer buttons
- LLM chat for querying system state
- Event log viewer (toggle recent activity)

## Adding a New Exploratory Mandate

Mandates are stored in ArcadeDB's `MandateRecord` table, not in deployment configuration. To add a new mandate:

1. Insert a new record into ArcadeDB:

```sql
INSERT INTO MandateRecord SET 
  mandate_id = 'my_new_mandate',
  name = 'my_new_mandate',
  domain = 'my_domain',
  agent_type = 'free',
  polling_interval_minutes = 30,
  signal_threshold = 0.6,
  active = true
```

2. Create an EventBridge rule to trigger the exploratory Lambda on schedule:

```bash
aws events put-rule \
  --name agent-operations-explore-my-new-mandate \
  --schedule-expression 'rate(30 minutes)'

aws events put-targets \
  --rule agent-operations-explore-my-new-mandate \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:<account>:function:agent-operations-explore","Input"='{"mandate_name":"my_new_mandate"}'
```

3. Grant EventBridge permission to invoke the Lambda:

```bash
aws lambda add-permission \
  --function-name agent-operations-explore \
  --statement-id agent-operations-explore-my-new-mandate \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:<account>:rule/agent-operations-explore-my-new-mandate
```

The exploratory agent will automatically pick up the new mandate on its next invocation.

## Managing Focuses

Focus records define targeted exploration areas. They are created by the research/plan agent and can be managed via ArcadeDB:

```bash
# List active focuses
curl -u $ARCADEDB_USER:$ARCADEDB_PASSWORD \
  "$ARCADEDB_URL/api/v1/query/agent_operations" \
  -d '{"language":"sql","command":"SELECT FROM FocusRecord WHERE status=\"active\""}'
```

## Human Approval Workflow

1. Research/plan agent marks a commitment `pending_approval`
2. Open the approval UI (web service URL) — login with UI_USERNAME / UI_PASSWORD
3. Review the plan in the Pending Approvals panel
4. Use Approve/Reject/Defer buttons, or chat with the LLM to ask questions
5. Approved commitments are picked up by the orchestration function, which dispatches them to the coding agent
6. The coding agent executes the plan and updates the commitment status

## Signal Flow

```
Exploratory agent (cron)
    ↓ emits AgentSignal (observation)
Verification agent (worker, polls independently)
    ↓ emits AgentFinding with verdict: confirmed | contradicted | inconclusive
Research/plan agent (worker, polls independently)
    ↓ creates CommitmentRecord, runs research, writes plan & checkpoint
    ↓ marks status='pending_approval'
Human approval UI
    ↓ human approves → status='approved'
Orchestration function (cron)
    ↓ dispatches to coding agent → status='executing'
Coding agent (web)
    ↓ executes plan, calls arcadedb MCP tool
    ↓ status='complete' or 'stalled'
Orchestration function (cron)
    → promotes findings to knowledge graph
    → runs confidence decay
    → detects stalled commitments
```

## Common Failure Modes

| Symptom | Likely cause | Action |
|---------|-------------|--------|
| No signals emitted | Exploratory agent can't reach ArcadeDB | `render logs --service explore-competitor` |
| Signals not verified | Verification agent not polling | `render logs --service verify`, check interval |
| Commitments stuck in `executing` | Coding agent crashed mid-execution | Check coding-agent logs; orchestration will stall after 6h |
| Commitments stuck in `pending_approval` | No human has reviewed | Open approval UI |
| OpenRouter 429 errors | Rate limited | Increase polling interval, check OpenRouter dashboard |
| ArcadeDB connection refused | ArcadeDB service down | Check ArcadeDB service status, verify ARCADEDB_URL |
| ModelFamilyError | Verification using same model family as exploratory | Check verification model config (should be Qwen, not DeepSeek) |
| Missing plan in commitment | Research/plan agent failed to produce plan | Orchestration marks these as `stalled` |
