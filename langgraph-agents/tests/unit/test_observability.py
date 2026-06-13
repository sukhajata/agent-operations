from __future__ import annotations

import os
from unittest.mock import patch

from shared.observability.tracing import TracingConfig, configure_tracing


def test_configure_tracing_disabled_without_creds() -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = configure_tracing("exploratory", "agent-1", None, "1.0")
        assert config.enabled is False


def test_configure_tracing_enabled_with_creds() -> None:
    with patch.dict(os.environ, {
        "LANGFUSE_PUBLIC_KEY": "pk-test",
        "LANGFUSE_SECRET_KEY": "sk-test",
    }):
        config = configure_tracing("exploratory", "agent-1", None, "1.0")
        assert config.enabled is True
        assert config.pub_key == "pk-test"


def test_trace_llm_call_noop_when_disabled() -> None:
    config = TracingConfig(enabled=False, host="", pub_key="", secret_key="")
    with config.trace_llm_call("model", "exploratory", "a1", None, "1.0") as gen:
        gen.update(input_tokens=100)
    assert True


def test_trace_llm_call_noop_without_keys() -> None:
    config = TracingConfig(enabled=True, host="h", pub_key="", secret_key="")
    with config.trace_llm_call("model", "exploratory", "a1", None, "1.0") as gen:
        gen.update(input_tokens=100)
    assert True
