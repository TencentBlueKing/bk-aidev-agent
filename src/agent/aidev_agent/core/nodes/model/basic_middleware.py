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

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytz
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai.chat_models.base import _convert_dict_to_message, _convert_message_to_dict

from aidev_agent.core.ag_ui.types import ActivityMessage, InfoMessage
from aidev_agent.enums import ContextType
from aidev_agent.packages.langchain_core.models.utils import is_deepseek_r1_series_models
from aidev_agent.packages.langchain_core.tools.render import render_text_description_and_args

from .pydantic_models import DEFAULT_ENABLE_PARALLEL_TOOL_CALLS, NextFunction, ProcessorContext

logger = logging.getLogger(__name__)


# =============================================================================
# Default prompt prefix
# =============================================================================

# NOTE: Keep content aligned with graphs/react/prompts.py::MULTI_MODAL_PREFIX.
DEFAULT_MULTI_MODAL_PREFIX = """You are a professional assistant, 
respond to the human as helpfully,accurately,concisely as possible.

User who you are serving, already upload some documents and images already. 
The uploaded file list are:
```
{files_list}.
```

The documents also already split and store into a knowledgebase. 
An knowledgebase retriever is used to retrieve the document parts in natural language query.

If the theme what user talk about is closely related to the document type file name, follow the principles below:

- If the file type you care about is documents, no tool is specified to retrieve,
 use knowledgebase retriever to get the similar content.
- If the file type you care about is documents, and required to get the full documents,
 use `get_extracted_documents_content` to get the content directly, use file size to generate right page_size
- When using knowledgebase retriever, limit the search to a specific file name unless the user specifies otherwise.

If the theme what user talk about is closely related to the uploaded images, or user ask questions intermediately after upload images
never forget to use `add_image_to_chat_context` tool to add images content to chat context, 
if you already added same image before, never add it again.
Only use `add_image_to_chat_context` tool to get information from image files.

!!! If you are generating some python code, and you need to `import` some module in that code, 
MAKE SURE to use this format `globals()['module'] = __import__('module')` instead of `import module`. !!!

Follow the common principles below:

- If you can't get the information you need using tools, simply say you can't complete the requirement.
 if you already get the information you need using the tools, return Final Answer as soon as possible.
- When you plan to answer the question, 
 check whether the theme what user talk about is closely related with the document type file name first, 
 ONLY if closely related, use tools to get the content, 
 OTHERWISE never to get the content or use other tools or provide the answer directly. 
- Make sure the language of the Final Answer is Chinese.
- !!! The information what you get may be irrelevant to the the requirements, remove them in Final Answer, 
    or just say I dont't know NEVER return irrelevant information in Final Answer.!!! 
- !!! Never use same tool with same parameters multi times continuously. !!!
- If you got error from tools, try to fix it based on the error, but don't retry too much times (at most 2 times).
- !!! You MUST offer the error info if tool's error can not be handled !!!"""


# =============================================================================
# Helper Functions (from variables.py)
# =============================================================================


def get_beijing_now() -> str:
    """获取北京时间的格式化字符串。"""

    utc_now = datetime.now(pytz.utc)
    beijing_now = utc_now.astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y年%m月%d日 %H时%M分%S秒")
    return beijing_now


def beijing_to_timestamp(beijing_now):
    """将北京时间字符串转换为时间戳"""
    standard_format_str = (
        beijing_now.replace(" ", "")
        .replace("年", "-")
        .replace("月", "-")
        .replace("日", " ")
        .replace("时", ":")
        .replace("分", ":")
        .replace("秒", "")
    )
    timestamp = int(
        datetime.strptime(standard_format_str.strip(), "%Y-%m-%d %H:%M:%S")
        .replace(tzinfo=timezone(timedelta(hours=8)))
        .astimezone(timezone.utc)
        .timestamp()
    )
    return timestamp


def get_context_type_from_state(state: Dict[str, Any]) -> str:
    knowledge_content = state.get("knowledge_content")
    knowledge_qa_content = state.get("knowledge_qa_content")

    if knowledge_content and knowledge_qa_content:
        return ContextType.BOTH.value
    elif knowledge_content:
        return ContextType.PRIVATE.value
    elif knowledge_qa_content:
        return ContextType.QA_RESPONSE.value
    return ""


