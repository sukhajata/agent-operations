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
        mtp_version="1.0",
        claim="The system has a memory leak in the auth module",
        domain="performance",
        confidence=0.8,
        reasoning="Observed heap growth over 24h with no corresponding traffic increase",
        sources=["heap_dump_2026-06-10.hprof", "metrics/dashboard-42"],
        focus_id="obj-001",
        novelty_flag=True,
    )
    assert signal.confidence == 0.8
    assert signal.novelty_flag is True
    assert signal.claim == "The system has a memory leak in the auth module"
    assert signal.focus_id == "obj-001"
    assert len(signal.sources) == 2


def test_agent_signal_focus_id_none_for_free_exploration() -> None:
    signal = AgentSignal(
        event_type="AgentSignal",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        mtp_version="1.0",
        claim="test claim",
        domain="test",
        confidence=0.5,
        reasoning="test reasoning",
        sources=[],
        focus_id=None,
        novelty_flag=False,
    )
    assert signal.focus_id is None


def test_agent_signal_wrong_event_type() -> None:
    with pytest.raises(ValueError, match="event_type must be 'AgentSignal'"):
        AgentSignal(
            event_type="Wrong",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            mtp_version="1.0",
            claim="test",
            domain="test",
            confidence=0.5,
            reasoning="test",
            sources=[],
            focus_id=None,
            novelty_flag=False,
        )


def test_agent_signal_confidence_too_high() -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        AgentSignal(
            event_type="AgentSignal",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            mtp_version="1.0",
            claim="test",
            domain="test",
            confidence=1.5,
            reasoning="test",
            sources=[],
            focus_id=None,
            novelty_flag=False,
        )


def test_agent_signal_confidence_too_low() -> None:
    with pytest.raises(ValueError, match="confidence must be in"):
        AgentSignal(
            event_type="AgentSignal",
            ts=datetime.now(UTC),
            agent_id="agent-1",
            mtp_version="1.0",
            claim="test",
            domain="test",
            confidence=-0.1,
            reasoning="test",
            sources=[],
            focus_id=None,
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
        mtp_version="1.0",
        claim="test",
        domain="test",
        confidence=0.0,
        reasoning="test",
        sources=[],
        focus_id=None,
        novelty_flag=False,
    )
    assert signal.confidence == 0.0


def test_confidence_boundary_one() -> None:
    signal = AgentSignal(
        event_type="AgentSignal",
        ts=datetime.now(UTC),
        agent_id="agent-1",
        mtp_version="1.0",
        claim="test",
        domain="test",
        confidence=1.0,
        reasoning="test",
        sources=[],
        focus_id=None,
        novelty_flag=False,
    )
    assert signal.confidence == 1.0
