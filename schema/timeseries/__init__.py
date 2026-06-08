"""TimeSeries schema migration runner.

Executes TimeSeries migrations idempotently against ArcadeDB.
All migration SQL uses CREATE TYPE IF NOT EXISTS and CREATE PROPERTY IF NOT EXISTS,
making the runner safe to execute multiple times.
"""

from pathlib import Path
from typing import Any, Protocol


class ArcadeDBClientProtocol(Protocol):
    """Protocol defining the ArcadeDB client interface needed for migrations."""

    async def execute_command(self, database: str, command: str) -> dict[str, Any]: ...


MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations(client: ArcadeDBClientProtocol, database: str) -> None:
    """Execute all TimeSeries migrations in filename order.

    Args:
        client: ArcadeDB client instance
        database: Database name to run migrations against

    The migrations are idempotent - safe to run multiple times.
    """
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    for migration_file in migration_files:
        sql_content = migration_file.read_text()

        # Split into individual statements (skip empty lines and comments)
        statements = [
            stmt.strip()
            for stmt in sql_content.split(";")
            if stmt.strip() and not stmt.strip().startswith("--")
        ]

        for statement in statements:
            await client.execute_command(database, statement)
