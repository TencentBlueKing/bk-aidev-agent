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
import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

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


class TestCompleteAgentExecution:
    """测试完整的 Agent 执行流程，模拟真实场景"""

    def test_single_question_without_tool(self, tracer_and_exporter):
        """
        测试单次输入，无工具调用的场景

        模拟一个简单的问答场景，不涉及工具调用
        """
        tracer, exporter = tracer_and_exporter

        # 准备测试数据
        execute_kwargs = MagicMock()
        execute_kwargs.session_code = "test-session-simple"
        execute_kwargs.caller_executor = "test-user"
        execute_kwargs.caller_bk_app_code = "test-app"
        execute_kwargs.caller_bk_biz_env = "domestic_biz"
        execute_kwargs.caller_bk_biz_id = 100
        execute_kwargs.caller_order_type = "ai_chat"

        agent_info = {
            "agent_id": "simple-agent-001",
            "agent_code": "simple_qa_agent",
            "agent_name": "简单问答智能体",
            "agent_type": "qa",
            "service_catalogue": "qa_service",
            "updated_by": "admin",
        }

        inputs = {"input": "什么是人工智能？"}

        # 创建注入器和回调处理器
        injector = BkAidevAgentInjector(tracer=tracer, debug=True)
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟 Agent 执行流程
        # 1. Agent 开始
        injector.on_bk_agent_start(
            inputs=inputs,
            execute_kwargs=execute_kwargs,
            agent_info=agent_info,
        )

        # 2. Chain 开始
        chain_run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "qa_chain"},
            inputs=inputs,
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 3. LLM 调用
        llm_run_id = uuid4()
        handler.on_chat_model_start(
            serialized={"name": "gpt-4"},
            messages=[[HumanMessage(content="什么是人工智能？")]],
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )

        llm_result = LLMResult(
            generations=[[ChatGeneration(
                message=AIMessage(content="人工智能是计算机科学的一个分支...")
            )]],
            llm_output={"model_name": "gpt-4"},
        )

        handler.on_llm_end(
            response=llm_result,
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )

        # 4. Chain 结束
        handler.on_chain_end(
            outputs={"output": "人工智能是计算机科学的一个分支..."},
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 5. Agent 结束
        injector.on_bk_agent_end()

        # 验证 spans
        spans = exporter.get_finished_spans()

        # 验证 span 数量：agent.execution + chain + llm
        assert len(spans) == 3

        # 验证 agent.execution span
        agent_span = next((s for s in spans if s.name == "agent.execution"), None)
        assert agent_span is not None
        assert agent_span.attributes["agent.info.id"] == "simple-agent-001"
        assert agent_span.attributes["agent.session.session_code"] == "test-session-simple"

        # 验证 chain span
        chain_span = next((s for s in spans if "chain" in s.name), None)
        assert chain_span is not None

        # 验证 llm span
        llm_span = next((s for s in spans if "chat_model" in s.name), None)
        assert llm_span is not None
        assert "llm.input" in llm_span.attributes
        assert "llm.output" in llm_span.attributes

    def test_question_with_tool_call(self, tracer_and_exporter):
        """
        测试带工具调用的场景

        模拟一个需要调用工具的问答场景
        """
        tracer, exporter = tracer_and_exporter

        # 准备测试数据
        execute_kwargs = MagicMock()
        execute_kwargs.session_code = "test-session-tool"
        execute_kwargs.caller_executor = "tool-user"
        execute_kwargs.caller_bk_app_code = "tool-app"
        execute_kwargs.caller_bk_biz_env = "domestic_biz"
        execute_kwargs.caller_bk_biz_id = 200
        execute_kwargs.caller_order_type = "ai_chat"

        agent_info = {
            "agent_id": "tool-agent-002",
            "agent_code": "tool_qa_agent",
            "agent_name": "工具调用智能体",
            "agent_type": "qa",
            "service_catalogue": "tool_service",
            "updated_by": "admin",
        }

        inputs = {"input": "北京今天的天气怎么样？"}

        # 创建注入器和回调处理器
        injector = BkAidevAgentInjector(tracer=tracer, debug=True)
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟 Agent 执行流程
        # 1. Agent 开始
        injector.on_bk_agent_start(
            inputs=inputs,
            execute_kwargs=execute_kwargs,
            agent_info=agent_info,
        )

        # 2. Chain 开始
        chain_run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "tool_chain"},
            inputs=inputs,
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 3. 第一次 LLM 调用（决定使用工具）
        llm_run_id_1 = uuid4()
        handler.on_chat_model_start(
            serialized={"name": "gpt-4"},
            messages=[[HumanMessage(content="北京今天的天气怎么样？")]],
            run_id=llm_run_id_1,
            parent_run_id=chain_run_id,
        )

        # LLM 返回需要调用工具
        llm_result_1 = LLMResult(
            generations=[[ChatGeneration(
                message=AIMessage(
                    content="",
                    additional_kwargs={
                        "tool_calls": [{
                            "id": "call_123",
                            "function": {
                                "name": "get_weather",
                                "arguments": '{"city": "北京"}'
                            }
                        }]
                    }
                )
            )]],
            llm_output={"model_name": "gpt-4"},
        )

        handler.on_llm_end(
            response=llm_result_1,
            run_id=llm_run_id_1,
            parent_run_id=chain_run_id,
        )

        # 4. 工具调用
        tool_run_id = uuid4()
        handler.on_tool_start(
            serialized={"name": "get_weather"},
            input_str='{"city": "北京"}',
            run_id=tool_run_id,
            parent_run_id=chain_run_id,
        )

        handler.on_tool_end(
            output='{"temperature": 15, "condition": "晴"}',
            run_id=tool_run_id,
            parent_run_id=chain_run_id,
        )

        # 5. 第二次 LLM 调用（根据工具结果回答）
        llm_run_id_2 = uuid4()
        handler.on_chat_model_start(
            serialized={"name": "gpt-4"},
            messages=[[
                HumanMessage(content="北京今天的天气怎么样？"),
                AIMessage(content="调用工具..."),
                HumanMessage(content='工具结果: {"temperature": 15, "condition": "晴"}'),
            ]],
            run_id=llm_run_id_2,
            parent_run_id=chain_run_id,
        )

        llm_result_2 = LLMResult(
            generations=[[ChatGeneration(
                message=AIMessage(content="北京今天的天气是晴天，温度15度")
            )]],
            llm_output={"model_name": "gpt-4"},
        )

        handler.on_llm_end(
            response=llm_result_2,
            run_id=llm_run_id_2,
            parent_run_id=chain_run_id,
        )

        # 6. Chain 结束
        handler.on_chain_end(
            outputs={"output": "北京今天的天气是晴天，温度15度"},
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 7. Agent 结束
        injector.on_bk_agent_end()

        # 验证 spans
        spans = exporter.get_finished_spans()

        # 验证 span 数量：agent.execution + chain + 2*llm + tool
        assert len(spans) == 5

        # 验证所有 tool.* span 包含 tool.input 和 tool.output
        tool_spans = [s for s in spans if s.name.startswith("tool.")]
        assert len(tool_spans) == 1

        for tool_span in tool_spans:
            assert "tool.input" in tool_span.attributes
            assert "tool.output" in tool_span.attributes
            assert "tool.name" in tool_span.attributes

        # 验证所有 llm/chat_model span 包含 llm.input 和 llm.output
        llm_spans = [s for s in spans if "llm" in s.name or "chat_model" in s.name]
        assert len(llm_spans) == 2

        for llm_span in llm_spans:
            assert "llm.input" in llm_span.attributes or "gen_ai.prompt0" in llm_span.attributes
            assert "llm.output" in llm_span.attributes

    def test_question_with_rag_retrieval(self, tracer_and_exporter):
        """
        测试带 RAG 检索的场景

        模拟一个需要知识库检索的问答场景
        """
        tracer, exporter = tracer_and_exporter

        # 准备测试数据
        execute_kwargs = MagicMock()
        execute_kwargs.session_code = "test-session-rag"
        execute_kwargs.caller_executor = "rag-user"
        execute_kwargs.caller_bk_app_code = "rag-app"
        execute_kwargs.caller_bk_biz_env = "domestic_biz"
        execute_kwargs.caller_bk_biz_id = 300
        execute_kwargs.caller_order_type = "ai_chat"

        agent_info = {
            "agent_id": "rag-agent-003",
            "agent_code": "rag_qa_agent",
            "agent_name": "RAG 智能体",
            "agent_type": "qa",
            "service_catalogue": "rag_service",
            "updated_by": "admin",
        }

        inputs = {"input": "如何使用蓝鲸平台？"}

        # 创建注入器和回调处理器
        injector = BkAidevAgentInjector(tracer=tracer, debug=True)
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟 Agent 执行流程
        # 1. Agent 开始
        injector.on_bk_agent_start(
            inputs=inputs,
            execute_kwargs=execute_kwargs,
            agent_info=agent_info,
        )

        # 2. Chain 开始
        chain_run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "rag_chain"},
            inputs=inputs,
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 3. RAG 检索
        with handler.create_custom_span(
            "rag.retrieval",
            attributes={
                "query": "如何使用蓝鲸平台？",
                "knowledge_bases": [1, 2],
                "knowledge_items": [101, 102, 103],
            },
        ) as rag_span:
            # 模拟检索过程
            rag_span.set_attribute("rag.knowledge_resources_emb_recalled", '[{"id": "doc1"}, {"id": "doc2"}]')
            rag_span.set_attribute("rag.knowledge_resources_highly_relevant", '[{"id": "doc1"}]')

        # 4. LLM 调用
        llm_run_id = uuid4()
        handler.on_chat_model_start(
            serialized={"name": "gpt-4"},
            messages=[[HumanMessage(content="如何使用蓝鲸平台？")]],
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )

        llm_result = LLMResult(
            generations=[[ChatGeneration(
                message=AIMessage(content="根据文档，蓝鲸平台的使用方法是...")
            )]],
            llm_output={"model_name": "gpt-4"},
        )

        handler.on_llm_end(
            response=llm_result,
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )

        # 5. Chain 结束
        handler.on_chain_end(
            outputs={"output": "根据文档，蓝鲸平台的使用方法是..."},
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 6. Agent 结束
        injector.on_bk_agent_end()

        # 验证 spans
        spans = exporter.get_finished_spans()

        # 验证包含 rag.retrieval span
        rag_spans = [s for s in spans if s.name == "rag.retrieval"]
        assert len(rag_spans) == 1

        rag_span = rag_spans[0]

        # 验证 RAG span 的属性
        assert rag_span.attributes["query"] == "如何使用蓝鲸平台？"
        # OpenTelemetry 将列表转换为元组
        assert rag_span.attributes["knowledge_bases"] == (1, 2)
        assert rag_span.attributes["knowledge_items"] == (101, 102, 103)
        assert "rag.knowledge_resources_emb_recalled" in rag_span.attributes
        assert "rag.knowledge_resources_highly_relevant" in rag_span.attributes

    def test_streaming_response_span_lifecycle(self, tracer_and_exporter):
        """
        测试流式响应场景下的 span 生命周期管理

        这个测试验证在流式响应（StreamingHttpResponse）的场景下：
        1. BkAidevAgentInjector 的 root span 能够正确关闭
        2. 不会导致线程的 trace 被污染
        3. 所有 span 都能正确结束，没有泄露

        背景：
        在 aidev_bkplugin/views/builtin.py 的 ChatCompletionViewSet.create 中，
        当使用流式响应时，StreamingHttpResponse 会在返回时立即结束 HTTP span。
        如果 BkAidevAgentInjector 的 span 没有正确结束，会导致该线程的 trace 被污染。
        """
        tracer, exporter = tracer_and_exporter

        # 准备测试数据
        execute_kwargs = MagicMock()
        execute_kwargs.session_code = "test-session-streaming"
        execute_kwargs.caller_executor = "streaming-user"
        execute_kwargs.caller_bk_app_code = "streaming-app"
        execute_kwargs.caller_bk_biz_env = "domestic_biz"
        execute_kwargs.caller_bk_biz_id = 400
        execute_kwargs.caller_order_type = "ai_chat"
        execute_kwargs.stream = True  # 启用流式响应

        agent_info = {
            "agent_id": "streaming-agent-004",
            "agent_code": "streaming_agent",
            "agent_name": "流式响应智能体",
            "agent_type": "qa",
            "service_catalogue": "streaming_service",
            "updated_by": "admin",
        }

        inputs = {"input": "流式响应测试"}

        # 创建注入器和回调处理器
        injector = BkAidevAgentInjector(tracer=tracer, debug=True)
        handler = BkAidevAgentCallbackHandler(tracer=tracer, debug=True)

        # 模拟流式响应的 Agent 执行流程
        # 1. Agent 开始
        injector.on_bk_agent_start(
            inputs=inputs,
            execute_kwargs=execute_kwargs,
            agent_info=agent_info,
        )

        # 验证 root span 已创建
        assert injector.root_span is not None
        assert injector.context_token is not None

        # 2. Chain 开始
        chain_run_id = uuid4()
        handler.on_chain_start(
            serialized={"name": "streaming_chain"},
            inputs=inputs,
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 3. LLM 流式调用开始
        llm_run_id = uuid4()
        handler.on_chat_model_start(
            serialized={"name": "gpt-4"},
            messages=[[HumanMessage(content="流式响应测试")]],
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )

        # 模拟流式响应：在 StreamingHttpResponse 返回后，
        # HTTP span 会立即结束，但 LLM 和 Chain 的执行还在继续

        # 4. LLM 流式调用结束
        llm_result = LLMResult(
            generations=[[ChatGeneration(
                message=AIMessage(content="这是流式响应的内容...")
            )]],
            llm_output={"model_name": "gpt-4"},
        )

        handler.on_llm_end(
            response=llm_result,
            run_id=llm_run_id,
            parent_run_id=chain_run_id,
        )

        # 5. Chain 结束
        handler.on_chain_end(
            outputs={"output": "这是流式响应的内容..."},
            run_id=chain_run_id,
            parent_run_id=None,
        )

        # 6. 关键验证点：在流式响应场景下，必须确保 Agent 正确结束
        # 这是修复后的行为，确保 BkAidevAgentInjector 的 span 被正确关闭
        injector.on_bk_agent_end()

        # 验证所有 spans 都已正确结束
        spans = exporter.get_finished_spans()

        # 验证 span 数量：agent.execution + chain + llm
        assert len(spans) == 3

        # 验证 agent.execution span 存在且已结束
        agent_span = next((s for s in spans if s.name == "agent.execution"), None)
        assert agent_span is not None, "agent.execution span 应该存在"
        assert agent_span.end_time is not None, "agent.execution span 应该已经结束"
        assert agent_span.attributes["agent.status"] == "completed"
        assert agent_span.attributes["agent.info.id"] == "streaming-agent-004"
        assert agent_span.attributes["agent.session.session_code"] == "test-session-streaming"

        # 验证 chain span 已结束
        chain_span = next((s for s in spans if "chain" in s.name), None)
        assert chain_span is not None, "chain span 应该存在"
        assert chain_span.end_time is not None, "chain span 应该已经结束"

        # 验证 llm span 已结束
        llm_span = next((s for s in spans if "chat_model" in s.name), None)
        assert llm_span is not None, "llm span 应该存在"
        assert llm_span.end_time is not None, "llm span 应该已经结束"

        # 验证 injector 的状态已清理
        assert injector.root_span.end_time is not None, "root span 已经结束，不会污染线程 trace"

        # 关键验证：确保没有未结束的 span（避免 trace 污染）
        for span in spans:
            assert span.end_time is not None, f"Span {span.name} 已经结束"
