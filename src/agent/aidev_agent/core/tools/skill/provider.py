# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Union

from langchain_core.tools import BaseTool, StructuredTool

from .local_backend import LocalBackend
from .types import SkillOptions, SkillProviderBackend

logger = logging.getLogger(__name__)


class SkillRegistry:
    """技能注册表，用于发现（摘要）和激活（完整说明）。

    支持**基于后端**的可扩展性模型。每个 :class:`~SkillProviderBackend`
    负责发现技能并获取其说明。注册表汇总来自所有已注册后端的结果。

    向后兼容性
    ---------------------
    当 *sources* 包含纯 ``str`` 路径（原始 API）时，每个路径
    自动包装在 :class:`LocalBackend` 中。这意味着
    现有调用站点（``SkillRegistry(["./.agent/skills"])``)继续
    可以工作而无需任何修改。
    """

    # ------------------------------------------------------------------
    # 实例初始化
    # ------------------------------------------------------------------

    def __init__(self, sources: list[Union[str, SkillProviderBackend]]) -> None:
        self._providers: list[SkillProviderBackend] = []
        self._skills: dict[str, SkillOptions] = {}
        self._skill_provider_map: dict[str, SkillProviderBackend] = {}
        self._loaded = False

        for source in sources:
            if isinstance(source, str):
                # 将字符串源视为本地文件系统路径
                self._providers.append(LocalBackend(source))
            else:
                # 直接的 SkillProviderBackend 实例
                self._providers.append(source)

    # ------------------------------------------------------------------
    # 提供者注册辅助方法
    # ------------------------------------------------------------------

    def register_provider(self, provider: SkillProviderBackend) -> None:
        """在运行时注册一个额外的后端。

        如果技能已经被加载，注册表会在下次访问时自动重新发现，
        无需手动调用 :meth:`reload`。
        """
        self._providers.append(provider)
        self._loaded = False

    def reload(self) -> None:
        """在下次访问时强制从所有后端重新发现。"""
        self._loaded = False
        self._skills.clear()
        self._skill_provider_map.clear()

    # ------------------------------------------------------------------
    # 加载（延迟加载）
    # ------------------------------------------------------------------

    def ensure_loaded(self) -> None:
        if self._loaded:
            return

        skills: dict[str, SkillOptions] = {}
        skill_provider_map: dict[str, SkillProviderBackend] = {}

        for provider in self._providers:
            loaded_skills = provider.discover()
            for skill in loaded_skills:
                if skill["name"] in skills:
                    logger.debug(f"技能 '{skill['name']}' 被来自 '{provider!r}' 的版本覆盖")
                skills[skill["name"]] = skill
                skill_provider_map[skill["name"]] = provider

        self._skills = skills
        self._skill_provider_map = skill_provider_map
        self._loaded = True
        logger.info(f"共加载 {len(self._skills)} 个技能")

    # ------------------------------------------------------------------
    # 公共查询 API（签名未改变）
    # ------------------------------------------------------------------

    def list_skills(self) -> list[SkillOptions]:
        self.ensure_loaded()
        return list(self._skills.values())

    def get_skill(self, name: str) -> SkillOptions | None:
        self.ensure_loaded()
        return self._skills.get(name)

    def get_skills_summary(self, *, include_runtime: bool = False) -> str:
        self.ensure_loaded()

        if not self._skills:
            return "暂无可用技能"

        lines: list[str] = []
        for skill in self._skills.values():
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            if skill.get("allowed_tools"):
                lines.append(f"  -> 允许使用的工具: {', '.join(skill['allowed_tools'])}")
            if include_runtime:
                runtime = skill.get("runtime", "local")
                lines.append(f"  -> Runtime: `{runtime}_{skill['name']}`")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 激活
    # ------------------------------------------------------------------

    def activate_skill(self, name: str) -> SkillOptions | None:
        self.ensure_loaded()

        skill = self._skills.get(name)
        if skill is None:
            return None

        if "instructions" in skill:
            return skill

        provider = self._skill_provider_map.get(name)
        if provider is None:
            logger.warning(f"激活技能失败 '{name}': 未找到对应的 provider")
            skill["instructions"] = ""
            return skill

        try:
            skill["instructions"] = provider.fetch_instructions(skill)
            logger.debug(f"已激活技能: {name}")
        except Exception as e:
            logger.warning(f"激活技能失败 '{name}': {e}")
            skill["instructions"] = ""

        return skill

    # ------------------------------------------------------------------
    # activate_skill LangChain Tool
    # ------------------------------------------------------------------

    def get_activate_skill_tool(self) -> BaseTool:
        """构建 activate_skill LangChain Tool。"""

        def activate_skill(skill_name: str) -> str:
            """Load and return full instructions for a skill."""
            skill = self.activate_skill(skill_name)
            if skill is None:
                available = ", ".join(s["name"] for s in self.list_skills())
                return f"Error: Unknown skill '{skill_name}'. Available skills: {available or '(none)'}"
            return skill.get("instructions", "") or ""

        return StructuredTool.from_function(
            name="activate_skill",
            description="Activate a skill by name and return its full SKILL.md instructions (YAML frontmatter removed).",
            func=activate_skill,
            # function_type 供 AG-UI 事件构造层透传给前端 functionType，用于区分展示样式
            metadata={"function_type": "skill"},
        )
