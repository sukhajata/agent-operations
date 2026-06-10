"""Research/plan agent LangGraph node functions.

Nodes: poll_for_findings, create_commitment, traverse_graph,
read_artifacts, read_event_delta, form_understanding,
write_checkpoint, produce_plan, mark_pending_approval.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from schema.identity.models import (
    CognitiveCheckpoint,
    CommitmentRecord,
    HypothesisRecord,
)
from schema.timeseries.event_log import AgentFinding

from .state import ResearchPlanState

if TYPE_CHECKING:
    from langchain_openrouter import ChatOpenRouter

    from shared.arcadedb.client import ArcadeDBClient
    from shared.mcp.manager import MCPConnectionManager

logger = logging.getLogger(__name__)

MAX_RESEARCH_ITERATIONS = 3

SYNTHESIS_PROMPT = """You are a research agent synthesising findings from multiple sources.

Domain: {domain}
Claim under investigation: {claim}
Verified finding reasoning: {finding_reasoning}

Knowledge graph context:
{graph_context}

Recent event log activity in this domain:
{event_delta}

Your task: form hypotheses about what is happening and produce a current best
understanding. Return a JSON object:

{{
    "hypotheses": [
        {{"hypothesis": "...", "conclusion": "pending", "evidence": "..."}}
    ],
    "current_understanding": "synthesis of what you now understand"
}}"""

PLAN_PROMPT = """You are a planning agent producing a concrete implementation plan.

Current understanding:
{understanding}

Domain: {domain}

Produce a step-by-step implementation plan as a single string. Each step should
be concrete and actionable. Number the steps. Include verification steps.
Be specific about what files to create/modify and what changes to make.
"""


async def poll_for_findings(
    state: ResearchPlanState,
    db_client: ArcadeDBClient,
) -> dict[str, Any]:
    """Poll for confirmed AgentFinding events with no existing CommitmentRecord."""
    from shared.arcadedb.timeseries import poll_events

    cursor: datetime = state.get("last_cursor") or datetime(2026, 1, 1, tzinfo=UTC)
    events = await poll_events(
        db_client,
        event_type="AgentFinding",
        since_ts=cursor,
        limit=50,
    )

    for event in events:
        verdict = event.get("verdict", "")
        if verdict != "confirmed":
            continue

        # Check if commitment already exists for this focus
        focus_id = event.get("focus_id")
        if focus_id:
            from shared.arcadedb.identity import get_commitment
            existing = await get_commitment(
                db_client,
                commitment_id=f"com-{focus_id}",
            )
            if existing is not None:
                continue

        ts = event.get("ts")
        if isinstance(ts, str):
            event["ts"] = datetime.fromisoformat(ts)

        originating_ts = event.get("originating_signal_ts")
        if isinstance(originating_ts, str):
            event["originating_signal_ts"] = datetime.fromisoformat(originating_ts)

        finding = AgentFinding(**event)
        return {
            "finding": finding,
            "last_cursor": finding.ts,
            "completed": False,
            "commitment": None,
            "graph_context": [],
            "artifact_context": [],
            "event_delta": [],
            "hypotheses": [],
            "current_understanding": None,
            "plan": None,
            "iteration": 0,
        }
    latest_ts: datetime = cursor
    for e in events:
        ts_val = e.get("ts")
        if isinstance(ts_val, datetime) and ts_val > latest_ts:
            latest_ts = ts_val
        elif isinstance(ts_val, str):
            parsed = datetime.fromisoformat(ts_val)
            if parsed > latest_ts:
                latest_ts = parsed
    return {"last_cursor": latest_ts, "completed": True}


async def create_commitment(
    state: ResearchPlanState,
    db_client: ArcadeDBClient,
) -> dict[str, Any]:
    """Create a CommitmentRecord for the confirmed finding."""
    from shared.arcadedb.identity import create_commitment

    finding = state.get("finding")
    if finding is None:
        return {"completed": True}

    if not finding.focus_id:
        logger.error("Confirmed AgentFinding missing focus_id; cannot create CommitmentRecord")
        return {"completed": True}

    commitment_id = f"com-{finding.focus_id}"
        commitment_id=commitment_id,
        status="active",
        created_at=datetime.now(UTC),
        domain=finding.domain,
        priority_signal=finding.confidence,
        assigned_agent_id=state["agent_id"],
    )
    await create_commitment(db_client, commitment)
    return {"commitment": commitment}


async def traverse_graph(
    state: ResearchPlanState,
    db_client: ArcadeDBClient,
) -> dict[str, Any]:
    """Query the knowledge graph for context in the finding's domain."""
    finding = state.get("finding")
    if finding is None:
        return {}

    records = await db_client.execute_query(
        "SELECT FROM ProductStructure WHERE domain = :domain LIMIT 20",
        {"domain": finding.domain},
    )
    if not records:
        records = await db_client.execute_query(
            "SELECT FROM InvestigationFinding WHERE domain = :domain LIMIT 20",
            {"domain": finding.domain},
        )
    return {"graph_context": list(records)}


