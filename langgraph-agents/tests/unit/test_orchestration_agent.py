from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from functions.orchestration import run as run_orch


def test_run_no_issues() -> None:
    db_client = MagicMock()
    # all empty: no approved, no stalled, no completed
    db_client.execute_query = AsyncMock(return_value=[])

    import shared.arcadedb.graph as graph_mod
    original_decay = graph_mod.apply_decay_all

    async def mock_decay(*args: object, **kwargs: object) -> int:
        return 0

    graph_mod.apply_decay_all = mock_decay

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ):
            async def _run() -> None:
                counts = await run_orch("/tmp/config")
                assert counts["stalled_escalated"] == 0
                assert counts["promoted"] == 0
                assert counts["decayed"] == 0

            asyncio.run(_run())
    finally:
        graph_mod.apply_decay_all = original_decay


def test_run_escalates_stalled_commitments() -> None:
    import shared.arcadedb.identity as id_mod
    original_update = id_mod.update_commitment

    calls: list[dict[str, str]] = []

    async def mock_update(client: object, cid: str, updates: dict[str, str]) -> None:
        calls.append({"cid": cid, "status": updates.get("status", "")})

    id_mod.update_commitment = mock_update

    db_client = MagicMock()
    db_client.execute_query = AsyncMock(side_effect=[
        [],  # approved (empty)
        [{"commitment_id": "com-stalled", "status": "executing",
          "checkpoint": {"checkpoint_at": datetime(2026, 1, 1, tzinfo=UTC)}}],
        [],  # completed (empty)
    ])

    import shared.arcadedb.graph as graph_mod
    original_decay = graph_mod.apply_decay_all

    async def mock_decay(*args: object, **kwargs: object) -> int:
        return 0

    graph_mod.apply_decay_all = mock_decay

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ):
            async def _run() -> None:
                counts = await run_orch("/tmp/config")
                assert counts["stalled_escalated"] >= 1

            asyncio.run(_run())
    finally:
        id_mod.update_commitment = original_update
        graph_mod.apply_decay_all = original_decay

    assert calls[0]["status"] == "stalled"


def test_run_promotes_closed_findings() -> None:
    import shared.arcadedb.identity as id_mod
    original_update = id_mod.update_commitment

    async def mock_update(client: object, cid: str, updates: dict[str, str]) -> None:
        pass

    id_mod.update_commitment = mock_update

    db_client = MagicMock()
    db_client.execute_query = AsyncMock(side_effect=[
        [],  # approved (empty)
        [],  # stalled (empty)
        [{"commitment_id": "com-done", "domain": "performance"}],  # completed
        [{"claim": "API architecture restructured", "confidence": 0.9,
          "reasoning": "verified"}],  # findings
        [],  # existing nodes
        [],  # upsert_node existing check
    ])
    db_client.execute_command = AsyncMock()

    import shared.arcadedb.graph as graph_mod
    original_decay = graph_mod.apply_decay_all

    async def mock_decay(*args: object, **kwargs: object) -> int:
        return 0

    graph_mod.apply_decay_all = mock_decay

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ):
            async def _run() -> None:
                counts = await run_orch("/tmp/config")
                assert counts["promoted"] >= 1

            asyncio.run(_run())
    finally:
        id_mod.update_commitment = original_update
        graph_mod.apply_decay_all = original_decay


def test_run_dispatches_approved() -> None:
    import shared.arcadedb.identity as id_mod
    original_update = id_mod.update_commitment

    calls: list[dict[str, str]] = []
    async def mock_update(client: object, cid: str, updates: dict[str, str]) -> None:
        calls.append({"cid": cid, "status": updates.get("status", "")})

    id_mod.update_commitment = mock_update

    from datetime import UTC, datetime

    from schema.identity.models import CognitiveCheckpoint

    checkpoint = CognitiveCheckpoint(
        current_best_understanding="u",
        recommended_next_action="n",
        plan="Step 1: Do X.",
        checkpoint_at=datetime(2026, 6, 9, tzinfo=UTC),
    )

    db_client = MagicMock()
    db_client.execute_query = AsyncMock(side_effect=[
        [{  # approved
            "commitment_id": "com-001", "status": "approved",
            "created_at": "2026-06-09T00:00:00Z",
            "domain": "test", "priority_signal": 0.8,
            "checkpoint": checkpoint.model_dump(mode="json"),
        }],
        [],  # stalled
        [],  # completed
    ])
    db_client.execute_command = AsyncMock()

    import shared.arcadedb.graph as graph_mod
    original_decay = graph_mod.apply_decay_all
    async def mock_decay(*args: object, **kwargs: object) -> int:
        return 0
    graph_mod.apply_decay_all = mock_decay

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ):
            async def _run() -> None:
                with patch(
                    "httpx.AsyncClient",
                ) as mock_cls:
                    mock_cls.return_value.__aenter__.return_value.post = AsyncMock(
                        return_value=mock_response,
                    )
                    counts = await run_orch("/tmp/config")
                    assert counts["dispatched"] >= 1

            asyncio.run(_run())
    finally:
        id_mod.update_commitment = original_update
        graph_mod.apply_decay_all = original_decay

    statuses = [c["status"] for c in calls if c["status"] == "executing"]
    assert len(statuses) >= 1
