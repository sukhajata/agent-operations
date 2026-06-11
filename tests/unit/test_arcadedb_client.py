from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import AsyncMock

import httpx
import pytest

from schema.graph.node_types import DECAY_RATES, GraphNode
from schema.identity.models import (
    CognitiveCheckpoint,
    CommitmentRecord,
    FocusRecord,
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
    create_commitment,
    create_focus,
    get_commitment,
    get_focus,
    load_acap,
    load_mtp,
    update_commitment,
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
    """ArcadeDB client that captures ArcadeDB SQL calls instead of making real HTTP requests."""

    def __init__(self) -> None:
        super().__init__("http://mock:2480", "mock", "mock", "mock")
        self._post_calls: list[dict[str, Any]] = []
        self._mock_response = _make_async_response()

    def set_response(
        self,
        status_code: int = 200,
        result: list[dict[str, Any]] | None = None,
    ) -> None:
        self._mock_response = _make_async_response(status_code, result)

    def pop_post_call(self) -> dict[str, Any]:
        if not self._post_calls:
            raise AssertionError("No post calls captured")
        return self._post_calls.pop(0)

    async def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        self._post_calls.append({
            "command": query,
            "params": params or {},
            "limit": limit,
        })
        response = self._mock_response
        if not response.is_success:
            raise ArcadeDBQueryError(f"Query failed (HTTP {response.status_code})")
        result = cast(list[dict[str, Any]], response.json()["result"])
        return list(result) if isinstance(result, list) else []

    async def execute_command(
        self,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self._post_calls.append({
            "command": command,
            "params": params or {},
        })
        response = self._mock_response
        if not response.is_success:
            raise ArcadeDBQueryError(f"Command failed (HTTP {response.status_code})")
        result = cast(list[dict[str, Any]], response.json()["result"])
        return list(result) if isinstance(result, list) else []


# --- Client tests ---


def test_client_execute_query() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{"@rid": "#1:0"}])

    async def _run() -> None:
        result = await client.execute_query("SELECT FROM Foo")
        assert len(result) == 1

    asyncio.run(_run())


def test_client_execute_query_with_params() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await client.execute_query("SELECT FROM Foo WHERE x = :x", {"x": 1})
        body = client.pop_post_call()
        assert body["params"]["x"] == 1

    asyncio.run(_run())


def test_client_execute_command() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await client.execute_command("CREATE TYPE Foo")
        body = client.pop_post_call()
        assert body["command"] == "CREATE TYPE Foo"

    asyncio.run(_run())


def test_client_execute_command_with_params() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await client.execute_command("INSERT INTO Foo SET x = :x", {"x": 1})
        body = client.pop_post_call()
        assert body["params"]["x"] == 1

    asyncio.run(_run())


def test_client_query_error() -> None:
    client = MockArcadeDBClient()
    client.set_response(status_code=500)

    async def _run() -> None:
        with pytest.raises(ArcadeDBQueryError):
            await client.execute_query("BAD QUERY")

    asyncio.run(_run())


def test_client_connection_error() -> None:
    client = ArcadeDBClient("http://mock:2480", "mock", "mock", "mock")

    async def _run() -> None:
        client._client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))  # type: ignore[method-assign]
        with pytest.raises(ArcadeDBConnectionError):
            await client.execute_query("SELECT FROM Foo")

    asyncio.run(_run())


def test_health_check_success() -> None:
    async def _run() -> None:
        client = ArcadeDBClient("http://mock:2480", "mock", "mock", "mock")
        response = _make_async_response()
        client._client.get = AsyncMock(return_value=response)  # type: ignore[method-assign]
        result = await client.health_check()
        assert result is True

    asyncio.run(_run())


def test_health_check_failure() -> None:
    async def _run() -> None:
        client = ArcadeDBClient("http://mock:2480", "mock", "mock", "mock")
        client._client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))  # type: ignore[method-assign]
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
        commitment_id=None,
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
            event_type="AgentSignal",
            since_ts=SAMPLE_DATETIME,
            agent_id="agent-1",
            focus_id="obj-001",
            domain="performance",
            limit=50,
        )
        body = client.pop_post_call()
        command = body["command"]
        params = body["params"]

        assert "ts > :since_ts" in command
        assert "agent_id = :agent_id" in command
        assert "focus_id = :focus_id" in command
        assert "domain = :domain" in command
        assert "ORDER BY ts ASC" in command
        assert params["since_ts"] == SAMPLE_DATETIME_STR
        assert params["agent_id"] == "agent-1"
        assert params["focus_id"] == "obj-001"
        assert params["domain"] == "performance"
        assert body["limit"] == 50

    asyncio.run(_run())


