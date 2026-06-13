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
        [{"commitment_id": "com-stalled", "status": "active", "implementation_state": "in_progress",
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
            "repository_url": "https://github.com/test/repo",
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

    async def mock_invoke(agent_id: str, session_id: str, prompt: str) -> str:
        return "Task completed successfully."

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ), patch(
            "shared.config.loader.load_project_config",
            return_value=MagicMock(mtp=MagicMock(version="1.0")),
        ), patch(
            "shared.bedrock_agent.invoke_bedrock_agent", mock_invoke,
        ), patch(
            "functions.orchestration.CODING_AGENT_ID", "test-agent-id",
        ):
            async def _run() -> None:
                counts = await run_orch("/tmp/config")
                assert counts["dispatched"] >= 1

            asyncio.run(_run())
    finally:
        id_mod.update_commitment = original_update
        graph_mod.apply_decay_all = original_decay

    statuses = [c["status"] for c in calls if c["status"] == "executing"]
    assert len(statuses) >= 1


def test_run_dispatches_with_repository_and_branch() -> None:
    """Test that dispatch includes repository_url and base_branch in the task."""
    import shared.arcadedb.identity as id_mod
    original_update = id_mod.update_commitment

    calls: list[dict[str, str]] = []
    async def mock_update(client: object, cid: str, updates: dict[str, str]) -> None:
        calls.append({"cid": cid, "status": updates.get("status", "")})

    id_mod.update_commitment = mock_update

    from datetime import UTC, datetime

    from schema.identity.models import CognitiveCheckpoint

    checkpoint = CognitiveCheckpoint(
        current_best_understanding="Refactor auth module",
        recommended_next_action="Implement changes",
        plan="Step 1: Refactor auth module.",
        checkpoint_at=datetime(2026, 6, 9, tzinfo=UTC),
    )

    db_client = MagicMock()
    db_client.execute_query = AsyncMock(side_effect=[
        [{  # approved with repository_url and base_branch
            "commitment_id": "com-001", "status": "approved",
            "created_at": "2026-06-09T00:00:00Z",
            "domain": "test", "priority_signal": 0.8,
            "checkpoint": checkpoint.model_dump(mode="json"),
            "repository_url": "https://github.com/org/repo",
            "base_branch": "develop",
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

    captured_invoke_calls: list[dict] = []

    async def mock_invoke(agent_id: str, session_id: str, prompt: str) -> str:
        captured_invoke_calls.append({
            "agent_id": agent_id, "session_id": session_id, "prompt": prompt,
        })
        return "Task completed successfully."

    try:
        with patch(
            "shared.arcadedb.client.ArcadeDBClient", return_value=db_client,
        ), patch(
            "shared.config.loader.load_project_config",
            return_value=MagicMock(mtp=MagicMock(version="1.0")),
        ), patch(
            "shared.bedrock_agent.invoke_bedrock_agent", mock_invoke,
        ), patch(
            "functions.orchestration.CODING_AGENT_ID", "test-agent-id",
        ):
            async def _run() -> None:
                counts = await run_orch("/tmp/config")
                assert counts["dispatched"] >= 1

                assert len(captured_invoke_calls) >= 1
                task_text = captured_invoke_calls[0]["prompt"]
                assert "https://github.com/org/repo" in task_text
                assert "develop" in task_text

            asyncio.run(_run())
    finally:
        id_mod.update_commitment = original_update
        graph_mod.apply_decay_all = original_decay

    statuses = [c["status"] for c in calls if c["status"] == "executing"]
    assert len(statuses) >= 1
