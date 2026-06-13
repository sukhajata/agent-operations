"""AWS Lambda entrypoint — dispatches to the right agent/function.

All Lambda functions share the same Docker image. The LAMBDA_HANDLER
environment variable determines which function to run.

Set LAMBDA_HANDLER to one of:
  - orchestrate           (functions.orchestration.run)
  - explore-dispatcher    (reads mandates from ArcadeDB, invokes AgentCore for each)
  - explore-run           (runs exploratory agent for a single mandate, invoked by AgentCore)
  - verify                (agents.verification.run_agent — one-shot mode)
  - migrate               (runs pending ArcadeDB schema migrations)
  - ui                    (ui.server:app — FastAPI via mangum)
"""

from __future__ import annotations

import asyncio
import logging
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: object, context: object) -> dict[str, object]:
    """AWS Lambda handler — dispatches based on LAMBDA_HANDLER."""
    handler_name = os.environ.get("LAMBDA_HANDLER", "orchestrate")
    config_path = os.environ.get("CONFIG_PATH", "./config/reference")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if handler_name == "orchestrate":
        from functions.orchestration import run
        counts = asyncio.run(run(config_path))
        return {"status": "ok", "counts": counts}

    if handler_name == "verify":
        from agents.verification import run_agent as verify_run
        asyncio.run(verify_run(config_path, polling_interval=0))
        return {"status": "ok"}

    if handler_name == "explore-dispatcher":
        from agents.exploratory import dispatch_to_agentcore
        results = asyncio.run(dispatch_to_agentcore())
        return {"status": "ok", "mandates_processed": len(results), "results": results}

    if handler_name == "explore-run":
        from agents.exploratory import run_agent as explore_run
        mandate_name = os.environ.get("MANDATE_NAME")
        if not mandate_name:
            return {"status": "error", "message": "MANDATE_NAME not set"}
        count = asyncio.run(explore_run(config_path, mandate_name))
        return {"status": "ok", "signals_emitted": count}

    if handler_name == "migrate":
        from config.env import settings
        from shared.arcadedb.client import ArcadeDBClient
        from schema.migrate import run_migrations

        client = ArcadeDBClient(
            url=settings.arcadedb_url,
            database="agent_operations",
            user=settings.arcadedb_user,
            password=settings.arcadedb_password,
        )
        count = asyncio.run(run_migrations(client))
        return {"status": "ok", "migrations_applied": count}

    if handler_name == "ui":
        from mangum import Mangum

        from ui.server import app
        mangum_handler = Mangum(app)
        return mangum_handler(event, context)  # type: ignore[return-value]

    return {"status": "error", "message": f"Unknown handler: {handler_name}"}
