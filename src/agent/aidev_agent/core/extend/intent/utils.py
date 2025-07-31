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
import time
import traceback
from functools import wraps

from langchain_core.callbacks.manager import dispatch_custom_event
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage

from aidev_agent.config import settings
from aidev_agent.core.extend.models.llm_gateway import ChatModel

logger = logging.getLogger(__name__)

HUNYUAN_SPECIFIC_RESPONSE = "很抱歉，我还未学习到如何回答这个问题的内容，暂时无法提供相关信息。"


def is_structured_data(doc):
    structured_data_file_types = ["csv", "xlsx"]
    if isinstance(doc, Document):
        if not hasattr(doc, "metadata"):
            raise RuntimeError(f"召回的文档没有metadata属性！\n文档格式为 Document\n文档内容为：{doc}\n")
        return "file_type" in doc.metadata and doc.metadata["file_type"] in structured_data_file_types
    elif isinstance(doc, dict):
        if "metadata" not in doc:
            raise RuntimeError(f"召回的文档没有metadata属性！\n文档格式为 dict\n文档内容为：{doc}\n")
        return "file_type" in doc["metadata"] and doc["metadata"]["file_type"] in structured_data_file_types
    else:
        raise RuntimeError(f"不支持的文档格式！\n文档内容为：{doc}\n")


def timeit(message=""):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not kwargs.pop("disable_timeit", False):
                st_time = time.time()
                result = func(*args, **kwargs)
                elapsed_time = time.time() - st_time
                logger.info(f"=====> {message}耗时 ({func.__name__}): {elapsed_time:.2f}s")
                return result
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


def retry(max_retries=5, max_seconds=1800):
    def _retry(func):
        def wrapper(*args, **kwargs):
            try_cnt = 0
            start_time = time.time()
            while try_cnt < max_retries and (time.time() - start_time) < max_seconds:
                try:
                    try_cnt += 1
                    return func(*args, **kwargs)
                except Exception:  # noqa: PERF203
                    logger.info(
                        f"\n\n=====\n>>>>> 执行出错，重试中。当前尝试次数: {try_cnt}。"
                        f"详细错误情况：\n{traceback.format_exc()}\n=====\n\n"
                    )
                    if try_cnt >= max_retries or (time.time() - start_time) >= max_seconds:
                        # 如果达到最大重试次数或者超过最大时间限制，最后一次重试的异常将被抛出。
                        # 这样可以确保在所有重试都失败的情况下，异常会被正确地抛出并处理。
                        raise
                    continue

        return wrapper

    return _retry


def deduplicate_tools(candidate_tools):
    return list({tool.name: tool for tool in candidate_tools}.values())


def deduplicate_knowledge_chunks(knowledge_chunks):
    return list({item["metadata"]["uid"]: item for item in knowledge_chunks}.values())


def deduplicate_knowledge_file_paths(knowledge_chunks):
    """按照 file path 进行去重，且只保留 metadata，且按照 fine grained score 进行降序排序"""
    unique_items = list(
        {item["metadata"]["file_path"]: {"metadata": item["metadata"]} for item in knowledge_chunks}.values()
    )
    return sorted(unique_items, key=lambda x: x["metadata"]["fine_grained_score"], reverse=True)


def conditional_dispatch_custom_event(name, data, **kwargs):
    if kwargs.get("enable_custom_event", True):
        dispatch_custom_event(name, data)


def filter_and_select_topk(items, score_threshold, topk):
    if score_threshold:
        filtered_items = [
            item for item in items if item.get("metadata", {}).get("fine_grained_score", 0) >= score_threshold
        ]
    else:
        filtered_items = items
    sorted_items = sorted(filtered_items, key=lambda x: x["metadata"]["fine_grained_score"], reverse=True)
    return sorted_items[:topk]


def remove_thinking_process(resp_content):
    if resp_content.startswith("<think>\n") and "\n</think>\n\n" in resp_content:
        return resp_content.split("\n</think>\n\n")[-1]
    return resp_content


def is_deepseek_r1_series_models(llm):
    return "deepseek-r1" in llm.model_name or "qwq" in llm.model_name or "qwen3-nothinking" in llm.model_name


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
]

FINAL_ANSWER_SUFFIXES = [
    '"\n}\n```',
    '"\n}\n```',
    """\"\n}\n```""",
    """\"\n}\n```""",
    '\\"\n}\\n\\n```',
    """\"\n}\n```""",
    "\n}\n```",
]
