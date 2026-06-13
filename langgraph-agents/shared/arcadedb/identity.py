"""ArcadeDB identity store, focus registry, and commitment registry operations.

Provides functions to load MTP documents, ACAP definitions, and manage
focus records and commitment records including checkpoints.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from schema.identity.models import (
    ACAPDefinition,
    CognitiveCheckpoint,
    CommitmentRecord,
    FocusRecord,
    MandateRecord,
    MTPDocument,
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
        agent_type: One of exploratory, verification, orchestration

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


async def get_focus(
    client: ArcadeDBClient, focus_id: str
) -> FocusRecord | None:
    """Retrieve a focus record by ID.

    Args:
        client: ArcadeDB client instance
        focus_id: The focus identifier

    Returns:
        The FocusRecord if found, None otherwise
    """
    records = await client.execute_query(
        "SELECT FROM FocusRecord WHERE focus_id = :focus_id LIMIT 1",
        {"focus_id": focus_id},
    )
    if not records:
        return None
    return FocusRecord.model_validate(records[0])


async def create_focus(
    client: ArcadeDBClient, focus: FocusRecord
) -> str:
    """Create a new focus record in the registry.

    Args:
        client: ArcadeDB client instance
        focus: The focus record to create

    Returns:
        The focus_id of the created record
    """
    params = _focus_params(focus)
    columns = ", ".join(f"{k} = :{k}" for k in params)
    await client.execute_command(
        f"INSERT INTO FocusRecord SET {columns}", params
    )
    return focus.focus_id


async def get_commitment(
    client: ArcadeDBClient, commitment_id: str
) -> CommitmentRecord | None:
    """Retrieve a commitment record by ID.

    Args:
        client: ArcadeDB client instance
        commitment_id: The commitment identifier

    Returns:
        The CommitmentRecord if found, None otherwise
    """
    records = await client.execute_query(
        "SELECT FROM CommitmentRecord WHERE commitment_id = :commitment_id LIMIT 1",
        {"commitment_id": commitment_id},
    )
    if not records:
        return None
    return CommitmentRecord.model_validate(records[0])


async def create_commitment(
    client: ArcadeDBClient, commitment: CommitmentRecord
) -> str:
    """Create a new commitment record in the registry.

    Args:
        client: ArcadeDB client instance
        commitment: The commitment record to create

    Returns:
        The commitment_id of the created record
    """
    params = _commitment_params(commitment)
    columns = ", ".join(f"{k} = :{k}" for k in params)
    await client.execute_command(
        f"INSERT INTO CommitmentRecord SET {columns}", params
    )
    return commitment.commitment_id


async def update_commitment(
    client: ArcadeDBClient,
    commitment_id: str,
    updates: dict[str, Any],
) -> None:
    """Update fields on a commitment record.

    Args:
        client: ArcadeDB client instance
        commitment_id: The commitment to update
        updates: Dict of field names to new values
    """
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["commitment_id"] = commitment_id
    await client.execute_command(
        f"UPDATE CommitmentRecord SET {set_clause} WHERE commitment_id = :commitment_id",
        updates,
    )


async def write_checkpoint(
    client: ArcadeDBClient,
    commitment_id: str,
    checkpoint: CognitiveCheckpoint,
) -> None:
    """Write a cognitive checkpoint to a commitment record.

    Args:
        client: ArcadeDB client instance
        commitment_id: The commitment to update
        checkpoint: The cognitive checkpoint to write
    """
    params: dict[str, Any] = {
        "commitment_id": commitment_id,
        "checkpoint": checkpoint.model_dump(mode="json"),
        "checkpoint_at": datetime.now(UTC).isoformat(),
    }
    await client.execute_command(
        "UPDATE CommitmentRecord SET checkpoint = :checkpoint, "
        "checkpoint_at = :checkpoint_at "
        "WHERE commitment_id = :commitment_id",
        params,
    )


def _focus_params(focus: FocusRecord) -> dict[str, Any]:
    """Convert a FocusRecord to ArcadeDB parameter map."""
    params: dict[str, Any] = {
        "focus_id": focus.focus_id,
        "domain": focus.domain,
        "description": focus.description,
        "status": focus.status,
        "created_at": focus.created_at.isoformat(),
        "priority_signal": focus.priority_signal,
        "assigned_agent_id": focus.assigned_agent_id,
    }
    if focus.checkpoint is not None:
        params["checkpoint"] = focus.checkpoint.model_dump(mode="json")
    return params


def _commitment_params(commitment: CommitmentRecord) -> dict[str, Any]:
    """Convert a CommitmentRecord to ArcadeDB parameter map."""
    params: dict[str, Any] = {
        "commitment_id": commitment.commitment_id,
        "status": commitment.status,
        "created_at": commitment.created_at.isoformat(),
        "domain": commitment.domain,
        "priority_signal": commitment.priority_signal,
        "assigned_agent_id": commitment.assigned_agent_id,
        "implementation_state": commitment.implementation_state,
    }
    if commitment.checkpoint is not None:
        params["checkpoint"] = commitment.checkpoint.model_dump(mode="json")
    return params


async def get_active_mandates(client: ArcadeDBClient) -> list[MandateRecord]:
    """List all active mandates from ArcadeDB."""
    records = await client.execute_query(
        "SELECT FROM MandateRecord WHERE active = true ORDER BY mandate_id ASC"
    )
    return [MandateRecord.model_validate(r) for r in records]


async def get_all_mandates(client: ArcadeDBClient) -> list[MandateRecord]:
    """List all mandates (active and inactive)."""
    records = await client.execute_query(
        "SELECT FROM MandateRecord ORDER BY mandate_id ASC"
    )
    return [MandateRecord.model_validate(r) for r in records]


async def create_mandate(client: ArcadeDBClient, mandate: MandateRecord) -> str:
    """Create a new mandate record."""
    params = {
        "mandate_id": mandate.mandate_id,
        "name": mandate.name,
        "domain": mandate.domain,
        "agent_type": mandate.agent_type,
        "focus_id": mandate.focus_id or "",
        "polling_interval_minutes": mandate.polling_interval_minutes,
        "signal_threshold": mandate.signal_threshold,
        "active": mandate.active,
    }
    columns = ", ".join(f"{k} = :{k}" for k in params)
    await client.execute_command(
        f"INSERT INTO MandateRecord SET {columns}", params,
    )
    return mandate.mandate_id


async def update_mandate(
    client: ArcadeDBClient, mandate_id: str, updates: dict[str, Any],
) -> None:
    """Update fields on a mandate record."""
    allowed = {
        "name",
        "domain",
        "agent_type",
        "focus_id",
        "polling_interval_minutes",
        "signal_threshold",
        "active",
    }
    safe_updates = {k: v for k, v in updates.items() if k in allowed}
    if not safe_updates:
        return

    set_clause = ", ".join(f"{k} = :{k}" for k in safe_updates)
    safe_updates["mandate_id"] = mandate_id
    await client.execute_command(
        f"UPDATE MandateRecord SET {set_clause} WHERE mandate_id = :mandate_id",
        safe_updates,
    )


async def delete_mandate(client: ArcadeDBClient, mandate_id: str) -> None:
    """Delete a mandate record."""
    await client.execute_command(
        "DELETE FROM MandateRecord WHERE mandate_id = :mandate_id",
        {"mandate_id": mandate_id},
    )
