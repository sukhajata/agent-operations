from datetime import UTC, datetime, timedelta

import pytest

from schema.graph.node_types import (
    DECAY_RATES,
    REVALIDATION_THRESHOLD,
    CompetitorCapability,
    CustomerSignal,
    CustomerTheme,
    DecisionRecord,
    GraphNode,
    InvestigationFinding,
    ProductStructure,
    calculate_current_confidence,
)


def _make_node(
    node_type: str,
    confidence: float = 0.9,
    last_reinforced: datetime | None = None,
) -> GraphNode:
    if last_reinforced is None:
        last_reinforced = datetime.now(UTC)
    return GraphNode(
        node_id="test-1",
        node_type=node_type,
        confidence=confidence,
        initial_confidence=confidence,
        decay_rate=DECAY_RATES[node_type],
        last_reinforced=last_reinforced,
        revalidation_required=False,
    )


def test_product_structure_decay_rate() -> None:
    assert DECAY_RATES["ProductStructure"] == 0.001


def test_decision_record_decay_rate() -> None:
    assert DECAY_RATES["DecisionRecord"] == 0.0001


def test_investigation_finding_decay_rate() -> None:
    assert DECAY_RATES["InvestigationFinding"] == 0.005


def test_competitor_capability_decay_rate() -> None:
    assert DECAY_RATES["CompetitorCapability"] == 0.01


def test_customer_theme_decay_rate() -> None:
    assert DECAY_RATES["CustomerTheme"] == 0.008


def test_customer_signal_decay_rate() -> None:
    assert DECAY_RATES["CustomerSignal"] == 0.1


def test_product_structure_slower_than_customer_signal() -> None:
    assert DECAY_RATES["ProductStructure"] < DECAY_RATES["CustomerSignal"]


def test_calculate_confidence_no_decay_at_zero_days() -> None:
    now = datetime.now(UTC)
    node = _make_node("ProductStructure", confidence=0.9, last_reinforced=now)
    result = calculate_current_confidence(node, now)
    assert result == pytest.approx(0.9)


def test_calculate_confidence_1_day_product_structure() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "ProductStructure",
        confidence=0.9,
        last_reinforced=now - timedelta(days=1),
    )
    result = calculate_current_confidence(node, now)
    expected = 0.9 * (1.0 - 0.001) ** 1
    assert result == pytest.approx(expected)


def test_calculate_confidence_30_days_product_structure() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "ProductStructure",
        confidence=0.9,
        last_reinforced=now - timedelta(days=30),
    )
    result = calculate_current_confidence(node, now)
    expected = 0.9 * (1.0 - 0.001) ** 30
    assert result == pytest.approx(expected)


def test_calculate_confidence_365_days_product_structure() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "ProductStructure",
        confidence=0.9,
        last_reinforced=now - timedelta(days=365),
    )
    result = calculate_current_confidence(node, now)
    expected = 0.9 * (1.0 - 0.001) ** 365
    assert result == pytest.approx(expected)


def test_calculate_confidence_1_day_customer_signal() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "CustomerSignal",
        confidence=0.9,
        last_reinforced=now - timedelta(days=1),
    )
    result = calculate_current_confidence(node, now)
    expected = 0.9 * (1.0 - 0.1) ** 1
    assert result == pytest.approx(expected)


def test_calculate_confidence_30_days_customer_signal() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "CustomerSignal",
        confidence=0.9,
        last_reinforced=now - timedelta(days=30),
    )
    result = calculate_current_confidence(node, now)
    expected = 0.9 * (1.0 - 0.1) ** 30
    assert result == pytest.approx(expected)


def test_calculate_confidence_365_days_customer_signal() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "CustomerSignal",
        confidence=0.9,
        last_reinforced=now - timedelta(days=365),
    )
    result = calculate_current_confidence(node, now)
    expected = 0.9 * (1.0 - 0.1) ** 365
    assert result == pytest.approx(expected)


def test_revalidation_flagged_below_threshold() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "CustomerSignal",
        confidence=0.5,
        last_reinforced=now - timedelta(days=10),
    )
    result = calculate_current_confidence(node, now)
    assert result < REVALIDATION_THRESHOLD
    assert node.revalidation_required is True


