from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.opentelemetry import resilience
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai.chat_models import ChatOpenAI as RawChatOpenAI


class RateLimitError(Exception):
    pass


def test_fallback_events_include_models_but_metric_dimensions_do_not(monkeypatch):
    recorder = MagicMock()
    span = MagicMock()
    span.is_recording.return_value = True
    monkeypatch.setattr(resilience, "get_enabled_agent_metrics", lambda: recorder)
    monkeypatch.setattr(resilience.trace, "get_current_span", lambda: span)

    trigger_error = RateLimitError()
    resilience.record_model_fallback_switch(
        trigger_error=trigger_error,
        primary_model="primary-model",
        fallback_model="fallback-model",
    )
    resilience.record_model_fallback_result(
        outcome="succeeded",
        trigger_error=trigger_error,
        primary_model="primary-model",
        fallback_model="fallback-model",
        response_model="routed-fallback-model",
    )

    metric_attributes = [call.args[0] for call in recorder.record_llm_fallback.call_args_list]
    assert [attrs["outcome"] for attrs in metric_attributes] == ["started", "succeeded"]
    assert all("gen_ai.request.model" not in attrs for attrs in metric_attributes)
    switch_event = next(call for call in span.add_event.call_args_list if call.args[0] == "gen_ai.fallback.switch")
    assert switch_event.kwargs["attributes"]["gen_ai.request.model"] == "primary-model"
    assert switch_event.kwargs["attributes"]["gen_ai.model.fallback"] == "fallback-model"
    result_event = next(call for call in span.add_event.call_args_list if call.args[0] == "gen_ai.fallback.result")
    assert result_event.kwargs["attributes"]["gen_ai.response.model"] == "routed-fallback-model"


def test_retry_wait_and_deadline_are_separate_low_cardinality_metrics(monkeypatch):
    recorder = MagicMock()
    span = MagicMock()
    span.is_recording.return_value = True
    monkeypatch.setattr(resilience, "get_enabled_agent_metrics", lambda: recorder)
    monkeypatch.setattr(resilience.trace, "get_current_span", lambda: span)

    resilience.record_model_retry(
        outcome="scheduled",
        attempt=2,
        max_attempts=10,
        wait_seconds=60,
        retry_strategy="sdk",
        error="RateLimitError",
    )
    resilience.record_operation_timeout(
        scope="session",
        outcome="cancelled",
        error="AgentDeadlineExceededError",
        timeout_seconds=600,
    )
    resilience.record_operation_timeout(
        scope="tool",
        outcome="failed",
        error="TimeoutError",
        timeout_seconds=30,
    )

    retry_attributes = recorder.record_llm_retry.call_args.args[0]
    assert retry_attributes == {
        "model_role": "primary",
        "retry_strategy": "sdk",
        "error.type": "RateLimitError",
        "outcome": "scheduled",
    }
    assert recorder.record_llm_retry.call_args.kwargs["wait_seconds"] == 60
    timeout_scopes = [call.args[0]["timeout.scope"] for call in recorder.record_operation_timeout.call_args_list]
    assert timeout_scopes == ["session", "tool"]


