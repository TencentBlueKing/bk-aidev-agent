# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

技能加载器模块。

提供从文件系统加载技能的功能，包括解析 SKILL.md 文件的 YAML frontmatter、
验证技能名称、以及批量加载技能。

参考 LangChain DeepAgents 的 SkillsMiddleware 实现，针对基于 LangGraph 的
Agent 进行适配。
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import PurePosixPath
from typing import NotRequired, Optional

import yaml
from typing_extensions import TypedDict

logger = logging.getLogger(__name__)

# 常量定义
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024

# 技能名称验证正则表达式
# 仅小写字母数字和连字符，不能以连字符开头或结尾，不能有连续连字符
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class SkillMetadata(TypedDict):
    """技能元数据，从 SKILL.md YAML frontmatter 解析。

    遵循 Agent Skills 规范 (https://agentskills.io/specification)。

    Attributes:
        name: 技能名称 (必需，最大64字符，小写字母数字和连字符)
        description: 技能描述 (必需，最大1024字符)
        path: SKILL.md 文件路径
        license: 许可证 (可选)
        compatibility: 环境要求 (可选，最大500字符)
        metadata: 额外元数据 (可选)
        allowed_tools: 预批准工具列表 (可选)
        instructions: 完整指令内容 (激活后加载)
    """

    name: str
    description: str
    path: str
    license: NotRequired[str]
    compatibility: NotRequired[str]
    metadata: NotRequired[dict[str, str]]
    allowed_tools: NotRequired[list[str]]
    instructions: NotRequired[str]


def _validate_skill_name(name: str, directory_name: str) -> tuple[bool, str]:
    """验证技能名称是否符合规范。

    技能名称验证规则：
    - 最大 64 字符
    - 仅小写字母数字和连字符
    - 不能以连字符开头或结尾
    - 不能有连续连字符
    - 必须匹配父目录名

    Args:
        name: 要验证的技能名称
        directory_name: 技能所在目录的名称

    Returns:
        元组 (is_valid, error_message)，
        is_valid 为 True 时表示验证通过，error_message 为空字符串；
        is_valid 为 False 时表示验证失败，error_message 包含失败原因
    """
    # 检查是否为空
    if not name:
        return False, "技能名称不能为空"

    # 检查长度
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, f"技能名称长度 ({len(name)}) 超过限制 ({MAX_SKILL_NAME_LENGTH})"

    # 检查格式（使用正则表达式）
    if not SKILL_NAME_PATTERN.match(name):
        return False, "技能名称格式无效：仅允许小写字母、数字和连字符，不能以连字符开头或结尾，不能有连续连字符"

    # 检查是否匹配目录名
    if name != directory_name:
        return False, f"技能名称 '{name}' 必须与目录名 '{directory_name}' 一致"

    return True, ""


def _parse_skill_metadata(content: str, skill_path: str, directory_name: str) -> SkillMetadata | None:
    """解析 SKILL.md 的 YAML frontmatter。

    从指定路径的 SKILL.md 文件内容中解析 YAML frontmatter 元数据，
    并将其转换为 SkillMetadata 对象。

    参考 deepagents 中的 _parse_skill_metadata 函数。

    Args:
        content: SKILL.md 文件的完整内容
        skill_path: SKILL.md 文件的完整路径
        directory_name: 技能所在目录的名称，用于验证技能名称

    Returns:
        解析后的 SkillMetadata 字典，如果解析失败则返回 None
    """
    # 检查文件大小
    file_size = len(content.encode("utf-8"))
    if file_size > MAX_SKILL_FILE_SIZE:
        logger.warning(f"技能文件大小 ({file_size} bytes) 超过限制 ({MAX_SKILL_FILE_SIZE} bytes): {skill_path}")
        return None

    # 解析 YAML frontmatter
    frontmatter = _parse_frontmatter(content)

    if frontmatter is None:
        logger.warning(f"技能文件缺少 YAML frontmatter: {skill_path}")
        return None

    # 提取必需字段
    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    if not name:
        logger.warning(f"技能文件缺少 'name' 字段: {skill_path}")
        return None
    if not description:
        logger.warning(f"技能文件缺少 'description' 字段: {skill_path}")
        return None

    # 验证技能名称
    is_valid, error_msg = _validate_skill_name(name, directory_name)
    if not is_valid:
        logger.warning(f"技能名称验证失败 ({skill_path}): {error_msg}")
        return None

    # 验证描述长度
    if len(description) > MAX_SKILL_DESCRIPTION_LENGTH:
        logger.warning(f"技能描述长度 ({len(description)}) 超过限制 ({MAX_SKILL_DESCRIPTION_LENGTH}): {skill_path}")
        return None

    # 构建 SkillMetadata
    result: SkillMetadata = {
        "name": name,
        "description": description,
        "path": skill_path,
    }

    # 添加可选字段
    if "license" in frontmatter:
        result["license"] = frontmatter["license"]
    if "compatibility" in frontmatter:
        result["compatibility"] = frontmatter["compatibility"]
    if "metadata" in frontmatter and isinstance(frontmatter["metadata"], dict):
        result["metadata"] = frontmatter["metadata"]
    if "allowed-tools" in frontmatter:
        allowed_tools = frontmatter["allowed-tools"]
        if isinstance(allowed_tools, str):
            result["allowed_tools"] = allowed_tools.split()
        elif isinstance(allowed_tools, list):
            result["allowed_tools"] = allowed_tools

    return result


