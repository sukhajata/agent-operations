"""ACAP (Access Control and Action Policy) enforcer.

Validates agent actions against their permitted scope before execution.
All violations are logged to ArcadeDB before the exception propagates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from schema.identity.models import ACAPDefinition

from .exceptions import ACAPViolationError

if TYPE_CHECKING:
    from shared.arcadedb.client import ArcadeDBClient


class ACAPEnforcer:
    """Enforces ACAP constraints on agent tool usage, MCP connections,
    event emissions, and resource consumption."""

    def __init__(self, acap: ACAPDefinition, client: ArcadeDBClient) -> None:
        self._acap = acap
        self._client = client

    def check_tool(
        self,
        tool_name: str,
        agent_id: str,
        objective_id: str,
        mtp_version: str,
    ) -> None:
        """Raise ACAPViolationError if tool_name is not permitted."""
        if tool_name not in self._acap.permitted_tools:
            violation = ACAPViolationError(
                action=f"use tool '{tool_name}'",
                reason="tool not in permitted_tools",
                agent_id=agent_id,
                objective_id=objective_id,
            )
            self.log_violation(violation, mtp_version)
            raise violation

    def check_mcp_connection(
        self,
        server_url: str,
        agent_id: str,
        objective_id: str,
        mtp_version: str,
    ) -> None:
        """Raise ACAPViolationError if server_url is not permitted."""
        if server_url not in self._acap.permitted_mcp_connections:
            violation = ACAPViolationError(
                action=f"connect to MCP server '{server_url}'",
                reason="server_url not in permitted_mcp_connections",
                agent_id=agent_id,
                objective_id=objective_id,
            )
            self.log_violation(violation, mtp_version)
            raise violation

    def check_event_type(
        self,
        event_type: str,
        agent_id: str,
        objective_id: str,
        mtp_version: str,
    ) -> None:
        """Raise ACAPViolationError if event_type is not permitted."""
        if event_type not in self._acap.permitted_event_types:
            violation = ACAPViolationError(
                action=f"emit event '{event_type}'",
                reason="event_type not in permitted_event_types",
                agent_id=agent_id,
                objective_id=objective_id,
            )
            self.log_violation(violation, mtp_version)
            raise violation

    def check_resource_ceiling(
        self,
        tokens_used: int,
        duration_seconds: float,
        mcp_reads: int,
        agent_id: str,
        objective_id: str,
        mtp_version: str,
    ) -> None:
        """Raise ACAPViolationError if any resource ceiling is exceeded."""
        ceiling = self._acap.resource_ceiling

        if tokens_used > ceiling.max_tokens_per_run:
            violation = ACAPViolationError(
                action="resource consumption",
                reason=(
                    f"tokens_used ({tokens_used}) exceeds "
                    f"max_tokens_per_run ({ceiling.max_tokens_per_run})"
                ),
                agent_id=agent_id,
                objective_id=objective_id,
            )
            self.log_violation(violation, mtp_version)
            raise violation

        if duration_seconds > ceiling.max_duration_seconds:
            violation = ACAPViolationError(
                action="resource consumption",
                reason=(
                    f"duration ({duration_seconds}s) exceeds "
                    f"max_duration_seconds ({ceiling.max_duration_seconds}s)"
                ),
                agent_id=agent_id,
                objective_id=objective_id,
            )
            self.log_violation(violation, mtp_version)
            raise violation

        if mcp_reads > ceiling.max_mcp_reads_per_run:
            violation = ACAPViolationError(
                action="resource consumption",
                reason=(
                    f"mcp_reads ({mcp_reads}) exceeds "
                    f"max_mcp_reads_per_run ({ceiling.max_mcp_reads_per_run})"
                ),
                agent_id=agent_id,
                objective_id=objective_id,
            )
            self.log_violation(violation, mtp_version)
            raise violation

    def log_violation(
        self,
        violation: ACAPViolationError,
        mtp_version: str,
    ) -> None:
        """Emit a violation event to ArcadeDB before the exception propagates.

        Uses fire-and-forget pattern — if emission fails, the violation
        still propagates. Violations are always logged on a best-effort basis.
        """
        try:
            import asyncio

            from schema.timeseries.event_log import AgentSignal
            from shared.arcadedb.timeseries import emit_event

            signal = AgentSignal(
                event_type="AgentSignal",
                ts=datetime.now(UTC),
                agent_id=violation.agent_id,
                objective_id=violation.objective_id,
                mtp_version=mtp_version,
                payload={
                    "violation_action": violation.action,
                    "violation_reason": violation.reason,
                },
                confidence=1.0,
                novelty_flag=True,
            )

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(emit_event(self._client, signal))
            except RuntimeError:
                asyncio.run(emit_event(self._client, signal))
        except Exception:
            pass
