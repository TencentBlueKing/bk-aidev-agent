# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_approval

TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the " License ");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.

命令级审批（Layer 2 HITL）。

在命令既未命中危险命令黑名单（``packages.security.command.command_blocklist``）、也未命中命令
允许列表（``packages.security.command.command_security``）时——即「灰名单」命令——由执行
路径调用本模块，经 ``interrupt()`` 挂起图执行并走 ITSM 审批。

本模块只在 ``command_review_disposition="approval"`` 时被调用；``allow`` / ``block`` 两档
在 ``command_security.enforce_command_security`` 内直接返回 / 抛错，不经过此处。

与工具级审批的分工：工具级审批在工具调用前对「整个工具」做一次性审批；本模块在工具
**内部**对「单条命令」做分级审批——允许列表直行、黑名单硬拒绝、灰名单按处置档处理，避免审批
疲劳被利用。分级的意义在于把人工注意力只花在真正无法静态判定的那条命令上。

复用现有审批设施：构造 :class:`~aidev_agent.packages.interrupt_manager.approval.ApprovalTarget`
（``target_type="command"``，toolName/toolCode 均为 ``execute``，args 携带命令
与目标运行时），经 ``interrupt()`` 挂起；流结束侧由既有 ``ApprovalHandler``
建 ITSM 工单，resume 侧由既有编排校验终态后回放。

安全语义（fail-closed）：未启用 / 未配置审批人 / 非字符串命令 / interrupt
异常，一律返回 False（拒绝执行），绝不因审批能力缺失而放行。放行只能来自「明确
解析出的人工批准」，任何「无法判定」都归入拒绝。

公开接口：
- require_command_approval(): 对单条灰名单命令发起审批，返回是否放行
- command_fingerprint(): 归一化命令指纹（审计追踪用）
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from langgraph.types import interrupt

from aidev_agent.packages.interrupt_manager.approval import (
    TOOL_APPROVAL_REASON,
    ApprovalTarget,
)
from aidev_agent.pydantic_models import SecurityCommandSettings

logger = logging.getLogger(__name__)


def _command_approvers(security_settings: SecurityCommandSettings) -> list[str]:
    """读取命令级审批人（安全配置 ``command_approval_approvers``，逗号分隔）。

    仅当 ``command_review_disposition="approval"`` 时被消费。去空（容忍配置里的多余逗号与
    空格）且**保序**去重：审批人顺序对建单可见，重复项没有业务含义，故只消除重复而不重排。
    """
    raw = security_settings.command_approval_approvers
    return list(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))


def command_fingerprint(command: str) -> str:
    """归一化命令指纹（去空白 / 统一小写），供审计追踪与 ``toolCallId`` 使用。

    归一化两个维度：内部连续空白折叠为单空格、整体转小写。目的是让「同一条命令
    的不同书写」（大小写差异、多余空格）落到同一指纹，使审计与审批单能按命令聚合。
    截断到 16 位十六进制：足够区分、又不至于让 ``toolCallId`` 过长。
    """
    normalized = re.sub(r"\s+", " ", command.strip().lower())
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def _decision_is_approved(decision: Any) -> bool:
    """解析 ``interrupt()`` 返回的审批 decision，判定是否放行。

    要接受三种形状，因为 resume 侧的载荷形态由调用方与历史工单共同决定：

    - ``list[dict]``：取首元素（``interrupt()`` 在部分编排下会把 decision 包成列表）；
    - ``dict`` 且含 ``payload`` 子对象：读 ``payload["approved"]``；
    - 扁平 ``dict``：读 ``approved``，否则读 ``payload.status`` 或 ``status``。

    非 dict / 空列表 / 无任何终态字段一律判为拒绝（fail-closed）：无法确认「人工批准」
    时不能默认放行。
    """
    if isinstance(decision, list) and decision:
        decision = decision[0]
    if not isinstance(decision, dict):
        return False
    payload = decision.get("payload") if isinstance(decision.get("payload"), dict) else decision
    if "approved" in payload:
        return payload["approved"] is True
    status = payload.get("status") or decision.get("status")
    return status in (True, "approved", "resolved", "approve")


def require_command_approval(
    command: Any,
    *,
    target_runtime: str = "",
    security_settings: SecurityCommandSettings,
    command_review: dict[str, Any] | None = None,
) -> bool:
    """对单条灰名单命令发起 ITSM 审批（HITL），返回是否放行。

    Args:
        command: 待审批的命令字符串（防御性接受任意类型；非字符串拒绝，因为非字符串
            无法构成一条可执行命令，也就无法审批）。
        target_runtime: 目标运行时标识（写入审批单 ``toolArgs``，便于审计）。
        security_settings: 安全配置，由调用方显式传入（来自 ``AgentConfig.security_settings``）。
            **必填**：配置缺失时无从取审批人，属 fail-closed 场景，不做默认值兜底。
        command_review: 可选的命令校验明细（**普通 JSON 对象**：来源父链 + 全部
            ``review`` 命令规则）。仅在提供时作为额外键写入
            :attr:`ApprovalTarget.args`；``reason`` / 指纹 / schema 均不受其影响。
            设计成可选键是为了让「不传明细」的调用方保持既有 ``args`` 形状不变
            ——审批载荷形状是与平台之间的契约。

    Returns:
        True 表示人工审批通过、可继续执行；False 表示拒绝 / 未配置 / 异常。
    """
    if not isinstance(command, str) or not command.strip():
        return False
    approvers = _command_approvers(security_settings)
    if not approvers:
        logger.warning("[CommandApproval] 未配置审批人，fail-closed 拒绝: command=%s", command[:200])
        return False

    approval_cfg = {
        "approvers": approvers,
        "tool_type": "command",
        "tool_name": "execute",
        "tool_code": "execute",
    }
    args: dict[str, Any] = {"command": command, "target_runtime": target_runtime}
    if command_review is not None:
        args["command_review"] = command_review
    target = ApprovalTarget(
        target_type="command",
        target_id=command_fingerprint(command),
        target_name="execute",
        target_code="execute",
        args=args,
        approval=approval_cfg,
    )
    value = {**target.model_dump(by_alias=True), "reason": TOOL_APPROVAL_REASON}
    try:
        decision = interrupt(value)
    except Exception:
        # 无 LangGraph 上下文 / interrupt 本身出错：此时拿不到人工决定，只能拒绝。
        logger.exception("[CommandApproval] interrupt 异常，fail-closed 拒绝: command=%s", command[:200])
        return False
    return _decision_is_approved(decision)
