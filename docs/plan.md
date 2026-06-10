# Agent Operations

**Repository Build Plan — Task Instructions for Agent Execution**

June 2026 — v0.2

## Instructions for the Executing Agent

You are building the initial repository for Agent Operations — an agent platform that implements the ExO 3.0 Intelligence Stack.

Complete each task in order. Do not skip tasks. Each task specifies its inputs, outputs (files to create or modify), numbered steps, and done-when criteria. A task is complete only when all done-when criteria pass.

Commit after each completed task with the task ID as the commit message prefix (e.g. `TASK-01: repository scaffold`).

**Language:** Python 3.12+. **Package manager:** uv. **Type checker:** mypy strict mode. **Linter:** ruff. **Test runner:** pytest.

All code must be fully typed. No hardcoded project names, domains, or credentials anywhere in the codebase.

**Deployment target:** Render.com. ArcadeDB as a private service with persistent disk. Each agent type as an independent Render service — exploratory agents as cron jobs, verification/research-plan/implementation agents as background workers triggered by event log polling. Orchestration agent as a thin background worker. PostgreSQL via Render managed Postgres for LangGraph checkpoints (implementation agent only).

**Architecture principles:**

- Each agent is an independent process. Coordination happens through the shared substrate (ArcadeDB event log and commitment registry), not through a managing process.
- Colony workers (exploratory agents) are homogeneous — same code, different mandate configuration.
- Signal flow is: `observation` → verification → `finding` → research/plan → human approval → implementation.
- Each stage agent polls the event log or commitment registry independently. No agent spawns another.
- The orchestration agent monitors health, escalates failures, and manages knowledge graph promotion. It does not coordinate agent execution.

**Key invariants to enforce throughout:**

1. No project-specific code in this repository
2. No credentials in any file
3. Every emitted event carries `agent_id`, `focus_id`, `mtp_version`, and `timestamp`
4. ACAP boundaries are checked before every agent action
5. Verification agents always use a different model family from the signal's originating agent

## Phase Overview

| Phase | Name | Tasks |
|-------|------|-------|
| A | Repository Scaffold | TASK-01 to TASK-03 |
| B | ArcadeDB Schema | TASK-04 to TASK-07 |
| C | Shared Libraries | TASK-08 to TASK-13 |
| D | Schema Migration | TASK-14-M |
| E | Agent Implementations | TASK-15 to TASK-19 |
| F | Orchestration | TASK-20 |
| G | Human Approval UI | TASK-21 |
| H | Guardrails | TASK-22 |
| I | Observability | TASK-23 to TASK-24 |
| J | Tests | TASK-25 to TASK-28 |
| K | CI/CD and Deployment | TASK-29 to TASK-31 |
| L | Reference Configuration | TASK-32 to TASK-33 |

---

## Phase A — Repository Scaffold

### - [x] TASK-01: Initialise repository structure and tooling

**Inputs:**
- This document
- Python 3.12+ installed
- uv installed
- git installed

**Outputs:**
- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `ruff.toml`
- `mypy.ini`
- `.gitignore`
- `README.md`
- `AGENTS.md`

**Steps:**

1. Initialise uv project: `uv init --python 3.12`
2. Create the full directory tree:
   - `agents/exploratory/`
   - `agents/verification/`
   - `agents/research_plan/`
   - `agents/implementation/`
   - `agents/orchestration/`
   - `shared/event_schemas/`
   - `shared/acap/`
   - `shared/arcadedb/`
   - `shared/openrouter/`
   - `shared/mcp/`
   - `schema/timeseries/`
   - `schema/graph/`
   - `schema/identity/`
   - `schema/migrations/`
   - `guardrails/profiles/`
   - `config/schema/`
   - `infra/render/`
   - `tests/unit/`
   - `tests/integration/`
   - `tests/agent/`
3. Add `__init__.py` to every Python package directory under `agents/` and `shared/`
4. Configure `ruff.toml`: `target-version='py312'`, `line-length=100`, `select=['E','F','I','N','UP','ANN']`, strict type annotation rules
5. Configure `mypy.ini`: `strict=true`, `python_version=3.12`, `warn_return_any=true`, `disallow_untyped_defs=true`
6. Configure `pyproject.toml` with dev dependencies: `ruff`, `mypy`, `pytest`, `pytest-cov`, `pytest-asyncio`
7. Add core runtime dependencies: `langgraph`, `langgraph-checkpoint-postgres`, `openai` (for OpenRouter compat), `httpx` for ArcadeDB HTTP, `pydantic>=2`, `langfuse`, `prometheus-client`, `presidio-analyzer`, `presidio-anonymizer`
8. Create `.gitignore` excluding: `.env`, `*.env`, `__pycache__`, `.mypy_cache`, `.ruff_cache`, `.venv`, `*.pyc`, `secrets/`
9. Write `AGENTS.md` at repository root — see AGENTS.md specification in TASK-03
10. Write `README.md` with: project overview, architecture summary link, required environment variables table, local development setup, running tests

**Done when:**
- `uv run ruff check .` exits 0 on the empty project
- `uv run mypy .` exits 0 on the empty project
- All specified directories exist
- `git status` shows a clean initial commit

---

### - [x] TASK-02: Define environment variable contract

**Inputs:**
- List of all secrets the platform requires

**Outputs:**
- `.env.example`
- `config/env.py`

**Steps:**

