"""OpenRouter API client with agent-role routing.

Provides an async client for making LLM completion calls via the OpenRouter
API, with automatic model selection and provider routing based on agent role.
"""

from __future__ import annotations

from typing import Any

import httpx

from .models import (
    MODEL_ASSIGNMENTS,
    PROVIDER_ROUTING,
    AgentRole,
    ModelFamily,
    enforce_independence,
)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    """Base exception for OpenRouter client errors."""


class OpenRouterAPIError(OpenRouterError):
    """OpenRouter returned an error response."""


class OpenRouterConnectionError(OpenRouterError):
    """Failed to connect to the OpenRouter API."""


class OpenRouterClient:
    """Async client for OpenRouter LLM completions with agent-role routing."""

    def __init__(self, api_key: str, timeout: float = 120.0) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def complete(
        self,
        role: AgentRole,
        messages: list[dict[str, Any]],
        system: str,
        max_tokens: int = 4096,
        enable_caching: bool = False,
        originating_model_family: ModelFamily | None = None,
        provider: dict[str, Any] | None = None,
    ) -> str:
        """Execute an LLM completion with automatic model and provider routing.

        Args:
            role: The agent role (determines model and provider defaults)
            messages: Conversation messages in OpenAI format
            system: System prompt (prepended to messages)
            max_tokens: Maximum completion tokens
            enable_caching: Enable prompt caching (OBJECTIVE role)
            originating_model_family: Model family of the originating agent
                (required for VERIFICATION role independence check)
            provider: Optional provider routing config (order, only,
                allow_fallbacks, quantizations, etc). Overrides the default
                routing from PROVIDER_ROUTING when specified.

        Returns:
            The completion text from the LLM

        Raises:
            ModelFamilyError: If verification independence is violated
            OpenRouterAPIError: On API error response
            OpenRouterConnectionError: On connection failure
        """
        if originating_model_family is not None:
            enforce_independence(role, originating_model_family)

        model_name, model_family = MODEL_ASSIGNMENTS[role]
        provider_config = provider if provider is not None else PROVIDER_ROUTING[model_family]

        full_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            *messages,
        ]

        body: dict[str, Any] = {
            "model": model_name,
            "messages": full_messages,
            "max_tokens": max_tokens,
            "provider": provider_config,
        }

        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        if enable_caching and role == AgentRole.OBJECTIVE:
            headers["HTTP-Referer"] = "agent-operations"
            headers["X-Title"] = "Agent Operations — Objective Agent"

        try:
            response = await self._client.post(
                OPENROUTER_API_URL,
                json=body,
                headers=headers,
            )
        except httpx.RequestError as e:
            raise OpenRouterConnectionError(
                f"Failed to connect to OpenRouter: {e}"
            ) from e

        if not response.is_success:
            raise OpenRouterAPIError(
                f"OpenRouter returned HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise OpenRouterAPIError("OpenRouter returned no choices in response")

        message = choices[0].get("message", {})
        content = message.get("content", "")
        return str(content)
