from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from agents.verification.graph import _route_after_poll, build_verification_graph
from agents.verification.nodes import emit_finding, investigate, poll_for_observations
from agents.verification.state import VerificationState
from schema.timeseries.event_log import AgentSignal

SAMPLE_DATETIME = datetime(2026, 6, 9, 12, 0, 0, tzinfo=UTC)
SAMPLE_DATETIME_STR = "2026-06-09T12:00:00+00:00"


def _mk_signal(overrides: dict[str, Any] | None = None) -> AgentSignal:
    kwargs: dict[str, Any] = {
        "event_type": "AgentSignal",
        "ts": SAMPLE_DATETIME,
        "agent_id": "exploratory-test",
        "mtp_version": "1.0",
        "claim": "The auth module has a memory leak",
        "domain": "performance",
        "confidence": 0.85,
        "reasoning": "Observed heap growth without traffic increase",
        "sources": ["heap_dump.hprof"],
        "focus_id": "focus-001",
        "novelty_flag": True,
    }
    if overrides:
        kwargs.update(overrides)
    return AgentSignal(**kwargs)


def _mk_state(overrides: dict[str, Any] | None = None) -> VerificationState:
    from shared.openrouter.models import ModelFamily

    state: VerificationState = {
        "signal": None,
        "originating_model_family": ModelFamily.DEEPSEEK,
        "mtp_version": "1.0",
        "agent_id": "verification-test",
        "focus_id": None,
        "verdict": None,
        "verdict_confidence": None,
        "verdict_rationale": None,
        "last_cursor": None,
        "completed": False,
    }
    if overrides:
        state.update(overrides)  # type: ignore[typeddict-item]
    return state


# --- State tests ---


def test_state_defaults() -> None:
    state = _mk_state()
    assert state["signal"] is None
    assert state["verdict"] is None
    assert state["completed"] is False


# --- poll_for_observations ---


def test_poll_finds_signal() -> None:
    import shared.arcadedb.timeseries as ts_mod
    original = ts_mod.poll_events

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return [{
            "event_type": "AgentSignal", "ts": SAMPLE_DATETIME_STR,
            "agent_id": "exploratory-test", "mtp_version": "1.0",
            "claim": "test claim", "domain": "test", "confidence": 0.9,
            "reasoning": "test", "sources": [], "focus_id": "focus-001",
            "novelty_flag": True,
        }]

    ts_mod.poll_events = mock_poll
    try:
        state = _mk_state()

        async def _run() -> None:
            result = await poll_for_observations(
                state, db_client=MagicMock(), signal_threshold=0.6,
            )
            assert result.get("signal") is not None
            assert result["focus_id"] == "focus-001"

        asyncio.run(_run())
    finally:
        ts_mod.poll_events = original


def test_poll_filters_low_confidence() -> None:
    import shared.arcadedb.timeseries as ts_mod
    original = ts_mod.poll_events

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return [{
            "event_type": "AgentSignal", "ts": SAMPLE_DATETIME_STR,
            "agent_id": "exploratory-test", "mtp_version": "1.0",
            "claim": "low", "domain": "test", "confidence": 0.3,
            "reasoning": "weak", "sources": [], "focus_id": None,
            "novelty_flag": False,
        }]

    ts_mod.poll_events = mock_poll
    try:
        state = _mk_state()

        async def _run() -> None:
            result = await poll_for_observations(
                state, db_client=MagicMock(), signal_threshold=0.6,
            )
            assert result.get("signal") is None
            assert result["completed"] is True

        asyncio.run(_run())
    finally:
        ts_mod.poll_events = original


def test_poll_empty_returns_completed() -> None:
    import shared.arcadedb.timeseries as ts_mod
    original = ts_mod.poll_events

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return []

    ts_mod.poll_events = mock_poll
    try:
        state = _mk_state()

        async def _run() -> None:
            result = await poll_for_observations(
                state, db_client=MagicMock(), signal_threshold=0.6,
            )
            assert result["completed"] is True
            assert "last_cursor" in result

        asyncio.run(_run())
    finally:
        ts_mod.poll_events = original


# --- investigate ---


def test_investigate_no_signal() -> None:
    state = _mk_state({"signal": None})
    model = MagicMock()

    async def _run() -> None:
        result = await investigate(state, model=model, tools=[])
        assert result["completed"] is True

    asyncio.run(_run())


def test_investigate_no_tool_calls() -> None:
    state = _mk_state({"signal": _mk_signal()})
    model = MagicMock()
    model.bind_tools = MagicMock(return_value=model)

    response = MagicMock()
    response.content = (
        '{"verdict": "confirmed", "verdict_confidence": 0.9,'
        ' "verdict_rationale": "test"}'
    )
    response.tool_calls = []
    model.ainvoke = AsyncMock(return_value=response)

    async def _run() -> None:
        result = await investigate(state, model=model, tools=[])
        assert result["verdict"] == "confirmed"
        assert result["verdict_confidence"] == 0.9

    asyncio.run(_run())