1. Create `.env.example` listing every required environment variable with placeholder values and a comment describing each. Never use real values. Include: `OPENROUTER_API_KEY`, `ARCADEDB_URL`, `ARCADEDB_USER`, `ARCADEDB_PASSWORD`, `POSTGRES_URL`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`, `CONFIG_PATH`, `RENDER_API_KEY`
2. Create `config/env.py` that reads all required environment variables using pydantic `BaseSettings`. Raise a clear `ValueError` at import time if any required variable is missing, naming the missing variable. No defaults for secrets — fail loudly.
3. Add `config/__init__.py` and export the settings object

**Done when:**
- `.env.example` contains all required variables with placeholder values only
- `config/env.py` raises `ValueError` with the variable name if any required env var is absent
- mypy passes on `config/env.py`

---

### - [x] TASK-03: Write AGENTS.md

**Inputs:**
- Repository structure from TASK-01
- Architecture understanding from requirements document

**Outputs:**
- `AGENTS.md`

**Steps:**

1. Write `AGENTS.md` at the repository root. This file governs how AI agents (including future implementation agents working on this codebase) behave when working in this repository.
2. Include the following sections:
   - **(1) Repository purpose** — This is a reusable agent platform, not a product. No project-specific code belongs here.
   - **(2) Directory map** — one line per top-level directory explaining what belongs there.
   - **(3) Autonomous modification rules** — agents MAY modify: `agents/`, `shared/`, `tests/unit/`, `tests/agent/` for implementation work. Agents MUST NOT autonomously modify: `schema/migrations/` (human review required for all migrations), `config/schema/` (configuration API is a public contract), `infra/` (infrastructure changes require human approval), `AGENTS.md` itself.
   - **(4) Event schema contract** — any code that emits events MUST use the canonical schemas in `shared/event_schemas/`. Every event MUST carry `agent_id`, `focus_id`, `mtp_version`, `timestamp`.
   - **(5) ACAP constraints** — this repository has its own ACAP. Agents working here may not make external network calls except to: OpenRouter API, ArcadeDB at `ARCADEDB_URL`, Postgres at `POSTGRES_URL`, Langfuse at `LANGFUSE_HOST`.
   - **(6) Test requirement** — all changes must pass: `ruff check`, `mypy --strict`, `pytest tests/unit/` with 80% coverage on modified modules.

**Done when:**
- `AGENTS.md` exists at repository root
- All six sections are present
- Autonomous modification rules explicitly list both allowed and prohibited directories

---

## Phase B — ArcadeDB Schema

### - [x] TASK-04: Define event log TimeSeries schema

**Inputs:**
- ArcadeDB documentation for TimeSeries types

**Outputs:**
- `schema/timeseries/event_log.py`
- `schema/timeseries/migrations/0001_create_event_log_types.sql`

**Steps:**

1. Create `schema/timeseries/event_log.py` defining Python dataclasses for four event types: `AgentSignal`, `AgentAction`, `AgentCheckpoint`, `CommitmentTransition`. Each must have: `event_type` (str), `ts` (datetime with nanosecond precision), `agent_id` (str), `focus_id` (str | None), `mtp_version` (str), `payload` (dict[str, Any]). `AgentSignal` additionally requires: `confidence` (float, 0.0–1.0), `novelty_flag` (bool), `stage` (Literal['observation', 'finding']), `claim` (str), `reasoning` (str), `sources` (list[str]).

   Note: `AgentFinding` has been merged into `AgentSignal` via the `stage` field. An `observation` is emitted by exploratory agents; a `finding` is emitted by the verification agent after challenge. This eliminates a redundant type with identical structure.

2. Create the SQL migration file creating four ArcadeDB TimeSeries types with correct retention:
   - `AgentSignals` RETENTION 30 DAYS
   - `AgentActions` RETENTION 30 DAYS
   - `AgentCheckpoints` RETENTION 180 DAYS
   - `CommitmentTransitions` RETENTION 0 (indefinite)

   Each type must define TAGS (`agent_id` STRING, `focus_id` STRING, `mtp_version` STRING) and FIELDS appropriate to the event type.
3. Add a migration runner function in `schema/timeseries/__init__.py` that executes the migration SQL idempotently (`CREATE TYPE IF NOT EXISTS` pattern)

**Done when:**
- All four Python dataclasses are fully typed and pass mypy strict
- Migration SQL file exists with all four `CREATE TIMESERIES TYPE` statements
- Migration runner function is idempotent — safe to call twice

---

### - [x] TASK-05: Define knowledge graph schema

**Inputs:**
- Knowledge graph node type specifications: `ProductStructure`, `DecisionRecord`, `InvestigationFinding`, `CompetitorCapability`, `CustomerTheme`, `CustomerSignal`

**Outputs:**
- `schema/graph/node_types.py`
- `schema/graph/migrations/0001_create_graph_schema.sql`

**Steps:**

1. Create `schema/graph/node_types.py` defining Python dataclasses for all six base node types. Every node type must include: `node_id` (str), `node_type` (str), `confidence` (float, 0.0–1.0), `initial_confidence` (float), `decay_rate` (float, per-day), `last_reinforced` (datetime), `revalidation_required` (bool). Define `decay_rate` constants per type:
   - `ProductStructure` = 0.001
   - `DecisionRecord` = 0.0001
   - `InvestigationFinding` = 0.005
   - `CompetitorCapability` = 0.01
   - `CustomerTheme` = 0.008
   - `CustomerSignal` = 0.1
2. Create the SQL migration creating ArcadeDB vertex types for each node type with the correct properties. Include edge types:
   - `DEPENDS_ON` (ProductStructure → ProductStructure)
   - `DECIDED_BY` (DecisionRecord → ProductStructure)
   - `INVESTIGATED` (InvestigationFinding → ProductStructure or DecisionRecord)
   - `OBSERVED` (CompetitorCapability → ProductStructure)
   - `REPORTED_BY` (CustomerTheme → CustomerSignal)
   - `NEGATIVE_KNOWLEDGE` (InvestigationFinding → InvestigationFinding with reason property)
3. Add a decay calculation function: `calculate_current_confidence(node: GraphNode, current_time: datetime) -> float` that applies the per-type decay rate. Flag for revalidation if confidence drops below 0.3.

**Done when:**
- All six node type dataclasses pass mypy strict
- Decay calculation function returns correct values for sample inputs
- Migration SQL exists for all vertex and edge types
- Unit test in `tests/unit/test_graph_schema.py` verifies decay calculation

---

### - [x] TASK-06: Define identity store, focus registry, and commitment registry schema

**Inputs:**
- MTP document structure, ACAP definition structure from requirements

**Outputs:**
- `schema/identity/models.py`
- `schema/identity/migrations/0001_create_identity_schema.sql`

**Steps:**

1. Create `schema/identity/models.py` with Pydantic v2 models for:
   - `MTPDocument` (`mtp_id`: str, `version`: str, `purpose`: str, `constraints`: list[str], `intent_description`: str, `created_at`: datetime, `created_by`: str)
   - `ACAPDefinition` (`acap_id`: str, `agent_type`: Literal['exploratory','verification','research_plan','implementation','orchestration'], `permitted_tools`: list[str], `permitted_mcp_connections`: list[str], `permitted_event_types`: list[str], `forbidden_targets`: list[str], `resource_ceiling`: ResourceCeiling)
   - `ResourceCeiling` (`max_tokens_per_run`: int, `max_duration_seconds`: int, `max_mcp_reads_per_run`: int)
   - `FocusRecord` (`focus_id`: str, `domain`: str, `description`: str, `status`: Literal['active','closed'], `created_at`: datetime, `created_by`: str, `signal_count`: int)
   - `CommitmentRecord` (`commitment_id`: str, `focus_id`: str, `status`: Literal['pending','active','pending_approval','approved','rejected','deferred','complete','stalled','escalated'], `created_at`: datetime, `domain`: str, `priority_signal`: float, `checkpoint`: CognitiveCheckpoint | None, `assigned_agent_id`: str | None)
   - `CognitiveCheckpoint` (`hypotheses_investigated`: list[HypothesisRecord], `current_best_understanding`: str, `plan`: str | None, `recommended_next_action`: str, `checkpoint_at`: datetime)
   - `HypothesisRecord` (`hypothesis`: str, `conclusion`: Literal['confirmed','rejected','pending'], `evidence`: str)
2. Create the SQL migration creating ArcadeDB document types for `MTPDocument`, `ACAPDefinition`, `FocusRecord`, and `CommitmentRecord` with appropriate indexes.
3. Add a schema version constant `VERSION = '1.0'` to `schema/identity/__init__.py`

**Done when:**
- All Pydantic models pass validation with sample data
- mypy strict passes on `schema/identity/models.py`
- Unit test verifies `CognitiveCheckpoint` serialises and deserialises correctly

---

### - [x] TASK-07: Write schema migration runner

**Inputs:**
- TASK-04, TASK-05, TASK-06 complete

**Outputs:**
- `schema/migrate.py`

**Steps:**

1. Create `schema/migrate.py` as the single entrypoint for running all migrations. It must:
   1. Connect to ArcadeDB using credentials from `env.py`
   2. Run time-series migrations from `schema/timeseries/migrations/` in filename order
   3. Run graph migrations from `schema/graph/migrations/` in filename order
   4. Run identity migrations from `schema/identity/migrations/` in filename order
   5. Track applied migrations in an ArcadeDB document type called `SchemaMigration` (`migration_id`: str, `applied_at`: datetime)
   6. Skip already-applied migrations
   7. Fail immediately on any migration error, logging the failing migration filename
2. Add a CLI entry: `python -m schema.migrate` that can be called from deployment scripts
3. Enforce migration immutability: the runner must compute a SHA-256 hash of each migration file and store it in `SchemaMigration`. On subsequent runs, if a previously applied migration's hash has changed, raise an error.

**Done when:**
- `python -m schema.migrate` against a fresh ArcadeDB instance applies all migrations and exits 0
- Running it a second time skips all migrations and exits 0
- Modifying a migration file's content after it has been applied causes the runner to raise an error on next run
- Unit test mocks ArcadeDB and verifies idempotency and hash enforcement

---

## Phase C — Shared Libraries

### - [x] TASK-08: Build ArcadeDB client

**Inputs:**
- ArcadeDB HTTP API documentation
- TASK-04, TASK-05, TASK-06 schemas

**Outputs:**
- `shared/arcadedb/__init__.py`
- `shared/arcadedb/client.py`
- `shared/arcadedb/timeseries.py`
- `shared/arcadedb/graph.py`
- `shared/arcadedb/identity.py`

**Steps:**

1. Create `shared/arcadedb/client.py` with an `ArcadeDBClient` class using `httpx.AsyncClient`. Methods: `execute_query(database: str, query: str, params: dict | None) -> list[dict]`, `execute_command(database: str, command: str) -> dict`, `health_check() -> bool`. All methods are async. Handle ArcadeDB HTTP error responses and raise typed exceptions.
2. Create `shared/arcadedb/timeseries.py` with functions: `emit_event(client, event: AgentSignal | AgentAction | AgentCheckpoint | CommitmentTransition) -> None`, `poll_events(client, event_type: str, since_ts: datetime, focus_id: str | None, limit: int = 100) -> list[dict]`. The poll function uses cursor-based queries (`WHERE ts > :since_ts`) and must not perform full table scans.
3. Create `shared/arcadedb/graph.py` with functions: `upsert_node(client, node: GraphNode) -> str`, `get_node(client, node_id: str) -> GraphNode | None`, `traverse_from(client, node_id: str, max_depth: int = 3) -> list[GraphNode]`, `reinforce_node(client, node_id: str) -> None`, `flag_for_revalidation(client, node_id: str) -> None`, `apply_decay_all(client) -> int`.
4. Create `shared/arcadedb/identity.py` with functions: `load_mtp(client) -> MTPDocument`, `load_acap(client, agent_type: str) -> ACAPDefinition`, `get_focus(client, focus_id: str) -> FocusRecord | None`, `list_active_focuses(client) -> list[FocusRecord]`, `get_commitment(client, commitment_id: str) -> CommitmentRecord | None`, `create_commitment(client, commitment: CommitmentRecord) -> str`, `update_commitment(client, commitment_id: str, updates: dict) -> None`, `write_checkpoint(client, commitment_id: str, checkpoint: CognitiveCheckpoint) -> None`

**Done when:**
- mypy strict passes on all files
- Unit tests mock httpx and verify correct query construction for `poll_events` (partition pruning query pattern)
- Unit test verifies `reinforce_node` resets `last_reinforced` timestamp

---

### - [x] TASK-09: Build OpenRouter client with agent-role routing

**Inputs:**
- OpenRouter API documentation
- Model assignments: exploratory/orchestration=`deepseek/deepseek-v4-flash`, verification=`qwen/qwen3.7-plus`, research_plan/implementation=`deepseek/deepseek-v4-pro`

**Outputs:**
- `shared/openrouter/__init__.py`
- `shared/openrouter/client.py`
- `shared/openrouter/models.py`

**Steps:**

1. Create `shared/openrouter/models.py` defining:
   - `AgentRole` enum (`EXPLORATORY`, `VERIFICATION`, `RESEARCH_PLAN`, `IMPLEMENTATION`, `ORCHESTRATION`)
   - `ModelFamily` enum (`DEEPSEEK`, `QWEN`, `KIMI`)
   - `MODEL_ASSIGNMENTS` dict mapping `AgentRole` to model string and `ModelFamily`
   - `PROVIDER_ROUTING` dict mapping `AgentRole` to OpenRouter provider config:
     - exploratory/orchestration: `order=['DeepSeek','DeepInfra']`, `allow_fallbacks=True`
     - research_plan/implementation: `only=['DeepSeek']`, `allow_fallbacks=False`, `enable_caching=True`
     - verification: `only=['Alibaba']`, `allow_fallbacks=True`
2. Create `shared/openrouter/client.py` with `OpenRouterClient` class. Key method: `complete(role: AgentRole, messages: list[dict], system: str, max_tokens: int = 4096, enable_caching: bool = False) -> str`. Must:
   1. Look up model and provider routing from `MODEL_ASSIGNMENTS` and `PROVIDER_ROUTING`
   2. Build the provider object for the OpenRouter request body
   3. Enable prompt caching headers for `RESEARCH_PLAN` and `IMPLEMENTATION` roles
   4. Raise `ModelFamilyError` if a verification call is attempted with the same model family as a supplied `originating_model_family` parameter
3. Add `enforce_independence(requesting_role: AgentRole, originating_model_family: ModelFamily) -> None` that raises `ModelFamilyError` if `requesting_role=VERIFICATION` and `originating_model_family` matches the verification model's family.

**Done when:**
- `enforce_independence` raises `ModelFamilyError` when verification and originating agent share a model family
- `enforce_independence` does not raise when model families differ
- Unit tests verify provider routing objects are built correctly for each agent role
- mypy strict passes

---

### - [x] TASK-10: Build ACAP enforcer

**Inputs:**
- TASK-06 `ACAPDefinition` model

**Outputs:**
- `shared/acap/__init__.py`
- `shared/acap/enforcer.py`
- `shared/acap/exceptions.py`

**Steps:**

1. Create `shared/acap/exceptions.py` with: `ACAPViolationError(action: str, reason: str, agent_id: str, focus_id: str)`, `ScopeViolationError` (subclass of `ACAPViolationError`).
2. Create `shared/acap/enforcer.py` with `ACAPEnforcer` class. Constructor takes `ACAPDefinition` and `ArcadeDBClient`. Methods:
   - `check_tool(tool_name: str) -> None`
   - `check_mcp_connection(server_url: str) -> None`
   - `check_event_type(event_type: str) -> None`
   - `check_resource_ceiling(tokens_used: int, duration_seconds: float, mcp_reads: int) -> None`
   - `log_violation(violation: ACAPViolationError, agent_id: str, focus_id: str, mtp_version: str) -> None`
3. All `check_` methods must call `log_violation` before raising.

**Done when:**
- `check_tool` raises `ACAPViolationError` for unlisted tools
- `check_mcp_connection` raises `ACAPViolationError` for unlisted connections
- `log_violation` emits an event to the event log before the exception propagates
- Unit tests cover all check methods and verify `log_violation` is always called on violation
- mypy strict passes

---

### - [x] TASK-11: Build event schema validator

**Inputs:**
- TASK-04 event type dataclasses

**Outputs:**
- `shared/event_schemas/__init__.py`
- `shared/event_schemas/validator.py`

**Steps:**

1. Create `shared/event_schemas/validator.py` with: `validate_event(event: dict) -> AgentSignal | AgentAction | AgentCheckpoint | CommitmentTransition` that validates the event dict against the correct typed dataclass based on the `event_type` field. Raise `EventSchemaError` if: `event_type` is missing, `event_type` is not one of the four valid types, any required field is missing or wrongly typed, `confidence` is outside 0.0–1.0 range.
2. Create a `check_required_fields(event: dict) -> None` helper that verifies `agent_id`, `mtp_version`, and `ts` are all present and non-empty on every event regardless of type. `focus_id` is optional (free exploration workers emit without one).
3. Export a single `emit_validated(event: dict, client: ArcadeDBClient) -> None` function that validates then emits.

**Done when:**
- `validate_event` correctly parses all four event types from valid dicts
- `validate_event` raises `EventSchemaError` for missing required fields
- `validate_event` raises `EventSchemaError` for confidence outside 0.0–1.0
- Unit tests cover all four event types and all error cases
- mypy strict passes

---

### - [x] TASK-12: Build MCP connection manager

**Inputs:**
- TASK-10 `ACAPEnforcer`

**Outputs:**
- `shared/mcp/__init__.py`
- `shared/mcp/manager.py`

**Steps:**

1. Create `shared/mcp/manager.py` with `MCPConnectionManager` class. Constructor takes `ACAPDefinition` and `ArcadeDBClient`. Method: `read(server_url: str, resource_path: str, params: dict | None = None) -> str`. The read method must:
   1. Call `enforcer.check_mcp_connection(server_url)` before making any network call
   2. Make the MCP read request via httpx
   3. Log an `AgentAction` event via `emit_validated`
   4. Return the raw response content as a string
2. The manager must never cache MCP responses.
3. Add a `list_permitted_connections() -> list[str]` method.

**Done when:**
- `read()` raises `ACAPViolationError` for unpermitted servers before any network call
- `read()` emits an `AgentAction` event for every successful read
- Unit tests mock httpx and verify ACAP check happens before network call
- mypy strict passes

---

### - [x] TASK-13: Build configuration loader

**Inputs:**
- TASK-06 schema models

**Outputs:**
- `config/schema/v1.py`
- `config/schema/mtp_schema.yaml`
- `config/schema/acap_schema.yaml`
- `config/schema/mandate_schema.yaml`
- `shared/config/__init__.py`
- `shared/config/loader.py`

**Steps:**

1. Create JSON Schema (as YAML) files for `mtp_schema.yaml`, `acap_schema.yaml`, and `mandate_schema.yaml`. These are versioned public contracts.
2. Create `config/schema/v1.py` that exposes the schemas as Python dicts for programmatic validation.
3. Create `shared/config/loader.py` with `load_project_config(config_path: str) -> ProjectConfig`.
4. `ProjectConfig` must have: `mtp`: `MTPDocument`, `acap_overrides`: `dict[str, dict]`, `mandates`: `list[MandateDefinition]`. `MandateDefinition`: `name` (str), `domain` (str), `polling_interval_minutes` (int), `signal_threshold` (float), `observation_modes` (list[Literal['web_search','mcp']]).

   Note: `search_queries` has been removed from `MandateDefinition`. The mandate defines the domain and observation capability; active focuses and MTP purpose provide the direction at runtime.

**Done when:**
- `load_project_config` succeeds on the reference config created in TASK-32
- `load_project_config` raises `ConfigValidationError` with field path on invalid config
- mypy strict passes
- Unit tests cover valid config, missing fields, and wrong types

---

## Phase D — Schema Migration

### - [x] TASK-14-M: Migrate completed code to revised schema

**Inputs:**
- TASK-04 through TASK-13 complete
- This revised plan

**Outputs:**
- Updated `schema/timeseries/event_log.py`
- Updated `schema/timeseries/migrations/0002_revise_event_log_types.sql`
- Updated `schema/identity/models.py`
- Updated `schema/identity/migrations/0002_add_focus_commitment.sql`
- Updated `shared/arcadedb/identity.py`
- Updated `shared/event_schemas/validator.py`
- Updated `shared/acap/exceptions.py`
- Updated `shared/openrouter/models.py`
- Updated `agents/exploratory/state.py`

**Steps:**

1. Update `schema/timeseries/event_log.py`: merge `AgentFinding` into `AgentSignal` by adding `stage: Literal['observation','finding']`, `claim: str`, `reasoning: str`, `sources: list[str]` fields. Remove `AgentFinding` class. Add `WorkerStarted` and `WorkerCompleted` event types to `AgentAction` payload schema (no new TimeSeries type needed — use `AgentActions`).
2. Create migration `0002_revise_event_log_types.sql`: add `stage`, `claim`, `reasoning`, `sources` fields to `AgentSignals` TimeSeries type. Drop `AgentFindings` TimeSeries type if it exists.
3. Update `schema/identity/models.py`: rename `ObjectiveRecord` to `CommitmentRecord`, rename `objective_id` fields to `commitment_id`, add `FocusRecord` model, update `CommitmentRecord.status` to include `'pending_approval'`, `'approved'`, `'rejected'`, `'deferred'`. Add `plan: str | None` field to `CognitiveCheckpoint`.
4. Create migration `0002_add_focus_commitment.sql`: create `FocusRecord` document type, rename `ObjectiveRecord` to `CommitmentRecord`, add new status values and fields.
5. Update all references throughout `shared/` and `agents/exploratory/` to use `focus_id` instead of `objective_id`, `CommitmentRecord` instead of `ObjectiveRecord`, and the revised event types.
6. Update `shared/openrouter/models.py`: add `RESEARCH_PLAN` and `IMPLEMENTATION` to `AgentRole`, add `KIMI` to `ModelFamily`, rename `OBJECTIVE` role to `RESEARCH_PLAN`.

**Done when:**
- `schema/migrate.py` applies both migrations idempotently
- `validate_event` handles `AgentSignal` with `stage` field correctly
- `validate_event` rejects events with `event_type='AgentFinding'` (removed type)
- All references to `objective_id` in completed code replaced with `focus_id`
- mypy strict passes across all updated files
- Unit tests updated to match revised schemas

---

## Phase E — Agent Implementations

### - [x] TASK-14 (now TASK-15): Build exploratory agent

*Previously TASK-14 — completed. Directory and entry point reference `agents/exploratory/`. No renumbering of files required.*

**Design: Two exploratory agent modes**

1. **Free explorer** (`agent_type: "free"`) — investigates a domain with no specific focus. Oriented toward the MTP and active focuses as context. Looks for what is not currently being looked for.
2. **Focus follower** (`agent_type: "focus"`) — spawned against a specific `FocusRecord`. Oriented toward finding observations that create leverage toward that focus.

Both modes use the same tools (`search_graph`, `search_signals`, `emit_signal`) via `ChatOpenRouter` with `bind_tools()` and `ToolNode`.

**System prompts:**

*Free explorer:*
```
You are a scout operating in the {domain} domain.

