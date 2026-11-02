# -*- coding: utf-8 -*-
"""工具加载模式（``mode``）的装配期过滤与装配级回归测试。

覆盖 T-3（纯函数矩阵）与 T-8（``ReActAgentBuilder`` 装配出的工具名集合），
对应 REQ-2～REQ-5、REQ-7、REQ-10 与 AC-1～AC-4、AC-6、AC-7、AC-12。
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from typing import List

import pytest
from aidev_agent.core.graphs.react import team_middleware
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.graphs.react.tool_loading_mode import (
    command_approval_allowed,
    filter_tools_by_loading_mode,
    filter_tools_by_request,
)
from aidev_agent.core.nodes.tool import build_tool_node
from aidev_agent.core.tools.ask_user_question import ask_user_question as _ask_user_question_tool
from aidev_agent.packages.interrupt_manager import ASK_USER_QUESTION_TOOL_NAME
from aidev_agent.pydantic_models import (
    AgentExecutorKwargs,
    ExecuteKwargs,
    SecurityCommandSettings,
    SecuritySettings,
)
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


def _builder(mode: str | None = None, **request_filters) -> ReActAgentBuilder:
    execute_kwargs = ExecuteKwargs() if mode is None else ExecuteKwargs(mode=mode)
    execute_kwargs = execute_kwargs.model_copy(update=request_filters)
    return ReActAgentBuilder().set_bkai_options(
        AgentExecutorKwargs(security_settings=SecuritySettings(), execute_kwargs=execute_kwargs)
    )


def _assemble(mode: str | None, extra_tools: List[BaseTool]) -> set[str]:
    builder = _builder(mode)
    tools, _, _ = builder._prepare_agent_tools(extra_tools=extra_tools, langchain_middleware=[])
    return _names(tools)


def _assemble_with_request(extra_tools: List[BaseTool], **request_filters) -> List[BaseTool]:
    """请求级过滤（tool_deny / tool_allow / spawn_depth）在装配期一次完成。"""
    builder = _builder(**request_filters)
    return builder._prepare_agent_tools(extra_tools=extra_tools, langchain_middleware=[])[0]


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
        """AC-12：mode 裁剪与 tool_allow 同在装配期完成，结果为两者交集。"""
        extra = [_approval_tool(), _execute_tool(), _plain_tool()]
        names = _names(_assemble_with_request(extra, mode=mode, tool_allow=[APPROVAL_TOOL_NAME, PLAIN_TOOL_NAME]))

        expected = {PLAIN_TOOL_NAME} if mode == "dontInterrupt" else {APPROVAL_TOOL_NAME, PLAIN_TOOL_NAME}
        assert names == expected

    @pytest.mark.parametrize("mode", ["dontInterrupt", "dontAsk"])
    def test_mode_intersects_tool_deny(self, mode):
        """AC-12：mode 与 tool_deny 叠加后黑名单工具也缺失。"""
        extra = [_approval_tool(), _execute_tool(), _plain_tool()]
        names = _names(_assemble_with_request(extra, mode=mode, tool_deny=[PLAIN_TOOL_NAME]))

        assert PLAIN_TOOL_NAME not in names
        assert EXECUTE_TOOL_NAME in names


class TestAssemblyRequestFilters:
    """请求级过滤（深度 / 允许 / 拒绝）全部在装配期完成，不再有绑定期中间件。"""

    @pytest.mark.parametrize(
        "request_filters, expected",
        [
            ({"tool_deny": [EXECUTE_TOOL_NAME]}, {APPROVAL_TOOL_NAME, PLAIN_TOOL_NAME}),
            ({"tool_allow": [EXECUTE_TOOL_NAME, ASK_USER_QUESTION_TOOL_NAME]}, {EXECUTE_TOOL_NAME}),
            ({}, {APPROVAL_TOOL_NAME, EXECUTE_TOOL_NAME, PLAIN_TOOL_NAME}),
        ],
    )
    def test_request_filters_trim_assembly(self, request_filters, expected):
        extra = [_approval_tool(), _execute_tool(), _plain_tool()]
        names = _names(_assemble_with_request(extra, **request_filters))
        assert names == {ASK_USER_QUESTION_TOOL_NAME, *expected}

    def test_deny_then_allow_order(self):
        """deny 先于 allow：先被 deny 掉的名字不会再被 allow 列表捞回来。"""
        extra = [_approval_tool(), _execute_tool(), _plain_tool()]
        both = (PLAIN_TOOL_NAME, APPROVAL_TOOL_NAME)
        names = _names(_assemble_with_request(extra, tool_deny=[PLAIN_TOOL_NAME], tool_allow=both))
        assert names == {APPROVAL_TOOL_NAME}
        assert _names(filter_tools_by_request(list(extra), ExecuteKwargs(tool_deny=[APPROVAL_TOOL_NAME]))) == {
            EXECUTE_TOOL_NAME,
            PLAIN_TOOL_NAME,
        }

    @pytest.mark.parametrize("spawn_depth", [0, 1])
    def test_spawn_depth_drops_agent_tools(self, spawn_depth):
        """spawn_depth >= max_spawn_depth 时 Agent / sendMessages 在装配期即被移除。"""
        extra = [_plain_tool(), _plain_tool(name="Agent"), _plain_tool(name="sendMessages")]
        names = _names(_assemble_with_request(extra, spawn_depth=spawn_depth, max_spawn_depth=1))
        assert ("Agent" not in names and "sendMessages" not in names) is (spawn_depth >= 1)
        assert PLAIN_TOOL_NAME in names


class TestAssemblyStructure:
    def test_tools_package_has_no_graphs_import(self):
        package_root = Path(inspect.getfile(ReActAgentBuilder)).parents[3]
        tools_root = package_root / "core" / "tools"
        assert tools_root.is_dir()
        files = list(tools_root.rglob("*.py"))
        assert files
        offenders = []
        for path in files:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import):
                    modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module]
                else:
                    continue
                offenders.extend((str(path), module) for module in modules if "graphs" in module.split("."))
        assert offenders == []

    def test_build_tool_node_signature_is_pre_feature(self):
        assert list(inspect.signature(build_tool_node).parameters) == [
            "tools",
            "name",
            "tags",
            "handle_tool_errors",
            "messages_key",
            "node_options",
            "security_settings",
            "wrappers",
            "async_wrappers",
        ]

    def test_filter_runs_once_at_assembly_without_builder_catalog_cache(self):
        assert not hasattr(ReActAgentBuilder(), "_lazy_catalog")
        source = textwrap.dedent(inspect.getsource(ReActAgentBuilder._prepare_agent_tools))
        calls = [
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "filter_tools_by_request"
        ]
        assert len(calls) == 2  # 外部与内置集合分别过滤，随后共享定型结果。
        assert not hasattr(team_middleware, "ToolFilterMiddleware")
        assert not hasattr(team_middleware, "apply_tool_filters")

    def test_builder_has_no_source_tracking_fields(self):
        builder = ReActAgentBuilder()
        for name in ("_builtin_tool_names", "_tool_source_order", "_lazy_catalog"):
            assert not hasattr(builder, name)
        module_source = inspect.getsource(inspect.getmodule(ReActAgentBuilder))
        for name in ("source_ids", "builtin_ids", "_remap_tools_named"):
            assert name not in module_source

    def test_lazy_loading_is_prepared_only_by_tool_preparation(self):
        def called_methods(method):
            tree = ast.parse(textwrap.dedent(inspect.getsource(method)))
            return [
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            ]

        assert "_prepare_agent_tools" in called_methods(ReActAgentBuilder.build)
        assert "make_meta_tools(" not in inspect.getsource(ReActAgentBuilder.build)
        assert "make_meta_tools(" in inspect.getsource(ReActAgentBuilder._prepare_agent_tools)
        assert not hasattr(ReActAgentBuilder, "_prepare_lazy_loading")
