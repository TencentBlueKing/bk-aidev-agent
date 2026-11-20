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

hook 协议词汇表：6 个点位、处理器上下文与两个控制流异常。

处理器作者只需要读这一个模块就能拿到全部契约类型；点位入口见 ``runner``。
payload 直接是 LangGraph / LangChain 原生对象，不做二次封装：

- ``turn_start`` / ``model_pre``：``list[BaseMessage]``
- ``model_post``：``AIMessage``（可能带 ``tool_calls``）
- ``tool_pre``：``ToolCallRequest``
- ``tool_post``：``ToolMessage``
- ``turn_end``：``None``（本轮正常走到终点；中断与异常的轮次不会触发）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aidev_agent.exceptions import AgentException

__all__ = [
    "HookAbort",
    "HookContext",
    "HookIdentity",
    "HookPoint",
    "HookRetry",
]


class HookPoint(str, Enum):
    """6 个 hook 点位；取值即点位名，不得改名。"""

    TURN_START = "turn_start"
    MODEL_PRE = "model_pre"
    MODEL_POST = "model_post"
    TOOL_PRE = "tool_pre"
    TOOL_POST = "tool_post"
    TURN_END = "turn_end"


@dataclass(frozen=True)
class HookIdentity:
    """处理器可见的只读运行标识；由执行器从 ``RunnableConfig`` 解析。"""

    agent_code: str = ""
    session_code: str = ""
    turn_id: str = ""


@dataclass(frozen=True)
class HookContext:
    """传给处理器的唯一入参；``payload`` 承载原生对象（见模块注释）。"""

    point: HookPoint
    identity: HookIdentity = field(default_factory=HookIdentity)
    payload: Any = None


class HookAbort(AgentException):
    """处理器主动终止本次运行；由 ``runner`` 原样抛出，不做 fail-open。"""

    def __init__(self, point: HookPoint, reason: str = ""):
        self.point = point
        self.reason = reason
        super().__init__(message=f"hook abort at {point.value}: {reason}")


class HookRetry(AgentException):
    """``model_post`` 要求重新调用模型；模型链捕获后转为可重试异常。"""

    def __init__(self, reason: str = ""):
        self.reason = reason
        super().__init__(message=f"hook retry at model_post: {reason}")
