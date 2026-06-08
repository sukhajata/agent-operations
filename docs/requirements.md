# Agent Operational Framework

**Agent Platform — Initial Repository Requirements**

June 2026 — v0.1 — Internal

## 1. Purpose and Scope

This is an outline of a reusable agent platform — the executable form of ExO 3.0's Intelligence Stack. It provides the operational substrate for ambient, purposive organisational intelligence: agents that sense opportunity, verify findings, execute toward objectives, and accumulate knowledge continuously, without requiring human initiation at every step.

The platform is a standalone infrastructure component, separate from any product or codebase it operates on. It connects to target projects via Model Context Protocol (MCP) and is configured per project and per organisation through externally supplied YAML definitions. The same platform binary can serve multiple projects and multiple organisations.

It is not an agent for a specific product. It is the operational infrastructure that makes any product capable of continuous, purposive self-improvement. It represents the Intelligence Stack layer of ExO 3.0 — specifically the implementation of DRIVE (Decision Architecture, Recursive Learning, Integrated Intelligence, Velocity, Elastic Agency) and the Safe Autonomy and Purpose Control components of SHAPE.

### 1.1 What This Document Covers

This document specifies the requirements for the initial repository — the minimum viable platform sufficient to run all four agent types against a single configured project, with full observability, ACAP-governed boundaries, and the five-store data architecture. It does not specify requirements for multi-tenant SaaS deployment, commercial licensing, or multi-organisation governance — those are subsequent phases.

### 1.2 What Is Explicitly Out of Scope

- Multi-organisation governance and cross-organisation A2A protocols
- Commercial packaging, licensing, or distribution
- A conversational agent UI (specified as a separate future component)
- Self-hosted guardrail GPU infrastructure — initial deployment uses cloud-hosted guardrail APIs
- NeMo Guardrails multi-turn detection — specified as future when production-ready
- High-availability ArcadeDB cluster — initial deployment runs single-node

---

## 2. Architecture Overview

The platform is organised around five stores and four agent types. The stores provide the data substrate; the agent types provide the operational behaviour. Neither is derivable from the other — both must be designed explicitly.

### 2.1 The Five Stores

| Store | Role and nature |
|-------|----------------|
| **Identity Store** | What are we and what are we allowed to do? Holds the MTP, ACAPs, governance rules, and policy constraints. Versioned, strongly consistent. Agents read from it on every decision cycle. Writes are rare, human-governed, and go through formal governance. |
| **Objective Registry** | What are we trying to achieve and where are we? Holds active objectives as persistent entities: status, priority signal, cognitive checkpoint, progress, assigned agents. Updated by checkpoint events. Operational artifacts discarded at objective closure. |
| **Event Log** | What has happened recently? Append-only, time-partitioned, retention-managed. The coordination substrate through which all agent types communicate. Implemented in ArcadeDB time-series with per-type retention policies. |
| **Knowledge Graph** | What do we know and how do things relate? Persistent, temporally weighted, queryable by relationship. Confidence decays by node type; reinforced by ongoing agent activity. The accumulation of organisational learning across objectives and time. |
| **Structural Artifacts** | What actually exists right now? Codebase, schemas, APIs, documentation. Ground truth accessed directly via MCP. Referenced by the knowledge graph but not stored in it. |

### 2.2 The Four Agent Types

| Type | Character | Description |
|------|-----------|-------------|
| **Exploratory** | Always-on scouts | Scheduled polling against standing mandates. Observes the external environment and internal system state. Self-filters before emitting to the event log. Source of ambient organisational intelligence. |
| **Verification** | Short-lived investigators | Spawned in response to findings above a significance threshold. Must use a different model family from the originating agent. Attempts to disprove findings, not confirm them. Terminates on completion. |
| **Objective** | Assigned executors | Triggered by objective assignment from the orchestration layer. Reads event log and knowledge graph for research context. Writes cognitive checkpoints at decision boundaries. Replaceable via checkpoint handoff. |
| **Orchestration** | System allocators | Continuous polling against event log and objective registry. Watches signal density and objective health. Creates and closes objectives. Provisions and terminates agents. Escalates to human review at defined thresholds. |
| **Implementation** | Code executors | Triggered by human-approved objectives. Reads the plan from the objective agent's checkpoint. Executes code changes, writes files, runs tests. Emits implementation events. Terminates on completion or failure. |

### 2.3 The Coordination Loop

The five agent types operate in a self-sustaining loop with a human gate: **Sense → Reinforce → Verify → Commit → Execute → Checkpoint → Promote → Approve → Implement → Close**. The loop does not require human initiation below the escalation threshold. Humans govern the thresholds, handle escalations, own the identity store, set exploratory agent standing mandates, and approve implementation tasks before execution.

