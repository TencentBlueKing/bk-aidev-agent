# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import asyncio
import re
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from aidev_agent.packages.opentelemetry.callback_handler import (
    AGENT_SDK_VERSION,
    BkAidevAgentCallbackHandler,
    BkAidevAgentInjector,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import NoOpTracerProvider


@pytest.fixture
def tracer_and_exporter():
    """
    创建 tracer 和内存导出器用于测试

    注意: 此 fixture 为每个测试创建独立的 TracerProvider 实例，
    不设置全局 TracerProvider，以确保测试之间的隔离性。
    """
    # 创建内存导出器
    exporter = InMemorySpanExporter()

    # 创建 TracerProvider
    provider = TracerProvider()
    span_processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(span_processor)

    # 直接从 provider 获取 tracer，不设置全局 TracerProvider
    tracer = provider.get_tracer(__name__)

    yield tracer, exporter

    # 强制刷新所有 spans
    span_processor.force_flush()

    # 清理
    exporter.clear()


class TestBkAidevAgentInjector:
    """测试 BkAidevAgentInjector 类"""

    def test_on_bk_agent_start_span_attributes(self, tracer_and_exporter):
        """测试 on_bk_agent_start 创建的 span 包含所有必需的属性"""
        tracer, exporter = tracer_and_exporter

        # 准备测试数据 - 使用 Mock 对象代替真实的 ExecuteKwargs
        execute_kwargs = MagicMock()
        execute_kwargs.executor = "test-executor"
        execute_kwargs.session_code = "test-session-123"
        execute_kwargs.caller_bk_app_code = "test-app"
        execute_kwargs.caller_bk_biz_env = "domestic_biz"
        execute_kwargs.caller_bk_biz_id = 123
        execute_kwargs.caller_executor = "test-user"
        execute_kwargs.caller_order_type = "ai_chat"

        agent_info = {
            "agent_id": "agent-123",
            "agent_code": "test_agent",
            "agent_name": "测试智能体",
            "agent_type": "qa",
            "service_catalogue": "test_service",
            "updated_by": "admin",
        }

        inputs = {"input": "测试输入"}

        # 创建 BkAidevAgentInjector 实例
        injector = BkAidevAgentInjector(tracer=tracer, debug=True)

        # 调用 on_bk_agent_start
        injector.on_bk_agent_start(
            inputs=inputs,
            execute_kwargs=execute_kwargs,
            agent_info=agent_info,
        )

        # 结束 span
        injector.on_bk_agent_end()

        # 获取导出的 spans
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]

        # 验证 span 名称
        assert span.name == "agent.execution"

        # 验证 agent.info.* 属性
        assert span.attributes["agent.info.id"] == "agent-123"
        assert span.attributes["agent.info.code"] == "test_agent"
        assert span.attributes["agent.info.name"] == "测试智能体"
        assert span.attributes["agent.info.type"] == "qa"
        assert span.attributes["agent.info.service_catalogue"] == "test_service"
        assert span.attributes["agent.info.updated_by"] == "admin"
        assert "agent.info.sdk_version" in span.attributes
        assert "agent.info.agent_info" in span.attributes

        # 验证 agent.session.* 属性
        assert span.attributes["agent.session.executor"] == "test-executor"
        assert span.attributes["agent.session.session_code"] == "test-session-123"
        assert span.attributes["agent.session.caller_executor"] == "test-user"
        assert span.attributes["agent.session.caller_bk_app_code"] == "test-app"
        assert span.attributes["agent.session.caller_bk_biz_env"] == "domestic_biz"
        assert span.attributes["agent.session.caller_bk_biz_id"] == 123
        assert span.attributes["agent.session.caller_order_type"] == "ai_chat"
        assert "agent.session.input" in span.attributes
        assert "agent.session.start_time" in span.attributes
        assert "agent.session.start_time_unix_nano" in span.attributes

        # 验证 debug 属性（start 与 end 都应记录线程名，便于排查跨线程结束 root span 的场景）
        assert "debug.thread_id" in span.attributes
        assert "debug.end_thread_id" in span.attributes

    def test_on_bk_agent_end_records_end_thread_when_cross_thread(self, tracer_and_exporter):
        """跨线程结束 root span 时，``debug.end_thread_id`` 应记录的是 end 线程，而非 start 线程。

        模拟生产场景：start 发生在 HTTP 线程，end 由 LangChain callback
        在 producer 线程触发（这是 trace 上报丢失修复后的新行为）。
        """
        import threading as _threading

        tracer, exporter = tracer_and_exporter
        execute_kwargs = MagicMock()
        execute_kwargs.executor = "u"
        execute_kwargs.session_code = "s"
        execute_kwargs.caller_bk_app_code = "app"
        execute_kwargs.caller_bk_biz_env = "env"
        execute_kwargs.caller_bk_biz_id = 1
        execute_kwargs.caller_executor = "u"
        execute_kwargs.caller_order_type = "ai_chat"
        agent_info = {"agent_id": "a", "agent_code": "c", "agent_name": "n"}

        injector = BkAidevAgentInjector(tracer=tracer, debug=True)
        # start 在主线程
        injector.on_bk_agent_start(inputs={"input": "x"}, execute_kwargs=execute_kwargs, agent_info=agent_info)
        start_thread_name = _threading.current_thread().name

        # end 在子线程
        producer_thread_name = "producer-thread-1"
        t = _threading.Thread(target=injector.on_bk_agent_end, name=producer_thread_name)
        t.start()
        t.join()

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.attributes["debug.thread_id"] == start_thread_name
        assert span.attributes["debug.end_thread_id"] == producer_thread_name

    @pytest.mark.parametrize("session_code", ["session-a", "session-b"])
    def test_root_span_carries_gen_ai_conversation_id(self, tracer_and_exporter, session_code):
        """根 span 冗余 gen_ai.conversation.id 便于按会话检索，但不赋 gen_ai.operation.name"""
        tracer, exporter = tracer_and_exporter
        execute_kwargs = MagicMock()
        execute_kwargs.executor = "u"
        execute_kwargs.session_code = session_code
        execute_kwargs.caller_bk_app_code = "app"
        execute_kwargs.caller_bk_biz_env = "env"
        execute_kwargs.caller_bk_biz_id = 1
        execute_kwargs.caller_executor = "u"
        execute_kwargs.caller_order_type = "ai_chat"

        injector = BkAidevAgentInjector(tracer=tracer)
        injector.on_bk_agent_start(inputs={"input": "x"}, execute_kwargs=execute_kwargs, agent_info={})
        injector.on_bk_agent_end()

        span = exporter.get_finished_spans()[0]
        assert span.name == "agent.execution"
        assert span.attributes["gen_ai.conversation.id"] == session_code
        assert "gen_ai.operation.name" not in span.attributes

    def test_root_span_writes_empty_conversation_id_without_session_code(self, tracer_and_exporter):
        """session_code 为空时 gen_ai.conversation.id 恒存在：写空字符串而非缺键"""
        tracer, exporter = tracer_and_exporter
        execute_kwargs = MagicMock()
        execute_kwargs.session_code = None
        execute_kwargs.executor = None
        execute_kwargs.caller_bk_app_code = None
        execute_kwargs.caller_bk_biz_env = None
        execute_kwargs.caller_bk_biz_id = None
        execute_kwargs.caller_executor = None
        execute_kwargs.caller_order_type = None

        injector = BkAidevAgentInjector(tracer=tracer)
        injector.on_bk_agent_start(inputs={"input": "x"}, execute_kwargs=execute_kwargs, agent_info={})
        injector.on_bk_agent_end()

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.conversation.id"] == ""


