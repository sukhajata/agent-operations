# Agent Operations

**Repository Build Plan — Task Instructions for Agent Execution**

June 2026 — v0.1

## Instructions for the Executing Agent

You are building the initial repository for Agent Operations — an agent platform that implements the ExO 3.0 Intelligence Stack.

Complete each task in order. Do not skip tasks. Each task specifies its inputs, outputs (files to create or modify), numbered steps, and done-when criteria. A task is complete only when all done-when criteria pass.

Commit after each completed task with the task ID as the commit message prefix (e.g. `TASK-01: repository scaffold`).

**Language:** Python 3.12+. **Package manager:** uv. **Type checker:** mypy strict mode. **Linter:** ruff. **Test runner:** pytest.

All code must be fully typed. No hardcoded project names, domains, or credentials anywhere in the codebase.

**Deployment target:** Render.com. ArcadeDB as a private service with persistent disk. Orchestration agent as a background worker. Exploratory agents as cron jobs. Verification and objective agents as LangGraph subgraphs within the orchestration agent process. PostgreSQL via Render managed Postgres for LangGraph checkpoints.

**Key invariants to enforce throughout:**

1. No project-specific code in this repository
2. No credentials in any file
3. Every emitted event carries `agent_id`, `objective_id`, `mtp_version`, and `timestamp`
4. ACAP boundaries are checked before every agent action
5. Verification agents always use a different model family from the finding's originating agent

## Phase Overview

| Phase | Name | Tasks |
|-------|------|-------|
| A | Repository Scaffold | TASK-01 to TASK-03 |
| B | ArcadeDB Schema | TASK-04 to TASK-07 |
| C | Shared Libraries | TASK-08 to TASK-13 |
| D | Agent Implementations | TASK-14 to TASK-19 |
| E | Orchestration and Subagents | TASK-20 to TASK-22 |
| F | Human Approval UI | TASK-23 |
| G | Guardrails | TASK-24 |
| H | Observability | TASK-25 to TASK-26 |
| I | Tests | TASK-27 to TASK-30 |
| J | CI/CD and Deployment | TASK-31 to TASK-33 |
| K | Reference Configuration | TASK-34 to TASK-35 |

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
   - `agents/objective/`
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
7. Add core runtime dependencies: `langgraph`, `langgraph-checkpoint-postgres`, `openai` (for OpenRouter compat), `arcadedb-client` or `httpx` for ArcadeDB HTTP, `pydantic>=2`, `langfuse`, `prometheus-client`, `presidio-analyzer`, `presidio-anonymizer`
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