### 2.4 Technology Stack

| Layer | Technology and rationale |
|-------|-------------------------|
| **Inference** | OpenRouter API. DeepSeek V4 Flash (exploratory, orchestration). Qwen3.7-Plus (verification — different model family). DeepSeek V4 Pro (objective — prompt caching enabled). |
| **Data** | ArcadeDB single instance. Time-series (event log), graph (knowledge graph), document (identity store, objective registry), vector (embeddings). Apache 2.0, self-hosted on Fly.io. |
| **LangGraph checkpoints** | PostgreSQL via `langgraph-checkpoint-postgres`. Aurora or Neon. LangGraph open-source only — no LangSmith Deployment dependency. |
| **Observability — LLM** | Langfuse Cloud. OpenTelemetry export. Traces, token costs, prompt quality. Core tier ($29/month) for initial deployment. |
| **Observability — infrastructure** | Fly.io native Prometheus/Grafana. Datadog via OpenTelemetry exporter for unified alerting. Custom agent metrics as Prometheus gauges. |
| **Guardrails** | WildGuard 7B (input), Granite Guardian 8B (output), ShieldGemma 2B (pre-screen), Presidio (PII redaction). Self-hosted on Fly.io GPU machines. |
| **Deployment** | Fly.io. Exploratory and orchestration agents as EventBridge-equivalent scheduled tasks. Verification agents as triggered ephemeral Machines. Objective agents as on-demand Machines. |
| **Agent workflow** | LangGraph open-source. One state graph per agent type. `PostgresSaver` checkpointer against Aurora/Neon. |
| **Product access** | Model Context Protocol (MCP). Per-project ACAP defines which MCP connections agents may use. |
| **CI/CD** | GitHub Actions. Pre-merge gate: lint, type check, unit tests, prompt regression tests, ACAP validation, event schema validation. Deployment: `fly deploy` on merge to main. |

### 2.5 Polling Architecture and ArcadeDB Access Strategy

**Polling, not push:**

The platform uses a polling architecture rather than event-driven push notifications. All agents poll the event log at configurable intervals using cursor-based queries (`WHERE ts > :last_processed_ts`). This design choice provides:

- **Cursor persistence** — agents maintain their position in the event stream across restarts via LangGraph checkpoints
- **Backpressure control** — agents control their consumption rate rather than being overwhelmed by event bursts
- **Simplicity** — no need for message queue infrastructure or pub/sub coordination
- **Idempotency** — polling with cursors naturally handles duplicate processing

ArcadeDB supports triggers and event notifications, but the platform deliberately avoids them in favor of explicit polling for predictability and debugging.

**ArcadeDB access strategy:**

Agents access ArcadeDB through two complementary mechanisms:

1. **Direct HTTP client** (`shared/arcadedb/client.py`) — for high-frequency operations:
   - Cursor-based event log polling (exploratory, orchestration agents)
   - Bulk event writes (all agents emitting to event log)
   - Graph traversal queries (objective agent research loop)
   - Checkpoint writes (objective agent decision boundaries)
   
   Direct access provides better performance, connection pooling, and query optimization for hot paths.

2. **ArcadeDB built-in MCP server** — for ad-hoc exploration:
   - Objective agents exploring the knowledge graph during investigation
   - Verification agents querying for contrary evidence
   - Human operators debugging via MCP-compatible tools
   
   The MCP server (`http://arcadedb:2480/api/v1/mcp`) exposes `query`, `execute_command`, `get_schema`, and `list_databases` tools. Agents can use this for flexible, exploratory queries where the schema or query structure isn't known in advance.

**Access control:**

Both access paths are governed by ACAP. The direct client enforces ACAP boundaries in application code. The MCP server enforces them via ArcadeDB's `mcp-config.json` permissions (`allowReads`, `allowInsert`, etc.) and user authorization.

### 2.6 ArcadeDB Multimodal Storage Model

ArcadeDB is a single storage engine with multiple type systems layered on top. All data types — documents, graph vertices/edges, time series, and vectors — coexist in one database and can reference each other natively.

**Type categories:**

- `DOCUMENT` — structured records (MTP, ACAP definitions, objective records)
- `VERTEX` / `EDGE` — graph nodes and relationships (knowledge graph)
- `TIMESERIES` — time-stamped events with retention policies (event log)
- Vector embeddings — for semantic similarity queries

**Cross-type linking:**

Types can be linked via edges regardless of their category. For example:

