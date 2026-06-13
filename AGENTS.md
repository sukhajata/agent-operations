# AGENTS.md

## 1. Repository Purpose

Agent Operations is a reusable agent platform implementing the ExO 3.0 Intelligence Stack. It is not a product. No project-specific code belongs in this repository. All code must be generic, configurable, and free of hardcoded project names, domains, or credentials.

## 2. Directory Map

- `langgraph-agents/` — Primary codebase: agent implementations, shared libraries, schema, config, tools, functions, UI
- `coding-agent/` — Coding agent implementation (invoked by orchestration to execute approved commitments)
- `ui-frontend/` — Web frontend for approval UI
- `infra/` — Infrastructure-as-code for AWS deployment (Terraform)
- `docs/` — Operational documentation and runbooks

## 3. Autonomous Modification Rules

Agents **MAY** modify all directories in this repository except:
- `guardrails/` — guardrail profiles and ensemble logic require human approval

## 4. Event Schema Contract

Any code that emits events **MUST** use the canonical schemas in `shared/event_schemas/`. Every event **MUST** carry: `agent_id`, `focus_id`, `mtp_version`, `timestamp`.

`AgentSignal` and `AgentFinding` are separate types: `AgentSignal` for exploratory observations, `AgentFinding` for verification conclusions with a `verdict` field (`confirmed`, `contradicted`, or `inconclusive`). `ObjectiveTransition` is removed — use `CommitmentTransition`.

## 5. ACAP Constraints

This repository has its own ACAP. Agents working here may not make external network calls except to:
- OpenRouter API
- ArcadeDB at `ARCADEDB_URL`
- Postgres at `POSTGRES_URL` (LangGraph checkpoint persistence)
- Langfuse at `LANGFUSE_HOST`

## 6. Verification Independence

Verification agents **MUST** use a different model family from the signal's originating agent. `enforce_independence()` in `shared/openrouter/models.py` enforces this at runtime.

## 7. Test Requirement

Ensure to write tests for new code which is testable.

All changes must pass:
- `ruff check .`
- `mypy --strict .`
- `pytest tests/unit/` with 80% coverage on modified modules

## 8. Documentation Requirements

Ensure that the README.md is up to date with the current state of the repo.

## 9. Task management

If using a plan or tasks document, be sure to mark completed tasks as completed.

