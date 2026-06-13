# Agent Operations

An agent platform implementing the ExO 3.0 Intelligence Stack.

## Introduction

A consistent picture is emerging across research from Google, MIT, Berkeley, WEF, IMD, and leading practitioners: AI adoption alone is not a competitive advantage. The organisations that will survive the next decade are those that restructure how decisions are made, how knowledge is accumulated, and how work is coordinated — not just those that deploy the best tools.

Deploying AI within existing organisational structures produces marginal gains. The structural redesign — of decision rights, coordination patterns, and information flows — is what produces compounding advantage.

The goal of this project is to provide a platform where agents do the work and humans do the decision making, governance and steering.

## Architecture

The platform consists of four agent types — exploratory, verification, objective, and orchestration — coordinated via an event log stored in ArcadeDB. Knowledge is maintained in a graph database with confidence decay. All agent output passes through a guardrail ensemble before delivery.

See [docs/plan.md](docs/plan.md) for the full build plan and [docs/requirements.md](docs/requirements.md) for requirements.

## Background Reading

This project is grounded in research about how AI reshapes organizational decision-making and coordination:

- **[Decision Making in the AI Era](docs/decision_making_in_AI_era.md)** — Why AI adoption alone isn't a competitive advantage, and how decision rights must be restructured
- **[Swarms vs Sequential](docs/swarms_vs_sequential.md)** — Coordination patterns for agent swarms vs sequential workflows
- **[Surviving the AI Shift](docs/Surviving_the_AI_Shift.md)** — How organizations must adapt to survive the next decade of AI disruption
- **[AI-Native Organization (Technical)](docs/AI_Native_Organization_Technical.md)** — Technical architecture for AI-native organizations implementing the ExO 3.0 Intelligence Stack

## Deployment

Infrastructure is managed via Terraform in `infra/terraform/` and deploys to AWS.

### Prerequisites

1. **AWS credentials** configured (via env vars, `~/.aws/credentials`, or IAM role).
2. **Terraform state backend** (one-time):
   ```bash
   aws s3 mb s3://agent-ops-terraform-state --region us-east-1
   aws s3api put-bucket-versioning \
     --bucket agent-ops-terraform-state \
     --versioning-configuration Status=Enabled
   ```
   State locking is handled via S3 lock files (`use_lockfile = true`) — no DynamoDB needed.
3. **Secrets Manager secrets** created (before `terraform apply`):
   ```bash
   aws secretsmanager create-secret \
     --name "agent-ops/arcadedb" \
     --secret-string "<arcadedb-password>"

   aws secretsmanager create-secret \
     --name "agent-ops/postgres" \
     --secret-string "<postgres-password>"
   ```

### Apply (locally)

```bash
cd infra/terraform
terraform init
terraform apply \
  -var="openrouter_api_key=$OPENROUTER_API_KEY" \
  -var="langfuse_public_key=$LANGFUSE_PUBLIC_KEY" \
  -var="langfuse_secret_key=$LANGFUSE_SECRET_KEY" \
  -var="ui_password=$UI_PASSWORD"
```

All variables are passed via command line — no `terraform.tfvars` needed. On CI, these come from GitHub Secrets automatically.

### Deploying via CI/CD

Three workflows trigger on push to `main`, each scoped to its own paths:

| Workflow | Trigger | What it does |
|---|---|---|
| `deploy-infra.yml` | `infra/terraform/**` | `terraform plan` + `apply` |
| `deploy-agents.yml` | `langgraph-agents/**`, `coding-agent/**` | Builds and pushes Docker images to ECR |
| `deploy-ui.yml` | `ui-frontend/**` | Builds frontend, syncs to S3, invalidates CloudFront |

**Required GitHub Actions setup:**

1. Create the GitHub OIDC provider (one-time per AWS account):
   ```bash
   aws iam create-open-id-connect-provider \
     --url https://token.actions.githubusercontent.com \
     --client-id-list sts.amazonaws.com
   ```
   The AWS CLI will auto-discover the certificate thumbprint.

