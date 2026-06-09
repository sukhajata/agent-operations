from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

import schema.migrate
from schema.migrate import compute_hash, run_migrations


class MockArcadeDBClient:
    """Mock ArcadeDB client that tracks commands and simulates migration tracking."""

    def __init__(self) -> None:
        self.commands: list[tuple[str, str]] = []
        self.queries: list[str] = []
        self._applied: dict[str, str] = {}

    async def execute_command(self, database: str, command: str) -> dict[str, Any]:
        self.commands.append((database, command))
        if "INSERT INTO SchemaMigration" in command:
            parts = command.split("'")
            if len(parts) >= 4:
                self._applied[parts[1]] = parts[3]
        return {"result": [{"count": 1}]}

    async def execute_query(
        self,
        database: str,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        self.queries.append(query)
        rows: list[dict[str, Any]] = []
        for migration_id, file_hash in self._applied.items():
            rows.append({
                "migration_id": migration_id,
                "file_hash": file_hash,
                "applied_at": "2026-01-01T00:00:00Z",
            })
        return rows

    def record_applied(self, migration_id: str, file_hash: str) -> None:
        self._applied[migration_id] = file_hash


@pytest.fixture
def migration_files(tmp_path: Path) -> dict[str, Path]:
    """Create temporary migration directories with test SQL files."""
    dirs: dict[str, Path] = {}
    for group_name in ("timeseries", "graph", "identity"):
        group_dir = tmp_path / group_name
        group_dir.mkdir()
        (group_dir / f"0001_create_{group_name}.sql").write_text(
            f"CREATE TYPE IF NOT EXISTS {group_name}_test;\n"
        )
        dirs[group_name] = group_dir
    return dirs


@pytest.fixture
def _patch_groups(migration_files: dict[str, Path]) -> Generator[None, None, None]:
    """Patch MIGRATION_GROUPS to point at temporary directories."""
    patched_groups = [
        ("timeseries", migration_files["timeseries"]),
        ("graph", migration_files["graph"]),
        ("identity", migration_files["identity"]),
    ]
    with patch.object(schema.migrate, "MIGRATION_GROUPS", patched_groups):
        yield


def test_run_migrations_applies_all_files(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    client = MockArcadeDBClient()
    count = asyncio.run(run_migrations(client))
    assert count == 3

    ddl_commands = [c for _, c in client.commands if "CREATE TYPE" in c.upper()]
    assert any("timeseries_test" in c for c in ddl_commands)
    assert any("graph_test" in c for c in ddl_commands)
    assert any("identity_test" in c for c in ddl_commands)


def test_run_migrations_is_idempotent(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    client = MockArcadeDBClient()

    count_first = asyncio.run(run_migrations(client))
    assert count_first == 3

    client2 = MockArcadeDBClient()
    for mid in client._applied:
        client2.record_applied(mid, client._applied[mid])

    count_second = asyncio.run(run_migrations(client2))
    assert count_second == 0

    ddl_commands = [c for _, c in client2.commands if "CREATE TYPE" in c.upper()]
    assert len(ddl_commands) == 0


def test_run_migrations_hash_enforcement(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    client = MockArcadeDBClient()

    asyncio.run(run_migrations(client))
    assert len(client._applied) == 3

    migration_dir = migration_files["timeseries"]
    migration_file = list(migration_dir.glob("*.sql"))[0]
    migration_file.write_text("CREATE TYPE IF NOT EXISTS modified_test;\n")

    client2 = MockArcadeDBClient()
    first_id = sorted(client._applied.keys())[0]
    client2.record_applied(first_id, "different-old-hash")

    with pytest.raises(RuntimeError, match="has been modified after it was applied"):
        asyncio.run(run_migrations(client2))


def test_run_migrations_execution_order(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    client = MockArcadeDBClient()
    asyncio.run(run_migrations(client))

    ddl_commands = [c for _, c in client.commands if "CREATE TYPE" in c.upper()]
    ts_idx = next(i for i, c in enumerate(ddl_commands) if "timeseries_test" in c)
    graph_idx = next(i for i, c in enumerate(ddl_commands) if "graph_test" in c)
    identity_idx = next(i for i, c in enumerate(ddl_commands) if "identity_test" in c)

    assert ts_idx < graph_idx < identity_idx


def test_run_migrations_empty_directories(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    for group_dir in migration_files.values():
        for f in group_dir.glob("*.sql"):
            f.unlink()

    client = MockArcadeDBClient()
    count = asyncio.run(run_migrations(client))
    assert count == 0


def test_run_migrations_missing_directory() -> None:
    missing_path = Path("/nonexistent/migrations/path")
    patched_groups = [("missing", missing_path)]
    with patch("schema.migrate.MIGRATION_GROUPS", patched_groups):
        client = MockArcadeDBClient()
        count = asyncio.run(run_migrations(client))
        assert count == 0


def test_compute_hash_is_deterministic(tmp_path: Path) -> None:
    f = tmp_path / "test.sql"
    f.write_text("CREATE TYPE test;")
    h1 = compute_hash(f)
    h2 = compute_hash(f)
    assert h1 == h2


def test_compute_hash_changes_with_content(tmp_path: Path) -> None:
    f = tmp_path / "test.sql"
    f.write_text("CREATE TYPE test;")
    h1 = compute_hash(f)
    f.write_text("CREATE TYPE different;")
    h2 = compute_hash(f)
    assert h1 != h2


def test_run_migrations_creates_schema_migration_document_type(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    client = MockArcadeDBClient()
    asyncio.run(run_migrations(client))

    doc_type_commands = [
        c
        for _, c in client.commands
        if "SchemaMigration" in c and "DOCUMENT TYPE" in c.upper()
    ]
    assert len(doc_type_commands) >= 1


def test_run_migrations_records_after_execution(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    client = MockArcadeDBClient()
    asyncio.run(run_migrations(client))

    insert_commands = [
        c for _, c in client.commands if "INSERT INTO SchemaMigration" in c
    ]
    assert len(insert_commands) == 3


def test_run_migrations_error_on_failing_statement(
    migration_files: dict[str, Path], _patch_groups: None
) -> None:
    migration_dir = migration_files["timeseries"]
    migration_file = list(migration_dir.glob("*.sql"))[0]
    migration_file.write_text(
        "CREATE TYPE IF NOT EXISTS ok_type;\n"
        "THIS IS NOT VALID SQL AND SHOULD CAUSE AN ERROR;\n"
    )

    class FailingClient(MockArcadeDBClient):
        async def execute_command(self, database: str, command: str) -> dict[str, Any]:
            if "NOT VALID" in command:
                raise RuntimeError("Simulated ArcadeDB error")
            return await super().execute_command(database, command)

    client = FailingClient()
    with pytest.raises(RuntimeError, match="Simulated ArcadeDB error"):
        asyncio.run(run_migrations(client))

    insert_commands = [
        c for _, c in client.commands if "INSERT INTO SchemaMigration" in c
    ]
    assert len(insert_commands) == 0
