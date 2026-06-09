"""ArcadeDB TimeSeries operations for the Agent Operations event log.

Provides functions to emit events and poll events with cursor-based
queries for partition pruning.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from schema.timeseries.event_log import (
    AgentAction,
    AgentCheckpoint,
    AgentFinding,
    AgentSignal,
    ObjectiveTransition,
)

from .client import ArcadeDBClient

Event = AgentSignal | AgentAction | AgentFinding | AgentCheckpoint | ObjectiveTransition


def _serialize_params(event: Event) -> dict[str, Any]:
    """Convert event dataclass to ArcadeDB INSERT parameter map."""
    params: dict[str, Any] = {}
    for field_name, value in asdict(event).items():
        if isinstance(value, datetime):
            params[field_name] = value.isoformat()
        else:
            params[field_name] = value
    return params


async def emit_event(client: ArcadeDBClient, event: Event) -> None:
    """Emit an event to the ArcadeDB TimeSeries event log.

    Args:
        client: ArcadeDB client instance
        event: The event to emit (AgentSignal, AgentAction, AgentFinding,
            AgentCheckpoint, or ObjectiveTransition)

    Raises:
        ArcadeDBError: If the insert command fails
    """
    event_type = event.event_type
    params = _serialize_params(event)

    columns = ", ".join(f"{k} = :{k}" for k in params)
    command = f"INSERT INTO {event_type} SET {columns}"

    await client.execute_command(command, params)


async def poll_events(
    client: ArcadeDBClient,
    event_type: str,
    since_ts: datetime,
    agent_id: str | None = None,
    objective_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Poll events from ArcadeDB TimeSeries using cursor-based queries.

    Uses ts > :since_ts filter for partition pruning (no full table scans).

    Args:
        client: ArcadeDB client instance
        event_type: The TimeSeries type name to query
        since_ts: Return only events after this timestamp
        agent_id: Optional filter by agent ID
        objective_id: Optional filter by objective ID
        limit: Maximum number of events to return

    Returns:
        List of event records matching the criteria

    Raises:
        ArcadeDBError: If the query fails
    """
    conditions = ["ts > :since_ts"]
    params = {"since_ts": since_ts.isoformat()}

    if agent_id is not None:
        conditions.append("agent_id = :agent_id")
        params["agent_id"] = agent_id
    if objective_id is not None:
        conditions.append("objective_id = :objective_id")
        params["objective_id"] = objective_id

    where_clause = " AND ".join(conditions)
    query = (
        f"SELECT FROM {event_type} WHERE {where_clause} ORDER BY ts ASC"
    )

    return await client.execute_query(query, params, limit=limit)
