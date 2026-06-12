"""Verification agent state definition."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from typing_extensions import TypedDict

from schema.timeseries.event_log import AgentSignal
from shared.openrouter.models import ModelFamily


class VerificationState(TypedDict):
    """State carried through the verification agent LangGraph.

    The agent polls for unverified AgentSignal observations, investigates
    them adversarially using a different model family, and emits an
    AgentFinding with a verdict.
    """

    signal: AgentSignal | None
    originating_model_family: ModelFamily
    mtp_version: str
    agent_id: str
    focus_id: str | None
    verdict: Literal["confirmed", "contradicted", "inconclusive"] | None
    verdict_confidence: float | None
    verdict_rationale: str | None
    last_cursor: datetime | None
    completed: bool
