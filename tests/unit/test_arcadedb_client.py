from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from schema.graph.node_types import DECAY_RATES, GraphNode
from schema.identity.models import (
    CognitiveCheckpoint,
    HypothesisRecord,
    ObjectiveRecord,
)
from schema.timeseries.event_log import AgentAction, AgentSignal
from shared.arcadedb.client import ArcadeDBClient, ArcadeDBConnectionError, ArcadeDBQueryError
from shared.arcadedb.graph import (
    apply_decay_all,
    flag_for_revalidation,
    get_node,
    reinforce_node,
    traverse_from,
    upsert_node,
)
from shared.arcadedb.identity import (
    create_objective,
    get_objective,
    load_acap,
    load_mtp,
    update_objective,
    write_checkpoint,
)
from shared.arcadedb.timeseries import emit_event, poll_events

SAMPLE_DATETIME = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
SAMPLE_DATETIME_STR = "2026-06-09T12:00:00+00:00"


# --- Helpers ---


def _make_async_response(
    status_code: int = 200, result: list[dict[str, Any]] | None = None
) -> AsyncMock:
    response = AsyncMock()
    response.is_success = status_code < 400
    response.status_code = status_code
    response.json = lambda: {"result": result or []}
    return response


class MockArcadeDBClient(ArcadeDBClient):
    """Testable ArcadeDBClient that records calls."""

    def __init__(self) -> None:
        super().__init__("http://localhost:2480", "testdb", "user", "pass")
        self.post_mock = AsyncMock()
        self.get_mock = AsyncMock()
        self._client.post = self.post_mock  # type: ignore[method-assign]
        self._client.get = self.get_mock  # type: ignore[method-assign]

    def set_response(
        self, status_code: int = 200, result: list[dict[str, Any]] | None = None
    ) -> None:
        self.post_mock.return_value = _make_async_response(status_code, result)
        self.get_mock.return_value = _make_async_response(status_code, result)

    def pop_post_call(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = cast(
            dict[str, Any], self.post_mock.call_args.kwargs
        )
        return kwargs["json"]  # type: ignore[no-any-return]


# --- ArcadeDBClient tests ---


def test_client_execute_query() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{"@rid": "#1:0", "name": "test"}])

    async def _run() -> None:
        r = await client.execute_query("SELECT FROM Test")
        assert len(r) == 1
        assert r[0]["name"] == "test"

    asyncio.run(_run())


def test_client_execute_query_with_params() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await client.execute_query(
            "SELECT FROM Test WHERE name = :name",
            {"name": "Alice"},
            limit=50,
        )
        body = client.pop_post_call()
        assert body["language"] == "sql"
        assert body["command"] == "SELECT FROM Test WHERE name = :name"
        assert body["params"] == {"name": "Alice"}
        assert body["limit"] == 50

    asyncio.run(_run())


def test_client_execute_command() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{"@rid": "#1:0"}])

    async def _run() -> None:
        r = await client.execute_command("CREATE VERTEX Test SET name = 'X'")
        assert len(r) == 1
        assert r[0]["@rid"] == "#1:0"

    asyncio.run(_run())


def test_client_execute_command_with_params() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await client.execute_command(
            "UPDATE Test SET name = :name WHERE id = :id",
            {"name": "Bob", "id": "x"},
        )
        body = client.pop_post_call()
        assert body["params"] == {"name": "Bob", "id": "x"}

    asyncio.run(_run())


def test_client_query_error() -> None:
    client = MockArcadeDBClient()
    client.set_response(status_code=400)

    async def _run() -> None:
        with pytest.raises(ArcadeDBQueryError):
            await client.execute_query("INVALID SQL")

    asyncio.run(_run())


def test_client_connection_error() -> None:
    async def _run() -> None:
        import httpx
        client = MockArcadeDBClient()
        client.post_mock.side_effect = httpx.ConnectError("refused")
        with pytest.raises(ArcadeDBConnectionError):
            await client.execute_query("SELECT 1")

    asyncio.run(_run())


def test_health_check_success() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        result = await client.health_check()
        assert result is True

    asyncio.run(_run())


def test_health_check_failure() -> None:
    async def _run() -> None:
        import httpx
        client = MockArcadeDBClient()
        client.get_mock.side_effect = httpx.ConnectError("refused")
        result = await client.health_check()
        assert result is False

    asyncio.run(_run())


