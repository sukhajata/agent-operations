"""Knowledge promotion classifier.

Decides how epistemic content from completed commitments should be
promoted from the event log into the knowledge graph.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from schema.timeseries.event_log import AgentFinding, AgentSignal

PromotionAction = Literal[
    "discard",
    "promote_durable",
    "promote_medium",
    "reinforce",
    "return_to_log",
]

NEGATIVE_KNOWLEDGE_EDGE = "NEGATIVE_KNOWLEDGE"

# Terms that indicate operational state (should be discarded, not promoted)
_OPERATIONAL_TERMS = frozenset({
    "checkpoint", "intermediate", "retry", "attempt", "progress",
    "partial", "aborted", "timed_out", "retrying",
})


@dataclass
class PromotionDecision:
    """Result of classifying a signal/finding for knowledge graph promotion."""

    action: PromotionAction
    node_type: str | None = None
    confidence: float | None = None
    rationale: str = ""
    node_id: str | None = None


def classify_for_promotion(
    event: AgentSignal | AgentFinding,
    existing_nodes: list[dict[str, object]] | None = None,
) -> PromotionDecision:
    """Classify an event for knowledge graph promotion.

    Args:
        event: An AgentSignal or AgentFinding from a completed commitment.
        existing_nodes: Optional list of existing graph nodes to check for
            semantic overlap. Each node should have node_id, node_type,
            and confidence fields.

    Returns:
        A PromotionDecision indicating what to do with this knowledge.
    """
    existing_nodes = existing_nodes or []
    claim = event.claim.lower() if event.claim else ""
    reasoning = event.reasoning.lower() if hasattr(event, "reasoning") else ""

    # Empty or near-empty claims are not actionable knowledge
    if len(claim.strip()) < 3:
        return PromotionDecision(
            action="discard",
            rationale="Empty or near-empty claim — not actionable knowledge",
        )

    # Check for negative knowledge (hypothesis rejected)
    is_contradicted_finding = isinstance(event, AgentFinding) and event.verdict == "contradicted"
    if (
        is_contradicted_finding
        or "disproved" in reasoning
        or "contradicted" in claim
        or "rejected" in reasoning
    ):
        return PromotionDecision(
            action="promote_durable",
            node_type="InvestigationFinding",
            confidence=event.confidence,
            rationale="Contradicted or rejected hypothesis — negative knowledge edge",
        )

    # Check for operational state (discard)
    if any(term in claim for term in _OPERATIONAL_TERMS):
        return PromotionDecision(
            action="discard",
            rationale="Operational state — not durable knowledge",
        )

    # Check for structural discoveries
    if "structure" in claim or "architecture" in claim or "api" in claim:
        return PromotionDecision(
            action="promote_durable",
            node_type="ProductStructure",
            confidence=event.confidence,
            rationale="Structural discovery about the product",
        )

    # Check for existing node reinforcement
    for node in existing_nodes:
        node_type = str(node.get("node_type", ""))
        node_id = str(node.get("node_id", ""))
        if node_type and _claims_overlap(claim, str(node.get("claim", ""))):
            return PromotionDecision(
                action="reinforce",
                node_type=node_type,
                node_id=node_id,
                confidence=event.confidence,
                rationale=f"Reinforces existing node {node_id}",
            )

    # Low confidence — leave in event log
    if event.confidence < 0.5:
        return PromotionDecision(
            action="return_to_log",
            rationale=f"Confidence {event.confidence:.2f} below threshold — not promoted",
        )

    # Default: medium durability (customer themes, competitor signals, etc.)
    if "customer" in claim or "user" in claim:
        node_type = "CustomerTheme"
    else:
        node_type = "InvestigationFinding"
    return PromotionDecision(
        action="promote_medium",
        node_type=node_type,
        confidence=event.confidence,
        rationale="Default medium-durability promotion",
    )


def _claims_overlap(claim: str, existing_claim: str) -> bool:
    """Simple word overlap check between two claims."""
    if not existing_claim:
        return False
    claim_words = set(claim.lower().split())
    existing_words = set(existing_claim.lower().split())
    if not claim_words or not existing_words:
        return False
    overlap = claim_words & existing_words
    return len(overlap) / min(len(claim_words), len(existing_words)) > 0.4
