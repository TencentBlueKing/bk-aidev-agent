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

from logging import getLogger

IMAGE_SUFFIXES = ("jpg", "jpeg", "png", "gif", "webp")
_textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})

logger = getLogger(__name__)
OUTPUT_PARSER_ERR_MSG = "无法从 LLM 输出内容中解析出要求的 JSON BLOB，本次工具调用或结论解析失败。"
ACTION_INPUT_ERR_MSG = """要求LLM返回的 $JSON_BLOB 中的 $TOOL_INPUT 务必是个字典，
即务必同时指定参数名和参数值，而不要只指定参数值。但是LLM却只指定了其参数值，而没有指定参数名！工具调用失败！"""