1. Create `.env.example` listing every required environment variable with placeholder values and a comment describing each. Never use real values. Include: `OPENROUTER_API_KEY`, `ARCADEDB_URL`, `ARCADEDB_USER`, `ARCADEDB_PASSWORD`, `POSTGRES_URL`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`, `CONFIG_PATH`, `RENDER_API_KEY` (for future orchestration use)
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

1. Write `AGENTS.md` at the repository root. This file governs how AI agents (including future objective agents working on this codebase) behave when working in this repository.
2. Include the following sections:
   - **(1) Repository purpose** — This is a reusable agent platform, not a product. No project-specific code belongs here.
   - **(2) Directory map** — one line per top-level directory explaining what belongs there.
   - **(3) Autonomous modification rules** — agents MAY modify: `agents/`, `shared/`, `tests/unit/`, `tests/agent/` for implementation work. Agents MUST NOT autonomously modify: `schema/migrations/` (human review required for all migrations), `config/schema/` (configuration API is a public contract), `infra/` (infrastructure changes require human approval), `AGENTS.md` itself.
   - **(4) Event schema contract** — any code that emits events MUST use the canonical schemas in `shared/event_schemas/`. Every event MUST carry `agent_id`, `objective_id`, `mtp_version`, `timestamp`.
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
- Event type specifications from requirements REQ-EL-01

**Outputs:**
- `schema/timeseries/event_log.py`
- `schema/timeseries/migrations/0001_create_event_log_types.sql`

**Steps:**

1. Create `schema/timeseries/event_log.py` defining Python dataclasses for all five event types: `AgentSignal`, `AgentAction`, `AgentFinding`, `AgentCheckpoint`, `ObjectiveTransition`. Each must have: `event_type` (str), `ts` (datetime with nanosecond precision), `agent_id` (str), `objective_id` (str), `mtp_version` (str), `payload` (dict[str, Any]). `AgentSignal` and `AgentFinding` additionally require: `confidence` (float, 0.0–1.0), `novelty_flag` (bool).
2. Create the SQL migration file creating all five ArcadeDB TimeSeries types with correct retention:
   - `AgentSignals` RETENTION 7 DAYS
   - `AgentActions` RETENTION 30 DAYS
   - `AgentFindings` RETENTION 90 DAYS
   - `AgentCheckpoints` RETENTION 180 DAYS
   - `ObjectiveTransitions` RETENTION 0 (indefinite)
   
   Each type must define TAGS (`agent_id` STRING, `objective_id` STRING, `mtp_version` STRING) and FIELDS appropriate to the event type.
3. Add a migration runner function in `schema/timeseries/__init__.py` that executes the migration SQL idempotently (`CREATE TYPE IF NOT EXISTS` pattern)

**Done when:**
- All five Python dataclasses are fully typed and pass mypy strict
- Migration SQL file exists with all five `CREATE TIMESERIES TYPE` statements
- Migration runner function is idempotent — safe to call twice

---

### - [x] TASK-05: Define knowledge graph schema

**Inputs:**
- Knowledge graph node type specifications from conversation: `ProductStructure`, `DecisionRecord`, `InvestigationFinding`, `CompetitorCapability`, `CustomerTheme`, `CustomerSignal`

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

### - [x] TASK-06: Define identity store and objective registry schema

**Inputs:**
- MTP document structure, ACAP definition structure from requirements

**Outputs:**
- `schema/identity/models.py`
- `schema/identity/migrations/0001_create_identity_schema.sql`

**Steps:**

1. Create `schema/identity/models.py` with Pydantic v2 models for:
   - `MTPDocument` (`mtp_id`: str, `version`: str, `purpose`: str, `constraints`: list[str], `intent_description`: str, `created_at`: datetime, `created_by`: str)
   - `ACAPDefinition` (`acap_id`: str, `agent_type`: Literal['exploratory','verification','objective','orchestration'], `permitted_tools`: list[str], `permitted_mcp_connections`: list[str], `permitted_event_types`: list[str], `forbidden_targets`: list[str], `resource_ceiling`: ResourceCeiling)
   - `ResourceCeiling` (`max_tokens_per_run`: int, `max_duration_seconds`: int, `max_mcp_reads_per_run`: int)
   - `ObjectiveRecord` (`objective_id`: str, `status`: Literal['pending','active','stalled','complete','escalated'], `created_at`: datetime, `domain`: str, `priority_signal`: float, `checkpoint`: CognitiveCheckpoint | None, `assigned_agent_id`: str | None)
   - `CognitiveCheckpoint` (`hypotheses_investigated`: list[HypothesisRecord], `current_best_understanding`: str, `recommended_next_action`: str, `checkpoint_at`: datetime)
   - `HypothesisRecord` (`hypothesis`: str, `conclusion`: Literal['confirmed','rejected','pending'], `evidence`: str)
2. Create the SQL migration creating ArcadeDB document types for `MTPDocument`, `ACAPDefinition`, and `ObjectiveRecord` with appropriate indexes on `version`, `agent_type`, and `status` respectively.
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
3. Enforce migration immutability: the runner must compute a SHA-256 hash of each migration file and store it in `SchemaMigration`. On subsequent runs, if a previously applied migration's hash has changed, raise an error — migration files must never be modified after being applied.

**Done when:**
- `python -m schema.migrate` against a fresh ArcadeDB instance applies all migrations and exits 0
- Running it a second time skips all migrations and exits 0
- Modifying a migration file's content after it has been applied causes the runner to raise an error on next run
- Unit test mocks ArcadeDB and verifies idempotency and hash enforcement

---

## Phase C — Shared Libraries

### - [ ] TASK-08: Build ArcadeDB client

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
2. Create `shared/arcadedb/timeseries.py` with functions: `emit_event(client, event: AgentSignal | AgentAction | AgentFinding | AgentCheckpoint | ObjectiveTransition) -> None`, `poll_events(client, event_type: str, since_ts: datetime, agent_id: str | None, objective_id: str | None, limit: int = 100) -> list[dict]`. The poll function uses cursor-based queries (`WHERE ts > :since_ts`) and must not perform full table scans.
3. Create `shared/arcadedb/graph.py` with functions: `upsert_node(client, node: GraphNode) -> str`, `get_node(client, node_id: str) -> GraphNode | None`, `traverse_from(client, node_id: str, max_depth: int = 3) -> list[GraphNode]`, `reinforce_node(client, node_id: str) -> None` (resets decay clock, updates confidence), `flag_for_revalidation(client, node_id: str) -> None`, `apply_decay_all(client) -> int` (returns count of nodes updated).
4. Create `shared/arcadedb/identity.py` with functions: `load_mtp(client) -> MTPDocument`, `load_acap(client, agent_type: str) -> ACAPDefinition`, `get_objective(client, objective_id: str) -> ObjectiveRecord | None`, `create_objective(client, objective: ObjectiveRecord) -> str`, `update_objective(client, objective_id: str, updates: dict) -> None`, `write_checkpoint(client, objective_id: str, checkpoint: CognitiveCheckpoint) -> None`

**Done when:**
- mypy strict passes on all files
- Unit tests mock httpx and verify correct query construction for `poll_events` (partition pruning query pattern)
- Unit test verifies `reinforce_node` resets `last_reinforced` timestamp

---

### - [ ] TASK-09: Build OpenRouter client with agent-role routing

**Inputs:**
- OpenRouter API documentation
- Model assignments: exploratory/orchestration=`deepseek/deepseek-v4-flash`, verification=`qwen/qwen3.7-plus`, objective=`deepseek/deepseek-v4-pro`

**Outputs:**
- `shared/openrouter/__init__.py`
- `shared/openrouter/client.py`
- `shared/openrouter/models.py`

**Steps:**

1. Create `shared/openrouter/models.py` defining:
   - `AgentRole` enum (`EXPLORATORY`, `VERIFICATION`, `OBJECTIVE`, `ORCHESTRATION`)
   - `ModelFamily` enum (`DEEPSEEK`, `QWEN`)
   - `MODEL_ASSIGNMENTS` dict mapping `AgentRole` to model string and `ModelFamily`
   - `PROVIDER_ROUTING` dict mapping `AgentRole` to OpenRouter provider config:
     - exploratory/orchestration: `order=['DeepSeek','DeepInfra']`, `allow_fallbacks=True`
     - objective: `only=['DeepSeek']`, `allow_fallbacks=False`
     - verification: `only=['Alibaba']`, `allow_fallbacks=True`
2. Create `shared/openrouter/client.py` with `OpenRouterClient` class. Key method: `complete(role: AgentRole, messages: list[dict], system: str, max_tokens: int = 4096, enable_caching: bool = False) -> str`. Must:
   1. Look up model and provider routing from `MODEL_ASSIGNMENTS` and `PROVIDER_ROUTING`
   2. Build the provider object for the OpenRouter request body
   3. Enable prompt caching headers for `OBJECTIVE` role when `enable_caching=True`
   4. Raise `ModelFamilyError` if a verification call is attempted with the same model family as a supplied `originating_model_family` parameter
3. Add `enforce_independence(requesting_role: AgentRole, originating_model_family: ModelFamily) -> None` that raises `ModelFamilyError` if `requesting_role=VERIFICATION` and `originating_model_family` matches the verification model's family.

**Done when:**
- `enforce_independence` raises `ModelFamilyError` when verification and originating agent share a model family
- `enforce_independence` does not raise when model families differ
- Unit tests verify provider routing objects are built correctly for each agent role
- mypy strict passes

---

### - [ ] TASK-10: Build ACAP enforcer

**Inputs:**
- TASK-06 `ACAPDefinition` model
- TASK-09 client

**Outputs:**
- `shared/acap/__init__.py`
- `shared/acap/enforcer.py`
- `shared/acap/exceptions.py`

**Steps:**

1. Create `shared/acap/exceptions.py` with: `ACAPViolationError(action: str, reason: str, agent_id: str, objective_id: str)`, `ScopeViolationError` (subclass of `ACAPViolationError`).
2. Create `shared/acap/enforcer.py` with `ACAPEnforcer` class. Constructor takes `ACAPDefinition` and `ArcadeDBClient`. Methods:
   - `check_tool(tool_name: str) -> None` (raises `ACAPViolationError` if tool not in `permitted_tools`)
   - `check_mcp_connection(server_url: str) -> None` (raises `ACAPViolationError` if not in `permitted_mcp_connections`)
   - `check_event_type(event_type: str) -> None` (raises `ACAPViolationError` if not in `permitted_event_types`)
   - `check_resource_ceiling(tokens_used: int, duration_seconds: float, mcp_reads: int) -> None` (raises `ACAPViolationError` if any ceiling exceeded)
   - `log_violation(violation: ACAPViolationError, agent_id: str, objective_id: str, mtp_version: str) -> None` (emits a ScopeViolation event to ArcadeDB event log)
3. All `check_` methods must call `log_violation` before raising — violations are always logged even if the agent catches the exception.

**Done when:**
- `check_tool` raises `ACAPViolationError` for unlisted tools
- `check_mcp_connection` raises `ACAPViolationError` for unlisted connections
- `log_violation` emits an event to the event log before the exception propagates
- Unit tests cover all check methods and verify `log_violation` is always called on violation
- mypy strict passes

---

### - [ ] TASK-11: Build event schema validator

**Inputs:**
- TASK-04 event type dataclasses

**Outputs:**
- `shared/event_schemas/__init__.py`
- `shared/event_schemas/validator.py`

**Steps:**

1. Create `shared/event_schemas/validator.py` with: `validate_event(event: dict) -> AgentSignal | AgentAction | AgentFinding | AgentCheckpoint | ObjectiveTransition` that validates the event dict against the correct typed dataclass based on the `event_type` field. Raise `EventSchemaError` if: `event_type` is missing, `event_type` is not one of the five valid types, any required field is missing or wrongly typed, `confidence` is outside 0.0–1.0 range.
2. Create a `check_required_fields(event: dict) -> None` helper that verifies `agent_id`, `objective_id`, `mtp_version`, and `ts` are all present and non-empty on every event regardless of type.
3. Export a single `emit_validated(event: dict, client: ArcadeDBClient) -> None` function that validates then emits — this is the only function agents should call to emit events. Direct writes to ArcadeDB bypassing this function are an ACAP violation.

**Done when:**
- `validate_event` correctly parses all five event types from valid dicts
- `validate_event` raises `EventSchemaError` for missing required fields
- `validate_event` raises `EventSchemaError` for confidence outside 0.0–1.0
- Unit tests cover all five event types and all error cases
- mypy strict passes

---

### - [ ] TASK-12: Build MCP connection manager

**Inputs:**
- TASK-10 `ACAPEnforcer`
- MCP protocol documentation

**Outputs:**
- `shared/mcp/__init__.py`
- `shared/mcp/manager.py`

**Steps:**

1. Create `shared/mcp/manager.py` with `MCPConnectionManager` class. Constructor takes `ACAPDefinition` and `ArcadeDBClient`. Method: `read(server_url: str, resource_path: str, params: dict | None = None) -> str`. The read method must:
   1. Call `enforcer.check_mcp_connection(server_url)` before making any network call — raises `ACAPViolationError` if not permitted
   2. Make the MCP read request via httpx
   3. Log an `AgentAction` event via `emit_validated` with `tool='mcp_read'`, payload including `server_url` and `resource_path`
   4. Return the raw response content as a string
2. The manager must never cache MCP responses — agents always get current state from the artifact source.
3. Add a `list_permitted_connections() -> list[str]` method that returns the ACAP's `permitted_mcp_connections` without making any network call.

**Done when:**
- `read()` raises `ACAPViolationError` for unpermitted servers before any network call
- `read()` emits an `AgentAction` event for every successful read
- Unit tests mock httpx and verify ACAP check happens before network call
- mypy strict passes

---

### - [ ] TASK-13: Build configuration loader

**Inputs:**
- TASK-06 schema models
- `config/schema/` directory

**Outputs:**
- `config/schema/v1.py`
- `config/schema/mtp_schema.yaml`
- `config/schema/acap_schema.yaml`
- `config/schema/mandate_schema.yaml`
- `shared/config/__init__.py`
- `shared/config/loader.py`

**Steps:**

1. Create JSON Schema (as YAML) files for:
   - `mtp_schema.yaml` (validates `mtp.yaml` project config)
   - `acap_schema.yaml` (validates `acap_overrides.yaml`)
   - `mandate_schema.yaml` (validates exploratory agent mandate definitions)
   
   These are the public configuration API — treat them as versioned contracts.
2. Create `config/schema/v1.py` that exposes the schemas as Python dicts for programmatic validation.
3. Create `shared/config/loader.py` with `load_project_config(config_path: str) -> ProjectConfig` that:
   1. Reads `mtp.yaml`, `acap_overrides.yaml`, and `mandates/` from the `config_path` directory
   2. Validates each against its schema using `jsonschema`
   3. Raises `ConfigValidationError` with field path and constraint violated if validation fails
   4. Returns a typed `ProjectConfig` dataclass
4. `ProjectConfig` must have: `mtp`: `MTPDocument`, `acap_overrides`: `dict[str, dict]`, `mandates`: `list[MandateDefinition]`. `MandateDefinition`: `name` (str), `domain` (str), `polling_interval_minutes` (int), `signal_threshold` (float), `search_queries` (list[str]).

**Done when:**
- `load_project_config` succeeds on the reference config created in TASK-31
- `load_project_config` raises `ConfigValidationError` with field path on invalid config
- mypy strict passes
- Unit tests cover valid config, missing fields, and wrong types

---

## Phase D — Agent Implementations

### - [ ] TASK-14: Build exploratory agent

**Inputs:**
- TASK-08 ArcadeDB client
- TASK-09 OpenRouter client
- TASK-10 ACAP enforcer
- TASK-11 event schema validator
- TASK-13 config loader

**Outputs:**
- `agents/exploratory/__init__.py`
- `agents/exploratory/graph.py`
- `agents/exploratory/nodes.py`
- `agents/exploratory/state.py`

**Steps:**

1. Create `agents/exploratory/state.py` with `ExploratoryState` TypedDict: `mandate` (`MandateDefinition`), `mtp_version` (str), `agent_id` (str), `last_cursor` (datetime | None), `observations` (list[str]), `signals_emitted` (int), `run_at` (datetime).
2. Create `agents/exploratory/nodes.py` with async node functions:
   - `load_context(state)` loads MTP version and ACAP from identity store
   - `observe(state)` queries the mandate's domain using OpenRouter (`EXPLORATORY` role) with the mandate's `search_queries` as context — returns raw observations
   - `filter_signals(state)` applies quality threshold (`confidence >= mandate.signal_threshold`) and novelty check (query ArcadeDB for existing signals with same domain in last 7 days)
   - `emit_signals(state)` calls `emit_validated` for each signal that passed filtering
   - `update_cursor(state)` sets `last_cursor` to `now()`
3. Create `agents/exploratory/graph.py` composing the nodes into a LangGraph `StateGraph`: `load_context` → `observe` → `filter_signals` → `emit_signals` → `update_cursor` → `END`. Compile with `PostgresSaver` checkpointer.
4. The `observe` node must NEVER write to the objective registry — ACAP enforcer must prevent this. Add a test that attempts a write and verifies `ACAPViolationError` is raised.
5. Entry point: `run_exploratory_agent(config_path: str, mandate_name: str) -> None` that loads config, builds the graph, and invokes it.

**Done when:**
- Graph compiles without error
- `observe` node uses `EXPLORATORY` model role
- `filter_signals` suppresses signals below threshold
- Novelty check queries ArcadeDB for duplicate signals within retention window
- Objective registry write attempt raises `ACAPViolationError`
- All emitted signals carry `agent_id`, `objective_id='none'`, `mtp_version`, `ts`
- mypy strict passes

---

### - [ ] TASK-15: Build verification agent as LangGraph subgraph

**Inputs:**
- TASK-08, TASK-09, TASK-10, TASK-11
- Requirement: must use different model family from originating agent

**Outputs:**
- `agents/verification/__init__.py`
- `agents/verification/graph.py`
- `agents/verification/nodes.py`
- `agents/verification/state.py`

**Steps:**

1. Create `agents/verification/state.py` with `VerificationState` TypedDict: `finding` (`AgentFinding`), `originating_model_family` (`ModelFamily`), `mtp_version` (str), `agent_id` (str), `objective_id` (str), `investigation_steps` (list[str]), `verdict` (Literal['confirmed','contradicted','inconclusive'] | None), `verdict_confidence` (float | None), `verdict_rationale` (str | None).
2. Create `agents/verification/nodes.py`:
   - `enforce_independence(state)` calls `enforce_independence(AgentRole.VERIFICATION, state['originating_model_family'])` — raises `ModelFamilyError` if same family
   - `investigate(state)` uses OpenRouter `VERIFICATION` role to independently investigate the finding with an adversarial system prompt: "Your task is to determine whether the following finding is false. Assume it is wrong and attempt to disprove it. Only conclude it is confirmed if you cannot find evidence against it." The investigate node must query ArcadeDB for contrary evidence and use MCP connections permitted by ACAP
   - `emit_verdict(state)` calls `emit_validated` with an `AgentFinding` event carrying `verdict`, `verdict_confidence`, `verdict_rationale`
3. Create `agents/verification/graph.py` as a compiled `StateGraph`: `enforce_independence` → `investigate` → `emit_verdict` → `END`. This graph is designed to be used as a subgraph node within the orchestration graph — it is not run standalone.
4. Export `build_verification_subgraph() -> CompiledGraph` factory function.

**Done when:**
- `enforce_independence` node raises `ModelFamilyError` when families match
- `investigate` node system prompt is adversarial (contains language about disproving)
- `emit_verdict` always emits a finding event before the subgraph exits
- Subgraph can be added as a node to a parent `StateGraph` without error
- mypy strict passes

---

### - [ ] TASK-16: Build objective agent as LangGraph subgraph

**Inputs:**
- TASK-08, TASK-09, TASK-10, TASK-11, TASK-12

**Outputs:**
- `agents/objective/__init__.py`
- `agents/objective/graph.py`
- `agents/objective/nodes.py`
- `agents/objective/state.py`

**Steps:**

1. Create `agents/objective/state.py` with `ObjectiveState` TypedDict: `objective` (`ObjectiveRecord`), `mtp_version` (str), `agent_id` (str), `graph_context` (list[GraphNode]), `artifact_context` (list[str]), `event_delta` (list[dict]), `hypothesis` (str | None), `checkpoint` (`CognitiveCheckpoint` | None), `plan` (str | None), `actions_taken` (list[str]).
2. Create `agents/objective/nodes.py` with the research loop nodes:
   - `traverse_graph(state)` queries ArcadeDB graph from the objective's domain node outward `max_depth=3`
   - `read_artifacts(state)` uses `MCPConnectionManager` to read structural artifacts identified in `graph_context` — enforces ACAP on each read
   - `read_event_delta(state)` polls ArcadeDB event log for events since the last checkpoint timestamp
   - `form_hypothesis(state)` uses OpenRouter `OBJECTIVE` role to synthesise `graph_context`, `artifact_context`, and `event_delta` into a hypothesis
   - `write_checkpoint(state)` calls `write_checkpoint()` on ArcadeDB identity store with the current `CognitiveCheckpoint` — must occur at this node boundary
   - `execute_plan(state)` uses OpenRouter `OBJECTIVE` role to execute the plan, emitting `AgentAction` events for each action
   - `promote_findings(state)` emits `AgentFinding` events for durable findings to be promoted by orchestration at closure
3. Create `agents/objective/graph.py`: `traverse_graph` → `read_artifacts` → `read_event_delta` → `form_hypothesis` → `write_checkpoint` → `execute_plan` → `promote_findings` → `END`.
4. The `write_checkpoint` node must always execute even if a previous node raises — use LangGraph's error handling to ensure checkpoint writes are not skipped.
5. Export `build_objective_subgraph() -> CompiledGraph` factory function.

**Done when:**
- Research loop executes in correct order (graph → artifacts → events → hypothesis)
- `write_checkpoint` is called before `execute_plan`
- A simulated mid-execution failure still results in a checkpoint being written
- Artifact reads are logged as `AgentAction` events
- mypy strict passes

---

## Phase E — Orchestration and Subagents

### - [ ] TASK-17: Build knowledge promotion logic

**Inputs:**
- TASK-05 graph schema
- TASK-08 ArcadeDB client

**Outputs:**
- `agents/orchestration/promotion.py`

**Steps:**

1. Create `agents/orchestration/promotion.py` with `classify_for_promotion(finding: AgentFinding, existing_nodes: list[GraphNode]) -> PromotionDecision`. `PromotionDecision` is a dataclass with: `action` (Literal['discard','promote_durable','promote_medium','reinforce','return_to_log']), `node_type` (str | None), `confidence` (float | None), `rationale` (str).
2. Classification rules:
   - If `finding.payload` contains `'hypothesis_conclusion': 'rejected'` → `action='promote_durable'`, `node_type='InvestigationFinding'` with `NEGATIVE_KNOWLEDGE` edge
   - If `finding.payload` contains `'structural_discovery'` → `action='promote_durable'`, `node_type='ProductStructure'`
   - If finding matches an existing node (semantic similarity via embedding comparison) → `action='reinforce'`
   - If `finding.confidence < 0.5` → `action='return_to_log'`
   - If finding contains operational state (action logs, intermediate steps) → `action='discard'`
   - Default for customer/competitor findings → `action='promote_medium'`
3. Create `promote_findings(client: ArcadeDBClient, findings: list[AgentFinding]) -> PromotionSummary` that classifies each finding and executes the correct ArcadeDB operation.

**Done when:**
- `classify_for_promotion` returns `'discard'` for operational state
- `classify_for_promotion` returns `'promote_durable'` for rejected hypotheses with `NEGATIVE_KNOWLEDGE` edge
- `classify_for_promotion` returns `'reinforce'` when a matching node exists
- Unit tests cover all five classification outcomes
- mypy strict passes

---

### - [ ] TASK-18: Build orchestration agent

**Inputs:**
- TASK-14, TASK-15, TASK-16, TASK-17 complete
- TASK-08, TASK-09, TASK-10

**Outputs:**
- `agents/orchestration/__init__.py`
- `agents/orchestration/graph.py`
- `agents/orchestration/nodes.py`
- `agents/orchestration/state.py`

**Steps:**

1. Create `agents/orchestration/state.py` with `OrchestrationState` TypedDict: `mtp_version` (str), `agent_id` (str), `signal_density` (dict[str, float]), `active_objectives` (list[ObjectiveRecord]), `stalled_objectives` (list[str]), `escalations_pending` (list[str]), `verification_input` (`AgentFinding` | None), `verification_output` (`VerificationState` | None), `objective_input` (`ObjectiveRecord` | None), `objective_output` (`ObjectiveState` | None), `promotion_pending` (list[AgentFinding]).
2. Create `agents/orchestration/nodes.py`:
   - `monitor_signals(state)` polls `AgentSignals` from ArcadeDB for the last polling window, computes signal density per domain
   - `detect_stalls(state)` queries `ObjectiveRegistry` for objectives with no checkpoint in the last N minutes (configurable)
   - `create_objective(state)` creates a new `ObjectiveRecord` when signal density exceeds threshold
   - `escalate(state)` writes escalation events for: resource ceiling breach, inconclusive verification above threshold, ACAP violation detected
   - `trigger_promotion(state)` calls `promote_findings()` for all completed objectives
   - `check_human_queue(state)` reads the escalation queue and logs current pending items
3. Create `agents/orchestration/graph.py` composing the orchestration loop and embedding verification and objective subgraphs as nodes: `monitor_signals` → `detect_stalls` → conditional edge (if high-density signal → `run_verification` using verification subgraph) → conditional edge (if verified finding → `run_objective` using objective subgraph) → `trigger_promotion` → `escalate` → `check_human_queue` → `END`. The orchestration graph loops — add a cycle edge back to `monitor_signals` for background worker continuous operation.
4. Embed subgraphs: `orchestration_graph.add_node('run_verification', build_verification_subgraph())`. `orchestration_graph.add_node('run_objective', build_objective_subgraph())`.
5. Compile with `PostgresSaver` checkpointer. Entry point: `run_orchestration_loop(config_path: str) -> None`.

**Done when:**
- Orchestration graph compiles with embedded verification and objective subgraphs
- `monitor_signals` correctly computes signal density from ArcadeDB poll results
- `detect_stalls` identifies objectives with no recent checkpoint
- `escalate` writes escalation events for all three escalation conditions
- `trigger_promotion` calls `promote_findings` for closed objectives
- mypy strict passes

---

### - [ ] TASK-19: Build implementation agent

**Inputs:**
- TASK-08, TASK-09, TASK-10, TASK-11, TASK-12 complete
- TASK-16 objective agent complete

**Outputs:**
- `agents/implementation/__init__.py`
- `agents/implementation/graph.py`
- `agents/implementation/nodes.py`
- `agents/implementation/state.py`

**Steps:**

1. Create `agents/implementation/state.py` with `ImplementationState` TypedDict: `objective` (`ObjectiveRecord`), `mtp_version` (str), `agent_id` (str), `plan` (str), `checkpoint` (`CognitiveCheckpoint`), `actions_taken` (list[str]), `files_modified` (list[str]), `test_results` (dict[str, Any] | None), `status` (Literal['in_progress', 'complete', 'failed']).
2. Create `agents/implementation/nodes.py` with async node functions:
   - `load_plan(state)` reads the execution plan from the objective's cognitive checkpoint
   - `execute_plan(state)` uses OpenRouter `IMPLEMENTATION` role to execute the plan step-by-step, emitting `AgentAction` events for each file operation and tool usage
   - `run_tests(state)` executes test suite and captures results
   - `update_objective(state)` marks objective as `complete` on success or `stalled` on failure, writes final checkpoint
   - `promote_findings(state)` calls `promote_findings()` for durable findings discovered during implementation
3. Create `agents/implementation/graph.py` composing the nodes into a LangGraph `StateGraph`: `load_plan` → `execute_plan` → `run_tests` → `update_objective` → `promote_findings` → `END`. Compile with `PostgresSaver` checkpointer.
4. The `execute_plan` node must enforce ACAP boundaries on all file operations and tool usage. Add a test that attempts an unpermitted operation and verifies `ACAPViolationError` is raised.
5. Entry point: `run_implementation_agent(config_path: str, objective_id: str) -> None` that loads config, builds the graph, and invokes it.
6. The implementation agent must only process objectives with `implementation_status='approved'` and `implementation_state` in `['to_do', 'pending']`. Add validation at graph entry.

**Done when:**
- Graph compiles without error
- `execute_plan` node enforces ACAP boundaries on all operations
- Implementation agent only processes approved objectives
- All file operations are logged as `AgentAction` events
- On completion, objective status is updated to `complete`
- On failure, checkpoint is written and objective is marked `stalled`
- mypy strict passes

---

## Phase E — Orchestration and Subagents

### - [ ] TASK-20: Update orchestration agent for human approval workflow

**Inputs:**
- TASK-18 orchestration agent complete
- TASK-19 implementation agent complete
- REQ-HR-01 human gate requirement

**Outputs:**
- `agents/orchestration/nodes.py` (update)
- `agents/orchestration/graph.py` (update)

**Steps:**

1. Update `agents/orchestration/nodes.py` to add:
   - `mark_for_approval(state)` sets `implementation_status='pending_approval'` and `implementation_state='to_do'` on completed objectives
   - `spawn_implementation(state)` spawns implementation agent for objectives with `implementation_status='approved'` and `implementation_state='to_do'`
2. Update `agents/orchestration/graph.py` to add conditional edge after `trigger_promotion`: if objective has execution plan → `mark_for_approval` → `check_human_queue` → conditional edge (if approved objective exists → `spawn_implementation`) → `escalate` → `END`.
3. The orchestration agent must poll for approved objectives and spawn implementation agents accordingly.

**Done when:**
- Orchestration agent marks completed objectives as `pending_approval`
- Orchestration agent spawns implementation agents for approved objectives
- Graph compiles with new approval workflow nodes
- mypy strict passes

---

## Phase F — Human Approval UI

### - [ ] TASK-23: Build human approval UI with CopilotKit

**Inputs:**
- TASK-20 orchestration agent with approval workflow complete
- REQ-HR-01 human gate requirement
- CopilotKit framework

**Outputs:**
- `ui/` directory with CopilotKit-based React application
- `ui/package.json`
- `ui/src/components/ApprovalQueue.tsx`
- `ui/src/components/ApprovalCard.tsx`
- `ui/src/api/arcadedb.ts`

**Steps:**

1. Create `ui/` directory with a CopilotKit-based React application for human approval workflow.
2. Create `ui/package.json` with dependencies: `react`, `@copilotkit/react-core`, `@copilotkit/react-ui`, `axios`.
3. Create `ui/src/api/arcadedb.ts` with functions to query ArcadeDB for objectives with `implementation_status='pending_approval'` and to update approval decisions.
4. Create `ui/src/components/ApprovalQueue.tsx` that displays a list of pending approval items with plan details, context, and approve/reject/defer buttons.
5. Create `ui/src/components/ApprovalCard.tsx` that renders a single approval item with: objective domain, execution plan summary, research context, approve/reject/defer buttons with optional comments.
6. Implement approval workflow: when human approves, update objective with `implementation_status='approved'`, `approval_metadata` (reviewer_id, approved_at, comments). When human rejects, update with `implementation_status='rejected'`. When human defers, update with `implementation_status='deferred'`.
7. Add authentication and reviewer identity tracking (integrate with existing auth system or add simple username/password for v1).

**Done when:**
- UI displays pending approval items with plan details and context
- Human can approve, reject, or defer with optional comments
- Approval decision is stored in ArcadeDB objective registry
- Implementation agent only processes approved objectives
- UI is built with CopilotKit and provides clear approval workflow
- README includes instructions for running the UI locally

---

## Phase G — Guardrails

### - [ ] TASK-24: Build guardrail ensemble

**Inputs:**
- WildGuard, Granite Guardian, ShieldGemma model access (via hosted API or HuggingFace)
- Presidio

**Outputs:**
- `guardrails/__init__.py`
- `guardrails/ensemble.py`
- `guardrails/profiles/default.yaml`

**Steps:**

1. Create `guardrails/profiles/default.yaml` defining:
   - `high_stakes_categories` (list — use OR logic: these categories block on either model flagging)
   - `soft_categories` (list — use AND logic: both models must flag to block)
2. Create `guardrails/ensemble.py` with `GuardrailEnsemble` class. Constructor: loads profile from `guardrails/profiles/`, initialises Presidio `AnalyzerEngine` and `AnonymizerEngine`. Method: `check(content: str, agent_id: str, objective_id: str, mtp_version: str) -> GuardrailResult`. `GuardrailResult`: `passed` (bool), `violations` (list[GuardrailViolation]), `redacted_content` (str | None). `GuardrailViolation`: `category` (str), `blocking_model` (str), `severity` (str).
3. `check()` pipeline:
   1. ShieldGemma pre-screen via API — if flagged for obvious harm, return immediately without calling heavier models
   2. WildGuard input classification via API
   3. Granite Guardian output validation via API
   4. Apply OR/AND logic from profile
   5. If passed, run Presidio PII redaction and return `redacted_content`
   6. If blocked, emit an `AgentAction` event with violation details to ArcadeDB before returning
4. For v1, guardrail model APIs may be stubbed with a configurable `GUARDRAILS_MODE` env var: `'live'` calls real APIs, `'stub_pass'` always passes (for dev), `'stub_block'` always blocks (for testing). Default to `'live'`.
5. All agent output must pass through `check()` before delivery. Create a decorator `@guardrailed(agent_id, objective_id, mtp_version)` that wraps any async function returning `str` and applies the ensemble check.

**Done when:**
- `check()` returns `GuardrailResult` with `passed=False` for a known prompt injection payload
- `check()` returns `redacted_content` with PII removed via Presidio
- Violation events are emitted to ArcadeDB before returning a blocked result
- `@guardrailed` decorator correctly intercepts output and applies `check()`
- `GUARDRAILS_MODE='stub_pass'` bypasses all API calls
- mypy strict passes

---

## Phase H — Observability

### - [ ] TASK-25: Configure Langfuse OpenTelemetry export

**Inputs:**
- Langfuse Cloud account and API keys in environment

**Outputs:**
- `shared/observability/__init__.py`
- `shared/observability/tracing.py`

**Steps:**

1. Create `shared/observability/tracing.py`. Import and configure the Langfuse OpenTelemetry SDK. Create `configure_tracing(agent_type: str, agent_id: str, objective_id: str, mtp_version: str) -> None` that initialises the OTel tracer with Langfuse as the exporter and sets resource attributes: `agent_type`, `agent_id`, `objective_id`, `mtp_version`.
2. Create a context manager `trace_llm_call(model: str, role: str) -> Iterator[Span]` that wraps any OpenRouter call and records: model name, input token count, output token count, estimated cost (compute from token counts and known per-token prices), latency in milliseconds.
3. Wrap the `OpenRouterClient.complete()` method with `trace_llm_call` automatically — no agent code should need to call it manually.
4. `configure_tracing` must be called at agent startup. If `LANGFUSE_SECRET_KEY` is not set, log a warning and use a no-op tracer rather than failing.

**Done when:**
- A test LLM call produces a trace visible in Langfuse Cloud with model, token counts, cost, and latency
- `agent_type`, `agent_id`, `objective_id`, `mtp_version` appear as trace attributes
- Missing Langfuse credentials produce a warning not a crash
- mypy strict passes

---

### - [ ] TASK-26: Configure Prometheus custom metrics

**Inputs:**
- `prometheus-client` library

**Outputs:**
- `shared/observability/metrics.py`

**Steps:**

1. Create `shared/observability/metrics.py` defining all five required custom metrics using `prometheus-client`:
   - `signal_emission_total` (Counter, labels: `agent_id`, `domain`)
   - `checkpoint_write_total` (Counter, labels: `objective_id`)
   - `verification_verdict_total` (Counter, labels: `verdict` — confirmed/contradicted/inconclusive)
   - `objective_completion_total` (Counter, labels: `domain`)
   - `escalation_total` (Counter, labels: `reason`)
2. Export increment functions for each: `record_signal_emitted(agent_id, domain)`, `record_checkpoint_written(objective_id)`, `record_verification_verdict(verdict)`, `record_objective_completed(domain)`, `record_escalation(reason)`. These are the only way agent code should update metrics — no direct Counter access.
3. Start a Prometheus HTTP metrics server on port 9090 when `METRICS_ENABLED=true`. This is the endpoint Render's observability or an external scraper reads from.

**Done when:**
- All five metric types are registered and incrementable
- Metrics server starts on port 9090 when `METRICS_ENABLED=true`
- Unit test verifies each `record_` function increments the correct counter
- mypy strict passes

---

## Phase I — Tests

### - [ ] TASK-27: Write unit tests for shared libraries

**Inputs:**
- TASK-08 through TASK-13 complete

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

1. Write tests using pytest and pytest-asyncio. Mock all external calls (httpx, ArcadeDB, OpenRouter) using `unittest.mock` or `pytest-mock`.
2. `test_acap_enforcer.py` must cover: permitted tool passes, unpermitted tool raises `ACAPViolationError`, violation is logged to ArcadeDB before raising, MCP connection check for unlisted server raises.
3. `test_event_schema.py` must cover: all five valid event types parse correctly, missing `agent_id` raises `EventSchemaError`, confidence outside range raises `EventSchemaError`.
4. `test_promotion.py` must cover: rejected hypothesis → `promote_durable` with `NEGATIVE_KNOWLEDGE` edge, operational state → `discard`, low confidence → `return_to_log`, matching existing node → `reinforce`.
5. `test_graph_schema.py` must cover: decay calculation for each node type at 1 day, 30 days, 365 days. Verify `ProductStructure` decays slower than `CustomerSignal`.
6. Achieve 80% line coverage on `shared/` as reported by pytest-cov.

**Done when:**
- `pytest tests/unit/` exits 0
- `pytest --cov=shared --cov-report=term-missing` shows >= 80% coverage
- mypy strict passes on all test files

---

### - [ ] TASK-28: Write integration tests

**Inputs:**
- Docker installed
- TASK-07 migration runner
- TASK-14 through TASK-18 complete

**Outputs:**
- `tests/integration/conftest.py`
- `tests/integration/test_event_log.py`
- `tests/integration/test_knowledge_graph.py`
- `tests/integration/test_coordination_loop.py`

**Steps:**

1. Create `tests/integration/conftest.py` with pytest fixtures:
   - `arcadedb_client` (starts ArcadeDB via docker-compose, runs migrations, yields client, tears down)
   - `postgres_url` (starts Postgres via docker-compose, yields connection string, tears down)
   
   Use pytest-asyncio for async tests.
2. `test_event_log.py`: emit one of each event type, verify it can be polled back with cursor-based query, verify events outside retention window are not returned (use a mock retention date), verify duplicate signal within retention window is detected by novelty check.
3. `test_knowledge_graph.py`: create a `ProductStructure` node, traverse from it, verify confidence decays after simulated time, verify `reinforce_node` resets decay clock, verify `flag_for_revalidation` sets `revalidation_required=True`.
4. `test_coordination_loop.py`: run a minimal coordination loop — emit a synthetic high-confidence signal, verify orchestration creates an objective, verify verification subgraph runs and emits a verdict, verify objective subgraph runs and writes a checkpoint, verify promotion runs at objective closure and adds a node to the knowledge graph.

**Done when:**
- All integration tests pass against live ArcadeDB and Postgres Docker containers
- `test_coordination_loop.py` passes end-to-end without errors
- CI runs integration tests as a separate job with Docker services

---

### - [ ] TASK-29: Write prompt regression tests

**Inputs:**
- TASK-14, TASK-15, TASK-16 complete
- OpenRouter API key in environment

**Outputs:**
- `tests/agent/test_exploratory_regression.py`
- `tests/agent/test_verification_regression.py`
- `tests/agent/test_objective_regression.py`
- `tests/agent/fixtures/`

**Steps:**

1. Create fixture files in `tests/agent/fixtures/` for each agent type: sample mandate for exploratory, sample finding for verification, sample objective with checkpoint for objective.
2. `test_exploratory_regression.py`: run exploratory agent against fixture mandate, assert output is a list of `AgentSignal` objects with correct schema, assert confidence values are floats in [0,1], assert no objective registry writes occur. Use `GUARDRAILS_MODE=stub_pass`.
3. `test_verification_regression.py`: run verification subgraph with a fixture finding and `originating_model_family=ModelFamily.DEEPSEEK`, assert `ModelFamilyError` is NOT raised (Qwen verifies DeepSeek finding), assert verdict is one of confirmed/contradicted/inconclusive, assert `verdict_confidence` is in [0,1].
4. `test_objective_regression.py`: run objective subgraph with a fixture objective that has a prior checkpoint, assert the agent does not re-investigate hypotheses marked 'confirmed' or 'rejected' in the checkpoint, assert a new checkpoint is written during execution.
5. These tests call real OpenRouter APIs. Use DeepSeek V4 Flash for all to keep cost low during CI. Mark with `@pytest.mark.agent_regression` to allow selective skipping.

**Done when:**
- All three regression test files pass when run with a valid OpenRouter API key
- Verification test confirms `ModelFamilyError` is not raised for correct family pairing
- Objective test confirms checkpoint continuity — no re-investigation of concluded hypotheses
- Tests are marked `@pytest.mark.agent_regression` and can be excluded with `-m 'not agent_regression'`

---

### - [ ] TASK-30: Write ACAP boundary and secret scanning tests

**Inputs:**
- TASK-10, TASK-14 through TASK-18 complete

**Outputs:**
- `tests/agent/test_acap_boundaries.py`
- `tests/unit/test_no_hardcoded_secrets.py`

**Steps:**

1. `test_acap_boundaries.py`: for each agent type, attempt an action outside its ACAP (exploratory writes to objective registry, objective reads an unpermitted MCP connection, verification attempts to use same model family as originator). Assert `ACAPViolationError` is raised for each. Assert each violation generates an event in the ArcadeDB event log.
2. `test_no_hardcoded_secrets.py`: scan all Python files in the repository for patterns matching API keys, tokens, and passwords. Patterns to check: strings matching `/sk-[a-zA-Z0-9]{40,}/`, `/[A-Z0-9]{32,}/`, any `.env` variable value used as a literal. Fail if any match is found outside of `.env.example` (which uses placeholder values only).

**Done when:**
- All ACAP boundary violations raise `ACAPViolationError`
- All violations generate ArcadeDB event log entries
- Secret scanning test passes on a clean repository
- Secret scanning test fails if a fake API key is added to a source file (verify this with a test of the test)

---

## Phase J — CI/CD and Deployment

### - [ ] TASK-31: Configure GitHub Actions CI pipeline

**Inputs:**
- All previous tasks complete
- GitHub repository created

**Outputs:**
- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`

