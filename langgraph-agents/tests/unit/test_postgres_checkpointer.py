from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


def test_create_checkpointer_sets_up_and_yields() -> None:
    """Verify create_checkpointer calls setup() and yields the saver."""
    import asyncio

    mock_saver = MagicMock()
    mock_saver.setup = AsyncMock()

    async def _run() -> None:
        with patch(
            "shared.postgres.AsyncPostgresSaver.from_conn_string",
        ) as mock_from:
            mock_from.return_value.__aenter__ = AsyncMock(return_value=mock_saver)
            mock_from.return_value.__aexit__ = AsyncMock(return_value=None)

            from shared.postgres import create_checkpointer

            async with create_checkpointer() as saver:
                assert saver is mock_saver
                mock_saver.setup.assert_awaited_once()

    asyncio.run(_run())
