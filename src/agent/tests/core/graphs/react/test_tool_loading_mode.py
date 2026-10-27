# -*- coding: utf-8 -*-
"""工具加载模式（``mode``）的装配期过滤与装配级回归测试。

覆盖 T-3（纯函数矩阵）与 T-8（``ReActAgentBuilder`` 装配出的工具名集合），
对应 REQ-2～REQ-5、REQ-7、REQ-10 与 AC-1～AC-4、AC-6、AC-7、AC-12。
"""

from __future__ import annotations

from typing import List

import pytest
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.graphs.react.team_middleware import ToolFilterMiddleware
from aidev_agent.core.graphs.react.tool_loading_mode import (
    command_approval_allowed,
    filter_tools_by_loading_mode,
)
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.core.tools.ask_user_question import ask_user_question as _ask_user_question_tool
from aidev_agent.packages.interrupt_manager import ASK_USER_QUESTION_TOOL_NAME
from aidev_agent.pydantic_models import (
    AgentExecutorKwargs,
    ExecuteKwargs,
    SecurityCommandSettings,
    SecuritySettings,
)
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool

APPROVAL_TOOL_NAME = "itsm_tool"
EXECUTE_TOOL_NAME = "execute"
PLAIN_TOOL_NAME = "calculator"


def _plain_tool(name: str = PLAIN_TOOL_NAME, **kwargs) -> BaseTool:
    def _run(**_: object) -> str:  # noqa: ARG001
        return "ok"

    return StructuredTool.from_function(func=_run, name=name, description=f"{name} tool", **kwargs)


def _approval_tool() -> BaseTool:
    """带生效审批配置的工具（``metadata.approval.enabled``）。"""
    return _plain_tool(APPROVAL_TOOL_NAME, metadata={"approval": {"enabled": True}})


def _execute_tool() -> BaseTool:
    return _plain_tool(EXECUTE_TOOL_NAME)


@pytest.fixture
def all_tools() -> List[BaseTool]:
    """四类工具：ask 类 / 带审批 / execute / 普通。"""
    return [_ask_user_question_tool, _approval_tool(), _execute_tool(), _plain_tool()]


def _names(tools: List[BaseTool]) -> set[str]:
    return {t.name for t in tools}


# ============================================================================
# T-3 纯函数矩阵：3 种 mode × 4 类工具
# ============================================================================


class TestFilterToolsByLoadingMode:
    @pytest.mark.parametrize(
        "mode, expected",
        [
            # default：四类工具全部保留（含 ask 与带审批）
            ("default", {ASK_USER_QUESTION_TOOL_NAME, APPROVAL_TOOL_NAME, EXECUTE_TOOL_NAME, PLAIN_TOOL_NAME}),
            # dontAsk：仅剔除 ask，带审批与 execute 保留
            ("dontAsk", {APPROVAL_TOOL_NAME, EXECUTE_TOOL_NAME, PLAIN_TOOL_NAME}),
            # dontInterrupt：剔除 ask 与带审批，execute 与普通工具保留
            ("dontInterrupt", {EXECUTE_TOOL_NAME, PLAIN_TOOL_NAME}),
        ],
    )
    def test_mode_matrix(self, all_tools, mode, expected):
        assert _names(filter_tools_by_loading_mode(all_tools, mode)) == expected

    def test_default_returns_same_list_object(self, all_tools):
        """default 不做拷贝：返回同一列表对象，保证与变更前逐项一致。"""
        assert filter_tools_by_loading_mode(all_tools, "default") is all_tools

    def test_default_preserves_order(self, all_tools):
        assert [t.name for t in filter_tools_by_loading_mode(all_tools, "default")] == [t.name for t in all_tools]

    def test_unknown_mode_behaves_like_default(self, all_tools):
        """理论上被 ExecuteKwargs 的 Literal 拒绝；函数层面按 default 兜底不裁剪。"""
        assert filter_tools_by_loading_mode(all_tools, "disabled") is all_tools

    @pytest.mark.parametrize(
        "mode, allowed",
        [("default", True), ("dontAsk", True), ("dontInterrupt", False)],
    )
    def test_command_approval_allowed(self, mode, allowed):
        assert command_approval_allowed(mode) is allowed

    def test_command_approval_allowed_unknown_mode_keeps_approval(self):
        assert command_approval_allowed("disabled") is True


# ============================================================================
# T-8 装配级：ReActAgentBuilder 三种 mode 下的工具名集合
# ============================================================================


def _builder(mode: str | None) -> ReActAgentBuilder:
    execute_kwargs = ExecuteKwargs() if mode is None else ExecuteKwargs(mode=mode)
    return ReActAgentBuilder().set_bkai_options(
        AgentExecutorKwargs(security_settings=SecuritySettings(), execute_kwargs=execute_kwargs)
    )


def _assemble(mode: str | None, extra_tools: List[BaseTool]) -> set[str]:
    builder = _builder(mode)
    tools = builder._prepare_agent_tools(extra_tools=extra_tools, langchain_middleware=[])
    return _names(tools)