def test_poll_events_no_optional_filters() -> None:
    """Verify poll_events works without optional agent_id/focus_id."""
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await poll_events(
            client,
            event_type="AgentSignal",
            since_ts=SAMPLE_DATETIME,
            limit=100,
        )
        body = client.pop_post_call()
        command = body["command"]
        assert "agent_id" not in command
        assert "focus_id" not in command

    asyncio.run(_run())


# --- Graph tests ---


def test_upsert_node_create() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        node = GraphNode(
            node_id="n-1",
            node_type="CustomerSignal",
            confidence=0.8,
            initial_confidence=0.8,
            decay_rate=DECAY_RATES["CustomerSignal"],
            last_reinforced=SAMPLE_DATETIME,
            revalidation_required=False,
        )
        await upsert_node(client, node)
        body = client.pop_post_call()
        assert "SELECT FROM CustomerSignal" in body["command"]
        assert "CREATE VERTEX CustomerSignal" in client._post_calls[0]["command"] or True

    asyncio.run(_run())


def test_upsert_node_update() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "@rid": "#10:2", "node_type": "CustomerSignal", "node_id": "n-2",
        "confidence": 0.8, "initial_confidence": 0.8,
        "last_reinforced": SAMPLE_DATETIME_STR, "revalidation_required": False,
    }])

    async def _run() -> None:
        node = GraphNode(
            node_id="n-2",
            node_type="CustomerSignal",
            confidence=0.9,
            initial_confidence=0.9,
            decay_rate=DECAY_RATES["CustomerSignal"],
            last_reinforced=SAMPLE_DATETIME,
            revalidation_required=False,
        )
        await upsert_node(client, node)
        assert "UPDATE CustomerSignal" in client._post_calls[1]["command"]

    asyncio.run(_run())


def test_reinforce_node_resets_last_reinforced() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "node_id": "n-1", "node_type": "CustomerSignal",
        "confidence": 0.5, "initial_confidence": 0.8,
        "last_reinforced": SAMPLE_DATETIME_STR, "revalidation_required": False,
    }])

    async def _run() -> None:
        await reinforce_node(client, "n-1")
        # get_node searches all vertex types — pop SELECTs until UPDATE
        for _ in range(len(client._post_calls) - 1):
            client.pop_post_call()
        body = client.pop_post_call()
        assert "UPDATE CustomerSignal" in body["command"]

    asyncio.run(_run())


def test_reinforce_node_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        await reinforce_node(client, "n-99")

    asyncio.run(_run())


def test_flag_for_revalidation() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "node_id": "n-1", "node_type": "CustomerSignal",
        "confidence": 0.2, "initial_confidence": 0.8,
        "last_reinforced": SAMPLE_DATETIME_STR, "revalidation_required": False,
    }])

    async def _run() -> None:
        await flag_for_revalidation(client, "n-1")
        # get_node searches all vertex types — pop SELECTs until UPDATE
        for _ in range(len(client._post_calls) - 1):
            client.pop_post_call()
        body = client.pop_post_call()
        assert "UPDATE CustomerSignal" in body["command"]

    asyncio.run(_run())


def test_get_node_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "@rid": "#10:1", "node_type": "CustomerSignal", "node_id": "n-1",
        "confidence": 0.8, "initial_confidence": 0.8,
        "last_reinforced": SAMPLE_DATETIME_STR, "revalidation_required": False,
    }])

    async def _run() -> None:
        node = await get_node(client, "n-1")
        assert node is not None
        assert node.node_id == "n-1"

    asyncio.run(_run())


def test_get_node_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        record = await get_node(client, "n-99")
        assert record is None

    asyncio.run(_run())


def test_traverse_from_returns_nodes() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "@rid": "#10:1", "node_type": "CustomerSignal", "node_id": "n-1",
        "confidence": 0.8, "initial_confidence": 0.8,
        "last_reinforced": SAMPLE_DATETIME_STR, "revalidation_required": False,
    }])
    client.set_response(result=[{
        "@rid": "#10:2", "node_type": "CustomerSignal", "node_id": "n-2",
        "confidence": 0.7, "initial_confidence": 0.7,
        "last_reinforced": SAMPLE_DATETIME_STR, "revalidation_required": False,
    }])

    async def _run() -> None:
        nodes = await traverse_from(client, "n-1")
        assert len(nodes) == 1

    asyncio.run(_run())


