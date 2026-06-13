"""Human approval UI — CopilotKit backend with ArcadeDB tools.

Provides a conversational interface for humans to review pending commitments,
approve/reject/defer them, and query system state.

Start with: uv run uvicorn ui.server:app --port 3001
"""  # noqa: E501 — long JSON schema strings in action definitions

from __future__ import annotations

import json
import logging
import os
import secrets
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

UI_USERNAME = os.environ.get("UI_USERNAME", "admin")
UI_PASSWORD = os.environ.get("UI_PASSWORD", "agentops")

app = FastAPI(title="Agent Operations UI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def basic_auth(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response | JSONResponse:
    if request.url.path in ("/ping", "/health"):
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        import base64
        try:
            decoded = base64.b64decode(auth[6:]).decode()
            user, _, pwd = decoded.partition(":")
            match_user = secrets.compare_digest(user, UI_USERNAME)
            match_pwd = secrets.compare_digest(pwd, UI_PASSWORD)
            if match_user and match_pwd:
                return await call_next(request)
        except Exception:
            pass
    return JSONResponse(
        status_code=401,
        content={"detail": "Unauthorized"},
        headers={"WWW-Authenticate": "Basic"},
    )


async def _get_db():  # noqa: ANN202
    from config.env import settings
    from shared.arcadedb.client import ArcadeDBClient
    return ArcadeDBClient(
        url=settings.arcadedb_url,
        database="agent_operations",
        user=settings.arcadedb_user,
        password=settings.arcadedb_password,
    )


def _serialize_dt(v: object) -> str:
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v) if v else ""


async def _list_pending() -> list[dict[str, object]]:
    db = await _get_db()
    try:
        records = await db.execute_query(
            "SELECT FROM CommitmentRecord WHERE status = 'pending_approval' "
            "ORDER BY created_at ASC LIMIT 20",
        )
        result: list[dict[str, object]] = []
        for r in records:
            checkpoint = r.get("checkpoint")
            plan = ""
            understanding = ""
            if isinstance(checkpoint, dict):
                plan = str(checkpoint.get("plan", ""))[:500]
                understanding = str(checkpoint.get("current_best_understanding", ""))[:500]
            result.append({
                "commitment_id": r.get("commitment_id"),
                "domain": r.get("domain"),
                "priority_signal": r.get("priority_signal"),
                "created_at": _serialize_dt(r.get("created_at")),
                "plan_preview": plan,
                "understanding": understanding,
            })
        return result
    finally:
        await db.close()


async def _get_status() -> dict[str, object]:
    db = await _get_db()
    try:
        pending = await db.execute_query(
            "SELECT COUNT(*) as count FROM CommitmentRecord WHERE status = 'pending_approval'",
        )
        executing = await db.execute_query(
            "SELECT COUNT(*) as count FROM CommitmentRecord WHERE status = 'executing'",
        )
        completed = await db.execute_query(
            "SELECT COUNT(*) as count FROM CommitmentRecord WHERE status = 'complete'",
        )
        return {
            "pending_approval": pending[0].get("count", 0) if pending else 0,
            "executing": executing[0].get("count", 0) if executing else 0,
            "completed": completed[0].get("count", 0) if completed else 0,
        }
    finally:
        await db.close()


# ── CopilotKit-compatible actions ──────────────────────────────────────


