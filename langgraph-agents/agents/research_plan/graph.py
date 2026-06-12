"""Research/plan agent LangGraph composition."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from langgraph.graph import END, StateGraph

from .nodes import (
    create_commitment,
    form_understanding,
    mark_pending_approval,
    poll_for_findings,
    produce_plan,
    read_artifacts,
    read_event_delta,
    traverse_graph,
    write_checkpoint,
)
from .state import ResearchPlanState

if TYPE_CHECKING:
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.base import BaseCheckpointSaver

    from shared.arcadedb.client import ArcadeDBClient
    from shared.mcp.manager import MCPConnectionManager

logger = logging.getLogger(__name__)


def build_research_plan_graph(
    model: ChatOpenRouter,
    db_client: ArcadeDBClient,
    mcp: MCPConnectionManager,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:  # noqa: ANN401
    """Build the research/plan agent StateGraph.

    Flow:
      poll_for_findings → (finding?)
        → create_commitment → traverse_graph → read_artifacts →
          read_event_delta → form_understanding → write_checkpoint →
          (sufficient understanding?)
            → produce_plan → mark_pending_approval → poll_for_findings
            → traverse_graph (research loop)
        → END (no finding)
    """
    graph = StateGraph(ResearchPlanState)

    graph.add_node("poll_for_findings", _with_deps(poll_for_findings, db_client=db_client))
    graph.add_node("create_commitment", _with_deps(create_commitment, db_client=db_client))
    graph.add_node("traverse_graph", _with_deps(traverse_graph, db_client=db_client))
    graph.add_node("read_artifacts", _with_deps(read_artifacts, mcp=mcp))
    graph.add_node("read_event_delta", _with_deps(read_event_delta, db_client=db_client))
    graph.add_node("form_understanding", _with_deps(form_understanding, model=model))
    graph.add_node("write_checkpoint", _with_deps(write_checkpoint, db_client=db_client))
    graph.add_node("produce_plan", _with_deps(produce_plan, model=model))
    graph.add_node("mark_pending_approval", _with_deps(mark_pending_approval, db_client=db_client))

    graph.set_entry_point("poll_for_findings")
    graph.add_conditional_edges(
        "poll_for_findings",
        _route_after_poll,
        {"create_commitment": "create_commitment", "end": END},
    )
    graph.add_edge("create_commitment", "traverse_graph")
    graph.add_edge("traverse_graph", "read_artifacts")
    graph.add_edge("read_artifacts", "read_event_delta")
    graph.add_edge("read_event_delta", "form_understanding")
    graph.add_edge("form_understanding", "write_checkpoint")
    graph.add_conditional_edges(
        "write_checkpoint",
        _route_after_checkpoint,
        {"produce_plan": "produce_plan", "traverse_graph": "traverse_graph"},
    )
    graph.add_edge("produce_plan", "mark_pending_approval")
    graph.add_edge("mark_pending_approval", "poll_for_findings")

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def _route_after_poll(state: ResearchPlanState) -> str:
    if state.get("completed"):
        return "end"
    if state.get("finding") is not None:
        return "create_commitment"
    return "end"


def _route_after_checkpoint(state: ResearchPlanState) -> str:
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)
    understanding = state.get("current_understanding")
    if understanding and (iteration >= max_iter):
        return "produce_plan"
    return "traverse_graph"


def _with_deps(
    fn: Callable[..., Any],
    **deps: object,
) -> Callable[..., Any]:
    """Wrap a node function with dependency injection."""

    async def wrapped(state: ResearchPlanState, config: object = None) -> dict[str, Any]:  # noqa: ARG001
        return cast(dict[str, Any], await fn(state, **deps))

    wrapped.__name__ = fn.__name__
    return wrapped