async def read_artifacts(
    state: ResearchPlanState,
    mcp: MCPConnectionManager,
) -> dict[str, Any]:
    """Read structural artifacts via MCP for additional context."""
    graph = state.get("graph_context", [])
    if not graph:
        return {"artifact_context": ["(no artifacts available)"]}

    permitted = mcp.list_permitted_connections()
    if not permitted:
        return {"artifact_context": ["(no MCP connections permitted)"]}

    artifacts: list[str] = []
    finding = state.get("finding")
    focus: str = finding.focus_id if finding and finding.focus_id else "unknown"
    for server_url in permitted[:2]:
        try:
            result = await mcp.read(
                server_url=server_url,
                resource_path="/docs/architecture",
                agent_id=state["agent_id"],
                focus_id=focus,
                mtp_version=state["mtp_version"],
            )
            artifacts.append(result[:2000])
        except Exception as e:
            artifacts.append(f"(MCP read failed: {e})")
    return {"artifact_context": artifacts or ["(no artifacts read)"]}


async def read_event_delta(
    state: ResearchPlanState,
    db_client: ArcadeDBClient,
) -> dict[str, Any]:
    """Read recent event log activity in the finding's domain."""
    from shared.arcadedb.timeseries import poll_events

    finding = state.get("finding")
    if finding is None:
        return {}

    since = finding.originating_signal_ts
    events = await poll_events(
        db_client,
        event_type="AgentSignal",
        since_ts=since,
        limit=30,
    )
    return {"event_delta": list(events)}


async def form_understanding(
    state: ResearchPlanState,
    model: ChatOpenRouter,
) -> dict[str, Any]:
    """Synthesise research context into hypotheses and understanding."""
    import json

    finding = state.get("finding")
    if finding is None:
        return {"completed": True}

    graph_str = str(state.get("graph_context", []))[:4000]
    delta_str = str(state.get("event_delta", []))[:4000]

    prompt = SYNTHESIS_PROMPT.format(
        domain=finding.domain,
        claim=finding.claim,
        finding_reasoning=finding.reasoning[:1000],
        graph_context=graph_str,
        event_delta=delta_str,
    )

    response = await model.ainvoke(prompt)
    content = str(response.content) if hasattr(response, "content") else ""

    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = {
            "hypotheses": [],
            "current_understanding": content[:2000] if content else "synthesis failed",
        }

    hypotheses = [
        HypothesisRecord(
            hypothesis=h.get("hypothesis", ""),
            conclusion=h.get("conclusion", "pending"),
            evidence=h.get("evidence", ""),
        )
        for h in result.get("hypotheses", [])
    ]

    return {
        "hypotheses": hypotheses,
        "current_understanding": result.get("current_understanding", ""),
    }


async def write_checkpoint(
    state: ResearchPlanState,
    db_client: ArcadeDBClient,
) -> dict[str, Any]:
    """Write a CognitiveCheckpoint to the commitment.

    Must execute even if a preceding node raised. Uses try/except to
    ensure the graph can continue.
    """
    commitment = state.get("commitment")
    if commitment is None:
        return {}

    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", MAX_RESEARCH_ITERATIONS)
    next_action = "produce plan" if iteration >= max_iter else "continue research"

    checkpoint = CognitiveCheckpoint(
        hypotheses_investigated=state.get("hypotheses", []),
        current_best_understanding=state.get("current_understanding") or "pending",
        recommended_next_action=next_action,
        plan=state.get("plan"),
        checkpoint_at=datetime.now(UTC),
    )

    try:
        from shared.arcadedb.identity import write_checkpoint as _write
        await _write(db_client, commitment.commitment_id, checkpoint)
    except Exception as e:
        logger.error("Failed to write checkpoint: %s", e)

    return {"iteration": iteration + 1}


async def produce_plan(
    state: ResearchPlanState,
    model: ChatOpenRouter,
) -> dict[str, Any]:
    """Produce a concrete implementation plan."""
    finding = state.get("finding")
    understanding = state.get("current_understanding") or "no understanding formed"

    prompt = PLAN_PROMPT.format(
        understanding=understanding,
        domain=finding.domain if finding else "unknown",
    )

    response = await model.ainvoke(prompt)
    plan = str(response.content) if hasattr(response, "content") else ""

    return {"plan": plan}


async def mark_pending_approval(
    state: ResearchPlanState,
    db_client: ArcadeDBClient,
) -> dict[str, Any]:
    """Mark the commitment as pending human approval."""
    commitment = state.get("commitment")
    if commitment is None:
        return {"completed": True}

    from shared.arcadedb.identity import update_commitment
    await update_commitment(db_client, commitment.commitment_id, {"status": "pending_approval"})
    logger.info("Commitment %s marked pending_approval", commitment.commitment_id)
    return {"completed": True}
