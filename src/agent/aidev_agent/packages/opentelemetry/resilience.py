# -*- coding: utf-8 -*-
"""Low-cardinality resilience metrics and correlated OTel span events."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from typing import Any

from opentelemetry import trace

from .metrics import get_enabled_agent_metrics


@dataclass(frozen=True)
class ModelAttempt:
    model_role: str
    request_model: str
    active: bool = True
    error_type: str = ""


@dataclass(frozen=True)
class ModelAttemptHandle:
    nested: bool


_model_attempt: ContextVar[ModelAttempt | None] = ContextVar("aidev_model_attempt", default=None)
_operation_scope: ContextVar[str] = ContextVar("aidev_operation_scope", default="external")


def _error_type(error: BaseException | type[BaseException] | str) -> str:
    if isinstance(error, str):
        return error or "unknown"
    if isinstance(error, type):
        return error.__name__
    return type(error).__name__


def is_timeout_error(error: BaseException) -> bool:
    """Recognize timeout classes without importing every optional HTTP client."""
    return isinstance(error, TimeoutError) or "timeout" in type(error).__name__.lower()


def _event(name: str, attributes: dict[str, Any]) -> None:
    span = trace.get_current_span()
    if not span.is_recording():
        return
    safe_attributes = {
        key: value
        for key, value in attributes.items()
        if value is not None and isinstance(value, (bool, int, float, str))
    }
    span.add_event(name, attributes=safe_attributes)


def begin_model_attempt(*, model_role: str, request_model: str) -> ModelAttemptHandle:
    previous = _model_attempt.get()
    if (
        previous is not None
        and previous.active
        and previous.model_role == model_role
        and previous.request_model == request_model
    ):
        return ModelAttemptHandle(nested=True)

    _model_attempt.set(
        ModelAttempt(
            model_role=model_role,
            request_model=request_model or "unknown",
        )
    )
    return ModelAttemptHandle(nested=False)


def finish_model_attempt_success(handle: ModelAttemptHandle) -> None:
    if handle.nested:
        return
    attempt = _model_attempt.get()
    if attempt is None:
        return
    _model_attempt.set(None)


def finish_model_attempt_error(handle: ModelAttemptHandle, error: BaseException, *, retry_strategy: str) -> None:
    if handle.nested:
        return
    attempt = _model_attempt.get()
    if attempt is None:
        return
    error_type = _error_type(error)
    _model_attempt.set(replace(attempt, active=False, error_type=error_type))
    recorder = get_enabled_agent_metrics()
    if error_type == "RateLimitError":
        attributes = {
            "model_role": attempt.model_role,
            "retry_strategy": retry_strategy or "unknown",
            "error.type": error_type,
            "outcome": "encountered",
        }
        if recorder is not None:
            recorder.record_llm_rate_limit(attributes)
        _event(
            "gen_ai.rate_limit",
            {
                **attributes,
                "gen_ai.request.model": attempt.request_model,
            },
        )


def propagate_model_failure(*, model_role: str, request_model: str, error: BaseException) -> None:
    """Restore a failed attempt in the caller context after LangChain copied it."""
    _model_attempt.set(
        ModelAttempt(
            model_role=model_role,
            request_model=request_model or "unknown",
            active=False,
            error_type=_error_type(error),
        )
    )


def record_model_fallback_switch(
    *,
    trigger_error: BaseException,
    primary_model: str,
    fallback_model: str,
) -> None:
    error_type = _error_type(trigger_error)
    attributes = {
        "model_role": "fallback",
        "error.type": error_type,
        "outcome": "started",
    }
    recorder = get_enabled_agent_metrics()
    if recorder is not None:
        recorder.record_llm_fallback(attributes)
    _event(
        "gen_ai.fallback.switch",
        {
            **attributes,
            "gen_ai.request.model": primary_model or "unknown",
            "gen_ai.fallback.trigger.error.type": error_type,
            "gen_ai.model.primary": primary_model or "unknown",
            "gen_ai.model.fallback": fallback_model or "unknown",
        },
    )


def record_model_fallback_result(
    *,
    outcome: str,
    trigger_error: BaseException,
    primary_model: str,
    fallback_model: str,
    response_model: str | None = None,
    fallback_error: BaseException | None = None,
) -> None:
    trigger_error_type = _error_type(trigger_error)
    attributes = {
        "model_role": "fallback",
        "error.type": trigger_error_type,
        "outcome": outcome,
    }
    recorder = get_enabled_agent_metrics()
    if recorder is not None:
        recorder.record_llm_fallback(attributes)
    event_attributes: dict[str, Any] = {
        **attributes,
        "gen_ai.request.model": primary_model or "unknown",
        "gen_ai.fallback.model": fallback_model or "unknown",
        "gen_ai.fallback.trigger.error.type": trigger_error_type,
    }
    if response_model is not None:
        event_attributes["gen_ai.response.model"] = response_model
    if fallback_error is not None:
        event_attributes["gen_ai.fallback.error.type"] = _error_type(fallback_error)
    _event("gen_ai.fallback.result", event_attributes)


def failed_model_attempt() -> ModelAttempt | None:
    attempt = _model_attempt.get()
    return attempt if attempt is not None and not attempt.active else None


def record_model_rate_limit(*, retry_strategy: str, error: BaseException) -> None:
    """Record a rate limit when the concrete model wrapper did not already do so."""
    model_attempt = failed_model_attempt()
    # ChatModel records the same failure at the concrete request boundary.
    if model_attempt is not None and model_attempt.error_type == _error_type(error):
        return
    attributes = {
        "model_role": model_attempt.model_role if model_attempt is not None else "primary",
        "retry_strategy": retry_strategy or "unknown",
        "error.type": _error_type(error),
        "outcome": "encountered",
    }
    recorder = get_enabled_agent_metrics()
    if recorder is not None:
        recorder.record_llm_rate_limit(attributes)
    _event(
        "gen_ai.rate_limit",
        {
            **attributes,
            "gen_ai.request.model": model_attempt.request_model if model_attempt is not None else "unknown",
        },
    )


def record_model_retry(
    *,
    outcome: str,
    attempt: int,
    max_attempts: int,
    wait_seconds: float,
    retry_strategy: str,
    error: BaseException | str,
) -> None:
    model_attempt = failed_model_attempt()
    attributes = {
        "model_role": model_attempt.model_role if model_attempt is not None else "primary",
        "retry_strategy": retry_strategy or "unknown",
        "error.type": _error_type(error),
        "outcome": outcome,
    }
    recorder = get_enabled_agent_metrics()
    if recorder is not None:
        recorder.record_llm_retry(attributes, wait_seconds=wait_seconds if outcome == "scheduled" else None)
    event_attributes: dict[str, Any] = {
        **attributes,
        "retry.attempt": attempt,
        "retry.max_attempts": max_attempts,
        "retry.wait_seconds": wait_seconds,
    }
    if model_attempt is not None:
        event_attributes["gen_ai.request.model"] = model_attempt.request_model
    _event(f"gen_ai.retry.{outcome}", event_attributes)


def record_operation_retry(
    *,
    outcome: str,
    attempt: int,
    max_attempts: int,
    error: BaseException,
) -> None:
    scope = _operation_scope.get()
    attributes = {
        "operation.scope": scope,
        "error.type": _error_type(error),
        "outcome": outcome,
    }
    recorder = get_enabled_agent_metrics()
    if recorder is not None:
        recorder.record_operation_retry(attributes)
    _event(
        "aidev.operation.retry",
        {
            **attributes,
            "retry.attempt": attempt,
            "retry.max_attempts": max_attempts,
        },
    )


def record_operation_timeout(
    *,
    scope: str,
    outcome: str,
    error: BaseException | str,
    timeout_seconds: float | None = None,
) -> None:
    attributes = {
        "timeout.scope": scope,
        "error.type": _error_type(error),
        "outcome": outcome,
    }
    recorder = get_enabled_agent_metrics()
    if recorder is not None:
        recorder.record_operation_timeout(attributes)
    _event(
        "aidev.deadline.exceeded" if scope in {"agent", "session"} else "aidev.operation.timeout",
        {**attributes, "timeout.seconds": timeout_seconds},
    )


def set_operation_scope(scope: str) -> Token[str]:
    return _operation_scope.set(scope)


def current_operation_scope() -> str:
    return _operation_scope.get()


def reset_operation_scope(token: Token[str]) -> None:
    try:
        _operation_scope.reset(token)
    except ValueError:
        # Some LangChain callbacks may finish in a copied async context.
        _operation_scope.set("external")
