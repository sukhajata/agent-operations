"""AgentCore Runtime HTTP server.

Implements the AWS Bedrock AgentCore service contract:
  GET  /ping        → {"status": "Healthy"|"HealthyBusy", "time_of_last_update": <epoch>}
  POST /invocations → text/event-stream of JSON SSE events

Startup sequence (in main()):
  1. Resolve *_SSM_PARAMETER env vars → actual secret values via AWS SSM
  2. Configure git credential helper from GITHUB_TOKEN
  3. Pre-build agent settings (loads skills, MCP config)
  4. Start uvicorn on 0.0.0.0:8080
"""

import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import boto3
import uvicorn
from fastapi import FastAPI, Header
from fastapi.responses import StreamingResponse
from openhands.sdk import (
    AgentContext,
    Conversation,
    Event,
    OpenHandsAgentSettings,
    get_logger,
)
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.event import ActionEvent
from openhands.sdk.settings import CondenserSettings
from openhands.sdk.tool import Tool
from openhands.tools.browser_use import BrowserToolSet
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.glob import GlobTool
from openhands.tools.grep import GrepTool
from openhands.tools.preset.default import register_builtins_agents
from openhands.tools.task import TaskToolSet
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool
from pydantic import BaseModel, SecretStr

from openhands_coding_agent.main import (
    DEFAULT_CONDENSER_MAX_SIZE,
    DEFAULT_LLM_MODEL,
    DEFAULT_MAX_COST_USD,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PERSISTENCE_DIR,
    load_agent_skills,
    load_mcp_config,
)

logger = get_logger(__name__)

app = FastAPI()

_busy = False
_last_update = int(time.time())
_settings: OpenHandsAgentSettings | None = None


class InvokeRequest(BaseModel):
    prompt: str
    conversation_id: str | None = None


# ── Startup helpers ────────────────────────────────────────────────────────────


def resolve_ssm_secrets() -> None:
    """Replace *_SSM_PARAMETER env vars with the actual secret values from SSM.

    Terraform passes SSM parameter *names* as env vars rather than plaintext
    values.  This function resolves them so the rest of the process can simply
    read os.environ["LLM_API_KEY"] etc.
    """
    region = os.getenv("AWS_REGION", "ap-southeast-2")
    ssm = boto3.client("ssm", region_name=region)
    for key in list(os.environ):
        if not key.endswith("_SSM_PARAMETER"):
            continue
        param_name = os.environ[key]
        if not param_name:
            continue
        target_key = key.removesuffix("_SSM_PARAMETER")
        try:
            value = ssm.get_parameter(Name=param_name, WithDecryption=True)["Parameter"]["Value"]
            os.environ[target_key] = value
            logger.info("Resolved SSM parameter %s → %s", param_name, target_key)
        except Exception:
            logger.exception("Failed to resolve SSM parameter %s for %s", param_name, target_key)


