"""Event log dataclasses for ArcadeDB TimeSeries types.

Defines the event types used in the Agent Operations event log:
- AgentSignal: Exploratory agent observations (7-day retention)
- AgentFinding: Verification agent conclusions with verdict (90-day retention)
- AgentAction: Agent tool executions, operations, and worker lifecycle events
- AgentCheckpoint: Agent decision boundaries
- CommitmentTransition: Commitment lifecycle state changes

Each event type carries: event_type, ts, agent_id, mtp_version.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal


@dataclass
class AgentSignal:
    """Exploratory agent observation emitted to the event log.

    Retention: 7 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    mtp_version: str
    claim: str
    domain: str
    confidence: float
    reasoning: str
    sources: list[str]
    focus_id: str | None
    novelty_flag: bool

    def __post_init__(self) -> None:
        if self.event_type != "AgentSignal":
            raise ValueError(f"event_type must be 'AgentSignal', got '{self.event_type}'")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass
class AgentFinding:
    """Verification agent conclusion confirming or contradicting an observation.

    Retention: 90 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    mtp_version: str
    claim: str
    domain: str
    confidence: float
    reasoning: str
    sources: list[str]
    focus_id: str | None
    verdict: Literal["confirmed", "contradicted", "inconclusive"]
    originating_signal_ts: datetime

    def __post_init__(self) -> None:
        if self.event_type != "AgentFinding":
            raise ValueError(f"event_type must be 'AgentFinding', got '{self.event_type}'")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass
class AgentAction:
    """Agent tool execution, operation, or worker lifecycle event.

    Use payload.action for the action type (e.g. 'WorkerStarted', 'WorkerCompleted',
    'tool_call', 'query').

    Retention: 30 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    commitment_id: str | None
    mtp_version: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.event_type != "AgentAction":
            raise ValueError(f"event_type must be 'AgentAction', got '{self.event_type}'")


@dataclass
class AgentCheckpoint:
    """Agent decision boundary checkpoint.

    Retention: 180 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    commitment_id: str
    mtp_version: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.event_type != "AgentCheckpoint":
            raise ValueError(f"event_type must be 'AgentCheckpoint', got '{self.event_type}'")


@dataclass
class CommitmentTransition:
    """Commitment lifecycle state change event.

    Retention: indefinite (0 days).
    """

    event_type: str
    ts: datetime
    agent_id: str
    commitment_id: str
    mtp_version: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.event_type != "CommitmentTransition":
            raise ValueError(
                f"event_type must be 'CommitmentTransition', got '{self.event_type}'"
            )
