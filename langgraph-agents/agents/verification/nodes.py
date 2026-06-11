"""Verification agent LangGraph node functions.

Nodes: poll_for_observations, investigate, emit_finding.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from shared.openrouter.models import ModelFamily

from .state import VerificationState

if TYPE_CHECKING:
    from langchain_openrouter import ChatOpenRouter

    from shared.arcadedb.client import ArcadeDBClient

logger = logging.getLogger(__name__)

INVESTIGATE_PROMPT = """You are a verification agent. Your task is to determine whether
the following claim is FALSE. Assume it is wrong and attempt to disprove it.
Only conclude it is 'confirmed' if you cannot find evidence against it.

Claim: {claim}
Domain: {domain}
Reasoning given by the originating agent: {reasoning}

Use `search_graph` to find contrary evidence in the knowledge graph.
Use `search_signals` to find contradictory recent signals.

Respond with a JSON object:
{{
    "verdict": "confirmed" | "contradicted" | "inconclusive",
    "verdict_confidence": 0.0 to 1.0,
    "verdict_rationale": "explanation of your reasoning and evidence"
}}"""


async def poll_for_observations(
    state: VerificationState,
    db_client: ArcadeDBClient,
    signal_threshold: float,
) -> dict[str, Any]:
    """Poll the event log for unverified AgentSignal observations.

    Uses cursor-based polling to find observations with confidence above
    the threshold that haven't been verified yet.
    """
    from shared.arcadedb.timeseries import poll_events

    cursor: datetime = state.get("last_cursor") or datetime(2026, 1, 1, tzinfo=UTC)
    events = await poll_events(
        db_client,
        event_type="AgentSignal",
        since_ts=cursor,
        limit=50,
    )

    for event in events:
        confidence = event.get("confidence", 0)
        if isinstance(confidence, (int, float)) and confidence >= signal_threshold:
            from schema.timeseries.event_log import AgentSignal
            ts = event.get("ts")
            if isinstance(ts, str):
                event["ts"] = datetime.fromisoformat(ts)
            signal = AgentSignal(**event)
            return {
                "signal": signal,
                "focus_id": signal.focus_id,
                "originating_model_family": _model_family_from_agent(signal.agent_id),
                "last_cursor": signal.ts,
                "completed": False,
                "verdict": None,
                "verdict_confidence": None,
                "verdict_rationale": None,
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
    return {
        "last_cursor": latest_ts,
        "completed": True,
        "signal": None,
        "focus_id": None,
        "verdict": None,
        "verdict_confidence": None,
        "verdict_rationale": None,
    }


async def investigate(
    state: VerificationState,
    model: ChatOpenRouter,
    tools: list[Any],
) -> dict[str, Any]:
    """Investigate the signal adversarially using the verification model."""
    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph.prebuilt import ToolNode

    signal = state["signal"]
    if signal is None:
        return {"completed": True}

    system = INVESTIGATE_PROMPT.format(
        claim=signal.claim,
        domain=signal.domain,
        reasoning=signal.reasoning,
    )

    model_with_tools = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    messages: list[Any] = [
        SystemMessage(content=system),
        HumanMessage(content=f"Investigate this claim: {signal.claim}"),
    ]

    max_iterations = 5
    for i in range(max_iterations):
        logger.debug("Investigation iteration %d/%d", i + 1, max_iterations)
        response = await model_with_tools.ainvoke(messages)
        messages.append(response)

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_result = await tool_node.ainvoke({"messages": messages})
            messages = tool_result["messages"]
        else:
            break

    content = ""
    last_msg = messages[-1]
    if hasattr(last_msg, "content"):
        content = str(last_msg.content)

    import json
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        result = {}

    verdict_raw = result.get("verdict")
    verdict = (
        verdict_raw
        if verdict_raw in {"confirmed", "contradicted", "inconclusive"}
        else "inconclusive"
    )

    confidence_raw = result.get("verdict_confidence", 0.5)
    confidence = confidence_raw if isinstance(confidence_raw, (int, float)) else 0.5
    confidence = min(1.0, max(0.0, float(confidence)))

    rationale_raw = result.get("verdict_rationale")
    rationale = rationale_raw if isinstance(rationale_raw, str) else content

    return {
        "verdict": verdict,
        "verdict_confidence": confidence,
        "verdict_rationale": rationale,
    }


async def emit_finding(
    state: VerificationState,
    emit_fn: Any,  # noqa: ANN401
) -> dict[str, Any]:
    """Emit an AgentFinding with the verification verdict.

    emit_fn is an injectable async function that wraps emit_validated.
    Passed by the graph builder; mockable in tests.
    """
    signal = state["signal"]
    if signal is None:
        return {"completed": True}

    await emit_fn(
        claim=signal.claim,
        domain=signal.domain,
        confidence=state["verdict_confidence"] or 0.5,
        reasoning=state["verdict_rationale"] or "",
        sources=signal.sources,
        focus_id=state["focus_id"],
        verdict=state["verdict"] or "inconclusive",
        originating_signal_ts=signal.ts.isoformat(),
    )
    logger.info(
        "Verification complete: %s — %s (confidence: %.2f)",
        signal.claim[:80], state["verdict"], state["verdict_confidence"] or 0.0,
    )
    return {"completed": True}


def _model_family_from_agent(agent_id: str) -> ModelFamily:
    """Determine the model family of the originating agent.

    Exploratory agents use DeepSeek; verification agents use Qwen.
    """
    if agent_id.startswith("verification-"):
        return ModelFamily.QWEN
    return ModelFamily.DEEPSEEK