def _parse_frontmatter(content: str) -> Optional[dict]:
    """解析 Markdown 文件的 YAML frontmatter。

    Args:
        content: Markdown 文件的完整内容

    Returns:
        解析后的 frontmatter 字典，如果没有 frontmatter 则返回 None
    """
    # YAML frontmatter 以 --- 开头和结尾
    if not content.startswith("---"):
        return None

    # 查找结束标记
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return None

    # 提取 YAML 内容
    yaml_end = end_match.start() + 3
    yaml_content = content[3:yaml_end]

    try:
        frontmatter = yaml.safe_load(yaml_content)
        return frontmatter if isinstance(frontmatter, dict) else None
    except yaml.YAMLError as e:
        logger.warning(f"YAML 解析失败: {e}")
        return None


def _list_skills(source_path: str) -> list[SkillMetadata]:
    """列出指定路径下的所有技能（同步版本）。

    参考 deepagents 中的 _list_skills 函数。

    Args:
        source_path: 技能源路径

    Returns:
        成功加载的 SkillMetadata 列表
    """
    skills: list[SkillMetadata] = []

    # 检查路径是否存在
    if not os.path.isdir(source_path):
        logger.warning(f"技能源路径不存在: {source_path}")
        return skills

    # 遍历子目录
    try:
        entries = os.listdir(source_path)
    except PermissionError:
        logger.warning(f"无权限访问技能源路径: {source_path}")
        return skills

    for entry in entries:
        entry_path = os.path.join(source_path, entry)

        # 只处理目录
        if not os.path.isdir(entry_path):
            continue

        # 查找 SKILL.md 文件
        skill_file = os.path.join(entry_path, "SKILL.md")
        if not os.path.isfile(skill_file):
            continue

        # 加载技能
        try:
            with open(skill_file, "r", encoding="utf-8") as f:
                content = f.read()

            skill_metadata = _parse_skill_metadata(content, skill_file, entry)
            if skill_metadata:
                skills.append(skill_metadata)
                logger.debug(f"成功加载技能: {skill_metadata['name']} (from {source_path})")
        except (OSError, IOError) as e:
            logger.warning(f"加载技能失败 '{entry}': {e}")
            continue

    return skills


async def _alist_skills(source_path: str) -> list[SkillMetadata]:
    """列出指定路径下的所有技能（异步版本）。

    参考 deepagents 中的 _alist_skills 函数。

    Args:
        source_path: 技能源路径

    Returns:
        成功加载的 SkillMetadata 列表
    """
    # 由于当前实现基于文件系统，异步版本直接调用同步版本
    # 未来如果需要支持异步后端（如 S3、远程 API），可以在这里实现真正的异步逻辑
    return _list_skills(source_path)


