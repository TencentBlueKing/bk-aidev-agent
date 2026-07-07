# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from aidev_agent.config import settings
from aidev_agent.core.nodes.model.pydantic_models import NextFunction, ProcessorContext
from aidev_agent.core.tools.skill.provider import SkillRegistry
from aidev_agent.core.tools.skill.types import SkillOptions

logger = logging.getLogger(__name__)


def _extract_local_params(skill: SkillOptions, config: dict) -> dict:
    """提取 FilesystemBackend 的构造参数。

    FilesystemBackend.__init__ 签名：
        root_dir=None, virtual_mode=False, max_file_size_mb=10, envs=None

    返回空字典，使用 FilesystemBackend 默认参数。
    """
    return {}


def _extract_e2b_params(skill: SkillOptions, config: dict) -> dict:
    """提取 E2BSandboxBackend 的构造参数。

    E2BSandboxBackend.__init__ 签名：
        template="sdt-hcomwqox", timeout=600, api_key=None, domain=None, envs=None

    返回空字典，使用 E2BSandboxBackend 默认参数。
    api_key/domain 从环境变量读取（使用默认值）。
    """
    return {}


def _extract_paas_params(skill: SkillOptions, config: dict) -> dict:
    """提取 PaasSandboxBackend 的构造参数。

    PaasSandboxBackend.__init__ 签名（全部 keyword-only）：
        app_code: str = "",
        client: BkPaaSSandboxApi,  # 必填，由 resource_manager 构造
        snapshot: str,
        snapshot_entrypoint: list[str],
        env_vars: dict,

    参数来源优先级：
        - app_code: config 传入（gongfeng 端 executor_info） > settings
        - client: 由 ReActAgentBuilder._prepare_skills() 通过 resource_manager.get_paas_sbx_client 注入
        - snapshot / env_vars: 从 skill metadata 的 bkai_paas_sandbox 字段获取

    env_vars 中的 ACCESS_TOKEN / BKAI_USERNAME 由本函数根据 executor_info 和平台环境解析，
    避免调用全局 resource_manager()（app_code=bkaidev）导致凭证不一致。
    """
    # 由平台测试页传入 app_code
    app_code = config.get("app_code") or settings.APP_CODE

    # 从 skill metadata 中获取 paas sandbox 配置
    paas_sandbox = {}
    env_vars: dict[Any, Any] = {}
    if skill:
        paas_sandbox = skill.get("metadata", {}).get("bkai_paas_sandbox", {})
        env_vars = paas_sandbox.get("envs", {})

    # 特殊规则：如果值是 None，则从环境变量中获取
    for key, value in env_vars.items():
        if value is None or value == "":
            env_vars[key] = os.getenv(key, "")

    # 优先使用 executor_info 中传入的 access_token（由平台测试页通过 oauth_client 生成），
    # 其次回退到环境变量 SANDBOX_BP_ACCESS_TOKEN。
    # 不使用全局 resource_manager().resolve_access_token()，因为全局单例会默认使用平台的 app_code=bkaidev，
    # 其签发的 token 会导致沙箱内 MCP 调用 403（appCode[bkaidev] 无权限）。
    _token_from_config = config.get("access_token")
    _token_from_env = os.getenv("SANDBOX_BP_ACCESS_TOKEN", "")
    access_token = _token_from_config or _token_from_env

    env_vars["ACCESS_TOKEN"] = access_token or os.getenv("SANDBOX_BP_ACCESS_TOKEN", "")
    env_vars["BKAI_USERNAME"] = config.get("executor") or os.getenv("BKAI_USERNAME", "")
    logger.info(
        f"[credential] _extract_paas_params: "
        f"app_code={app_code}, "
        f"token_source={'config' if _token_from_config else 'env' if _token_from_env else 'empty'}, "
        f"executor={config.get('executor')}"
    )

    # 从 envs_mask 提取需要脱敏的 env 值
    envs_mask = paas_sandbox.get("envs_mask", [])
    extra_sensitive_values = [env_vars[k] for k in envs_mask if k in env_vars and env_vars[k]]
    if access_token:
        extra_sensitive_values.append(access_token)

    return {
        "app_code": app_code,
        "bk_username": config.get("executor"),
        "snapshot": paas_sandbox.get("image", ""),
        "snapshot_entrypoint": [],
        "env_vars": env_vars,
        "extra_sensitive_values": extra_sensitive_values,
    }


