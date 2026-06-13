"""Orchestration — dispatches, monitors, promotes, and maintains the system.

One-shot execution. Run as a cron job. Each invocation:
  0. Dispatches approved commitments to the coding agent
  1. Detects stalled executing commitments
  2. Promotes findings from completed commitments to the knowledge graph
  3. Runs confidence decay on the knowledge graph

The orchestration agent does NOT coordinate other agents — each polls independently.
"""

from __future__ import annotations

import logging
import os
import sys
import uuid
from datetime import UTC, datetime, timedelta

from shared.status import (
    ACTIVE,
    APPROVED,
    COMPLETE,
    EXECUTING,
    IN_PROGRESS,
    STALLED,
)

logger = logging.getLogger(__name__)

CODING_AGENT_ID = os.environ.get("CODING_AGENT_ID", "")
STALL_HOURS = 6


async def run(config_path: str) -> dict[str, int]:
    """Run a single orchestration cycle. Returns counts of actions taken."""
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    from shared.arcadedb.identity import update_commitment
    from shared.event_schemas.validator import emit_validated

    db_client = ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )

    counts: dict[str, int] = {
        "dispatched": 0, "stalled_escalated": 0, "promoted": 0, "decayed": 0,
    }

    # ── 0. Dispatch approved commitments to the coding agent ─────────────
    from schema.identity.models import CommitmentRecord

    approved = await db_client.execute_query(
        f"SELECT FROM CommitmentRecord WHERE status = '{APPROVED}' "
        "ORDER BY created_at ASC LIMIT 1",
    )
    if approved:
        record = approved[0]
        created_at = record.get("created_at")
        if isinstance(created_at, str):
            record["created_at"] = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        commitment = CommitmentRecord.model_validate(record)
        cid = commitment.commitment_id
        checkpoint = commitment.checkpoint
        repo = commitment.repository_url or ""
        branch = commitment.base_branch or "main"
        claim = ""
        if checkpoint:
            claim = checkpoint.current_best_understanding or ""
        domain = commitment.domain

        task = (
            f"Commitment ID: {cid}\n"
            f"Repository: {repo}\n"
            f"Base Branch: {branch}\n"
            f"Domain: {domain}\n"
            f"Claim: {claim}\n\n"
            f"Research the codebase, plan the implementation, make the changes, "
            f"create a PR, and report the result back to ArcadeDB."
        )
        if checkpoint and checkpoint.plan:
            task += f"\n\nApproved plan context:\n{checkpoint.plan[:2000]}"

        try:
            from shared.bedrock_agent import invoke_bedrock_agent

            session_id = f"orch-{cid}-{uuid.uuid4().hex[:8]}"
            await invoke_bedrock_agent(CODING_AGENT_ID, session_id, task)
            await update_commitment(
                db_client,
                cid,
                {"status": EXECUTING, "implementation_state": IN_PROGRESS},
            )
                {
                    "event_type": "AgentAction",
                    "ts": datetime.now(UTC).isoformat(),
                    "agent_id": f"orch-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
                    "commitment_id": cid,
                    "mtp_version": "1.0",
                    "payload": {
                        "action": "coding_agent_dispatched",
                        "commitment_id": cid,
                        "repository_url": repo,
                        "base_branch": branch,
                    },
                },
                db_client,
            )
            counts["dispatched"] += 1
            logger.info("Dispatched commitment %s to coding agent", cid)
        except Exception as e:
            logger.error("Failed to dispatch %s: %s", cid, e)
            await update_commitment(db_client, cid, {"status": STALLED})

    # ── 1. Detect stalled executing commitments ──────────────────────────
    cutoff = datetime.now(UTC) - timedelta(hours=STALL_HOURS)
    stalled = await db_client.execute_query(
        "SELECT FROM CommitmentRecord "
        f"WHERE status IN ('{ACTIVE}', '{EXECUTING}') "
        f"AND implementation_state = '{IN_PROGRESS}'",
    )
    for record in stalled:
        checkpoint = record.get("checkpoint")
        if isinstance(checkpoint, dict):
            last_checkpoint = checkpoint.get("checkpoint_at")
            if isinstance(last_checkpoint, str):
                last_checkpoint = datetime.fromisoformat(last_checkpoint.replace("Z", "+00:00"))
            if isinstance(last_checkpoint, datetime) and last_checkpoint < cutoff:
                cid = str(record.get("commitment_id", ""))
                await update_commitment(db_client, cid, {"status": STALLED})
                counts["stalled_escalated"] += 1
                logger.warning("Escalated stalled commitment: %s", cid)

    # ── 2. Promote findings from closed commitments ──────────────────────
    completed = await db_client.execute_query(
        f"SELECT FROM CommitmentRecord WHERE status = '{COMPLETE}'",
    )
    for record in completed:
        cid = str(record.get("commitment_id", ""))
        domain = str(record.get("domain", ""))

        # Read associated finding events
        findings = await db_client.execute_query(
            "SELECT FROM AgentFinding WHERE domain = :domain LIMIT 20",
            {"domain": domain},
        )
        if findings:
            from schema.graph.node_types import DECAY_RATES, GraphNode
            from shared.arcadedb.graph import upsert_node
            from shared.promotion.classifier import classify_for_promotion

            for finding_dict in findings:
                claim = str(finding_dict.get("claim", ""))
                confidence = float(finding_dict.get("confidence", 0.5))
                reason = str(finding_dict.get("reasoning", ""))

                # Look for existing nodes that overlap
                existing = await db_client.execute_query(
                    "SELECT FROM InvestigationFinding LIMIT 20",
                )

                # Build a lightweight event for classification
                class _LightweightEvent:
                    def __init__(self) -> None:
                        self.claim = claim
                        self.confidence = confidence
                        self.reasoning = reason

                decision = classify_for_promotion(
                    _LightweightEvent(),  # type: ignore[arg-type]
                    existing,
                )

                if decision.action in ("promote_durable", "promote_medium") and decision.node_type:
                    safe_claim = "".join(
                        ch if ch.isalnum() else "-" for ch in claim.lower()
                    )[:40].strip("-")
                    node = GraphNode(
                        node_id=f"promoted-{decision.node_type}-{safe_claim}",
                        node_type=decision.node_type,
                        confidence=confidence,
                        initial_confidence=confidence,
                        decay_rate=DECAY_RATES[decision.node_type],
                        last_reinforced=datetime.now(UTC),
                        revalidation_required=False,
                    )
                    await upsert_node(db_client, node)
                    counts["promoted"] += 1

                elif decision.action == "reinforce" and decision.node_id:
                    from shared.arcadedb.graph import reinforce_node
                    await reinforce_node(db_client, decision.node_id)
                    counts["promoted"] += 1

    # ── 3. Run confidence decay ─────────────────────────────────────────
    from shared.arcadedb.graph import apply_decay_all
    decayed = await apply_decay_all(db_client)
    counts["decayed"] = decayed

    logger.info(
        "Orchestration cycle complete: stalled=%d promoted=%d decayed=%d",
        counts["stalled_escalated"], counts["promoted"], counts["decayed"],
    )
    return counts


def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run orchestration cycle")
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
        counts = asyncio.run(run(args.config))
        logger.info("Orchestration cycle: %s", counts)
    except Exception as e:
        logger.error("Orchestration agent failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
