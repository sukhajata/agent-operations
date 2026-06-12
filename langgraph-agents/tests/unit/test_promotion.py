from __future__ import annotations

from datetime import UTC, datetime

from schema.timeseries.event_log import AgentFinding, AgentSignal
from shared.promotion.classifier import classify_for_promotion

SAMPLE_DATETIME = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)


def _mk_signal(**overrides: object) -> AgentSignal:
    kwargs: dict[str, object] = {
        "event_type": "AgentSignal",
        "ts": SAMPLE_DATETIME,
        "agent_id": "a1",
        "mtp_version": "1.0",
        "claim": "test claim",
        "domain": "performance",
        "confidence": 0.8,
        "reasoning": "test reasoning",
        "sources": [],
        "focus_id": None,
        "novelty_flag": True,
    }
    kwargs.update(overrides)
    return AgentSignal(**kwargs)  # type: ignore[arg-type]


def _mk_finding(**overrides: object) -> AgentFinding:
    kwargs: dict[str, object] = {
        "event_type": "AgentFinding",
        "ts": SAMPLE_DATETIME,
        "agent_id": "v1",
        "mtp_version": "1.0",
        "claim": "confirmed claim",
        "domain": "performance",
        "confidence": 0.9,
        "reasoning": "verified",
        "sources": [],
        "focus_id": None,
        "verdict": "confirmed",
        "originating_signal_ts": SAMPLE_DATETIME,
    }
    kwargs.update(overrides)
    return AgentFinding(**kwargs)  # type: ignore[arg-type]


# --- discard ---


def test_discards_operational_state() -> None:
    signal = _mk_signal(claim="intermediate checkpoint update")
    result = classify_for_promotion(signal)
    assert result.action == "discard"


def test_discards_retry() -> None:
    signal = _mk_signal(claim="retry attempt 3 failed")
    result = classify_for_promotion(signal)
    assert result.action == "discard"


# --- promote_durable: negative knowledge ---


def test_promotes_rejected_hypothesis() -> None:
    signal = _mk_signal(reasoning="this was disproved by further analysis")
    result = classify_for_promotion(signal)
    assert result.action == "promote_durable"
    assert result.node_type == "InvestigationFinding"


def test_promotes_contradicted_from_finding() -> None:
    finding = _mk_finding(verdict="contradicted", reasoning="disproved by evidence")
    result = classify_for_promotion(finding)
    assert result.action == "promote_durable"


# --- promote_durable: structural ---


def test_promotes_architectural_discovery() -> None:
    signal = _mk_signal(claim="The API architecture should be restructured")
    result = classify_for_promotion(signal)
    assert result.action == "promote_durable"
    assert result.node_type == "ProductStructure"


# --- reinforce ---


def test_reinforces_existing_node() -> None:
    signal = _mk_signal(claim="memory leak in auth module")
    existing = [{
        "node_id": "n1",
        "node_type": "InvestigationFinding",
        "claim": "auth module has memory leak",
    }]
    result = classify_for_promotion(signal, existing)
    assert result.action == "reinforce"
    assert result.node_id == "n1"


def test_reinforce_requires_overlap() -> None:
    signal = _mk_signal(claim="memory leak in auth module")
    existing = [{
        "node_id": "n1",
        "node_type": "InvestigationFinding",
        "claim": "unrelated payment bug",
    }]
    result = classify_for_promotion(signal, existing)
    assert result.action != "reinforce"


# --- return_to_log ---


def test_returns_low_confidence_to_log() -> None:
    signal = _mk_signal(confidence=0.3, claim="uncertain observation")
    result = classify_for_promotion(signal)
    assert result.action == "return_to_log"


# --- promote_medium ---


def test_promotes_medium_customer_theme() -> None:
    signal = _mk_signal(claim="customer reports frequent timeout errors")
    result = classify_for_promotion(signal)
    assert result.action == "promote_medium"
    assert result.node_type == "CustomerTheme"


def test_promotes_medium_default() -> None:
    signal = _mk_signal(claim="competitor launched a new feature", confidence=0.7)
    result = classify_for_promotion(signal)
    assert result.action == "promote_medium"
    assert result.node_type == "InvestigationFinding"


# --- edge cases ---


def test_empty_claim() -> None:
    signal = _mk_signal(claim="")
    result = classify_for_promotion(signal)
    assert result.action in ("return_to_log", "discard")


def test_none_existing_nodes() -> None:
    signal = _mk_signal(claim="some valid discovery", confidence=0.8)
    result = classify_for_promotion(signal, existing_nodes=None)
    assert result.action == "promote_medium"