- An `ObjectiveRecord` (document) can link to its `AgentCheckpoint` events (time series) via `HAS_CHECKPOINT` edges
- A `ProductStructure` node (graph vertex) can link to the `AgentFinding` events (time series) that created it
- An `ACAPDefinition` (document) can be queried alongside the scope violation events that reference it

This eliminates the need for separate databases or application-level joins. Relationships are native to the storage engine.

**Retention caveat:**

TimeSeries types have retention policies that auto-delete old data. If events need to persist longer than their retention window (e.g., for long-term knowledge accumulation), they must be promoted to regular Document types before expiration.

---

## 3. Repository Structure

The platform repository contains only reusable infrastructure — no project-specific code, no hardcoded product assumptions. Project-specific configuration (MTP, ACAPs, standing mandates, knowledge graph domain model) is loaded at runtime from an external configuration path, which may live in the target project's repository or in a separate configuration repository.

| Path | Contents and purpose |
|------|---------------------|
| `agents/exploratory/` | Exploratory agent implementation. LangGraph state graph. Standing mandate loader. Signal quality filter. Novelty check against event log. |
| `agents/verification/` | Verification agent implementation. Independence enforcement — model family check at instantiation. Adversarial investigation pattern. Confidence-weighted verdict emission. |
| `agents/objective/` | Objective agent implementation. Research loop (graph → MCP → event log delta). Checkpoint discipline at node boundaries. Scope enforcement via ACAP. |
| `agents/implementation/` | Implementation agent implementation. Polls for approved objectives. Executes code changes from checkpoint plans. Emits implementation events. ACAP-enforced file operations. |
| `agents/orchestration/` | Orchestration agent implementation. Signal density monitor. Objective lifecycle manager. Agent provisioner. Escalation logic. Knowledge graph promotion trigger. Human approval workflow coordination. |
| `shared/event_schemas/` | Canonical event type definitions and validation. All five event categories: signals, actions, findings, checkpoints, state transitions. Schema version management. |
| `shared/acap/` | ACAP loader, validator, and runtime enforcer. Reads from identity store. Applies boundary checks before each agent action. Scope violation detection. |
| `shared/arcadedb/` | ArcadeDB client. Query helpers for each store type. Time-series polling with cursor management. Graph traversal patterns. Confidence decay functions. |
| `shared/openrouter/` | OpenRouter client. Agent-role to model mapping. Provider routing configuration per agent type. Prompt caching configuration for objective agents. |
| `shared/mcp/` | MCP connection manager. Loads permitted connections from ACAP. Structural artifact access patterns. Ground truth read helpers. |
| `schema/timeseries/` | ArcadeDB TimeSeries type definitions for each event category. Retention policy configuration. Tag and field schemas. |
| `schema/graph/` | Knowledge graph node type definitions. Base node types: product structure, decision, investigation, competitor, customer pattern. Confidence decay rates by type. |
| `schema/identity/` | Identity store schema. MTP document structure. ACAP definition schema. Governance rule schema. Version management. |
| `schema/migrations/` | Sequential schema migration scripts. Immutability enforced by CI — existing migrations cannot be modified, only new ones added. |
| `guardrails/` | Guardrail ensemble configuration. Per-agent-type guardrail profiles. Ensembling logic (OR/AND per category). PII redaction configuration. |
| `config/schema/` | Project configuration schema definitions. `mtp.yaml` structure. `acap_overrides.yaml` structure. Mandate definition format. Versioned configuration API. |
| `infra/fly/` | Fly.io deployment configuration. Per-agent-type `fly.toml`. Scheduled task definitions. Machine sizing. Volume configuration for ArcadeDB. |
| `tests/unit/` | Unit tests for shared libraries, agent logic, schema validation, ACAP enforcement, promotion classification. |
| `tests/integration/` | Integration tests running ArcadeDB in Docker. Full coordination loop tests. Event schema compliance. Graph promotion verification. |
| `tests/agent/` | Prompt regression tests per agent type. ACAP boundary tests. Event schema emission tests. Confidence scoring tests. |
| `AGENTS.md` | Root-level agent instructions. Repository layout. Which directories agents may modify autonomously. Event schema they must conform to. ACAP constraints applying to this repository itself. |

---

## 4. Functional Requirements

### 4.1 Identity Store and Configuration

#### REQ-ID-01: MTP Loading and Version Tracking

**Description:**

The platform must load the project MTP from the configured external path on startup and on each agent decision cycle. The current MTP version must be attached to every event emitted by every agent. Version mismatches between the loaded MTP and the identity store must be detected and logged.

**Acceptance:**

