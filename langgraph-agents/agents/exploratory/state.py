"""Exploratory agent state definition."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from typing_extensions import TypedDict

from shared.config.loader import MandateDefinition


class ExploratoryState(TypedDict):
    """State carried through the exploratory agent LangGraph."""

    mandate: MandateDefinition
    mtp_version: str
    agent_id: str
    last_cursor: datetime | None
    messages: list[dict[str, Any]]
    signals_emitted: int
    run_at: datetime
    max_iterations: int
    completed: bool
    focus_id: str | None
