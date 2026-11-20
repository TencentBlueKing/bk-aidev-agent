# -*- coding: utf-8 -*-
"""hook 测试夹具：fake 模型、fake 工具与运行标识绑定。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda
from langchain_core.tools import tool

from aidev_agent.core.hook import HookRunner


class FakeLLM:
    """按顺序返回预置响应的 fake 模型，记录每次实际发送的消息。"""

    def __init__(self, responses: list[AIMessage]) -> None:
        self.responses = list(responses)
        self.calls: list[list] = []
        self.runnable = RunnableLambda(self._invoke, afunc=self._ainvoke)
        self.runnable.bind_tools = Mock(return_value=self.runnable)

    def _next(self, messages) -> AIMessage:
        self.calls.append(list(messages))
        return self.responses.pop(0) if self.responses else AIMessage(content="")

    def _invoke(self, messages, config=None, **kwargs) -> AIMessage:
        return self._next(messages)

    async def _ainvoke(self, messages, config=None, **kwargs) -> AIMessage:
        return self._next(messages)


@pytest.fixture
def fake_llm():
    """返回 FakeLLM 工厂。"""
    return FakeLLM


@pytest.fixture
def search_tool():
    @tool
    def search(query: str) -> str:
        """Search for information"""
        return f"result for {query}"

    return search


@pytest.fixture
def build_model_node_with_hooks(monkeypatch, search_tool):
    """构造模型节点，并把提示词装配固定为单条 HumanMessage。"""
    from aidev_agent.core.nodes.model.node import build_model_node

    def factory(llm: FakeLLM, hooks=None, tools=None):
        prompt_template = Mock()
        prompt_value = Mock()
        prompt_value.to_messages.return_value = [HumanMessage(content="hello")]
        prompt_template.invoke = Mock(return_value=prompt_value)

        tool_list = list(tools if tools is not None else [search_tool])
        monkeypatch.setattr(
            "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_template",
            lambda self, ctx: prompt_template,
        )
        monkeypatch.setattr(
            "aidev_agent.core.nodes.model.node.ContextAssembly.get_chat_prompt_variables",
            lambda self, ctx: {"query": "hello", "chat_history": [], "agent_scratchpad": []},
        )
        monkeypatch.setattr(
            "aidev_agent.core.nodes.model.node.ContextAssembly.get_choice_tools",
            lambda self, ctx: tool_list,
        )
        return build_model_node(
            llm=llm.runnable,
            tools=tool_list,
            hook_runner=HookRunner(hooks) if hooks is not None else None,
        )

    return factory


def make_config(*, agent_code: str = "agent", session_code: str = "session", turn_id: str = "turn-1") -> RunnableConfig:
    """构造运行时配置：执行器从 thread_id 与 execute_kwargs 解析本轮标识。"""
    return RunnableConfig(
        configurable={
            "thread_id": session_code,
            "execute_kwargs": SimpleNamespace(agent_code=agent_code, session_code=session_code, turn_id=turn_id),
        }
    )


def run_node(node, config: RunnableConfig, messages=None):
    """以固定状态调用模型节点。"""
    state = {"messages": messages or [HumanMessage(content="hello")]}
    return node.invoke(state, config=config, store=Mock())