def test_real_runnable_fallback_records_started_and_success(monkeypatch):
    recorder = MagicMock()
    span = MagicMock()
    span.is_recording.return_value = True
    monkeypatch.setattr(resilience, "get_enabled_agent_metrics", lambda: recorder)
    monkeypatch.setattr(resilience.trace, "get_current_span", lambda: span)

    def _generate(model, *_args, **_kwargs):
        if model.model_name == "primary-model":
            raise RuntimeError("sanitized primary failure")
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="fallback response"))],
            llm_output={"model_name": "routed-fallback-model"},
        )

    monkeypatch.setattr(RawChatOpenAI, "_generate", _generate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    response = model.invoke([HumanMessage(content="hello")])

    assert response.content == "fallback response"
    attributes = [call.args[0] for call in recorder.record_llm_fallback.call_args_list]
    outcomes = [item["outcome"] for item in attributes]
    assert outcomes == ["started", "succeeded"]
    assert {item["error.type"] for item in attributes} == {"RuntimeError"}


def test_fallback_failure_keeps_trigger_error_in_metric_and_own_error_in_event(monkeypatch):
    recorder = MagicMock()
    span = MagicMock()
    span.is_recording.return_value = True
    monkeypatch.setattr(resilience, "get_enabled_agent_metrics", lambda: recorder)
    monkeypatch.setattr(resilience.trace, "get_current_span", lambda: span)

    trigger_error = RateLimitError()
    resilience.record_model_fallback_switch(
        trigger_error=trigger_error,
        primary_model="primary-model",
        fallback_model="fallback-model",
    )
    resilience.record_model_fallback_result(
        outcome="failed",
        trigger_error=trigger_error,
        primary_model="primary-model",
        fallback_model="fallback-model",
        fallback_error=TimeoutError("sanitized"),
    )

    failed_attributes = recorder.record_llm_fallback.call_args.args[0]
    assert failed_attributes == {
        "model_role": "fallback",
        "error.type": "RateLimitError",
        "outcome": "failed",
    }
    result_event = [call for call in span.add_event.call_args_list if call.args[0] == "gen_ai.fallback.result"][-1]
    assert result_event.kwargs["attributes"]["gen_ai.fallback.error.type"] == "TimeoutError"


async def test_real_async_runnable_fallback_records_trigger_error(monkeypatch):
    recorder = MagicMock()
    span = MagicMock()
    span.is_recording.return_value = True
    monkeypatch.setattr(resilience, "get_enabled_agent_metrics", lambda: recorder)
    monkeypatch.setattr(resilience.trace, "get_current_span", lambda: span)

    async def _agenerate(model, *_args, **_kwargs):
        if model.model_name == "primary-model":
            raise RateLimitError()
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="fallback response"))],
            llm_output={"model_name": "routed-fallback-model"},
        )

    monkeypatch.setattr(RawChatOpenAI, "_agenerate", _agenerate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    response = await model.ainvoke([HumanMessage(content="hello")])

    assert response.content == "fallback response"
    attributes = [call.args[0] for call in recorder.record_llm_fallback.call_args_list]
    assert [item["outcome"] for item in attributes] == ["started", "succeeded"]
    assert {item["error.type"] for item in attributes} == {"RateLimitError"}


def test_real_runnable_fallback_failure_records_both_error_categories(monkeypatch):
    recorder = MagicMock()
    span = MagicMock()
    span.is_recording.return_value = True
    monkeypatch.setattr(resilience, "get_enabled_agent_metrics", lambda: recorder)
    monkeypatch.setattr(resilience.trace, "get_current_span", lambda: span)

    def _generate(model, *_args, **_kwargs):
        if model.model_name == "primary-model":
            raise RateLimitError()
        raise TimeoutError("sanitized fallback timeout")

    monkeypatch.setattr(RawChatOpenAI, "_generate", _generate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    with pytest.raises(RateLimitError):
        model.invoke([HumanMessage(content="hello")])

    attributes = [call.args[0] for call in recorder.record_llm_fallback.call_args_list]
    assert [item["outcome"] for item in attributes] == ["started", "failed"]
    assert {item["error.type"] for item in attributes} == {"RateLimitError"}
    result_event = [call for call in span.add_event.call_args_list if call.args[0] == "gen_ai.fallback.result"][-1]
    assert result_event.kwargs["attributes"]["gen_ai.fallback.error.type"] == "TimeoutError"


def test_fallback_failure_propagates_primary_rate_limit_for_outer_deduplication(monkeypatch):
    recorder = MagicMock()
    span = MagicMock()
    span.is_recording.return_value = True
    monkeypatch.setattr(resilience, "get_enabled_agent_metrics", lambda: recorder)
    monkeypatch.setattr(resilience.trace, "get_current_span", lambda: span)

    def _generate(model, *_args, **_kwargs):
        if model.model_name == "primary-model":
            raise RateLimitError()
        raise TimeoutError("sanitized fallback timeout")

    monkeypatch.setattr(RawChatOpenAI, "_generate", _generate)
    model = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

    with pytest.raises(RateLimitError) as error_info:
        model.invoke([HumanMessage(content="hello")])
    resilience.record_model_rate_limit(retry_strategy="sdk", error=error_info.value)

    recorder.record_llm_rate_limit.assert_called_once()
