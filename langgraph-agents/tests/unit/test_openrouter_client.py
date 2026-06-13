from __future__ import annotations

import pytest

from shared.openrouter.models import (
    AgentRole,
    ModelFamily,
    ModelFamilyError,
    enforce_independence,
)


def test_enforce_independence_raises_same_family() -> None:
    with pytest.raises(ModelFamilyError):
        enforce_independence(AgentRole.VERIFICATION, ModelFamily.QWEN)


def test_enforce_independence_no_raise_different_family() -> None:
    enforce_independence(AgentRole.VERIFICATION, ModelFamily.DEEPSEEK)


def test_enforce_independence_no_raise_non_verification() -> None:
    enforce_independence(AgentRole.EXPLORATORY, ModelFamily.QWEN)


def test_exploratory_uses_deepseek_flash() -> None:
    from shared.openrouter.models import MODEL_ASSIGNMENTS
    name, family = MODEL_ASSIGNMENTS[AgentRole.EXPLORATORY]
    assert "flash" in name.lower()
    assert family == ModelFamily.DEEPSEEK


def test_verification_uses_qwen() -> None:
    from shared.openrouter.models import MODEL_ASSIGNMENTS
    name, family = MODEL_ASSIGNMENTS[AgentRole.VERIFICATION]
    assert "qwen" in name.lower()
    assert family == ModelFamily.QWEN


def test_orchestration_uses_deepseek_flash() -> None:
    from shared.openrouter.models import MODEL_ASSIGNMENTS
    name, family = MODEL_ASSIGNMENTS[AgentRole.ORCHESTRATION]
    assert "flash" in name.lower()
    assert family == ModelFamily.DEEPSEEK


def test_deepseek_provider_routing() -> None:
    from shared.openrouter.models import PROVIDER_ROUTING, ModelFamily
    routing = PROVIDER_ROUTING[ModelFamily.DEEPSEEK]
    assert "only" in routing
    assert routing["allow_fallbacks"] is False


def test_qwen_provider_routing() -> None:
    from shared.openrouter.models import PROVIDER_ROUTING, ModelFamily
    routing = PROVIDER_ROUTING[ModelFamily.QWEN]
    assert "only" in routing
    assert routing["allow_fallbacks"] is True


def test_mimo_provider_routing() -> None:
    from shared.openrouter.models import PROVIDER_ROUTING, ModelFamily
    routing = PROVIDER_ROUTING[ModelFamily.MIMO]
    assert routing["allow_fallbacks"] is True


def test_kimi_provider_routing() -> None:
    from shared.openrouter.models import PROVIDER_ROUTING, ModelFamily
    routing = PROVIDER_ROUTING[ModelFamily.KIMI]
    assert routing["allow_fallbacks"] is True


def test_mimo_model_family_exists() -> None:
    assert ModelFamily.MIMO is ModelFamily.MIMO


def test_kimi_model_family_exists() -> None:
    assert ModelFamily.KIMI is ModelFamily.KIMI


def test_enforce_independence_non_matching_families() -> None:
    for family in ModelFamily:
        if family != ModelFamily.QWEN:
            enforce_independence(AgentRole.VERIFICATION, family)
