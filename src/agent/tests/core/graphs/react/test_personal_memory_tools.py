"""Personal memory stays builtin when develop enables lazy tool loading."""

from unittest.mock import MagicMock

import pytest
from aidev_agent.config import settings
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.pydantic_models import AgentExecutorKwargs, SecuritySettings
from langchain_core.tools import BaseTool


class MemoryTestTool(BaseTool):
    name: str
    description: str = "test tool"

    def _run(self):
        return "ok"


@pytest.mark.parametrize("lazy", [True, False])
def test_memory_tools_are_directly_available_and_keep_names(monkeypatch, lazy):
    monkeypatch.setitem(settings._resolved, "BKAI_TOOL_LAZY_LOADING_ENABLED", lazy)
    monkeypatch.setitem(settings._resolved, "BKAI_TOOL_LAZY_LOADING_THRESHOLD", 1)
    monkeypatch.setitem(settings._resolved, "BKAI_TOOL_NAME_DEDUPE_ENABLED", True)
    memory = [MemoryTestTool(name=name) for name in ("memory_search", "memory_write", "memory_update")]
    runtime = MagicMock()
    runtime.make_tools.return_value = memory
    builder = ReActAgentBuilder().enable_personal_memory(runtime).set_enable_ask_user_question_tool(False)
    external = [MemoryTestTool(name="memory_search"), MemoryTestTool(name="external")]
    tools, builtin, catalog = builder._prepare_agent_tools(extra_tools=external, langchain_middleware=())
    assert all(any(tool is item for tool in tools) for item in memory)
    assert all(any(tool is item for tool in builtin) for item in memory)
    assert len({tool.name for tool in tools}) == len(tools)
    assert (catalog is not None) is lazy
    if catalog:
        assert catalog.executable("memory_search") is None
        assert catalog.executable("external") is not None


@pytest.mark.parametrize("enabled", [True, False])
def test_model_option_overrides_preserve_memory_source_tracking(mocker, enabled):
    factory = mocker.patch("aidev_agent.core.graphs.react.graph.std_make_model_node")
    builder = (
        ReActAgentBuilder()
        .set_llm(MagicMock(model_name="gpt-4o"))
        .set_bkai_options(AgentExecutorKwargs(security_settings=SecuritySettings()))
    )
    if enabled:
        builder.enable_personal_memory(MagicMock())
    builder._prepare_agent_model_node(
        llm=MagicMock(), non_thinking_llm=None, judge_llm=None, tools=[], node_options_kwargs={"token_limit": 4096}
    )
    options = factory.call_args.kwargs["node_options"]
    assert options.token_limit == 4096
    assert options.track_memory_source is enabled
