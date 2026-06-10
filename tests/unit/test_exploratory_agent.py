from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from agents.exploratory.graph import build_exploratory_graph
from agents.exploratory.nodes import MAX_ITERATIONS, OBSERVE_SYSTEM_PROMPT
from agents.exploratory.state import ExploratoryState
from shared.config.loader import MandateDefinition


def _make_mandate(agent_type: str = "free") -> MandateDefinition:
    return MandateDefinition(
        name="test_mandate",
        domain="competitive_intelligence",
        agent_type=agent_type,
        polling_interval_minutes=30,
        signal_threshold=0.6,
    )


def _make_state(agent_type: str = "free") -> ExploratoryState:
    return {
        "mandate": _make_mandate(agent_type),
        "mtp_version": "1.0",
        "agent_id": "agent-test-1",
        "last_cursor": None,
        "messages": [],
        "signals_emitted": 0,
        "run_at": datetime.now(UTC),
        "max_iterations": MAX_ITERATIONS,
        "completed": False,
        "focus_id": None,
    }


def _mock_aimessage(
    content: str = "SUMMARY: Done.",
    tool_calls: list[object] | None = None,
) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    return msg


# --- Tool definitions ---


def test_tools_create_exploratory_tools_returns_list() -> None:
    from shared.arcadedb.client import ArcadeDBClient
    from tools import create_exploratory_tools

    client = ArcadeDBClient("http://localhost:2480", "db", "u", "p")
    tools = create_exploratory_tools(client, "agent-1", "1.0")
    assert len(tools) == 3
    names = [t.name for t in tools]
    assert "search_graph" in names
    assert "search_signals" in names
    assert "emit_signal" in names


# --- system prompt ---


def test_system_prompt_includes_domain() -> None:
    prompt = OBSERVE_SYSTEM_PROMPT.format(
        domain="competitive_intelligence",
        mandate_name="test",
        signal_threshold=0.6,
    )
    assert "competitive_intelligence" in prompt
    assert "test" in prompt
    assert "0.6" in prompt


def test_focus_prompt_includes_focus() -> None:
    from agents.exploratory.nodes import OBSERVE_FOCUS_PROMPT

    prompt = OBSERVE_FOCUS_PROMPT.format(
        domain="test_domain",
        focus_summary="Investigate performance regression",
        signal_threshold=0.7,
    )
    assert "test_domain" in prompt
    assert "performance regression" in prompt


# --- graph compilation ---


def test_graph_compiles() -> None:
    from shared.arcadedb.client import ArcadeDBClient
    from shared.openrouter.models import (
        MODEL_ASSIGNMENTS,
        PROVIDER_ROUTING,
        AgentRole,
        ModelFamily,
    )

    model_name, _ = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
    provider_config = PROVIDER_ROUTING[ModelFamily.DEEPSEEK]

    from langchain_openrouter import ChatOpenRouter

    model = ChatOpenRouter(
        model=model_name,
        api_key="sk-test",  # type: ignore[arg-type]
        openrouter_provider=provider_config,
    )

    db_client = ArcadeDBClient("http://localhost:2480", "db", "u", "p")
    tools: list[object] = []

    graph = build_exploratory_graph(model, db_client, tools)
    assert graph is not None


def test_graph_compiles_from_package() -> None:
    from agents.exploratory.graph import build_exploratory_graph as _build
    assert _build is not None


# --- node tests ---


def test_load_context_loads_mtp() -> None:
    from agents.exploratory.nodes import load_context

    client = MagicMock()
    client.execute_query = AsyncMock(return_value=[{
        "mtp_id": "mtp-1", "version": "2.0", "purpose": "test",
        "constraints": [], "intent_description": "test",
        "created_at": "2026-01-01T00:00:00Z", "created_by": "tester",
    }])

    async def _run() -> None:
        result = await load_context(_make_state(), db_client=client)
        assert result["mtp_version"] == "2.0"

    import asyncio
    asyncio.run(_run())


def test_load_context_no_mtp() -> None:
    from agents.exploratory.nodes import load_context

    client = MagicMock()
    client.execute_query = AsyncMock(return_value=[])

    async def _run() -> None:
        result = await load_context(_make_state(), db_client=client)
        assert result == {}

    import asyncio
    asyncio.run(_run())


def test_update_cursor_sets_timestamps() -> None:
    from agents.exploratory.nodes import update_cursor

    async def _run() -> None:
        result = await update_cursor(_make_state())
        assert "last_cursor" in result
        assert "run_at" in result

    import asyncio
    asyncio.run(_run())


def test_observe_free_mode_produces_summary() -> None:
    from agents.exploratory.nodes import observe

    state = _make_state(agent_type="free")
    model = MagicMock()
    mock_response = _mock_aimessage(content="SUMMARY: Explored domain. No novel findings.")
    mock_response.tool_calls = []
    model.bind_tools = MagicMock(return_value=model)
    model.ainvoke = AsyncMock(return_value=mock_response)

    async def _run() -> None:
        result = await observe(state, model=model, tools=[])
        assert result["completed"] is True
        assert "messages" in result

    import asyncio
    asyncio.run(_run())


def test_observe_focus_mode_produces_summary() -> None:
    from agents.exploratory.nodes import observe

    state = _make_state(agent_type="focus")
    model = MagicMock()
    mock_response = _mock_aimessage(content="SUMMARY: Investigated focus. No novel findings.")
    mock_response.tool_calls = []
    model.bind_tools = MagicMock(return_value=model)
    model.ainvoke = AsyncMock(return_value=mock_response)

    async def _run() -> None:
        result = await observe(state, model=model, tools=[])
        assert result["completed"] is True

    import asyncio
    asyncio.run(_run())


def test_observe_respects_max_iterations() -> None:
    from agents.exploratory.nodes import observe

    state = _make_state(agent_type="free")
    state["max_iterations"] = 2
    model = MagicMock()
    mock_response = _mock_aimessage(content="Still investigating...")
    mock_response.tool_calls = []
    model.bind_tools = MagicMock(return_value=model)
    model.ainvoke = AsyncMock(return_value=mock_response)

    async def _run() -> None:
        result = await observe(state, model=model, tools=[])
        assert result["completed"] is True

    import asyncio
    asyncio.run(_run())


def test_observe_uses_existing_messages() -> None:
    from agents.exploratory.nodes import observe

    state = _make_state(agent_type="free")
    state["messages"] = [{"role": "assistant", "content": "previous message"}]
    model = MagicMock()
    mock_response = _mock_aimessage(content="SUMMARY: Done.")
    mock_response.tool_calls = []
    model.bind_tools = MagicMock(return_value=model)
    model.ainvoke = AsyncMock(return_value=mock_response)

    async def _run() -> None:
        result = await observe(state, model=model, tools=[])
        assert result["completed"] is True

    import asyncio
    asyncio.run(_run())