- MTP loads successfully from a valid `mtp.yaml` at the configured path
- Every emitted event carries the MTP version string
- Startup fails with a clear error if no valid MTP is found
- Version change between startup and runtime is logged as a governance event

#### REQ-ID-02: ACAP Loading and Runtime Enforcement

**Description:**

The platform must load Agent Capability and Authorization Profiles from the identity store for each agent type. ACAP boundaries must be enforced before every agent action — tool calls, event emissions, objective modifications, and MCP reads. Scope violations must be rejected and logged, not silently ignored.

**Acceptance:**

- Each agent type loads its ACAP from the identity store at instantiation
- Tool calls outside ACAP scope are rejected before execution
- MCP connections not listed in the agent's ACAP are inaccessible
- Scope violations are emitted as state transition events to the event log
- ACAP validation passes for all four agent types against a valid project configuration

#### REQ-ID-03: Project Configuration Schema Validation

**Description:**

The platform must validate all project configuration files against published schemas on startup. Invalid configuration must produce actionable error messages identifying the specific field and violation. The configuration schema must be versioned, and the platform must support the current schema version.

**Acceptance:**

- Startup fails with a specific error if `mtp.yaml` fails schema validation
- Startup fails with a specific error if any ACAP definition fails schema validation
- Error messages identify the failing field and the constraint violated
- A valid reference configuration passes all schema checks

### 4.2 Event Log

#### REQ-EL-01: ArcadeDB TimeSeries Schema Initialisation

**Description:**

The platform must initialise the required ArcadeDB TimeSeries types on first run if they do not exist. Five types are required: `AgentSignal` (7-day retention), `AgentAction` (30-day retention), `AgentFinding` (90-day retention), `AgentCheckpoint` (180-day retention), `ObjectiveTransition` (indefinite). Initialisation must be idempotent — safe to run against an already-initialised database.

**Acceptance:**

- All five TimeSeries types are created with correct retention policies on a fresh ArcadeDB instance
- Re-running initialisation against an existing database produces no error and no data loss
- Each type enforces the correct tag and field schema on write

#### REQ-EL-02: Event Emission

**Description:**

All four agent types must emit events to the event log using the canonical event schemas. Every event must carry: event type, timestamp (nanosecond precision), agent identity, objective reference, MTP version, payload structured to the event type, confidence score (for signals and findings), and novelty flag. Events that fail schema validation must be rejected before write.

**Acceptance:**

- Each agent type emits at least one event type successfully in integration tests
- Schema-invalid events are rejected and logged, not written
- All required fields are present and correctly typed on every emitted event
- Novelty check suppresses duplicate signals within the retention window

#### REQ-EL-03: Cursor-Based Polling

**Description:**

All consuming agents must read from the event log using cursor-based queries (`WHERE ts > :last_processed_ts`). Each agent must maintain its own cursor in working context. Polling intervals must be configurable per agent type. The polling implementation must be efficient — queries must use ArcadeDB's time-partitioned index and not perform full table scans.

**Acceptance:**

- Exploratory and orchestration agents poll at a configurable interval (default: 30 seconds)
- Verification and objective agents read relevant events after instantiation using a cursor
- Query execution plans confirm partition pruning is occurring (no full scans)
- Cursor state survives agent restart via LangGraph checkpoint

### 4.3 Knowledge Graph

#### REQ-KG-01: Graph Schema Initialisation

**Description:**

The platform must initialise the required ArcadeDB graph node and edge types on first run. Base node types: `ProductStructure`, `DecisionRecord`, `InvestigationFinding`, `CompetitorCapability`, `CustomerTheme`, `CustomerSignal`. Each node type must carry confidence score, initial confidence, decay rate, and last reinforced timestamp as schema properties. Initialisation must be idempotent.

**Acceptance:**

- All base node types exist with correct properties after initialisation
- Re-running initialisation against an existing graph produces no error and no data loss
- Confidence, decay rate, and last reinforced timestamp are present and correctly typed on each node type

#### REQ-KG-02: Confidence Decay

**Description:**

The platform must implement confidence decay for all knowledge graph nodes. Decay rates are node-type-specific: `ProductStructure` (slow — invalidated by deployment events), `DecisionRecord` (very slow), `InvestigationFinding` (medium), `CompetitorCapability` (medium with explicit revalidation period), `CustomerTheme` (medium — reinforced by signal flow), `CustomerSignal` (fast). Nodes below the revalidation threshold must be flagged, not deleted.

**Acceptance:**

