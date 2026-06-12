"""Implementation agent — dispatches approved commitments to the coding agent.

One-shot execution. Run as a cron job or serverless function. Each invocation:
  1. Finds the oldest approved commitment
  2. Validates the plan
  3. Dispatches to the coding agent via HTTP
  4. Sets the commitment status to 'executing' on successful dispatch
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import UTC, datetime

import httpx

logger = logging.getLogger(__name__)

CODING_AGENT_URL = os.environ.get("CODING_AGENT_URL", "http://localhost:8080")


async def run(config_path: str) -> int:
    """Find and dispatch one approved commitment. Returns number dispatched (0 or 1)."""
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.identity import update_commitment
    from shared.config.loader import load_project_config
    from shared.event_schemas.validator import emit_validated

    config = load_project_config(config_path)

    db_client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    agent_id = f"impl-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    mtp_version = config.mtp.version

    # Find oldest approved commitment
    records = await db_client.execute_query(
        "SELECT FROM CommitmentRecord WHERE status = 'approved' "
        "ORDER BY created_at ASC LIMIT 1",
    )

    if not records:
        logger.info("No approved commitments found")
        return 0

    record = records[0]
    created_at = record.get("created_at")
    if isinstance(created_at, str):
        record["created_at"] = datetime.fromisoformat(created_at)

    from schema.identity.models import CommitmentRecord
    commitment = CommitmentRecord.model_validate(record)
    commitment_id = commitment.commitment_id

    # Validate plan
    checkpoint = commitment.checkpoint
    if checkpoint is None or not checkpoint.plan or not checkpoint.plan.strip():
        logger.warning("Commitment %s has no plan — marking stalled", commitment_id)
        await update_commitment(db_client, commitment_id, {"status": "stalled"})
        return 0

    plan = checkpoint.plan
    logger.info(
        "Dispatching commitment %s to coding agent (%d char plan)",
        commitment_id, len(plan),
    )

    # Dispatch to coding agent
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0)) as http:
            response = await http.post(
                f"{CODING_AGENT_URL}/invocations",
                json={"prompt": plan},
            )
            response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("Failed to dispatch commitment %s: %s", commitment_id, e)
        await update_commitment(db_client, commitment_id, {"status": "stalled"})
        return 0

    # Set status to executing AFTER successful dispatch
    await update_commitment(db_client, commitment_id, {"status": "executing"})

    await emit_validated(
        {
            "event_type": "AgentAction",
            "ts": datetime.now(UTC),
            "agent_id": agent_id,
            "commitment_id": commitment_id,
            "mtp_version": mtp_version,
            "payload": {
                "action": "coding_agent_dispatched",
                "commitment_id": commitment_id,
            },
        },
        db_client,
    )

    logger.info(
        "Commitment %s dispatched — coding agent will update status on completion",
        commitment_id,
    )
    return 1


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Dispatch one approved commitment to the coding agent",
    )
    parser.add_argument(
        "--config",
        default="./config/reference",
        help="Path to configuration directory",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    import asyncio
    try:
        dispatched = asyncio.run(run(args.config))
        logger.info("Dispatched: %d", dispatched)
    except Exception as e:
        logger.error("Agent failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
