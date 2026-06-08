"""TimeSeries schema migration runner.

Executes TimeSeries migrations idempotently against ArcadeDB.
All migration SQL uses CREATE TYPE IF NOT EXISTS and CREATE PROPERTY IF NOT EXISTS,
making the runner safe to execute multiple times.
"""

import logging
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class ArcadeDBClientProtocol(Protocol):
    """Protocol defining the ArcadeDB client interface needed for migrations."""

    async def execute_command(self, database: str, command: str) -> dict[str, Any]: ...


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations(client: ArcadeDBClientProtocol, database: str) -> None:
    """Execute all TimeSeries migrations in filename order.

    Args:
        client: ArcadeDB client instance
        database: Database name to run migrations against

    Raises:
        FileNotFoundError: If migrations directory doesn't exist
        Exception: If any migration statement fails

    The migrations are idempotent - safe to run multiple times.
    """
    if not MIGRATIONS_DIR.exists():
        raise FileNotFoundError(f"Migrations directory not found: {MIGRATIONS_DIR}")

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    if not migration_files:
        logger.info("No TimeSeries migrations found")
        return

    for migration_file in migration_files:
        logger.info(f"Running migration: {migration_file.name}")
        sql_content = migration_file.read_text()

        # Split into individual statements (strip comment lines before splitting/executing)
        statements: list[str] = []
        for chunk in sql_content.split(";"):
            cleaned = "\n".join(
                line
                for line in chunk.splitlines()
                if line.strip() and not line.strip().startswith("--")
            ).strip()
            if cleaned:
                statements.append(cleaned)

        for statement in statements:
            try:
                await client.execute_command(database, statement)
            except Exception as e:
                logger.error(f"Migration failed: {migration_file.name}")
                logger.error(f"Statement: {statement}")
                logger.error(f"Error: {e}")
                raise
