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

import json
from typing import Any, Sequence

import langchain_core.agents
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
)


def _convert_agent_observation_to_messages(
    agent_action: langchain_core.agents.AgentAction, observation: Any
) -> Sequence[BaseMessage]:
    """
    补丁改进：
    针对非 agents.AgentActionMessageLog 的分支，如果 observation 不是 str 类型，则进行特殊处理，防止报以下错误：
    ```
    ValidationError: 2 validation errors for HumanMessage
    content
      str type expected (type=type_error.str)
    content
      value is not a valid list (type=type_error.list)
    ```
    """
    if isinstance(agent_action, langchain_core.agents.AgentActionMessageLog):
        return [langchain_core.agents._create_function_message(agent_action, observation)]
    else:
        if isinstance(observation, str):
            content = observation
        else:
            try:
                content = json.dumps(observation, ensure_ascii=False)
            except Exception:
                content = str(observation)
        return [HumanMessage(content=content)]


def apply_patches():
    langchain_core.agents._convert_agent_observation_to_messages = _convert_agent_observation_to_messages
