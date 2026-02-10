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

from aidev_agent.packages.langchain_core.output_parsers.structured_output_parser import (
    ACTION_INPUT_ERR_MSG,
    FINAL_ANSWER_PREFIXES,
    FINAL_ANSWER_SUFFIXES,
    OUTPUT_PARSER_ERR_MSG,
    StructuredOutputToToolMessageParser,
    is_deepseek_r1_series_models,
    remove_thinking_process,
)

__all__ = [
    "StructuredOutputToToolMessageParser",
    # 工具函数（从 langchain_classic 移植）
    "remove_thinking_process",
    "is_deepseek_r1_series_models",
    # 常量
    "OUTPUT_PARSER_ERR_MSG",
    "ACTION_INPUT_ERR_MSG",
    "FINAL_ANSWER_PREFIXES",
    "FINAL_ANSWER_SUFFIXES",
]
