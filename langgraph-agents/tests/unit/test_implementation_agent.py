from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from agents.implementation import run as run_impl
from schema.identity.models import CognitiveCheckpoint, CommitmentRecord

SAMPLE_DATETIME = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
SAMPLE_DATETIME_STR = "2026-06-09T12:00:00+00:00"


def _mk_commitment(**overrides: object) -> CommitmentRecord:  # noqa: ANN401
    kwargs: dict[str, object] = {
        "commitment_id": "com-001",
        "status": "approved",
        "created_at": SAMPLE_DATETIME,
        "domain": "performance",
        "priority_signal": 0.8,
        "checkpoint": CognitiveCheckpoint(
            current_best_understanding="understood",
            recommended_next_action="implement",
            plan="Step 1: Fix auth module memory leak.\nStep 2: Add tests.",
            checkpoint_at=SAMPLE_DATETIME,
        ),
    }
    kwargs.update(overrides)
    return CommitmentRecord.model_validate(kwargs)


def test_run_no_approved_commitments() -> None:
    db_client = MagicMock()
    db_client.execute_query = AsyncMock(return_value=[])

    with patch(
        "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
    ), patch("shared.config.loader.load_project_config"):
        async def _run() -> None:
            result = await run_impl("/tmp/config")
            assert result == 0

        asyncio.run(_run())


def test_run_dispatches_and_sets_executing() -> None:
    import shared.arcadedb.identity as id_mod
    original_update = id_mod.update_commitment

    call_args: list[dict[str, str]] = []

    async def mock_update(client: object, cid: str, updates: dict[str, str]) -> None:
        call_args.append({"cid": cid, "status": updates.get("status", "")})

    id_mod.update_commitment = mock_update

    db_client = MagicMock()
    db_client.execute_query = AsyncMock(return_value=[{
        "commitment_id": "com-001",
        "status": "approved",
        "created_at": SAMPLE_DATETIME_STR,
        "domain": "performance",
        "priority_signal": 0.8,
        "checkpoint": {
            "current_best_understanding": "u",
            "recommended_next_action": "n",
            "plan": "Step 1: Do X.\nStep 2: Do Y.",
            "checkpoint_at": SAMPLE_DATETIME_STR,
        },
    }])
    db_client.execute_command = AsyncMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ), patch("shared.config.loader.load_project_config"):
            async def _run() -> None:
                with patch(
                    "httpx.AsyncClient",
                ) as mock_client_cls:
                    mock_client_cls.return_value.__aenter__.return_value.post = AsyncMock(
                        return_value=mock_response,
                    )
                    result = await run_impl("/tmp/config")
                    assert result == 1

            asyncio.run(_run())
    finally:
        id_mod.update_commitment = original_update

    statuses = [c["status"] for c in call_args]
    assert "executing" in statuses


def test_run_no_plan_marks_stalled() -> None:
    import shared.arcadedb.identity as id_mod
    original_update = id_mod.update_commitment

    call_args: list[dict[str, str]] = []

    async def mock_update(client: object, cid: str, updates: dict[str, str]) -> None:
        call_args.append({"cid": cid, "status": updates.get("status", "")})

    id_mod.update_commitment = mock_update

    db_client = MagicMock()
    db_client.execute_query = AsyncMock(return_value=[{
        "commitment_id": "com-001",
        "status": "approved",
        "created_at": SAMPLE_DATETIME_STR,
        "domain": "performance",
        "priority_signal": 0.8,
    }])

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ), patch("shared.config.loader.load_project_config"):
            async def _run() -> None:
                result = await run_impl("/tmp/config")
                assert result == 0

            asyncio.run(_run())
    finally:
        id_mod.update_commitment = original_update

    assert call_args[0]["status"] == "stalled"