class TestBkAidevAgentCallbackHandler:
    """测试 BkAidevAgentCallbackHandler 类"""

    def test_agent_metrics_follow_top_level_chain_without_injector(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        run_id = uuid4()

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=run_id))
        asyncio.run(handler.on_chain_end(outputs={}, run_id=run_id))

        recorder.record_active_agent.assert_any_call(1, handler._metric_agent_attributes)
        recorder.record_active_agent.assert_any_call(-1, handler._metric_agent_attributes)
        recorder.record_agent.assert_called_once()

    def test_agent_metrics_are_finalized_once_on_top_level_error(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        run_id = uuid4()
        error = RuntimeError("boom")

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=run_id))
        asyncio.run(handler.on_chain_error(error, run_id=run_id))
        handler._finalize_injector(error=error)

        assert recorder.record_active_agent.call_count == 2
        recorder.record_active_agent.assert_called_with(-1, handler._metric_agent_attributes)
        recorder.record_agent.assert_called_once()

    def test_active_llm_is_decremented_with_the_same_dimensions(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        run_id = uuid4()

        asyncio.run(handler.on_llm_start(serialized={"name": "model-a"}, prompts=["hello"], run_id=run_id))
        asyncio.run(handler.on_llm_error(RuntimeError("boom"), run_id=run_id))

        assert recorder.record_active_llm.call_count == 2
        start_call, end_call = recorder.record_active_llm.call_args_list
        assert start_call.args[0] == 1
        assert end_call.args[0] == -1
        assert start_call.args[1] == end_call.args[1]

    def test_agent_iteration_count_equals_llm_start_callbacks_in_one_run(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        chain_run_id = uuid4()
        llm_run_id = uuid4()
        chat_run_id = uuid4()

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=chain_run_id))
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "model-a"},
                prompts=["hello"],
                run_id=llm_run_id,
                parent_run_id=chain_run_id,
            )
        )
        asyncio.run(handler.on_llm_error(RuntimeError("retry"), run_id=llm_run_id, parent_run_id=chain_run_id))
        asyncio.run(
            handler.on_chat_model_start(
                serialized={"name": "model-b"},
                messages=[[HumanMessage(content="retry")]],
                run_id=chat_run_id,
                parent_run_id=chain_run_id,
            )
        )
        asyncio.run(handler.on_llm_error(RuntimeError("boom"), run_id=chat_run_id, parent_run_id=chain_run_id))
        asyncio.run(handler.on_chain_end(outputs={}, run_id=chain_run_id))

        assert recorder.record_agent.call_args.kwargs["iteration_count"] == 2

    def test_agent_phase_and_first_token_metrics_follow_runtime_callbacks(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        chain_run_id = uuid4()
        llm_run_id = uuid4()

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=chain_run_id))
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "model-a"},
                prompts=["hello"],
                run_id=llm_run_id,
                parent_run_id=chain_run_id,
            )
        )
        asyncio.run(handler.on_llm_new_token("a", run_id=llm_run_id, parent_run_id=chain_run_id))
        asyncio.run(handler.on_llm_new_token("b", run_id=llm_run_id, parent_run_id=chain_run_id))
        asyncio.run(handler.on_llm_error(RuntimeError("boom"), run_id=llm_run_id, parent_run_id=chain_run_id))
        asyncio.run(handler.on_chain_end(outputs={}, run_id=chain_run_id))

        recorder.record_agent_started.assert_called_once_with(handler._metric_agent_attributes)
        recorder.record_agent_first_token.assert_called_once()
        phase_deltas: dict[str, int] = {}
        for call in recorder.record_agent_phase_active.call_args_list:
            phase_deltas[call.args[1]] = phase_deltas.get(call.args[1], 0) + call.args[0]
        assert phase_deltas == {"processing": 0, "llm": 0, "finalizing": 0}

    def test_active_tool_is_decremented_with_the_same_dimensions(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        run_id = uuid4()

        asyncio.run(handler.on_tool_start(serialized={"name": "demo-tool"}, input_str="input", run_id=run_id))
        asyncio.run(handler.on_tool_error(RuntimeError("boom"), run_id=run_id))

        assert recorder.record_active_tool.call_count == 2
        start_call, end_call = recorder.record_active_tool.call_args_list
        assert start_call.args[0] == 1
        assert end_call.args[0] == -1
        assert start_call.args[1] == end_call.args[1]

    def test_finalize_balances_unfinished_llm_and_tool_operations(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        chain_run_id = uuid4()
        llm_run_id = uuid4()
        tool_run_id = uuid4()

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=chain_run_id))
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "model-a"},
                prompts=["hello"],
                run_id=llm_run_id,
                parent_run_id=chain_run_id,
            )
        )
        asyncio.run(
            handler.on_tool_start(
                serialized={"name": "demo-tool"},
                input_str="input",
                run_id=tool_run_id,
                parent_run_id=chain_run_id,
            )
        )
        asyncio.run(handler.on_chain_error(RuntimeError("cancelled"), run_id=chain_run_id))

        assert [call.args[0] for call in recorder.record_active_llm.call_args_list] == [1, -1]
        assert [call.args[0] for call in recorder.record_active_tool.call_args_list] == [1, -1]
        assert handler._active_llm_operation_count == 0
        assert handler._active_tool_operation_count == 0

    def test_tool_error_metric_is_recorded_when_traces_are_disabled(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(
            tracer=tracer,
            enable_traces=False,
            metric_recorder=recorder,
        )
        run_id = uuid4()
        error = RuntimeError("boom")

        asyncio.run(handler.on_tool_start(serialized={"name": "demo-tool"}, input_str="input", run_id=run_id))
        asyncio.run(handler.on_tool_error(error, run_id=run_id))

        recorder.record_tool.assert_called_once()
        assert recorder.record_tool.call_args.kwargs["error"] is error

    def test_tool_timeout_is_classified_separately_from_session_deadline(self, tracer_and_exporter, mocker):
        tracer, _ = tracer_and_exporter
        timeout_metric = mocker.patch("aidev_agent.packages.opentelemetry.callback_handler.record_operation_timeout")
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=MagicMock())
        run_id = uuid4()

        asyncio.run(handler.on_tool_start(serialized={"name": "demo-tool"}, input_str="input", run_id=run_id))
        asyncio.run(handler.on_tool_error(TimeoutError("upstream timed out"), run_id=run_id))

        timeout_metric.assert_called_once()
        assert timeout_metric.call_args.kwargs["scope"] == "tool"
        assert timeout_metric.call_args.kwargs["outcome"] == "failed"

    def test_llm_metric_keeps_request_model_when_traces_are_disabled(self):
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(
            tracer=NoOpTracerProvider().get_tracer(__name__),
            enable_traces=False,
            metric_recorder=recorder,
        )
        run_id = uuid4()

        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "demo-model"},
                prompts=["hello"],
                run_id=run_id,
                invocation_params={"model": "qwen3"},
            )
        )

        attributes = recorder.record_active_llm.call_args_list[0].args[1]
        assert attributes["gen_ai.request.model"] == "qwen3"

    def test_llm_generate_span_attributes(self, tracer_and_exporter):
        """测试 llm.generate span 包含 llm.input 和 llm.output 属性"""
        tracer, exporter = tracer_and_exporter

        # 创建回调处理器
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟 LLM 调用
        run_id = uuid4()
        parent_run_id = None

        # LLM 开始（async 回调需 await，否则 dont_throw + async 双装饰会让函数体静默不执行）
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "test_llm"},
                prompts=["请回答这个问题"],
                run_id=run_id,
                parent_run_id=parent_run_id,
            )
        )

        # LLM 结束
        llm_result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="这是答案"))]],
            llm_output={"model_name": "qwen3"},
        )

        asyncio.run(
            handler.on_llm_end(
                response=llm_result,
                run_id=run_id,
                parent_run_id=parent_run_id,
            )
        )

        # 获取导出的 spans
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]

        # 验证 span 名称
        assert span.name == "llm.generate"

        # 验证包含 llm.input 和 llm.output 属性
        assert "llm.input" in span.attributes
        assert "llm.output" in span.attributes

    def test_chat_model_generate_span_attributes(self, tracer_and_exporter):
        """测试 chat_model.generate span 包含 llm.input 和 llm.output 属性"""
        tracer, exporter = tracer_and_exporter

        # 创建回调处理器
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟 Chat Model 调用
        run_id = uuid4()
        parent_run_id = None

        # Chat Model 开始
        messages = [[HumanMessage(content="你好")]]
        asyncio.run(
            handler.on_chat_model_start(
                serialized={"name": "test_chat_model"},
                messages=messages,
                run_id=run_id,
                parent_run_id=parent_run_id,
            )
        )

        # Chat Model 结束
        llm_result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="你好,我是AI助手"))]],
            llm_output={"model_name": "qwen3"},
        )

        asyncio.run(
            handler.on_llm_end(
                response=llm_result,
                run_id=run_id,
                parent_run_id=parent_run_id,
            )
        )

        # 获取导出的 spans
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]

        # 验证 span 名称
        assert span.name == "chat_model.generate"

        # 验证包含 llm.input 和 llm.output 属性
        assert "llm.input" in span.attributes
        assert "llm.output" in span.attributes

    def test_llm_content_uses_separate_input_and_output_limits(self, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(
            tracer=tracer,
            max_input_attribute_length=8,
            max_output_attribute_length=4,
        )
        run_id = uuid4()

        asyncio.run(handler.on_llm_start(serialized={}, prompts=["0123456789"], run_id=run_id))
        response = LLMResult(generations=[[ChatGeneration(message=AIMessage(content="abcdefghij"))]])
        asyncio.run(handler.on_llm_end(response=response, run_id=run_id))

        span = exporter.get_finished_spans()[0]
        assert len(span.attributes["llm.input"]) == 8
        assert len(span.attributes["gen_ai.input.messages"]) == 8
        assert len(span.attributes["llm.output"]) == 4
        assert len(span.attributes["gen_ai.output.messages"]) == 4

    def test_tool_execution_span_attributes(self, tracer_and_exporter):
        """测试 tool.* span 包含 tool.input 属性"""
        tracer, exporter = tracer_and_exporter

        # 创建回调处理器
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟工具调用
        run_id = uuid4()
        parent_run_id = None

        # 工具开始
        asyncio.run(
            handler.on_tool_start(
                serialized={"name": "calculator"},
                input_str="1+1",
                run_id=run_id,
                parent_run_id=parent_run_id,
            )
        )

        # 工具结束
        asyncio.run(
            handler.on_tool_end(
                output="2",
                run_id=run_id,
                parent_run_id=parent_run_id,
            )
        )

        # 获取导出的 spans
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]

        # 验证 span 名称
        assert span.name == "tool.execution"

        # 验证包含 tool.input 属性
        assert span.attributes["tool.input"] == "1+1"
        assert span.attributes["tool.name"] == "calculator"

    def test_tool_content_uses_separate_input_and_output_limits(self, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(
            tracer=tracer,
            max_input_attribute_length=8,
            max_output_attribute_length=4,
        )
        run_id = uuid4()

        asyncio.run(handler.on_tool_start(serialized={"name": "bounded"}, input_str="0123456789", run_id=run_id))
        asyncio.run(handler.on_tool_end(output="abcdefghij", run_id=run_id))

        span = exporter.get_finished_spans()[0]
        assert span.attributes["tool.input"] == "23456789"
        assert span.attributes["gen_ai.tool.call.result"] == "ghij"

    def test_mcp_tool_execution_span_has_mcp_semantic_attributes(self, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        asyncio.run(
            handler.on_tool_start(
                serialized={"name": "search"},
                input_str='{"query": "blueking"}',
                run_id=run_id,
                metadata={"mcp_name": "resource", "mcp_transport": "streamable_http"},
            )
        )
        asyncio.run(handler.on_tool_end(output="ok", run_id=run_id))

        span = exporter.get_finished_spans()[0]
        assert span.attributes["tool.type"] == "mcp"
        assert span.attributes["rpc.system.name"] == "jsonrpc"
        assert span.attributes["mcp.method.name"] == "tools/call"
        assert span.attributes["mcp.server.name"] == "resource"
        assert span.attributes["mcp.transport"] == "streamable_http"

    def test_http_tool_execution_span_has_interface_attributes(self, tracer_and_exporter):
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        asyncio.run(
            handler.on_tool_start(
                serialized={"name": "get_ticket"},
                input_str="{}",
                run_id=run_id,
                metadata={"tool_code": "get_ticket"},
            )
        )
        asyncio.run(handler.on_tool_end(output="ok", run_id=run_id))

        span = exporter.get_finished_spans()[0]
        assert span.attributes["tool.type"] == "http_api"
        assert span.attributes["tool.code"] == "get_ticket"

    def test_rag_retrieval_span_attributes(self, tracer_and_exporter):
        """测试 rag.retrieval span 包含 rag.knowledge_bases 和 rag.knowledge_items 属性"""
        tracer, exporter = tracer_and_exporter

        # 创建回调处理器
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 创建一个顶层 workflow chain 以便挂载自定义 span
        chain_run_id = uuid4()
        asyncio.run(
            handler.on_chain_start(
                serialized={"name": "test_workflow"},
                inputs={"input": "测试"},
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        # 使用 create_custom_span 创建 RAG span
        with handler.create_custom_span(
            "rag.retrieval",
            attributes={
                "query": "测试查询",
                "knowledge_bases": [1, 2, 3],
                "knowledge_items": [101, 102],
            },
        ):
            # 模拟 RAG 检索
            pass

        # 结束 chain
        asyncio.run(
            handler.on_chain_end(
                outputs={"output": "结果"},
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        # 获取导出的 spans
        spans = exporter.get_finished_spans()

        # 找到 rag.retrieval span
        rag_span = None
        for s in spans:
            if s.name == "rag.retrieval":
                rag_span = s
                break

        assert rag_span is not None

        # operation.name=retrieval 由建 span 漏斗按 rag.retrieval span 名统一写入
        assert rag_span.attributes["gen_ai.operation.name"] == "retrieval"

        # 验证包含 rag.knowledge_bases 和 rag.knowledge_items 属性
        assert rag_span.attributes["query"] == "测试查询"
        assert "knowledge_bases" in rag_span.attributes
        assert "knowledge_items" in rag_span.attributes

    def _run_llm_call(self, handler, token_usage, *, use_chat=False):
        """构造一次带 token_usage 的 LLM 调用并执行 on_llm_start/on_llm_end。

        返回 run_id，便于调用方精确断言该次调用的 span 属性。
        """
        run_id = uuid4()
        if use_chat:
            asyncio.run(
                handler.on_chat_model_start(
                    serialized={"name": "test_chat_model"},
                    messages=[[HumanMessage(content="你好")]],
                    run_id=run_id,
                    parent_run_id=None,
                )
            )
        else:
            asyncio.run(
                handler.on_llm_start(
                    serialized={"name": "test_llm"},
                    prompts=["请回答这个问题"],
                    run_id=run_id,
                    parent_run_id=None,
                )
            )
        llm_result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
            llm_output={"model_name": "qwen3", "token_usage": token_usage},
        )
        asyncio.run(
            handler.on_llm_end(
                response=llm_result,
                run_id=run_id,
                parent_run_id=None,
            )
        )
        return run_id

    def test_llm_generate_span_token_usage_attributes(self, tracer_and_exporter):
        """Test 1: llm.generate span 设 gen_ai.usage.input_tokens/output_tokens 为 int（total 由 collector 推导）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        self._run_llm_call(
            handler,
            {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        )

        spans = exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "llm.generate")
        assert span.attributes["gen_ai.usage.input_tokens"] == 10
        assert span.attributes["gen_ai.usage.output_tokens"] == 5
        assert "gen_ai.usage.total_tokens" not in span.attributes

    def test_chat_model_generate_span_token_usage_attributes(self, tracer_and_exporter):
        """Test 2: chat_model.generate span 设 gen_ai.usage.*（同一 on_llm_end 路径）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        self._run_llm_call(
            handler,
            {"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
            use_chat=True,
        )

        spans = exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "chat_model.generate")
        assert span.attributes["gen_ai.usage.input_tokens"] == 20
        assert span.attributes["gen_ai.usage.output_tokens"] == 8
        assert "gen_ai.usage.total_tokens" not in span.attributes

    def _make_root_span_handler(self, tracer):
        """构造带有效 injector 的 handler，使顶层 chain 能创建 root span。

        injector.on_bk_agent_start 会解引用 execute_kwargs.session_code 等字段，
        故必须传入一个带完整属性的 ExecuteKwargs mock，否则 root span 无法创建。
        """
        execute_kwargs = MagicMock()
        execute_kwargs.executor = "test-executor"
        execute_kwargs.session_code = "test-session-123"
        execute_kwargs.caller_bk_app_code = "test-app"
        execute_kwargs.caller_bk_biz_env = "domestic_biz"
        execute_kwargs.caller_bk_biz_id = 123
        execute_kwargs.caller_executor = "test-user"
        execute_kwargs.caller_order_type = "ai_chat"
        injector = BkAidevAgentInjector(tracer=tracer, debug=True)
        handler = BkAidevAgentCallbackHandler(
            tracer=tracer,
            debug=True,
            injector=injector,
            start_inputs={"input": "x"},
            start_execute_kwargs=execute_kwargs,
            start_agent_info={"agent_id": "a", "agent_code": "c", "agent_name": "n"},
        )
        return handler

    def test_root_span_session_total_tokens_normal_path(self, tracer_and_exporter):
        """Test 3: root span agent.session.total_*_tokens == 2 次 LLM 调用累加和（on_chain_end 正常路径）"""
        tracer, exporter = tracer_and_exporter
        handler = self._make_root_span_handler(tracer)

        chain_run_id = uuid4()
        asyncio.run(
            handler.on_chain_start(
                serialized={"name": "wf"},
                inputs={"input": "x"},
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

        asyncio.run(
            handler.on_chain_end(
                outputs={"output": "r"},
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        spans = exporter.get_finished_spans()
        root = next(s for s in spans if s.name == "agent.execution")
        assert root.attributes["agent.session.total_input_tokens"] == 20
        assert root.attributes["agent.session.total_output_tokens"] == 10
        assert root.attributes["agent.session.total_tokens"] == 30

    def test_root_span_session_total_tokens_on_chain_error(self, tracer_and_exporter):
        """Test 4: on_chain_error 顶层路径 root span 仍有 agent.session.total_*_tokens"""
        tracer, exporter = tracer_and_exporter
        handler = self._make_root_span_handler(tracer)

        chain_run_id = uuid4()
        asyncio.run(
            handler.on_chain_start(
                serialized={"name": "wf"},
                inputs={"input": "x"},
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

        asyncio.run(
            handler.on_chain_error(
                error=ValueError("boom"),
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        spans = exporter.get_finished_spans()
        root = next(s for s in spans if s.name == "agent.execution")
        assert root.attributes["agent.session.total_input_tokens"] == 20
        assert root.attributes["agent.session.total_output_tokens"] == 10
        assert root.attributes["agent.session.total_tokens"] == 30

    def test_root_span_session_total_tokens_generator_exit(self, tracer_and_exporter):
        """Test 5: on_chain_error GeneratorExit 关流路径 root span 仍有汇总"""
        tracer, exporter = tracer_and_exporter
        handler = self._make_root_span_handler(tracer)

        chain_run_id = uuid4()
        asyncio.run(
            handler.on_chain_start(
                serialized={"name": "wf"},
                inputs={"input": "x"},
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})
        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

        asyncio.run(
            handler.on_chain_error(
                error=GeneratorExit(),
                run_id=chain_run_id,
                parent_run_id=None,
            )
        )

        spans = exporter.get_finished_spans()
        root = next(s for s in spans if s.name == "agent.execution")
        assert root.attributes["agent.session.total_input_tokens"] == 20
        assert root.attributes["agent.session.total_output_tokens"] == 10
        assert root.attributes["agent.session.total_tokens"] == 30

    def test_malformed_llm_output_no_usage_attributes(self, tracer_and_exporter):
        """Test 6: 畸形 llm_output → 无数值型 usage 属性、计数器不变、不抛异常"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        run_id = uuid4()
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "test_llm"},
                prompts=["请回答这个问题"],
                run_id=run_id,
                parent_run_id=None,
            )
        )
        malformed = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="x"))]],
            llm_output=None,
        )
        asyncio.run(
            handler.on_llm_end(
                response=malformed,
                run_id=run_id,
                parent_run_id=None,
            )
        )

        spans = exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "llm.generate")
        # 数值型 usage 键缺失；缓存三键按恒存在语义写空串
        number_keys = ("gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens")
        assert all(key not in span.attributes for key in number_keys)
        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == ""
        assert handler._total_input_tokens == 0
        assert handler._total_output_tokens == 0
        assert handler._total_total_tokens == 0

    def test_usage_metadata_details_sets_cache_and_reasoning(self, tracer_and_exporter):
        """Test 7: usage_metadata 有 details → cached_tokens/reasoning_tokens 属性被设置"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        run_id = uuid4()
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "test_llm"},
                prompts=["请回答这个问题"],
                run_id=run_id,
                parent_run_id=None,
            )
        )
        llm_result = LLMResult(
            generations=[
                [
                    ChatGeneration(
                        message=AIMessage(
                            content="答案",
                            usage_metadata={
                                "input_tokens": 10,
                                "output_tokens": 5,
                                "total_tokens": 15,
                                "input_token_details": {"cache_read": 3},
                                "output_token_details": {"reasoning": 2},
                            },
                        )
                    )
                ]
            ],
            llm_output={"model_name": "qwen3"},
        )
        asyncio.run(
            handler.on_llm_end(
                response=llm_result,
                run_id=run_id,
                parent_run_id=None,
            )
        )

        spans = exporter.get_finished_spans()
        span = next(s for s in spans if s.name == "llm.generate")
        assert span.attributes["gen_ai.usage.input_tokens"] == 10
        assert span.attributes["gen_ai.usage.output_tokens"] == 5
        assert "gen_ai.usage.total_tokens" not in span.attributes
        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 3
        # 上报过缓存字段（details 内 cache_read）：同批未出现的 cache_creation 写真 0
        assert span.attributes["gen_ai.usage.cache_write.input_tokens"] == 0
        assert span.attributes["gen_ai.usage.reasoning.output_tokens"] == 2

    def test_llm_end_provider_native_completion_details_sets_reasoning(self, tracer_and_exporter):
        """provider 原始 usage 的 completion_tokens_details.reasoning_tokens → span reasoning 属性；span 无 total_tokens"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_llm_call(
            handler,
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "completion_tokens_details": {"reasoning_tokens": 4},
            },
        )

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.usage.reasoning.output_tokens"] == 4
        assert "gen_ai.usage.total_tokens" not in span.attributes

    @pytest.mark.parametrize("chain_name", ["qa_chain", "rag_chain"])
    async def test_top_level_chain_span_carries_invoke_agent_attributes(self, tracer_and_exporter, chain_name):
        """顶层 chain 是一次 agent 执行主体：invoke_agent 命名 + gen_ai.agent.* + conversation.id"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(
            tracer=tracer,
            agent_code="test_agent",
            agent_name="显示名",
            session_code="session-9",
        )
        run_id = uuid4()
        await handler.on_chain_start({"name": chain_name}, {}, run_id=run_id, parent_run_id=None)

        span = handler.spans[run_id].span
        assert span.name == "invoke_agent test_agent"
        assert span.attributes["chain.name"] == chain_name
        assert span.attributes["gen_ai.operation.name"] == "invoke_agent"
        assert span.attributes["gen_ai.agent.name"] == "显示名"
        assert span.attributes["gen_ai.conversation.id"] == "session-9"
        assert span.attributes["gen_ai.agent.description"] == ""
        assert span.attributes["gen_ai.agent.version"] == AGENT_SDK_VERSION
        # 通用层旧键已删除（agent.info.code 为唯一保留旧键，未传 agent_id 时不写 gen_ai.agent.id）
        assert "agent.info.id" not in span.attributes
        assert "agent.info.name" not in span.attributes
        assert "agent.session.session_code" not in span.attributes
        assert "agent.session.caller_executor" not in span.attributes

    async def test_create_span_replaces_generic_agent_keys_with_gen_ai_semantics(self, tracer_and_exporter):
        """非根 span 通用注入：四旧键换 gen_ai 语义四新键，agent.info.code 保留"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(
            tracer=tracer,
            agent_id="agent-1",
            agent_code="test_agent",
            agent_name="显示名",
            session_code="session-1",
            caller_executor="caller-user",
        )
        run_id = uuid4()
        await handler.on_tool_start(serialized={"name": "calculator"}, input_str="1+1", run_id=run_id)

        span = handler.spans[run_id].span
        assert span.attributes["gen_ai.agent.id"] == "agent-1"
        assert span.attributes["gen_ai.agent.name"] == "显示名"
        assert span.attributes["gen_ai.conversation.id"] == "session-1"
        assert span.attributes["user.name"] == "caller-user"
        assert span.attributes["agent.info.code"] == "test_agent"
        assert span.attributes["gen_ai.operation.name"] == "execute_tool"
        assert "agent.info.id" not in span.attributes
        assert "agent.info.name" not in span.attributes
        assert "agent.session.session_code" not in span.attributes
        assert "agent.session.caller_executor" not in span.attributes

    @pytest.mark.parametrize("child_name", ["model_node", "tool_node"])
    async def test_nested_chain_span_carries_execute_task_attributes(self, tracer_and_exporter, child_name):
        """graph 内节点/子链：execute_task + task.name"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        parent_id, child_id = uuid4(), uuid4()
        await handler.on_chain_start({"name": "graph"}, {}, run_id=parent_id, parent_run_id=None)
        await handler.on_chain_start({"name": child_name}, {}, run_id=child_id, parent_run_id=parent_id)

        span = handler.spans[child_id].span
        assert span.name == "chain.task"
        assert span.attributes["gen_ai.operation.name"] == "execute_task"
        assert span.attributes["gen_ai.task.name"] == child_name

    @pytest.mark.parametrize(
        "use_chat, span_name, expected_operation",
        [(True, "chat_model.generate", "chat"), (False, "llm.generate", "text_completion")],
    )
    async def test_llm_span_carries_gen_ai_operation_name(
        self, tracer_and_exporter, use_chat, span_name, expected_operation
    ):
        """LLM span 建 span 期即写 operation.name：chat 模型 chat，纯文本补全 text_completion"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        if use_chat:
            await handler.on_chat_model_start(
                serialized={"name": "test_chat_model"},
                messages=[[HumanMessage(content="你好")]],
                run_id=run_id,
            )
        else:
            await handler.on_llm_start(serialized={"name": "test_llm"}, prompts=["请回答"], run_id=run_id)

        span = handler.spans[run_id].span
        assert span.name == span_name
        assert span.attributes["gen_ai.operation.name"] == expected_operation

    def test_llm_end_writes_cache_write_alongside_cache_creation(self, tracer_and_exporter):
        """on_llm_end 在既有 cache_creation 之外双写官方新名 cache_write（零破坏）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        asyncio.run(handler.on_llm_start(serialized={"name": "test_llm"}, prompts=["请回答"], run_id=run_id))
        llm_result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
            llm_output={
                "model_name": "qwen3",
                "token_usage": {
                    "prompt_tokens": 30,
                    "completion_tokens": 5,
                    "total_tokens": 35,
                    "cache_creation_input_tokens": 12,
                    "cache_read_input_tokens": 3,
                },
            },
        )
        asyncio.run(handler.on_llm_end(response=llm_result, run_id=run_id))

        span = exporter.get_finished_spans()[0]
        # input_tokens 含缓存总数 = (30-12-3) + 3 + 12，恰好还原 provider 总数
        assert span.attributes["gen_ai.usage.input_tokens"] == 30
        assert span.attributes["gen_ai.usage.cache_creation.input_tokens"] == 12
        assert span.attributes["gen_ai.usage.cache_write.input_tokens"] == 12

    def test_llm_end_cache_read_follows_metrics_extractor(self, tracer_and_exporter):
        """cache_read 只由 metrics 提取器写入：两个提取器取值冲突时不再受语句顺序影响"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_llm_call(
            handler,
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "input_token_details": {"cache_read": 3},
                "cache_read_input_tokens": 7,
            },
        )

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 7

    def test_llm_end_writes_empty_cache_attributes_without_cache_usage(self, tracer_and_exporter):
        """模型从未上报缓存字段：缓存三键写空串（字段恒存在），空串而非 0 避免污染命中率统计"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == ""
        assert span.attributes["gen_ai.usage.cache_creation.input_tokens"] == ""
        assert span.attributes["gen_ai.usage.cache_write.input_tokens"] == ""

    def test_llm_end_writes_zero_cache_attributes_when_provider_reports_zero(self, tracer_and_exporter):
        """provider 上报缓存字段但命中 0：三键写真 0（区别于未上报的空串）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_llm_call(
            handler,
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
        )

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 0
        assert span.attributes["gen_ai.usage.cache_creation.input_tokens"] == 0
        assert span.attributes["gen_ai.usage.cache_write.input_tokens"] == 0

    def test_llm_end_input_tokens_includes_cache_without_double_counting(self, tracer_and_exporter):
        """provider 总数已含缓存（prompt_tokens + cached_tokens 形状）：还原总数而非再叠加 cache"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_llm_call(
            handler,
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "prompt_tokens_details": {"cached_tokens": 4},
            },
        )

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.usage.input_tokens"] == 10
        assert span.attributes["gen_ai.usage.cache_read.input_tokens"] == 4

    def _run_streamed_llm_call(self, handler, *, model_name="qwen3"):
        """构造一次流式 LLM 调用（llm_output 为 None，served 模型名/id/ttfc 由末 chunk generation_info 携带）。"""
        run_id = uuid4()
        asyncio.run(handler.on_llm_start(serialized={"name": "test_llm"}, prompts=["请回答"], run_id=run_id))
        asyncio.run(
            handler.on_llm_end(
                response=LLMResult(
                    generations=[
                        [
                            ChatGeneration(
                                message=AIMessage(content="答案"),
                                generation_info={
                                    "time_to_first_chunk": 0.05,
                                    "model_name": model_name,
                                    "id": "chatcmpl-1",
                                    "finish_reason": "stop",
                                },
                            )
                        ]
                    ],
                    llm_output=None,
                ),
                run_id=run_id,
            )
        )
        return run_id

    @pytest.mark.parametrize("enable_metrics", [True, False])
    def test_llm_end_backfills_stream_and_ttfc_for_streamed_call(self, tracer_and_exporter, enable_metrics):
        """流式调用：响应期实化 stream=True 与非负 float 秒 ttfc；metrics 开关无关（ttfc 经首 chunk 携带）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, enable_metrics=enable_metrics)

        self._run_streamed_llm_call(handler)

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.request.stream"] is True
        ttfc = span.attributes["gen_ai.response.time_to_first_chunk"]
        assert isinstance(ttfc, float)
        assert ttfc >= 0

    def test_llm_end_writes_served_model_and_response_id_for_streamed_call(self, tracer_and_exporter):
        """流式调用：gen_ai.response.model 取 served 模型名、gen_ai.response.id 取 provider id（非请求模型名）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_streamed_llm_call(handler, model_name="served-model")

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.response.model"] == "served-model"
        assert span.attributes["gen_ai.response.id"] == "chatcmpl-1"

    def test_llm_end_writes_finish_reasons_for_streamed_call(self, tracer_and_exporter):
        """流式调用：末 chunk 的 finish_reason 上报为 gen_ai.response.finish_reasons"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_streamed_llm_call(handler)

        span = exporter.get_finished_spans()[0]
        assert list(span.attributes["gen_ai.response.finish_reasons"]) == ["stop"]

    def test_llm_end_does_not_overwrite_request_model_with_response_model(self, tracer_and_exporter):
        """请求模型名与响应模型名分离：非流式响应模型名不污染 gen_ai.request.model"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "test_llm"},
                prompts=["请回答"],
                invocation_params={"model": "requested-model"},
                run_id=run_id,
            )
        )
        asyncio.run(
            handler.on_llm_end(
                response=LLMResult(
                    generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
                    llm_output={"model_name": "served-model", "id": "chatcmpl-2"},
                ),
                run_id=run_id,
            )
        )

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.request.model"] == "requested-model"
        assert span.attributes["gen_ai.response.model"] == "served-model"
        assert span.attributes["gen_ai.response.id"] == "chatcmpl-2"

    def test_llm_end_actualizes_stream_declaration_from_result(self, tracer_and_exporter):
        """请求期声明 stream=True（invocation_params.stream），响应期按结果实化：无 ttfc → False"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()
        asyncio.run(
            handler.on_llm_start(
                serialized={"name": "test_llm"},
                prompts=["请回答"],
                invocation_params={"stream": True},
                run_id=run_id,
            )
        )
        asyncio.run(
            handler.on_llm_end(
                response=LLMResult(
                    generations=[[ChatGeneration(message=AIMessage(content="答案"))]],
                    llm_output={"model_name": "qwen3"},
                ),
                run_id=run_id,
            )
        )

        span = next(s for s in exporter.get_finished_spans() if s.name == "llm.generate")
        assert span.attributes["gen_ai.request.stream"] is False

    def test_llm_end_writes_stream_false_and_empty_ttfc_without_tokens(self, tracer_and_exporter):
        """非流式调用：stream=False 且 ttfc 写空串"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.request.stream"] is False
        assert span.attributes["gen_ai.response.time_to_first_chunk"] == ""

    def test_llm_end_writes_completed_response_status(self, tracer_and_exporter):
        """正常结束：gen_ai.response.status=completed"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)

        self._run_llm_call(handler, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.response.status"] == "completed"

    def test_llm_error_writes_failed_response_status(self, tracer_and_exporter):
        """异常结束：gen_ai.response.status=failed（官方枚举非 error）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()
        asyncio.run(handler.on_llm_start(serialized={"name": "test_llm"}, prompts=["请回答"], run_id=run_id))
        asyncio.run(handler.on_llm_error(ValueError("boom"), run_id=run_id))

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.response.status"] == "failed"

    @pytest.mark.parametrize("tool_name", ["calculator", "knowledge_search"])
    async def test_tool_execution_span_carries_execute_tool_attributes(self, tracer_and_exporter, tool_name):
        """tool.execution 建 span 期写 execute_tool + tool.name/type，description 按上限截断"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, max_input_attribute_length=8)
        description = "这是一个很长的工具描述"
        run_id = uuid4()

        await handler.on_tool_start(
            serialized={"name": tool_name, "description": description},
            input_str="1+1",
            run_id=run_id,
        )

        span = handler.spans[run_id].span
        assert span.name == "tool.execution"
        assert span.attributes["gen_ai.operation.name"] == "execute_tool"
        assert span.attributes["gen_ai.tool.name"] == tool_name
        assert span.attributes["gen_ai.tool.type"] == "function"
        assert span.attributes["gen_ai.tool.description"] == description[-8:]
        # 既有 tool.* 键零破坏保留
        assert span.attributes["tool.name"] == tool_name

    @pytest.mark.parametrize("tool_name", ["from_kwargs", "from_other_kwargs"])
    async def test_tool_name_falls_back_to_callback_kwargs(self, tracer_and_exporter, tool_name):
        """on_tool_start 需展开 **kwargs，否则 kwargs 里的 name 分支永不命中并退化为 unknown"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        await handler.on_tool_start(serialized={}, input_str="1+1", run_id=run_id, name=tool_name)

        span = handler.spans[run_id].span
        assert span.attributes["tool.name"] == tool_name
        assert span.attributes["gen_ai.tool.name"] == tool_name

    async def test_tool_error_writes_error_type(self, tracer_and_exporter):
        """工具失败时 error.type 由共用错误路径写入（异常类名）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        await handler.on_tool_start(serialized={"name": "calculator"}, input_str="1+1", run_id=run_id)
        await handler.on_tool_error(ValueError("boom"), run_id=run_id)

        span = exporter.get_finished_spans()[0]
        assert span.attributes["error.type"] == "ValueError"
        assert "tool.error_message" not in span.attributes

    def test_chain_error_writes_error_type(self, tracer_and_exporter):
        """chain 失败时 error.type 同样由共用错误路径写入（泛化自工具路径）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=run_id))
        asyncio.run(handler.on_chain_error(RuntimeError("boom"), run_id=run_id))

        span = next(s for s in exporter.get_finished_spans() if s.name == "invoke_agent")
        assert span.attributes["error.type"] == "RuntimeError"

    @pytest.mark.parametrize("tool_call_id", ["call-1", None])
    async def test_tool_start_writes_call_id_and_arguments(self, tracer_and_exporter, tool_call_id):
        """建 span 期写 gen_ai.tool.call.id（kwargs 缺失兜底空串）与 call.arguments（input_str 原样字符串）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        await handler.on_tool_start(
            serialized={"name": "calculator"}, input_str="1+1", run_id=run_id, tool_call_id=tool_call_id
        )

        span = handler.spans[run_id].span
        assert span.attributes["gen_ai.tool.call.id"] == (tool_call_id or "")
        assert span.attributes["gen_ai.tool.call.arguments"] == "1+1"

    @pytest.mark.parametrize(
        "output, expected",
        [("42", "42"), ({"x": 1}, "{'x': 1}")],
    )
    async def test_tool_end_writes_call_result_as_string(self, tracer_and_exporter, output, expected):
        """on_tool_end 写 gen_ai.tool.call.result：output 一律 str 转换（dict 输出亦然）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        await handler.on_tool_start(serialized={"name": "calculator"}, input_str="1+1", run_id=run_id)
        await handler.on_tool_end(output=output, run_id=run_id)  # type: ignore[assignment]

        span = exporter.get_finished_spans()[0]
        call_result = span.attributes["gen_ai.tool.call.result"]
        assert isinstance(call_result, str)
        assert call_result == expected

    async def test_tool_end_call_result_takes_only_message_content(self, tracer_and_exporter):
        """消息对象输出（审批拒绝的 ToolMessage）call.result 只取 content，不带 name/tool_call_id"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        await handler.on_tool_start(serialized={"name": "calculator"}, input_str="1+1", run_id=run_id)
        await handler.on_tool_end(
            output=ToolMessage(content="审批未通过", name="calculator", tool_call_id="call-1"),
            run_id=run_id,
        )

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.tool.call.result"] == "审批未通过"

    async def test_mcp_tool_span_writes_function_gen_ai_type_with_legacy_mcp_type(self, tracer_and_exporter):
        """MCP 工具：gen_ai.tool.type 恒 function，MCP 区分由 legacy tool.type=mcp 承载并存"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()

        await handler.on_tool_start(
            serialized={"name": "search"},
            input_str='{"query": "blueking"}',
            run_id=run_id,
            metadata={"mcp_name": "srv", "mcp_transport": "streamable_http"},
        )

        span = handler.spans[run_id].span
        assert span.attributes["gen_ai.tool.type"] == "function"
        assert span.attributes["tool.type"] == "mcp"

    async def test_tool_call_arguments_and_result_share_truncation_limits(self, tracer_and_exporter):
        """call.arguments/call.result 截断与 tool.input 同款（尾部保留、输入/输出各自上限）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(
            tracer=tracer,
            max_input_attribute_length=8,
            max_output_attribute_length=4,
        )
        run_id = uuid4()

        await handler.on_tool_start(serialized={"name": "bounded"}, input_str="0123456789", run_id=run_id)
        await handler.on_tool_end(output="abcdefghij", run_id=run_id)

        span = exporter.get_finished_spans()[0]
        assert span.attributes["gen_ai.tool.call.arguments"] == "23456789"
        assert span.attributes["gen_ai.tool.call.result"] == "ghij"

    @pytest.mark.parametrize(
        "use_chat, span_name",
        [(True, "chat_model.generate"), (False, "llm.generate")],
    )
    async def test_llm_span_under_chain_carries_conversation_root(self, tracer_and_exporter, use_chat, span_name):
        """LLM span 挂顶层 chain 下：conversation_root == 顶层 span 的 16 位小写 hex id"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        chain_id, llm_id = uuid4(), uuid4()
        await handler.on_chain_start({"name": "wf"}, {}, run_id=chain_id, parent_run_id=None)
        if use_chat:
            await handler.on_chat_model_start(
                serialized={"name": "m"},
                messages=[[HumanMessage(content="hi")]],
                run_id=llm_id,
                parent_run_id=chain_id,
            )
        else:
            await handler.on_llm_start(serialized={"name": "m"}, prompts=["hi"], run_id=llm_id, parent_run_id=chain_id)
        root_hex = format(handler.spans[chain_id].span.get_span_context().span_id, "016x")
        value = handler.spans[llm_id].span.attributes["agent.conversation_root_span_id"]
        assert value == root_hex
        assert re.fullmatch(r"[0-9a-f]{16}", value)

    async def test_tool_span_under_chain_carries_conversation_root(self, tracer_and_exporter):
        """tool span 挂顶层 chain 下：conversation_root 指向顶层 span"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        chain_id, tool_id = uuid4(), uuid4()
        await handler.on_chain_start({"name": "wf"}, {}, run_id=chain_id, parent_run_id=None)
        await handler.on_tool_start(
            serialized={"name": "calculator"},
            input_str="1+1",
            run_id=tool_id,
            parent_run_id=chain_id,
        )
        root_hex = format(handler.spans[chain_id].span.get_span_context().span_id, "016x")
        assert handler.spans[tool_id].span.attributes["agent.conversation_root_span_id"] == root_hex

    async def test_rag_span_carries_conversation_root(self, tracer_and_exporter):
        """rag.retrieval 经漏斗被动获得 conversation_root（rag 是顶层 chain 直接子）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        chain_id = uuid4()
        await handler.on_chain_start({"name": "wf"}, {}, run_id=chain_id, parent_run_id=None)
        with handler.create_custom_span("rag.retrieval"):
            pass
        rag_span = next(s for s in exporter.get_finished_spans() if s.name == "rag.retrieval")
        root_hex = format(handler.spans[chain_id].span.get_span_context().span_id, "016x")
        assert rag_span.attributes["agent.conversation_root_span_id"] == root_hex

    async def test_nested_chain_task_span_carries_conversation_root(self, tracer_and_exporter):
        """漏斗统一注入的自然覆盖面：chain.task 子链也携带 conversation_root（值同顶层）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        top_id, task_id = uuid4(), uuid4()
        await handler.on_chain_start({"name": "graph"}, {}, run_id=top_id, parent_run_id=None)
        await handler.on_chain_start({"name": "model_node"}, {}, run_id=task_id, parent_run_id=top_id)
        root_hex = format(handler.spans[top_id].span.get_span_context().span_id, "016x")
        assert handler.spans[task_id].span.attributes["agent.conversation_root_span_id"] == root_hex

    async def test_tool_span_without_parent_link_carries_conversation_root(self, tracer_and_exporter):
        """关联语义绑定 handler 会话根而非 span 父子结构：顶层建立后无父链的 span 仍携带"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        chain_id, tool_id = uuid4(), uuid4()
        await handler.on_chain_start({"name": "wf"}, {}, run_id=chain_id, parent_run_id=None)
        await handler.on_tool_start(serialized={"name": "t"}, input_str="x", run_id=tool_id, parent_run_id=None)
        root_hex = format(handler.spans[chain_id].span.get_span_context().span_id, "016x")
        assert handler.spans[tool_id].span.attributes["agent.conversation_root_span_id"] == root_hex

    @pytest.mark.parametrize("kind", ["llm", "tool", "rag"])
    async def test_bare_handler_span_lacks_conversation_root(self, tracer_and_exporter, kind):
        """bare handler 无顶层 chain：LLM/tool/rag span 键缺省（关联键无根不写，非空串）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        run_id = uuid4()
        if kind == "llm":
            await handler.on_llm_start(serialized={"name": "m"}, prompts=["hi"], run_id=run_id)
            span = handler.spans[run_id].span
        elif kind == "tool":
            await handler.on_tool_start(serialized={"name": "t"}, input_str="x", run_id=run_id)
            span = handler.spans[run_id].span
        else:
            with handler.create_custom_span("rag.retrieval"):
                pass
            span = next(s for s in exporter.get_finished_spans() if s.name == "rag.retrieval")
        assert "agent.conversation_root_span_id" not in span.attributes

    async def test_top_level_chain_span_lacks_conversation_root(self, tracer_and_exporter):
        """顶层 invoke_agent chain 自身不携带 conversation_root（先建后缓存时序，不自指）"""
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer, agent_code="test_agent")
        run_id = uuid4()
        await handler.on_chain_start({"name": "wf"}, {}, run_id=run_id, parent_run_id=None)
        span = handler.spans[run_id].span
        assert span.name == "invoke_agent test_agent"
        assert "agent.conversation_root_span_id" not in span.attributes

    async def test_agent_execution_root_span_lacks_conversation_root(self, tracer_and_exporter):
        """agent.execution 根 span 不携带 conversation_root（injector 直建不经漏斗，冻结）"""
        tracer, exporter = tracer_and_exporter
        handler = self._make_root_span_handler(tracer)
        chain_id = uuid4()
        await handler.on_chain_start(
            serialized={"name": "wf"}, inputs={"input": "x"}, run_id=chain_id, parent_run_id=None
        )
        root_span = handler._injector.root_span
        assert root_span is not None
        assert root_span.name == "agent.execution"
        assert "agent.conversation_root_span_id" not in root_span.attributes

    async def test_top_level_chain_span_carries_input_value(self, tracer_and_exporter):
        """顶层 chain span 带 input.value：值取 handler 入参快照，与回调 inputs 参数无关"""
        tracer, exporter = tracer_and_exporter
        start_inputs = {"input": "agent-level"}
        handler = BkAidevAgentCallbackHandler(tracer=tracer, start_inputs=start_inputs)
        chain_id, child_id = uuid4(), uuid4()
        # 回调入参与快照取不同值：锁定 input.value 的值源是构造期快照而非本参数
        await handler.on_chain_start({"name": "wf"}, {"chain": "local"}, run_id=chain_id, parent_run_id=None)
        await handler.on_chain_start({"name": "node"}, {}, run_id=child_id, parent_run_id=chain_id)
        assert handler.spans[chain_id].span.attributes["input.value"] == str(start_inputs)
        assert "input.value" not in handler.spans[child_id].span.attributes

    async def test_top_level_chain_span_input_value_defaults_to_none_str(self, tracer_and_exporter):
        """未提取到入参快照（None）：input.value 键恒写入，值为 str(None) 即 "None"

        与根 span agent.session.input 的无条件 str() 语义一致：恒写入，None 落为 "None"。
        """
        tracer, exporter = tracer_and_exporter
        handler = BkAidevAgentCallbackHandler(tracer=tracer)
        chain_id = uuid4()
        await handler.on_chain_start({"name": "wf"}, {}, run_id=chain_id, parent_run_id=None)
        assert handler.spans[chain_id].span.attributes["input.value"] == "None"

    async def test_top_level_chain_input_value_matches_root_span_session_input(self, tracer_and_exporter):
        """同源同格式对账：chain span 的 input.value == agent.execution 的 agent.session.input"""
        tracer, exporter = tracer_and_exporter
        handler = self._make_root_span_handler(tracer)
        chain_id = uuid4()
        await handler.on_chain_start(
            serialized={"name": "wf"}, inputs={"input": "x"}, run_id=chain_id, parent_run_id=None
        )
        chain_span = handler.spans[chain_id].span
        root_span = handler._injector.root_span
        assert root_span is not None and root_span.name == "agent.execution"
        assert chain_span.attributes["input.value"] == root_span.attributes["agent.session.input"]
