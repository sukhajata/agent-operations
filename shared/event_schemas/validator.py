"""Event schema validator — canonical validation for all events.

Every event emitted by any agent must pass through validate_event or
emit_validated. Direct writes to ArcadeDB bypassing validation are
an ACAP violation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from schema.timeseries.event_log import (
    AgentAction,
    AgentCheckpoint,
    AgentSignal,
    CommitmentTransition,
)

if TYPE_CHECKING:
    from shared.arcadedb.client import ArcadeDBClient

VALID_EVENT_TYPES = frozenset({
    "AgentSignal",
    "AgentAction",
    "AgentCheckpoint",
    "CommitmentTransition",
})

REQUIRED_FIELDS = frozenset({
    "agent_id",
    "mtp_version",
    "ts",
    "event_type",
})

Event = AgentSignal | AgentAction | AgentCheckpoint | CommitmentTransition

_EVENT_CLASSES: dict[str, type[Event]] = {
    "AgentSignal": AgentSignal,
    "AgentAction": AgentAction,
    "AgentCheckpoint": AgentCheckpoint,
    "CommitmentTransition": CommitmentTransition,
}

_REMOVED_EVENT_TYPES = frozenset({
    "AgentFinding",
    "ObjectiveTransition",
})


class EventSchemaError(ValueError):
    """Raised when an event fails schema validation."""


def check_required_fields(event: dict[str, Any]) -> None:
    """Verify all required fields are present and non-empty.

    Fields checked: agent_id, mtp_version, ts, event_type.

    Raises EventSchemaError if any required field is missing or empty.
    """
    missing = [
        field for field in REQUIRED_FIELDS
        if field not in event or not event[field]
    ]
    if missing:
        raise EventSchemaError(
            f"Missing or empty required fields: {', '.join(sorted(missing))}"
        )


def validate_event(event: dict[str, Any]) -> Event:
    """Validate and parse an event dict into the correct typed dataclass.

    Args:
        event: Raw event dict from ArcadeDB or agent emit

    Returns:
        The validated, typed event instance

    Raises:
        EventSchemaError: If validation fails
    """
    check_required_fields(event)

    event_type = event["event_type"]

    if event_type in _REMOVED_EVENT_TYPES:
        raise EventSchemaError(
            f"Event type '{event_type}' has been removed. "
            f"Use 'AgentSignal' with stage='finding' instead of 'AgentFinding', "
            f"or 'CommitmentTransition' instead of 'ObjectiveTransition'."
        )

    if event_type not in VALID_EVENT_TYPES:
        raise EventSchemaError(
            f"Unknown event_type '{event_type}'. "
            f"Must be one of: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )

    cls = _EVENT_CLASSES[event_type]
    try:
        return cls(**event)
    except (TypeError, ValueError) as e:
        raise EventSchemaError(
            f"Failed to parse {event_type}: {e}"
        ) from e


async def emit_validated(
    event: dict[str, Any],
    client: ArcadeDBClient,
) -> None:
    """Validate an event dict and emit it to ArcadeDB.

    This is the single entry point agents must use to emit events.
    Direct writes bypassing this function are an ACAP violation.

    Args:
        event: Raw event dict
        client: ArcadeDB client instance
    """
    validated = validate_event(event)
    from shared.arcadedb.timeseries import emit_event  # late import
    await emit_event(client, validated)
