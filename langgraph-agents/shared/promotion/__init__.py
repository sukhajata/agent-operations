"""Knowledge promotion — promotes signal content from the event log
into the knowledge graph at commitment closure.

This module is called by the orchestration agent, not by individual
working agents.
"""

from .classifier import (
    NEGATIVE_KNOWLEDGE_EDGE,
    PromotionAction,
    PromotionDecision,
    classify_for_promotion,
)

__all__ = [
    "classify_for_promotion",
    "PromotionDecision",
    "PromotionAction",
    "NEGATIVE_KNOWLEDGE_EDGE",
]
