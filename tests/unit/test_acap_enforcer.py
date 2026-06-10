from __future__ import annotations

import pytest

from schema.identity.models import ACAPDefinition, ResourceCeiling
from shared.acap.enforcer import ACAPEnforcer
from shared.acap.exceptions import ACAPViolationError
from shared.arcadedb.client import ArcadeDBClient


def _make_acap() -> ACAPDefinition:
    return ACAPDefinition(
        acap_id="acap-exploratory",
        agent_type="exploratory",
        permitted_tools=["search_graph", "search_signals", "emit_signal"],
        permitted_mcp_connections=["https://example.com/mcp"],
        permitted_event_types=["AgentSignal", "AgentAction"],
        forbidden_targets=["https://blocked.com"],
        resource_ceiling=ResourceCeiling(
            max_tokens_per_run=10000,
            max_duration_seconds=300,
            max_mcp_reads_per_run=100,
        ),
    )


def _make_client() -> ArcadeDBClient:
    return ArcadeDBClient("http://localhost:2480", "db", "u", "p")


def test_check_tool_permitted() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_tool("search_graph", "a1", "f1", "1.0")


def test_check_tool_not_permitted_raises() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError):
        enforcer.check_tool("forbidden_tool", "a1", "f1", "1.0")


def test_check_mcp_connection_permitted() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_mcp_connection("https://example.com/mcp", "a1", "f1", "1.0")


def test_check_mcp_connection_not_permitted_raises() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError):
        enforcer.check_mcp_connection("https://evil.com", "a1", "f1", "1.0")


def test_check_event_type_permitted() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_event_type("AgentSignal", "a1", "f1", "1.0")


def test_check_event_type_not_permitted_raises() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError):
        enforcer.check_event_type("ForbiddenEvent", "a1", "f1", "1.0")


def test_check_resource_ceiling_within_limits() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    enforcer.check_resource_ceiling(100, 10.0, 5, "a1", "f1", "1.0")


def test_check_resource_ceiling_tokens_exceeded() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError):
        enforcer.check_resource_ceiling(20000, 10.0, 5, "a1", "f1", "1.0")


def test_check_resource_ceiling_duration_exceeded() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError):
        enforcer.check_resource_ceiling(100, 400.0, 5, "a1", "f1", "1.0")


def test_check_resource_ceiling_mcp_reads_exceeded() -> None:
    enforcer = ACAPEnforcer(_make_acap(), _make_client())
    with pytest.raises(ACAPViolationError):
        enforcer.check_resource_ceiling(100, 10.0, 200, "a1", "f1", "1.0")


def test_acap_violation_error_message() -> None:
    error = ACAPViolationError("test action", "test reason", "agent-1", "focus-1")
    assert "agent-1" in str(error)
    assert "test action" in str(error)
    assert error.agent_id == "agent-1"
    assert error.focus_id == "focus-1"