Organisational purpose: {mtp_purpose}

Constraints you must never violate:
{mtp_constraints}

What we are currently pursuing:
{active_focuses_summary}

This is context, not direction. You are looking for what is happening in this
domain that the organisation should know about, is not currently looking for,
and would care about given its purpose.

You have access to: {permitted_tools}

For each finding, state:
- What you observed
- Why it matters given the organisational purpose
- Whether it suggests a new focus, or challenges an assumption behind an existing one
- Your confidence and the basis for it

Contradictions and surprises are more valuable than confirmations.
```

*Focus follower:*
```
You are a scout operating in the {domain} domain.

Organisational purpose: {mtp_purpose}

Constraints you must never violate:
{mtp_constraints}

Your focus:
{focus_description}

Find observations that create leverage toward this focus — things that would
move it forward, remove a blocker, or reveal that its assumptions are wrong.

You have access to: {permitted_tools}

For each finding, state:
- What you observed
- How it relates to the focus
- Whether it confirms, extends, or contradicts current understanding
- Your confidence and the basis for it

When you have exhausted productive lines of investigation, stop.
```

**Steps:**

*(Completed — preserved from original TASK-14. State uses `focus_id` per TASK-14-M migration.)*

**Done when:**
- *(Completed)*

---

### - [ ] TASK-15: Build verification agent

**Inputs:**
- TASK-08, TASK-09, TASK-10, TASK-11 complete
- TASK-14-M schema migration complete

**Outputs:**
- `agents/verification/__init__.py`
- `agents/verification/nodes.py`
- `agents/verification/state.py`
- `agents/verification/graph.py`
- `agents/verification/__main__.py`

**Design:**

The verification agent is an independent background worker that polls the event log for `AgentSignal` events with `stage='observation'` and `confidence >= signal_threshold` that have not yet been verified. For each, it challenges the claim adversarially using a different model family and emits a new `AgentSignal` with `stage='finding'`.

This agent does not receive instructions from any other agent. It discovers work by polling.

**Steps:**

1. Create `agents/verification/state.py` with `VerificationState` TypedDict: `signal` (`AgentSignal`), `originating_model_family` (`ModelFamily`), `mtp_version` (str), `agent_id` (str), `focus_id` (str | None), `verdict` (Literal['confirmed','contradicted','inconclusive'] | None), `verdict_confidence` (float | None), `verdict_rationale` (str | None).

2. Create `agents/verification/nodes.py` with async node functions:
   - `poll_for_observations(state)` — queries ArcadeDB `AgentSignals` for unverified `stage='observation'` signals above the configured `signal_threshold`. Uses cursor-based polling with `last_cursor` persisted between runs. Returns the oldest unprocessed signal or sets `completed=True` if none found.
   - `enforce_independence(state)` — calls `enforce_independence(AgentRole.VERIFICATION, state['originating_model_family'])`. Raises `ModelFamilyError` if same family.
   - `investigate(state)` — uses OpenRouter `VERIFICATION` role with adversarial system prompt to challenge the signal's `claim`. Queries ArcadeDB knowledge graph and permitted MCP connections for contrary evidence. System prompt: *"Your task is to determine whether the following claim is false. Assume it is wrong and attempt to disprove it. Only conclude it is confirmed if you cannot find evidence against it. Claim: {claim}. Reasoning given: {reasoning}."*
   - `emit_finding(state)` — emits a new `AgentSignal` with `stage='finding'`, `claim` (same as original or refined), `verdict`, `verdict_confidence`, `verdict_rationale`, `sources` (combined from original signal and investigation).

3. Create `agents/verification/graph.py` as a compiled `StateGraph`: `poll_for_observations` → conditional edge (if signal found → `enforce_independence` → `investigate` → `emit_finding` → loop back to `poll_for_observations`, else → `END`).

4. Create `agents/verification/__main__.py` entry point: `run_verification_agent(config_path: str) -> None` that loops continuously with a configurable polling interval (default 60 seconds).

**Done when:**
- Agent polls ArcadeDB independently with cursor-based state
- `enforce_independence` raises `ModelFamilyError` when model families match
- `investigate` system prompt is adversarial
- `emit_finding` always emits a `stage='finding'` signal before the loop continues
- Agent runs standalone: `python -m agents.verification`
- mypy strict passes

---

### - [ ] TASK-16: Build research/plan agent

**Inputs:**
- TASK-08, TASK-09, TASK-10, TASK-11, TASK-12 complete
- TASK-14-M schema migration complete

**Outputs:**
- `agents/research_plan/__init__.py`
- `agents/research_plan/nodes.py`
- `agents/research_plan/state.py`
- `agents/research_plan/graph.py`
- `agents/research_plan/__main__.py`

**Design:**

The research/plan agent polls for `AgentSignal` events with `stage='finding'` and `verdict='confirmed'` where no `CommitmentRecord` yet exists for the signal's `focus_id`. When it finds one, it creates a `CommitmentRecord`, runs a research loop to understand the problem space deeply, and produces a plan. The plan is written to a `CognitiveCheckpoint` on the commitment and the commitment is marked `pending_approval`. A human then reviews the plan before implementation proceeds.

This agent earns being a LangGraph graph because the research loop has genuine internal complexity — it reads the knowledge graph, reads artifacts, reads the event delta, forms hypotheses, checks hypotheses, and may loop back if understanding is insufficient.

**Steps:**

1. Create `agents/research_plan/state.py` with `ResearchPlanState` TypedDict: `signal` (`AgentSignal`), `commitment` (`CommitmentRecord`), `mtp_version` (str), `agent_id` (str), `graph_context` (list[GraphNode]), `artifact_context` (list[str]), `event_delta` (list[dict]), `hypotheses` (list[HypothesisRecord]), `current_understanding` (str | None), `plan` (str | None), `iteration` (int), `max_iterations` (int), `completed` (bool).

2. Create `agents/research_plan/nodes.py` with async node functions:
   - `poll_for_findings(state)` — queries ArcadeDB `AgentSignals` for verified `stage='finding'` signals with no corresponding `CommitmentRecord`. Uses cursor-based polling.
   - `create_commitment(state)` — creates a `CommitmentRecord` with `status='active'` for the signal's `focus_id`.
   - `traverse_graph(state)` — queries ArcadeDB graph from the focus domain node outward `max_depth=3`.
   - `read_artifacts(state)` — uses `MCPConnectionManager` to read structural artifacts identified in `graph_context`.
   - `read_event_delta(state)` — polls event log for signals in this domain since the last checkpoint timestamp.
   - `form_understanding(state)` — uses OpenRouter `RESEARCH_PLAN` role to synthesise `graph_context`, `artifact_context`, and `event_delta` into hypotheses and a current best understanding.
   - `write_checkpoint(state)` — writes `CognitiveCheckpoint` to ArcadeDB. Must always execute even if a previous node raises.
   - `produce_plan(state)` — uses OpenRouter `RESEARCH_PLAN` role to produce a concrete, step-by-step implementation plan from the current understanding. Writes plan to checkpoint.
   - `mark_pending_approval(state)` — updates `CommitmentRecord` status to `pending_approval`.

3. Create `agents/research_plan/graph.py`: `poll_for_findings` → conditional edge (if finding → `create_commitment` → `traverse_graph` → `read_artifacts` → `read_event_delta` → `form_understanding` → `write_checkpoint` → conditional edge (if understanding sufficient or max_iterations reached → `produce_plan` → `mark_pending_approval` → loop to `poll_for_findings`, else → loop back to `traverse_graph`), else → `END`).

4. Compile with `PostgresSaver` checkpointer — this agent may run for extended periods and must survive restarts.

5. Create `agents/research_plan/__main__.py` entry point: `run_research_plan_agent(config_path: str) -> None`.

**Done when:**
- Agent polls independently and creates commitments without external orchestration
- Research loop traverses graph → artifacts → events → understanding in correct order
- `write_checkpoint` executes even when a preceding node raises
- Commitment is marked `pending_approval` with plan in checkpoint before agent moves on
- `PostgresSaver` checkpointer is configured and survives a simulated restart
- Agent runs standalone: `python -m agents.research_plan`
- mypy strict passes

---

### - [ ] TASK-17: Build implementation agent

**Inputs:**
- TASK-08, TASK-09, TASK-10, TASK-11, TASK-12 complete
- TASK-14-M schema migration complete

**Outputs:**
- `agents/implementation/__init__.py`
- `agents/implementation/nodes.py`
- `agents/implementation/state.py`
- `agents/implementation/graph.py`
- `agents/implementation/__main__.py`

**Design:**

The implementation agent polls the commitment registry for `CommitmentRecord` entries with `status='approved'`. When it finds one, it reads the plan from the `CognitiveCheckpoint`, executes it step by step, runs tests, and marks the commitment complete or stalled.

This agent must survive restarts mid-execution — `PostgresSaver` checkpointing is mandatory.

**Steps:**

1. Create `agents/implementation/state.py` with `ImplementationState` TypedDict: `commitment` (`CommitmentRecord`), `mtp_version` (str), `agent_id` (str), `plan` (str), `checkpoint` (`CognitiveCheckpoint`), `actions_taken` (list[str]), `files_modified` (list[str]), `test_results` (dict[str, Any] | None), `status` (Literal['in_progress','complete','failed']).

2. Create `agents/implementation/nodes.py` with async node functions:
   - `poll_for_approved(state)` — queries commitment registry for `status='approved'` commitments. Uses cursor-based polling.
   - `load_plan(state)` — reads the execution plan from the commitment's `CognitiveCheckpoint`.
   - `execute_plan(state)` — uses OpenRouter `IMPLEMENTATION` role to execute the plan step-by-step, emitting `AgentAction` events for each file operation. Enforces ACAP boundaries on all operations.
   - `run_tests(state)` — executes test suite and captures results.
   - `write_outcome(state)` — marks commitment `complete` on success or `stalled` on failure. Writes final checkpoint.
   - `promote_findings(state)` — emits `AgentSignal` events with `stage='finding'` for durable knowledge discovered during implementation, for knowledge graph promotion.

3. Create `agents/implementation/graph.py`: `poll_for_approved` → conditional edge (if commitment found → `load_plan` → `execute_plan` → `run_tests` → `write_outcome` → `promote_findings` → loop to `poll_for_approved`, else → `END`). Compile with `PostgresSaver` checkpointer.

4. Create `agents/implementation/__main__.py` entry point.

5. The agent must only process commitments with `status='approved'`. Validate at `load_plan` and raise if status has changed since polling.

**Done when:**
- Agent polls independently without external orchestration
- `execute_plan` enforces ACAP boundaries — unpermitted operations raise `ACAPViolationError`
- Agent only processes approved commitments
- All file operations are logged as `AgentAction` events
- On completion, commitment status is updated to `complete`
- On failure, checkpoint is written and commitment is marked `stalled`
- `PostgresSaver` checkpointer survives a simulated mid-execution restart
- Agent runs standalone: `python -m agents.implementation`
- mypy strict passes

---

### - [ ] TASK-18: Build knowledge promotion logic

**Inputs:**
- TASK-05 graph schema
- TASK-08 ArcadeDB client

**Outputs:**
- `shared/promotion/__init__.py`
- `shared/promotion/classifier.py`

**Steps:**

1. Create `shared/promotion/classifier.py` with `classify_for_promotion(signal: AgentSignal, existing_nodes: list[GraphNode]) -> PromotionDecision`. `PromotionDecision` is a dataclass with: `action` (Literal['discard','promote_durable','promote_medium','reinforce','return_to_log']), `node_type` (str | None), `confidence` (float | None), `rationale` (str).

2. Classification rules:
   - If `signal.payload` contains `'hypothesis_conclusion': 'rejected'` → `action='promote_durable'`, `node_type='InvestigationFinding'` with `NEGATIVE_KNOWLEDGE` edge
   - If `signal.payload` contains `'structural_discovery'` → `action='promote_durable'`, `node_type='ProductStructure'`
   - If signal matches an existing node (semantic similarity) → `action='reinforce'`
   - If `signal.confidence < 0.5` → `action='return_to_log'`
   - If signal contains operational state → `action='discard'`
   - Default for customer/competitor findings → `action='promote_medium'`

3. Create `promote_signals(client: ArcadeDBClient, signals: list[AgentSignal]) -> PromotionSummary` that classifies each signal and executes the correct ArcadeDB operation.

**Done when:**
- `classify_for_promotion` returns correct action for all five cases
- Unit tests cover all five classification outcomes
- mypy strict passes

---

## Phase F — Orchestration

### - [ ] TASK-19: Build orchestration agent

**Inputs:**
- TASK-08, TASK-18 complete

**Outputs:**
- `agents/orchestration/__init__.py`
- `agents/orchestration/nodes.py`
- `agents/orchestration/state.py`
- `agents/orchestration/graph.py`
- `agents/orchestration/__main__.py`

**Design:**

The orchestration agent is intentionally thin. It does not coordinate agent execution — each agent polls independently. Its responsibilities are:

1. **Health monitoring** — detect workers that have emitted `WorkerStarted` but not `WorkerCompleted` within the expected window. Escalate stalled workers.
2. **Commitment health** — detect commitments with no checkpoint within the stall window. Escalate stalled commitments.
3. **Knowledge graph promotion** — trigger `promote_signals()` for signals from closed commitments.
4. **Decay maintenance** — periodically run `apply_decay_all()` to decay knowledge graph confidence scores.
5. **Escalation** — write escalation events for ACAP violations, resource ceiling breaches, and stalled agents/commitments.

The orchestration agent does NOT: spawn other agents, embed subgraphs, route signals, or make content decisions.

**Steps:**

1. Create `agents/orchestration/state.py` with `OrchestrationState` TypedDict: `mtp_version` (str), `agent_id` (str), `active_workers` (list[dict]), `stalled_commitments` (list[str]), `escalations_pending` (list[str]), `promotion_pending` (list[AgentSignal]), `last_decay_run` (datetime | None).

2. Create `agents/orchestration/nodes.py`:
   - `check_worker_health(state)` — polls `AgentActions` for `WorkerStarted` events without a matching `WorkerCompleted` within the configured window. Adds stalled workers to `escalations_pending`.
   - `check_commitment_health(state)` — queries commitment registry for `status='active'` commitments with no checkpoint in the last N minutes.
   - `run_promotion(state)` — calls `promote_signals()` for signals from commitments that have moved to `complete` since the last promotion run.
   - `run_decay(state)` — calls `apply_decay_all()` if more than 24 hours since `last_decay_run`.
   - `escalate(state)` — writes escalation events for all items in `escalations_pending`.

3. Create `agents/orchestration/graph.py`: `check_worker_health` → `check_commitment_health` → `run_promotion` → `run_decay` → `escalate` → `END`. The orchestration agent runs on a schedule (every 5 minutes) rather than continuously.

4. Create `agents/orchestration/__main__.py` entry point.

**Done when:**
- Orchestration agent detects a stalled worker and writes an escalation event
- `run_promotion` calls `promote_signals` for completed commitment signals
- `run_decay` only runs when 24+ hours have elapsed since last run
- Agent runs standalone: `python -m agents.orchestration`
- mypy strict passes

---

## Phase G — Human Approval UI

### - [ ] TASK-20: Build human approval UI

**Inputs:**
- TASK-16 research/plan agent complete (produces `pending_approval` commitments)
- TASK-17 implementation agent complete (polls for `approved` commitments)

**Outputs:**
- `ui/` directory with React application
- `ui/package.json`
- `ui/src/components/Dashboard.tsx`
- `ui/src/components/ApprovalQueue.tsx`
- `ui/src/components/ApprovalCard.tsx`
- `ui/src/components/WorkerStatus.tsx`
- `ui/src/components/CommitmentList.tsx`
- `ui/src/api/arcadedb.ts`

**Steps:**

1. Create `ui/` directory with a React application.
2. Create `ui/package.json` with dependencies: `react`, `axios`.
3. Create `ui/src/api/arcadedb.ts` with functions to:
   - Query commitments by status
   - Query active workers (via `WorkerStarted`/`WorkerCompleted` event log)
   - Update commitment approval decisions
4. Create `ui/src/components/Dashboard.tsx` as the root component with three panels:
   - **Active Workers** — lists workers with `WorkerStarted` but no `WorkerCompleted`, showing agent type, start time, and domain.
   - **Commitments in Progress** — lists active commitments with status, domain, last checkpoint time.
   - **Recently Completed** — lists commitments that moved to `complete` in the last 24 hours.
5. Create `ui/src/components/ApprovalQueue.tsx` — displays commitments with `status='pending_approval'` with plan details and context.
6. Create `ui/src/components/ApprovalCard.tsx` — renders a single pending commitment with: domain, focus description, plan from checkpoint, research context (hypotheses investigated, current understanding), approve/reject/defer buttons with optional comments.
7. Implement approval workflow: approve → `status='approved'`, reject → `status='rejected'`, defer → `status='deferred'`. Store `approval_metadata` (reviewer_id, decided_at, comments) on the commitment.
8. Add simple username/password authentication for v1.

**Done when:**
- Dashboard displays active workers, in-progress commitments, and completed commitments
- Approval queue shows pending plans with full research context
- Human can approve, reject, or defer with optional comments
- Approval decision is stored in ArcadeDB commitment registry
- Implementation agent processes approved commitments
- README includes instructions for running the UI locally

---

## Phase H — Guardrails

### - [ ] TASK-21: Build guardrail ensemble

**Inputs:**
- WildGuard, Granite Guardian, ShieldGemma model access (via hosted API or HuggingFace)
- Presidio

**Outputs:**
- `guardrails/__init__.py`
- `guardrails/ensemble.py`
- `guardrails/profiles/default.yaml`

**Steps:**

1. Create `guardrails/profiles/default.yaml` defining:
   - `high_stakes_categories` (list — OR logic: block if either model flags)
   - `soft_categories` (list — AND logic: block only if both models flag)
2. Create `guardrails/ensemble.py` with `GuardrailEnsemble` class. Method: `check(content: str, agent_id: str, focus_id: str | None, mtp_version: str) -> GuardrailResult`. `GuardrailResult`: `passed` (bool), `violations` (list[GuardrailViolation]), `redacted_content` (str | None).
3. `check()` pipeline:
   1. ShieldGemma pre-screen — if flagged for obvious harm, return immediately
   2. WildGuard input classification
   3. Granite Guardian output validation
   4. Apply OR/AND logic from profile
   5. If passed, run Presidio PII redaction
   6. If blocked, emit `AgentAction` event with violation details
4. `GUARDRAILS_MODE` env var: `'live'`, `'stub_pass'`, `'stub_block'`.
5. Create `@guardrailed(agent_id, focus_id, mtp_version)` decorator.

**Done when:**
- `check()` returns `passed=False` for a known prompt injection payload
- `check()` returns `redacted_content` with PII removed
- Violation events are emitted to ArcadeDB
- `GUARDRAILS_MODE='stub_pass'` bypasses all API calls
- mypy strict passes

---

## Phase I — Observability

### - [ ] TASK-22: Configure Langfuse OpenTelemetry export

**Inputs:**
- Langfuse Cloud account and API keys

**Outputs:**
- `shared/observability/__init__.py`
- `shared/observability/tracing.py`

**Steps:**

1. Create `shared/observability/tracing.py`. Configure Langfuse OTel SDK. Create `configure_tracing(agent_type: str, agent_id: str, focus_id: str | None, mtp_version: str) -> None`.
2. Create `trace_llm_call(model: str, role: str) -> Iterator[Span]` context manager recording: model, input/output token counts, estimated cost, latency.
3. Wrap `OpenRouterClient.complete()` automatically.
4. Missing Langfuse credentials → warning + no-op tracer, not a crash.

**Done when:**
- Test LLM call produces a trace in Langfuse Cloud with model, tokens, cost, latency
- `agent_type`, `agent_id`, `focus_id`, `mtp_version` appear as trace attributes
- Missing credentials produce a warning not a crash
- mypy strict passes

---

### - [ ] TASK-23: Configure Prometheus custom metrics

**Inputs:**
- `prometheus-client` library

**Outputs:**
- `shared/observability/metrics.py`

**Steps:**

1. Create `shared/observability/metrics.py` defining custom metrics:
   - `signal_emission_total` (Counter, labels: `agent_id`, `domain`, `stage`)
   - `checkpoint_write_total` (Counter, labels: `commitment_id`)
   - `verification_verdict_total` (Counter, labels: `verdict`)
   - `commitment_completion_total` (Counter, labels: `domain`)
   - `escalation_total` (Counter, labels: `reason`)
   - `worker_active_gauge` (Gauge, labels: `agent_type`)
2. Export increment/set functions for each.
3. Start Prometheus HTTP server on port 9090 when `METRICS_ENABLED=true`.

**Done when:**
- All metric types are registered and incrementable
- Metrics server starts on port 9090 when `METRICS_ENABLED=true`
- Unit test verifies each function updates the correct metric
- mypy strict passes

---

## Phase J — Tests

### - [ ] TASK-24: Write unit tests for shared libraries

**Inputs:**
- TASK-08 through TASK-13, TASK-14-M complete

**Outputs:**
- `tests/unit/test_arcadedb_client.py`
- `tests/unit/test_openrouter_client.py`
- `tests/unit/test_acap_enforcer.py`
- `tests/unit/test_event_schema.py`
- `tests/unit/test_mcp_manager.py`
- `tests/unit/test_config_loader.py`
- `tests/unit/test_graph_schema.py`
- `tests/unit/test_promotion.py`

**Steps:**

1. Write tests using pytest and pytest-asyncio. Mock all external calls.
2. `test_event_schema.py` must cover: all four valid event types parse correctly; `AgentSignal` with `stage='observation'` and `stage='finding'` both parse; `event_type='AgentFinding'` raises `EventSchemaError` (removed type); missing `agent_id` raises `EventSchemaError`; confidence outside range raises.
3. `test_promotion.py` must cover: rejected hypothesis → `promote_durable`; operational state → `discard`; low confidence → `return_to_log`; matching existing node → `reinforce`.
4. `test_graph_schema.py`: decay calculation for each node type at 1 day, 30 days, 365 days.
5. Achieve 80% line coverage on `shared/`.

**Done when:**
- `pytest tests/unit/` exits 0
- `pytest --cov=shared --cov-report=term-missing` shows >= 80% coverage
- mypy strict passes on all test files

---

### - [ ] TASK-25: Write integration tests

**Inputs:**
- Docker installed
- TASK-07 migration runner
- TASK-15 through TASK-19 complete

**Outputs:**
- `tests/integration/conftest.py`
- `tests/integration/test_event_log.py`
- `tests/integration/test_knowledge_graph.py`
- `tests/integration/test_signal_flow.py`

**Steps:**

1. Create `tests/integration/conftest.py` with pytest fixtures: `arcadedb_client` (starts ArcadeDB via docker-compose, runs migrations, yields client, tears down), `postgres_url`.
2. `test_event_log.py`: emit one of each event type, verify cursor-based polling returns correct results, verify `AgentSignal` with `stage='observation'` is returned separately from `stage='finding'`.
3. `test_knowledge_graph.py`: create a `ProductStructure` node, traverse from it, verify confidence decays, verify `reinforce_node` resets decay clock.
4. `test_signal_flow.py`: emit a synthetic high-confidence `stage='observation'` signal; verify the verification agent's `poll_for_observations` picks it up; emit a synthetic `stage='finding'` signal; verify the research/plan agent's `poll_for_findings` picks it up; verify a `CommitmentRecord` is created; verify marking it `approved` causes the implementation agent's `poll_for_approved` to pick it up.

**Done when:**
- All integration tests pass against live ArcadeDB and Postgres Docker containers
- `test_signal_flow.py` passes the full observation → finding → commitment → approved pipeline

---

### - [ ] TASK-26: Write prompt regression tests

**Inputs:**
- TASK-15 exploratory agent complete
- TASK-15 verification agent complete
- TASK-16 research/plan agent complete
- OpenRouter API key in environment

**Outputs:**
- `tests/agent/test_exploratory_regression.py`
- `tests/agent/test_verification_regression.py`
- `tests/agent/test_research_plan_regression.py`
- `tests/agent/fixtures/`

**Steps:**

1. Create fixture files in `tests/agent/fixtures/` for each agent type.
2. `test_exploratory_regression.py`: run exploratory agent against a fixture mandate in free-explorer mode, assert output signals have correct schema, `stage='observation'`, confidence in [0,1]. Use `GUARDRAILS_MODE=stub_pass`.
3. `test_verification_regression.py`: inject a fixture `stage='observation'` signal, run verification agent, assert verdict is one of confirmed/contradicted/inconclusive, assert `stage='finding'` signal is emitted, assert `ModelFamilyError` is not raised for correct family pairing.
4. `test_research_plan_regression.py`: inject a fixture `stage='finding'` signal, run research/plan agent, assert a `CommitmentRecord` is created with `status='pending_approval'`, assert `CognitiveCheckpoint` contains a non-empty `plan`.
5. Mark all with `@pytest.mark.agent_regression`.

**Done when:**
- All three regression test files pass with a valid OpenRouter API key
- Verification test confirms `stage='finding'` signal is emitted
- Research/plan test confirms plan is produced and commitment is marked `pending_approval`
- Tests are marked and can be excluded with `-m 'not agent_regression'`

---

### - [ ] TASK-27: Write ACAP boundary and secret scanning tests

**Inputs:**
- TASK-10, TASK-15 through TASK-19 complete

**Outputs:**
- `tests/agent/test_acap_boundaries.py`
- `tests/unit/test_no_hardcoded_secrets.py`

**Steps:**

1. `test_acap_boundaries.py`: for each agent type, attempt an action outside its ACAP. Assert `ACAPViolationError` is raised. Assert each violation generates an event log entry.
2. `test_no_hardcoded_secrets.py`: scan all Python files for patterns matching API keys and tokens. Fail on any match outside `.env.example`.

**Done when:**
- All ACAP boundary violations raise `ACAPViolationError`
- All violations generate ArcadeDB event log entries
- Secret scanning test passes on a clean repository

---

## Phase K — CI/CD and Deployment

### - [ ] TASK-28: Configure GitHub Actions CI pipeline

**Inputs:**
- All previous tasks complete
- GitHub repository created

**Outputs:**
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`

