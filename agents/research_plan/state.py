"""Research/plan agent state definition."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from typing_extensions import TypedDict

from schema.identity.models import CommitmentRecord, HypothesisRecord
from schema.timeseries.event_log import AgentFinding


class ResearchPlanState(TypedDict):
    """State carried through the research/plan agent LangGraph.

    Polls for confirmed AgentFinding events, creates CommitmentRecords,
    runs a research loop, and produces an implementation plan for human
    approval.
    """

    finding: AgentFinding | None
    commitment: CommitmentRecord | None
    mtp_version: str
    agent_id: str
    graph_context: list[dict[str, Any]]
    artifact_context: list[str]
    event_delta: list[dict[str, Any]]
    hypotheses: list[HypothesisRecord]
    current_understanding: str | None
    plan: str | None
    iteration: int
    max_iterations: int
    last_cursor: datetime | None
    completed: bool
