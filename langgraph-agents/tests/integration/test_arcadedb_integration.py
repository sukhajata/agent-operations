"""Integration tests for ArcadeDB graph and timeseries operations.

Requires ARCADEDB_URL pointing to a real instance.
"""
# ruff: noqa: ANN001, ANN201, ANN202
from __future__ import annotations

import asyncio

import pytest


@pytest.mark.integration
def test_graph_upsert_and_traverse(arcadedb_client) -> None:
    """Create a node, traverse from it, verify it exists."""
    from schema.graph.node_types import GraphNode
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.graph import get_node, traverse_from, upsert_node
    from shared.config.loader import MandateDefinition

    client: ArcadeDBClient = arcadedb_client

    async def _run() -> None:
        node = GraphNode(
            name="integration-test-node",
            node_type="ProductStructure",
            domain="integration_testing",
            description="A test node for graph integration tests",
            confidence=0.9,
            sources=["integration-test"],
            created_at="2026-06-01T00:00:00Z",
            mandate=MandateDefinition(
                name="integration-test",
                domain="integration_testing",
                agent_type="free",
                polling_interval_minutes=60,
                signal_threshold=0.6,
            ).model_dump(mode="json"),
        )

        await upsert_node(client, node)

        # Verify node exists
        retrieved = await get_node(client, "integration-test-node", "ProductStructure")
        assert retrieved is not None
        assert retrieved.name == "integration-test-node"
        assert retrieved.confidence == 0.9

        # Traverse
        results = await traverse_from(client, "integration-test-node", max_depth=1)
        assert isinstance(results, list)

    asyncio.run(_run())


@pytest.mark.integration
def test_graph_confidence_decay(arcadedb_client) -> None:
    """Verify confidence decay applies correctly."""
    from datetime import UTC, datetime, timedelta

    from schema.graph.node_types import DECAY_RATES, GraphNode
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.graph import apply_decay_all, get_node, upsert_node
    from shared.config.loader import MandateDefinition

    client: ArcadeDBClient = arcadedb_client

    async def _run() -> None:
        old_date = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")

        node = GraphNode(
            name="integration-test-decay",
            node_type="DecisionRecord",
            domain="integration_testing",
            description="A node for testing decay",
            confidence=1.0,
            sources=["integration-test"],
            created_at=old_date,
            mandate=MandateDefinition(
                name="integration-test",
                domain="integration_testing",
                agent_type="free",
                polling_interval_minutes=60,
                signal_threshold=0.6,
            ).model_dump(mode="json"),
        )

        await upsert_node(client, node)

        # Apply decay
        count = await apply_decay_all(client)
        assert isinstance(count, int)
        assert count >= 0

        # Verify confidence reduced
        retrieved = await get_node(client, "integration-test-decay", "DecisionRecord")
        if retrieved is not None:
            expected = 1.0 * (1 - DECAY_RATES["DecisionRecord"]) ** 10
            assert abs(retrieved.confidence - expected) < 0.1

    asyncio.run(_run())


@pytest.mark.integration
def test_timeseries_emit_and_poll(arcadedb_client) -> None:
    """Emit an event and poll it back."""
    from datetime import UTC, datetime

    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.timeseries import emit_event, poll_events

    client: ArcadeDBClient = arcadedb_client

    unique_id = f"integration-test-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S-%f')}"
    event = {
        "event_type": "AgentSignal",
        "ts": datetime.now(UTC).isoformat(),
        "agent_id": unique_id,
        "mtp_version": "1.0",
        "claim": "Timeseries integration test claim",
        "domain": "integration_testing",
        "confidence": 0.7,
        "reasoning": "Testing emit and poll",
        "sources": ["integration-test"],
        "focus_id": None,
        "novelty_flag": True,
    }

    async def _run() -> None:
        await emit_event(client, "AgentSignal", event)

        results = await poll_events(client, agent_id=unique_id, limit=1)
        assert len(results) > 0
        assert results[0].get("agent_id") == unique_id

    asyncio.run(_run())


@pytest.mark.integration
def test_identity_mandate_crud(arcadedb_client) -> None:
    """Create, read, and delete a mandate via the identity module."""
    from schema.identity.models import MandateRecord
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.identity import (
        create_mandate,
        delete_mandate,
        get_active_mandates,
        get_all_mandates,
    )

    client: ArcadeDBClient = arcadedb_client

    mandate = MandateRecord(
        mandate_id="integration-test-mandate",
        name="integration-test-mandate",
        domain="integration_testing",
        agent_type="free",
        polling_interval_minutes=60,
        signal_threshold=0.5,
        active=True,
    )

    async def _run() -> None:
        await create_mandate(client, mandate)

        all_mandates = await get_all_mandates(client)
        active = await get_active_mandates(client)

        assert any(m.name == "integration-test-mandate" for m in active)
        assert any(m.name == "integration-test-mandate" for m in all_mandates)

        await delete_mandate(client, "integration-test-mandate")

        after_delete = await get_active_mandates(client)
        assert not any(m.name == "integration-test-mandate" for m in after_delete)

    asyncio.run(_run())


@pytest.mark.integration
def test_event_schema_validation(arcadedb_client) -> None:
    """Verify event schema validation with a real ArcadeDB emit."""
    from datetime import UTC, datetime

    from shared.arcadedb.client import ArcadeDBClient
    from shared.event_schemas.validator import emit_validated

    client: ArcadeDBClient = arcadedb_client
    agent_id = f"integration-test-schema-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

    valid_events = [
        {
            "event_type": "AgentSignal",
            "ts": datetime.now(UTC).isoformat(),
            "agent_id": agent_id,
            "mtp_version": "1.0",
            "claim": "Schema validation test",
            "domain": "integration_testing",
            "confidence": 0.7,
            "reasoning": "Test",
            "sources": ["test"],
            "focus_id": None,
            "novelty_flag": False,
        },
        {
            "event_type": "AgentFinding",
            "ts": datetime.now(UTC).isoformat(),
            "agent_id": agent_id,
            "mtp_version": "1.0",
            "claim": "test claim",
            "domain": "integration_testing",
            "verdict": "inconclusive",
            "verdict_confidence": 0.5,
            "verdict_rationale": "not enough data",
            "originating_signal_id": None,
            "focus_id": None,
            "originating_signal_ts": datetime.now(UTC).isoformat(),
        },
    ]

    async def _run() -> None:
        for event in valid_events:
            await emit_validated(event, client)

        # Verify they were persisted
        from shared.arcadedb.timeseries import poll_events
        results = await poll_events(client, agent_id=agent_id, limit=5)
        assert len(results) >= 2

    asyncio.run(_run())
