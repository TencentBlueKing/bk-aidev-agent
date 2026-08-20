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

def remove_thinking_process(resp_content):
    if resp_content.startswith("<think>\n") and "\n</think>\n\n" in resp_content:
        return resp_content.split("\n</think>\n\n")[-1]
    return resp_content


def is_deepseek_r1_series_models(llm):
    return "deepseek-r1" in llm.model_name


def is_model_without_function_calling(llm):
    return "deepseek-r1" in llm.model_name or "qwq" in llm.model_name or "qwen3-nothinking" in llm.model_name


def support_multimodal(llm):
    return "deepseek" not in llm.model_name
