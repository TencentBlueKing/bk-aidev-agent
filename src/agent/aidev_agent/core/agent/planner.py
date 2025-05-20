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
"""

from abc import ABC, ABCMeta, abstractmethod
from typing import Any, List, Tuple, Union

from asgiref.sync import sync_to_async
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import Callbacks


class AgentPlanner(metaclass=ABCMeta):
    @abstractmethod
    def plan(
        self,
        intermediate_steps: List[Tuple["AgentAction", str]],
        callbacks: "Callbacks" = None,
        **kwargs: Any,
    ) -> Union["AgentAction", "AgentFinish", None]:
        pass


class ToolControlSupportPlanner(AgentPlanner):
    def __init__(
        self,
        suggested_continue_message="当前工具无法解决用户问题，请继续使用其他合适的工具，或者按照你的理解回答该问题。",
    ):
        self.suggested_continue_message = suggested_continue_message

    def plan(
        self,
        intermediate_steps: List[Tuple["AgentAction", str]],
        callbacks: "Callbacks" = None,
        **kwargs: Any,
    ) -> Union["AgentAction", "AgentFinish", None]:
        last_step = None
        if len(intermediate_steps) >= 1:
            last_step = intermediate_steps[-1]
        if last_step:
            if isinstance(last_step[1], AgentFinish):
                return AgentFinish(return_values={"output": last_step[1].return_values["output"]}, log="")
            if isinstance(last_step[1], AgentAction) and last_step[1].tool == "continue":
                intermediate_steps[-1] = (last_step[0], last_step[1].log or self.suggested_continue_message)
        return None


class CustomPlanMixIn(ABC):
    def plan(
        self,
        intermediate_steps: List[Tuple[AgentAction, str]],
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> Union[AgentAction, AgentFinish]:
        custom_ret = self.custom_plan(intermediate_steps, callbacks, **kwargs)
        if custom_ret:
            if isinstance(custom_ret, AgentAction) and custom_ret.tool == "modify_plan_context":
                kwargs["modified_plan_context"] = custom_ret.tool_input
            else:
                return custom_ret
        return super().plan(intermediate_steps, callbacks, **kwargs)

    async def aplan(
        self,
        intermediate_steps: List[Tuple[AgentAction, str]],
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> Union[AgentAction, AgentFinish]:
        custom_ret = await sync_to_async(self.custom_plan)(intermediate_steps, callbacks, **kwargs)
        if custom_ret:
            if isinstance(custom_ret, AgentAction) and custom_ret.tool == "modify_plan_context":
                kwargs["modified_plan_context"] = custom_ret.tool_input
            else:
                return custom_ret
        return await super().aplan(intermediate_steps, callbacks, **kwargs)

    @abstractmethod
    def custom_plan(
        self,
        intermediate_steps: List[Tuple[AgentAction, str]],
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> Union[AgentAction, AgentFinish, None]:
        pass
