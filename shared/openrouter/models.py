"""OpenRouter model assignments, agent roles, and provider routing.

Defines the mapping between agent roles and LLM models, along with
provider routing configuration for the OpenRouter API.
"""

from enum import StrEnum
from typing import Any

# --- Provider name constants ---

PROVIDER_DEEPSEEK = "DeepSeek"
PROVIDER_DEEPINFRA = "DeepInfra"
PROVIDER_ALIBABA = "Alibaba"

# --- Model ID constants ---

MODEL_DEEPSEEK_V4_FLASH = "deepseek/deepseek-v4-flash"
MODEL_DEEPSEEK_V4_PRO = "deepseek/deepseek-v4-pro"
MODEL_QWEN3_7_MAX = "qwen/qwen3.7-max"


class AgentRole(StrEnum):
    """Agent role determines the model used for LLM calls."""

    EXPLORATORY = "exploratory"
    VERIFICATION = "verification"
    OBJECTIVE = "objective"
    ORCHESTRATION = "orchestration"


class ModelFamily(StrEnum):
    """Model families used for independence verification and provider routing."""

    DEEPSEEK = "deepseek"
    QWEN = "qwen"
    MIMO = "mimo"
    KIMI = "kimi"


MODEL_ASSIGNMENTS: dict[AgentRole, tuple[str, ModelFamily]] = {
    AgentRole.EXPLORATORY: (MODEL_DEEPSEEK_V4_FLASH, ModelFamily.DEEPSEEK),
    AgentRole.VERIFICATION: (MODEL_QWEN3_7_MAX, ModelFamily.QWEN),
    AgentRole.OBJECTIVE: (MODEL_DEEPSEEK_V4_PRO, ModelFamily.DEEPSEEK),
    AgentRole.ORCHESTRATION: (MODEL_DEEPSEEK_V4_FLASH, ModelFamily.DEEPSEEK),
}

PROVIDER_ROUTING: dict[ModelFamily, dict[str, Any]] = {
    ModelFamily.DEEPSEEK: {
        "only": [PROVIDER_DEEPSEEK],
        "allow_fallbacks": False,
    },
    ModelFamily.QWEN: {
        "only": [PROVIDER_ALIBABA],
        "allow_fallbacks": True,
    },
    ModelFamily.MIMO: {
        "allow_fallbacks": True,
    },
    ModelFamily.KIMI: {
        "allow_fallbacks": True,
    },
}

VERIFICATION_MODEL_FAMILY = ModelFamily.QWEN


class ModelFamilyError(Exception):
    """Raised when verification independence is violated — verification
    agent must use a different model family from the originating agent."""


def enforce_independence(
    requesting_role: AgentRole,
    originating_model_family: ModelFamily,
) -> None:
    """Enforce that the verification agent uses a different model family.

    Raises ModelFamilyError if the requesting role is VERIFICATION and
    the originating agent shares the verification model's family.

    Args:
        requesting_role: The role requesting the LLM call
        originating_model_family: The model family of the finding's origin agent

    Raises:
        ModelFamilyError: If independence is violated
    """
    if requesting_role != AgentRole.VERIFICATION:
        return
    if originating_model_family == VERIFICATION_MODEL_FAMILY:
        raise ModelFamilyError(
            f"Verification agent must use a different model family "
            f"from the originating agent. Both use {originating_model_family.value}."
        )