@dataclass
class SkillsPromptMiddleware:
    """将 Agent Skills 发现信息注入到 system prompt 中（模板管道）。"""

    registry: SkillRegistry
    enable_runtime_tool: bool = False

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        summary = self.registry.get_skills_summary(include_runtime=self.enable_runtime_tool)

        parts: list[str] = [
            "\n\n",
            "# Agent Skills\n",
            "\n技能（Skill）是 Agent 能力的外部延伸，遵循**“按需感知，受控触发”**的渐进式披露原则。每一个技能描述都包含其核心逻辑、环境约束与触发边界。",
            "\n1. 技能的核心定义",
            "\n功能封装：技能是针对特定任务（如数据提取、系统操作、协议转换）的原子化工具集。",
            "\n环境隔离：每个技能运行在独立的 Runtime 环境中，具有特定的 Shell 限制和生命周期。",
            "特例：部分沙箱环境（如 paas_sandbox 系列）接入了共享的持久化卷（PV，Persistent Volume）。PV 指向的路径在多个指定的沙箱之间是完全共享且跨轮次持久化的，用于实现跨技能的产物传递与数据协同。",
            "\n数据旁路：高性能技能通常采用“非对称”设计，即数据流直接在后端处理或下载，不强制经过模型 Context，以确保零 Token 消耗。",
            "\n2. 感知与触发机制",
            "\nAgent 必须通过扫描用户指令中的**“意图特征”**来感知识别技能：",
            "\n场景匹配：当用户需求命中技能描述中的 使用场景 (Scenario) 列表时，该技能的加载优先级高于一切通用推理逻辑。",
            "\n隐式推理：若用户请求的任务规模（如“海量”、“全量”）或技术栈（如特定协议、API）暗示了技能的必要性，应优先选择技能路径。",
            "\n3. 使用规范",
            "\n一旦识别到匹配技能，Agent 必须严格遵守以下 “激活-执行” 协议：",
            "\n主动激活(必须): 在任何实质性操作前，必须首先调用 activate_skill(skill_name=...)。",
            "\n环境适配(必须): 执行技能相关命令时，请将技能的 Runtime 值作为 `runtime` 参数传入`execute` 等工具。",
            "\n路径：skill 脚本通常在 ~/.agents/skills/<skill_name> 中，如果特定 runtime 有指定路径，以指定为主，注意, 不要猜测 ~ 的指向，应该直接使用 ~ 符号",
            "\n执行命令时的 Working Directory 即为技能根目录，初始内容是从 ~/.agents/skills/<skill_name>/ 复制而来的。请直接运行脚本，不要试图修改脚本。如果脚本不能执行可以分析原因，但不可以绕过脚本直接编码执行。",
            "\n参数必须从用户上下文提取，严禁凭空编造。",
            f"\n\n可用技能列表：\n{summary}\n\n",
        ]

        if self.enable_runtime_tool:
            part = (
                "[重要规范：沙箱环境与数据流转] 对于 paas_sandbox 该环境是非持久化的"
                "Runtime 的临时性与非持久化:"
                "临时性：每次用户发送消息，你都将面对一个完全初始化的环境。"
                "禁止依赖：禁止假设之前的执行结果（如临时文件、后台进程、环境变量）在当前轮次依然可用。"
                "PV 的持久性与多沙箱共享:"
                "paas_sandbox 系列的沙箱已经接入 PV, STORAGE_PATH/session 下的文件对于多个paas_sandbox系列的沙箱可见, STORAGE_PATH已经写入系统环境变量，不允许去推测 STORAGE_PATH 的值。"
                "数据协同：若上一个技能在 PV 路径中写入了中间产物，由于 PV 路径在多个沙箱中被共享且持久化，你在当前轮次切换到另一个技能时，依然可以通过 PV 路径直接读取和使用该中间产物。请善加利用此机制进行跨沙箱的任务编排。\n"
                "原子化执行：请尽可能将“准备、执行、清理”逻辑集成在单次指令中，以确保任务的连续性。\n"
                "合并指令:\n 对于 paas_sandbox 命令是单次的。"
                "正确做法：在一次 execute 中使用 && 或管道符，例如：ls -l | grep 'target'"
            )
            parts.append(part)

        injection = "".join(parts)
        ctx.prompt_slots.system = (ctx.prompt_slots.system or "") + injection
        next()
