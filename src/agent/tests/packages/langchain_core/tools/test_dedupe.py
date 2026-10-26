# -*- coding: utf-8 -*-
"""工具重名去重（packages/langchain_core/tools/dedupe.py）单元测试。

规则：
- 按工具名分组，组内仅一个工具时名字不变；
- 同名组再分组：内置 -> default（原名）；带审批 -> mcp-<mcp_name>（无则 approvalNNN）独立；
  MCP -> mcp-<service>-prod 同服务合并；其余 -> ToolNNN 独立；
- 再分组后只剩一个组时保留原名；改名冲突时序号前缀取下一个序号，其余前缀追加 2、3 ...
"""

from __future__ import annotations

import pytest
from aidev_agent.config import settings
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.nodes.tool import build_tool_node
from aidev_agent.core.tools.tool_lazy_loading.meta_tools import DESCRIBE_TOOL_NAME
from aidev_agent.packages.langchain_core.tools.dedupe import (
    MAX_TOOL_NAME_LEN,
    _classify,
    compose_name,
    dedupe_tool_names,
)
from langchain_core.tools import StructuredTool

APPROVAL = {"enabled": True, "target": {"type": "mcp", "id": "1"}}


def _tool(name: str, mcp_name: str | None = None, approval: dict | None = None) -> StructuredTool:
    def _run(**kwargs):
        return mcp_name or name

    metadata: dict = {}
    if mcp_name:
        metadata["mcp_name"] = mcp_name
    if approval is not None:
        metadata["approval"] = approval
    return StructuredTool.from_function(func=_run, name=name, description=name, metadata=metadata or None)


def _names(tools) -> list[str]:
    return [each.name for each in tools]


def _p(name, mcp=None, approval=None):
    return (name, mcp, approval)


class TestResolveGroup:
    @pytest.mark.parametrize(
        "mcp_name, approval, expected",
        [
            (None, None, ("Tool", True, False)),
            (None, APPROVAL, ("approval", True, False)),
            ("msdk-prod-mcp1", APPROVAL, ("mcp-msdk-prod-mcp1", False, False)),
            ("msdk-console-prod-mcp", None, ("mcp-msdk-console-prod", False, True)),
            ("msdk-prod-1", {}, ("mcp-msdk-prod", False, True)),
            ("foo-mcp", None, ("mcp-foo-mcp", False, True)),
            ("a-prod-x-prod-y", None, ("mcp-a-prod-x-prod-y", False, True)),
            ("-prod-mcp", None, ("mcp--prod-mcp", False, True)),
        ],
    )
    def test_group(self, mcp_name, approval, expected):
        assert _classify(_tool("list", mcp_name, approval=approval)) == expected


class TestComposeName:
    def test_double_underscore_separator(self):
        assert compose_name("mcp-msdk-console-prod", "list") == "mcp-msdk-console-prod__list"

    def test_invalid_chars_sanitized(self):
        assert compose_name("mcp-a.b", "do/it") == "mcp-a_b__do_it"

    @pytest.mark.parametrize("prefix, name", [("mcp-" + "a" * 100, "list"), ("mcp-" + "." * 100, "list")])
    def test_long_prefix_truncated(self, prefix, name):
        result = compose_name(prefix, name)
        assert len(result) <= MAX_TOOL_NAME_LEN
        assert "__list_" in result

    def test_tool_name_longer_than_budget_keeps_digest(self):
        name = compose_name("mcp-" + "a" * 100, "t" * 100)
        assert len(name) <= MAX_TOOL_NAME_LEN
        assert name.startswith("t" * 10)


