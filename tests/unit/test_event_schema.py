from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from schema.timeseries.event_log import (
    AgentAction,
    AgentCheckpoint,
    AgentFinding,
    AgentSignal,
    CommitmentTransition,
)
from shared.event_schemas.validator import (
    EventSchemaError,
    check_required_fields,
    validate_event,
)

SAMPLE_DATETIME = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


def _valid_event(event_type: str) -> dict[str, Any]:
    if event_type == "AgentSignal":
        return {
            "event_type": "AgentSignal",
            "ts": SAMPLE_DATETIME,
            "agent_id": "agent-1",
            "mtp_version": "1.0",
            "claim": "test claim",
            "domain": "test",
            "confidence": 0.8,
            "reasoning": "test reasoning",
            "sources": ["source-1"],
            "focus_id": "obj-1",
            "novelty_flag": False,
        }
    if event_type == "AgentFinding":
        return {
            "event_type": "AgentFinding",
            "ts": SAMPLE_DATETIME,
            "agent_id": "agent-1",
            "mtp_version": "1.0",
            "claim": "verified claim",
            "domain": "test",
            "confidence": 0.95,
            "reasoning": "verified via independent analysis",
            "sources": ["source-1"],
            "focus_id": "obj-1",
            "verdict": "confirmed",
            "originating_signal_ts": SAMPLE_DATETIME,
        }
    if event_type == "AgentAction":
        return {
            "event_type": "AgentAction",
            "ts": SAMPLE_DATETIME,
            "agent_id": "agent-1",
            "commitment_id": None,
            "mtp_version": "1.0",
            "payload": {},
        }
    if event_type == "AgentCheckpoint":
        return {
            "event_type": "AgentCheckpoint",
            "ts": SAMPLE_DATETIME,
            "agent_id": "agent-1",
            "commitment_id": "com-1",
            "mtp_version": "1.0",
            "payload": {},
        }
    if event_type == "CommitmentTransition":
        return {
            "event_type": "CommitmentTransition",
            "ts": SAMPLE_DATETIME,
            "agent_id": "agent-1",
            "commitment_id": "com-1",
            "mtp_version": "1.0",
            "payload": {},
        }
    raise ValueError(f"Unknown event type: {event_type}")


# --- validate_event ---


def test_validate_agent_signal() -> None:
    event = _valid_event("AgentSignal")
    result = validate_event(event)
    assert isinstance(result, AgentSignal)
    assert result.agent_id == "agent-1"
    assert result.confidence == 0.8


def test_validate_agent_finding() -> None:
    event = _valid_event("AgentFinding")
    result = validate_event(event)
    assert isinstance(result, AgentFinding)
    assert result.verdict == "confirmed"
    assert result.confidence == 0.95


def test_validate_agent_action() -> None:
    event = _valid_event("AgentAction")
    result = validate_event(event)
    assert isinstance(result, AgentAction)


def test_validate_agent_checkpoint() -> None:
    event = _valid_event("AgentCheckpoint")
    result = validate_event(event)
    assert isinstance(result, AgentCheckpoint)


def test_validate_commitment_transition() -> None:
    event = _valid_event("CommitmentTransition")
    result = validate_event(event)
    assert isinstance(result, CommitmentTransition)


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


def test_validate_rejects_removed_objective_transition() -> None:
    event = _valid_event("CommitmentTransition")
    event["event_type"] = "ObjectiveTransition"
    with pytest.raises(EventSchemaError, match="has been removed"):
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


def test_check_required_fields_focus_id_optional() -> None:
    event = _valid_event("AgentSignal")
    del event["focus_id"]
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
