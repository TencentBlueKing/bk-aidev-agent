# -*- coding: utf-8 -*-
"""aidev_agent.packages.security.command.command_risk_assessor

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

命令风险评估器（review 智能预分流核心）。

当 ``command_review_disposition="approval"``（命令落入 review 需人工审批）且
``enable_command_review_auto`` 开启时，用辅助 LLM 对「灰名单命令」做三级预分流，
以**减少人工审批量**，返回与 ``command_review_disposition`` **同一套处置词汇**：

- ``allow`` —— 明显安全、无副作用（ls / cat / echo 等），自动放行，跳过处置档；
- ``block`` —— 明显危险（破坏数据 / 外泄 / 提权 / SSRF / 远程执行管道），直接拒绝；
- ``approval`` —— 无法确定，落回 ``command_review_disposition`` 处置档（``approval`` 时升级 ITSM 人工审批）。

设计原则：

- **fail-closed**：LLM 未注入 / 非字符串命令 / 调用异常 / 输出非法，一律回退
  ``approval``，绝不因评估能力缺失而自动放行；
- **外置**：本模块只依赖标准库 / pydantic，不依赖 ``core`` / ``services`` / ``api``，
  与 ``core.tools.runtime_tools`` 的命令允许列表、review 处置共同构成命令执行安全三层。

公开接口：
- CommandRiskAssessor: 风险评估器（构造时注入辅助 LLM）
- RiskAssessment: 结构化评估结果（disposition + reason）
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)

RiskDisposition = Literal["allow", "approval", "block"]

_RISK_PROMPT = (
    "你是命令安全风险评估器，判断以下 shell 命令的处置方式。\n"
    "只输出 JSON，字段：disposition（取 allow/approval/block）、reason（简短中文说明）。\n"
    "分级标准：\n"
    "- allow：明显安全、无副作用（ls、cat、echo、pwd、简单文件读取等）。\n"
    "- block：明显危险（破坏数据、外泄敏感信息、提权、SSRF、远程执行管道等）。\n"
    "- approval：无法确定或需人工判断（新工具、复杂脚本、生产环境操作等）。\n\n"
    "命令（已脱敏）：\n{command}"
)


class RiskAssessment(BaseModel):
    """命令风险评估结果。"""

    disposition: RiskDisposition
    reason: str = ""


class CommandRiskAssessor:
    """命令风险评估器（review 智能预分流）。

    Args:
        llm: 辅助 LLM（建议轻量 / fast 模型）。None 时评估能力缺失，
            ``assess`` 一律返回 ``approval``（fail-closed）。
    """

    def __init__(self, llm: Any = None) -> None:
        self._llm = llm

    def assess(self, command: Any) -> str:
        """评估单条命令的处置方式，返回 ``allow`` / ``approval`` / ``block``。

        fail-closed：非字符串命令、LLM 未注入、调用异常、输出非法，一律返回
        ``approval``（升级人工审批），绝不自动放行。
        """
        if not isinstance(command, str) or not command.strip():
            return "approval"
        if self._llm is None:
            return "approval"
        try:
            disposition = self._invoke_llm(command)
        except Exception:
            logger.exception("[CommandRiskAssessor] 风险评估失败，fail-closed 回退 approval")
            return "approval"
        return disposition if disposition in ("allow", "approval", "block") else "approval"

    def _invoke_llm(self, command: str) -> str:
        """调用辅助 LLM，优先 structured output，失败回退文本 + JSON 解析。"""
        prompt = _RISK_PROMPT.format(command=command)
        try:
            llm = self._llm.with_structured_output(RiskAssessment)
            result = llm.invoke(prompt)
        except (AttributeError, NotImplementedError, TypeError):
            # 模型不支持 structured output：回退普通 invoke + JSON 解析
            result = self._llm.invoke(prompt)
            return self._parse_text_result(result)
        if isinstance(result, RiskAssessment):
            return result.disposition
        return self._parse_text_result(result)

    @staticmethod
    def _parse_text_result(result: Any) -> str:
        """从普通 LLM 输出（AIMessage / str）中提取 ``disposition`` 字段。"""
        content = getattr(result, "content", result)
        if isinstance(content, str):
            try:
                data = json.loads(content)
                if isinstance(data, dict):
                    return str(data.get("disposition", "approval"))
            except (ValueError, TypeError):
                return "approval"
        return "approval"