class TestAssemblyToolSets:
    def test_default_without_mode_equals_explicit_default(self):
        """AC-1 / AC-2：未传 mode 与 mode=default 的工具集合完全一致。"""
        extra = [_approval_tool(), _execute_tool(), _plain_tool()]
        assert _assemble(None, extra) == _assemble("default", extra)

    def test_default_keeps_ask_and_approval(self):
        """AC-1：default 下 ask 类与带审批工具均在集合中。"""
        names = _assemble(None, [_approval_tool(), _execute_tool()])
        assert ASK_USER_QUESTION_TOOL_NAME in names
        assert APPROVAL_TOOL_NAME in names

    def test_dont_interrupt_drops_ask_and_approval_but_keeps_execute(self):
        """AC-3 / AC-4 / AC-6：缺 ask 与带审批，但 execute 与普通工具仍在。"""
        names = _assemble("dontInterrupt", [_approval_tool(), _execute_tool(), _plain_tool()])
        assert ASK_USER_QUESTION_TOOL_NAME not in names
        assert APPROVAL_TOOL_NAME not in names
        assert {EXECUTE_TOOL_NAME, PLAIN_TOOL_NAME} <= names

    def test_dont_ask_drops_ask_only(self):
        """AC-7：dontAsk 仅缺 ask，带审批与 execute 仍在。"""
        names = _assemble("dontAsk", [_approval_tool(), _execute_tool()])
        assert ASK_USER_QUESTION_TOOL_NAME not in names
        assert {APPROVAL_TOOL_NAME, EXECUTE_TOOL_NAME} <= names

    @pytest.mark.parametrize(
        "mode, expected",
        [("dontInterrupt", "block"), ("dontAsk", "approval"), ("default", "approval")],
    )
    def test_build_rewrites_command_approval_in_security_settings(self, mode, expected):
        """命令审批开关在 build 期落到安全配置上：dontInterrupt 把 review 处置档降为 block。

        工具工厂与 ``enforce_command_security`` 都只读这份配置，不再接收开关参数。
        """
        from unittest.mock import MagicMock

        from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
        from aidev_agent.core.tools.runtime_tools.provider import RuntimeBackendResolver

        llm = MagicMock()
        llm.model_name = "gpt-4o"
        settings = SecuritySettings(
            command=SecurityCommandSettings(command_review_disposition="approval", command_approval_approvers="u1")
        )
        resolver = RuntimeBackendResolver(default_runtime="local", security_settings=settings)
        resolver.register_runtime("local", FilesystemBackend())
        builder = (
            ReActAgentBuilder()
            .set_llm(llm)
            .set_bkai_options(
                AgentExecutorKwargs(
                    security_settings=settings,
                    execute_kwargs=ExecuteKwargs(mode=mode),
                    runtime_backend_resolver=resolver,
                )
            )
        )

        builder.build()

        assert settings.command.command_review_disposition == "approval"  # 注入的对象不被原地改写
        assert builder._security_settings.command.command_review_disposition == expected
        assert resolver.security_settings.command.command_review_disposition == expected

    @pytest.mark.parametrize("mode", ["dontInterrupt", "dontAsk"])
    def test_mode_intersects_tool_allow(self, mode):
        """AC-12：mode 裁剪与 tool_allow 叠加，结果为两者交集。"""
        extra = [_approval_tool(), _execute_tool(), _plain_tool()]
        builder = _builder(mode)
        mode_filtered = builder._prepare_agent_tools(extra_tools=extra, langchain_middleware=[])

        allow = [APPROVAL_TOOL_NAME, PLAIN_TOOL_NAME]
        ctx = ProcessorContext(
            state={},
            config=RunnableConfig(configurable={"execute_kwargs": ExecuteKwargs(mode=mode, tool_allow=allow)}),
            tools=list(mode_filtered),
        )
        ToolFilterMiddleware()(ctx, lambda: None)

        expected = {PLAIN_TOOL_NAME} if mode == "dontInterrupt" else {APPROVAL_TOOL_NAME, PLAIN_TOOL_NAME}
        assert _names(ctx.tools) == expected

    @pytest.mark.parametrize("mode", ["dontInterrupt", "dontAsk"])
    def test_mode_intersects_tool_deny(self, mode):
        """AC-12：mode 与 tool_deny 叠加后黑名单工具也缺失。"""
        extra = [_approval_tool(), _execute_tool(), _plain_tool()]
        builder = _builder(mode)
        mode_filtered = builder._prepare_agent_tools(extra_tools=extra, langchain_middleware=[])

        ctx = ProcessorContext(
            state={},
            config=RunnableConfig(
                configurable={"execute_kwargs": ExecuteKwargs(mode=mode, tool_deny=[PLAIN_TOOL_NAME])}
            ),
            tools=list(mode_filtered),
        )
        ToolFilterMiddleware()(ctx, lambda: None)

        assert PLAIN_TOOL_NAME not in _names(ctx.tools)
        assert EXECUTE_TOOL_NAME in _names(ctx.tools)
