from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from schema.identity.models import ACAPDefinition, ResourceCeiling
from shared.acap.enforcer import ACAPEnforcer
from shared.acap.exceptions import ACAPViolationError
from shared.arcadedb.client import ArcadeDBClient


def _make_acap(agent_type: str = "exploratory") -> ACAPDefinition:
    return ACAPDefinition(
        acap_id=f"acap-{agent_type}",
        agent_type=agent_type,  # type: ignore[arg-type]
        permitted_tools=["web_search", "code_read"],
        permitted_mcp_connections=["https://mcp.example.com/v1"],
        permitted_event_types=["AgentSignal", "AgentAction"],
        forbidden_targets=["objective_registry"],
        resource_ceiling=ResourceCeiling(
            max_tokens_per_run=100000,
            max_duration_seconds=300,
            max_mcp_reads_per_run=10,
        ),
    )


def _make_client() -> ArcadeDBClient:
    client = ArcadeDBClient("http://localhost:2480", "testdb", "user", "pass")
    client._client.post = AsyncMock()  # type: ignore[method-assign]
    return client


# --- check_tool ---


def test_check_tool_permitted() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_tool("web_search", "a1", "o1", "1.0")


def test_check_tool_not_permitted_raises() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError, match="tool not in permitted_tools"):
        enforcer.check_tool("admin_delete", "a1", "o1", "1.0")


# --- check_mcp_connection ---


def test_check_mcp_connection_permitted() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_mcp_connection("https://mcp.example.com/v1", "a1", "o1", "1.0")


def test_check_mcp_connection_not_permitted_raises() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError, match="not in permitted_mcp_connections"):
        enforcer.check_mcp_connection("https://evil.com", "a1", "o1", "1.0")


# --- check_event_type ---


def test_check_event_type_permitted() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_event_type("AgentSignal", "a1", "o1", "1.0")


def test_check_event_type_not_permitted_raises() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError, match="not in permitted_event_types"):
        enforcer.check_event_type("AgentCheckpoint", "a1", "o1", "1.0")


# --- check_resource_ceiling ---


def test_check_resource_ceiling_within_limits() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_resource_ceiling(50000, 100.0, 5, "a1", "o1", "1.0")


def test_check_resource_ceiling_tokens_exceeded() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError, match="tokens_used"):
        enforcer.check_resource_ceiling(200000, 100.0, 5, "a1", "o1", "1.0")


def test_check_resource_ceiling_duration_exceeded() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError, match="duration"):
        enforcer.check_resource_ceiling(50000, 500.0, 5, "a1", "o1", "1.0")


def test_check_resource_ceiling_mcp_reads_exceeded() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError, match="mcp_reads"):
        enforcer.check_resource_ceiling(50000, 100.0, 20, "a1", "o1", "1.0")


# --- log_violation emits event ---


def test_log_violation_emits_event() -> None:
    client = _make_client()
    enforcer = ACAPEnforcer(_make_acap(), client)

    violation = ACAPViolationError("test", "reason", "a1", "o1")
    enforcer.log_violation(violation, "1.0")

    async def _run() -> None:
        pass

    asyncio.run(_run())


# --- ACAPViolationError ---


def test_acap_violation_error_message() -> None:
    err = ACAPViolationError("do X", "not allowed", "agent-1", "obj-1")
    assert "agent-1" in str(err)
    assert "do X" in str(err)
    assert "not allowed" in str(err)
