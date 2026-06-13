from __future__ import annotations

from unittest.mock import MagicMock, patch

from shared.bedrock_agent import TEST_ALIAS_ID, invoke_bedrock_agent


def test_test_alias_id() -> None:
    assert TEST_ALIAS_ID == "TSTALIASID"


def test_invoke_bedrock_agent_collects_chunks() -> None:
    """Verify invoke_bedrock_agent collects completion chunks into a string."""
    import asyncio

    mock_client = MagicMock()
    mock_response = {
        "completion": [
            {"chunk": {"bytes": b'{"result": "'}},
            {"chunk": {"bytes": b'Task'}},
            {"chunk": {"bytes": b' completed."}'}},
        ],
    }
    mock_client.invoke_agent = MagicMock(return_value=mock_response)

    async def _run() -> None:
        with patch(
            "shared.bedrock_agent.boto3.client", return_value=mock_client,
        ), patch(
            "shared.bedrock_agent.asyncio.to_thread",
            side_effect=lambda fn: fn(),
        ):
            result = await invoke_bedrock_agent("agent-1", "session-1", "test")
            assert result == '{"result": "Task completed."}'

    asyncio.run(_run())


def test_invoke_bedrock_agent_empty_completion() -> None:
    """Verify invoke_bedrock_agent returns empty string when no chunks."""
    import asyncio

    mock_client = MagicMock()
    mock_response: dict = {"completion": []}
    mock_client.invoke_agent = MagicMock(return_value=mock_response)

    async def _run() -> None:
        with patch(
            "shared.bedrock_agent.boto3.client", return_value=mock_client,
        ), patch(
            "shared.bedrock_agent.asyncio.to_thread",
            side_effect=lambda fn: fn(),
        ):
            result = await invoke_bedrock_agent("agent-1", "session-1", "test")
            assert result == ""

    asyncio.run(_run())


def test_invoke_bedrock_agent_passes_parameters() -> None:
    """Verify invoke_bedrock_agent passes correct params to boto3."""
    import asyncio

    mock_client = MagicMock()
    mock_client.invoke_agent = MagicMock(return_value={"completion": []})

    async def _run() -> None:
        with patch(
            "shared.bedrock_agent.boto3.client", return_value=mock_client,
        ), patch(
            "shared.bedrock_agent.asyncio.to_thread",
            side_effect=lambda fn: fn(),
        ):
            await invoke_bedrock_agent("agent-id-001", "session-xyz", "hello")

        mock_client.invoke_agent.assert_called_once_with(
            agentId="agent-id-001",
            agentAliasId="TSTALIASID",
            sessionId="session-xyz",
            inputText="hello",
            enableTrace=False,
        )

    asyncio.run(_run())