- Confidence values decay at the correct rate for each node type over simulated time
- Nodes below the revalidation threshold are flagged with a `revalidation_required` property
- Flagged nodes remain readable by agents with their epistemic status visible
- Reinforcement events reset the decay clock on the reinforced node

#### REQ-KG-03: Knowledge Promotion from Event Log

**Description:**

The orchestration agent must execute a promotion step at objective closure. Promotion classifies checkpoint content into: discard (operational state), promote as durable node, promote as medium-durability node, reinforce existing node, or return to event log as finding. Checkpoints themselves must not be written to the graph — only extracted epistemic content.

**Acceptance:**

- Objective closure triggers promotion step execution
- Confirmed findings from checkpoints appear as graph nodes after promotion
- Rejected hypotheses appear as negative-knowledge edges
- Operational state from checkpoints is not written to the graph
- Reinforcement updates confidence scores on existing nodes rather than creating duplicates

### 4.4 Agent Implementations

#### REQ-AG-01: Exploratory Agent — Scheduled Execution

**Description:**

The exploratory agent must execute on a configurable schedule (default: every 30 minutes) against its configured standing mandates. It must apply a quality threshold before emitting, and a novelty check against the event log before emitting a signal that matches an existing signal within the retention window. It must not write to the objective registry.

**Acceptance:**

- Exploratory agent executes on schedule without manual trigger
- Below-threshold observations are not written to the event log
- Duplicate signals within the retention window are suppressed
- Any attempt to write to the objective registry is rejected by ACAP enforcement
- At least one standing mandate type is supported in v1: competitor monitoring

#### REQ-AG-02: Verification Agent — Independence Enforcement

**Description:**

The verification agent must be instantiated with a different model family from the agent whose finding it is verifying. The model family check must occur at instantiation — it must not be possible to instantiate a verification agent with the same model family as the originating agent. The verification agent must be designed to attempt to disprove the finding, not confirm it.

**Acceptance:**

- Instantiation with the same model family as the originating agent raises an error
- Verification agent system prompt frames the task as adversarial investigation
- Verification verdict is emitted as a finding event with confidence score
- Agent terminates after emitting its verdict

#### REQ-AG-03: Objective Agent — Research Loop and Checkpoint Discipline

**Description:**

The objective agent must execute the research loop before forming a plan: graph traversal → MCP artifact reads → event log delta read → hypothesis formation. It must write a cognitive checkpoint at every meaningful decision boundary. The checkpoint must contain: hypotheses investigated, findings confirmed or rejected, current best understanding, recommended next action. A replacement agent seeded with the checkpoint must be able to resume without re-executing completed research.

**Acceptance:**

- Research loop executes in the correct order before plan formation
- Cognitive checkpoint is written at each LangGraph node boundary
- Checkpoint contains all four required fields
- A new agent instance seeded with the checkpoint passes a research continuity test — it does not re-investigate hypotheses marked as concluded in the checkpoint

#### REQ-AG-04: Orchestration Agent — Lifecycle Management

**Description:**

The orchestration agent must monitor signal density per objective domain and objective health (checkpoint recency, event density). It must create objectives when verified signals cross the configured significance threshold. It must escalate to the human review queue when: an objective exceeds the resource ceiling, a verification verdict is inconclusive above a significance threshold, or an agent has exceeded its ACAP boundaries. It must trigger knowledge graph promotion at objective closure.

**Acceptance:**

- Objective creation is triggered when signal density crosses the configured threshold
- Escalation events are written to a human review queue for all three escalation conditions
- Stalled objectives (no checkpoint within the configured window) are detected and flagged
- Knowledge graph promotion is triggered at every objective closure
- Orchestration agent makes no content decisions — only structural decisions

#### REQ-AG-05: Objective Agent — Verified Findings Only

**Description:**

Objective agents must only be instantiated with findings that have been confirmed by a verification agent. Unverified or contradicted findings must not trigger objective creation. The orchestration agent must enforce this verification gate before provisioning an objective agent. This ensures objective agents invest research effort only on validated signals, preventing wasted computation on false positives.

**Acceptance:**

- Objective creation is blocked when the triggering finding has not been verified
- Contradicted findings are discarded and do not enter the objective pipeline
- Inconclusive findings are escalated to the human review queue rather than triggering an objective
- The orchestration agent logs a gate decision event for every finding it evaluates (pass, block, escalate)
- Integration test confirms an unverified finding does not result in objective creation

#### REQ-AG-06: Verification Agent — Swarm Coordination

**Description:**

