# -*- coding: utf-8 -*-
"""工具重名去重（packages/langchain_core/tools/dedupe.py）单元测试。

规则：
- 按工具名分组，组内仅一个实例时名字不变；
- 分组名：带审批 -> mcp-<mcp_name>；MCP -> mcp-<-prod- 前的服务名>（解析失败退回 mcp-<mcp_name>）；其余 -> None
- default 组依次 <tool> / Tool001__<tool> / Tool002__<tool>；有分组名 -> <group>__<tool>，同分组合并
"""

from __future__ import annotations

import pytest
from aidev_agent.config import settings
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.nodes.tool import build_tool_node
from aidev_agent.packages.langchain_core.tools.dedupe import (
    MAX_TOOL_NAME_LEN,
    compose_name,
    dedupe_tool_names,
    resolve_group,
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


class TestResolveGroup:
    def test_approval_wins_over_mcp_service(self):
        """带审批一定独立成组，用完整 Server 名而不是服务名。"""
        assert resolve_group(_tool("list", "msdk-prod-mcp1", approval=APPROVAL)) == "mcp-msdk-prod-mcp1"

    def test_approval_without_mcp_name_falls_back_to_tool_name(self):
        assert resolve_group(_tool("list", approval=APPROVAL)) == "mcp-list"

    def test_mcp_uses_service_name(self):
        assert resolve_group(_tool("list", "msdk-console-prod-mcp")) == "mcp-msdk-console"

    def test_mcp_service_unresolvable_falls_back_to_server_name(self):
        assert resolve_group(_tool("list", "foo-mcp")) == "mcp-foo-mcp"
        assert resolve_group(_tool("list", "a-prod-x-prod-y")) == "mcp-a-prod-x-prod-y"
        assert resolve_group(_tool("list", "-prod-mcp")) == "mcp--prod-mcp"

    def test_non_mcp_is_default(self):
        assert resolve_group(_tool("list")) is None

    def test_empty_approval_is_not_approval_group(self):
        """空审批配置不算带审批，按 MCP 服务名分组。"""
        assert resolve_group(_tool("list", "msdk-prod-1", approval={})) == "mcp-msdk"


class TestComposeName:
    def test_double_underscore_separator(self):
        assert compose_name("mcp-msdk-console", "list") == "mcp-msdk-console__list"

    def test_invalid_chars_sanitized(self):
        assert compose_name("mcp-a.b", "do/it") == "mcp-a_b__do_it"

    def test_long_name_truncated(self):
        name = compose_name("mcp-" + "a" * 100, "list")
        assert len(name) <= MAX_TOOL_NAME_LEN
        assert "__list" in name

    def test_long_name_with_invalid_chars_truncated(self):
        """前缀先清洗再截断：非法字符替换成下划线后仍不超长（清洗不能放在截断之后）。"""
        name = compose_name("mcp-" + "." * 100, "list")
        assert len(name) <= MAX_TOOL_NAME_LEN
        assert name.endswith("__list_" + name.rsplit("_", 1)[-1])
        assert set(name) - set("mcp-list_") <= set("0123456789abcdef")  # 仅剩 sha1 摘要字符

    def test_tool_name_longer_than_budget_keeps_digest(self):
        name = compose_name("mcp-" + "a" * 100, "t" * 100)
        assert len(name) <= MAX_TOOL_NAME_LEN
        assert name.startswith("t" * 10)


class TestDedupeNoop:
    def test_unique_names_untouched(self):
        tools = [_tool("a"), _tool("b", mcp_name="s-prod-mcp")]
        result = dedupe_tool_names(tools)
        assert _names(result) == ["a", "b"]
        assert result[0] is tools[0] and result[1] is tools[1]

    def test_empty(self):
        assert dedupe_tool_names([]) == []

    def test_missing_name_raises(self):
        class _NoName:
            name = ""
            metadata = None

        with pytest.raises(ValueError):
            dedupe_tool_names([_tool("a"), _tool("a"), _NoName()])


class TestDefaultGroup:
    def test_sequence_prefixes(self):
        result = dedupe_tool_names([_tool("list"), _tool("list"), _tool("list")])
        assert _names(result) == ["list", "Tool001__list", "Tool002__list"]

    def test_input_order_kept_and_originals_untouched(self):
        first, second = _tool("list"), _tool("list")
        result = dedupe_tool_names([first, second])
        assert result[0] is first
        assert second.name == "list"
        assert result[1].metadata["original_name"] == "list"
        assert result[1].description == "list"

    def test_default_never_merged(self):
        assert _names(dedupe_tool_names([_tool("list"), _tool("list")])) == ["list", "Tool001__list"]


class TestSameGroupMerge:
    def test_same_service_endpoints_merge_into_one(self):
        """同一服务多端点暴露同一份后端能力，合并为一个并记录被合并的 Server。"""
        result = dedupe_tool_names([_tool("list", "msdk-prod-1"), _tool("list", "msdk-prod-2")])
        assert _names(result) == ["mcp-msdk__list"]
        assert result[0].metadata["merged_mcp_servers"] == ["msdk-prod-2"]

    def test_three_endpoints_merge_in_order(self):
        result = dedupe_tool_names([_tool("list", f"msdk-prod-{i}") for i in (1, 2, 3)])
        assert _names(result) == ["mcp-msdk__list"]
        assert result[0].metadata["merged_mcp_servers"] == ["msdk-prod-2", "msdk-prod-3"]

    def test_merged_input_object_untouched(self):
        kept, merged = _tool("list", "msdk-prod-1"), _tool("list", "msdk-prod-2")
        dedupe_tool_names([kept, merged])
        assert kept.metadata == {"mcp_name": "msdk-prod-1"}
        assert merged.metadata == {"mcp_name": "msdk-prod-2"}

    def test_approved_tools_never_merge(self):
        """审批工具分组名含完整 Server 名，同服务也不会合并，审批各自生效。"""
        result = dedupe_tool_names(
            [
                _tool("list", "msdk-prod-1", approval=APPROVAL),
                _tool("list", "msdk-prod-2", approval=APPROVAL),
            ]
        )
        assert _names(result) == ["mcp-msdk-prod-1__list", "mcp-msdk-prod-2__list"]
        assert result[0].metadata["approval"] == APPROVAL

    def test_approved_and_plain_not_merged(self):
        result = dedupe_tool_names([_tool("list", "msdk-prod-1", approval=APPROVAL), _tool("list", "msdk-prod-2")])
        assert _names(result) == ["mcp-msdk-prod-1__list", "mcp-msdk__list"]


class TestGroupedNames:
    def test_different_service_groups_separately(self):
        result = dedupe_tool_names([_tool("list", "a-prod-1"), _tool("list", "b-prod-1")])
        assert _names(result) == ["mcp-a__list", "mcp-b__list"]

    def test_mixed_default_and_mcp(self):
        result = dedupe_tool_names([_tool("list"), _tool("list", "a-prod-1"), _tool("list", "b-prod-1")])
        assert _names(result) == ["list", "mcp-a__list", "mcp-b__list"]

    def test_same_service_merged_but_default_kept(self):
        result = dedupe_tool_names([_tool("list", "a-prod-1"), _tool("list", "a-prod-2"), _tool("list")])
        assert _names(result) == ["mcp-a__list", "list"]

    def test_default_duplicates_numbered_independently(self):
        result = dedupe_tool_names(
            [_tool("list"), _tool("list", "a-prod-1"), _tool("list"), _tool("list"), _tool("list")]
        )
        assert _names(result) == ["list", "mcp-a__list", "Tool001__list", "Tool002__list", "Tool003__list"]

    def test_mcp_without_prod_falls_back_in_group_name(self):
        result = dedupe_tool_names([_tool("list", "foo-mcp"), _tool("list", "foo-mcp-admin")])
        assert _names(result) == ["mcp-foo-mcp__list", "mcp-foo-mcp-admin__list"]

    def test_renamed_group_result_inserted_at_first_position(self):
        """同名组的处理结果整体回填到首次出现的位置，其余工具顺序不变。"""
        result = dedupe_tool_names([_tool("a"), _tool("list", "x-prod-1"), _tool("b"), _tool("list", "y-prod-1")])
        assert _names(result) == ["a", "mcp-x__list", "mcp-y__list", "b"]


class TestResidualDuplicate:
    def test_group_name_collision_raises(self):
        """分组名恰好等于别的工具原名时不做兜底改名，结尾扫描发现重名直接报错。"""
        tools = [_tool("mcp-a__list"), _tool("list", "a-prod-1"), _tool("list", "a-prod-2")]
        with pytest.raises(ValueError, match="重名"):
            dedupe_tool_names(tools)

    def test_many_duplicates_unique(self):
        names = _names(dedupe_tool_names([_tool("list", f"s{i}-prod-1") for i in range(200)]))
        assert len(names) == 200
        assert len(set(names)) == 200


class TestToolNodeRouting:
    """重名工具改名后，tool_node 按名路由与拼装入口接线验证。"""

    @staticmethod
    def _deduped():
        # 跨服务同名工具：各自按服务前缀成组，两个都能被 tool_node 按名路由
        return dedupe_tool_names([_tool("get_task_list", "a-prod-mcp"), _tool("get_task_list", "b-prod-mcp")])

    def test_tool_node_indexes_renamed_names(self):
        node = build_tool_node(tools=self._deduped())
        assert set(node.tools_by_name) == {"mcp-a__get_task_list", "mcp-b__get_task_list"}
        assert set(node._injected_args) == set(node.tools_by_name)

    def test_tool_node_resolves_each_name(self):
        node = build_tool_node(tools=self._deduped())
        assert node.tools_by_name["mcp-a__get_task_list"].invoke({}) == "a-prod-mcp"
        assert node.tools_by_name["mcp-b__get_task_list"].invoke({}) == "b-prod-mcp"

    def test_unknown_old_name_rejected(self):
        node = build_tool_node(tools=self._deduped())
        # 被改名的工具不再以原名注册，模型若凭空造出第三个同名调用会被拒绝而非误路由
        assert node.tools_by_name.get("get_task_list") is None
        assert node.tools_by_name.get("mcp-c__get_task_list") is None

    @staticmethod
    def _prepare(tools):
        builder = ReActAgentBuilder().set_enable_ask_user_question_tool(False)
        builder._enable_agentic_rag_tool = False
        return builder._prepare_agent_tools(extra_tools=tools, langchain_middleware=())

    def test_prepare_agent_tools_dedupes_all_sources(self):
        """拼装入口统一去重：传入的工具与其它来源合并后名字唯一。"""
        tools = self._prepare([_tool("get_task_list", "a-prod-mcp"), _tool("get_task_list", "b-prod-mcp")])
        assert [each.name for each in tools] == ["mcp-a__get_task_list", "mcp-b__get_task_list"]

    def test_switch_off_keeps_original_names(self, monkeypatch):
        """BKAI_TOOL_NAME_DEDUPE_ENABLED=False 时跳过去重，恢复本功能引入前的行为。"""
        monkeypatch.setitem(settings._resolved, "BKAI_TOOL_NAME_DEDUPE_ENABLED", False)
        tools = self._prepare([_tool("get_task_list", "a-prod-mcp"), _tool("get_task_list", "b-prod-mcp")])
        assert [each.name for each in tools] == ["get_task_list", "get_task_list"]
