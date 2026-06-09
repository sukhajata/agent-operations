from __future__ import annotations

import json
from unittest.mock import AsyncMock

import httpx
import pytest

from schema.identity.models import ACAPDefinition, ResourceCeiling
from shared.acap.exceptions import ACAPViolationError
from shared.arcadedb.client import ArcadeDBClient
from shared.mcp.manager import MCPConnectionManager


def _make_acap() -> ACAPDefinition:
    return ACAPDefinition(
        acap_id="acap-1",
        agent_type="exploratory",
        permitted_tools=["search_graph"],
        permitted_mcp_connections=["https://ok.example.com/mcp"],
        permitted_event_types=["AgentSignal"],
        forbidden_targets=[],
        resource_ceiling=ResourceCeiling(
            max_tokens_per_run=10000,
            max_duration_seconds=300,
            max_mcp_reads_per_run=100,
        ),
    )


def test_list_permitted_connections() -> None:
    client = ArcadeDBClient("http://localhost:2480", "db", "u", "p")
    manager = MCPConnectionManager(_make_acap(), client)
    urls = manager.list_permitted_connections()
    assert "https://ok.example.com/mcp" in urls


def test_read_permitted_server() -> None:
    client = ArcadeDBClient("http://localhost:2480", "db", "u", "p")
    manager = MCPConnectionManager(_make_acap(), client)

    mock_response = httpx.Response(200, text=json.dumps({"data": "hello"}))
    manager._http.post = AsyncMock(return_value=mock_response)

    async def _run() -> None:
        result = await manager.read(
            server_url="https://ok.example.com/mcp",
            resource_path="/docs/report",
            agent_id="a1",
            focus_id="f1",
            mtp_version="1.0",
        )
        await manager.close()
        assert "hello" in result

    import asyncio
    asyncio.run(_run())


def test_read_unpermitted_server_raises_before_network() -> None:
    client = ArcadeDBClient("http://localhost:2480", "db", "u", "p")
    manager = MCPConnectionManager(_make_acap(), client)

    with pytest.raises(ACAPViolationError):
        import asyncio

        async def _run() -> None:
            await manager.read(
                server_url="https://evil.example.com/mcp",
                resource_path="/docs/secret",
                agent_id="a1",
                focus_id="f1",
                mtp_version="1.0",
            )
            await manager.close()

        asyncio.run(_run())