class TestDedupe:
    @pytest.mark.parametrize(
        "externals, builtins, expected",
        [
            ([_p("a"), _p("b", "s-prod-mcp")], [], ["a", "b"]),
            ([_p("list"), _p("list")], [], ["Tool001__list", "Tool002__list"]),
            ([_p("list", "msdk-prod-1"), _p("list", "msdk-prod-2")], [], ["list"]),
            ([_p("list", f"msdk-prod-{i}") for i in (1, 2, 3)], [], ["list"]),
            ([_p("list", "a-prod-1"), _p("list", "b-prod-1")], [], ["mcp-a-prod__list", "mcp-b-prod__list"]),
            (
                [_p("list", "msdk-prod-1", APPROVAL), _p("list", "msdk-prod-2", APPROVAL)],
                [],
                ["mcp-msdk-prod-1__list", "mcp-msdk-prod-2__list"],
            ),
            (
                [_p("list", "msdk-prod-1", APPROVAL), _p("list", "msdk-prod-2")],
                [],
                ["mcp-msdk-prod-1__list", "mcp-msdk-prod__list"],
            ),
            ([_p("list", approval=APPROVAL), _p("list")], [], ["approval001__list", "Tool001__list"]),
            (
                [_p("list"), _p("list", "a-prod-1"), _p("list", "b-prod-1")],
                [],
                ["Tool001__list", "mcp-a-prod__list", "mcp-b-prod__list"],
            ),
            ([_p("list", "a-prod-1"), _p("list", "a-prod-2"), _p("list")], [], ["mcp-a-prod__list", "Tool001__list"]),
            (
                [_p("list", "foo-mcp"), _p("list", "foo-mcp-admin")],
                [],
                ["mcp-foo-mcp__list", "mcp-foo-mcp-admin__list"],
            ),
            (
                [_p("a"), _p("list", "x-prod-1"), _p("b"), _p("list", "y-prod-1")],
                [],
                ["a", "mcp-x-prod__list", "mcp-y-prod__list", "b"],
            ),
            ([_p("read_file")], ["read_file"], ["Tool001__read_file"]),
            ([_p("read_file"), _p("read_file")], ["read_file"], ["Tool001__read_file", "Tool002__read_file"]),
            ([_p("list", "m-prod-1"), _p("list", "m-prod-2")], ["list"], ["mcp-m-prod__list"]),
            ([_p("read_file"), _p("biz")], ["read_file"], ["Tool001__read_file", "biz"]),
        ],
    )
    def test_names(self, externals, builtins, expected):
        builtin = [_tool(name) for name in builtins]
        assert _names(dedupe_tool_names([_tool(*each) for each in externals], builtin_tools=builtin)) == expected
        assert _names(builtin) == builtins

    @pytest.mark.parametrize(
        "externals, builtins, expected",
        [
            (
                [_p("mcp-a-prod__list"), _p("list", "a-prod-1"), _p("list", "b-prod-1")],
                [],
                ["mcp-a-prod__list", "mcp-a-prod2__list", "mcp-b-prod__list"],
            ),
            (
                [_p("read_file"), _p("read_file"), _p("Tool001__read_file")],
                ["read_file", "Tool002__read_file"],
                ["Tool003__read_file", "Tool004__read_file", "Tool001__read_file"],
            ),
            ([_p("list", "msdk-prod-1")], ["list", "mcp-msdk-prod__list"], ["mcp-msdk-prod2__list"]),
            (
                [_p("list", approval=APPROVAL), _p("list", approval=APPROVAL), _p("approval001__list")],
                [],
                ["approval002__list", "approval003__list", "approval001__list"],
            ),
        ],
    )
    def test_allocated_name_skips_taken(self, externals, builtins, expected):
        """改名冲突：序号前缀取下一个序号，其余前缀追加 2、3 ...（原名、内置名、已分配名均算占用）。"""
        builtin = [_tool(name) for name in builtins]
        assert _names(dedupe_tool_names([_tool(*each) for each in externals], builtin_tools=builtin)) == expected

    @pytest.mark.parametrize(
        "externals, builtins, reserved",
        [
            ([_p("list"), _p("list"), _p("list", approval=APPROVAL)], [], ()),
            ([_p("list", "m-prod-1"), _p("list", "m-prod-2"), _p("list", "n-prod-1")], [], ()),
            ([_p("list", "m-prod-1", APPROVAL), _p("list", "m-prod-2", APPROVAL)], ["list"], ()),
            ([_p("mcp-a-prod__list"), _p("list", "a-prod-1"), _p("list", "b-prod-1")], [], ()),
            ([_p("read_file"), _p("read_file"), _p("Tool001__read_file")], ["read_file", "Tool002__read_file"], ()),
            ([_p("tool_call"), _p("biz")], [], ("tool_call",)),
            ([_p("t" * MAX_TOOL_NAME_LEN)], ["t" * MAX_TOOL_NAME_LEN], ()),
        ],
    )
    def test_idempotent(self, externals, builtins, reserved):
        """同一工具列表多次去重结果固定（工具名进入 prompt 前缀，变化会让模型 KV cache 失效）。

        覆盖：同一批实例重复调用、每次请求重新构造实例；输入不被修改，所以重复调用不会漂移。
        """

        def run(tools, builtin):
            return _names(dedupe_tool_names(tools, builtin_tools=builtin, reserved_names=reserved))

        tools, builtin = [_tool(*each) for each in externals], [_tool(name) for name in builtins]
        first = run(tools, builtin)
        assert run(tools, builtin) == first
        assert run([_tool(*each) for each in externals], [_tool(name) for name in builtins]) == first
        assert _names(tools) == [each[0] for each in externals]

    def test_unique_and_empty_untouched(self):
        tools = [_tool("a"), _tool("b")]
        assert all(x is y for x, y in zip(dedupe_tool_names(tools), tools))
        assert dedupe_tool_names([]) == []

    def test_inputs_untouched_and_no_extra_metadata(self):
        first, second = _tool("list", "m-prod-1"), _tool("list")
        result = dedupe_tool_names([first, second, _tool("list", "m-prod-2")])
        assert _names([first, second]) == ["list", "list"]
        assert first.metadata == {"mcp_name": "m-prod-1"} and second.metadata is None
        assert result[0].metadata == {"mcp_name": "m-prod-1"} and result[1].description == "list"

    def test_many_duplicates_unique(self):
        names = _names(dedupe_tool_names([_tool("list", f"s{i}-prod-1") for i in range(200)] + [_tool("list")] * 3))
        assert len(names) == len(set(names)) == 203