**Steps:**

1. Create `.github/workflows/ci.yml` triggered on `pull_request` to `main`. Jobs in order:
   1. **lint**: runs `uv run ruff check .` — fails on any warning
   2. **type-check**: runs `uv run mypy . --strict`
   3. **schema-validation**: runs `python -m schema.migrate --dry-run` to validate schema files without executing, plus checks that no existing migration file in `schema/*/migrations/` has been modified (compare git diff against main)
   4. **unit-tests**: runs `uv run pytest tests/unit/ --cov=shared --cov=agents --cov-fail-under=80`
   5. **acap-validation**: runs a script that loads all four agent type ACAPs from the reference config and validates them
   6. **event-schema-tests**: runs a script that verifies each agent type only emits events matching canonical schemas
   7. **integration-tests**: uses `services:` arcadedb and postgres Docker containers, runs `uv run pytest tests/integration/`
   8. **secret-scan**: runs `uv run pytest tests/unit/test_no_hardcoded_secrets.py`
   
   All jobs are required status checks — PR cannot merge until all pass.
2. Create `.github/workflows/deploy.yml` triggered on `push` to `main`. Jobs:
   1. **deploy-arcadedb**: if `infra/render/arcadedb.yaml` changed, triggers Render deploy hook
   2. **deploy-orchestration**: if `agents/orchestration/` or `agents/verification/` or `agents/objective/` or `shared/` changed, triggers Render deploy hook for orchestration background worker
   3. **deploy-exploratory**: if `agents/exploratory/` or `shared/` changed, triggers Render deploy hooks for each cron job service
   4. **run-migrations**: after any deploy, runs `python -m schema.migrate` via Render one-off job API
