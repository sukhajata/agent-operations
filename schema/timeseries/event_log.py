"""Event log dataclasses for ArcadeDB TimeSeries types.

Defines the five event types used in the Agent Operations event log:
- AgentSignal: Exploratory agent observations
- AgentAction: Agent tool executions and operations
- AgentFinding: Verification and objective agent conclusions
- AgentCheckpoint: Objective agent decision boundaries
- ObjectiveTransition: Objective lifecycle state changes

Each event type carries: event_type, ts, agent_id, objective_id, mtp_version, payload.
AgentSignal and AgentFinding additionally carry confidence and novelty_flag.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AgentSignal:
    """Exploratory agent observation emitted to the event log.

    Retention: 7 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    objective_id: str
    mtp_version: str
    payload: dict[str, Any]
    confidence: float
    novelty_flag: bool

    def __post_init__(self) -> None:
        if self.event_type != "AgentSignal":
            raise ValueError(f"event_type must be 'AgentSignal', got '{self.event_type}'")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass
class AgentAction:
    """Agent tool execution or operational event.

    Retention: 30 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    objective_id: str
    mtp_version: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.event_type != "AgentAction":
            raise ValueError(f"event_type must be 'AgentAction', got '{self.event_type}'")


@dataclass
class AgentFinding:
    """Verification or objective agent conclusion.

    Retention: 90 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    objective_id: str
    mtp_version: str
    payload: dict[str, Any]
    confidence: float
    novelty_flag: bool

    def __post_init__(self) -> None:
        if self.event_type != "AgentFinding":
            raise ValueError(f"event_type must be 'AgentFinding', got '{self.event_type}'")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")


@dataclass
class AgentCheckpoint:
    """Objective agent decision boundary checkpoint.

    Retention: 180 days.
    """

    event_type: str
    ts: datetime
    agent_id: str
    objective_id: str
    mtp_version: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.event_type != "AgentCheckpoint":
            raise ValueError(f"event_type must be 'AgentCheckpoint', got '{self.event_type}'")


@dataclass
class ObjectiveTransition:
    """Objective lifecycle state change event.

    Retention: indefinite (0 days).
    """

    event_type: str
    ts: datetime
    agent_id: str
    objective_id: str
    mtp_version: str
    payload: dict[str, Any]

    def __post_init__(self) -> None:
        if self.event_type != "ObjectiveTransition":
            raise ValueError(
                f"event_type must be 'ObjectiveTransition', got '{self.event_type}'"
            )
