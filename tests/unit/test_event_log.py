from datetime import UTC, datetime

import pytest

from schema.timeseries.event_log import (
    AgentAction,
    AgentCheckpoint,
    AgentFinding,
    AgentSignal,
    ObjectiveTransition,
)


def test_agent_signal_valid() -> None:
    signal = AgentSignal(
        event_type="AgentSignal",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        objective_id="none",
        mtp_version="1.0",
        payload={"domain": "test"},
        confidence=0.8,
        novelty_flag=True,
    )
    assert signal.confidence == 0.8
    assert signal.novelty_flag is True


def test_agent_signal_wrong_event_type() -> None:
    with pytest.raises(ValueError, match="event_type must be 'AgentSignal'"):
        AgentSignal(
            event_type="Wrong",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            objective_id="none",
            mtp_version="1.0",
            payload={},
            confidence=0.5,
            novelty_flag=False,
        )


def test_agent_signal_confidence_too_high() -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        AgentSignal(
            event_type="AgentSignal",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            objective_id="none",
            mtp_version="1.0",
            payload={},
            confidence=1.5,
            novelty_flag=False,
        )


def test_agent_signal_confidence_too_low() -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        AgentSignal(
            event_type="AgentSignal",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            objective_id="none",
            mtp_version="1.0",
            payload={},
            confidence=-0.1,
            novelty_flag=False,
        )


def test_agent_action_valid() -> None:
    action = AgentAction(
        event_type="AgentAction",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        objective_id="obj-1",
        mtp_version="1.0",
        payload={"tool": "web_search"},
    )
    assert action.event_type == "AgentAction"


def test_agent_action_wrong_event_type() -> None:
    with pytest.raises(ValueError, match="event_type must be 'AgentAction'"):
        AgentAction(
            event_type="Wrong",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            objective_id="none",
            mtp_version="1.0",
            payload={},
        )


def test_agent_finding_valid() -> None:
    finding = AgentFinding(
        event_type="AgentFinding",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        objective_id="obj-1",
        mtp_version="1.0",
        payload={"verdict": "confirmed"},
        confidence=0.9,
        novelty_flag=False,
    )
    assert finding.confidence == 0.9


def test_agent_finding_confidence_out_of_range() -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        AgentFinding(
            event_type="AgentFinding",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            objective_id="obj-1",
            mtp_version="1.0",
            payload={},
            confidence=2.0,
            novelty_flag=False,
        )


def test_agent_checkpoint_valid() -> None:
    checkpoint = AgentCheckpoint(
        event_type="AgentCheckpoint",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        objective_id="obj-1",
        mtp_version="1.0",
        payload={"hypotheses": []},
    )
    assert checkpoint.event_type == "AgentCheckpoint"


def test_agent_checkpoint_wrong_event_type() -> None:
    with pytest.raises(ValueError, match="event_type must be 'AgentCheckpoint'"):
        AgentCheckpoint(
            event_type="Wrong",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            objective_id="none",
            mtp_version="1.0",
            payload={},
        )


def test_objective_transition_valid() -> None:
    transition = ObjectiveTransition(
        event_type="ObjectiveTransition",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        objective_id="obj-1",
        mtp_version="1.0",
        payload={"from_status": "active", "to_status": "complete"},
    )
    assert transition.event_type == "ObjectiveTransition"


def test_objective_transition_wrong_event_type() -> None:
    with pytest.raises(ValueError, match="event_type must be 'ObjectiveTransition'"):
        ObjectiveTransition(
            event_type="Wrong",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            objective_id="none",
            mtp_version="1.0",
            payload={},
        )


def test_confidence_boundary_zero() -> None:
    signal = AgentSignal(
        event_type="AgentSignal",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        objective_id="none",
        mtp_version="1.0",
        payload={},
        confidence=0.0,
        novelty_flag=False,
    )
    assert signal.confidence == 0.0


def test_confidence_boundary_one() -> None:
    signal = AgentSignal(
        event_type="AgentSignal",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        objective_id="none",
        mtp_version="1.0",
        payload={},
        confidence=1.0,
        novelty_flag=False,
    )
    assert signal.confidence == 1.0
