# Agent Operations — Outstanding Work

## Critical

- [x] **Fix directory structure mismatch** — Updated `Dockerfile.lambda` COPY paths to `langgraph-agents/…` and updated `AGENTS.md` directory map.
- [x] **Add NAT instance** — `t4g.nano` NAT instance in public subnet, `~$3.50/mo`. Private route table sends `0.0.0.0/0` through it. Lambdas can now reach OpenRouter/Langfuse.
- [x] **Fix AgentCore dispatch — SDK vs HTTP** — `dispatch_to_agentcore()` and `orchestration.py` now use boto3 `bedrock-agent-runtime.invoke_agent()` instead of `httpx.post()`. Terraform env vars changed to `AGENTCORE_AGENT_ID`/`CODING_AGENT_ID`. Added `bedrock:InvokeAgent` IAM policy. Created `shared/bedrock_agent.py` helper. Added `boto3` to pyproject.toml.
- [x] **Decide infra platform** — `AGENTS.md` updated: infra is AWS Terraform (not Render.com). Removed stale Render references.
- [ ] **Implement guardrails** — Both `guardrails/` directories are empty. Define safety profiles and ensemble logic.

## High Priority

- [x] **Add Postgres for LangGraph checkpoints** — Created `shared/postgres.py` with `create_checkpointer()` factory using `AsyncPostgresSaver`. Wired into exploratory and verification agents. Added `POSTGRES_URL` env var to verify and both AgentCore dispatcher Lambdas.
- [x] **Wire UI frontend to S3** — Created `infra/deploy-ui.sh` build+sync script and `.github/workflows/deploy-ui.yml` CI workflow. Added `ui_assets_bucket` and `cloudfront_distribution_id` terraform outputs.
- [x] **Add LANGFUSE env vars to all Lambdas** — Added `langfuse_public_key`, `langfuse_secret_key`, `langfuse_host` variables. Wired `LANGFUSE_*` env vars to all 6 Lambdas via shared `local.langfuse_env` map.

## Medium Priority

- [x] **Document required AWS Secrets Manager secrets** — `terraform.tfvars.example` now includes prerequisite `aws secretsmanager create-secret` commands. README.md has a full Deployment section with prerequisites.
- [ ] **Multi-AZ support** — ArcadeDB and RDS are in a single AZ (`private_a`). `private_b` is defined but unused. Documented in README productionisation section.
- [x] **Verify Lambda schedule** — Changed from every 60 seconds to every 1 hour (same as orchestrate). Schedule was adjusted earlier in this session.

## Low Priority

- [x] **Convert orchestration function to LangGraph agent** — Cancelled. Orchestration is a stateless dispatch/detect/promote/decay cycle. A procedural function is the right fit.
- [x] **Add integration tests** — Created `tests/integration/` with env-var-gated tests: exploratory end-to-end, verification full cycle, orchestration cycle, Postgres checkpoint persistence + resumability, ArcadeDB graph/timeseries/identity CRUD. Skipped when `ARCADEDB_URL`/`POSTGRES_URL` are localhost.
- [x] **Add `terraform.tfvars.example` documentation** — File now includes prerequisite Secrets Manager commands, variable descriptions, and usage instructions.