class SkillRegistry:
    """技能注册表，对标 deepagents 的 SkillsMiddleware。

    该类管理技能的加载、注册和激活，提供渐进式披露功能。
    由于当前 Agent 直接基于 LangGraph 实现，不需要 AgentMiddleware，
    因此 SkillRegistry 提供了 SkillsMiddleware 的核心功能，但不包含
    中间件相关的方法（如 _get_backend、modify_request、before_agent、
    abefore_agent、wrap_model_call）。

    Attributes:
        sources: 技能源路径列表
        _skills: 已注册技能的字典，键为技能名称
        _loaded: 是否已完成初始加载

    Example:
        >>> registry = SkillRegistry(["/path/to/skills"])
        >>> summary = registry.get_skills_summary()  # 发现阶段
        >>> skill = registry.activate_skill("code-review")  # 激活阶段
    """

    def __init__(self, sources: list[str]) -> None:
        """初始化注册表。

        Args:
            sources: 技能源路径列表，按顺序加载，后加载覆盖先加载
        """
        self.sources = sources
        self._skills: dict[str, SkillMetadata] = {}
        self._loaded = False

    async def ensure_loaded(self) -> None:
        """确保技能已加载（懒加载，异步）。

        如果技能尚未加载，则调用加载器扫描所有技能目录，
        并将技能元数据注册到内部字典中。
        """
        if self._loaded:
            return

        skills: dict[str, SkillMetadata] = {}

        for source_path in self.sources:
            loaded_skills = await _alist_skills(source_path)
            for skill in loaded_skills:
                if skill["name"] in skills:
                    logger.debug(f"技能 '{skill['name']}' 被来自 '{source_path}' 的版本覆盖")
                skills[skill["name"]] = skill

        self._skills = skills
        self._loaded = True
        logger.info(f"共加载 {len(self._skills)} 个技能")

    def ensure_loaded_sync(self) -> None:
        """确保技能已加载（懒加载，同步）。

        如果技能尚未加载，则调用加载器扫描所有技能目录，
        并将技能元数据注册到内部字典中。
        """
        if self._loaded:
            return

        skills: dict[str, SkillMetadata] = {}

        for source_path in self.sources:
            loaded_skills = _list_skills(source_path)
            for skill in loaded_skills:
                if skill["name"] in skills:
                    logger.debug(f"技能 '{skill['name']}' 被来自 '{source_path}' 的版本覆盖")
                skills[skill["name"]] = skill

        self._skills = skills
        self._loaded = True
        logger.info(f"共加载 {len(self._skills)} 个技能")

    def get_skill(self, name: str) -> SkillMetadata | None:
        """获取指定技能。

        Args:
            name: 技能名称

        Returns:
            技能元数据，如果不存在则返回 None
        """
        self.ensure_loaded_sync()
        return self._skills.get(name)

    async def askill(self, name: str) -> SkillMetadata | None:
        """获取指定技能（异步版本）。

        Args:
            name: 技能名称

        Returns:
            技能元数据，如果不存在则返回 None
        """
        await self.ensure_loaded()
        return self._skills.get(name)

    def list_skills(self) -> list[SkillMetadata]:
        """获取所有技能（同步版本）。

        Returns:
            所有已注册技能的元数据列表
        """
        self.ensure_loaded_sync()
        return list(self._skills.values())

    async def alist_skills(self) -> list[SkillMetadata]:
        """获取所有技能（异步版本）。

        Returns:
            所有已注册技能的元数据列表
        """
        await self.ensure_loaded()
        return list(self._skills.values())

    def get_skills_summary(self) -> str:
        """获取技能摘要（发现阶段）。

        仅返回 name 和 description，用于渐进式披露的第一阶段。
        格式:
            - **skill-name**: description
              → Read `/path/to/SKILL.md` for full instructions

        Returns:
            格式化的技能摘要字符串，每个技能占两行
        """
        self.ensure_loaded_sync()

        if not self._skills:
            paths = self.sources
            return f"(No skills available yet. You can create skills in {' or '.join(paths)})"

        lines = []
        for skill in self._skills.values():
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            if skill.get("allowed_tools"):
                lines.append(f"  -> Allowed tools: {', '.join(skill['allowed_tools'])}")
            lines.append(f"  -> Read `{skill['path']}` for full instructions")

        return "\n".join(lines)

    def _format_skills_locations(self) -> str:
        """格式化技能位置用于系统提示中显示。

        参考 deepagents 中的 _format_skills_locations 方法。

        Returns:
            格式化的技能位置字符串
        """
        locations = []
        for i, source_path in enumerate(self.sources):
            name = PurePosixPath(source_path.rstrip("/")).name.capitalize()
            suffix = " (higher priority)" if i == len(self.sources) - 1 else ""
            locations.append(f"**{name} Skills**: `{source_path}`{suffix}")
        return "\n".join(locations)

    def _format_skills_list(self, skills: list[SkillMetadata]) -> str:
        """格式化技能元数据用于系统提示中显示。

        参考 deepagents 中的 _format_skills_list 方法。

        Args:
            skills: 技能元数据列表

        Returns:
            格式化的技能列表字符串
        """
        if not skills:
            paths = self.sources
            return f"(No skills available yet. You can create skills in {' or '.join(paths)})"

        lines = []
        for skill in skills:
            lines.append(f"- **{skill['name']}**: {skill['description']}")
            if skill.get("allowed_tools"):
                lines.append(f"  -> Allowed tools: {', '.join(skill['allowed_tools'])}")
            lines.append(f"  -> Read `{skill['path']}` for full instructions")
        return "\n".join(lines)

    def activate_skill(self, name: str) -> SkillMetadata | None:
        """激活技能（激活阶段）。

        加载完整的 SKILL.md 指令内容，用于渐进式披露的第二阶段。

        Args:
            name: 技能名称

        Returns:
            包含完整指令的技能元数据，如果技能不存在则返回 None
        """
        self.ensure_loaded_sync()

        skill = self._skills.get(name)
        if skill is None:
            return None

        # 如果指令已加载，直接返回
        if "instructions" in skill:
            return skill

        # 读取 SKILL.md 文件内容
        try:
            with open(skill["path"], "r", encoding="utf-8") as f:
                content = f.read()
            skill["instructions"] = self._extract_instructions(content)
            logger.debug(f"已激活技能: {name}")
        except (OSError, IOError) as e:
            logger.warning(f"激活技能失败 '{name}': {e}")
            skill["instructions"] = ""

        return skill

    @staticmethod
    def _extract_instructions(content: str) -> str:
        """从 SKILL.md 提取指令（跳过 YAML frontmatter）。

        YAML frontmatter 以 '---' 开始和结束，该方法会移除 frontmatter 部分，
        只返回正文内容。

        Args:
            content: SKILL.md 文件的完整内容

        Returns:
            去除 frontmatter 后的指令内容，已去除首尾空白
        """
        if not content.startswith("---"):
            return content.strip()

        # 查找 frontmatter 结束位置
        match = re.search(r"\n---\s*\n", content[3:])
        if match:
            # 返回 frontmatter 之后的内容
            start_pos = 3 + match.end()
            return content[start_pos:].strip()

        return content.strip()
