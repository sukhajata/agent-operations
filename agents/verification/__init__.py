"""Verification agent — polls for observations and issues verdicts.

Entry point: python -m agents.verification --config=path
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from typing import cast

from .graph import build_verification_graph
from .state import VerificationState

logger = logging.getLogger(__name__)

DEFAULT_POLLING_INTERVAL = 60
DEFAULT_SIGNAL_THRESHOLD = 0.6


async def run_agent(
    config_path: str,
    polling_interval: int = DEFAULT_POLLING_INTERVAL,
    signal_threshold: float = DEFAULT_SIGNAL_THRESHOLD,
) -> None:
    """Run the verification agent in a continuous polling loop.

    Polls the event log for unverified AgentSignal observations, investigates
    each adversarially using a different model family, and emits AgentFinding
    events with verdicts.
    """
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    from shared.config.loader import load_project_config
    from shared.openrouter.models import (
        MODEL_ASSIGNMENTS,
        PROVIDER_ROUTING,
        AgentRole,
        ModelFamily,
    )
    from tools import create_exploratory_tools

    config = load_project_config(config_path)

    db_client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.VERIFICATION]
    provider_config = PROVIDER_ROUTING[model_family]

    from langchain_openrouter import ChatOpenRouter

    model = ChatOpenRouter(
        model=model_name,
        api_key=settings.openrouter_api_key,  # type: ignore[arg-type]
        openrouter_provider=provider_config,
        max_tokens=4096,
    )

    agent_id = f"verification-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    mtp_version = config.mtp.version

    tools = create_exploratory_tools(db_client, agent_id, mtp_version)
    graph = build_verification_graph(model, db_client, tools, signal_threshold)

    logger.info(
        "Verification agent %s starting (threshold=%.2f, interval=%ds)",
        agent_id, signal_threshold, polling_interval,
    )

    initial_state: VerificationState = {
        "signal": None,
        "originating_model_family": ModelFamily.DEEPSEEK,
        "mtp_version": mtp_version,
        "agent_id": agent_id,
        "focus_id": None,
        "verdict": None,
        "verdict_confidence": None,
        "verdict_rationale": None,
        "last_cursor": None,
        "completed": False,
    }

    while True:
        try:
            result = await graph.ainvoke(initial_state)
            if result.get("verdict"):
                logger.info(
                    "Verdict: %s (%.2f) — %s",
                    result["verdict"], result.get("verdict_confidence", 0),
                    result.get("verdict_rationale", "")[:120],
                )
            initial_state = cast(VerificationState, result)
            await asyncio.sleep(polling_interval)
        except Exception as e:
            logger.error("Verification agent error: %s", e)
            await asyncio.sleep(polling_interval)


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run verification agent")
    parser.add_argument(
        "--config",
        default="./config/reference",
        help="Path to configuration directory",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_POLLING_INTERVAL,
        help=f"Polling interval in seconds (default: {DEFAULT_POLLING_INTERVAL})",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_SIGNAL_THRESHOLD,
        help=f"Minimum signal confidence to investigate (default: {DEFAULT_SIGNAL_THRESHOLD})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        asyncio.run(run_agent(args.config, args.interval, args.threshold))
    except Exception as e:
        logger.error("Agent failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