# --- TimeSeries tests ---


def test_emit_event_signal() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    signal = AgentSignal(
        event_type="AgentSignal",
        ts=SAMPLE_DATETIME,
        agent_id="agent-1",
        mtp_version="1.0",
        claim="interesting finding",
        domain="test",
        confidence=0.8,
        reasoning="found via graph search",
        sources=["node-42"],
        focus_id="obj-001",
        novelty_flag=True,
    )

    async def _run() -> None:
        await emit_event(client, signal)
        body = client.pop_post_call()
        assert "INSERT INTO AgentSignal" in body["command"]
        assert body["params"]["agent_id"] == "agent-1"
        assert body["params"]["confidence"] == 0.8
        assert body["params"]["focus_id"] == "obj-001"
        assert body["params"]["claim"] == "interesting finding"

    asyncio.run(_run())


def test_emit_event_action() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    action = AgentAction(
        event_type="AgentAction",
        ts=SAMPLE_DATETIME,
        agent_id="agent-2",
        objective_id="obj-1",
        mtp_version="1.0",
        payload={"tool": "web_search", "query": "test"},
    )

    async def _run() -> None:
        await emit_event(client, action)
        body = client.pop_post_call()
        assert "INSERT INTO AgentAction" in body["command"]

    asyncio.run(_run())


def test_poll_events_partition_pruning() -> None:
    """Verify poll_events uses ts > :since_ts for partition pruning."""
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await poll_events(
            client,
            event_type="AgentFinding",
            since_ts=SAMPLE_DATETIME,
            agent_id="agent-1",
            objective_id="obj-1",
            limit=50,
        )
        body = client.pop_post_call()
        command = body["command"]
        params = body["params"]

        assert "ts > :since_ts" in command
        assert "agent_id = :agent_id" in command
        assert "objective_id = :objective_id" in command
        assert "ORDER BY ts ASC" in command
        assert params["since_ts"] == SAMPLE_DATETIME_STR
        assert params["agent_id"] == "agent-1"
        assert params["objective_id"] == "obj-1"
        assert body["limit"] == 50

    asyncio.run(_run())


def test_poll_events_with_focus_id() -> None:
    """Verify poll_events supports focus_id filtering for AgentSignal."""
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await poll_events(
            client,
            event_type="AgentSignal",
            since_ts=SAMPLE_DATETIME,
            agent_id="agent-1",
            focus_id="obj-001",
            limit=50,
        )
        body = client.pop_post_call()
        command = body["command"]
        params = body["params"]

        assert "focus_id = :focus_id" in command
        assert params["focus_id"] == "obj-001"

    asyncio.run(_run())


def test_poll_events_no_optional_filters() -> None:
    """Verify poll_events works without optional agent_id/objective_id."""
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await poll_events(
            client,
            event_type="AgentFinding",
            since_ts=SAMPLE_DATETIME,
            limit=25,
        )
        body = client.pop_post_call()
        command = body["command"]
        params = body["params"]

        assert "ts > :since_ts" in command
        assert "since_ts" in params
        assert "agent_id" not in params
        assert "agent_id" not in command

    asyncio.run(_run())


# --- Graph tests ---


def _node_records(node: GraphNode) -> list[dict[str, Any]]:
    return [{
        "node_id": node.node_id,
        "node_type": node.node_type,
        "confidence": node.confidence,
        "initial_confidence": node.initial_confidence,
        "decay_rate": node.decay_rate,
        "last_reinforced": node.last_reinforced.isoformat(),
        "revalidation_required": node.revalidation_required,
    }]


def _graph_client(*graph_nodes: GraphNode) -> MockArcadeDBClient:
    records: list[dict[str, Any]] = []
    for node in graph_nodes:
        records.extend(_node_records(node))
    client = MockArcadeDBClient()
    client.set_response(result=records)
    return client


def test_upsert_node_create() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    node = GraphNode(
        node_id="ps-1",
        node_type="ProductStructure",
        confidence=0.9,
        initial_confidence=0.9,
        decay_rate=DECAY_RATES["ProductStructure"],
        last_reinforced=SAMPLE_DATETIME,
        revalidation_required=False,
    )

    async def _run() -> None:
        result = await upsert_node(client, node)
        assert result == "ps-1"
        body = client.pop_post_call()
        assert "CREATE VERTEX ProductStructure" in body["command"]

    asyncio.run(_run())


