"""MCP (Model Context Protocol) connection manager.

Manages read-only connections to external MCP servers for artifact access.
All reads are gated by ACAP enforcement and logged to the event log.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import httpx

from shared.acap.enforcer import ACAPEnforcer
from shared.event_schemas.validator import emit_validated

if TYPE_CHECKING:
    from schema.identity.models import ACAPDefinition
    from shared.arcadedb.client import ArcadeDBClient

MCP_RPC_VERSION = "2.0"


class MCPConnectionManager:
    """Manages MCP connections to external artifact sources.

    Never caches responses — agents always get current state from the source.
    All reads are logged as AgentAction events with tool='mcp_read'.
    """

    def __init__(self, acap: ACAPDefinition, client: ArcadeDBClient) -> None:
        self._enforcer = ACAPEnforcer(acap, client)
        self._acap = acap
        self._client = client
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def close(self) -> None:
        await self._http.aclose()

    def list_permitted_connections(self) -> list[str]:
        """Return the list of URLs this agent is permitted to read from."""
        return list(self._acap.permitted_mcp_connections)

    async def read(
        self,
        server_url: str,
        resource_path: str,
        agent_id: str,
        focus_id: str,
        mtp_version: str,
        params: dict[str, Any] | None = None,
    ) -> str:
        """Read a resource from an MCP server.

        ACAP enforcement happens before any network call. Failed reads
        (including ACAP violations) do not log an AgentAction — only
        successful reads are logged.

        Args:
            server_url: The MCP server URL
            resource_path: The resource path/URI to read
            agent_id: Agent performing the read
            focus_id: Active focus
            mtp_version: Current MTP version
            params: Optional additional parameters

        Returns:
            Raw response content as a string

        Raises:
            ACAPViolationError: If server_url is not permitted
            httpx.RequestError: On connection failure
        """
        self._enforcer.check_mcp_connection(
            server_url, agent_id, focus_id, mtp_version
        )

        body: dict[str, Any] = {
            "jsonrpc": MCP_RPC_VERSION,
            "id": str(uuid.uuid4()),
            "method": "resources/read",
            "params": {"uri": resource_path},
        }
        if params:
            body["params"].update(params)

        response = await self._http.post(
            server_url,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        content = response.text

        await emit_validated(
            {
                "event_type": "AgentAction",
                "ts": datetime.now(UTC),
                "agent_id": agent_id,
                "commitment_id": None,
                "mtp_version": mtp_version,
                "payload": {
                    "tool": "mcp_read",
                    "server_url": server_url,
                    "resource_path": resource_path,
                },
            },
            self._client,
        )

        return content
