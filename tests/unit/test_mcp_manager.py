from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from schema.identity.models import ACAPDefinition, ResourceCeiling
from shared.acap.exceptions import ACAPViolationError
from shared.arcadedb.client import ArcadeDBClient
from shared.mcp.manager import MCPConnectionManager


def _make_acap() -> ACAPDefinition:
    return ACAPDefinition(
        acap_id="acap-test",
        agent_type="exploratory",
        permitted_tools=["web_search"],
        permitted_mcp_connections=["https://mcp.example.com/v1"],
        permitted_event_types=["AgentSignal", "AgentAction"],
        forbidden_targets=[],
        resource_ceiling=ResourceCeiling(
            max_tokens_per_run=100000,
            max_duration_seconds=300,
            max_mcp_reads_per_run=10,
        ),
    )


def _mock_http_response() -> AsyncMock:
    resp = AsyncMock()
    resp.is_success = True
    resp.status_code = 200
    resp.text = "mock response content"
    resp.raise_for_status = lambda: None
    return resp


def test_list_permitted_connections() -> None:
    mgr = MCPConnectionManager(_make_acap(), _make_client())
    connections = mgr.list_permitted_connections()
    assert "https://mcp.example.com/v1" in connections


def _make_client() -> ArcadeDBClient:
    client = ArcadeDBClient("http://localhost:2480", "testdb", "user", "pass")
    response = _mock_http_response()
    response.json = lambda: {"result": []}
    client._client.post = AsyncMock(return_value=response)  # type: ignore[method-assign]
    return client


def test_read_permitted_server() -> None:
    mgr = MCPConnectionManager(_make_acap(), _make_client())
    mgr._http.post = AsyncMock(return_value=_mock_http_response())  # type: ignore[method-assign]

    async def _run() -> None:
        content = await mgr.read(
            server_url="https://mcp.example.com/v1",
            resource_path="docs/design.md",
            agent_id="a1",
            objective_id="o1",
            mtp_version="1.0",
        )
        assert content == "mock response content"

    asyncio.run(_run())


def test_read_unpermitted_server_raises_before_network() -> None:
    mgr = MCPConnectionManager(_make_acap(), _make_client())

    async def _run() -> None:
        with pytest.raises(ACAPViolationError, match="not in permitted_mcp_connections"):
            await mgr.read(
                server_url="https://evil.com",
                resource_path="docs/secret.md",
                agent_id="a1",
                objective_id="o1",
                mtp_version="1.0",
            )

    asyncio.run(_run())
