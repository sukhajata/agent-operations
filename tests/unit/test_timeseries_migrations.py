import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from schema.timeseries import run_migrations


@pytest.mark.asyncio
async def test_run_migrations_executes_all_statements() -> None:
    mock_client = AsyncMock()
    mock_client.execute_command = AsyncMock(return_value={})

    await run_migrations(mock_client, "testdb")

    assert mock_client.execute_command.call_count > 0
    for call in mock_client.execute_command.call_args_list:
        assert call.args[0] == "testdb"


@pytest.mark.asyncio
async def test_run_migrations_executes_if_not_exists_statements() -> None:
    mock_client = AsyncMock()
    mock_client.execute_command = AsyncMock(return_value={})

    await run_migrations(mock_client, "testdb")

    for call in mock_client.execute_command.call_args_list:
        stmt = call.args[1]
        if "CREATE" in stmt:
            assert "IF NOT EXISTS" in stmt


@pytest.mark.asyncio
async def test_run_migrations_handles_empty_directory() -> None:
    """Test that runner handles empty migrations directory gracefully."""
    mock_client = AsyncMock()

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("schema.timeseries.MIGRATIONS_DIR", Path(tmpdir)):
            await run_migrations(mock_client, "testdb")

    mock_client.execute_command.assert_not_called()


@pytest.mark.asyncio
async def test_run_migrations_propagates_errors() -> None:
    """Test that migration errors are propagated with context."""
    mock_client = AsyncMock()
    mock_client.execute_command = AsyncMock(side_effect=Exception("Database error"))

    with pytest.raises(Exception, match="Database error"):
        await run_migrations(mock_client, "testdb")
