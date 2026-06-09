"""Unified migration runner for Agent Operations schema.

Single entrypoint that coordinates migrations across all schema domains:
timeseries, graph, and identity. Tracks applied migrations in ArcadeDB document
type SchemaMigration, enforces immutability of previously-applied files via
SHA-256 hashing, and skips already-applied migrations.

Usage: python -m schema.migrate
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

logger = logging.getLogger(__name__)

SCHEMA_MIGRATION_DOCUMENT_TYPE = "SchemaMigration"
DEFAULT_DATABASE = "agent_operations"

MIGRATION_GROUPS: list[tuple[str, Path]] = [
    ("timeseries", Path(__file__).parent / "timeseries" / "migrations"),
    ("graph", Path(__file__).parent / "graph" / "migrations"),
    ("identity", Path(__file__).parent / "identity" / "migrations"),
]


class MigrationClientProtocol(Protocol):
    """Protocol defining the ArcadeDB client interface needed for unified migrations."""

    async def execute_command(self, database: str, command: str) -> dict[str, Any]: ...
    async def execute_query(
        self, database: str, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class AppliedMigration:
    """Record of a previously applied migration."""

    migration_id: str
    file_hash: str
    applied_at: datetime


def compute_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a migration file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _split_sql_statements(sql_content: str) -> list[str]:
    """Split SQL content into individual non-comment statements."""
    statements: list[str] = []
    for chunk in sql_content.split(";"):
        cleaned = "\n".join(
            line
            for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ).strip()
        if cleaned:
            statements.append(cleaned)
    return statements


async def _ensure_schema_migration_document_type(
    client: MigrationClientProtocol,
    database: str,
) -> None:
    """Create the SchemaMigration document type and properties if they don't exist."""
    await client.execute_command(
        database,
        f"CREATE DOCUMENT TYPE IF NOT EXISTS {SCHEMA_MIGRATION_DOCUMENT_TYPE}",
    )
    await client.execute_command(
        database,
        f"CREATE PROPERTY IF NOT EXISTS {SCHEMA_MIGRATION_DOCUMENT_TYPE}.migration_id STRING",
    )
    await client.execute_command(
        database,
        f"CREATE PROPERTY IF NOT EXISTS {SCHEMA_MIGRATION_DOCUMENT_TYPE}.file_hash STRING",
    )
    await client.execute_command(
        database,
        f"CREATE PROPERTY IF NOT EXISTS {SCHEMA_MIGRATION_DOCUMENT_TYPE}.applied_at DATETIME",
    )
    await client.execute_command(
        database,
        "CREATE INDEX IF NOT EXISTS SchemaMigration.migration_id "
        "ON SchemaMigration (migration_id) UNIQUE",
    )


async def _get_applied_migrations(
    client: MigrationClientProtocol,
    database: str,
) -> dict[str, AppliedMigration]:
    """Query all previously applied migrations, keyed by migration_id."""
    rows = await client.execute_query(
        database,
        f"SELECT FROM {SCHEMA_MIGRATION_DOCUMENT_TYPE}",
    )
    result: dict[str, AppliedMigration] = {}
    for row in rows:
        m = AppliedMigration(
            migration_id=row["migration_id"],
            file_hash=row["file_hash"],
            applied_at=row["applied_at"],
        )
        result[m.migration_id] = m
    return result


async def _record_migration(
    client: MigrationClientProtocol,
    database: str,
    migration_id: str,
    file_hash: str,
) -> None:
    """Record a successfully applied migration in SchemaMigration tracking table."""
    await client.execute_command(
        database,
        "INSERT INTO SchemaMigration SET "
        f"migration_id = '{migration_id}', "
        f"file_hash = '{file_hash}', "
        "applied_at = SYSDATE()",
    )


async def run_migrations(
    client: MigrationClientProtocol,
    database: str = DEFAULT_DATABASE,
) -> int:
    """Run all pending migrations across all schema groups in order.

    Args:
        client: ArcadeDB client implementing MigrationClientProtocol
        database: Database name to run migrations against

    Returns:
        Number of migrations applied during this run

    Raises:
        RuntimeError: If a previously-applied migration file has been modified
        Exception: If any migration statement fails to execute

    The runner is idempotent — already-applied migrations are skipped.
    Migration immutability is enforced via SHA-256 hash comparison.
    """
    await _ensure_schema_migration_document_type(client, database)
    applied = await _get_applied_migrations(client, database)

    total_applied = 0

    for group_name, migrations_dir in MIGRATION_GROUPS:
        if not migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {migrations_dir}")
            continue

        migration_files = sorted(migrations_dir.glob("*.sql"))

        if not migration_files:
            logger.info(f"No {group_name} migrations found")
            continue

        for file_path in migration_files:
            migration_id = file_path.name
            file_hash = compute_hash(file_path)

            if migration_id in applied:
                existing = applied[migration_id]
                if existing.file_hash != file_hash:
                    raise RuntimeError(
                        f"Migration file '{migration_id}' has been modified after "
                        f"it was applied. Original hash: {existing.file_hash}, "
                        f"current hash: {file_hash}"
                    )
                logger.info(f"Skipping already applied: {migration_id}")
                continue

            logger.info(f"Running migration: {group_name}/{migration_id}")
            sql_content = file_path.read_text()
            statements = _split_sql_statements(sql_content)

            for statement in statements:
                try:
                    await client.execute_command(database, statement)
                except Exception:
                    logger.error(
                        f"Migration failed: {migration_id}",
                    )
                    logger.error(f"Failing statement: {statement}")
                    raise

            await _record_migration(client, database, migration_id, file_hash)
            total_applied += 1
            logger.info(f"Applied: {migration_id}")

    return total_applied


def main() -> None:
    """CLI entry point — connects to ArcadeDB and runs all pending migrations."""
    import asyncio

    import httpx

    from config.env import settings

    base_url = settings.arcadedb_url.rstrip("/")

    class ArcadeDBConnection:
        """Minimal ArcadeDB HTTP connection for the migration CLI."""

        def __init__(self, url: str, user: str, password: str) -> None:
            self._url = url
            self._auth = (user, password)

        async def execute_command(self, database: str, command: str) -> dict[str, Any]:
            async with httpx.AsyncClient(
                auth=self._auth,
                timeout=httpx.Timeout(30.0),
            ) as client:
                response = await client.post(
                    f"{self._url}/api/v1/command/{database}",
                    content=command,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                return dict(response.json())

        async def execute_query(
            self,
            database: str,
            query: str,
            params: dict[str, Any] | None = None,
        ) -> list[dict[str, Any]]:
            body: dict[str, Any] = {"query": query}
            if params:
                body["params"] = params
            async with httpx.AsyncClient(
                auth=self._auth,
                timeout=httpx.Timeout(30.0),
            ) as client:
                response = await client.post(
                    f"{self._url}/api/v1/query/{database}",
                    json=body,
                )
                response.raise_for_status()
                data = response.json()
                return list(data.get("result", []))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    connection = ArcadeDBConnection(
        url=base_url,
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    count = asyncio.run(run_migrations(connection))
    logger.info(f"Migrations complete: {count} applied ({len(MIGRATION_GROUPS)} groups checked)")


if __name__ == "__main__":
    main()
