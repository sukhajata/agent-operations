from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from agents.research_plan.graph import (
    _route_after_checkpoint,
    _route_after_poll,
    build_research_plan_graph,
)
from agents.research_plan.nodes import (
    create_commitment,
    form_understanding,
    mark_pending_approval,
    poll_for_findings,
    produce_plan,
    read_event_delta,
    traverse_graph,
    write_checkpoint,
)
from agents.research_plan.state import ResearchPlanState
from schema.identity.models import CommitmentRecord, HypothesisRecord
from schema.timeseries.event_log import AgentFinding

SAMPLE_DATETIME = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
SAMPLE_DATETIME_STR = "2026-06-09T12:00:00+00:00"


def _mk_finding(**overrides: Any) -> AgentFinding:  # noqa: ANN401
    kwargs: dict[str, Any] = {
        "event_type": "AgentFinding",
        "ts": SAMPLE_DATETIME,
        "agent_id": "verifier-1",
        "mtp_version": "1.0",
        "claim": "The auth module has a memory leak",
        "domain": "performance",
        "confidence": 0.95,
        "reasoning": "Verified via independent analysis",
        "sources": ["heap_dump.hprof"],
        "focus_id": "focus-001",
        "verdict": "confirmed",
        "originating_signal_ts": SAMPLE_DATETIME,
    }
    kwargs.update(overrides)
    return AgentFinding(**kwargs)


def _mk_state(overrides: dict[str, Any] | None = None) -> ResearchPlanState:  # noqa: ANN401
    state: ResearchPlanState = {
        "finding": None,
        "commitment": None,
        "mtp_version": "1.0",
        "agent_id": "research-plan-test",
        "graph_context": [],
        "artifact_context": [],
        "event_delta": [],
        "hypotheses": [],
        "current_understanding": None,
        "plan": None,
        "iteration": 0,
        "max_iterations": 3,
        "last_cursor": None,
        "completed": False,
    }
    if overrides:
        state.update(overrides)  # type: ignore[typeddict-item]
    return state


# --- poll_for_findings ---


def test_poll_finds_confirmed_finding() -> None:
    import shared.arcadedb.timeseries as ts_mod
    original = ts_mod.poll_events

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return [{
            "event_type": "AgentFinding", "ts": SAMPLE_DATETIME_STR,
            "agent_id": "verifier-1", "mtp_version": "1.0",
            "claim": "test claim", "domain": "test", "confidence": 0.9,
            "reasoning": "test", "sources": [],
            "focus_id": "focus-001", "verdict": "confirmed",
            "originating_signal_ts": SAMPLE_DATETIME_STR,
        }]

    ts_mod.poll_events = mock_poll

    import shared.arcadedb.identity as id_mod
    original_get = id_mod.get_commitment
    async def mock_get(*args: object, **kwargs: object) -> None:
        return None
    id_mod.get_commitment = mock_get

    try:
        state = _mk_state()

        async def _run() -> None:
            db_client = MagicMock()
            result = await poll_for_findings(state, db_client=db_client)
            assert result.get("finding") is not None
            assert result["finding"].verdict == "confirmed"

        asyncio.run(_run())
    finally:
        ts_mod.poll_events = original
        id_mod.get_commitment = original_get


def test_poll_finds_no_findings() -> None:
    import shared.arcadedb.timeseries as ts_mod
    original = ts_mod.poll_events

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return []

    ts_mod.poll_events = mock_poll

    import shared.arcadedb.identity as id_mod
    original_get = id_mod.get_commitment
    async def mock_get(*args: object, **kwargs: object) -> None:
        return None
    id_mod.get_commitment = mock_get

    try:
        state = _mk_state()

        async def _run() -> None:
            result = await poll_for_findings(state, db_client=MagicMock())
            assert result["completed"] is True
            assert result.get("finding") is None

        asyncio.run(_run())
    finally:
        ts_mod.poll_events = original
        id_mod.get_commitment = original_get


def test_poll_filters_non_confirmed() -> None:
    import shared.arcadedb.timeseries as ts_mod
    original = ts_mod.poll_events

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return [{
            "event_type": "AgentFinding", "ts": SAMPLE_DATETIME_STR,
            "agent_id": "v1", "mtp_version": "1.0",
            "claim": "test", "domain": "test", "confidence": 0.5,
            "reasoning": "test", "sources": [],
            "focus_id": None, "verdict": "contradicted",
            "originating_signal_ts": SAMPLE_DATETIME_STR,
        }]

    ts_mod.poll_events = mock_poll
    try:
        state = _mk_state()

        async def _run() -> None:
            result = await poll_for_findings(state, db_client=MagicMock())
            assert result["completed"] is True

        asyncio.run(_run())
    finally:
        ts_mod.poll_events = original


# --- create_commitment ---


def test_create_commitment() -> None:
    import shared.arcadedb.identity as id_mod
    original = id_mod.create_commitment

    async def mock_create(*args: object, **kwargs: object) -> str:
        return "com-focus-001"

    id_mod.create_commitment = mock_create
    try:
        state = _mk_state({"finding": _mk_finding()})

        async def _run() -> None:
            result = await create_commitment(state, db_client=MagicMock())
            assert result.get("commitment") is not None
            assert result["commitment"].status == "active"

        asyncio.run(_run())
    finally:
        id_mod.create_commitment = original


def test_create_commitment_no_finding() -> None:
    state = _mk_state()

    async def _run() -> None:
        result = await create_commitment(state, db_client=MagicMock())
        assert result["completed"] is True

    asyncio.run(_run())


# --- traverse_graph ---