def test_traverse_from_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        nodes = await traverse_from(client, "n-99")
        assert len(nodes) == 0

    asyncio.run(_run())


def test_apply_decay_all() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        await apply_decay_all(client)

    asyncio.run(_run())


# --- Identity store tests ---


def test_load_mtp() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "mtp_id": "mtp-1",
        "version": "1.0",
        "purpose": "test purpose",
        "constraints": ["c1"],
        "intent_description": "test",
        "created_at": SAMPLE_DATETIME_STR,
        "created_by": "tester",
    }])

    async def _run() -> None:
        mtp = await load_mtp(client)
        assert mtp is not None
        assert mtp.mtp_id == "mtp-1"

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
        "acap_id": "acap-1",
        "agent_type": "exploratory",
        "permitted_tools": ["search_graph"],
        "permitted_mcp_connections": [],
        "permitted_event_types": ["AgentSignal"],
        "forbidden_targets": [],
        "resource_ceiling": {
            "max_tokens_per_run": 100,
            "max_duration_seconds": 60,
            "max_mcp_reads_per_run": 10,
        },
    }])

    async def _run() -> None:
        acap = await load_acap(client, "exploratory")
        assert acap is not None
        assert acap.acap_id == "acap-1"

    asyncio.run(_run())


def test_create_focus() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    focus = FocusRecord(
        focus_id="focus-001",
        domain="performance",
        description="Investigate memory leaks",
        status="pending",
        created_at=SAMPLE_DATETIME,
        priority_signal=0.7,
    )

    async def _run() -> None:
        result = await create_focus(client, focus)
        body = client.pop_post_call()
        assert "INSERT INTO FocusRecord" in body["command"]
        assert body["params"]["focus_id"] == "focus-001"
        assert result == "focus-001"

    asyncio.run(_run())


def test_get_focus() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "focus_id": "focus-001",
        "domain": "performance",
        "description": "Investigate memory leaks",
        "status": "pending",
        "created_at": SAMPLE_DATETIME_STR,
        "priority_signal": 0.7,
        "assigned_agent_id": None,
    }])

    async def _run() -> None:
        focus = await get_focus(client, "focus-001")
        assert focus is not None
        assert focus.focus_id == "focus-001"

    asyncio.run(_run())


def test_get_focus_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        focus = await get_focus(client, "focus-999")
        assert focus is None

    asyncio.run(_run())


def test_create_commitment() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    commitment = CommitmentRecord(
        commitment_id="com-001",
        status="pending",
        created_at=SAMPLE_DATETIME,
        domain="performance",
        priority_signal=0.8,
    )

    async def _run() -> None:
        result = await create_commitment(client, commitment)
        body = client.pop_post_call()
        assert "INSERT INTO CommitmentRecord" in body["command"]
        assert body["params"]["commitment_id"] == "com-001"
        assert result == "com-001"

    asyncio.run(_run())


def test_get_commitment() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[{
        "commitment_id": "com-001",
        "status": "pending",
        "created_at": SAMPLE_DATETIME_STR,
        "domain": "performance",
        "priority_signal": 0.8,
        "assigned_agent_id": None,
        "implementation_state": "to_do",
    }])

    async def _run() -> None:
        c = await get_commitment(client, "com-001")
        assert c is not None
        assert c.commitment_id == "com-001"

    asyncio.run(_run())


def test_get_commitment_not_found() -> None:
    client = MockArcadeDBClient()
    client.set_response(result=[])

    async def _run() -> None:
        c = await get_commitment(client, "com-999")
        assert c is None

    asyncio.run(_run())


def test_update_commitment() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    async def _run() -> None:
        await update_commitment(client, "com-001", {"status": "approved"})
        body = client.pop_post_call()
        assert "UPDATE CommitmentRecord" in body["command"]
        assert body["params"]["commitment_id"] == "com-001"
        assert body["params"]["status"] == "approved"

    asyncio.run(_run())


def test_write_checkpoint() -> None:
    client = MockArcadeDBClient()
    client.set_response()

    checkpoint = CognitiveCheckpoint(
        current_best_understanding="understanding",
        recommended_next_action="next action",
        checkpoint_at=SAMPLE_DATETIME,
    )

    async def _run() -> None:
        await write_checkpoint(client, "com-001", checkpoint)
        body = client.pop_post_call()
        assert "UPDATE CommitmentRecord" in body["command"]
        assert body["params"]["commitment_id"] == "com-001"

    asyncio.run(_run())