3. Add branch protection rule documentation to README: require all CI checks, require 1 reviewer, require linear history.

**Done when:**
- CI pipeline runs on a test PR and all jobs complete
- A PR with a ruff lint error fails the lint job
- A PR modifying an existing migration file fails the schema-validation job
- A PR with coverage below 80% fails the unit-tests job

---

### - [ ] TASK-32: Configure Render deployment

**Inputs:**
- Render account with API access
- ArcadeDB Docker image
- All agent code complete

**Outputs:**
- `infra/render/arcadedb.yaml`
- `infra/render/orchestration.yaml`
- `infra/render/exploratory.yaml`
- `infra/render/render.yaml`

**Steps:**

1. Create `infra/render/render.yaml` as the Render Blueprint (Infrastructure as Code) defining all services:
   1. **arcadedb**: `type=private_service`, `image=arcadedata/arcadedb:latest`, `disk={name=arcadedb-data, mountPath=/arcadedb-data, sizeGB=50}`, `envVars=[JAVA_OPTS with password config]`
   2. **postgres**: `type=pserv` (managed Postgres), `plan=starter`, `databaseName=agent-operations`
   3. **orchestration**: `type=worker`, `buildCommand='uv sync'`, `startCommand='python -m agents.orchestration'`, `plan=starter`, `envVars=[all required secrets as references]`
   4. **implementation**: `type=worker`, `buildCommand='uv sync'`, `startCommand='python -m agents.implementation'`, `plan=starter`, `envVars=[all required secrets as references]`
   5. **approval-ui**: `type=web`, `buildCommand='cd ui && npm install && npm run build'`, `startCommand='cd ui && npm start'`, `plan=starter`, `envVars=[ARCADEDB_URL, ARCADEDB_USER, ARCADEDB_PASSWORD]`
   6. **exploratory-{mandate_name}**: `type=cron`, `schedule='0/30 * * * *'`, `buildCommand='uv sync'`, `startCommand='python -m agents.exploratory --mandate={mandate_name}'`, `plan=starter` for each configured mandate
