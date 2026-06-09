from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from agents.exploratory.graph import build_exploratory_graph
from agents.exploratory.nodes import MAX_ITERATIONS, OBSERVE_SYSTEM_PROMPT
from agents.exploratory.state import ExploratoryState
from shared.config.loader import MandateDefinition


def _make_mandate() -> MandateDefinition:
    return MandateDefinition(
        name="test_mandate",
        domain="competitive_intelligence",
        agent_type="free",
        polling_interval_minutes=30,
        signal_threshold=0.6,
    )


def _make_state() -> ExploratoryState:
    return {
        "mandate": _make_mandate(),
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
) -> object:
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


# --- Helpers ---


def _make_async_mock_response(
    status_code: int = 200, result: list[dict[str, Any]] | None = None
) -> AsyncMock:
    response = AsyncMock()
    response.is_success = status_code < 400
    response.status_code = status_code
    response.json = lambda: {"result": result or []}
    return response


def _make_mock_generation(text: str) -> object:
    gen = MagicMock()
    gen.text = text
    gen.generations = [[gen]]
    gen.llm_output = {}
    gen.run = []
    gen.message = _mock_aimessage(text)
    return gen
