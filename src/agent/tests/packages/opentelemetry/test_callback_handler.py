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
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from aidev_agent.packages.opentelemetry.callback_handler import (
    BkAidevAgentCallbackHandler,
    BkAidevAgentInjector,
)
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


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
        assert span.attributes["agent.info.type"] == "LLMGW"
        assert span.attributes["agent.info.service_catalogue"] == "test_service"
        assert span.attributes["agent.info.updated_by"] == "admin"
        assert "agent.info.sdk_version" in span.attributes
        assert "agent.info.agent_info" in span.attributes

        # 验证 agent.session.* 属性
        assert span.attributes["agent.session.executor"] == "test-executor"
        assert span.attributes["agent.session.session_code"] == "test-session-123"
        assert span.attributes["agent.session.caller_executor"] == "test-user"
        assert "agent.session.caller_bk_app_code" not in span.attributes
        assert "agent.session.caller_bk_biz_env" not in span.attributes
        assert "agent.session.caller_bk_biz_id" not in span.attributes
        assert "agent.session.caller_order_type" not in span.attributes
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


class TestBkAidevAgentCallbackHandler:
    """测试 BkAidevAgentCallbackHandler 类"""

    def test_agent_metrics_follow_top_level_chain_without_injector(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        run_id = uuid4()

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=run_id))
        asyncio.run(handler.on_chain_end(outputs={}, run_id=run_id))

        recorder.record_active_session.assert_any_call(1, handler._metric_agent_attributes)
        recorder.record_active_session.assert_any_call(-1, handler._metric_agent_attributes)
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

        assert recorder.record_active_session.call_count == 2
        recorder.record_active_session.assert_called_with(-1, handler._metric_agent_attributes)
        recorder.record_agent.assert_called_once()

    def test_active_session_is_decremented_when_summary_recording_fails(self, tracer_and_exporter):
        tracer, _ = tracer_and_exporter
        recorder = MagicMock()
        recorder.record_agent.side_effect = RuntimeError("metric backend failed")
        handler = BkAidevAgentCallbackHandler(tracer=tracer, metric_recorder=recorder)
        run_id = uuid4()

        asyncio.run(handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=run_id))
        asyncio.run(handler.on_chain_end(outputs={}, run_id=run_id))
        handler._finalize_injector()

        assert recorder.record_active_session.call_count == 2
        recorder.record_active_session.assert_called_with(-1, handler._metric_agent_attributes)
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

    def test_tool_execution_span_attributes(self, tracer_and_exporter):
        """测试 tool.* span 包含 tool.input 和 tool.output 属性"""
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

        # 验证包含 tool.input 和 tool.output 属性
        assert span.attributes["tool.input"] == "1+1"
        assert span.attributes["tool.output"] == "2"
        assert span.attributes["tool.name"] == "calculator"

    def test_tool_execution_with_dict_output(self, tracer_and_exporter):
        """测试 tool.execution span 当 output 为字典时，tool.output 正确转换为字符串"""
        tracer, exporter = tracer_and_exporter

        # 创建回调处理器
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟工具调用
        run_id = uuid4()
        parent_run_id = None

        # 工具开始
        asyncio.run(
            handler.on_tool_start(
                serialized={"name": "json_processor"},
                input_str='{"action": "process", "data": [1, 2, 3]}',
                run_id=run_id,
                parent_run_id=parent_run_id,
            )
        )

        # 工具结束 - 输出为字典
        output_dict = {
            "status": "success",
            "result": {"sum": 6, "count": 3},
            "message": "处理完成",
        }
        asyncio.run(
            handler.on_tool_end(
                output=output_dict,  # type: ignore[assignment]
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

        # 验证 tool.output 存在且为字符串类型
        assert "tool.output" in span.attributes
        tool_output = span.attributes["tool.output"]
        assert isinstance(tool_output, str), f"tool.output should be str, but got {type(tool_output)}"

        # 验证输出字符串包含字典的关键信息
        assert "status" in tool_output
        assert "success" in tool_output
        assert "result" in tool_output

        # 验证其他属性
        assert span.attributes["tool.name"] == "json_processor"
        assert span.attributes["tool.input"] == '{"action": "process", "data": [1, 2, 3]}'
        assert span.attributes["tool.execution_status"] == "success"

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

        # 验证包含 rag.knowledge_bases 和 rag.knowledge_items 属性
        assert rag_span.attributes["query"] == "测试查询"
        assert "knowledge_bases" in rag_span.attributes
        assert "knowledge_items" in rag_span.attributes
