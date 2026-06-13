"""Langfuse observability — LLM tracing.

Tracks every LLM call: model, tokens, cost, latency.
Exports to Langfuse Cloud (Hobby: free, 50K obs/month).

Usage:
    from shared.observability.tracing import configure_tracing

    tracer = configure_tracing("exploratory", "agent-1", None, "1.0")
    with tracer.trace_llm_call(model, role, agent_id, focus_id, mtp) as gen:
        response = await model.ainvoke(prompt)
        gen.update(input_tokens=100, output_tokens=50, cost=0.002)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Final

logger = logging.getLogger(__name__)

_DEFAULT_HOST: Final = "https://cloud.langfuse.com"


class TracingConfig:
    """Configured Langfuse tracer. Creates Langfuse generation spans."""

    def __init__(self, enabled: bool, host: str, pub_key: str, secret_key: str) -> None:
        self.enabled = enabled
        self.host = host
        self.pub_key = pub_key
        self.secret_key = secret_key

    def trace_llm_call(  # noqa: ANN401
        self, model: str, role: str, agent_id: str, focus_id: str | None, mtp_version: str,
    ) -> _GenerationContext:
        """Returns a context manager that records an LLM call to Langfuse.

        Use as: with tracer.trace_llm_call(...) as gen: ...  gen.update(...)
        """
        return _GenerationContext(self, model, role, agent_id, focus_id, mtp_version)


class _GenerationContext:
    """Context manager wrapping a Langfuse generation span."""

    def __init__(
        self, config: TracingConfig, model: str, role: str,
        agent_id: str, focus_id: str | None, mtp_version: str,
    ) -> None:
        self._config = config
        self._model = model
        self._role = role
        self._agent_id = agent_id
        self._focus_id = focus_id
        self._mtp_version = mtp_version

    def __enter__(self) -> object:
        if not self._config.enabled:
            return _noop()
        pub = self._config.pub_key
        sec = self._config.secret_key
        host = self._config.host
        if not pub or not sec:
            return _noop()
        from langfuse import Langfuse
        client = Langfuse(public_key=pub, secret_key=sec, host=host)
        self._gen = _GenSpan(
            self._agent_id, self._focus_id, self._mtp_version,
            self._model, self._role, time.monotonic(), client,
        )
        return self._gen

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        g = getattr(self, "_gen", None)
        if g is not None:
            if exc is not None:
                g._level = "ERROR"
            g._finalize()


class _GenSpan:
    def __init__(  # noqa: ANN401 — Langfuse SDK has no type stubs
        self, agent_id: str, focus_id: str | None, mtp_version: str,
        model: str, role: str, start: float, client: Any,  # noqa: ANN401
    ) -> None:
        self.agent_id = agent_id
        self.focus_id = focus_id
        self.mtp_version = mtp_version
        self.model = model
        self.role = role
        self._start = start
        self._client = client
        self._level = "DEFAULT"
        self._input_tokens: int | None = None
        self._output_tokens: int | None = None
        self._cost: float | None = None

    def update(
        self, input_tokens: int | None = None,
        output_tokens: int | None = None, cost: float | None = None,
    ) -> None:
        if input_tokens is not None:
            self._input_tokens = input_tokens
        if output_tokens is not None:
            self._output_tokens = output_tokens
        if cost is not None:
            self._cost = cost

    def _finalize(self) -> None:
        latency_ms = (time.monotonic() - self._start) * 1000
        try:
            self._client.generation(
                name=f"{self.role}-{self.model}",
                model=self.model,
                start_time=time.time() - latency_ms / 1000,
                end_time=time.time(),
                usage={
                    "input": self._input_tokens,
                    "output": self._output_tokens,
                    "total": (
                        (self._input_tokens or 0) + (self._output_tokens or 0)
                    ) or None,
                },
                metadata={
                    "agent_id": self.agent_id,
                    "focus_id": self.focus_id,
                    "mtp_version": self.mtp_version,
                },
                level=self._level,
            )
        except Exception as e:
            logger.debug("Failed to record Langfuse generation: %s", e)


class _NoopGen:
    def update(self, **kwargs: object) -> None:
        pass


def _noop() -> _NoopGen:
    return _NoopGen()


def configure_tracing(
    agent_type: str, agent_id: str, focus_id: str | None, mtp_version: str,
) -> TracingConfig:
    pub = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sec = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = os.environ.get("LANGFUSE_HOST", _DEFAULT_HOST)
    enabled = bool(pub and sec)
    if not enabled:
        logger.warning(
            "Langfuse credentials not set. Tracing disabled. "
            "Sign up at https://cloud.langfuse.com"
        )
    else:
        logger.info("Langfuse tracing enabled for %s/%s", agent_type, agent_id)
    return TracingConfig(enabled=enabled, host=host, pub_key=pub, secret_key=sec)
