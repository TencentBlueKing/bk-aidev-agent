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

真实 LangGraph 图下的 invoke_agent 顶层 span 属性测试。

用真实 ``StateGraph`` + ``InMemorySaver`` 驱动 callback，验证顶层 chain span 在
正常 invoke 与 interrupt/resume 两条路径上的 gen_ai.input/output.messages 表现。
"""

import json
from typing import Annotated, TypedDict

import pytest
from aidev_agent.packages.opentelemetry.callback_handler import BkAidevAgentCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

TOP_LEVEL_SPAN_NAME = "invoke_agent test_agent"
INTERRUPT_RESUME_INPUT_TEXT = "来自中断回调"


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


@pytest.fixture
def tracer_and_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield provider.get_tracer(__name__), exporter
    exporter.clear()


@pytest.fixture
def make_handler(tracer_and_exporter):
    tracer, _ = tracer_and_exporter

    def _make(start_inputs=None):
        return BkAidevAgentCallbackHandler(tracer=tracer, agent_code="test_agent", start_inputs=start_inputs)

    return _make


@pytest.fixture
def invoke_app():
    """单节点图：直接把用户消息回显为 AI 消息（正常 invoke 路径）。"""

    def echo_node(state: AgentState):
        last = state["messages"][-1]
        return {"messages": [AIMessage(content=f"echo:{last.content}")]}

    graph = StateGraph(AgentState)
    graph.add_node("echo", echo_node)
    graph.add_edge(START, "echo")
    graph.add_edge("echo", END)
    return graph.compile()


@pytest.fixture
def interrupt_app():
    """中断图：首次执行触发 interrupt，恢复后返回 AI 消息。"""

    def gate_node(state: AgentState):
        answer = interrupt({"question": "continue?"})
        return {"messages": [AIMessage(content=f"resumed:{answer}")]}

    graph = StateGraph(AgentState)
    graph.add_node("gate", gate_node)
    graph.add_edge(START, "gate")
    graph.add_edge("gate", END)
    return graph.compile(checkpointer=InMemorySaver())


def _top_level_spans(exporter):
    return [s for s in exporter.get_finished_spans() if s.name == TOP_LEVEL_SPAN_NAME]


def _child_spans(exporter):
    return [s for s in exporter.get_finished_spans() if s.name == "chain.task"]


class TestInvokeAgentSpanNormalInvoke:
    """正常 invoke 路径：顶层 span 携带本轮输入与产出的 parts 模型属性。"""

    async def test_top_level_span_carries_input_and_output_messages(
        self, invoke_app, make_handler, tracer_and_exporter
    ):
        """顶层 span 的 gen_ai.input/output.messages 分别为用户消息与末条 AI 消息，且无 input.value"""
        _, exporter = tracer_and_exporter
        cfg = {"callbacks": [make_handler()]}
        await invoke_app.ainvoke({"messages": [HumanMessage(content="hello")]}, cfg)

        span = _top_level_spans(exporter)[0]
        attrs = span.attributes
        assert json.loads(attrs["gen_ai.input.messages"]) == [
            {"role": "user", "parts": [{"type": "text", "content": "hello"}]}
        ]
        assert json.loads(attrs["gen_ai.output.messages"]) == [
            {"role": "assistant", "parts": [{"type": "text", "content": "echo:hello"}]}
        ]
        assert "input.value" not in attrs

    async def test_child_chain_task_span_lacks_message_attributes(self, invoke_app, make_handler, tracer_and_exporter):
        """子链 chain.task span 不写 gen_ai.input/output.messages"""
        _, exporter = tracer_and_exporter
        cfg = {"callbacks": [make_handler()]}
        await invoke_app.ainvoke({"messages": [HumanMessage(content="hello")]}, cfg)

        child_attrs = _child_spans(exporter)[0].attributes
        assert "gen_ai.input.messages" not in child_attrs
        assert "gen_ai.output.messages" not in child_attrs


class TestInvokeAgentSpanInterruptResume:
    """interrupt/resume 路径：恢复轮的顶层 span 表达中断回调语义。"""

    async def test_resume_round_input_messages_is_fixed_text(self, interrupt_app, make_handler, tracer_and_exporter):
        """resume 轮顶层 span 的 gen_ai.input.messages 为固定文案「来自中断回调」"""
        _, exporter = tracer_and_exporter
        cfg = {"configurable": {"thread_id": "t-resume"}, "callbacks": [make_handler("hello")]}
        await interrupt_app.ainvoke({"messages": [HumanMessage(content="hello")]}, cfg)

        cfg["callbacks"] = [make_handler("hello")]
        await interrupt_app.ainvoke(Command(resume="yes"), cfg)

        resume_span = _top_level_spans(exporter)[-1]
        attrs = resume_span.attributes
        assert json.loads(attrs["gen_ai.input.messages"]) == [
            {"role": "user", "parts": [{"type": "text", "content": INTERRUPT_RESUME_INPUT_TEXT}]}
        ]
        assert "input.value" not in attrs

    async def test_resume_round_output_messages_carries_ai_message(
        self, interrupt_app, make_handler, tracer_and_exporter
    ):
        """resume 轮顶层 span 的 gen_ai.output.messages 含恢复后产出，且带截断元信息"""
        _, exporter = tracer_and_exporter
        cfg = {"configurable": {"thread_id": "t-resume-out"}, "callbacks": [make_handler()]}
        await interrupt_app.ainvoke({"messages": [HumanMessage(content="hello")]}, cfg)

        cfg["callbacks"] = [make_handler()]
        await interrupt_app.ainvoke(Command(resume="yes"), cfg)

        attrs = _top_level_spans(exporter)[-1].attributes
        assert json.loads(attrs["gen_ai.output.messages"]) == [
            {"role": "assistant", "parts": [{"type": "text", "content": "resumed:yes"}]}
        ]
        assert attrs["gen_ai.output.messages_original_length"] > 0
        assert attrs["gen_ai.output.messages_truncated"] is False
