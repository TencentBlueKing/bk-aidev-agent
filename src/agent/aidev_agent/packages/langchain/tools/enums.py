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


class FieldType(Enum):
    """字段类型"""

    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    NUMBER = "number"
    OBJECT = "object"
    ARRAY = "array"


class FuncType(Enum):
    MAX_LENGTH = "max-length"
    MIN_LENGTH = "min-length"
    REGEXP = "regexp"