**Steps:**

1. Create `.github/workflows/ci.yml` triggered on `pull_request` to `main`. Jobs in order:
   1. **lint**: `uv run ruff check .`
   2. **type-check**: `uv run mypy . --strict`
   3. **schema-validation**: validate schema files, check no existing migration modified
   4. **unit-tests**: `uv run pytest tests/unit/ --cov=shared --cov=agents --cov-fail-under=80`
   5. **acap-validation**: load all five agent type ACAPs from reference config
   6. **integration-tests**: ArcadeDB and Postgres Docker services, `uv run pytest tests/integration/`
   7. **secret-scan**: `uv run pytest tests/unit/test_no_hardcoded_secrets.py`
2. Create `.github/workflows/deploy.yml` triggered on `push` to `main`. Per-agent deploy hooks triggered by changed directories. Run migrations after any deploy.

**Done when:**
- CI pipeline runs on a test PR and all jobs complete
- A PR with a ruff lint error fails lint
- A PR modifying an existing migration fails schema-validation
- Coverage below 80% fails unit-tests

---

### - [ ] TASK-29: Configure Render deployment

**Inputs:**
- Render account with API access
- All agent code complete

**Outputs:**
- `infra/render/render.yaml`
- `Makefile`

**Steps:**

1. Create `infra/render/render.yaml` as the Render Blueprint defining all services:
   1. **arcadedb**: `type=private_service`, `image=arcadedata/arcadedb:latest`, persistent disk
   2. **postgres**: `type=pserv` (managed Postgres), `plan=starter`
   3. **orchestration**: `type=cron`, `schedule='*/5 * * * *'`, `startCommand='python -m agents.orchestration'`
   4. **verification**: `type=worker`, `startCommand='python -m agents.verification'`
   5. **research-plan**: `type=worker`, `startCommand='python -m agents.research_plan'`
   6. **implementation**: `type=worker`, `startCommand='python -m agents.implementation'`
   7. **approval-ui**: `type=web`, React build and serve
   8. **exploratory-{mandate_name}**: `type=cron`, `schedule='0/30 * * * *'`, `startCommand='python -m agents.exploratory --mandate={mandate_name}'` for each configured mandate