The orchestration agent must coordinate verification agent instantiation to prevent double-handling of findings. When the orchestration agent detects a finding requiring verification, it must: (1) mark the finding as `verification_pending` in the event log, (2) spawn a verification agent with that specific finding, (3) mark the finding as `verification_in_progress` to prevent other orchestration cycles from re-assigning it. Verification agents must not poll for work independently — they are spawned by orchestration with a specific finding to investigate. This swarm coordination pattern ensures each finding is verified exactly once, preventing wasted compute on duplicate verification attempts.

**Acceptance:**

- Orchestration agent marks findings as `verification_pending` when first detected
- Orchestration agent marks findings as `verification_in_progress` before spawning a verification agent
- Verification agents are instantiated with a specific finding, not a general "find work" mandate
- A finding marked `verification_in_progress` is not re-assigned to another verification agent
- When verification completes, the finding is marked `verified` or `contradicted` with the verdict
- If a verification agent fails mid-execution, the finding is reset to `verification_pending` for retry
- Integration test confirms no finding is verified by multiple agents simultaneously

#### REQ-AG-07: Implementation Agent — Human-Approved Execution

**Description:**

The implementation agent must only execute objectives that have been explicitly approved by a human. It polls the objective registry for objectives with `implementation_status='approved'` and `implementation_state` in `['to_do', 'pending']`. The agent reads the execution plan from the objective's cognitive checkpoint, performs code changes, writes files, runs tests, and emits `AgentAction` events for each step. The agent must enforce ACAP boundaries on all file operations and tool usage. On completion, it updates the objective status to `complete` and promotes findings to the knowledge graph. On failure, it writes a checkpoint and marks the objective as `stalled` for human review.

**Acceptance:**

- Implementation agent only processes objectives with `implementation_status='approved'`
- Implementation agent only processes objectives with `implementation_state` in `['to_do', 'pending']`
- Implementation agent reads the execution plan from the objective's cognitive checkpoint
- All file operations are logged as `AgentAction` events
- ACAP boundaries are enforced for all tool usage
- On completion, objective status is updated to `complete`
- On failure, a checkpoint is written and objective is marked `stalled`
- Integration test confirms unapproved objectives are not executed

### 4.5 Human Review and Approval

#### REQ-HR-01: Human Gate for Implementation

**Description:**

The platform must provide a human approval gate before implementation agents execute code changes. When an objective agent completes its research and creates an execution plan, the orchestration agent must mark the objective with `implementation_status='pending_approval'` and `implementation_state='to_do'`. A human reviewer must approve or reject the plan via a UI (CopilotKit-based) before an implementation agent can execute it. The approval decision must be stored in the objective registry with timestamp, reviewer identity, and optional comments. The implementation agent polls for approved objectives and only executes those with `implementation_status='approved'`.

**Acceptance:**

- Objective registry includes `implementation_status` field with values: `pending_approval`, `approved`, `rejected`, `deferred`
- Objective registry includes `implementation_state` field with values: `to_do`, `in_progress`, `complete`, `failed`
- Objective registry includes `approval_metadata` field with: `reviewer_id`, `approved_at`, `comments`
- Orchestration agent marks completed objectives as `implementation_status='pending_approval'`
- Human UI displays pending approval items with plan details and context
- Human can approve, reject, or defer with optional comments
- Approval decision is stored in objective registry with timestamp and reviewer identity
- Implementation agent only processes objectives with `implementation_status='approved'`
- Integration test confirms unapproved objectives cannot be executed
- UI is built with CopilotKit and provides a clear approval workflow

### 4.5 Guardrail Ensemble

#### REQ-GR-01: Four-Layer Ensemble

**Description:**

All agent outputs must pass through the four-layer guardrail ensemble before delivery or tool execution: ShieldGemma 2B pre-screen (~29ms), WildGuard 7B input classifier, Granite Guardian 8B output validator, Presidio PII redaction. OR logic applies for high-stakes categories. AND logic applies for categories prone to false positives on legitimate content. All block events must be logged with the violating category, the blocking model, and the full input/output.

**Acceptance:**

- ShieldGemma pre-screen runs on every output before heavier classifiers
- WildGuard and Granite Guardian both run on all substantive agent outputs
- Presidio PII redaction runs after content classification before any output leaves the platform
- Block events are written to the event log as action events with violation category
- A known prompt injection attempt is blocked before reaching the objective agent

### 4.6 MCP Integration

#### REQ-MCP-01: ACAP-Governed MCP Access

**Description:**

The platform must load MCP connections from the project ACAP definition. Agents must only be able to access MCP connections explicitly listed in their ACAP. Connection attempts to unlisted MCP servers must be rejected by the ACAP enforcer before the connection is made. MCP read operations must be logged as action events in the event log.

