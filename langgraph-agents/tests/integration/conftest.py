"""Integration test fixtures — gated on live infrastructure.

All fixtures skip when ARCADEDB_URL or POSTGRES_URL are not set
to real endpoints (not localhost or default test values).
"""
# ruff: noqa: ANN001, ANN201, ANN202
from __future__ import annotations

import os

import pytest


def _is_localhost(url: str) -> bool:
    """Check if a URL is a localhost/default test value."""
    return not url or "localhost" in url or url == "postgresql://localhost:5432/test"


def _require_real_infra() -> None:
    """Skip the current test if infrastructure env vars aren't pointing at real services."""
    arcadedb_url = os.environ.get("ARCADEDB_URL", "")
    postgres_url = os.environ.get("POSTGRES_URL", "")

    missing = []
    if _is_localhost(arcadedb_url):
        missing.append("ARCADEDB_URL")
    if _is_localhost(postgres_url):
        missing.append("POSTGRES_URL")

    if missing:
        pytest.skip(
            f"Integration test requires real infrastructure. "
            f"Set {' and '.join(missing)} to non-localhost values."
        )


@pytest.fixture(scope="session")
def require_infra() -> None:
    """Session-scoped fixture that skips all integration tests if infra is unavailable."""
    _require_real_infra()


@pytest.fixture
async def arcadedb_client():
    """Return a real ArcadeDBClient connected to the configured instance."""
    _require_real_infra()

    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient

    client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )
    yield client


@pytest.fixture
async def arcadedb_clean(arcadedb_client):  # noqa: ANN001, ANN201
    """Return a client and clean up test data after the test."""
    _require_real_infra()

    from shared.arcadedb.client import ArcadeDBClient

    client: ArcadeDBClient = arcadedb_client
    yield client

    # Clean up test data
    await client.execute_command(
        "DELETE FROM AgentSignal WHERE agent_id LIKE 'integration-test-%'",
    )
    await client.execute_command(
        "DELETE FROM AgentFinding WHERE agent_id LIKE 'integration-test-%'",
    )
    await client.execute_command(
        "DELETE FROM CommitmentRecord WHERE commitment_id LIKE 'integration-test-%'",
    )
    await client.execute_command(
        "DELETE FROM MandateRecord WHERE name LIKE 'integration-test-%'",
    )
    await client.execute_command(
        "DELETE FROM ProductStructure WHERE name LIKE 'integration-test-%'",
    )


@pytest.fixture
async def openrouter_model():  # noqa: ANN201
    """Return a real OpenRouter model client for integration tests."""
    _require_real_infra()

    from langchain_openrouter import ChatOpenRouter

    from config.env import settings
    from shared.openrouter.models import MODEL_ASSIGNMENTS, PROVIDER_ROUTING, AgentRole

    model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
    provider_config = PROVIDER_ROUTING[model_family]

    return ChatOpenRouter(
        model=model_name,
        api_key=settings.openrouter_api_key,
        openrouter_provider=provider_config,
        max_tokens=1024,
    )
