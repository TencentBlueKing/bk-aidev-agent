from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.opentelemetry import resilience, span_utils
from aidev_agent.packages.opentelemetry.callback_handler import BkAidevAgentCallbackHandler
from aidev_agent.packages.opentelemetry.span_utils import SpanHolder, set_chat_request, set_chat_response
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult, LLMResult
from langchain_openai.chat_models import ChatOpenAI as RawChatOpenAI
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NoOpTracerProvider


class RateLimitError(Exception):
    pass


@pytest.fixture
def tracer_and_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield provider.get_tracer(__name__), exporter
    exporter.clear()


def _raise_parts_error(_msg):
    raise RuntimeError("parts construction failed")


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


async def test_parts_failure_does_not_block_span_end_or_response_attributes(tracer_and_exporter, monkeypatch):
    """REQ-5/AC8: 请求期 parts 构造异常被 @dont_throw 兜住，不阻断响应属性写入与 span 结束"""
    tracer, exporter = tracer_and_exporter
    handler = BkAidevAgentCallbackHandler(tracer=tracer)
    run_id = uuid4()

    monkeypatch.setattr(span_utils, "_chat_message_to_parts_dict", _raise_parts_error)
    await handler.on_chat_model_start(
        serialized={"name": "model-a"},
        messages=[[HumanMessage(content="hello")]],
        run_id=run_id,
    )
    # 异常未向调用方抛出，仅该属性缺失
    assert "gen_ai.input.messages" not in handler.spans[run_id].span.attributes

    monkeypatch.undo()
    await handler.on_llm_end(
        response=LLMResult(generations=[[ChatGeneration(message=AIMessage(content="answer"))]]),
        run_id=run_id,
    )

    spans = exporter.get_finished_spans()
    assert [span.name for span in spans] == ["chat_model.generate"]
    assert spans[0].attributes["gen_ai.output.messages"] == (
        '[{"role": "assistant", "parts": [{"type": "text", "content": "answer"}]}]'
    )
    assert run_id not in handler.spans


def test_model_call_result_unaffected_when_parts_construction_fails(tracer_and_exporter, monkeypatch):
    """AC8: 请求期与响应期 parts 构造异常都不向业务传播，模型返回结果与变更前一致"""
    tracer, _ = tracer_and_exporter
    monkeypatch.setattr(
        RawChatOpenAI,
        "_generate",
        lambda model, *_args, **_kwargs: ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="fallback response"))]
        ),
    )
    monkeypatch.setattr(span_utils, "_chat_message_to_parts_dict", _raise_parts_error)
    model = ChatModel.get_setup_instance(model="primary-model")
    handler = BkAidevAgentCallbackHandler(tracer=tracer)

    response = model.invoke([HumanMessage(content="hello")], config={"callbacks": [handler]})

    assert response.content == "fallback response"


def test_model_call_result_unaffected_without_handler(tracer_and_exporter, monkeypatch):
    """AC8: 无 callback handler 时模型调用结果不变，且不产生 span"""
    _, exporter = tracer_and_exporter
    monkeypatch.setattr(
        RawChatOpenAI,
        "_generate",
        lambda model, *_args, **_kwargs: ChatResult(
            generations=[ChatGeneration(message=AIMessage(content="no handler response"))]
        ),
    )
    model = ChatModel.get_setup_instance(model="primary-model")

    response = model.invoke([HumanMessage(content="hello")])

    assert response.content == "no handler response"
    assert exporter.get_finished_spans() == ()


def test_parts_helpers_are_silent_on_non_recording_span():
    """tracing 关闭（非记录 span）时 set_chat_request / set_chat_response 照常返回 None 且无异常"""
    span = NoOpTracerProvider().get_tracer(__name__).start_span("chat_model.generate")
    holder = SpanHolder(span=span, token=None, context=None, children=[], entity_name=None, entity_path="")

    assert set_chat_request(span, {}, [[HumanMessage(content="hi")]], {}, holder) is None
    assert (
        set_chat_response(
            span,
            LLMResult(
                generations=[
                    [ChatGeneration(message=AIMessage(content="答案", additional_kwargs={"reasoning_content": "思考"}))]
                ]
            ),
        )
        is None
    )