@app.get("/api/actions")
async def list_actions():  # noqa: ANN201
    """Return available actions for the CopilotKit frontend."""
    return {
        "actions": [
            {
                "name": "listPendingApprovals",
                "description": (
                    "List all commitments waiting for human approval. "
                    "Shows domain, plan preview, and understanding."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "getSystemStatus",
                "description": (
                    "Get counts of pending approvals, executing commitments, "
                    "and completed commitments."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "approveCommitment",
                "description": (
                    "Approve a commitment for implementation. "
                    "The implementation agent will pick it up."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commitment_id": {
                            "type": "string",
                            "description": "The commitment ID to approve",
                        },
                        "comments": {
                            "type": "string",
                            "description": "Optional comments",
                        },
                    },
                    "required": ["commitment_id"],
                },
            },
            {
                "name": "rejectCommitment",
                "description": (
                    "Reject a commitment. Provide a reason so the "
                    "research/plan agent can improve it."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commitment_id": {
                            "type": "string",
                            "description": "The commitment ID to reject",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why the commitment is being rejected",
                        },
                    },
                    "required": ["commitment_id", "reason"],
                },
            },
            {
                "name": "deferCommitment",
                "description": "Defer a commitment for later review. Provide a reason.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commitment_id": {
                            "type": "string",
                            "description": "The commitment ID to defer",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why the commitment is being deferred",
                        },
                    },
                    "required": ["commitment_id", "reason"],
                },
            },
        ]
    }


@app.post("/api/actions/execute")
async def execute_action(body: dict[str, Any]):  # noqa: ANN201
    """Execute a named action and return the result."""
    from shared.arcadedb.identity import update_commitment
    from shared.status import APPROVED, DEFERRED, REJECTED

    action_name = body.get("action", "")
    params = body.get("parameters", {})

    if action_name == "listPendingApprovals":
        return {"result": await _list_pending()}

    if action_name == "getSystemStatus":
        return {"result": await _get_status()}

    if action_name == "approveCommitment":
        commitment_id = str(params.get("commitment_id", ""))
        if not commitment_id:
            return {"error": "commitment_id required"}
        db = await _get_db()
        try:
            await update_commitment(db, commitment_id, {"status": APPROVED})
            return {"result": f"Commitment {commitment_id} approved"}
        finally:
            await db.close()

    if action_name == "rejectCommitment":
        commitment_id = str(params.get("commitment_id", ""))
        reason = str(params.get("reason", ""))
        if not commitment_id:
            return {"error": "commitment_id required"}
        db = await _get_db()
        try:
            await update_commitment(db, commitment_id, {"status": REJECTED})
            return {"result": f"Commitment {commitment_id} rejected: {reason}"}
        finally:
            await db.close()

    if action_name == "deferCommitment":
        commitment_id = str(params.get("commitment_id", ""))
        reason = str(params.get("reason", ""))
        if not commitment_id:
            return {"error": "commitment_id required"}
        db = await _get_db()
        try:
            await update_commitment(db, commitment_id, {"status": DEFERRED})
            return {"result": f"Commitment {commitment_id} deferred: {reason}"}
        finally:
            await db.close()

    return {"error": f"Unknown action: {action_name}"}


@app.get("/api/pending")
async def pending():  # noqa: ANN201
    return {"pending": await _list_pending()}


@app.get("/api/status")
async def status():  # noqa: ANN201
    return await _get_status()


@app.get("/ping")
async def ping():  # noqa: ANN201
    return {"status": "ok"}


# ── Mandate management ────────────────────────────────────────────────

@app.get("/api/mandates")
async def list_mandates() -> dict[str, object]:
    from shared.arcadedb.identity import get_all_mandates

    db = await _get_db()
    try:
        mandates = await get_all_mandates(db)
        return {"mandates": [m.model_dump(mode="json") for m in mandates]}
    finally:
        await db.close()


@app.post("/api/mandates")
async def create_mandate_ep(body: dict[str, object]) -> dict[str, object]:
    from schema.identity.models import MandateRecord
    from shared.arcadedb.identity import create_mandate as _create

    db = await _get_db()
    try:
        mandate = MandateRecord.model_validate(body)
        await _create(db, mandate)
        return {"ok": True, "mandate_id": mandate.mandate_id}
    finally:
        await db.close()