def test_investigate_with_tool_calls() -> None:
    from unittest.mock import patch

    mock_tn = MagicMock()
    mock_tn.ainvoke = AsyncMock(
        return_value={"messages": [MagicMock(content="ignored")]},
    )

    state = _mk_state({"signal": _mk_signal()})
    model = MagicMock()
    model.bind_tools = MagicMock(return_value=model)

    tool_msg = MagicMock()
    tool_msg.content = ""
    tool_msg.tool_calls = [{"name": "search_graph", "args": {}, "id": "1"}]

    final_msg = MagicMock()
    final_msg.content = (
        '{"verdict": "contradicted", "verdict_confidence": 0.8,'
        ' "verdict_rationale": "contradiction found"}'
    )
    final_msg.tool_calls = []
    model.ainvoke = AsyncMock(side_effect=[tool_msg, final_msg])

    async def _run() -> None:
        with patch("langgraph.prebuilt.ToolNode", return_value=mock_tn):
            result = await investigate(state, model=model, tools=[])
            assert result["verdict"] == "contradicted"

    asyncio.run(_run())


def test_investigate_non_json() -> None:
    state = _mk_state({"signal": _mk_signal()})
    model = MagicMock()
    model.bind_tools = MagicMock(return_value=model)

    response = MagicMock()
    response.content = "The claim appears correct based on available evidence."
    response.tool_calls = []
    model.ainvoke = AsyncMock(return_value=response)

    async def _run() -> None:
        result = await investigate(state, model=model, tools=[])
        assert result["verdict"] == "inconclusive"
        assert "correct" in result["verdict_rationale"]

    asyncio.run(_run())


# --- emit_finding ---


def test_emit_finding_no_signal() -> None:
    state = _mk_state({"signal": None})

    async def _run() -> None:
        result = await emit_finding(state, db_client=MagicMock())
        assert result["completed"] is True

    asyncio.run(_run())


def test_emit_finding_emits() -> None:
    import shared.event_schemas.validator as val_mod
    original = val_mod.emit_validated

    captured: list[dict[str, Any]] = []

    async def mock_emit(event: dict[str, Any], *args: object, **kwargs: object) -> None:
        captured.append(event)

    val_mod.emit_validated = mock_emit
    try:
        state = _mk_state({
            "signal": _mk_signal(),
            "verdict": "confirmed",
            "verdict_confidence": 0.95,
            "verdict_rationale": "Verified independently",
        })

        async def _run() -> None:
            result = await emit_finding(state, db_client=MagicMock())
            assert result["completed"] is True
            assert len(captured) == 1
            assert captured[0]["event_type"] == "AgentFinding"
            assert captured[0]["verdict"] == "confirmed"

        asyncio.run(_run())
    finally:
        val_mod.emit_validated = original


# --- Graph compilation ---


def test_graph_compiles() -> None:
    from shared.arcadedb.client import ArcadeDBClient
    from shared.openrouter.models import (
        MODEL_ASSIGNMENTS,
        PROVIDER_ROUTING,
        AgentRole,
        ModelFamily,
    )

    model_name, _ = MODEL_ASSIGNMENTS[AgentRole.VERIFICATION]
    provider_config = PROVIDER_ROUTING[ModelFamily.QWEN]

    from langchain_openrouter import ChatOpenRouter

    model = ChatOpenRouter(
        model=model_name,
        api_key="sk-test",  # type: ignore[arg-type]
        openrouter_provider=provider_config,
    )

    db_client = ArcadeDBClient("http://localhost:2480", "db", "u", "p")
    tools: list[object] = []

    graph = build_verification_graph(model, db_client, tools, 0.6)
    assert graph is not None


# --- Routing ---


def test_route_completed() -> None:
    state = _mk_state({"completed": True})
    assert _route_after_poll(state) == "end"


def test_route_investigate() -> None:
    state = _mk_state({"completed": False})
    assert _route_after_poll(state) == "investigate"


# --- Model family detection ---


def test_model_family_exploratory() -> None:
    from agents.verification.nodes import _model_family_from_agent
    result = _model_family_from_agent("exploratory-test-mandate")
    from shared.openrouter.models import ModelFamily
    assert result == ModelFamily.DEEPSEEK


def test_model_family_verification() -> None:
    from agents.verification.nodes import _model_family_from_agent
    result = _model_family_from_agent("verification-20260101-120000")
    from shared.openrouter.models import ModelFamily
    assert result == ModelFamily.QWEN


# --- Module loading ---


def test_verification_main_module_imports() -> None:
    import importlib

    importlib.import_module("agents.verification.__main__")



# --- CLI entry point ---


def test_main_argument_parser() -> None:
    import sys
    from unittest.mock import patch

    with patch.object(sys, "argv", ["verification", "--config", "/tmp/cfg"]):
        with patch("agents.verification.asyncio.run", side_effect=SystemExit):
            try:
                import agents.verification
                agents.verification.main()
            except SystemExit:
                pass
