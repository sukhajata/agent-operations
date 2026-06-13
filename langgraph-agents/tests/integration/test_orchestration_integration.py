"""Integration tests for orchestration functions.

Requires ARCADEDB_URL pointing to a real instance.
"""
# ruff: noqa: ANN001, ANN201, ANN202
from __future__ import annotations

import asyncio

import pytest


@pytest.mark.integration
def test_orchestrate_empty_cycle(arcadedb_client) -> None:
    """Run orchestrate against a real ArcadeDB when no work is pending."""
    from functions.orchestration import run as run_orch

    _ = arcadedb_client  # fixture gate — real client used internally by run()

    async def _run() -> None:
        counts = await run_orch("/tmp/config")
        assert isinstance(counts, dict)
        assert "dispatched" in counts
        assert "stalled_escalated" in counts
        assert "promoted" in counts
        assert "decayed" in counts

    asyncio.run(_run())


@pytest.mark.integration
def test_confidence_decay_runs(arcadedb_client) -> None:
    """Verify confidence decay executes against the real graph."""
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.graph import apply_decay_all

    client: ArcadeDBClient = arcadedb_client

    async def _run() -> None:
        count = await apply_decay_all(client)
        assert isinstance(count, int)
        assert count >= 0

    asyncio.run(_run())


@pytest.mark.integration
def test_commitment_status_query(arcadedb_client) -> None:
    """Verify querying commitment records works."""
    from shared.arcadedb.client import ArcadeDBClient

    client: ArcadeDBClient = arcadedb_client

    async def _run() -> None:
        records = await client.execute_query(
            "SELECT FROM CommitmentRecord WHERE status = 'approved' LIMIT 5",
        )
        assert isinstance(records, list)

    asyncio.run(_run())