2. All services must be in the same region. Set via `RENDER_REGION` env var, default to `oregon`.
3. Create a Makefile with targets:
   - `make deploy-all` (triggers full Render Blueprint sync)
   - `make migrate` (runs schema migrations via Render one-off job)
   - `make logs-orchestration` (tails orchestration worker logs via Render CLI)

**Done when:**
- `render.yaml` validates against Render Blueprint schema
- All services are in the same region (verified by inspecting rendered config)
- `make migrate` command correctly invokes schema migration

---

### - [ ] TASK-33: Write deployment and operations runbook

**Inputs:**
- TASK-31, TASK-32 complete

**Outputs:**
- `docs/runbook.md`

**Steps:**

1. Create `docs/runbook.md` covering:
   1. **Initial deployment** — steps to deploy from scratch to a new Render account
   2. **Required secrets** — table of all environment variables, what they are, where to obtain them
   3. **Running schema migrations** — when and how
   4. **Monitoring** — where to find Langfuse traces, how to check Prometheus metrics, where to see Render service logs
   5. **Adding a new exploratory mandate** — YAML structure, where to add it, how to deploy
   6. **Human approval workflow** — how to access the approval UI, review pending objectives, approve/reject/defer implementation tasks, track approval history
   7. **Implementation agent operations** — how implementation agents are spawned, what they do, how to monitor their progress, how to handle failures
   8. **Escalation queue** — where human review items appear, how to action them
   9. **Common failure modes** — ArcadeDB connection failures, OpenRouter rate limits, checkpoint write failures, implementation agent failures — with diagnosis steps and remediation