2. All services in the same region.
3. Makefile targets: `make deploy-all`, `make migrate`, `make logs-{service}`.

**Done when:**
- `render.yaml` validates against Render Blueprint schema
- All services are in the same region
- `make migrate` correctly invokes schema migration

---

### - [ ] TASK-30: Write deployment and operations runbook

**Inputs:**
- TASK-28, TASK-29 complete

**Outputs:**
- `docs/runbook.md`

**Steps:**

1. Create `docs/runbook.md` covering:
   1. **Initial deployment** — steps to deploy from scratch
   2. **Required secrets** — table of all environment variables
   3. **Running schema migrations** — when and how
   4. **Monitoring** — Langfuse traces, Prometheus metrics, Render service logs, active worker dashboard
   5. **Adding a new exploratory mandate** — YAML structure, observation modes, deployment
   6. **Managing focuses** — how to create, close, and view active focuses in ArcadeDB
   7. **Human approval workflow** — accessing the UI, reviewing plans, approve/reject/defer
   8. **Signal flow** — how observations become findings become commitments
   9. **Common failure modes** — ArcadeDB connection failures, OpenRouter rate limits, stalled agents, verification family mismatch errors

**Done when:**
- Runbook exists at `docs/runbook.md`
- Signal flow section explains the full observation → finding → commitment → approved → complete path
- Human approval section explains how to access UI and act on pending plans

