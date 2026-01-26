# -*- coding: utf-8 -*-
"""ContextAssembly 中间件集成测试（不依赖真实 LLM）。"""

from aidev_agent.core.nodes.model import ContextAssembly
from aidev_agent.core.nodes.model.basic_middleware import BaseToolsMiddleware
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool


@tool
def tool_a() -> str:
    """tool a"""

    return "a"


@tool
def tool_b() -> str:
    """tool b"""

    return "b"


class TestContextAssemblyIntegration:
    def test_custom_tool_middleware_can_filter_tools(self):
        ca = ContextAssembly(
            tools=[tool_a, tool_b],
        )

        def filter_mw(ctx, next_):
            next_()
            ctx.tools = [t for t in ctx.tools if t.name == "tool_b"]

        # ContextAssembly 不再在 __init__ 中自动加载基础中间件，这里显式加载工具初始化中间件
        ca.add_middleware("tool", BaseToolsMiddleware(), prepend=True)
        ca.add_middleware("tool", filter_mw)

        ctx = ProcessorContext(state={}, config={})
        tools = ca.get_choice_tools(ctx)
        assert [t.name for t in tools] == ["tool_b"]

    def test_custom_variable_middleware_can_inject_variable(self):
        ca = ContextAssembly(
            tools=[],
        )

        def inject_mw(ctx, next_):
            next_()
            ctx.variables["foo"] = "bar"

        ca.add_middleware("variable", inject_mw)

        prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
        ctx = ProcessorContext(
            state={"input": "hi", "messages": []},
            config={},
            store=None,
            chat_prompt_template=prompt,
        )
        variables = ca.get_chat_prompt_variables(ctx)

        assert variables["foo"] == "bar"
