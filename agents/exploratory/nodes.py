"""Exploratory agent LangGraph node functions.

Nodes: load_context, observe (ReAct loop with ChatOpenRouter), update_cursor.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from langgraph.prebuilt import ToolNode

from .state import ExploratoryState

if TYPE_CHECKING:
    from langchain_openrouter import ChatOpenRouter

    from shared.arcadedb.client import ArcadeDBClient

logger = logging.getLogger(__name__)

OBSERVE_SYSTEM_PROMPT = """You are an exploratory agent investigating the {domain} domain.
Your mandate: {mandate_name}

Your task:
1. Explore the domain freely. Use `search_graph` to discover what is already
   known and identify gaps in the knowledge base.
2. Before reporting any finding, call `search_graph` to check if it already
   exists. If a finding matches an existing node, do not emit a signal.
3. Call `search_signals` to check for recent near-duplicate signals.
4. Only call `emit_signal` for claims that are genuinely novel with
   confidence >= {signal_threshold}. Provide your reasoning and list any
   sources that support the claim. Set `is_novel: true` for new findings.
5. When done, respond with "SUMMARY:" followed by what you discovered."""

OBSERVE_FOCUS_PROMPT = """You are an exploratory agent following a specific focus.
Focus: {focus_summary}
Domain: {domain}

Your task:
1. Investigate this focus. Use `search_graph` to understand what is already
   known about this area.
2. Before reporting any finding, call `search_graph` to check if it already
   exists. If a finding matches an existing node, do not emit a signal.
3. Call `search_signals` to check for recent near-duplicate signals.
4. Only call `emit_signal` for claims that are genuinely novel with
   confidence >= {signal_threshold}. Provide your reasoning and list any
   sources that support the claim. Set `is_novel: true` for new findings.
5. When done, respond with "SUMMARY:" followed by what you discovered."""

MAX_ITERATIONS = 10


async def load_context(
    state: ExploratoryState,
    db_client: ArcadeDBClient,
) -> dict[str, Any]:
    """Load MTP version and ACAP from the identity store."""
    from shared.arcadedb.identity import load_mtp

    mtp = await load_mtp(db_client)
    if mtp is not None:
        return {"mtp_version": mtp.version}
    return {}


async def observe(
    state: ExploratoryState,
    model: ChatOpenRouter,
    tools: list[Any],
) -> dict[str, Any]:
    """ReAct loop: investigate domain with tool calling.

    Uses ChatOpenRouter with bound tools and ToolNode for execution.
    The LLM decides when to query the graph, check signals, and emit.
    """
    mandate = state["mandate"]

    if mandate.agent_type == "focus":
        system = OBSERVE_FOCUS_PROMPT.format(
            domain=mandate.domain,
            focus_summary=mandate.name,
            signal_threshold=mandate.signal_threshold,
        )
    else:
        system = OBSERVE_SYSTEM_PROMPT.format(
            domain=mandate.domain,
            mandate_name=mandate.name,
            signal_threshold=mandate.signal_threshold,
        )

    model_with_tools = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    messages: list[Any] = list(state.get("messages", []))
    if not messages:
        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=system),
            HumanMessage(
                content=f"Begin investigating the {mandate.domain} domain."
            ),
        ]

    signals_emitted = state.get("signals_emitted", 0)
    iteration = 0

    while iteration < state.get("max_iterations", MAX_ITERATIONS):
        iteration += 1
        logger.debug("Observe iteration %d/%d", iteration, MAX_ITERATIONS)

        response = await model_with_tools.ainvoke(messages)
        messages.append(response)

        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tc_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                if tc_name == "emit_signal":
                    signals_emitted += 1

            tool_result = await tool_node.ainvoke({"messages": messages})
            messages = tool_result["messages"]
        else:
            content = str(response.content) if hasattr(response, "content") else ""
            if "SUMMARY:" in content:
                break
            if iteration >= 3:
                break

    serializable_messages = []
    for m in messages:
        if hasattr(m, "model_dump"):
            serializable_messages.append(m.model_dump())
        elif isinstance(m, dict):
            serializable_messages.append(m)
        else:
            serializable_messages.append({"role": "assistant", "content": str(m)})

    return {
        "messages": serializable_messages,
        "signals_emitted": signals_emitted,
        "completed": True,
    }


async def update_cursor(
    state: ExploratoryState,
) -> dict[str, Any]:
    """Update the last_cursor timestamp to now."""
    return {
        "last_cursor": datetime.now(UTC),
        "run_at": datetime.now(UTC),
    }