2. Create the deploy IAM role:
   ```bash
   aws iam create-role \
     --role-name github-actions-agent-ops \
     --assume-role-policy-document '{
       "Version": "2012-10-17",
       "Statement": [{
         "Effect": "Allow",
         "Principal": {"Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"},
         "Action": "sts:AssumeRoleWithWebIdentity",
         "Condition": {
           "StringEquals": {
             "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
           },
           "StringLike": {
             "token.actions.githubusercontent.com:sub": "repo:sukhajata/agent-operations:*"
           }
         }
       }]
     }'
   ```
   Replace `ACCOUNT_ID` with your AWS account ID. Adjust `sukhajata/agent-operations` to match your repo.

3. Attach the required policies:
   ```bash
   aws iam attach-role-policy \
     --role-name github-actions-agent-ops \
     --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryPowerUser

   # Custom policy for S3 + CloudFront
   aws iam put-role-policy \
     --role-name github-actions-agent-ops \
     --policy-name s3-cloudfront-deploy \
     --policy-document '{
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": ["s3:ListBucket", "s3:PutObject", "s3:DeleteObject"],
           "Resource": ["arn:aws:s3:::agent-ops-ui-*", "arn:aws:s3:::agent-ops-ui-*/*"]
         },
         {
           "Effect": "Allow",
           "Action": "cloudfront:CreateInvalidation",
           "Resource": "*"
         }
       ]
     }'
   ```

4. Set GitHub Actions **variables** (repo Settings → Secrets and variables → Actions → Variables):
   - `AWS_REGION` → `us-east-1`
   - `AWS_DEPLOY_ROLE` → `arn:aws:iam::ACCOUNT_ID:role/github-actions-agent-ops`
   - `UI_S3_BUCKET` → from `terraform output ui_assets_bucket` (after first apply)
   - `CLOUDFRONT_DISTRIBUTION_ID` → from `terraform output cloudfront_distribution_id` (after first apply)

5. Set GitHub Actions **secrets** (repo Settings → Secrets and variables → Actions → Secrets):
   - `OPENROUTER_API_KEY`
   - `LANGFUSE_PUBLIC_KEY`
   - `LANGFUSE_SECRET_KEY`
   - `UI_PASSWORD`

### Resources created

| Resource | Purpose |
|---|---|
| VPC + 3 subnets + NAT instance | Network isolation with outbound internet |
| ArcadeDB on EC2 (t3.medium) | Graph + timeseries event log |
| RDS PostgreSQL 16 (t4g.micro) | LangGraph checkpoint persistence |
| 4 Lambda functions | orchestrate, explore, verify, UI |
| 2 AgentCore Bedrock agents | coding, exploratory (long-running tasks) |
| S3 + CloudFront | UI static asset hosting |

### Productionisation

Items to address before running in production:

- **Multi-AZ** — ArcadeDB EC2 and RDS are deployed in a single availability zone (`private_a`). A second private subnet (`private_b`) exists but is unused. For production, spread resources across AZs and add RDS Multi-AZ failover.
- **ArcadeDB backups** — The EC2 instance mounts a gp3 volume but has no snapshot schedule. Configure EBS snapshots or replicate ArcadeDB data.
- **Secrets rotation** — Secrets Manager secrets are read at deploy time but not rotated. Enable automatic rotation for both `agent-ops/arcadedb` and `agent-ops/postgres`.
- **Lambda concurrency** — Scheduled Lambdas have no concurrency limits. If EventBridge retries overlap, multiple instances may run. Set `reserved_concurrent_executions = 1` on each scheduled Lambda.

## Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | API key for OpenRouter (LLM routing) |
| `ARCADEDB_URL` | ArcadeDB HTTP endpoint |
| `ARCADEDB_USER` | ArcadeDB username |
| `ARCADEDB_PASSWORD` | ArcadeDB password |
| `POSTGRES_URL` | PostgreSQL connection string (LangGraph checkpoints) |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key for tracing |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key for tracing |
| `LANGFUSE_HOST` | Langfuse host URL |
| `AGENT_OPERATIONS_CONFIG_PATH` | Path to project configuration directory |

See `.env.example` for placeholder values.

## Local Development

```bash
uv sync
uv run ruff check .
uv run mypy .
uv run pytest tests/unit/
```

## Running Tests

```bash
uv run pytest tests/unit/ --cov=shared --cov=agents --cov-report=term-missing
uv run pytest tests/integration/
uv run pytest tests/agent/ -m 'not agent_regression'
```
