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
2. **Secrets Manager secrets** created (before `terraform apply`):
   ```bash
   aws secretsmanager create-secret \
     --name "agent-ops/arcadedb" \
     --secret-string '{"password":"<arcadedb-root-password>"}'

   aws secretsmanager create-secret \
     --name "agent-ops/postgres" \
     --secret-string '{"password":"<postgres-password>"}'
   ```
3. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill in your values:
   ```bash
   cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
   ```

### Apply

```bash
cd infra/terraform
terraform init
terraform apply -var="openrouter_api_key=..." -var="langfuse_public_key=..." -var="langfuse_secret_key=..."
```

### Deploy UI

```bash
./infra/deploy-ui.sh
```

Or push to `main` — the `.github/workflows/deploy-ui.yml` workflow handles it automatically when `ui-frontend/**` changes.

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
