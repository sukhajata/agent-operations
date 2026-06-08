# AGENTS.md

## 1. Repository Purpose

Nous is a reusable agent platform implementing the ExO 3.0 Intelligence Stack. It is not a product. No project-specific code belongs in this repository. All code must be generic, configurable, and free of hardcoded project names, domains, or credentials.

## 2. Directory Map

- `agents/` — Agent implementations (exploratory, verification, objective, orchestration)
- `shared/` — Shared libraries (ArcadeDB client, OpenRouter client, ACAP enforcer, event schemas, MCP manager)
- `schema/` — ArcadeDB schema definitions and migrations (timeseries, graph, identity)
- `guardrails/` — Guardrail ensemble and safety profiles
- `config/` — Configuration schemas and reference configurations
- `infra/` — Infrastructure-as-code for Render.com deployment
- `tests/` — Test suites (unit, integration, agent regression)
- `docs/` — Operational documentation and runbooks

## 3. Autonomous Modification Rules

Agents **MAY** modify:
- `agents/`
- `shared/`
- `tests/unit/`
- `tests/agent/`

Agents **MUST NOT** autonomously modify:
- `schema/migrations/` — human review required for all migrations
- `config/schema/` — configuration API is a public contract
- `infra/` — infrastructure changes require human approval
- `AGENTS.md` — this file

## 4. Event Schema Contract

Any code that emits events **MUST** use the canonical schemas in `shared/event_schemas/`. Every event **MUST** carry: `agent_id`, `objective_id`, `mtp_version`, `timestamp`.

## 5. ACAP Constraints

This repository has its own ACAP. Agents working here may not make external network calls except to:
- OpenRouter API
- ArcadeDB at `ARCADEDB_URL`
- Postgres at `POSTGRES_URL`
- Langfuse at `LANGFUSE_HOST`

## 6. Test Requirement

All changes must pass:
- `ruff check .`
- `mypy --strict .`
- `pytest tests/unit/` with 80% coverage on modified modules
