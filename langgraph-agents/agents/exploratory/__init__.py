"""Exploratory agent — investigates domains and emits novel signals.

Entry point: python -m agents.exploratory --config=path --mandate=name
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

from .graph import build_exploratory_graph
from .state import ExploratoryState

logger = logging.getLogger(__name__)


async def dispatch_to_agentcore() -> list[dict[str, object]]:
    """Read active mandates from ArcadeDB and invoke AgentCore for each.

    Uses boto3 bedrock-agent-runtime.invoke_agent() to dispatch
    each mandate to the Bedrock AgentCore exploratory agent.

    Returns a list of results, one per mandate processed.
    """
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.identity import get_active_mandates

    db_client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    mandates = await get_active_mandates(db_client)

    if not mandates:
        logger.info("No active mandates found")
        return []

    agent_id_param = os.environ.get("AGENTCORE_AGENT_ID")
    if not agent_id_param:
        logger.error("AGENTCORE_AGENT_ID not set")
        return []

    async def _dispatch_one(mandate: Any) -> dict[str, object]:  # noqa: ANN401
        """Dispatch a single mandate to the Bedrock agent."""
        prompt = (
            f"Execute the mandate '{mandate.name}' in domain '{mandate.domain}' "
            f"as a {mandate.agent_type} agent."
        )
        if mandate.focus_id:
            prompt += f" Focus on focus_id: {mandate.focus_id}."

        session_id = f"explore-{mandate.name}-{uuid.uuid4().hex[:8]}"
        try:
            from shared.bedrock_agent import invoke_bedrock_agent

            completion = await invoke_bedrock_agent(
                agent_id_param, session_id, prompt,
            )
            logger.info("Mandate %s invoked successfully", mandate.name)
            return {
                "mandate_name": mandate.name,
                "status": "dispatched",
                "completion": completion[:500] if completion else "",
            }
        except Exception as e:
            logger.error("Failed to invoke mandate %s: %s", mandate.name, e)
            return {
                "mandate_name": mandate.name,
                "status": "failed",
                "error": str(e),
            }

    results = await asyncio.gather(*[_dispatch_one(m) for m in mandates])
    return list(results)


async def run_agent(
    config_path: str,
    mandate_name: str | None = None,
) -> int:
    """Run the exploratory agent for all active mandates in ArcadeDB.

    Reads mandates from ArcadeDB instead of YAML config files. If mandate_name
    is provided, runs only that mandate (for CLI/testing compatibility).
    Returns total signals emitted.
    """
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.identity import get_active_mandates
    from shared.config.loader import MandateDefinition, load_project_config
    from shared.openrouter.models import MODEL_ASSIGNMENTS, PROVIDER_ROUTING, AgentRole
    from tools import create_exploratory_tools

    config = load_project_config(config_path)
    db_client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    # Read mandates from ArcadeDB
    if mandate_name:
        mandates = await get_active_mandates(db_client)
        mandates = [m for m in mandates if m.name == mandate_name]
    else:
        mandates = await get_active_mandates(db_client)

    if not mandates:
        logger.info("No active mandates found")
        return 0

    model_name, model_family = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
    provider_config = PROVIDER_ROUTING[model_family]

    from langchain_openrouter import ChatOpenRouter

    model = ChatOpenRouter(
        model=model_name,
        api_key=settings.openrouter_api_key,  # type: ignore[arg-type]
        openrouter_provider=provider_config,
        max_tokens=4096,
    )

    from shared.postgres import create_checkpointer

    mtp_version = config.mtp.version

    async with create_checkpointer() as checkpointer:
        async def process_mandate(mandate: Any) -> int:  # noqa: ANN001, ANN401
            """Process a single mandate and return signals emitted."""
            agent_id = f"exploratory-{mandate.name}"
            focus_id = mandate.focus_id if mandate.agent_type == "focus" else None

            tools = create_exploratory_tools(db_client, agent_id, mtp_version, focus_id)
            graph = build_exploratory_graph(model, db_client, tools, checkpointer)

            initial_state: ExploratoryState = {
                "mandate": MandateDefinition(
                    name=mandate.name,
                    domain=mandate.domain,
                    agent_type=mandate.agent_type,
                    polling_interval_minutes=mandate.polling_interval_minutes,
                    signal_threshold=mandate.signal_threshold,
                    focus_id=mandate.focus_id,
                ),
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
            logger.info("Exploratory agent %s: emitted %d signals", agent_id, signals)
            return int(signals)

        # Process all mandates in parallel
        results = await asyncio.gather(*[process_mandate(m) for m in mandates])
        total_signals = sum(results)

    return total_signals


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