---

## Phase L — Reference Configuration

### - [ ] TASK-31: Create reference project configuration

**Inputs:**
- TASK-13 config loader

**Outputs:**
- `config/reference/mtp.yaml`
- `config/reference/acap_overrides.yaml`
- `config/reference/mandates/competitor_monitor.yaml`
- `config/reference/mandates/product_structure.yaml`

**Steps:**

1. Create `config/reference/mtp.yaml`. Use a fictional organisation. Example:
   - `purpose='Continuously improve the quality and reliability of the software systems we operate'`
   - `constraints=['Never expose customer data', 'Never deploy to production without a checkpoint', 'Escalate all changes exceeding $1000 resource cost']`
   - `intent_description='We exist to make software that works well and gets better over time.'`

2. Create `config/reference/acap_overrides.yaml` with per-agent-type overrides:
   - **exploratory**: `permitted_tools=['web_search']`, `permitted_mcp_connections=[]`, `permitted_event_types=['AgentSignal','AgentAction']`, `observation_modes=['web_search']`
   - **verification**: `permitted_tools=['web_search']`, `permitted_mcp_connections=[]`, `permitted_event_types=['AgentSignal','AgentAction']`
   - **research_plan**: `permitted_tools=['web_search','code_read']`, `permitted_mcp_connections=['https://mcp.example.com/v1']`, `permitted_event_types=['AgentSignal','AgentAction','AgentCheckpoint']`
   - **implementation**: `permitted_tools=['code_read','code_write','test_run']`, `permitted_mcp_connections=['https://mcp.example.com/v1']`, `permitted_event_types=['AgentSignal','AgentAction','AgentCheckpoint']`
   - **orchestration**: `permitted_tools=[]`, `permitted_mcp_connections=[]`, `permitted_event_types=['AgentAction','CommitmentTransition']`

