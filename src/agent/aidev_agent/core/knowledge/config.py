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
from typing import Dict, Optional, Literal

from pydantic import BaseModel, Field


class ProceduralRetrieverSettings(BaseModel):
    """程序记忆配置。"""
    # ============================================================================================
    # 查询类型配置
    # ============================================================================================
    query_type: Literal["platform", "milvus"] = Field(default="platform", description="查询类型: platform(平台知识库) 或 milvus(直接查询milvus)")

    # ============================================================================================
    # 通用配置
    # ============================================================================================
    index_name: str = Field(description="索引名称/向量字段名称")
    # 一个查询表达式，用于过滤标量数据
    # 例如: and(gt("cond", {test1}), gt("cond", {test2}))
    # 如果有需要大模型进行生成的的表达式，没有匹配上的参数，需要大模型进行生成
    # 例如：and(gt("cond", {test1}), {test2}), test2：要求由模型进行编写格式为 gt("cond", {test2})的条件
    scalar_expression: Optional[str] = Field(default=None, description="标量表达式")
    scalar_expression_kwargs: Dict[str, str] = Field(default_factory=dict, description="标量表达式参数的描述")
    topk: int = Field(default=10, description="返回结果数量")
    desc_field_name: str = Field(default="desc", description="描述字段的名称")
    procedure_field_name: str = Field(default="procedure", description="流程字段的名称")

    # ============================================================================================
    # 平台知识库配置
    # ============================================================================================
    knowledge_id: Optional[int] = Field(default=None, description="需要查询的知识ID")
    knowledge_base_id: Optional[int] = Field(default=None, description="需要查询的知识库ID")