def test_upsert_node_update() -> None:
    existing = GraphNode(
        node_id="ps-1",
        node_type="ProductStructure",
        confidence=0.9,
        initial_confidence=0.9,
        decay_rate=DECAY_RATES["ProductStructure"],
        last_reinforced=SAMPLE_DATETIME,
        revalidation_required=False,
    )
    client = _graph_client(existing)

    updated = GraphNode(
        node_id="ps-1",
        node_type="ProductStructure",
        confidence=0.7,
        initial_confidence=0.9,
        decay_rate=DECAY_RATES["ProductStructure"],
        last_reinforced=SAMPLE_DATETIME,
        revalidation_required=True,
    )

    async def _run() -> None:
        result = await upsert_node(client, updated)
        assert result == "ps-1"
        body = client.pop_post_call()
        assert "UPDATE ProductStructure SET" in body["command"]
        assert body["params"]["confidence"] == 0.7

    asyncio.run(_run())


def test_reinforce_node_resets_last_reinforced() -> None:
    """Verify reinforce_node resets last_reinforced timestamp and clears flag."""
    node = GraphNode(
        node_id="ps-1",
        node_type="ProductStructure",
        confidence=0.3,
        initial_confidence=0.9,
        decay_rate=DECAY_RATES["ProductStructure"],
        last_reinforced=datetime(2026, 1, 1, tzinfo=UTC),
        revalidation_required=True,
    )
    client = _graph_client(node)

    async def _run() -> None:
        await reinforce_node(client, "ps-1")
        body = client.pop_post_call()
        params = body["params"]

        assert "UPDATE ProductStructure" in body["command"]
        assert params["node_id"] == "ps-1"
        assert params["confidence"] == 0.9
        assert "revalidation_required = false" in body["command"].lower()
        assert params["last_reinforced"] != "2026-01-01T00:00:00+00:00"
        assert "last_reinforced" in body["command"]

    asyncio.run(_run())


def test_reinforce_node_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        await reinforce_node(client, "nonexistent")

    asyncio.run(_run())


def test_flag_for_revalidation() -> None:
    node = GraphNode(
        node_id="ps-1",
        node_type="ProductStructure",
        confidence=0.5,
        initial_confidence=0.9,
        decay_rate=DECAY_RATES["ProductStructure"],
        last_reinforced=SAMPLE_DATETIME,
        revalidation_required=False,
    )
    client = _graph_client(node)

    async def _run() -> None:
        await flag_for_revalidation(client, "ps-1")
        body = client.pop_post_call()
        assert "revalidation_required = true" in body["command"]

    asyncio.run(_run())


def test_get_node_found() -> None:
    node = GraphNode(
        node_id="ps-1",
        node_type="ProductStructure",
        confidence=0.9,
        initial_confidence=0.9,
        decay_rate=DECAY_RATES["ProductStructure"],
        last_reinforced=SAMPLE_DATETIME,
        revalidation_required=False,
    )
    client = _graph_client(node)

    async def _run() -> None:
        result = await get_node(client, "ps-1")
        assert result is not None
        assert result.node_id == "ps-1"
        assert result.node_type == "ProductStructure"

    asyncio.run(_run())


def test_get_node_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        result = await get_node(client, "nonexistent")
        assert result is None

    asyncio.run(_run())


def test_traverse_from_returns_nodes() -> None:
    node_a = GraphNode(
        node_id="a", node_type="ProductStructure",
        confidence=0.9, initial_confidence=0.9,
        decay_rate=0.001, last_reinforced=SAMPLE_DATETIME,
        revalidation_required=False,
    )
    node_b = GraphNode(
        node_id="b", node_type="DecisionRecord",
        confidence=0.8, initial_confidence=0.8,
        decay_rate=0.0001, last_reinforced=SAMPLE_DATETIME,
        revalidation_required=False,
    )

    records: list[dict[str, Any]] = []
    records.extend(_node_records(node_a))
    records.extend(_node_records(node_b))
    client = MockArcadeDBClient()
    client.set_response(result=records)

    async def _run() -> None:
        result = await traverse_from(client, "a", max_depth=2)
        assert len(result) >= 1

    asyncio.run(_run())


