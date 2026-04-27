# -*- coding: utf-8 -*-

"""
BK-AIDev 技能提供者 - 从 agent_info.related_skills 获取技能。

此模块实现 SkillProvider Protocol，支持从蓝鲸 AIDev 平台
的 related_skills 列表中发现技能，并通过 API 获取完整指引。
"""

from __future__ import annotations

import logging
import re
from typing import Any

from aidev_agent.core.tools.skill.types import SkillOptions
from aidev_agent.core.tools.skill.utils import (
    apply_optional_frontmatter_fields,
    extract_instructions,
    parse_frontmatter,
)
from aidev_agent.packages.resource_manager import ResourceManagerProtocol

logger = logging.getLogger(__name__)

# path 格式: api://{skill_id}/{version}
_PATH_PATTERN = re.compile(r"^api://([^/]+)/(.+)$")


class BKAiProvider:
    """
    BK-AIDev 技能提供者 - 从预配置技能列表和 API 集成。

    该提供者从 Agent 构建时传入的 related_skills 列表（来自 agent_info）
    直接构建技能元数据。在 ``convert_to_options`` 中会调用 API 获取
    frontmatter 可选字段（license, allowed_tools 等），结果通过类级别缓存
    避免重复请求。

    激活时通过 ``fetch_instructions`` 从缓存中取出正文指引。

    Notes
    -----
    _bkai_skill_cache 是类级别缓存，以 (skill_id, version) 为 key，
    value 为 retrieve_skill 的完整返回 dict（附加 ``_cache_instructions``
    和 ``_cache_frontmatter`` 两个解析后字段）。
    相同 skill_id + version 的数据只会从 API 拉取一次，所有实例共享。

    Attributes
    ----------
    client : ResourceManagerProtocol
        业务级资源管理器（含 ``retrieve_skill`` 方法）
    related_skills : list[dict[str, Any]]
        技能列表，来自 agent_info.related_skills
    """

    # 类级别缓存：key 为 (skill_id, version)，value 为完整 API 返回 + 解析字段
    _bkai_skill_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def __init__(
        self,
        client: ResourceManagerProtocol,
        related_skills: list[dict[str, Any]],
    ) -> None:
        """
        初始化 BKAiProvider。

        Parameters
        ----------
        client
            业务级资源管理器，用于调用 retrieve_skill()
        related_skills
            从 agent_info.related_skills 传入的技能列表。
            每个元素是一个 dict，包含以下关键字段：
            - id (int): 技能唯一ID
            - skill_name (str): 技能名称
            - skill_description (str): 技能完整描述
            - version (str): 技能版本
            可选字段：license, compatibility, runtime, icon 等
        """
        self.client = client
        self.related_skills = related_skills

        # 初始化时直接构建 skill_metadata，无需延迟到 discover()
        self.skill_options: list[SkillOptions] = self._build_skill_options(related_skills)

    def __repr__(self) -> str:
        return f"BKAiProvider(skills={len(self.related_skills)})"

    # -- SkillProvider Protocol -----------------------------------------------

    def discover(self) -> list[SkillOptions]:
        """
        发现所有技能，返回初始化时构建的元数据列表。

        直接返回 self.skill_options，无额外计算。
        每个技能的元数据包含：
        - name: 技能名称（来自 skill_name）
        - description: 完整描述（来自 skill_description）
        - path: 伪路径标识来源 (api://...)
        - 可选字段：license, compatibility, metadata, allowed_tools, runtime
          （从 API 的 skill_markdown frontmatter 中获取）

        Returns
        -------
        list[SkillOptions]
            所有技能的元数据列表，不含 instructions 字段（延迟加载）
        """
        return self.skill_options

    def fetch_instructions(self, skill: SkillOptions) -> str:
        """
        获取技能的完整指引文本。

        从 path 字段解析 skill_id 和 version，通过 ``_get_skill_data``
        获取缓存数据，返回其中的 ``_cache_instructions``。

        Parameters
        ----------
        skill
            通过 discover() 返回的技能元数据

        Returns
        -------
        str
            技能的完整指引文本（或空字符串如果获取失败）
        """
        skill_name = skill.get("name", "unknown")

        # 从 path 解析 skill_id 和 version
        skill_id, version = self._parse_path(skill.get("path", ""))
        if not skill_id:
            logger.warning(f"技能 {skill_name} 的 path 格式无效，无法获取指引")
            return ""

        try:
            cached = self._get_skill_data(skill_id, version)
            return cached.get("_cache_instructions", "")
        except Exception as e:
            logger.error(
                f"获取技能指引失败 {skill_name}: {type(e).__name__}: {e}",
                exc_info=True,
            )
            return ""

    # -- 数据获取与缓存 -------------------------------------------------------

    def _get_skill_data(self, skill_id: str, version: str) -> dict[str, Any]:
        """
        根据 (skill_id, version) 获取完整的技能数据。

        优先从类级别缓存中读取；缓存未命中时调用
        ``self.client.retrieve_skill()`` 获取，解析 frontmatter
        并缓存结果。

        缓存的 dict 除了 API 原始字段外，还包含：
        - ``_cache_instructions``: 正文（去掉 frontmatter 后的内容）
        - ``_cache_frontmatter``: 解析后的 frontmatter dict（或空 dict）

        Parameters
        ----------
        skill_id
            技能 ID（字符串）
        version
            技能版本

        Returns
        -------
        dict[str, Any]
            缓存的完整技能数据
        """
        cache_key = (str(skill_id), str(version))

        if cache_key in BKAiProvider._bkai_skill_cache:
            logger.debug(f"使用缓存数据: skill_id={skill_id}, v={version}")
            return BKAiProvider._bkai_skill_cache[cache_key]

        logger.debug(f"调用 API 获取数据: skill_id={skill_id}, v={version}")
        api_response = self.client.retrieve_skill(skill_id=skill_id, version=version)

        # 解析 skill_markdown 中的 frontmatter 和正文
        raw_markdown = api_response.get("skill_markdown", "")
        frontmatter = parse_frontmatter(raw_markdown) if raw_markdown else None
        instructions = extract_instructions(raw_markdown) if raw_markdown else ""

        api_response["_cache_instructions"] = instructions
        api_response["_cache_frontmatter"] = frontmatter or {}

        BKAiProvider._bkai_skill_cache[cache_key] = api_response
        logger.debug(f"已缓存技能数据: skill_id={skill_id}, v={version} (instructions_len={len(instructions)})")
        return api_response

    # -- 辅助方法 -----------------------------------------------------------

    def _build_skill_options(self, related_skills: list[dict[str, Any]]) -> list[SkillOptions]:
        """
        从 related_skills 列表批量构建 SkillOptions。

        遍历 related_skills，逐个调用 convert_to_options()，
        转换失败的技能被记录警告后跳过。

        Parameters
        ----------
        related_skills
            来自 agent_info.related_skills 的技能列表

        Returns
        -------
        list[SkillOptions]
            成功转换的技能元数据列表
        """
        skills: list[SkillOptions] = []

        for skill_data in related_skills:
            try:
                skill_options = self.convert_to_options(skill_data)
                if skill_options:
                    skills.append(skill_options)
            except Exception as e:
                logger.warning(f"转换技能元数据失败 (skill_name={skill_data.get('skill_name', 'unknown')}): {e}")
                continue

        logger.info(f"从 related_skills 构建了 {len(skills)} 个技能元数据")
        return skills

    def convert_to_options(self, skill_data: dict[str, Any]) -> SkillOptions | None:
        """
        将 related_skills 中的单个记录转换为 SkillOptions。

        仅设置 name、description、path 基本字段。
        可选字段（license, compatibility, allowed_tools, runtime 等）
        通过调用 ``_get_skill_data`` 从 API 的 frontmatter 中获取。

        Parameters
        ----------
        skill_data
            来自 related_skills 列表中的单个技能记录

        Returns
        -------
        SkillOptions | None
            转换后的技能元数据，转换失败返回 None
        """
        # 提取必需字段
        skill_id = skill_data.get("id")  # int 类型
        skill_name: str = skill_data.get("skill_name")
        skill_description: str = skill_data.get("skill_description") or skill_data.get("description", "")
        version = skill_data.get("version", "latest")

        # 验证必需字段
        if not all([skill_id, skill_name, skill_description]):
            logger.debug(
                f"技能记录缺少必需字段: id={skill_id}, skill_name={skill_name}, skill_description={skill_description}"
            )
            return None

        # 构建基本 SkillOptions
        skill_options: SkillOptions = {
            "name": skill_name,
            "description": skill_description,
            "path": f"api://{skill_id}/{version}",
        }

        # 从 API 缓存中获取可选字段（frontmatter）
        try:
            cached = self._get_skill_data(str(skill_id), str(version))
            frontmatter = cached.get("_cache_frontmatter", {})
            if frontmatter:
                apply_optional_frontmatter_fields(
                    skill_options,
                    frontmatter,
                    stringify_simple_fields=True,
                    convert_list_elements=True,
                )

            # 将 sandbox 信息写入 metadata["metadata"]["bkai_paas_sandbox"]
            sandbox = cached.get("sandbox")
            if sandbox:
                skill_options.setdefault("metadata", {})
                skill_options["metadata"]["bkai_paas_sandbox"] = sandbox
                if "envs" in sandbox and "WORKSPACE" in sandbox["envs"]:
                    workspace_dir = sandbox["envs"]["WORKSPACE"]
                    skill_path_desc = (
                        f"\npaas沙箱环境：技能在沙箱的{workspace_dir}路径中,脚本放在 {workspace_dir}/scripts 下。"
                        f"初始内容是从 ~/.agents/skills/<skill_name>/ 复制的。"
                        f"执行命令时的 Working Directory 已经是技能根目录{workspace_dir} 了，可以直接 ls {workspace_dir} 了解结构。"
                        f"直接运行脚本，不要去修改脚本。"
                    )
                    skill_options["description"] = (skill_options["description"] or "") + skill_path_desc
        except Exception as e:
            logger.warning(f"获取技能 {skill_name} 的 frontmatter 失败，仅使用基本字段: {e}")

        # 如果 frontmatter 中没有提供 runtime，默认指定为 "paas"
        if "runtime" not in skill_options:
            skill_options["runtime"] = "paas_sandbox"

        logger.debug(f"成功转换技能: {skill_name} (id={skill_id}, v={version})")
        return skill_options

    @staticmethod
    def _parse_path(path: str) -> tuple[str, str]:
        """
        从 path 字段解析 skill_id 和 version。

        Parameters
        ----------
        path
            格式为 ``api://{skill_id}/{version}``

        Returns
        -------
        tuple[str, str]
            (skill_id, version)，解析失败返回 ("", "")
        """
        match = _PATH_PATTERN.match(path)
        if match:
            return match.group(1), match.group(2)
        return "", ""

    @classmethod
    def clear_cache(cls) -> None:
        """
        清空类级别的技能数据缓存。

        所有 BKAiProvider 实例共享此缓存，清空后
        下次访问会重新从 API 拉取。

        在以下场景下使用：
        - 需要重新从 API 获取最新数据
        - 长期运行需要定期清理内存
        """
        cls._bkai_skill_cache.clear()
        logger.info("已清空 BKAiProvider 类级别缓存")
