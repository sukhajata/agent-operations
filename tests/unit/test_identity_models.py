import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from schema.identity import VERSION
from schema.identity.models import (
    ACAPDefinition,
    CognitiveCheckpoint,
    HypothesisRecord,
    MTPDocument,
    ObjectiveRecord,
    ResourceCeiling,
)


def test_version_constant() -> None:
    assert VERSION == "1.0"


def test_resource_ceiling_valid() -> None:
    rc = ResourceCeiling(
        max_tokens_per_run=100000,
        max_duration_seconds=300,
        max_mcp_reads_per_run=10,
    )
    assert rc.max_tokens_per_run == 100000
    assert rc.max_duration_seconds == 300
    assert rc.max_mcp_reads_per_run == 10


def test_acap_definition_valid() -> None:
    acap = ACAPDefinition(
        acap_id="acap-exploratory",
        agent_type="exploratory",
        permitted_tools=["web_search"],
        permitted_mcp_connections=[],
        permitted_event_types=["AgentSignal", "AgentAction"],
        forbidden_targets=["objective_registry"],
        resource_ceiling=ResourceCeiling(
            max_tokens_per_run=50000,
            max_duration_seconds=120,
            max_mcp_reads_per_run=5,
        ),
    )
    assert acap.acap_id == "acap-exploratory"
    assert acap.agent_type == "exploratory"
    assert acap.permitted_tools == ["web_search"]
    assert acap.resource_ceiling.max_tokens_per_run == 50000


def test_acap_definition_invalid_agent_type() -> None:
    with pytest.raises(ValidationError):
        ACAPDefinition(
            acap_id="x",
            agent_type="invalid",  # type: ignore[arg-type]
            permitted_tools=[],
            permitted_mcp_connections=[],
            permitted_event_types=[],
            forbidden_targets=[],
            resource_ceiling=ResourceCeiling(
                max_tokens_per_run=1, max_duration_seconds=1, max_mcp_reads_per_run=1
            ),
        )


def test_mtp_document_valid() -> None:
    now = datetime.now(UTC)
    mtp = MTPDocument(
        mtp_id="mtp-v1",
        version="1.0",
        purpose="Continuously improve software quality and reliability",
        constraints=["Never expose customer data"],
        intent_description="We exist to make software that works well and gets better over time.",
        created_at=now,
        created_by="admin",
    )
    assert mtp.mtp_id == "mtp-v1"
    assert mtp.version == "1.0"
    assert len(mtp.constraints) == 1


def test_hypothesis_record_valid() -> None:
    hr = HypothesisRecord(
        hypothesis="The latency issue is caused by the cache layer",
        conclusion="confirmed",
        evidence="Removing the cache reduced latency by 40ms",
    )
    assert hr.hypothesis == "The latency issue is caused by the cache layer"
    assert hr.conclusion == "confirmed"


def test_hypothesis_record_invalid_conclusion() -> None:
    with pytest.raises(ValidationError):
        HypothesisRecord(
            hypothesis="test",
            conclusion="maybe",  # type: ignore[arg-type]
            evidence="some evidence",
        )


def test_cognitive_checkpoint_serialisation() -> None:
    now = datetime.now(UTC)
    checkpoint = CognitiveCheckpoint(
        hypotheses_investigated=[
            HypothesisRecord(
                hypothesis="Cache layer is the bottleneck",
                conclusion="confirmed",
                evidence="Metrics show cache hit ratio dropped to 20%",
            ),
            HypothesisRecord(
                hypothesis="Network latency is the cause",
                conclusion="rejected",
                evidence="Network latency is stable at 2ms",
            ),
        ],
        current_best_understanding="The cache hit ratio degradation is the primary cause",
        recommended_next_action="Investigate cache eviction policy",
        checkpoint_at=now,
    )

    serialised = checkpoint.model_dump(mode="json")
    assert serialised["current_best_understanding"] == (
        "The cache hit ratio degradation is the primary cause"
    )
    assert isinstance(serialised["checkpoint_at"], str)

    deserialised = CognitiveCheckpoint.model_validate(serialised)
    assert deserialised.current_best_understanding == checkpoint.current_best_understanding
    assert deserialised.recommended_next_action == checkpoint.recommended_next_action
    assert len(deserialised.hypotheses_investigated) == 2
    assert deserialised.hypotheses_investigated[0].conclusion == "confirmed"
    assert deserialised.hypotheses_investigated[1].conclusion == "rejected"


def test_cognitive_checkpoint_json_roundtrip() -> None:
    now = datetime.now(UTC)
    checkpoint = CognitiveCheckpoint(
        hypotheses_investigated=[
            HypothesisRecord(
                hypothesis="H1",
                conclusion="pending",
                evidence="Insufficient data",
            ),
        ],
        current_best_understanding="Unknown",
        recommended_next_action="Gather more data",
        checkpoint_at=now,
    )

    json_str = checkpoint.model_dump_json()
    data = json.loads(json_str)
    recreated = CognitiveCheckpoint.model_validate(data)

    assert recreated.current_best_understanding == "Unknown"
    assert len(recreated.hypotheses_investigated) == 1


def test_cognitive_checkpoint_defaults() -> None:
    now = datetime.now(UTC)
    checkpoint = CognitiveCheckpoint(
        current_best_understanding="Nothing yet",
        recommended_next_action="Start investigation",
        checkpoint_at=now,
    )
    assert checkpoint.hypotheses_investigated == []


def test_objective_record_valid() -> None:
    now = datetime.now(UTC)
    checkpoint = CognitiveCheckpoint(
        hypotheses_investigated=[],
        current_best_understanding="Starting investigation",
        recommended_next_action="Query event log",
        checkpoint_at=now,
    )
    obj = ObjectiveRecord(
        objective_id="obj-001",
        status="active",
        created_at=now,
        domain="competitive_intelligence",
        priority_signal=0.8,
        checkpoint=checkpoint,
        assigned_agent_id="agent-42",
    )
    assert obj.objective_id == "obj-001"
    assert obj.status == "active"
    assert obj.priority_signal == 0.8
    assert obj.checkpoint is not None


def test_objective_record_no_checkpoint() -> None:
    now = datetime.now(UTC)
    obj = ObjectiveRecord(
        objective_id="obj-002",
        status="pending",
        created_at=now,
        domain="cost_optimisation",
        priority_signal=0.3,
    )
    assert obj.checkpoint is None
    assert obj.assigned_agent_id is None


def test_objective_record_invalid_status() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ObjectiveRecord(
            objective_id="x",
            status="unknown",  # type: ignore[arg-type]
            created_at=now,
            domain="test",
            priority_signal=0.5,
        )


def test_objective_record_priority_signal_boundaries() -> None:
    now = datetime.now(UTC)
    obj_min = ObjectiveRecord(
        objective_id="x", status="pending", created_at=now, domain="d", priority_signal=0.0
    )
    assert obj_min.priority_signal == 0.0

    obj_max = ObjectiveRecord(
        objective_id="y", status="pending", created_at=now, domain="d", priority_signal=1.0
    )
    assert obj_max.priority_signal == 1.0


def test_objective_record_priority_signal_out_of_range() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        ObjectiveRecord(
            objective_id="x",
            status="pending",
            created_at=now,
            domain="test",
            priority_signal=1.5,
        )


def test_objective_record_implementation_defaults() -> None:
    now = datetime.now(UTC)
    obj = ObjectiveRecord(
        objective_id="obj-003",
        status="complete",
        created_at=now,
        domain="test",
        priority_signal=0.5,
    )
    assert obj.implementation_status == "none"
    assert obj.implementation_state == "to_do"
