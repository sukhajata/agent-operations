"""Signal emission tool.

Emits validated AgentSignal events to the event log.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.tools import tool

from shared.arcadedb.client import ArcadeDBClient
from shared.event_schemas.validator import emit_validated


def create_emit_signal_tool(
    client: ArcadeDBClient,
    agent_id: str,
    mtp_version: str,
    focus_id: str | None = None,
) -> Any:  # noqa: ANN401
    """Create an emit_signal tool bound to a specific agent.

    Args:
        client: ArcadeDB client for event emission
        agent_id: The agent emitting signals
        mtp_version: Current MTP version
        focus_id: ObjectiveRecord ID being followed, or None for free exploration
    """

    @tool
    async def emit_signal(
        claim: str,
        domain: str,
        confidence: float,
        reasoning: str,
        sources: list[str],
        is_novel: bool,
    ) -> str:
        """Emit a new exploratory signal to the event log.

        Only call this AFTER confirming the observation is genuinely novel
        and not already known in the graph or recent signals. Provide a
        confidence score (0.0-1.0) reflecting your certainty.

        Args:
            claim: The novel claim being asserted
            domain: The domain this claim belongs to
            confidence: Confidence in this claim (0.0-1.0)
            reasoning: Chain of reasoning that led to this claim
            sources: Citations or references supporting this claim
            is_novel: True if genuinely novel, not covered by existing graph nodes
        """
        signal: dict[str, Any] = {
            "event_type": "AgentSignal",
            "ts": datetime.now(UTC).isoformat(),
            "agent_id": agent_id,
            "mtp_version": mtp_version,
            "claim": claim,
            "domain": domain,
            "confidence": confidence,
            "reasoning": reasoning,
            "sources": sources,
            "focus_id": focus_id,
            "novelty_flag": is_novel,
        }
        await emit_validated(signal, client)
        return f"Signal emitted: domain={domain}, confidence={confidence}"

    return emit_signal
