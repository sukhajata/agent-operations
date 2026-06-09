"""OpenRouter client package — LLM completion with agent-role routing."""

from .client import (
    OpenRouterAPIError,
    OpenRouterClient,
    OpenRouterConnectionError,
    OpenRouterError,
)
from .models import (
    MODEL_ASSIGNMENTS,
    PROVIDER_ROUTING,
    AgentRole,
    ModelFamily,
    ModelFamilyError,
    enforce_independence,
)

__all__ = [
    "AgentRole",
    "ModelFamily",
    "ModelFamilyError",
    "MODEL_ASSIGNMENTS",
    "PROVIDER_ROUTING",
    "OpenRouterAPIError",
    "OpenRouterClient",
    "OpenRouterConnectionError",
    "OpenRouterError",
    "enforce_independence",
]