def configure_git_credentials() -> None:
    """Wire GITHUB_TOKEN into git's credential store.

    Uses the 'store' helper so the agent can clone and push without being
    prompted.  The credentials file is written to ~/.git-credentials.
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return
    subprocess.run(
        ["git", "config", "--global", "credential.helper", "store"],
        check=True,
    )
    creds_path = Path.home() / ".git-credentials"
    fd = os.open(str(creds_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"https://x-access-token:{token}@github.com\n")
    logger.info("Git credentials configured from GITHUB_TOKEN")


def _build_settings() -> OpenHandsAgentSettings:
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY is not set — ensure the SSM parameter was resolved at startup")

    llm_config: dict = {
        "usage_id": "agent",
        "api_key": SecretStr(api_key),
        "model": os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
    }
    if os.getenv("LLM_BASE_URL"):
        llm_config["base_url"] = os.getenv("LLM_BASE_URL")

    register_builtins_agents()
    skills = load_agent_skills(os.getcwd())
    mcp_config = load_mcp_config()

    if mcp_config:
        logger.info("Loaded MCP config with servers: %s", list(mcp_config.get("mcpServers", {}).keys()))

    return OpenHandsAgentSettings(
        llm=llm_config,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=GlobTool.name),
            Tool(name=GrepTool.name),
            Tool(name=TaskTrackerTool.name),
            Tool(name=TaskToolSet.name),
            Tool(name=BrowserToolSet.name),
        ],
        condenser=CondenserSettings(
            enabled=True,
            max_size=int(os.getenv("CONDENSER_MAX_SIZE", DEFAULT_CONDENSER_MAX_SIZE)),
        ),
        agent_context=AgentContext(
            skills=skills,
            load_public_skills=False,
        ),
        mcp_config=mcp_config,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@app.get("/ping")
def ping() -> dict:
    return {
        "status": "HealthyBusy" if _busy else "Healthy",
        "time_of_last_update": _last_update,
    }


@app.post("/invocations")
async def invoke(
    body: InvokeRequest,
    x_amzn_bedrock_agentcore_runtime_session_id: str | None = Header(default=None),
) -> StreamingResponse:
    global _busy, _last_update
    _busy = True
    _last_update = int(time.time())

    async def generate():
        global _busy, _last_update
        run_task: asyncio.Task | None = None
        try:
            if _settings is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Server not initialized'})}\n\n"
                return

            # Prefer explicit body conversation_id, then AgentCore session header,
            # then generate a fresh UUID.  The AgentCore session ID is stable for
            # the lifetime of the microVM session so it naturally maps to one
            # ongoing conversation.
            raw_id = body.conversation_id or x_amzn_bedrock_agentcore_runtime_session_id
            if raw_id:
                try:
                    conversation_id = uuid.UUID(raw_id)
                except ValueError:
                    # AgentCore may send non-UUID session IDs; derive a stable UUID
                    # from the raw string so persistence keys stay consistent.
                    conversation_id = uuid.uuid5(uuid.NAMESPACE_URL, raw_id)
            else:
                conversation_id = uuid.uuid4()

            max_cost = float(os.getenv("MAX_COST_USD", DEFAULT_MAX_COST_USD))
            max_iterations = int(os.getenv("MAX_ITERATIONS", DEFAULT_MAX_ITERATIONS))

            agent = _settings.create_agent()
            cost_cap_hit = False
            loop = asyncio.get_running_loop()
            queue: asyncio.Queue[dict | None] = asyncio.Queue()

            # conversation is assigned before the callback can fire (callback is
            # only called after conversation.run() starts, which is after the
            # Conversation object is created and send_message is called).
            conversation: Conversation

            def callback(event: Event) -> None:
                nonlocal cost_cap_hit
                payload: dict = {"type": type(event).__name__}

                if isinstance(event, ActionEvent):
                    payload["tool"] = event.tool_name
                    if event.action is not None:
                        action: dict = {}
                        for field in ("description", "subagent_type", "command", "path"):
                            val = getattr(event.action, field, None)
                            if val is not None:
                                action[field] = str(val)[:500]
                        if action:
                            payload["action"] = action

                payload["cost_usd"] = round(agent.llm.metrics.accumulated_cost, 4)

                if agent.llm.metrics.accumulated_cost >= max_cost and not cost_cap_hit:
                    cost_cap_hit = True
                    conversation.interrupt()
                    payload["interrupted"] = "cost_cap"

                loop.call_soon_threadsafe(queue.put_nowait, payload)

            persistence_dir = os.getenv("PERSISTENCE_DIR", DEFAULT_PERSISTENCE_DIR)
            conversation = Conversation(
                agent=agent,
                callbacks=[callback],
                workspace=os.getcwd(),
                persistence_dir=persistence_dir,
                conversation_id=conversation_id,
                max_iteration_per_run=max_iterations,
                stuck_detection=True,
            )
            conversation.send_message(body.prompt)

            async def _run() -> None:
                try:
                    await asyncio.to_thread(conversation.run)
                except ConversationRunError as e:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"type": "error", "message": str(e.__cause__ or e)},
                    )
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # signals stream end

            run_task = asyncio.create_task(_run())

            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"

            cost = agent.llm.metrics.accumulated_cost
            stuck = bool(conversation.stuck_detector and conversation.stuck_detector.is_stuck())
            yield f"data: {
                json.dumps(
                    {
                        'type': 'complete',
                        'conversation_id': str(conversation_id),
                        'cost_usd': round(cost, 4),
                        'cost_cap_hit': cost_cap_hit,
                        'stuck': stuck,
                    }
                )
            }\n\n"

        finally:
            if run_task is not None:
                run_task.cancel()
            _busy = False
            _last_update = int(time.time())

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Entry point ────────────────────────────────────────────────────────────────


def main() -> None:
    global _settings

    resolve_ssm_secrets()
    configure_git_credentials()

    try:
        _settings = _build_settings()
    except RuntimeError:
        logger.exception("Failed to build agent settings — server will return errors on /invocations")

    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")


if __name__ == "__main__":
    main()
