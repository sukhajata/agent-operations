"""Shared agent tools.

Tools are created via factory functions that bind runtime dependencies
(ArcadeDB client, agent identity) to @tool-decorated functions.

Usage:
    from tools import create_exploratory_tools
    tools = create_exploratory_tools(db_client, agent_id, mtp_version)
"""

from __future__ import annotations

from typing import Any

from shared.arcadedb.client import ArcadeDBClient
from tools.emit_signal import create_emit_signal_tool
from tools.search_graph import create_search_graph_tool
from tools.search_signals import create_search_signals_tool


def create_exploratory_tools(
    db_client: ArcadeDBClient,
    agent_id: str,
    mtp_version: str,
    focus_id: str | None = None,
) -> list[Any]:
    """Create the tool set for an exploratory agent."""
    return [
        create_search_graph_tool(db_client),
        create_search_signals_tool(db_client),
        create_emit_signal_tool(db_client, agent_id, mtp_version, focus_id),
    ]