def extract_tool_calls_from_messages(tool_messages: List[BaseMessage]) -> str:
    """将 AIMessage.tool_calls + ToolMessage 结果拼接为 structured agent_scratchpad 字符串。"""

    if not tool_messages:
        return ""

    tool_results: Dict[str, ToolMessage] = {}
    for msg in tool_messages:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = msg

    parts: list[str] = []
    for msg in tool_messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tool_call in msg.tool_calls:
                tool_name = tool_call.get("name", "")
                tool_input = tool_call.get("args", {})
                tool_call_id = tool_call.get("id", "")

                observation = ""
                if tool_call_id and tool_call_id in tool_results:
                    observation = tool_results[tool_call_id].content

                tried_tool = json.dumps({"action": tool_name, "action_input": tool_input}, ensure_ascii=False)
                parts.append(f"\n已经调用过的工具：\n{tried_tool}")
                parts.append(f"\n观察结果：{observation}\n")

    return "".join(parts)


# =============================================================================
# Template Pipeline
# =============================================================================
#
# Template assembly is now handled via:
# - `ProcessorContext.prompt_slots` (slots)
# - atomic middlewares in `prompt_middleware.py`
# - `ContextAssembly._assemble_template` (final assembly)
#
# =============================================================================


# =============================================================================
# Tools Middleware
# =============================================================================


class BaseToolsMiddleware:
    """确保 ctx.tools 有默认值。

    主要用于向后兼容：历史上 tools pipeline 可能依赖该中间件初始化 tools。
    当前 ContextAssembly.get_choice_tools 已会预先设置 ctx.tools。
    """

    def __init__(self, tools: Optional[List[BaseTool]] = None):
        self._tools = tools

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        if self._tools is not None:
            ctx.tools = list(self._tools)
        next()


# =============================================================================
# Variables Middleware (from variables.py)
# =============================================================================


class BaseVariablesMiddleware:
    """从 state 提取基础变量，并做消息拆分（支持缓存优化）。

    缓存策略：只缓存 last_human_idx，不缓存消息列表本身。
    通过切片 messages[:idx+1] 和 messages[idx+1:] 获取结果。
    """

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        if ctx.chat_prompt_template is None:
            next()
            return

        # 自动提取模板所需变量
        auto_vars: Dict[str, Any] = {}
        for var in ctx.chat_prompt_template.input_variables:
            if var in ctx.state:
                auto_vars[var] = ctx.state[var]

        messages: List[BaseMessage] = ctx.state.get("messages") or []
        messages = [each for each in messages if not isinstance(each, (ActivityMessage, InfoMessage))]
        cache = ctx.assembly_cache

        # 尝试使用缓存的 last_human_idx
        if isinstance(cache, dict) and self._is_cache_valid(cache, messages):
            last_human_idx = cache["last_human_idx"]
        else:
            last_human_idx = self._find_last_human_idx(messages)
            if isinstance(cache, dict):
                cache["messages_id"] = id(messages)
                cache["last_human_idx"] = last_human_idx

        # 基于 last_human_idx 切分消息
        if last_human_idx == -1:
            chat_history, tool_messages = [], list(messages)
        else:
            chat_history = list(messages[: last_human_idx + 1])
            tool_messages = list(messages[last_human_idx + 1 :])

        ctx.variables = {**ctx.variables, **auto_vars}
        ctx.metadata["chat_history"] = chat_history
        ctx.metadata["tool_messages"] = tool_messages

        next()

    @staticmethod
    def _find_last_human_idx(messages: List[BaseMessage]) -> int:
        """从尾部查找最后一条 HumanMessage/SystemMessage 的索引。"""
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], (HumanMessage, SystemMessage)):
                return i
        return -1

    @staticmethod
    def _is_cache_valid(cache: Dict[str, Any], messages: List[BaseMessage]) -> bool:
        """检查缓存是否有效：同一 messages 对象且最后一条消息不是 Human/System。"""
        if cache.get("messages_id") != id(messages):
            return False
        if not messages:
            return True
        # 只要最后一条消息不是 HumanMessage/SystemMessage，last_human_idx 就不会变
        return not isinstance(messages[-1], (HumanMessage, SystemMessage))