3. Create `config/reference/mandates/competitor_monitor.yaml`:
   - `name='competitor_monitor'`, `domain='competitive_intelligence'`
   - `polling_interval_minutes=30`, `signal_threshold=0.6`
   - `observation_modes=['web_search']`

4. Create `config/reference/mandates/product_structure.yaml`:
   - `name='product_structure'`, `domain='product_knowledge'`
   - `polling_interval_minutes=60`, `signal_threshold=0.4`
   - `observation_modes=['mcp']`

5. Verify: `load_project_config('config/reference')` succeeds with no validation errors.

**Done when:**
- `load_project_config('config/reference')` succeeds
- Reference config contains no real project names, organisation names, or credentials
- All five agent type ACAPs can be loaded and validated

---

### - [ ] TASK-32: Final validation and AGENTS.md self-test

**Inputs:**
- All previous tasks complete

**Outputs:**
- No new files — validation only

**Steps:**

1. Run the full CI pipeline locally: `uv run ruff check . && uv run mypy . --strict && uv run pytest tests/unit/ --cov=shared --cov=agents --cov-fail-under=80 && uv run pytest tests/integration/ && uv run pytest tests/agent/ -m 'not agent_regression'`
2. Run secret scan: `uv run pytest tests/unit/test_no_hardcoded_secrets.py`
3. Run `load_project_config('config/reference')` and assert it returns a valid `ProjectConfig`
4. Verify `AGENTS.md` is accurate:
   1. Every listed directory exists
   2. Autonomous modification rules match ACAP enforcer behaviour
   3. Event schema contract matches what `emit_validated` actually requires
   4. Permitted network calls match reference ACAP
