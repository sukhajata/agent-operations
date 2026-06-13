"""Postgres checkpointer factory for LangGraph state persistence.

Creates an AsyncPostgresSaver from the POSTGRES_URL environment variable.
Uses an async context manager so the connection pool is properly managed.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)


@asynccontextmanager
async def create_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """Create an async PostgresSaver from the POSTGRES_URL env var.

    Yields a connected saver with checkpoint tables created. The
    connection pool is closed when the context exits.
    """
    from config.env import settings

    logger.info("Creating Postgres checkpointer")
    async with AsyncPostgresSaver.from_conn_string(
        settings.postgres_url,
    ) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
