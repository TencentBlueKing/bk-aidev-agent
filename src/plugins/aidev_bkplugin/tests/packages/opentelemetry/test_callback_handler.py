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

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.outputs import LLMResult, ChatGeneration

from aidev_bkplugin.packages.opentelemetry.callback_handler import (
    BkAidevAgentInjector,
    BkAidevAgentCallbackHandler,
)


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
        execute_kwargs.session_code = "test-session-123"
        execute_kwargs.caller_executor = "test-user"
        execute_kwargs.caller_bk_app_code = "test-app"
        execute_kwargs.caller_bk_biz_env = "domestic_biz"
        execute_kwargs.caller_bk_biz_id = 123
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
        assert span.attributes["agent.session.session_code"] == "test-session-123"
        assert span.attributes["agent.session.executor"] == "test-user"
        assert span.attributes["agent.session.caller_bk_app_code"] == "test-app"
        assert span.attributes["agent.session.caller_bk_biz_env"] == "domestic_biz"
        assert span.attributes["agent.session.caller_bk_biz_id"] == 123
        assert span.attributes["agent.session.caller_executor"] == "test-user"
        assert span.attributes["agent.session.caller_order_type"] == "ai_chat"
        assert "agent.session.input" in span.attributes
        assert "agent.session.start_time" in span.attributes
        assert "agent.session.start_time_unix_nano" in span.attributes

        # 验证 debug 属性
        assert "debug.thread_id" in span.attributes


class TestBkAidevAgentCallbackHandler:
    """测试 BkAidevAgentCallbackHandler 类"""
    def test_llm_generate_span_attributes(self, tracer_and_exporter):
        """测试 llm.generate span 包含 llm.input 和 llm.output 属性"""
        tracer, exporter = tracer_and_exporter

        # 创建回调处理器
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟 LLM 调用
        run_id = uuid4()
        parent_run_id = None

        # LLM 开始
        handler.on_llm_start(
            serialized={"name": "test_llm"},
            prompts=["请回答这个问题"],
            run_id=run_id,
            parent_run_id=parent_run_id,
        )

        # LLM 结束
        llm_result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="这是答案"))]],
            llm_output={"model_name": "qwen3"},
        )

        handler.on_llm_end(
            response=llm_result,
            run_id=run_id,
            parent_run_id=parent_run_id,
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
        handler.on_chat_model_start(
            serialized={"name": "test_chat_model"},
            messages=messages,
            run_id=run_id,
            parent_run_id=parent_run_id,
        )

        # Chat Model 结束
        llm_result = LLMResult(
            generations=[[ChatGeneration(message=AIMessage(content="你好,我是AI助手"))]],
            llm_output={"model_name": "qwen3"},
        )

        handler.on_llm_end(
            response=llm_result,
            run_id=run_id,
            parent_run_id=parent_run_id,
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
        handler.on_tool_start(
            serialized={"name": "calculator"},
            input_str="1+1",
            run_id=run_id,
            parent_run_id=parent_run_id,
        )

        # 工具结束
        handler.on_tool_end(
            output="2",
            run_id=run_id,
            parent_run_id=parent_run_id,
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


    def test_rag_retrieval_span_attributes(self, tracer_and_exporter):
        """测试 rag.retrieval span 包含 rag.knowledge_bases 和 rag.knowledge_items 属性"""
        tracer, exporter = tracer_and_exporter

        # 创建回调处理器
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 创建一个顶层 workflow chain 以便挂载自定义 span
        chain_run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "test_workflow"},
            inputs={"input": "测试"},
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 使用 create_custom_span 创建 RAG span
        with handler.create_custom_span(
            "rag.retrieval",
            attributes={
                "query": "测试查询",
                "knowledge_bases": [1, 2, 3],
                "knowledge_items": [101, 102],
            },
        ) as span:
            # 模拟 RAG 检索
            pass

        # 结束 chain
        handler.on_chain_end(
            outputs={"output": "结果"},
            run_id=chain_run_id,
            parent_run_id=None,
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