@app.put("/api/mandates/{mandate_id}")
async def update_mandate_ep(mandate_id: str, body: dict[str, object]) -> dict[str, object]:
    from shared.arcadedb.identity import update_mandate as _update

    db = await _get_db()
    try:
        await _update(db, mandate_id, dict(body))
        return {"ok": True}
    finally:
        await db.close()


@app.delete("/api/mandates/{mandate_id}")
async def delete_mandate_ep(mandate_id: str) -> dict[str, object]:
    from shared.arcadedb.identity import delete_mandate as _delete

    db = await _get_db()
    try:
        await _delete(db, mandate_id)
        return {"ok": True}
    finally:
        await db.close()


# ── Event log ──────────────────────────────────────────────────────────

@app.get("/api/events/recent")
async def events_recent(limit: int = 50, domain: str = "") -> dict[str, object]:
    db = await _get_db()
    try:
        from shared.arcadedb.timeseries import poll_events

        # Last 24h window
        since = datetime.now() - __import__("datetime").timedelta(hours=24)
        since = since.replace(tzinfo=__import__("datetime").timezone.utc)

        signals = await poll_events(db, "AgentSignal", since, limit=limit)
        findings = await poll_events(db, "AgentFinding", since, limit=limit)

        events = []
        for s in signals:
            if domain and s.get("domain") != domain:
                continue
            events.append({
                "type": "signal",
                "ts": _serialize_dt(s.get("ts")),
                "agent_id": s.get("agent_id"),
                "domain": s.get("domain"),
                "claim": (s.get("claim") or "")[:300],
                "confidence": s.get("confidence"),
                "focus_id": s.get("focus_id"),
                "novelty_flag": s.get("novelty_flag"),
            })
        for f in findings:
            if domain and f.get("domain") != domain:
                continue
            events.append({
                "type": "finding",
                "ts": _serialize_dt(f.get("ts")),
                "agent_id": f.get("agent_id"),
                "domain": f.get("domain"),
                "claim": (f.get("claim") or "")[:300],
                "confidence": f.get("confidence"),
                "verdict": f.get("verdict"),
                "verdict_rationale": (f.get("reasoning") or "")[:300],
                "focus_id": f.get("focus_id"),
            })

        events.sort(key=lambda e: e["ts"], reverse=True)
        return {"events": events[:limit]}
    finally:
        await db.close()


# ── Chat with LLM + tool calling ───────────────────────────────────────

CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": (
                "Run a SELECT query against ArcadeDB. "
                "Use for questions about commitments, signals, findings, or system state."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {"type": "string", "description": "SELECT query to run"},
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pending",
            "description": "List commitments waiting for human approval.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_status",
            "description": "Get counts of pending, executing, and completed commitments.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_commitment",
            "description": "Approve a commitment so the implementation agent picks it up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_id": {"type": "string"},
                    "comments": {"type": "string"},
                },
                "required": ["commitment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reject_commitment",
            "description": "Reject a commitment with a reason.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["commitment_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "defer_commitment",
            "description": "Defer a commitment for later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["commitment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_commitment_detail",
            "description": "Get the full plan and research context for a commitment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "commitment_id": {"type": "string"},
                },
                "required": ["commitment_id"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are the Agent Operations approval assistant. You help humans
review implementation plans and manage the system.

Key concepts:
- Commitments move through: pending → active → pending_approval → approved → executing → complete
- Commitments in 'pending_approval' need human action (approve/reject/defer)
- The CommitmentRecord table stores all commitments. Key fields:
  commitment_id, status, domain, priority_signal, checkpoint
  (embedded with plan, current_best_understanding, hypotheses_investigated)
- AgentFinding events have verdicts (confirmed/contradicted/inconclusive)
- AgentSignal events are exploratory observations

When a human asks to approve something, find the commitment_id first (list them if needed),
show the plan summary, then ask for confirmation before approving."""


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]


async def _execute_tool(name: str, args: dict[str, object]) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "query_database":
        sql = str(args.get("sql", ""))
        if not sql.lower().strip().startswith("select"):
            return "Error: Only SELECT queries allowed"
        db = await _get_db()
        try:
            results = await db.execute_query(sql, limit=20)
            return json.dumps(results, default=str, indent=2)
        except Exception as e:
            return f"Query error: {e}"
        finally:
            await db.close()

    if name == "list_pending":
        return json.dumps(await _list_pending(), default=str, indent=2)

    if name == "get_status":
        return json.dumps(await _get_status(), default=str, indent=2)

    if name == "get_commitment_detail":
        cid = str(args.get("commitment_id", ""))
        db = await _get_db()
        try:
            records = await db.execute_query(
                "SELECT FROM CommitmentRecord WHERE commitment_id = :cid LIMIT 1",
                {"cid": cid},
            )
            if records:
                r = records[0]
                cp = r.get("checkpoint")
                plan = ""
                understanding = ""
                if isinstance(cp, dict):
                    plan = str(cp.get("plan", ""))
                    understanding = str(cp.get("current_best_understanding", ""))
                return json.dumps({
                    "commitment_id": r.get("commitment_id"),
                    "domain": r.get("domain"),
                    "status": r.get("status"),
                    "priority_signal": r.get("priority_signal"),
                    "plan": plan,
                    "understanding": understanding,
                }, default=str, indent=2)
            return "Commitment not found"
        finally:
            await db.close()

    if name == "approve_commitment":
        cid = str(args.get("commitment_id", ""))
        from shared.arcadedb.identity import update_commitment
        from shared.status import APPROVED
        db = await _get_db()
        try:
            await update_commitment(db, cid, {"status": APPROVED})
            return f"Commitment {cid} approved. The implementation agent will pick it up."
        finally:
            await db.close()

    if name == "reject_commitment":
        cid = str(args.get("commitment_id", ""))
        reason = str(args.get("reason", ""))
        from shared.arcadedb.identity import update_commitment
        from shared.status import REJECTED
        db = await _get_db()
        try:
            await update_commitment(db, cid, {"status": REJECTED})
            return f"Commitment {cid} rejected: {reason}"
        finally:
            await db.close()

    if name == "defer_commitment":
        cid = str(args.get("commitment_id", ""))
        reason = str(args.get("reason", "deferred"))
        from shared.arcadedb.identity import update_commitment
        from shared.status import DEFERRED
        db = await _get_db()
        try:
            await update_commitment(db, cid, {"status": DEFERRED})
            return f"Commitment {cid} deferred: {reason}"
        finally:
            await db.close()

    return f"Unknown tool: {name}"


@app.post("/api/chat")
async def chat(req: ChatRequest):  # noqa: ANN201
    """Chat endpoint that uses OpenRouter with tool calling to answer questions."""
    from openai import AsyncOpenAI

    from config.env import settings

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.openrouter_api_key,
    )

    messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    for m in req.messages:
        messages.append({"role": m["role"], "content": m["content"]})

    # Call LLM with tools
    response = await client.chat.completions.create(
        model="deepseek/deepseek-v4-flash",
        messages=messages,  # type: ignore[arg-type]
        tools=CHAT_TOOLS,  # type: ignore[arg-type]
        max_tokens=2048,
    )

    msg = response.choices[0].message

    # Handle tool calls
    while msg.tool_calls:
        messages.append(msg.model_dump())  # type: ignore[arg-type]
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tool_args = json.loads(tc.function.arguments)
            result = await _execute_tool(tool_name, tool_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

        response = await client.chat.completions.create(
            model="deepseek/deepseek-v4-flash",
            messages=messages,  # type: ignore[arg-type]
            tools=CHAT_TOOLS,  # type: ignore[arg-type]
            max_tokens=2048,
        )
        msg = response.choices[0].message

    return {"role": "assistant", "content": msg.content or ""}


def main():
    port = int(os.environ.get("UI_PORT", "3001"))
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
