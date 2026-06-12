"""Exploratory agent LangGraph composition.

Builds and compiles the exploratory agent StateGraph.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from langgraph.graph import END, StateGraph

from .nodes import load_context, observe, update_cursor
from .state import ExploratoryState

if TYPE_CHECKING:
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.base import BaseCheckpointSaver

    from shared.arcadedb.client import ArcadeDBClient

logger = logging.getLogger(__name__)


def build_exploratory_graph(
    model: ChatOpenRouter,
    db_client: ArcadeDBClient,
    tools: list[Any],
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> Any:  # noqa: ANN401
    """Build and compile the exploratory agent LangGraph.

    Graph flow: load_context → observe → update_cursor → END
    """
    graph = StateGraph(ExploratoryState)

    graph.add_node("load_context", _with_deps(load_context, db_client=db_client))
    graph.add_node(
        "observe",
        _with_deps(observe, model=model, tools=tools),
    )
    graph.add_node("update_cursor", update_cursor)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "observe")
    graph.add_edge("observe", "update_cursor")
    graph.add_edge("update_cursor", END)

    if checkpointer is not None:
        return graph.compile(checkpointer=checkpointer)
    return graph.compile()


def _with_deps(
    fn: Callable[..., Any],
    **deps: object,
) -> Callable[..., Any]:
    """Wrap a node function with dependency injection."""

    async def wrapped(state: ExploratoryState, config: object = None) -> dict[str, Any]:  # noqa: ARG001
        return cast(dict[str, Any], await fn(state, **deps))

    wrapped.__name__ = fn.__name__
    return wrapped
