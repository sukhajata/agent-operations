from __future__ import annotations

import asyncio
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from shared.openrouter.client import (
    OpenRouterAPIError,
    OpenRouterClient,
    OpenRouterConnectionError,
)
from shared.openrouter.models import (
    MODEL_ASSIGNMENTS,
    MODEL_DEEPSEEK_V4_FLASH,
    MODEL_DEEPSEEK_V4_PRO,
    MODEL_QWEN3_7_MAX,
    PROVIDER_ALIBABA,
    PROVIDER_DEEPSEEK,
    PROVIDER_ROUTING,
    AgentRole,
    ModelFamily,
    ModelFamilyError,
    enforce_independence,
)


def _make_async_response(status_code: int = 200, result: dict[str, Any] | None = None) -> AsyncMock:
    response = AsyncMock()
    response.is_success = status_code < 400
    response.status_code = status_code
    response.text = ""
    response.json = lambda: result or {
        "choices": [{"message": {"role": "assistant", "content": "response text"}}]
    }
    return response


class MockOpenRouterClient(OpenRouterClient):
    """Testable client that records API calls."""

    def __init__(self) -> None:
        super().__init__("sk-test-key")
        self.post_mock = AsyncMock()
        self._client.post = self.post_mock  # type: ignore[method-assign]

    def set_response(
        self, status_code: int = 200, result: dict[str, Any] | None = None
    ) -> None:
        self.post_mock.return_value = _make_async_response(status_code, result)

    def pop_post_kwargs(self) -> dict[str, Any]:
        return cast(dict[str, Any], self.post_mock.call_args.kwargs)


# --- enforce_independence tests ---


def test_enforce_independence_raises_same_family() -> None:
    with pytest.raises(ModelFamilyError, match="different model family"):
        enforce_independence(AgentRole.VERIFICATION, ModelFamily.QWEN)


def test_enforce_independence_no_raise_different_family() -> None:
    enforce_independence(AgentRole.VERIFICATION, ModelFamily.DEEPSEEK)


def test_enforce_independence_no_raise_non_verification() -> None:
    enforce_independence(AgentRole.EXPLORATORY, ModelFamily.DEEPSEEK)
    enforce_independence(AgentRole.OBJECTIVE, ModelFamily.QWEN)
    enforce_independence(AgentRole.ORCHESTRATION, ModelFamily.QWEN)


# --- Model assignments tests ---


def test_exploratory_uses_deepseek_flash() -> None:
    model, family = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
    assert model == MODEL_DEEPSEEK_V4_FLASH
    assert family == ModelFamily.DEEPSEEK


def test_verification_uses_qwen() -> None:
    model, family = MODEL_ASSIGNMENTS[AgentRole.VERIFICATION]
    assert model == MODEL_QWEN3_7_MAX
    assert family == ModelFamily.QWEN


def test_objective_uses_deepseek_pro() -> None:
    model, family = MODEL_ASSIGNMENTS[AgentRole.OBJECTIVE]
    assert model == MODEL_DEEPSEEK_V4_PRO
    assert family == ModelFamily.DEEPSEEK


def test_orchestration_uses_deepseek_flash() -> None:
    model, family = MODEL_ASSIGNMENTS[AgentRole.ORCHESTRATION]
    assert model == MODEL_DEEPSEEK_V4_FLASH
    assert family == ModelFamily.DEEPSEEK


# --- Provider routing tests ---


def test_deepseek_provider_routing() -> None:
    routing = PROVIDER_ROUTING[ModelFamily.DEEPSEEK]
    assert routing["only"] == [PROVIDER_DEEPSEEK]
    assert routing["allow_fallbacks"] is False


def test_qwen_provider_routing() -> None:
    routing = PROVIDER_ROUTING[ModelFamily.QWEN]
    assert routing["only"] == [PROVIDER_ALIBABA]
    assert routing["allow_fallbacks"] is True


def test_mimo_provider_routing() -> None:
    routing = PROVIDER_ROUTING[ModelFamily.MIMO]
    assert routing["allow_fallbacks"] is True


def test_kimi_provider_routing() -> None:
    routing = PROVIDER_ROUTING[ModelFamily.KIMI]
    assert routing["allow_fallbacks"] is True


# --- Client complete tests ---


def test_complete_builds_correct_request() -> None:
    client = MockOpenRouterClient()
    client.set_response()

    async def _run() -> None:
        result = await client.complete(
            role=AgentRole.EXPLORATORY,
            messages=[{"role": "user", "content": "Hello"}],
            system="You are helpful.",
        )
        assert result == "response text"

        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["model"] == MODEL_DEEPSEEK_V4_FLASH
        assert kwargs["json"]["provider"] == {
            "only": [PROVIDER_DEEPSEEK],
            "allow_fallbacks": False,
        }
        assert kwargs["json"]["messages"] == [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello"},
        ]

    asyncio.run(_run())


def test_complete_objective_role() -> None:
    client = MockOpenRouterClient()
    client.set_response()

    async def _run() -> None:
        result = await client.complete(
            role=AgentRole.OBJECTIVE,
            messages=[{"role": "user", "content": "Analyze this."}],
            system="You are an analyst.",
            enable_caching=True,
        )
        assert result == "response text"

        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["model"] == MODEL_DEEPSEEK_V4_PRO
        assert kwargs["json"]["provider"] == {
            "only": [PROVIDER_DEEPSEEK],
            "allow_fallbacks": False,
        }

    asyncio.run(_run())


