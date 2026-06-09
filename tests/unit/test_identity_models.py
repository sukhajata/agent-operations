from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schema.identity.models import (
    ACAPDefinition,
    CognitiveCheckpoint,
    CommitmentRecord,
    FocusRecord,
    HypothesisRecord,
    MTPDocument,
    ResourceCeiling,
)

now = datetime.now(UTC)


def test_version_constant() -> None:
    from schema.identity import models
    assert models is not None


def test_resource_ceiling_valid() -> None:
    rc = ResourceCeiling(max_tokens_per_run=100, max_duration_seconds=60, max_mcp_reads_per_run=10)
    assert rc.max_tokens_per_run == 100


def test_acap_definition_valid() -> None:
    acap = ACAPDefinition(
        acap_id="acap-1",
        agent_type="exploratory",
        permitted_tools=["search"],
        permitted_mcp_connections=[],
        permitted_event_types=["AgentSignal"],
        forbidden_targets=[],
        resource_ceiling=ResourceCeiling(
            max_tokens_per_run=100, max_duration_seconds=60, max_mcp_reads_per_run=10
        ),
    )
    assert acap.acap_id == "acap-1"
    assert acap.agent_type == "exploratory"


def test_acap_definition_invalid_agent_type() -> None:
    with pytest.raises(ValidationError):
        ACAPDefinition(
            acap_id="acap-1",
            agent_type="invalid_type",  # type: ignore[arg-type]
            permitted_tools=["search"],
            permitted_mcp_connections=[],
            permitted_event_types=["AgentSignal"],
            forbidden_targets=[],
            resource_ceiling=ResourceCeiling(
                max_tokens_per_run=100, max_duration_seconds=60, max_mcp_reads_per_run=10
            ),
        )


def test_mtp_document_valid() -> None:
    mtp = MTPDocument(
        mtp_id="mtp-1",
        version="1.0",
        purpose="test purpose",
        constraints=["c1", "c2"],
        intent_description="test intent",
        created_at=now,
        created_by="tester",
    )
    assert mtp.mtp_id == "mtp-1"
    assert len(mtp.constraints) == 2


def test_hypothesis_record_valid() -> None:
    hyp = HypothesisRecord(hypothesis="test", conclusion="confirmed", evidence="test evidence")
    assert hyp.conclusion == "confirmed"


def test_hypothesis_record_invalid_conclusion() -> None:
    with pytest.raises(ValidationError):
        HypothesisRecord(hypothesis="test", conclusion="maybe", evidence="test")  # type: ignore[arg-type]


def test_cognitive_checkpoint_serialisation() -> None:
    cp = CognitiveCheckpoint(
        current_best_understanding="understanding",
        recommended_next_action="next action",
        checkpoint_at=now,
    )
    assert cp.current_best_understanding == "understanding"


def test_cognitive_checkpoint_json_roundtrip() -> None:
    cp = CognitiveCheckpoint(
        hypotheses_investigated=[HypothesisRecord(
            hypothesis="test", conclusion="pending", evidence="some evidence"
        )],
        current_best_understanding="understanding",
        recommended_next_action="next action",
        checkpoint_at=now,
    )
    data = cp.model_dump(mode="json")
    cp2 = CognitiveCheckpoint.model_validate(data)
    assert cp2.current_best_understanding == "understanding"
    assert len(cp2.hypotheses_investigated) == 1


def test_cognitive_checkpoint_defaults() -> None:
    cp = CognitiveCheckpoint(
        current_best_understanding="u",
        recommended_next_action="n",
        checkpoint_at=now,
    )
    assert cp.hypotheses_investigated == []
    assert cp.plan is None


def test_focus_record_valid() -> None:
    focus = FocusRecord(
        focus_id="focus-001",
        domain="performance",
        description="Investigate memory leaks in auth module",
        status="pending",
        created_at=now,
        priority_signal=0.7,
    )
    assert focus.focus_id == "focus-001"
    assert focus.description == "Investigate memory leaks in auth module"


def test_focus_record_no_checkpoint() -> None:
    focus = FocusRecord(
        focus_id="focus-002",
        domain="security",
        description="Audit encryption",
        status="pending",
        created_at=now,
        priority_signal=0.5,
    )
    assert focus.checkpoint is None


def test_focus_record_invalid_status() -> None:
    with pytest.raises(ValidationError):
        FocusRecord(
            focus_id="x",
            domain="d",
            description="desc",
            status="invalid_status",  # type: ignore[arg-type]
            created_at=now,
            priority_signal=0.0,
        )


def test_focus_record_priority_signal_boundaries() -> None:
    low = FocusRecord(
        focus_id="x", domain="d", description="desc",
        status="pending", created_at=now, priority_signal=0.0,
    )
    high = FocusRecord(
        focus_id="y", domain="d", description="desc",
        status="pending", created_at=now, priority_signal=1.0,
    )
    assert low.priority_signal == 0.0
    assert high.priority_signal == 1.0


def test_focus_record_priority_signal_out_of_range() -> None:
    with pytest.raises(ValidationError):
        FocusRecord(
            focus_id="x", domain="d", description="desc",
            status="pending", created_at=now,
            priority_signal=1.5,  # type: ignore[arg-type]
        )


def test_commitment_record_valid() -> None:
    c = CommitmentRecord(
        commitment_id="com-001",
        status="pending",
        created_at=now,
        domain="performance",
        priority_signal=0.8,
    )
    assert c.commitment_id == "com-001"
    assert c.status == "pending"


def test_commitment_record_no_checkpoint() -> None:
    c = CommitmentRecord(
        commitment_id="com-002",
        status="active",
        created_at=now,
        domain="security",
        priority_signal=0.5,
    )
    assert c.checkpoint is None
    assert c.implementation_state == "to_do"


def test_commitment_record_invalid_status() -> None:
    with pytest.raises(ValidationError):
        CommitmentRecord(
            commitment_id="x",
            status="invalid",  # type: ignore[arg-type]
            created_at=now,
            domain="d",
            priority_signal=0.0,
        )


def test_commitment_record_priority_signal_boundaries() -> None:
    low = CommitmentRecord(
        commitment_id="x", status="pending", created_at=now, domain="d", priority_signal=0.0,
    )
    high = CommitmentRecord(
        commitment_id="y", status="pending", created_at=now, domain="d", priority_signal=1.0,
    )
    assert low.priority_signal == 0.0
    assert high.priority_signal == 1.0


def test_commitment_record_priority_signal_out_of_range() -> None:
    with pytest.raises(ValidationError):
        CommitmentRecord(
            commitment_id="x", status="pending", created_at=now, domain="d",
            priority_signal=1.5,  # type: ignore[arg-type]
        )


def test_commitment_record_approval_statuses() -> None:
    for status in ("pending_approval", "approved", "rejected", "deferred"):
        c = CommitmentRecord(
            commitment_id="x", status=status,  # type: ignore[arg-type]
            created_at=now, domain="d", priority_signal=0.5,
        )
        assert c.status == status