**Done when:**
- Runbook exists at `docs/runbook.md`
- Required secrets table is complete and matches `.env.example`
- Human approval workflow section explains how to access UI, review objectives, and approve/reject/defer tasks
- Implementation agent operations section explains spawning, monitoring, and failure handling
- Escalation queue section explains where items appear and how a human acts on them

---

## Phase K — Reference Configuration

### - [ ] TASK-34: Create reference project configuration

**Inputs:**
- TASK-13 config loader
- `config/schema/` schemas

**Outputs:**
- `config/reference/mtp.yaml`
- `config/reference/acap_overrides.yaml`
- `config/reference/mandates/competitor_monitor.yaml`

**Steps:**

1. Create `config/reference/mtp.yaml` as the minimal valid MTP for testing. Use a fictional organisation — do not reference Campaign Monitor or any real project. Example:
   - `purpose='Continuously improve the quality and reliability of the software systems we operate'`
   - `constraints=['Never expose customer data', 'Never deploy to production without a checkpoint', 'Escalate all changes exceeding $1000 resource cost']`
   - `intent_description='We exist to make software that works well and gets better over time.'`
2. Create `config/reference/acap_overrides.yaml` with per-agent-type overrides that are minimally permissive for testing:
   - **exploratory**: `permitted_tools=['web_search']`, `permitted_mcp_connections=[]`, `permitted_event_types=['AgentSignal','AgentAction']`
   - **objective**: `permitted_tools=['web_search','code_read']`, `permitted_mcp_connections=['https://mcp.example.com/v1']`, `permitted_event_types=['AgentAction','AgentFinding','AgentCheckpoint']`