**Acceptance:**

- MCP connections not listed in the agent ACAP are inaccessible
- Successful MCP reads are logged as action events
- A valid project configuration with at least one MCP connection passes end-to-end read test
- Connection rejection is logged as a scope violation event

---

## 5. Non-Functional Requirements

### 5.1 Observability

#### REQ-OBS-01: LLM Trace Export

**Description:**

All LLM calls made by all agent types must be traced and exported to Langfuse via OpenTelemetry. Traces must include: model used, input token count, output token count, estimated cost, latency, agent type, objective ID, and MTP version. Traces must be exportable to Langfuse Cloud without self-hosting.

**Acceptance:**

- All four agent types produce traces visible in Langfuse on a test run
- Token counts and estimated costs are populated on each trace
- Agent type and objective ID are present as trace metadata
- Langfuse Cloud (Core tier) receives traces without self-hosted infrastructure

#### REQ-OBS-02: Infrastructure Metrics

**Description:**

The platform must export custom Prometheus metrics for agent-level signals: `signal_emission_rate` per agent instance, `checkpoint_write_rate` per objective, `verification_verdict_distribution` (confirmed/contradicted/inconclusive), `objective_completion_rate`, `escalation_rate`. Metrics must be visible in Fly.io's native Grafana.

**Acceptance:**

- All five custom metric types are exported and visible in Grafana
- Metrics update in real-time during agent execution
- An alert can be configured in Grafana based on a custom metric threshold

### 5.2 Reliability and Recovery

#### REQ-REL-01: Agent Failure Recovery

**Description:**

Objective agent failure must not result in objective progress loss. On detection of agent failure, the orchestration agent must: read the most recent cognitive checkpoint from the objective registry, provision a replacement objective agent seeded with that checkpoint, and have the replacement read event log entries since the checkpoint timestamp. Recovery must not require human intervention below the escalation threshold.

**Acceptance:**

- Simulated objective agent failure results in automatic replacement provisioning
- Replacement agent resumes from the last checkpoint without re-executing concluded research
- Recovery time from failure detection to resumed execution is under 2 minutes
- Recovery event is logged to the event log as a state transition

### 5.3 Security

#### REQ-SEC-01: Secret Management

**Description:**

API keys, database credentials, and configuration secrets must not be stored in the repository. All secrets must be managed via Fly.io secrets or equivalent secret management, injected as environment variables at runtime. The repository must contain no credentials, even in example or template files.

**Acceptance:**

- Repository contains no API keys, tokens, or credentials
- CI pipeline passes secret scanning check with no findings
- Platform starts successfully when all required secrets are present as environment variables
- A documented list of required secrets exists in README or deployment guide

#### REQ-SEC-02: Prompt Injection Defence

**Description:**

The platform must defend against prompt injection via the guardrail ensemble input classifier (WildGuard). All subscriber-supplied data, external content, and MCP-read content that is included in agent prompts must pass through the input classifier before inclusion. A known prompt injection payload in a MCP read result must be blocked before reaching the agent context.

**Acceptance:**

- WildGuard input classifier runs on all externally-sourced content before prompt inclusion
- A test prompt injection payload in a MCP response is blocked and logged
- Block events for prompt injection attempts are written to the event log

### 5.4 Configuration Portability

#### REQ-CFG-01: Project Isolation

**Description:**

The platform must contain no hardcoded references to any specific project, organisation, or domain. All project-specific behaviour must be driven by the external configuration loaded at runtime. The same platform binary must be demonstrably runnable against two different project configurations producing different agent behaviour.

**Acceptance:**

- Platform starts successfully against a minimal reference configuration
- Platform starts successfully against a second distinct configuration
- No project-specific strings exist in the platform source code
- Changing only the configuration path changes agent standing mandates and MTP constraints

---

## 6. CI/CD Pipeline Requirements

The following checks must all pass as required status checks before any pull request can be merged to main. The pipeline runs on GitHub Actions and requires no Fly.io involvement for the pre-merge gate.

