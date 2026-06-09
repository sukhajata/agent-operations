"""ArcadeDB knowledge graph operations.

Provides functions for node CRUD, traversal, reinforcement, decay,
and revalidation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from schema.graph.node_types import DECAY_RATES, REVALIDATION_THRESHOLD, GraphNode

from .client import ArcadeDBClient

_VERTEX_TYPES = list(DECAY_RATES.keys())


async def _node_from_record(record: dict[str, Any]) -> GraphNode:
    """Deserialize an ArcadeDB record into a GraphNode."""
    node_type = record["node_type"]
    last_reinforced = record["last_reinforced"]
    if isinstance(last_reinforced, str):
        last_reinforced = datetime.fromisoformat(last_reinforced)
    return GraphNode(
        node_id=record["node_id"],
        node_type=node_type,
        confidence=record["confidence"],
        initial_confidence=record["initial_confidence"],
        decay_rate=DECAY_RATES[node_type],
        last_reinforced=last_reinforced,
        revalidation_required=record["revalidation_required"],
    )


def _node_params(node: GraphNode) -> dict[str, Any]:
    """Convert a GraphNode to parameter map for SQL commands."""
    return {
        "node_id": node.node_id,
        "node_type": node.node_type,
        "confidence": node.confidence,
        "initial_confidence": node.initial_confidence,
        "decay_rate": node.decay_rate,
        "last_reinforced": node.last_reinforced.isoformat(),
        "revalidation_required": node.revalidation_required,
    }


async def upsert_node(client: ArcadeDBClient, node: GraphNode) -> str:
    """Create or update a knowledge graph vertex.

    Args:
        client: ArcadeDB client instance
        node: The graph node to upsert

    Returns:
        The node_id of the created or updated node

    Raises:
        ArcadeDBError: On database error
    """
    existing = await client.execute_query(
        f"SELECT FROM {node.node_type} WHERE node_id = :node_id LIMIT 1",
        {"node_id": node.node_id},
    )

    params = _node_params(node)

    if existing:
        columns = ", ".join(f"{k} = :{k}" for k in params if k != "node_id")
        await client.execute_command(
            f"UPDATE {node.node_type} SET {columns} WHERE node_id = :node_id",
            params,
        )
    else:
        columns = ", ".join(f"{k} = :{k}" for k in params)
        await client.execute_command(
            f"CREATE VERTEX {node.node_type} SET {columns}",
            params,
        )
    return node.node_id


async def get_node(
    client: ArcadeDBClient, node_id: str
) -> GraphNode | None:
    """Retrieve a knowledge graph node by ID.

    Args:
        client: ArcadeDB client instance
        node_id: The node identifier

    Returns:
        The GraphNode if found, None otherwise
    """
    for vertex_type in _VERTEX_TYPES:
        records = await client.execute_query(
            f"SELECT FROM {vertex_type} WHERE node_id = :node_id LIMIT 1",
            {"node_id": node_id},
        )
        if records:
            return await _node_from_record(records[0])
    return None


async def traverse_from(
    client: ArcadeDBClient,
    node_id: str,
    max_depth: int = 3,
) -> list[GraphNode]:
    """Traverse the graph outward from a node.

    Args:
        client: ArcadeDB client instance
        node_id: Starting node identifier
        max_depth: Maximum traversal depth

    Returns:
        List of GraphNodes found in the traversal
    """
    node = await get_node(client, node_id)
    if node is None:
        return []

    query = (
        f"SELECT FROM (TRAVERSE OUT() FROM (SELECT FROM {node.node_type} "
        f"WHERE node_id = :node_id) MAXDEPTH {max_depth})"
    )
    records = await client.execute_query(query, {"node_id": node_id})

    nodes: list[GraphNode] = []
    for record in records:
        node_type = record.get("node_type")
        if node_type and node_type in DECAY_RATES:
            nodes.append(await _node_from_record(record))
    return nodes


async def reinforce_node(client: ArcadeDBClient, node_id: str) -> None:
    """Reinforce a node — reset decay clock and restore confidence.

    Sets confidence back to initial_confidence and updates last_reinforced
    to the current time. Clears the revalidation_required flag.

    Args:
        client: ArcadeDB client instance
        node_id: The node identifier to reinforce
    """
    node = await get_node(client, node_id)
    if node is None:
        return

    await client.execute_command(
        f"UPDATE {node.node_type} SET confidence = :confidence, "
        "last_reinforced = :last_reinforced, revalidation_required = false "
        "WHERE node_id = :node_id",
        {
            "node_id": node_id,
            "confidence": node.initial_confidence,
            "last_reinforced": datetime.now(UTC).isoformat(),
        },
    )


async def flag_for_revalidation(client: ArcadeDBClient, node_id: str) -> None:
    """Flag a node as requiring revalidation.

    Args:
        client: ArcadeDB client instance
        node_id: The node identifier to flag
    """
    node = await get_node(client, node_id)
    if node is None:
        return

    await client.execute_command(
        f"UPDATE {node.node_type} SET revalidation_required = true "
        "WHERE node_id = :node_id",
        {"node_id": node_id},
    )


async def apply_decay_all(client: ArcadeDBClient) -> int:
    """Apply confidence decay to all knowledge graph nodes.

    Computes current confidence using the per-type decay rate and time
    elapsed since last reinforcement. Flagging for revalidation
    if confidence falls below the threshold.

    Returns:
        Number of nodes updated
    """
    total_updated = 0
    now = datetime.now(UTC)

    for vertex_type in _VERTEX_TYPES:
        try:
            records = await client.execute_query(f"SELECT FROM {vertex_type}")
        except Exception:
            continue

        for record in records:
            node = await _node_from_record(record)
            elapsed_days = (now - node.last_reinforced).total_seconds() / 86400.0
            if elapsed_days < 0:
                elapsed_days = 0.0

            current_conf = node.confidence * (1.0 - node.decay_rate) ** elapsed_days
            needs_revalidation = current_conf < REVALIDATION_THRESHOLD

            if (
                abs(current_conf - node.confidence) > 1e-10
                or needs_revalidation != node.revalidation_required
            ):
                await client.execute_command(
                    f"UPDATE {vertex_type} SET confidence = :confidence, "
                    "revalidation_required = :revalidation_required "
                    "WHERE node_id = :node_id",
                    {
                        "node_id": node.node_id,
                        "confidence": current_conf,
                        "revalidation_required": needs_revalidation,
                    },
                )
                total_updated += 1

    return total_updated