def test_traverse_from_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        result = await traverse_from(client, "nonexistent")
        assert result == []

    asyncio.run(_run())


def test_apply_decay_all() -> None:
    old_date = datetime(2026, 1, 1, tzinfo=UTC)
    node = GraphNode(
        node_id="ps-1", node_type="ProductStructure",
        confidence=0.9, initial_confidence=0.9,
        decay_rate=0.001, last_reinforced=old_date,
        revalidation_required=False,
    )
    client = _graph_client(node)

    async def _run() -> None:
        count = await apply_decay_all(client)
        assert count >= 1

    asyncio.run(_run())


# --- Identity tests ---


def test_load_mtp() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "mtp_id": "mtp-v1", "version": "1.0",
        "purpose": "Improve quality",
        "constraints": ["Never expose data"],
        "intent_description": "We exist to improve software",
        "created_at": SAMPLE_DATETIME_STR,
        "created_by": "admin",
    }])

    async def _run() -> None:
        mtp = await load_mtp(client)
        assert mtp is not None
        assert mtp.mtp_id == "mtp-v1"
        assert mtp.version == "1.0"

    asyncio.run(_run())


def test_load_mtp_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        mtp = await load_mtp(client)
        assert mtp is None

    asyncio.run(_run())


def test_load_acap() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "acap_id": "acap-exploratory",
        "agent_type": "exploratory",
        "permitted_tools": ["web_search"],
        "permitted_mcp_connections": [],
        "permitted_event_types": ["AgentSignal", "AgentAction"],
        "forbidden_targets": [],
        "resource_ceiling": {
            "max_tokens_per_run": 50000,
            "max_duration_seconds": 120,
            "max_mcp_reads_per_run": 5,
        },
    }])

    async def _run() -> None:
        acap = await load_acap(client, "exploratory")
        assert acap is not None
        assert acap.acap_id == "acap-exploratory"
        assert acap.agent_type == "exploratory"

    asyncio.run(_run())


def test_create_objective() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])
    now = datetime.now(UTC)

    objective = ObjectiveRecord(
        objective_id="obj-001",
        status="active",
        created_at=now,
        domain="test",
        priority_signal=0.8,
    )

    async def _run() -> None:
        result = await create_objective(client, objective)
        assert result == "obj-001"
        body = client.pop_post_call()
        assert "INSERT INTO ObjectiveRecord" in body["command"]
        assert body["params"]["objective_id"] == "obj-001"

    asyncio.run(_run())


def test_get_objective() -> None:
    now = datetime.now(UTC)
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "objective_id": "obj-001",
        "status": "active",
        "created_at": now.isoformat(),
        "domain": "test",
        "priority_signal": 0.8,
        "checkpoint": None,
        "assigned_agent_id": None,
        "implementation_status": "none",
        "implementation_state": "to_do",
    }])

    async def _run() -> None:
        obj = await get_objective(client, "obj-001")
        assert obj is not None
        assert obj.objective_id == "obj-001"
        assert obj.status == "active"

    asyncio.run(_run())


def test_get_objective_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        obj = await get_objective(client, "nonexistent")
        assert obj is None

    asyncio.run(_run())


def test_update_objective() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        await update_objective(client, "obj-001", {"status": "complete"})
        body = client.pop_post_call()
        assert "UPDATE ObjectiveRecord SET" in body["command"]
        assert body["params"]["status"] == "complete"
        assert body["params"]["objective_id"] == "obj-001"

    asyncio.run(_run())


def test_write_checkpoint() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])
    now = datetime.now(UTC)
    checkpoint = CognitiveCheckpoint(
        hypotheses_investigated=[
            HypothesisRecord(
                hypothesis="H1", conclusion="confirmed", evidence="E1"
            ),
        ],
        current_best_understanding="Understood",
        recommended_next_action="Next step",
        checkpoint_at=now,
    )

    async def _run() -> None:
        await write_checkpoint(client, "obj-001", checkpoint)
        body = client.pop_post_call()
        assert "UPDATE ObjectiveRecord" in body["command"]
        assert "checkpoint = :checkpoint" in body["command"]
        assert body["params"]["objective_id"] == "obj-001"
        assert "checkpoint" in body["params"]

    asyncio.run(_run())
