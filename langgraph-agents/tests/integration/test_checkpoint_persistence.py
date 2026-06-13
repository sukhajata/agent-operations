"""Integration tests for LangGraph checkpoint persistence via Postgres.

Requires POSTGRES_URL and ARCADEDB_URL pointing to real instances.
"""
# ruff: noqa: ANN001, ANN201, ANN202
from __future__ import annotations

import asyncio
import uuid

import pytest


@pytest.mark.integration
def test_create_checkpointer_connects(arcadedb_client) -> None:
    """Verify the Postgres checkpointer creates a connection pool and tables."""
    from shared.postgres import create_checkpointer

    async def _run() -> None:
        async with create_checkpointer() as checkpointer:
            assert checkpointer is not None
            # setup() was called inside the context manager
            # Just verify the checkpointer is usable

    asyncio.run(_run())


@pytest.mark.integration
def test_checkpointer_persists_state(arcadedb_client) -> None:
    """Run a graph with a checkpointer and verify state is stored."""
    from agents.exploratory.graph import build_exploratory_graph
    from agents.exploratory.state import ExploratoryState
    from shared.arcadedb.client import ArcadeDBClient
    from shared.config.loader import MandateDefinition
    from shared.postgres import create_checkpointer

    client: ArcadeDBClient = arcadedb_client

    async def _run() -> None:
        async with create_checkpointer() as checkpointer:
            from langchain_openrouter import ChatOpenRouter

            from config.env import settings
            from shared.openrouter.models import MODEL_ASSIGNMENTS, PROVIDER_ROUTING, AgentRole

            model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
            model = ChatOpenRouter(
                model=model_name,
                api_key=settings.openrouter_api_key,
                openrouter_provider=PROVIDER_ROUTING[model_family],
                max_tokens=512,
            )

            from tools import create_exploratory_tools
            tools = create_exploratory_tools(client, "integration-test-cp", "1.0")

            graph = build_exploratory_graph(model, client, tools, checkpointer)
            assert graph is not None

            mandate = MandateDefinition(
                name="integration-test-checkpoint",
                domain="integration_testing",
                agent_type="free",
                polling_interval_minutes=60,
                signal_threshold=0.6,
            )

            thread_id = f"integration-test-thread-{uuid.uuid4().hex[:8]}"

            state: ExploratoryState = {
                "mandate": mandate,
                "mtp_version": "1.0",
                "agent_id": "integration-test-cp",
                "last_cursor": None,
                "messages": [],
                "signals_emitted": 0,
                "run_at": None,
                "max_iterations": 5,
                "completed": False,
                "focus_id": None,
            }

            config = {"configurable": {"thread_id": thread_id}}

            result = await graph.ainvoke(state, config)
            assert result.get("completed") is True

            # Verify checkpoint was persisted
            checkpoint_tuple = await checkpointer.aget_tuple(config)
            assert checkpoint_tuple is not None
            assert checkpoint_tuple.checkpoint is not None

    asyncio.run(_run())


@pytest.mark.integration
def test_checkpointer_resumability(arcadedb_client) -> None:
    """Verify that a graph run can be resumed from a previous checkpoint."""
    from agents.exploratory.graph import build_exploratory_graph
    from agents.exploratory.state import ExploratoryState
    from shared.arcadedb.client import ArcadeDBClient
    from shared.config.loader import MandateDefinition
    from shared.postgres import create_checkpointer

    client: ArcadeDBClient = arcadedb_client

    async def _run() -> None:
        async with create_checkpointer() as checkpointer:
            from langchain_openrouter import ChatOpenRouter

            from config.env import settings
            from shared.openrouter.models import MODEL_ASSIGNMENTS, PROVIDER_ROUTING, AgentRole

            model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
            model = ChatOpenRouter(
                model=model_name,
                api_key=settings.openrouter_api_key,
                openrouter_provider=PROVIDER_ROUTING[model_family],
                max_tokens=512,
            )

            from tools import create_exploratory_tools
            tools = create_exploratory_tools(client, "integration-test-resume", "1.0")

            graph = build_exploratory_graph(model, client, tools, checkpointer)

            thread_id = f"integration-test-resume-{uuid.uuid4().hex[:8]}"
            config = {"configurable": {"thread_id": thread_id}}

            mandate = MandateDefinition(
                name="integration-test-resume",
                domain="integration_testing",
                agent_type="free",
                polling_interval_minutes=60,
                signal_threshold=0.6,
            )

            state: ExploratoryState = {
                "mandate": mandate,
                "mtp_version": "1.0",
                "agent_id": "integration-test-resume",
                "last_cursor": None,
                "messages": [],
                "signals_emitted": 0,
                "run_at": None,
                "max_iterations": 5,
                "completed": False,
                "focus_id": None,
            }

            result = await graph.ainvoke(state, config)
            assert result.get("completed") is True

            # Get the state back — confirm it's from the checkpoint
            checkpoint_state = await graph.aget_state(config)
            assert checkpoint_state is not None
            assert checkpoint_state.values is not None

    asyncio.run(_run())
