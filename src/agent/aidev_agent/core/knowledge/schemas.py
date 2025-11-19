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
from typing import Any

from langchain_core.documents import Document
from pydantic import Field


class ProceduralDocument(Document):
    """程序记忆数据模型
    程序记忆是Agent对执行流程、操作步骤及行为规则的存储，本质是“知道怎么做”
    包括以下两种：
        1. 内隐在 LLM 参数中的记忆
        2. 提供给大模型的指导性的 prompt 或者 一个固定的流程

    本处主要描述了大模型的指导性的 prompt
    可用于：
    1. Skill 动态装载提示词
    """
    desc: str = Field(default="", description="描述了该程序记忆的适用场景")
    procedure: str = Field(default="", description="存储了执行流程、操作步骤及行为规则，用于指导 Agent 应该怎么做")

    def __init__(self, page_content: str, desc: str, procedure: str, **kwargs: Any) -> None:
        super().__init__(page_content=page_content, desc=desc, procedure=procedure, **kwargs)
