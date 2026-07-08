# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging
from typing import List

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from aidev_agent.core.nodes.interrupt.strategy import InterruptionStrategy

logger = logging.getLogger(__name__)


def make_interrupt_node(strategies: List[InterruptionStrategy]):
    """创建中断检查节点函数（策略模式，单方法协议 D-02）。

    在 model 节点之后、tools 节点之前检查各策略是否需要中断。
    D-04 统一前置检查（无 messages / 无 tool_calls → ``Command(goto="end")``），
    随后按顺序调用 ``strategy.interrupt(state, config)``：None 继续下一个，
    Command 短路返回。所有策略返回 None → ``Command(goto="pv_node")``。

    不直接调 ``dispatch`` 自定义事件或 LangGraph ``interrupt()`` ——
    中断逻辑封装在各策略的 ``interrupt`` 方法内（D-03 单方法协议）。

    Args:
        strategies: 中断策略列表，按顺序短路执行。
    """

    def _check(state: dict, config: RunnableConfig) -> Command:
        # D-04 统一前置检查
        messages = state.get("messages", [])
        if not messages:
            return Command(goto="end")

        last_message = messages[-1]
        if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
            return Command(goto="end")

        # D-03 顺序调用策略，None 继续下一个，Command 短路返回
        for strategy in strategies:
            result = strategy.interrupt(state, config)
            if result is not None:
                return result

        # 所有策略无中断，执行工具
        return Command(goto="pv_node")

    return _check