class SpecialVariablesMiddleware:
    """构建特殊变量（beijing_now/context_type/context 等）。

    beijing_now 和 timestamp 会缓存在 assembly_cache 中，同一轮对话内保持不变，
    从而避免每次 ReAct 循环都重新生成时间字符串破坏 prompt cache。
    超过 BEIJING_NOW_TTL_SECONDS 秒后自动刷新。
    """

    # 北京时间缓存超时时间（秒），同一轮对话内 beijing_now 在此时间内保持不变
    BEIJING_NOW_TTL_SECONDS: int = 3600

    def __init__(
        self,
        *,
        use_structured_response: bool,
        use_general_knowledge_on_miss: bool,
        rejection_message: str,
        enable_parallel_tool_calls: bool = DEFAULT_ENABLE_PARALLEL_TOOL_CALLS,
    ):
        self.use_structured_response = use_structured_response
        self.use_general_knowledge_on_miss = use_general_knowledge_on_miss
        self.rejection_message = rejection_message
        self.enable_parallel_tool_calls = enable_parallel_tool_calls

    def _get_beijing_now_cached(self, cache: Optional[Dict[str, Any]]) -> tuple[str, int]:
        """从 assembly_cache 获取缓存的 beijing_now / timestamp，超时则刷新。"""
        if isinstance(cache, dict):
            cached_timestamp = cache.get("_beijing_timestamp")
            if cached_timestamp and time.time() - cached_timestamp < self.BEIJING_NOW_TTL_SECONDS:
                beijing_str = cache.get("_beijing_now")
                if beijing_str:
                    return beijing_str, cached_timestamp

        now_str = get_beijing_now()
        now_ts = beijing_to_timestamp(now_str)

        if isinstance(cache, dict):
            cache["_beijing_now"] = now_str
            cache["_beijing_timestamp"] = now_ts

        return now_str, now_ts

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        chat_history: List[BaseMessage] = ctx.metadata.get("chat_history", [])
        tool_messages: List[BaseMessage] = ctx.metadata.get("tool_messages", [])
        history_messages = chat_history[:-1]
        history_system_prompt = "\n\n".join(
            str(msg.content)
            for msg in history_messages
            if isinstance(msg, SystemMessage) and isinstance(msg.content, str) and msg.content.strip()
        )
        history_non_system_messages = [msg for msg in history_messages if not isinstance(msg, SystemMessage)]

        if self.use_structured_response:
            agent_scratchpad: Any = extract_tool_calls_from_messages(tool_messages)
        else:
            agent_scratchpad = tool_messages

        beijing_now, timestamp = self._get_beijing_now_cached(ctx.assembly_cache)

        special_vars = {
            "beijing_now": beijing_now,
            "timestamp": timestamp,
            "context_type": get_context_type_from_state(ctx.state),
            "context": ctx.state.get("knowledge_content"),
            "qa_context": ctx.state.get("knowledge_qa_content"),
            "query": chat_history[-1].content if chat_history else "",
            "use_general_knowledge_on_miss": self.use_general_knowledge_on_miss,
            "has_tools": bool(ctx.tools),
            "chat_history": history_non_system_messages,
            "history_system_prompt": history_system_prompt,
            "rejection_response": self.rejection_message,
            "agent_scratchpad": agent_scratchpad,
            "enable_parallel_tool_calls": self.enable_parallel_tool_calls,
        }
        if self.use_structured_response:
            special_vars = {
                **special_vars,
                "tools": render_text_description_and_args(list(ctx.tools)),
                "tool_names": ",".join([t.name for t in ctx.tools]),
            }
        ctx.variables = {**ctx.variables, **special_vars}
        next()


class SpecialVariablesPostMiddleware:
    """在工具压缩后执行的变量渲染中间件，只重新渲染agent_scratchpad变量"""

    def __init__(
        self,
        *,
        use_structured_response: bool,
    ):
        self.use_structured_response = use_structured_response

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        tool_messages: List[BaseMessage] = ctx.metadata.get("tool_messages", [])
        # 只重新渲染agent_scratchpad变量
        if self.use_structured_response:
            agent_scratchpad: Any = extract_tool_calls_from_messages(tool_messages)
        else:
            agent_scratchpad = tool_messages

        ctx.variables["agent_scratchpad"] = agent_scratchpad
        next()


class DeepSeekR1VariablesMiddleware:
    """DeepSeek-R1：避免使用 system prompt（将 SystemMessage 视为 user）。"""

    def __init__(self, use_deepseek_r1_models_process: bool = True):
        self.use_deepseek_r1_models_process = use_deepseek_r1_models_process

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        llm = ctx.llm
        if llm is None or not self.use_deepseek_r1_models_process:
            next()
            return
        is_r1 = is_deepseek_r1_series_models(llm)
        if not is_r1:
            next()
            return
        chat_history = ctx.variables.get("chat_history")
        if isinstance(chat_history, list):
            for i in range(len(chat_history)):
                if isinstance(chat_history[i], SystemMessage):
                    msg = _convert_message_to_dict(chat_history[i])
                    msg["role"] = "user"
                    chat_history[i] = _convert_dict_to_message(msg)
            history_system_prompt = ctx.variables.get("history_system_prompt")
            if isinstance(history_system_prompt, str) and history_system_prompt.strip():
                chat_history.insert(0, HumanMessage(content=history_system_prompt))
                ctx.variables["history_system_prompt"] = ""
        next()
