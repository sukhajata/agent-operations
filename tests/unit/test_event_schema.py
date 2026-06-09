from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from schema.timeseries.event_log import (
    AgentAction,
    AgentCheckpoint,
    AgentFinding,
    AgentSignal,
    ObjectiveTransition,
)
from shared.event_schemas.validator import (
    EventSchemaError,
    check_required_fields,
    validate_event,
)

SAMPLE_DATETIME = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


def _valid_event(event_type: str) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_type": event_type,
        "ts": SAMPLE_DATETIME,
        "agent_id": "agent-1",
        "objective_id": "obj-1",
        "mtp_version": "1.0",
        "payload": {},
    }
    if event_type in ("AgentSignal", "AgentFinding"):
        base["confidence"] = 0.8
        base["novelty_flag"] = False
    return base


# --- validate_event ---


def test_validate_agent_signal() -> None:
    event = _valid_event("AgentSignal")
    result = validate_event(event)
    assert isinstance(result, AgentSignal)
    assert result.agent_id == "agent-1"
    assert result.confidence == 0.8


def test_validate_agent_action() -> None:
    event = _valid_event("AgentAction")
    result = validate_event(event)
    assert isinstance(result, AgentAction)


def test_validate_agent_finding() -> None:
    event = _valid_event("AgentFinding")
    result = validate_event(event)
    assert isinstance(result, AgentFinding)
    assert result.novelty_flag is False


def test_validate_agent_checkpoint() -> None:
    event = _valid_event("AgentCheckpoint")
    result = validate_event(event)
    assert isinstance(result, AgentCheckpoint)


def test_validate_objective_transition() -> None:
    event = _valid_event("ObjectiveTransition")
    result = validate_event(event)
    assert isinstance(result, ObjectiveTransition)


def test_validate_missing_event_type() -> None:
    event = _valid_event("AgentSignal")
    del event["event_type"]
    with pytest.raises(EventSchemaError):
        validate_event(event)


def test_validate_unknown_event_type() -> None:
    event = _valid_event("AgentSignal")
    event["event_type"] = "UnknownEvent"
    with pytest.raises(EventSchemaError, match="Unknown event_type"):
        validate_event(event)


def test_validate_confidence_out_of_range() -> None:
    event = _valid_event("AgentSignal")
    event["confidence"] = 1.5
    with pytest.raises(EventSchemaError):
        validate_event(event)


# --- check_required_fields ---


def test_check_required_fields_all_present() -> None:
    event = _valid_event("AgentSignal")
    check_required_fields(event)


def test_check_required_fields_missing_agent_id() -> None:
    event = _valid_event("AgentSignal")
    del event["agent_id"]
    with pytest.raises(EventSchemaError, match="agent_id"):
        check_required_fields(event)


def test_check_required_fields_missing_objective_id() -> None:
    event = _valid_event("AgentSignal")
    del event["objective_id"]
    with pytest.raises(EventSchemaError, match="objective_id"):
        check_required_fields(event)


def test_check_required_fields_missing_mtp_version() -> None:
    event = _valid_event("AgentSignal")
    del event["mtp_version"]
    with pytest.raises(EventSchemaError, match="mtp_version"):
        check_required_fields(event)


def test_check_required_fields_missing_ts() -> None:
    event = _valid_event("AgentSignal")
    del event["ts"]
    with pytest.raises(EventSchemaError, match="ts"):
        check_required_fields(event)


def test_check_required_fields_empty_values() -> None:
    event = _valid_event("AgentSignal")
    event["agent_id"] = ""
    with pytest.raises(EventSchemaError, match="agent_id"):
        check_required_fields(event)
