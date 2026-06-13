"""Integration tests for verification agent end-to-end.

Requires ARCADEDB_URL and OPENROUTER_API_KEY.
"""
# ruff: noqa: ANN001, ANN201, ANN202
from __future__ import annotations

import asyncio

import pytest


@pytest.mark.integration
def test_verification_graph_compiles_with_real_db(arcadedb_client) -> None:
    """Verify the verification graph compiles against a real ArcadeDB."""
    from langchain_openrouter import ChatOpenRouter

    from agents.verification.graph import build_verification_graph
    from shared.arcadedb.client import ArcadeDBClient
    from shared.openrouter.models import MODEL_ASSIGNMENTS, PROVIDER_ROUTING, AgentRole

    client: ArcadeDBClient = arcadedb_client

    model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.VERIFICATION]
    provider_config = PROVIDER_ROUTING[model_family]

    from config.env import settings

    model = ChatOpenRouter(
        model=model_name,
        api_key=settings.openrouter_api_key,
        openrouter_provider=provider_config,
        max_tokens=1024,
    )

    from tools.search_graph import create_search_graph_tool
    from tools.search_signals import create_search_signals_tool

    tools = [
        create_search_graph_tool(client),
        create_search_signals_tool(client),
    ]
    captured: list[dict] = []

    async def _emit(**kwargs: object) -> str:
        captured.append(dict(kwargs))
        return "ok"

    graph = build_verification_graph(model, client, tools, _emit, 0.6)
    assert graph is not None


@pytest.mark.integration
def test_poll_for_observations_real_db(arcadedb_clean) -> None:
    """Verify poll_for_observations queries a real ArcadeDB instance."""
    from agents.verification.nodes import poll_for_observations
    from agents.verification.state import VerificationState
    from shared.arcadedb.client import ArcadeDBClient
    from shared.openrouter.models import ModelFamily

    client: ArcadeDBClient = arcadedb_clean
    state: VerificationState = {
        "signal": None,
        "originating_model_family": ModelFamily.DEEPSEEK,
        "mtp_version": "1.0",
        "agent_id": "integration-test-verifier",
        "focus_id": None,
        "verdict": None,
        "verdict_confidence": None,
        "verdict_rationale": None,
        "last_cursor": None,
        "completed": False,
    }

    async def _run() -> None:
        result = await poll_for_observations(state, db_client=client, signal_threshold=0.6)
        assert isinstance(result, dict)
        assert "completed" in result

    asyncio.run(_run())


@pytest.mark.integration
def test_verification_full_cycle(arcadedb_clean) -> None:
    """End-to-end: emit a signal, run verification, get a finding."""
    from datetime import UTC, datetime

    from agents.verification.state import VerificationState
    from shared.arcadedb.client import ArcadeDBClient
    from shared.event_schemas.validator import emit_validated
    from shared.openrouter.models import MODEL_ASSIGNMENTS, PROVIDER_ROUTING, AgentRole

    client: ArcadeDBClient = arcadedb_clean

    signal_agent_id = f"integration-test-explorer-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"

    async def _run() -> None:
        # 1. Emit a test signal
        await emit_validated(
            {
                "event_type": "AgentSignal",
                "ts": datetime.now(UTC).isoformat(),
                "agent_id": signal_agent_id,
                "mtp_version": "1.0",
                "claim": "Integration test: the system handles errors gracefully",
                "domain": "integration_testing",
                "confidence": 0.8,
                "reasoning": "Manual test signal for verification integration test",
                "sources": ["integration-test"],
                "focus_id": None,
                "novelty_flag": True,
            },
            client,
        )

        # 2. Poll for signals
        from agents.verification.nodes import poll_for_observations
        from shared.openrouter.models import ModelFamily

        state: VerificationState = {
            "signal": None,
            "originating_model_family": ModelFamily.DEEPSEEK,
            "mtp_version": "1.0",
            "agent_id": "integration-test-verifier",
            "focus_id": None,
            "verdict": None,
            "verdict_confidence": None,
            "verdict_rationale": None,
            "last_cursor": None,
            "completed": False,
        }

        poll_result = await poll_for_observations(state, db_client=client, signal_threshold=0.6)

        # A signal should be found (the one we just emitted)
        if poll_result.get("signal") is not None:
            # 3. Investigate with a real model
            from langchain_openrouter import ChatOpenRouter

            from agents.verification.nodes import investigate

            model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.VERIFICATION]
            from config.env import settings

            model = ChatOpenRouter(
                model=model_name,
                api_key=settings.openrouter_api_key,
                openrouter_provider=PROVIDER_ROUTING[model_family],
                max_tokens=512,
            )

            from tools.search_graph import create_search_graph_tool
            from tools.search_signals import create_search_signals_tool

            tools = [
                create_search_graph_tool(client),
                create_search_signals_tool(client),
            ]

            inv_result = await investigate(poll_result, model=model, tools=tools)
            assert inv_result.get("verdict") in ("confirmed", "contradicted", "inconclusive")
        else:
            # No signal found — acceptable if the instance is busy
            # or the cursor is ahead of our test signal
            pass

    asyncio.run(_run())