5. If any discrepancy in `AGENTS.md`, update `AGENTS.md` — never change the implementation to match `AGENTS.md` without human review.
6. Create final commit: `TASK-32: validated — all checks pass, AGENTS.md accurate`

**Done when:**
- Full local CI pipeline exits 0
- Secret scan exits 0
- Reference config loads successfully
- `AGENTS.md` accurately describes the actual repository
- Final commit exists

---

All 32 tasks complete. The Agent Operations repository is ready for first deployment.

Proceed with:
1. Creating Render services from `infra/render/render.yaml`
2. Setting all required environment variables as Render secrets
3. Running `make migrate` to initialise the ArcadeDB schema
4. Deploying verification, research-plan, and implementation workers
5. Deploying exploratory cron jobs for each configured mandate
6. Running `make logs-verification` to confirm the verification worker is polling
7. Accessing the approval UI and verifying the dashboard shows active workers

**Architecture summary:**

```
Colony workers (exploratory cron jobs)
    ↓ emit AgentSignal stage='observation'
Verification worker (polls independently)
    ↓ emit AgentSignal stage='finding'
Research/Plan worker (polls independently)
    ↓ creates CommitmentRecord status='pending_approval'
Human approval UI
    ↓ CommitmentRecord status='approved'
Implementation worker (polls independently)
    ↓ CommitmentRecord status='complete'
Orchestration agent (5-min cron)
    → knowledge graph promotion, decay, health monitoring, escalation
```

**References:** Agent Operations Requirements Document (project); The Event Log and Agent Types (project); AI-Native Organization Blueprint (project); ArcadeDB documentation; Render.com documentation; LangGraph documentation; OpenRouter documentation.