def test_complete_verification_role() -> None:
    client = MockOpenRouterClient()
    client.set_response()

    async def _run() -> None:
        result = await client.complete(
            role=AgentRole.VERIFICATION,
            messages=[{"role": "user", "content": "Verify this finding."}],
            system="You are a skeptic.",
            originating_model_family=ModelFamily.DEEPSEEK,
        )
        assert result == "response text"

        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["model"] == MODEL_QWEN3_7_MAX
        assert kwargs["json"]["provider"] == {
            "only": [PROVIDER_ALIBABA],
            "allow_fallbacks": True,
        }

    asyncio.run(_run())


def test_complete_verification_violates_independence() -> None:
    client = MockOpenRouterClient()
    client.set_response()

    async def _run() -> None:
        with pytest.raises(ModelFamilyError, match="different model family"):
            await client.complete(
                role=AgentRole.VERIFICATION,
                messages=[{"role": "user", "content": "Verify this."}],
                system="You are a skeptic.",
                originating_model_family=ModelFamily.QWEN,
            )

    asyncio.run(_run())


def test_complete_orchestration_role() -> None:
    client = MockOpenRouterClient()
    client.set_response()

    async def _run() -> None:
        result = await client.complete(
            role=AgentRole.ORCHESTRATION,
            messages=[{"role": "user", "content": "Orchestrate."}],
            system="You are a coordinator.",
        )
        assert result == "response text"

        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["model"] == MODEL_DEEPSEEK_V4_FLASH
        assert kwargs["json"]["provider"] == {
            "only": [PROVIDER_DEEPSEEK],
            "allow_fallbacks": False,
        }

    asyncio.run(_run())


def test_complete_max_tokens() -> None:
    client = MockOpenRouterClient()
    client.set_response()

    async def _run() -> None:
        await client.complete(
            role=AgentRole.EXPLORATORY,
            messages=[],
            system="",
            max_tokens=100,
        )
        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["max_tokens"] == 100

    asyncio.run(_run())


def test_complete_api_error() -> None:
    client = MockOpenRouterClient()
    client.set_response(status_code=401)

    async def _run() -> None:
        with pytest.raises(OpenRouterAPIError):
            await client.complete(
                role=AgentRole.EXPLORATORY,
                messages=[],
                system="",
            )

    asyncio.run(_run())


def test_complete_connection_error() -> None:
    import httpx

    async def _run() -> None:
        client = MockOpenRouterClient()
        client.post_mock.side_effect = httpx.ConnectError("refused")
        with pytest.raises(OpenRouterConnectionError):
            await client.complete(
                role=AgentRole.EXPLORATORY,
                messages=[],
                system="",
            )

    asyncio.run(_run())


def test_complete_no_choices_in_response() -> None:
    client = MockOpenRouterClient()
    client.set_response(result={"choices": []})

    async def _run() -> None:
        with pytest.raises(OpenRouterAPIError, match="no choices"):
            await client.complete(
                role=AgentRole.EXPLORATORY,
                messages=[],
                system="",
            )

    asyncio.run(_run())


def test_complete_empty_content() -> None:
    client = MockOpenRouterClient()
    client.set_response(result={
        "choices": [{"message": {"role": "assistant", "content": ""}}]
    })

    async def _run() -> None:
        result = await client.complete(
            role=AgentRole.EXPLORATORY,
            messages=[],
            system="",
        )
        assert result == ""

    asyncio.run(_run())


# --- Model family tests ---


def test_mimo_model_family_exists() -> None:
    assert ModelFamily.MIMO.value == "mimo"
    assert ModelFamily.MIMO in ModelFamily


def test_kimi_model_family_exists() -> None:
    assert ModelFamily.KIMI.value == "kimi"
    assert ModelFamily.KIMI in ModelFamily


def test_enforce_independence_non_matching_families() -> None:
    enforce_independence(AgentRole.VERIFICATION, ModelFamily.DEEPSEEK)
    enforce_independence(AgentRole.VERIFICATION, ModelFamily.MIMO)
    enforce_independence(AgentRole.VERIFICATION, ModelFamily.KIMI)


# --- Provider override tests ---


def test_complete_with_provider_override() -> None:
    """Verify that passing a custom provider overrides the default routing."""
    client = MockOpenRouterClient()
    client.set_response()

    custom_provider = {
        "only": ["DeepSeek"],
        "quantizations": ["int8"],
    }

    async def _run() -> None:
        await client.complete(
            role=AgentRole.EXPLORATORY,
            messages=[{"role": "user", "content": "Hi"}],
            system="",
            provider=custom_provider,
        )
        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["provider"] == custom_provider
        assert kwargs["json"]["provider"]["quantizations"] == ["int8"]

    asyncio.run(_run())


def test_complete_without_provider_override_uses_default() -> None:
    """Verify that omitting provider uses the default routing from PROVIDER_ROUTING."""
    client = MockOpenRouterClient()
    client.set_response()

    async def _run() -> None:
        await client.complete(
            role=AgentRole.VERIFICATION,
            messages=[{"role": "user", "content": "Verify"}],
            system="",
        )
        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["provider"] == PROVIDER_ROUTING[ModelFamily.QWEN]

    asyncio.run(_run())


def test_complete_with_fallback_provider_override() -> None:
    """Verify provider override with fallback configuration."""
    client = MockOpenRouterClient()
    client.set_response()

    custom_provider = {
        "order": ["DeepSeek", "Fireworks"],
        "allow_fallbacks": True,
        "quantizations": ["int4", "int8"],
    }

    async def _run() -> None:
        await client.complete(
            role=AgentRole.OBJECTIVE,
            messages=[],
            system="Analyze.",
            provider=custom_provider,
        )
        kwargs = client.pop_post_kwargs()
        assert kwargs["json"]["provider"] == custom_provider
        assert kwargs["json"]["model"] == MODEL_DEEPSEEK_V4_PRO

    asyncio.run(_run())
