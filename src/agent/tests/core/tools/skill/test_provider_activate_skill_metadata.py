# -*- coding: utf-8 -*-
"""SkillRegistry.get_activate_skill_tool() 元数据契约单测。

activate_skill 工具需在 metadata 上标记 ``function_type="skill"``，供 AG-UI 事件
构造层透传为前端 ``functionType`` 字段以区分展示样式；同时该工具不是 MCP 工具，
metadata 不应携带 ``mcp_name``（存在即被判定为 MCP 工具，造成语义污染）。
"""

import pytest
from aidev_agent.core.tools.skill.provider import SkillRegistry


@pytest.fixture
def registry(tmp_path) -> SkillRegistry:
    """空目录源，专注工具自身契约，不依赖真实技能文件。"""
    return SkillRegistry([str(tmp_path)])


class TestActivateSkillMetadata:
    @pytest.mark.parametrize(
        "key, expected",
        [
            ("function_type", "skill"),
            ("mcp_name", None),
        ],
    )
    def test_metadata_contract(self, registry, key, expected):
        tool = registry.get_activate_skill_tool()
        assert tool.metadata.get(key) == expected

    def test_tool_name_unchanged(self, registry):
        assert registry.get_activate_skill_tool().name == "activate_skill"