3. Create `config/reference/mandates/competitor_monitor.yaml`:
   - `name='competitor_monitor'`
   - `domain='competitive_intelligence'`
   - `polling_interval_minutes=30`
   - `signal_threshold=0.6`
   - `search_queries=['competitor product updates', 'industry announcements']`
4. Verify: `load_project_config('config/reference')` succeeds with no validation errors.

**Done when:**
- `load_project_config('config/reference')` succeeds
- Reference config contains no real project names, organisation names, or credentials
- All four agent type ACAPs can be loaded and validated against the reference config

---

### - [ ] TASK-35: Final validation and AGENTS.md self-test

**Inputs:**
- All previous tasks complete

**Outputs:**
- No new files — validation only

**Steps:**

1. Run the full CI pipeline locally: `uv run ruff check . && uv run mypy . --strict && uv run pytest tests/unit/ --cov=shared --cov=agents --cov-fail-under=80 && uv run pytest tests/integration/ && uv run pytest tests/agent/ -m 'not agent_regression'`
2. Run the secret scan: `uv run pytest tests/unit/test_no_hardcoded_secrets.py`
3. Run `load_project_config('config/reference')` and assert it returns a valid `ProjectConfig`
4. Verify `AGENTS.md` is accurate by reading it and checking each claim:
   1. Every listed directory exists
   2. The autonomous modification rules match what the ACAP enforcer actually enforces
   3. The event schema contract matches what `emit_validated` actually requires
   4. The listed permitted network calls match what's in the reference ACAP
5. If any discrepancy is found in `AGENTS.md`, update `AGENTS.md` to match the actual implementation — never change the implementation to match `AGENTS.md` without human review.
6. Create a final commit: `TASK-35: validated — all checks pass, AGENTS.md accurate`

**Done when:**
- Full local CI pipeline exits 0
- Secret scan exits 0
- Reference config loads successfully
- `AGENTS.md` accurately describes the actual repository structure and enforcement rules
- Final commit exists with message `TASK-35: validated — all checks pass, AGENTS.md accurate`

---

All 35 tasks complete. The Agent Operations repository is ready for first deployment.

Proceed with:
1. Creating the Render services from `infra/render/render.yaml`
2. Setting all required environment variables as Render secrets
3. Running `make migrate` to initialise the ArcadeDB schema
4. Running the orchestration background worker
5. Running the human approval UI (`cd ui && npm install && npm start`)
6. Verifying traces appear in Langfuse Cloud

**References:** Agent Operations Requirements Document (project); The Event Log and Agent Types (project); AI-Native Organization Blueprint (project); ArcadeDB documentation; Render.com documentation; LangGraph documentation; OpenRouter documentation.
