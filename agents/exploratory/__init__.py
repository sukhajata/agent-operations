"""Exploratory agent — investigates domains and emits novel signals.

Entry point: python -m agents.exploratory --config=path --mandate=name
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime

from .graph import build_exploratory_graph
from .state import ExploratoryState

logger = logging.getLogger(__name__)


async def run_agent(
    config_path: str,
    mandate_name: str,
) -> int:
    """Run the exploratory agent for a given mandate."""
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    from shared.config.loader import load_project_config
    from shared.openrouter.models import MODEL_ASSIGNMENTS, PROVIDER_ROUTING, AgentRole
    from tools import create_exploratory_tools

    config = load_project_config(config_path)

    mandate = next(
        (m for m in config.mandates if m.name == mandate_name), None
    )
    if mandate is None:
        raise ValueError(f"Mandate '{mandate_name}' not found in {config_path}")

    db_client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
    provider_config = PROVIDER_ROUTING[model_family]

    from langchain_openrouter import ChatOpenRouter

    model = ChatOpenRouter(
        model=model_name,
        api_key=settings.openrouter_api_key,  # type: ignore[arg-type]
        openrouter_provider=provider_config,
        max_tokens=4096,
    )

    agent_id = f"exploratory-{mandate_name}"
    mtp_version = config.mtp.version

    focus_id: str | None = None
    if mandate.agent_type == "focus":
        if mandate.focus_id is None:
            raise ValueError(
                f"Mandate '{mandate_name}' has agent_type='focus' but no focus_id configured"
            )
        focus_id = mandate.focus_id

    tools = create_exploratory_tools(db_client, agent_id, mtp_version, focus_id)
    graph = build_exploratory_graph(model, db_client, tools)

    initial_state: ExploratoryState = {
        "mandate": mandate,
        "mtp_version": mtp_version,
        "agent_id": agent_id,
        "last_cursor": None,
        "messages": [],
        "signals_emitted": 0,
        "run_at": datetime.now(UTC),
        "max_iterations": 10,
        "completed": False,
        "focus_id": focus_id,
    }

    result = await graph.ainvoke(initial_state)
    signals = result.get("signals_emitted", 0)
    logger.info(f"Exploratory agent {agent_id}: emitted {signals} signals")
    return int(signals)


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run exploratory agent")
    parser.add_argument(
        "--config",
        default="./config/reference",
        help="Path to configuration directory",
    )
    parser.add_argument(
        "--mandate",
        required=True,
        help="Mandate name to execute",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        count = asyncio.run(run_agent(args.config, args.mandate))
        logger.info(f"Completed: {count} signals emitted")
    except Exception as e:
        logger.error(f"Agent failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
