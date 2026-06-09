"""Signal log search tool.

Searches recent AgentSignal events to avoid emitting near-duplicates.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from langchain_core.tools import tool

from shared.arcadedb.client import ArcadeDBClient
from shared.arcadedb.timeseries import poll_events


def create_search_signals_tool(client: ArcadeDBClient) -> Any:  # noqa: ANN401
    """Create a search_signals tool bound to an ArcadeDB client."""

    @tool
    async def search_signals(domain: str, query: str) -> str:
        """Search the recent signal log for previously emitted signals.

        Returns signals from the last 7 days that may be similar to what
        you're investigating. Use this to avoid emitting near-duplicate
        signals.

        Args:
            domain: The domain to search in
            query: Natural language description of what you're looking for
        """
        since = datetime.now(UTC) - timedelta(days=7)
        events = await poll_events(
            client,
            event_type="AgentSignal",
            since_ts=since,
            limit=100,
        )
        if not events:
            return "No recent signals found in this domain."
        return str(events)

    return search_signals
