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
from enum import Enum
from typing import Optional, List, Any

from pydantic import BaseModel, Field


# ================================================================================================
# 以下内容是对标 BK_AI 平台的知识库查询接口
# ================================================================================================
class IndexType(str, Enum):
    """索引类型枚举"""
    VECTOR_FULL_TEXT = "vector-full_text"
    VECTOR_MULTI_COLUMN = "vector-multi_column"


class Operator(str, Enum):
    """操作符枚举。"""
    AND = "and"
    OR = "or"
    NOT = "not"


class Comparator(str, Enum):
    """比较操作符枚举。"""
    EQ = "eq"      # 等于
    NE = "ne"      # 不等于
    GT = "gt"      # 大于
    GTE = "gte"    # 大于等于
    LT = "lt"      # 小于
    LTE = "lte"    # 小于等于
    CONTAIN = "contain"  # 包含子串
    LIKE = "like"        # 模糊匹配
    IN = "in"            # 包含于
    NIN = "nin"          # 不包含于


class ScalarFilter(BaseModel):
    """标量过滤器"""
    expression: str = Field(description="表达式")


class VectorFilter(BaseModel):
    """向量过滤器配置。"""
    index_name: str = Field(description="索引名称")
    index_value: str = Field(description="索引值")
    index_type: Optional[str] = Field(description="索引类型", default=IndexType.VECTOR_MULTI_COLUMN)
    knowledge_id: Optional[int] = Field(description="知识ID", default=None)
    knowledge_base_id: Optional[int] = Field(description="知识库ID", default=None)
    topk: Optional[int] = Field(description="前多少个")
    scalar: Optional[ScalarFilter] = Field(description="标量过滤")


class Filter(BaseModel):
    """过滤器"""
    vector: List[VectorFilter] = Field(description="向量过滤")
    scalar: List[Any] = Field(default_factory=list, description="标量过滤器列表，始终为空列表")
