"""ArcadeDB identity store and objective registry operations.

Provides functions to load MTP documents, ACAP definitions, and manage
objective records including checkpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from schema.identity.models import (
    ACAPDefinition,
    CognitiveCheckpoint,
    MTPDocument,
    ObjectiveRecord,
)

from .client import ArcadeDBClient


async def load_mtp(client: ArcadeDBClient) -> MTPDocument | None:
    """Load the latest MTP document from the identity store.

    Args:
        client: ArcadeDB client instance

    Returns:
        The latest MTPDocument, or None if none exists
    """
    records = await client.execute_query(
        "SELECT FROM MTPDocument ORDER BY version DESC LIMIT 1"
    )
    if not records:
        return None
    return MTPDocument.model_validate(records[0])


async def load_acap(
    client: ArcadeDBClient, agent_type: str
) -> ACAPDefinition | None:
    """Load the ACAP definition for a given agent type.

    Args:
        client: ArcadeDB client instance
        agent_type: One of exploratory, verification, objective, orchestration

    Returns:
        The ACAPDefinition if found, None otherwise
    """
    records = await client.execute_query(
        "SELECT FROM ACAPDefinition WHERE agent_type = :agent_type LIMIT 1",
        {"agent_type": agent_type},
    )
    if not records:
        return None
    return ACAPDefinition.model_validate(records[0])


async def get_objective(
    client: ArcadeDBClient, objective_id: str
) -> ObjectiveRecord | None:
    """Retrieve an objective record by ID.

    Args:
        client: ArcadeDB client instance
        objective_id: The objective identifier

    Returns:
        The ObjectiveRecord if found, None otherwise
    """
    records = await client.execute_query(
        "SELECT FROM ObjectiveRecord WHERE objective_id = :objective_id LIMIT 1",
        {"objective_id": objective_id},
    )
    if not records:
        return None
    return ObjectiveRecord.model_validate(records[0])


async def create_objective(
    client: ArcadeDBClient, objective: ObjectiveRecord
) -> str:
    """Create a new objective record in the registry.

    Args:
        client: ArcadeDB client instance
        objective: The objective record to create

    Returns:
        The objective_id of the created record
    """
    params = _objective_params(objective)
    columns = ", ".join(f"{k} = :{k}" for k in params)
    await client.execute_command(
        f"INSERT INTO ObjectiveRecord SET {columns}", params
    )
    return objective.objective_id


async def update_objective(
    client: ArcadeDBClient,
    objective_id: str,
    updates: dict[str, Any],
) -> None:
    """Update fields on an objective record.

    Args:
        client: ArcadeDB client instance
        objective_id: The objective to update
        updates: Dict of field names to new values
    """
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["objective_id"] = objective_id
    await client.execute_command(
        f"UPDATE ObjectiveRecord SET {set_clause} WHERE objective_id = :objective_id",
        updates,
    )


async def write_checkpoint(
    client: ArcadeDBClient,
    objective_id: str,
    checkpoint: CognitiveCheckpoint,
) -> None:
    """Write a cognitive checkpoint to an objective record.

    Args:
        client: ArcadeDB client instance
        objective_id: The objective to update
        checkpoint: The cognitive checkpoint to write
    """
    params: dict[str, Any] = {
        "objective_id": objective_id,
        "checkpoint": checkpoint.model_dump(mode="json"),
        "checkpoint_at": datetime.now(UTC).isoformat(),
    }
    await client.execute_command(
        "UPDATE ObjectiveRecord SET checkpoint = :checkpoint, "
        "checkpoint_at = :checkpoint_at "
        "WHERE objective_id = :objective_id",
        params,
    )


def _objective_params(obj: ObjectiveRecord) -> dict[str, Any]:
    """Convert an ObjectiveRecord to ArcadeDB parameter map."""
    params: dict[str, Any] = {
        "objective_id": obj.objective_id,
        "status": obj.status,
        "created_at": obj.created_at.isoformat(),
        "domain": obj.domain,
        "priority_signal": obj.priority_signal,
        "assigned_agent_id": obj.assigned_agent_id,
        "implementation_status": obj.implementation_status,
        "implementation_state": obj.implementation_state,
    }
    if obj.checkpoint is not None:
        params["checkpoint"] = obj.checkpoint.model_dump(mode="json")
    return params
