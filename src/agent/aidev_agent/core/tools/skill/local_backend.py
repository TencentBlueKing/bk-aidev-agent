# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import os
import re

from .types import SkillOptions
from .utils import apply_optional_frontmatter_fields, extract_instructions, parse_frontmatter

logger = logging.getLogger(__name__)

# 常数
MAX_SKILL_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_SKILL_NAME_LENGTH = 64
MAX_SKILL_DESCRIPTION_LENGTH = 1024

# 小写字母/数字和连字符，无前导/尾随连字符，无连续连字符
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _validate_skill_name(name: str, directory_name: str) -> tuple[bool, str]:
    if not name:
        return False, "技能名称不能为空"

    if len(name) > MAX_SKILL_NAME_LENGTH:
        return False, f"技能名称长度 ({len(name)}) 超过限制 ({MAX_SKILL_NAME_LENGTH})"

    if not SKILL_NAME_PATTERN.match(name):
        # 不再强制小写字母/数字/连字符格式，仅打警告
        logger.warning(
            f"技能名称 '{name}' 不符合推荐格式（仅允许小写字母、数字和连字符，"
            f"不能以连字符开头或结尾，不能有连续连字符）"
        )

    if name != directory_name:
        return False, f"技能名称 '{name}' 必须与目录名 '{directory_name}' 一致"

    return True, ""


# Keep backward-compatible alias so any external caller using the old name
# still works without changes.
_parse_frontmatter = parse_frontmatter


def _parse_skill_metadata(content: str, skill_path: str, directory_name: str) -> SkillOptions | None:
    file_size = len(content.encode("utf-8"))
    if file_size > MAX_SKILL_FILE_SIZE:
        logger.warning(f"技能文件大小 ({file_size} bytes) 超过限制 ({MAX_SKILL_FILE_SIZE} bytes): {skill_path}")
        return None

    frontmatter = _parse_frontmatter(content)
    if frontmatter is None:
        logger.warning(f"技能文件缺少 YAML frontmatter: {skill_path}")
        return None

    name = frontmatter.get("name", "")
    description = frontmatter.get("description", "")

    if not name:
        logger.warning(f"技能文件缺少 'name' 字段: {skill_path}")
        return None
    if not description:
        logger.warning(f"技能文件缺少 'description' 字段: {skill_path}")
        return None

    is_valid, error_msg = _validate_skill_name(name, directory_name)
    if not is_valid:
        logger.warning(f"技能名称验证失败 ({skill_path}): {error_msg}")
        return None

    if len(description) > MAX_SKILL_DESCRIPTION_LENGTH:
        logger.warning(f"技能描述长度 ({len(description)}) 超过限制 ({MAX_SKILL_DESCRIPTION_LENGTH}): {skill_path}")
        return None

    result: SkillOptions = {
        "name": name,
        "description": description,
        "path": skill_path,
    }

    apply_optional_frontmatter_fields(result, frontmatter)

    # frontmatter 未声明 runtime 时兜底为 "local"，
    # 否则 ReActAgentBuilder._prepare_skills 会因 runtime 为 None 而跳过该技能。
    if "runtime" not in result:
        result["runtime"] = "local"

    return result


def _list_skills(source_path: str) -> list[SkillOptions]:
    skills: list[SkillOptions] = []

    if not os.path.isdir(source_path):
        logger.warning(f"技能源路径不存在: {source_path}")
        return skills

    try:
        entries = os.listdir(source_path)
    except PermissionError:
        logger.warning(f"无权限访问技能源路径: {source_path}")
        return skills

    for entry in entries:
        entry_path = os.path.join(source_path, entry)
        if not os.path.isdir(entry_path):
            continue

        skill_file = os.path.join(entry_path, "SKILL.md")
        if not os.path.isfile(skill_file):
            continue

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


async def _alist_skills(source_path: str) -> list[SkillOptions]:
    # 当前文件系统实现；保持语义一致
    return _list_skills(source_path)


class LocalBackend:
    """本地文件系统技能后端。

    将现有的 ``_list_skills`` / 文件读取逻辑包装成
    :class:`~aidev_agent.core.tools.skill.types.SkillProviderBackend` 兼容的
    对象，以便与基于后端的
    :class:`~aidev_agent.core.tools.skill.provider.SkillRegistry` 一起使用。
    """

    def __init__(self, path: str) -> None:
        self.path = path

    # -- 技能提供者协议 ------------------------------------------------

    def discover(self) -> list[SkillOptions]:
        """通过扫描 *self.path* 中的 ``SKILL.md`` 文件来发现技能。"""
        return _list_skills(self.path)

    def fetch_instructions(self, skill: SkillOptions) -> str:
        """读取完整的 ``SKILL.md`` 并返回正文（已去除 frontmatter）。"""
        with open(skill["path"], "r", encoding="utf-8") as f:
            content = f.read()
        return extract_instructions(content)

    def __repr__(self) -> str:
        return f"LocalBackend(path={self.path!r})"
