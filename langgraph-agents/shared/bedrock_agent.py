"""Bedrock AgentCore invocation helper.

Calls boto3 bedrock-agent-runtime.invoke_agent() and collects
the streaming completion into a string.
"""

from __future__ import annotations

import asyncio
import logging

try:
    import boto3  # type: ignore[import-untyped]
except ImportError:
    boto3 = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

TEST_ALIAS_ID = "TSTALIASID"


async def invoke_bedrock_agent(agent_id: str, session_id: str, prompt: str) -> str:
    """Invoke a Bedrock agent and collect the streaming completion."""

    def _invoke() -> str:
        client = boto3.client("bedrock-agent-runtime")
        response = client.invoke_agent(
            agentId=agent_id,
            agentAliasId=TEST_ALIAS_ID,
            sessionId=session_id,
            inputText=prompt,
            enableTrace=False,
        )
        completion = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                completion += event["chunk"]["bytes"].decode()
        return completion

    return await asyncio.to_thread(_invoke)
