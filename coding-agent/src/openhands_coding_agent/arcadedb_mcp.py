#!/usr/bin/env python3
"""MCP server exposing commitment status updates to the coding agent.

Connected tools:
  - commitment_update_status: mark commitment as complete or failed
  - commitment_get: read commitment details

Uses the standard MCP stdio transport. Configured via environment variables:
  - ARCADEDB_URL (required)
  - ARCADEDB_DATABASE (default: agent_operations)
  - ARCADEDB_USER (required)
  - ARCADEDB_PASSWORD (required)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx

ARCADEDB_URL = os.environ["ARCADEDB_URL"]
ARCADEDB_DATABASE = os.environ.get("ARCADEDB_DATABASE", "agent_operations")
ARCADEDB_USER = os.environ["ARCADEDB_USER"]
ARCADEDB_PASSWORD = os.environ["ARCADEDB_PASSWORD"]


async def _execute_command(command: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    auth = (ARCADEDB_USER, ARCADEDB_PASSWORD)
    body: dict[str, Any] = {"language": "sql", "command": command, "params": params}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), auth=auth) as http:
        response = await http.post(
            f"{ARCADEDB_URL}/api/v1/command/{ARCADEDB_DATABASE}",
            json=body,
        )
        response.raise_for_status()
        return list(response.json().get("result", []))


async def commitment_update_status(params: dict[str, Any]) -> dict[str, Any]:
    """Update a commitment's status. Set to 'complete' on success, 'stalled' on failure."""
    await _execute_command(
        "UPDATE CommitmentRecord SET status = :status WHERE commitment_id = :commitment_id",
        {"commitment_id": params["commitment_id"], "status": params["status"]},
    )
    return {"ok": True}


async def commitment_get(params: dict[str, Any]) -> dict[str, Any]:
    """Read a commitment record by ID."""
    records = await _execute_command(
        "SELECT FROM CommitmentRecord WHERE commitment_id = :commitment_id LIMIT 1",
        {"commitment_id": params["commitment_id"]},
    )
    return records[0] if records else {"error": "not found"}


TOOLS = {
    "commitment_update_status": commitment_update_status,
    "commitment_get": commitment_get,
}


async def _handle_request(req: dict[str, Any]) -> dict[str, Any]:
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "arcadedb-commitments", "version": "0.1.0"},
            },
        }

    if method == "tools/list":
        tool_schemas = [
            {
                "name": "commitment_update_status",
                "description": (
                    "Update the status of a commitment record in ArcadeDB. "
                    "Must be called exactly once at the end of every execution. "
                    "The commitment_id is provided in the plan preamble at the "
                    "start of the task (look for 'Commitment ID: com-...'). "
                    "Set status to 'complete' if all steps were implemented, "
                    "verified, and reviewed. Set status to 'stalled' if the "
                    "plan could not be completed (missing info, blocked, or "
                    "failed tests after 5 review attempts)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "commitment_id": {
                            "type": "string",
                            "description": "The commitment ID from the plan preamble (e.g. 'com-focus-001')",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["complete", "stalled"],
                            "description": "'complete' if plan fully executed, 'stalled' if blocked or failed",
                        },
                    },
                    "required": ["commitment_id", "status"],
                },
            },
        ]
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": tool_schemas},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}
        result = await TOOLS[tool_name](tool_args)
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(result)}],
                "isError": False,
            },
        }

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


async def main() -> None:
    reader = sys.stdin.buffer
    writer = sys.stdout.buffer

    while True:
        line = reader.readline()
        if not line:
            break
        req = json.loads(line.decode())
        resp = await _handle_request(req)
        writer.write(json.dumps(resp).encode() + b"\n")
        writer.flush()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
