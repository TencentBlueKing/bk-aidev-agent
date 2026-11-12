# -*- coding: utf-8 -*-
"""Handoff 工具装配、可见性过滤与节点状态提交点测试。"""

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.ag_ui.types import InfoMessage
from aidev_agent.core.graphs.react.graph import DefaultState, ReActAgentBuilder
from aidev_agent.core.nodes.model.handoff import HandoffToolsMiddleware
from aidev_agent.core.nodes.model.node import _build_node_result, build_model_node
from aidev_agent.core.nodes.model.pydantic_models import ModelNodeSettings, ProcessorContext
from aidev_agent.pydantic_models import HandoffSettings, ModelContextSettings, SecuritySettings
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph


def _base_tool() -> StructuredTool:
    return StructuredTool.from_function(func=lambda query: query, name="demo_tool", description="demo")


def _build(enable_handoff: bool, tools=None):
    tools = tools if tools is not None else [_base_tool()]
    builder = ReActAgentBuilder().set_enable_ask_user_question_tool(False)
    builder.set_llm(MagicMock(model_name="gpt-4o"))
    builder._model_context_options = ModelContextSettings(handoff=HandoffSettings(enabled=enable_handoff))
    builder._security_settings = SecuritySettings()
    prepared_tools, _, _ = builder._prepare_agent_tools(extra_tools=tools, langchain_middleware=())
    with (
        patch("aidev_agent.core.nodes.model.node._build_model_chain") as chain,
        patch("aidev_agent.core.graphs.react.graph.std_make_model_node", wraps=build_model_node),
    ):
        builder._prepare_agent_model_node(
            llm=MagicMock(), non_thinking_llm=None, judge_llm=None, tools=prepared_tools
        )
    return chain.call_args.kwargs["context_assembly"], tools


def _tool_names(context_assembly, applied: bool) -> list:
    ctx = ProcessorContext(state={}, config={}, metadata={"_handoff_applied": applied})
    return [tool.name for tool in context_assembly.get_choice_tools(ctx)]


class TestToolRegistration:
    def test_registered_when_enabled(self):
        context_assembly, _ = _build(True)
        assert set(_tool_names(context_assembly, True)) == {
            "demo_tool",
            "handoff_search_history",
            "handoff_read_history",
        }

    def test_not_registered_when_disabled(self):
        context_assembly, _ = _build(False)
        assert _tool_names(context_assembly, True) == ["demo_tool"]

    def test_caller_tools_not_mutated(self):
        _, tools = _build(True)
        assert [tool.name for tool in tools] == ["demo_tool"]


class TestVisibility:
    def test_hidden_before_handoff(self):
        context_assembly, _ = _build(True)
        assert _tool_names(context_assembly, False) == ["demo_tool"]

    def test_visible_after_handoff(self):
        context_assembly, _ = _build(True)
        names = _tool_names(context_assembly, True)
        assert "handoff_search_history" in names and "handoff_read_history" in names

    def test_middleware_keeps_other_tools(self):
        ctx = ProcessorContext(state={}, config={}, tools=[_base_tool()])
        HandoffToolsMiddleware()(ctx, lambda: None)
        assert [tool.name for tool in ctx.tools] == ["demo_tool"]


class TestNodeCommit:
    def test_returns_handoff_when_update_exists(self):
        ctx = ProcessorContext(state={}, config={}, response=AIMessage(content="ok"))
        ctx.metadata["_handoff_state_update"] = {"rounds": [], "active_round": 0}
        assert _build_node_result(ctx)["handoff"] == {"rounds": [], "active_round": 0}

    @pytest.mark.parametrize("metadata", [{}, {"_handoff_applied": True}])
    def test_omits_handoff_without_update(self, metadata):
        ctx = ProcessorContext(state={}, config={}, response=AIMessage(content="ok"), metadata=metadata)
        result = _build_node_result(ctx)
        assert "handoff" not in result
        assert result["messages"][0].content == "ok"

    def test_graph_state_channel_keeps_handoff(self):
        from aidev_agent.core.graphs.react.graph import DefaultState
        from langgraph.graph import END, StateGraph

        handoff = {"rounds": [{"summary": "s", "searchable_until": "a1"}], "active_round": 0}
        graph = StateGraph(state_schema=DefaultState)
        graph.add_node("model", lambda _state: {"handoff": handoff})
        graph.set_entry_point("model")
        graph.add_edge("model", END)

        result = graph.compile().invoke({"messages": []})
        assert result["handoff"] == handoff

@pytest.mark.parametrize("enabled", [True, False])
def test_compression_middlewares_are_exclusive(enabled):
    assembly, _ = _build(enabled)
    names = [type(m).__name__ for m in assembly._variable_pipeline.middlewares]
    legacy = {
        "KnowledgeCompressionMiddleware",
        "ToolOutputLengthCompressionMiddleware",
        "ToolOutputTokenCompressionMiddleware",
        "SpecialVariablesPostMiddleware",
        "ChatHistoryCompressionMiddleware",
    }
    assert ("HandoffCompressionMiddleware" in names) is enabled
    assert legacy.intersection(names) == (set() if enabled else legacy)
    assert "DeepSeekR1VariablesMiddleware" in names


@pytest.mark.parametrize("settings_type", [ModelContextSettings, ModelNodeSettings])
def test_tail_character_limit_default(settings_type):
    assert settings_type().handoff.tail_char_limit == 30000


@pytest.mark.parametrize(
    "kwargs", [{"tail_char_limit": 0}, {"summary_ratio": 0}, {"keep_last": -1}, {"max_retries": 6}]
)
def test_handoff_settings_validation(kwargs):
    with pytest.raises(ValueError):
        HandoffSettings(**kwargs)


def test_tail_character_limit_reaches_compression_middleware():
    assembly, _ = _build(True)
    middleware = next(
        m for m in assembly._variable_pipeline.middlewares if type(m).__name__ == "HandoffCompressionMiddleware"
    )
    assert middleware.settings.tail_char_limit == 30000

def test_node_result_persists_handoff_info_in_checkpoint():
    response = AIMessage(content="ok", id="response")
    notice = InfoMessage(message_id="notice", content="压缩完成")
    ctx = ProcessorContext(state={}, config={}, response=response)
    ctx.metadata["_handoff_messages"] = [notice]
    graph = StateGraph(state_schema=DefaultState)
    graph.add_node("model", lambda state: _build_node_result(ctx))
    graph.set_entry_point("model")
    graph.add_edge("model", END)
    compiled = graph.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "handoff-info-test"}}
    compiled.invoke({"messages": []}, config)
    messages = compiled.get_state(config).values["messages"]
    assert [message.content for message in messages] == ["压缩完成", "ok"]