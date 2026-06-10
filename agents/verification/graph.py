"""Verification agent LangGraph composition.

Builds and compiles the verification agent StateGraph.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from langgraph.graph import END, StateGraph

from .nodes import emit_finding, investigate, poll_for_observations
from .state import VerificationState

if TYPE_CHECKING:
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.base import BaseCheckpointSaver

    from shared.arcadedb.client import ArcadeDBClient

logger = logging.getLogger(__name__)


def build_verification_graph(
    model: ChatOpenRouter,
    db_client: ArcadeDBClient,
    tools: list[Any],
    signal_threshold: float,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:  # noqa: ANN401
    """Build and compile the verification agent LangGraph.

    Graph flow:
        poll_for_observations → enforce_independence → investigate → emit_finding → poll...
        (conditional: if no signal found → END)
    """
    graph = StateGraph(VerificationState)

    graph.add_node(
        "poll_for_observations",
        _with_deps(poll_for_observations, db_client=db_client, signal_threshold=signal_threshold),
    )
    graph.add_node(
        "investigate",
        _with_deps(investigate, model=model, tools=tools),
    )
    graph.add_node(
        "emit_finding",
        _with_deps(emit_finding, db_client=db_client),
    )

    graph.set_entry_point("poll_for_observations")
    graph.add_conditional_edges(
        "poll_for_observations",
        _route_after_poll,
        {
            "investigate": "investigate",
            "end": END,
        },
    )
    graph.add_edge("investigate", "emit_finding")
    graph.add_edge("emit_finding", "poll_for_observations")

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def _route_after_poll(state: VerificationState) -> str:
    if state.get("completed"):
        return "end"
    return "investigate"


def _with_deps(
    fn: Callable[..., Any],
    **deps: object,
) -> Callable[..., Any]:
    """Wrap a node function with dependency injection."""

    async def wrapped(state: VerificationState, config: object = None) -> dict[str, Any]:  # noqa: ARG001
        return cast(dict[str, Any], await fn(state, **deps))

    wrapped.__name__ = fn.__name__
    return wrapped