| Check | Gate | Description and policy |
|-------|------|----------------------|
| `lint` | Pre-merge required | Ruff (Python) or ESLint (TypeScript). Zero warnings policy on new code. |
| `type-check` | Pre-merge required | mypy (Python) strict mode or `tsc --noEmit`. All agent implementations fully typed. |
| `unit-tests` | Pre-merge required | Pytest or Jest. Coverage threshold: 80% on `shared/` and `agents/` directories. |
| `schema-validation` | Pre-merge required | All schema definitions in `schema/` validate against their meta-schema. Migration immutability check — no existing migration file is modified. |
| `acap-validation` | Pre-merge required | All four agent type ACAPs in the reference configuration load and validate without error. Scope boundary checks pass. |
| `event-schema-tests` | Pre-merge required | Each agent type emits only events conforming to the canonical schemas in `shared/event_schemas/`. Schema violations are detected and fail the check. |
| `prompt-regression` | Pre-merge required | Each agent type runs against a fixture set of inputs. Output structure (schema validity, tool call patterns, constraint adherence) matches expected. Runs against DeepSeek V4 Flash to keep cost low. |
| `integration-tests` | Pre-merge required | ArcadeDB and Postgres run as Docker services in the GitHub Actions runner. Full coordination loop executes against them. Promotion logic verified end-to-end. |
| `secret-scan` | Pre-merge required | TruffleHog or equivalent. Zero credentials findings required. |
| `deploy` | Post-merge to main only | `fly deploy` for each modified agent service. Runs only after all pre-merge checks pass. |

---

## 7. Deferred to Future Phases

The following are explicitly deferred from v1. They are documented here to inform architectural decisions in v1 that should not foreclose these options.

| Feature | Rationale for deferral |
|---------|----------------------|
| **Conversational agent** | A human-facing conversational agent with session memory (AgentCore or equivalent). Reads from ArcadeDB knowledge graph and objective registry to answer questions about organisational state. Session memory via AgentCore Memory or similar, complementary to ArcadeDB. |
| **Multi-organisation governance** | Organisation-level MTP that constrains project MTPs. Cross-organisation A2A protocols. Ecosystem Trust protocols from ExO 3.0 SHAPE. |
| **NeMo Guardrails multi-turn** | Dialog-rail architecture detecting prompt injection across multiple agent turns. Monitor NVIDIA release cadence for production readiness signal. |
| **ArcadeDB HA cluster** | Three-node Raft cluster for production availability. Snapshot-and-restore bootstrap from single-node. Deferred until single-node deployment proves value. |
| **MTP evolution governance** | Full governance workflow for MTP revision: trigger conditions, evidence/decision separation, red team process, staged activation, version rollback. v1 MTP is treated as immutable. |
| **Objective agent code execution** | Objective agents that write and execute code against the target project, not just read and analyse. Requires sandbox environment and additional ACAP constraints. |
| **Self-hosted guardrail GPU** | Running WildGuard and Granite Guardian on self-hosted Fly.io GPU machines. v1 may use managed API endpoints for guardrail models if available, or a reduced guardrail configuration. |
| **Knowledge graph domain extensions** | Per-project custom node types beyond the base set. Project-specific relationship types. v1 supports the five base node types only. |

---

## 8. Open Questions

The following decisions are unresolved at requirements stage and must be resolved before or during implementation.

| ID | Question and options |
|----|---------------------|
| **OQ-01: Guardrail hosting for v1** | WildGuard and Granite Guardian require GPU for production throughput. v1 options: (a) managed API endpoints if available, (b) single Fly.io GPU machine shared across agent types, (c) reduced to ShieldGemma + Presidio only for v1 with full ensemble in v2. Decision needed before infra setup. |
| **OQ-02: LangGraph checkpoint store** | PostgreSQL via `langgraph-checkpoint-postgres`. Options: (a) Neon serverless Postgres (zero ops, pay-per-query), (b) Fly.io Postgres app (self-managed, cheaper at volume), (c) Aurora Serverless v2 on AWS (most mature, most expensive). Decision affects infra stack choice. |
| **OQ-03: Exploratory agent scheduling** | v1 uses scheduled polling (EventBridge equivalent). Fly.io scheduled Machine vs GitHub Actions scheduled workflow vs application-level scheduler within the orchestration agent. Trade-offs: Fly scheduled Machines have per-second billing; app-level scheduler requires the orchestration agent to be always-on. |
| **OQ-04: Reference project for v1** | The platform needs a reference project configuration to develop and test against. Scope of initial standing mandates and MCP connections to be agreed before mandate implementation begins. |
| **OQ-05: Langfuse tier** | Hobby tier (50K units/month, free) sufficient for development. Core tier ($29/month) for production. Decision: when to upgrade, and whether to start on Core to avoid data loss on upgrade. |

---

**Sources:** AI-Native Organization Blueprint (project document); The Event Log and Agent Types (project document); The Role and Evolution of MTP (project document); Guardrail Options (project document); ArcadeDB documentation (docs.arcadedb.com); OpenRouter documentation (openrouter.ai/docs); Fly.io documentation (fly.io/docs); Langfuse documentation (langfuse.com/docs).
