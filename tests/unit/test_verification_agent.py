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

    cursor_ts = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)

    async def mock_poll(*args: object, **kwargs: object) -> list[dict[str, Any]]:
        return [
            {
                "event_type": "AgentSignal", "ts": SAMPLE_DATETIME_STR,
                "agent_id": "exploratory-test", "mtp_version": "1.0",
                "claim": "low", "domain": "test", "confidence": 0.3,
                "reasoning": "weak", "sources": [], "focus_id": None,
                "novelty_flag": False,
            },
            {
                "event_type": "AgentSignal", "ts": cursor_ts,
                "agent_id": "exploratory-test", "mtp_version": "1.0",
                "claim": "another", "domain": "test", "confidence": 0.2,
                "reasoning": "w", "sources": [], "focus_id": None,
                "novelty_flag": False,
            },
        ]

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
    async def mock_emit(**kwargs: object) -> None:
        pass

    state = _mk_state({"signal": None})

    async def _run() -> None:
        result = await emit_finding(state, emit_fn=mock_emit)
        assert result["completed"] is True

    asyncio.run(_run())


def test_emit_finding_calls_emit_fn() -> None:
    captured: list[dict[str, object]] = []

    async def mock_emit(**kwargs: object) -> str:
        captured.append(kwargs)
        return "ok"

    state = _mk_state({
        "signal": _mk_signal(),
        "verdict": "confirmed",
        "verdict_confidence": 0.95,
        "verdict_rationale": "Verified independently",
    })

    async def _run() -> None:
        result = await emit_finding(state, emit_fn=mock_emit)
        assert result["completed"] is True
        assert len(captured) == 1
        assert captured[0]["verdict"] == "confirmed"
        assert captured[0]["claim"] == "The auth module has a memory leak"

    asyncio.run(_run())


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

    async def mock_emit(**kwargs: object) -> str:
        return "ok"

    graph = build_verification_graph(model, db_client, tools, mock_emit, 0.6)
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




# --- CLI entry point ---


def test_main_argument_parser() -> None:
    import sys
    from unittest.mock import patch

    with patch.object(sys, "argv", ["verification", "--config", "/tmp/cfg"]):
        with patch("agents.verification.__init__.asyncio.run", side_effect=SystemExit("ok")):
            try:
                from agents.verification.__init__ import main
                main()
            except SystemExit:
                pass


def test_emit_finding_node_injects_emit_fn() -> None:
    """Verify the emit_finding node passes the right fields to emit_fn."""
    from agents.verification.nodes import emit_finding as _emit_finding

    captured: dict[str, object] = {}

    async def capture(**kwargs: object) -> str:
        captured.update(kwargs)
        return "ok"

    state = _mk_state({
        "signal": _mk_signal(),
        "verdict": "inconclusive",
        "verdict_confidence": 0.5,
        "verdict_rationale": "need more data",
    })

    async def _run() -> None:
        result = await _emit_finding(state, emit_fn=capture)
        assert result["completed"] is True
        assert captured["verdict"] == "inconclusive"
        assert "originating_signal_ts" in captured

    asyncio.run(_run())





def test_with_deps_wrapper_name() -> None:
    from agents.verification.graph import _with_deps
    async def mock_node(state: VerificationState) -> dict[str, Any]:
        return {"completed": True}
    wrapped = _with_deps(mock_node)
    assert wrapped.__name__ == "mock_node"