class TestErrors:
    def test_missing_name_raises(self):
        class _NoName:
            name = ""
            metadata = None

        with pytest.raises(ValueError, match="name"):
            dedupe_tool_names([_tool("a"), _NoName()])

    @pytest.mark.parametrize("builtins, reserved", [(["read_file", "read_file"], ()), (["read_file"], ("read_file",))])
    def test_duplicate_builtin_names_fail_loud(self, builtins, reserved):
        """default 组只能有一个工具：内置之间、内置与保留名之间同名都无法改名消解。"""
        with pytest.raises(ValueError, match="read_file"):
            dedupe_tool_names([_tool("biz")], builtin_tools=[_tool(n) for n in builtins], reserved_names=reserved)

    def test_shared_builtin_instance_omitted(self):
        shared = _tool("read_file")
        assert _names(dedupe_tool_names([shared, _tool("biz")], builtin_tools=[shared])) == ["biz"]

    def test_long_name_alias_respects_limit(self):
        name = "t" * MAX_TOOL_NAME_LEN
        result = dedupe_tool_names([_tool(name)], builtin_tools=[_tool(name)])
        assert len(result[0].name) <= MAX_TOOL_NAME_LEN and result[0].name != name


class TestToolNodeRouting:
    """重名工具改名后，tool_node 按名路由与拼装入口接线验证。"""

    NAMES = {"mcp-a-prod__get_task_list", "mcp-b-prod__get_task_list"}

    @staticmethod
    def _sources():
        return [_tool("get_task_list", "a-prod-mcp"), _tool("get_task_list", "b-prod-mcp")]

    def test_tool_node_routes_renamed_names(self):
        node = build_tool_node(tools=dedupe_tool_names(self._sources()))
        assert set(node.tools_by_name) == set(node._injected_args) == self.NAMES
        assert node.tools_by_name["mcp-a-prod__get_task_list"].invoke({}) == "a-prod-mcp"
        assert node.tools_by_name["mcp-b-prod__get_task_list"].invoke({}) == "b-prod-mcp"
        assert node.tools_by_name.get("get_task_list") is None

    @staticmethod
    def _prepare(tools):
        builder = ReActAgentBuilder().set_enable_ask_user_question_tool(False)
        builder._enable_agentic_rag_tool = False
        prepared, _builtin, _catalog = builder._prepare_agent_tools(extra_tools=tools, langchain_middleware=())
        return prepared

    def test_prepare_agent_tools_dedupes_all_sources(self):
        assert set(_names(self._prepare(self._sources()))) == self.NAMES

    def test_switch_off_keeps_original_names(self, monkeypatch):
        """BKAI_TOOL_NAME_DEDUPE_ENABLED=False 时跳过去重，恢复本功能引入前的行为。"""
        monkeypatch.setitem(settings._resolved, "BKAI_TOOL_NAME_DEDUPE_ENABLED", False)
        assert _names(self._prepare(self._sources())) == ["get_task_list", "get_task_list"]

    def test_meta_tool_name_reserved_in_single_pass(self, monkeypatch):
        """延迟加载开启时元工具名在唯一一次去重里占位，外部同名工具让名。"""
        monkeypatch.setitem(settings._resolved, "BKAI_TOOL_LAZY_LOADING_ENABLED", True)
        monkeypatch.setitem(settings._resolved, "BKAI_TOOL_LAZY_LOADING_THRESHOLD", 0)
        names = _names(self._prepare([_tool(DESCRIBE_TOOL_NAME)]))
        assert f"Tool001__{DESCRIBE_TOOL_NAME}" in names and names.count(DESCRIBE_TOOL_NAME) == 1
