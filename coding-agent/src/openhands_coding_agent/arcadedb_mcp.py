#!/usr/bin/env python3
"""MCP server for the coding agent to report results to ArcadeDB.

Tools:
  - commitment_complete: set status='complete', PR URL, and summary
  - commitment_stall: set status='stalled' with reason
  - commitment_get: read commitment details (repo URL, branch, finding)

Uses MCP stdio transport. Env vars:
  - ARCADEDB_URL, ARCADEDB_USER, ARCADEDB_PASSWORD
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


async def commitment_complete(params: dict[str, Any]) -> dict[str, Any]:
    """Mark commitment complete with PR URL and summary."""
    await _execute_command(
        "UPDATE CommitmentRecord SET status = :status, pr_url = :pr_url, "
        "summary = :summary WHERE commitment_id = :commitment_id",
        {
            "commitment_id": params["commitment_id"],
            "status": "complete",
            "pr_url": params.get("pr_url", ""),
            "summary": params.get("summary", ""),
        },
    )
    return {"ok": True}


async def commitment_stall(params: dict[str, Any]) -> dict[str, Any]:
    """Mark commitment stalled with a summary."""
    await _execute_command(
        "UPDATE CommitmentRecord SET status = :status, summary = :summary "
        "WHERE commitment_id = :commitment_id",
        {
            "commitment_id": params["commitment_id"],
            "status": "stalled",
            "summary": params.get("summary", "unknown"),
        },
    )
    return {"ok": True}


async def commitment_get(params: dict[str, Any]) -> dict[str, Any]:
    """Read commitment details from ArcadeDB."""
    records = await _execute_command(
        "SELECT FROM CommitmentRecord WHERE commitment_id = :commitment_id LIMIT 1",
        {"commitment_id": params["commitment_id"]},
    )
    return records[0] if records else {"error": "not found"}


TOOLS: dict[str, Any] = {
    "commitment_complete": commitment_complete,
    "commitment_stall": commitment_stall,
    "commitment_get": commitment_get,
}


async def _handle_request(req: dict[str, Any]) -> dict[str, Any]:
    method = req.get("method", "")
    req_id = req.get("id")
    params = req.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "arcadedb-commitments", "version": "0.2.0"},
            },
        }

    if method == "tools/list":
        tool_schemas = [
            {
                "name": "commitment_complete",
                "description": (
                    "Mark a commitment as complete with the PR URL and a summary "
                    "of what was done. Call this after creating the PR. "
                    "The commitment_id is provided in the task preamble."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "commitment_id": {
                            "type": "string",
                            "description": "Commitment ID from the task preamble",
                        },
                        "pr_url": {
                            "type": "string",
                            "description": "URL of the created pull request",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Summary of what was changed, how it was verified",
                        },
                    },
                    "required": ["commitment_id", "pr_url", "summary"],
                },
            },
            {
                "name": "commitment_stall",
                "description": (
                    "Mark a commitment as stalled when work cannot proceed. "
                    "Call this if you cannot complete the task."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "commitment_id": {"type": "string"},
                        "summary": {
                            "type": "string",
                            "description": "Why the task cannot be completed",
                        },
                    },
                    "required": ["commitment_id", "summary"],
                },
            },
            {
                "name": "commitment_get",
                "description": (
                    "Read a commitment record from ArcadeDB. Returns the "
                    "repository_url, base_branch, and finding claim."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "commitment_id": {"type": "string"},
                    },
                    "required": ["commitment_id"],
                },
            },
        ]
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tool_schemas}}

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        if tool_name not in TOOLS:
            return {
                "jsonrpc": "2.0", "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
            }
        result = await TOOLS[tool_name](tool_args)
        return {
            "jsonrpc": "2.0", "id": req_id,
            "result": {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False},
        }

    return {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


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
