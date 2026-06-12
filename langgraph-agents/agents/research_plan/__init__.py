"""Research/plan agent — polls for confirmed findings and produces plans.

Entry point: python -m agents.research_plan --config=path
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from typing import cast

from .graph import build_research_plan_graph
from .state import ResearchPlanState

logger = logging.getLogger(__name__)

DEFAULT_POLLING_INTERVAL = 60


async def run_agent(
    config_path: str,
    polling_interval: int = DEFAULT_POLLING_INTERVAL,
) -> None:
    """Run the research/plan agent in a continuous polling loop."""
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    from shared.config.loader import load_project_config
    from shared.mcp.manager import MCPConnectionManager
    from shared.openrouter.models import (
        MODEL_ASSIGNMENTS,
        PROVIDER_ROUTING,
        AgentRole,
    )

    config = load_project_config(config_path)

    db_client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.RESEARCH_PLAN]
    provider_config = PROVIDER_ROUTING[model_family]

    from langchain_openrouter import ChatOpenRouter

    model = ChatOpenRouter(
        model=model_name,
        api_key=settings.openrouter_api_key,  # type: ignore[arg-type]
        openrouter_provider=provider_config,
        max_tokens=4096,
    )

    # Load ACAP for MCP connection management
    acap = config.acap_overrides.get("research_plan")
    mcp = MCPConnectionManager(
        acap if acap else {"permitted_mcp_connections": [], "agent_type": "research_plan"},  # type: ignore[arg-type]
        db_client,
    )

    agent_id = f"research-plan-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    mtp_version = config.mtp.version

    graph = build_research_plan_graph(model, db_client, mcp)

    logger.info(
        "Research/plan agent %s starting (interval=%ds)",
        agent_id, polling_interval,
    )

    initial_state: ResearchPlanState = {
        "finding": None,
        "commitment": None,
        "mtp_version": mtp_version,
        "agent_id": agent_id,
        "graph_context": [],
        "artifact_context": [],
        "event_delta": [],
        "hypotheses": [],
        "current_understanding": None,
        "plan": None,
        "iteration": 0,
        "max_iterations": 3,
        "last_cursor": None,
        "completed": False,
    }

    while True:
        try:
            result = await graph.ainvoke(initial_state)
            initial_state = cast(ResearchPlanState, result)
            if result.get("commitment"):
                logger.info("Commitment created: %s", result["commitment"].commitment_id)
            if result.get("completed"):
                await asyncio.sleep(polling_interval)
        except Exception as e:
            logger.error("Research/plan agent error: %s", e)
            await asyncio.sleep(polling_interval)


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run research/plan agent")
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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        asyncio.run(run_agent(args.config, args.interval))
    except Exception as e:
        logger.error("Agent failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