def test_revalidation_not_flagged_above_threshold() -> None:
    now = datetime.now(UTC)
    node = _make_node(
        "ProductStructure",
        confidence=0.9,
        last_reinforced=now - timedelta(days=1),
    )
    result = calculate_current_confidence(node, now)
    assert result > REVALIDATION_THRESHOLD
    assert node.revalidation_required is False


def test_negative_elapsed_days_clamped_to_zero() -> None:
    now = datetime.now(UTC)
    future = now + timedelta(days=1)
    node = _make_node("ProductStructure", confidence=0.9, last_reinforced=future)
    result = calculate_current_confidence(node, now)
    assert result == pytest.approx(0.9)


def test_product_structure_dataclass() -> None:
    now = datetime.now(UTC)
    node = ProductStructure(
        node_id="ps-1",
        node_type="",
        confidence=0.8,
        initial_confidence=0.8,
        decay_rate=0.0,
        last_reinforced=now,
        revalidation_required=False,
    )
    assert node.node_type == "ProductStructure"
    assert node.decay_rate == 0.001


def test_decision_record_dataclass() -> None:
    now = datetime.now(UTC)
    node = DecisionRecord(
        node_id="dr-1",
        node_type="",
        confidence=0.9,
        initial_confidence=0.9,
        decay_rate=0.0,
        last_reinforced=now,
        revalidation_required=False,
    )
    assert node.node_type == "DecisionRecord"
    assert node.decay_rate == 0.0001


def test_investigation_finding_dataclass() -> None:
    now = datetime.now(UTC)
    node = InvestigationFinding(
        node_id="if-1",
        node_type="",
        confidence=0.7,
        initial_confidence=0.7,
        decay_rate=0.0,
        last_reinforced=now,
        revalidation_required=False,
    )
    assert node.node_type == "InvestigationFinding"
    assert node.decay_rate == 0.005


def test_competitor_capability_dataclass() -> None:
    now = datetime.now(UTC)
    node = CompetitorCapability(
        node_id="cc-1",
        node_type="",
        confidence=0.6,
        initial_confidence=0.6,
        decay_rate=0.0,
        last_reinforced=now,
        revalidation_required=False,
    )
    assert node.node_type == "CompetitorCapability"
    assert node.decay_rate == 0.01


def test_customer_theme_dataclass() -> None:
    now = datetime.now(UTC)
    node = CustomerTheme(
        node_id="ct-1",
        node_type="",
        confidence=0.75,
        initial_confidence=0.75,
        decay_rate=0.0,
        last_reinforced=now,
        revalidation_required=False,
    )
    assert node.node_type == "CustomerTheme"
    assert node.decay_rate == 0.008


def test_customer_signal_dataclass() -> None:
    now = datetime.now(UTC)
    node = CustomerSignal(
        node_id="cs-1",
        node_type="",
        confidence=0.5,
        initial_confidence=0.5,
        decay_rate=0.0,
        last_reinforced=now,
        revalidation_required=False,
    )
    assert node.node_type == "CustomerSignal"
    assert node.decay_rate == 0.1


def test_invalid_node_type() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="node_type must be one of"):
        GraphNode(
            node_id="x-1",
            node_type="InvalidType",
            confidence=0.5,
            initial_confidence=0.5,
            decay_rate=0.01,
            last_reinforced=now,
            revalidation_required=False,
        )


def test_invalid_confidence_too_high() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="confidence must be in"):
        GraphNode(
            node_id="x-1",
            node_type="ProductStructure",
            confidence=1.5,
            initial_confidence=0.9,
            decay_rate=0.001,
            last_reinforced=now,
            revalidation_required=False,
        )


def test_invalid_confidence_too_low() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="confidence must be in"):
        GraphNode(
            node_id="x-1",
            node_type="ProductStructure",
            confidence=-0.1,
            initial_confidence=0.9,
            decay_rate=0.001,
            last_reinforced=now,
            revalidation_required=False,
        )


def test_invalid_initial_confidence() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="initial_confidence must be in"):
        GraphNode(
            node_id="x-1",
            node_type="ProductStructure",
            confidence=0.5,
            initial_confidence=2.0,
            decay_rate=0.001,
            last_reinforced=now,
            revalidation_required=False,
        )