def test_traverse_graph() -> None:
    db_client = MagicMock()
    db_client.execute_query = AsyncMock(return_value=[{"node_id": "n1", "confidence": 0.8}])

    state = _mk_state({"finding": _mk_finding()})

    async def _run() -> None:
        result = await traverse_graph(state, db_client=db_client)
        assert len(result["graph_context"]) == 1

    asyncio.run(_run())


def test_traverse_graph_no_finding() -> None:
    state = _mk_state()

    async def _run() -> None:
        result = await traverse_graph(state, db_client=MagicMock())
        assert result == {}

    asyncio.run(_run())


# --- read_event_delta ---


def test_read_event_delta() -> None:
    import shared.arcadedb.timeseries as ts_mod
    original = ts_mod.poll_events

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return [{"event_type": "AgentSignal", "ts": SAMPLE_DATETIME_STR}]

    ts_mod.poll_events = mock_poll
    try:
        state = _mk_state({"finding": _mk_finding()})

        async def _run() -> None:
            result = await read_event_delta(state, db_client=MagicMock())
            assert len(result["event_delta"]) == 1

        asyncio.run(_run())
    finally:
        ts_mod.poll_events = original


def test_read_event_delta_no_finding() -> None:
    state = _mk_state()

    async def _run() -> None:
        result = await read_event_delta(state, db_client=MagicMock())
        assert result == {}

    asyncio.run(_run())


# --- form_understanding ---


def test_form_understanding() -> None:
    state = _mk_state({
        "finding": _mk_finding(),
        "graph_context": [{"node_id": "n1"}],
    })
    model = MagicMock()
    response = MagicMock()
    response.content = (
        '{"hypotheses": [{"hypothesis": "h1", "conclusion": "pending", "evidence": "e1"}],'
        ' "current_understanding": "test understanding"}'
    )
    model.ainvoke = AsyncMock(return_value=response)

    async def _run() -> None:
        result = await form_understanding(state, model=model)
        assert len(result["hypotheses"]) == 1
        assert result["current_understanding"] == "test understanding"

    asyncio.run(_run())


def test_form_understanding_non_json() -> None:
    state = _mk_state({"finding": _mk_finding()})
    model = MagicMock()
    response = MagicMock()
    response.content = "Just some text, not JSON."
    model.ainvoke = AsyncMock(return_value=response)

    async def _run() -> None:
        result = await form_understanding(state, model=model)
        assert result["hypotheses"] == []

    asyncio.run(_run())


# --- write_checkpoint ---


def test_write_checkpoint() -> None:
    import shared.arcadedb.identity as id_mod
    original = id_mod.write_checkpoint

    async def mock_write(*args: object, **kwargs: object) -> None:
        pass

    id_mod.write_checkpoint = mock_write
    try:
        commitment = CommitmentRecord(
            commitment_id="com-1", status="active",
            created_at=SAMPLE_DATETIME, domain="test", priority_signal=0.8,
        )
        state = _mk_state({
            "commitment": commitment,
            "hypotheses": [HypothesisRecord(
                hypothesis="test", conclusion="pending", evidence="e",
            )],
            "current_understanding": "understood",
        })

        async def _run() -> None:
            result = await write_checkpoint(state, db_client=MagicMock())
            assert result is not None

        asyncio.run(_run())
    finally:
        id_mod.write_checkpoint = original


def test_write_checkpoint_no_commitment() -> None:
    state = _mk_state()

    async def _run() -> None:
        result = await write_checkpoint(state, db_client=MagicMock())
        assert result == {}

    asyncio.run(_run())


# --- produce_plan ---


def test_produce_plan() -> None:
    state = _mk_state({"finding": _mk_finding(), "current_understanding": "understood"})
    model = MagicMock()
    response = MagicMock()
    response.content = "Step 1: Do X. Step 2: Do Y."
    model.ainvoke = AsyncMock(return_value=response)

    async def _run() -> None:
        result = await produce_plan(state, model=model)
        assert "Step 1" in result["plan"]

    asyncio.run(_run())


# --- mark_pending_approval ---


def test_mark_pending_approval() -> None:
    import shared.arcadedb.identity as id_mod
    original = id_mod.update_commitment

    async def mock_update(*args: object, **kwargs: object) -> None:
        pass

    id_mod.update_commitment = mock_update
    try:
        commitment = CommitmentRecord(
            commitment_id="com-1", status="active",
            created_at=SAMPLE_DATETIME, domain="test", priority_signal=0.8,
        )
        state = _mk_state({"commitment": commitment})

        async def _run() -> None:
            result = await mark_pending_approval(state, db_client=MagicMock())
            assert result["completed"] is True

        asyncio.run(_run())
    finally:
        id_mod.update_commitment = original


def test_mark_pending_approval_no_commitment() -> None:
    state = _mk_state()

    async def _run() -> None:
        result = await mark_pending_approval(state, db_client=MagicMock())
        assert result["completed"] is True

    asyncio.run(_run())


# --- Routing ---


def test_route_after_poll_finding() -> None:
    state = _mk_state({
        "finding": _mk_finding(),
        "completed": False,
    })
    assert _route_after_poll(state) == "create_commitment"


def test_route_after_poll_completed() -> None:
    state = _mk_state({"completed": True})
    assert _route_after_poll(state) == "end"


def test_route_after_checkpoint_do_research() -> None:
    state = _mk_state({"iteration": 0, "max_iterations": 3})
    assert _route_after_checkpoint(state) == "traverse_graph"


def test_route_after_checkpoint_produce_plan() -> None:
    state = _mk_state({
        "iteration": 3, "max_iterations": 3,
        "current_understanding": "understood",
    })
    assert _route_after_checkpoint(state) == "produce_plan"


# --- Graph compilation ---


def test_graph_compiles() -> None:
    model = MagicMock()
    db_client = MagicMock()
    mcp = MagicMock()
    graph = build_research_plan_graph(model, db_client, mcp)
    assert graph is not None
