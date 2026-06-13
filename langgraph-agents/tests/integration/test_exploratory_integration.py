"""Integration tests for exploratory agent end-to-end.

Requires ARCADEDB_URL pointing to a real ArcadeDB instance and
OPENROUTER_API_KEY for live LLM calls.
"""
# ruff: noqa: ANN001, ANN201, ANN202
from __future__ import annotations

import asyncio

import pytest


@pytest.mark.integration
def test_exploratory_graph_invokes_with_real_arcadedb(arcadedb_clean, openrouter_model) -> None:
    """Run the exploratory graph against a real ArcadeDB instance."""
    from agents.exploratory.graph import build_exploratory_graph
    from agents.exploratory.state import ExploratoryState
    from shared.arcadedb.client import ArcadeDBClient
    from shared.config.loader import MandateDefinition

    client: ArcadeDBClient = arcadedb_clean
    model = openrouter_model

    from tools import create_exploratory_tools

    tools = create_exploratory_tools(client, "integration-test-explorer", "1.0")

    graph = build_exploratory_graph(model, client, tools)
    assert graph is not None

    mandate = MandateDefinition(
        name="integration-test-exploratory",
        domain="competitive_intelligence",
        agent_type="free",
        polling_interval_minutes=60,
        signal_threshold=0.6,
    )

    state: ExploratoryState = {
        "mandate": mandate,
        "mtp_version": "1.0",
        "agent_id": "integration-test-explorer",
        "last_cursor": None,
        "messages": [],
        "signals_emitted": 0,
        "run_at": None,
        "max_iterations": 3,
        "completed": False,
        "focus_id": None,
    }

    async def _run() -> None:
        result = await graph.ainvoke(state)
        assert result.get("completed") is True
        assert isinstance(result.get("signals_emitted"), int)

    asyncio.run(_run())


@pytest.mark.integration
def test_exploratory_tool_search_graph(arcadedb_client) -> None:
    """Verify search_graph tool queries a real ArcadeDB instance."""
    from shared.arcadedb.client import ArcadeDBClient
    from tools.search_graph import create_search_graph_tool

    client: ArcadeDBClient = arcadedb_client
    tool = create_search_graph_tool(client)
    assert tool.name == "search_graph"

    async def _run() -> None:
        result = await tool.ainvoke({"pattern": "test"})
        assert isinstance(result, str)

    asyncio.run(_run())


@pytest.mark.integration
def test_exploratory_tool_emit_signal(arcadedb_clean) -> None:
    """Verify emit_signal tool writes to a real ArcadeDB timeseries."""
    from shared.arcadedb.client import ArcadeDBClient
    from tools.emit_signal import create_emit_signal_tool

    client: ArcadeDBClient = arcadedb_clean
    tool = create_emit_signal_tool(
        client, "integration-test-emitter", "1.0", None,
    )
    assert tool.name == "emit_signal"

    async def _run() -> None:
        result = await tool.ainvoke({
            "claim": "Integration test signal claim",
            "domain": "integration_testing",
            "confidence": 0.75,
            "reasoning": "Testing emit signal tool end-to-end",
            "sources": ["integration-test"],
        })
        assert "emitted" in result.lower()

        # Verify it was persisted
        from shared.arcadedb.timeseries import poll_events
        events = await poll_events(client, agent_id="integration-test-emitter", limit=5)
        assert len(events) > 0
        assert any("integration test signal" in str(e.get("claim", "")).lower() for e in events)

    asyncio.run(_run())


@pytest.mark.integration
def test_exploratory_tool_search_signals(arcadedb_clean) -> None:
    """Verify search_signals tool queries the real ArcadeDB timeseries."""
    from shared.arcadedb.client import ArcadeDBClient
    from tools.search_signals import create_search_signals_tool

    client: ArcadeDBClient = arcadedb_clean
    tool = create_search_signals_tool(client)
    assert tool.name == "search_signals"

    async def _run() -> None:
        result = await tool.ainvoke({"domain": "integration_testing", "query": "signal"})
        assert isinstance(result, str)
        assert "signal" in result.lower() or "no signals" in result.lower()

    asyncio.run(_run())
