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

import logging

from langchain_core.messages import HumanMessage, SystemMessage

from aidev_agent.config import settings
from aidev_agent.core.extend.models.llm_gateway import ChatModel

logger = logging.getLogger(__name__)

HUNYUAN_SPECIFIC_RESPONSE = "很抱歉，我还未学习到如何回答这个问题的内容，暂时无法提供相关信息。"


def deduplicate_tools(candidate_tools):
    return list({tool.name: tool for tool in candidate_tools}.values())


def remove_thinking_process(resp_content):
    if resp_content.startswith("<think>\n") and "\n</think>\n\n" in resp_content:
        return resp_content.split("\n</think>\n\n")[-1]
    return resp_content


def is_deepseek_r1_series_models(llm):
    return "deepseek-r1" in llm.model_name


def is_model_without_function_calling(llm):
    return (
        "deepseek-r1" in llm.model_name
        or "qwq" in llm.model_name
        or "qwen3-nothinking" in llm.model_name
        or "gptoss-120b" in llm.model_name
    )


def support_multimodal(llm):
    return "deepseek" not in llm.model_name


def query_clarification_enabled(llm, kwargs):
    # 如果用户配置了，则按照用户的配置
    if "enable_query_clarification" in kwargs:
        return kwargs["enable_query_clarification"]
    # 在用户没有配置的情况下，默认只有在使用强模型的情况下，才开启 query 澄清的可能。
    # 其他模型由于指令遵循能力弱，为防止什么问题都进行 query 澄清，先不开启使用这种 prompt。
    return llm.model_name == "gpt-4o" or "deepseek" in llm.model_name or "qwq" in llm.model_name


def invoke_decorator(invoke_func, llm):
    def wrapper(*args, **kwargs):
        # 根据 https://huggingface.co/deepseek-ai/DeepSeek-R1#usage-recommendations 的建议：
        # Avoid adding a system prompt; all instructions should be contained within the user prompt.
        # NOTE: 目前假设只有第 1 个 message 才可能是 SystemMessage
        if global_llm_model_name := settings.INTENT_RECOGNITION_GLOBAL_LLM_MODEL_NAME:
            global_llm = ChatModel.get_setup_instance(
                model=global_llm_model_name,
                streaming=True,
            )
            invoke_func_to_use = global_llm.invoke
            llm = global_llm
        else:
            invoke_func_to_use = invoke_func

        if (
            is_deepseek_r1_series_models(llm)
            and isinstance(args[0][0], SystemMessage)
            and isinstance(args[0][-1], HumanMessage)
        ):
            args[0][-1] = HumanMessage(content=f"{args[0][0].content}\n\n{args[0][-1].content}")
            del args[0][0]

        result = invoke_func_to_use(*args)
        if kwargs.get("llm_input_output"):
            kwargs["llm_input_output"][llm.model_name]["input"].append(args[0])
            kwargs["llm_input_output"][llm.model_name]["output"].append(result.content)
        if is_deepseek_r1_series_models(llm):
            # deepseek-r1 系列模型会有 think 过程，在使用结果的时候需要去除
            result.content = remove_thinking_process(result.content)
            result.content = result.content.strip()
        return result

    return wrapper


FINAL_ANSWER_PREFIXES = [
    '```\n{\n  "action": "Final Answer",\n  "action_input": "',
    '```json\n{\n  "action": "Final Answer",\n  "action_input": "',
    """```\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    """```json\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    '```json\\n\\n{\n  \\"action\\": \\"Final Answer\\",\n  \\"action_input\\": \\"',
    """```json\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    # 匹配 "action_input" 的值为 {...} 的情况，例如用户问“用json格式给我输出不同排序算法的对比”
    """```json\n{\n  "action": "Final Answer",\n  "action_input": """,
    '{\n  "action": "Final Answer",\n  "action_input": "',
]

FINAL_ANSWER_SUFFIXES = [
    '"\n}\n```',
    '"\n}\n```',
    """\"\n}\n```""",
    """\"\n}\n```""",
    '\\"\n}\\n\\n```',
    """\"\n}\n```""",
    "\n}\n```",
    '"\n}',
]
