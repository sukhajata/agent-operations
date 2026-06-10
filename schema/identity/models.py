"""Identity store, focus registry, and commitment registry Pydantic v2 models.

Defines the data models for MTP documents, ACAP definitions, focus records,
commitment records, cognitive checkpoints, and hypothesis records.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ResourceCeiling(BaseModel):
    """Resource limits for an agent type."""

    max_tokens_per_run: int
    max_duration_seconds: int
    max_mcp_reads_per_run: int


class ACAPDefinition(BaseModel):
    """Access Control and Action Policy for an agent type."""

    acap_id: str
    agent_type: Literal[
        "exploratory", "verification", "research_plan", "implementation", "orchestration"
    ]
    permitted_tools: list[str] = Field(default_factory=list)
    permitted_mcp_connections: list[str] = Field(default_factory=list)
    permitted_event_types: list[str] = Field(default_factory=list)
    forbidden_targets: list[str] = Field(default_factory=list)
    resource_ceiling: ResourceCeiling


class MTPDocument(BaseModel):
    """Massive Transformative Purpose document."""

    mtp_id: str
    version: str
    purpose: str
    constraints: list[str] = Field(default_factory=list)
    intent_description: str
    created_at: datetime
    created_by: str


class HypothesisRecord(BaseModel):
    """Record of a hypothesis investigated by an agent."""

    hypothesis: str
    conclusion: Literal["confirmed", "rejected", "pending"]
    evidence: str


class CognitiveCheckpoint(BaseModel):
    """Cognitive state checkpoint written at decision boundaries."""

    hypotheses_investigated: list[HypothesisRecord] = Field(default_factory=list)
    current_best_understanding: str
    recommended_next_action: str
    plan: str | None = None
    checkpoint_at: datetime


class FocusRecord(BaseModel):
    """A targeted area of exploration for the colony.

    Focus records define what exploratory agents (focus followers)
    should investigate. They are created by research/plan agents
    and approved by humans before spawning focus-following workers.
    """

    focus_id: str
    domain: str
    description: str
    status: Literal["pending", "active", "stalled", "complete", "escalated"]
    created_at: datetime
    priority_signal: float = Field(ge=0.0, le=1.0)
    checkpoint: CognitiveCheckpoint | None = None
    assigned_agent_id: str | None = None


class CommitmentRecord(BaseModel):
    """Registry record for a commitment to deliver a specific outcome.

    Commitments move through: pending → pending_approval → approved →
    implementation → complete. They can be rejected, deferred, stalled,
    or escalated at any approval gate.
    """

    commitment_id: str
    status: Literal[
        "pending",
        "pending_approval",
        "approved",
        "rejected",
        "deferred",
        "active",
        "stalled",
        "complete",
        "escalated",
    ]
    created_at: datetime
    domain: str
    priority_signal: float = Field(ge=0.0, le=1.0)
    checkpoint: CognitiveCheckpoint | None = None
    assigned_agent_id: str | None = None
    implementation_state: Literal[
        "to_do", "pending", "in_progress", "complete", "failed"
    ] = "to_do"
