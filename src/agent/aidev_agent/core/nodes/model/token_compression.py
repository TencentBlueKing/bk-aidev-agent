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

Token 压缩中间件

该模块负责：
- Token 超限检测
- 知识库内容压缩（带哈希缓存复用）
- 工具输出压缩（已拆分为两个独立中间件：ToolOutputLengthCompressionMiddleware 和 ToolOutputTokenCompressionMiddleware）
- 聊天历史压缩（渐进式移除最早消息）
"""

from __future__ import annotations

import concurrent.futures
import copy
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from jinja2 import BaseLoader, Template
from jinja2.sandbox import SandboxedEnvironment as Environment
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage

from aidev_agent.core.ag_ui.types import CustomMessageType, InfoMessage
from aidev_agent.packages.langchain_core.retrievers.utils import HUNYUAN_SPECIFIC_RESPONSE
from aidev_agent.packages.langgraph.streaming.utils import conditional_dispatch_custom_event
from aidev_agent.utils.decorator import retry

from .pydantic_models import NextFunction, ProcessorContext

env = Environment(loader=BaseLoader)

logger = logging.getLogger(__name__)

_compression_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("COMPRESSION_EXECUTOR_MAX_WORKERS", "10"))
)


# ============================================================================
# 压缩状态
# ============================================================================
@dataclass
class CompressionState:
    """压缩状态（类型安全）。

    - knowledge_*: 知识库压缩的哈希/缓存/是否已压缩
    - tool_output_*: 工具输出压缩状态
    - chat_history_removed: 聊天历史累计移除条数
    """

    # 知识库压缩状态
    knowledge_hash: Optional[str] = None
    knowledge_cache: Optional[str] = None
    knowledge_compressed: bool = False

    # 工具输出压缩状态
    tool_output_compressed: bool = False
    tool_output_compressed_ids: set = field(default_factory=set)

    # 聊天历史压缩状态
    chat_history_removed: int = 0

    @classmethod
    def from_legacy(cls, raw: Dict[str, Any]) -> "CompressionState":
        """兼容旧版 Dict `_compression_state` 的迁移。"""
        knowledge_compressed = bool(raw.get("knowledge_compressed", raw.get("context_compressed", False)))
        chat_history_removed = int(raw.get("chat_history_removed", raw.get("chat_history_compression_count", 0)) or 0)
        tool_output_compressed = bool(raw.get("tool_output_compressed", False))
        tool_output_compressed_ids = set(raw.get("tool_output_compressed_ids", []))

        return cls(
            knowledge_hash=raw.get("knowledge_hash"),
            knowledge_cache=raw.get("knowledge_cache"),
            knowledge_compressed=knowledge_compressed,
            tool_output_compressed=tool_output_compressed,
            tool_output_compressed_ids=tool_output_compressed_ids,
            chat_history_removed=chat_history_removed,
        )


def _ensure_compression_state(ctx: ProcessorContext) -> CompressionState:
    """确保 ProcessorContext 中存在类型安全的 CompressionState。

    状态来源优先级：
    1) metadata["_compression_state"]
    2) assembly_cache["compression_state"]（用于跨 ReAct 周期持久化）

    同步策略：
    - 始终回写 metadata["_compression_state"]
    - 若存在 assembly_cache（dict），则同时回写 assembly_cache["compression_state"]
    """
    metadata = ctx.metadata
    raw = metadata.get("_compression_state")

    cache = ctx.assembly_cache
    if raw is None and isinstance(cache, dict):
        raw = cache.get("compression_state")

    if isinstance(raw, CompressionState):
        state = raw
    elif isinstance(raw, dict):
        state = CompressionState.from_legacy(raw)
    else:
        state = CompressionState()

    metadata["_compression_state"] = state
    if isinstance(cache, dict):
        cache["compression_state"] = state

    return state


# ============================================================================
# 基类
# ============================================================================
class BaseCompressionMiddleware:
    """压缩中间件基类：提供通用的 token 超限检测与事件发送。

    Args:
        token_limit: Token 限制，超过则触发压缩。如果为 None，则不进行基于 token 的压缩检查。
        token_margin: Token 余量，用于计算实际可用的 token 数量。
    """

    def __init__(
        self,
        *,
        token_limit: Optional[int] = None,
        token_margin: int = 100,
    ) -> None:
        self.token_limit = token_limit
        self.token_margin = token_margin

    @staticmethod
    def _try_get_token_len(ctx: ProcessorContext) -> Optional[int]:
        if ctx.chat_prompt_template is None or ctx.llm is None:
            logger.warning("【BaseCompressionMiddleware】_try_get_token_len 如果想要启用压缩，必须提供模板和llm")
            return None

        try:
            formatted_prompt = ctx.chat_prompt_template._format_prompt_with_error_handling(ctx.variables)
            return ctx.llm.get_num_tokens_from_messages(formatted_prompt.messages)
        except Exception as e:
            logger.warning(f"【BaseCompressionMiddleware】_try_get_token_len 计算 token 长度失败: {e}")
            return None

    def _is_overflow(self, ctx: ProcessorContext) -> bool:
        if self.token_limit is None:
            return False

        token_len = self._try_get_token_len(ctx)
        if token_len is None:
            return False

        return token_len > self.token_limit - self.token_margin

    # -------------------------------------------------------------------------
    # 压缩活动消息辅助方法
    # -------------------------------------------------------------------------
    @staticmethod
    def _estimate_tokens(ctx: ProcessorContext, text: str) -> int:
        """粗略估算文本的 token 数。"""
        if ctx.llm and hasattr(ctx.llm, "get_num_tokens"):
            try:
                return ctx.llm.get_num_tokens(text)
            except Exception:
                pass
        return len(text) // 4

    @staticmethod
    def _record_compression(ctx: ProcessorContext, item_name: str, saved_tokens: int) -> None:
        """记录压缩项到 metadata，供后续聚合推送。"""
        if saved_tokens <= 0:
            return
        items: dict = ctx.metadata.setdefault("_compressed_items", {})
        items[item_name] = items.get(item_name, 0) + saved_tokens

    @staticmethod
    def _dispatch_compress_activity(ctx: ProcessorContext) -> None:
        """聚合推送压缩信息消息（仅在确实发生了压缩时推送）。

        双通道发送：
        1) dispatch CustomEvent(name=info, value={messageId, content})
           → 运行期间实时 SSE 推送给前端，前端据此创建 info 消息占位。
           SSE 流中使用驼峰 messageId，content 为空字符串（前端后续通过 ACTIVITY_SNAPSHOT 更新内容）。
        2) 写入 InfoMessage 到 state["messages"]（id=message_id, content=text）
           → 持久化到会话记录，供下次 SSE 连接的 MESSAGES_SNAPSHOT 重建。
           入库使用蛇形 id 字段，content 为完整压缩摘要文本。
        """
        items: dict = ctx.metadata.pop("_compressed_items", None)
        if not items:
            return
        text = "上下文已自动压缩"
        msg_id = str(uuid.uuid4())

        # 1) 实时推送 CustomEvent（运行期间前端可收到）
        #    SSE 流中使用驼峰 messageId，content 为压缩摘要文本
        conditional_dispatch_custom_event(
            CustomMessageType.INFO.value,
            {"messageId": msg_id, "content": text},
            enable_custom_event=ctx.metadata.get("enable_custom_event", True),
        )

        # 2) 持久化 InfoMessage 到 state（下次连接快照可重建）
        messages: list = ctx.state.get("messages") or []
        messages.append(InfoMessage(message_id=msg_id, content=text))
        ctx.state["messages"] = messages


# ============================================================================
# 知识库压缩器 - Prompt 模板
# ============================================================================
_KNOWLEDGE_COMMON_COMPRESSOR_SYS_PROMPT = (
    "对提供给你的内容进行摘要总结，要求不能丢失关键信息。直接返回你总结后的摘要即可，不要返回其他任何内容！"
)
_KNOWLEDGE_COMMON_COMPRESSOR_USR_PROMPT = env.from_string("提供给你的内容如下：```{{content}}```")

_KNOWLEDGE_SPECIFIC_COMPRESSOR_SYS_PROMPT = """你是一个知识文档相关性判断与摘要生成器。你的任务是判断一个候选知识文档是否能够**部分或全部回答用户最新提问**。

请遵循以下规则：

1. **相关性判断标准**：
   - 只要文档中包含**可用于回答用户最新提问中任何一个子问题或信息点的内容**，无论信息是否完整、是否需要推理、是否隐含在叙述中，都视为"可以回答"。
   - 允许通过**语义理解、常识推断、上下文关联**等方式从文档中提取或推导答案，不要求原文与提问完全一致。

2. **摘要要求**：
   - 仅提取与用户最新提问直接相关的内容。
   - 摘要必须**言简意赅，保留回答所需的关键信息**（如名称、时间、数值、定义、因果关系等）。
   - 避免复制原文大段内容，优先提炼成简洁自然语言。
   - 如果信息分散在多句中，可合并为一句完整摘要。

3. **输出规则**：
   - 如果文档**能提供任何有助于回答提问的信息** → 返回**摘要内容**。
   - 只有当文档**完全不涉及提问主题、或无法从中获取任何可用信息时** → 返回："无效的知识文档"。

4. **特别注意**：
   - 为了让你可以更好地理解用户最新提问，我还会提供给你一段会话历史以供参考，格式如下：[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
     其中"HumanMessage"表示用户历史提问，"AIMessage"表示智能聊天系统的历史回答。
   - 会话历史仅用于帮助理解当前提问的背景和指代，你的判断对象是**用户最新提问**与**候选文档内容**之间的相关性。
   - 知识文档可能是叙述性、多主题或背景性内容，请聚焦其中**与当前问题最相关的片段**。
   - **宁可保留一条模糊但可能相关的信息，也不要轻易判定为"无效"**。

直接返回摘要或"无效的知识文档"，不要输出任何解释、前缀、格式标记或额外说明。"""

_KNOWLEDGE_SPECIFIC_COMPRESSOR_USR_PROMPT = env.from_string(
    "提供给你参考的会话历史内容如下：```{{provided_chat_history}}```"
    "\n\n\n给你的候选文档如下：```{{candidate_context}}```"
    "\n\n\n用户最新提问如下：```{{query}}```"
)


# ============================================================================
# 知识库压缩器
# ============================================================================
class KnowledgeCompressor:
    """知识库内容压缩器。

    提供并发压缩知识库内容的能力，可作为 KnowledgeCompressionMiddleware 的 knowledge_compressor_func 使用。

    Args:
        llm: 用于压缩的 LLM 实例
        compressor_type: 压缩模式，"specific"（带上下文）或 "common"（简单总结），默认为 "specific"
        common_sys_prompt: common 模式的系统提示词，默认使用内置模板
        common_usr_prompt: common 模式的用户提示词模板（Jinja2），需包含 {{content}} 变量
        specific_sys_prompt: specific 模式的系统提示词，默认使用内置模板
        specific_usr_prompt: specific 模式的用户提示词模板（Jinja2），需包含 {{provided_chat_history}}、{{query}}、{{candidate_context}} 变量
    """

    def __init__(
        self,
        llm: Any,
        *,
        compressor_type: str = "specific",
        common_sys_prompt: Optional[str] = None,
        common_usr_prompt: Optional[Template] = None,
        specific_sys_prompt: Optional[str] = None,
        specific_usr_prompt: Optional[Template] = None,
    ) -> None:
        self.llm = llm
        self.compressor_type = compressor_type
        self.common_sys_prompt = common_sys_prompt or _KNOWLEDGE_COMMON_COMPRESSOR_SYS_PROMPT
        self.common_usr_prompt = common_usr_prompt or _KNOWLEDGE_COMMON_COMPRESSOR_USR_PROMPT
        self.specific_sys_prompt = specific_sys_prompt or _KNOWLEDGE_SPECIFIC_COMPRESSOR_SYS_PROMPT
        self.specific_usr_prompt = specific_usr_prompt or _KNOWLEDGE_SPECIFIC_COMPRESSOR_USR_PROMPT

    def llm_context_compressor(
        self,
        provided_chat_history: list,
        query: str,
        candidate_context: Any,
    ) -> str:
        """压缩单个知识库内容。"""
        if self.compressor_type == "common":
            sys_prompt = self.common_sys_prompt
            usr_prompt = self.common_usr_prompt.render(content=candidate_context)
        elif self.compressor_type == "specific":
            sys_prompt = self.specific_sys_prompt
            usr_prompt = self.specific_usr_prompt.render(
                provided_chat_history=provided_chat_history,
                query=query,
                candidate_context=candidate_context,
            )
        else:
            raise ValueError(f"不支持的知识库知识压缩方式：{self.compressor_type}")

        messages: List[BaseMessage] = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]

        resp = self.llm.invoke(messages)
        resp_content = resp.content

        # 如果触发了混元的特殊回复，则不进行压缩
        if resp_content == HUNYUAN_SPECIFIC_RESPONSE:
            resp_content = candidate_context

        return resp_content

    def __call__(
        self,
        provided_chat_history: list,
        query: str,
        context: List[Any],
    ) -> List[Any]:
        """并发压缩知识库内容。

        Args:
            provided_chat_history: 聊天历史
            query: 用户查询
            context: 待压缩的知识库内容列表

        Returns:
            压缩后的内容列表
        """
        if not isinstance(context, list):
            raise TypeError(f"context 必须是列表类型，但收到了 {type(context).__name__}")

        if not context:
            return context

        try:
            futures = [
                _compression_executor.submit(
                    self.llm_context_compressor,
                    provided_chat_history,
                    query,
                    candidate_context,
                )
                for candidate_context in context
            ]
            results = [future.result() for future in futures]
        except Exception:
            # 如果 LLM 调用失败则不进行总结
            results = context
            logger.warning("调用 LLM 来对知识库内容进行压缩总结时失败，因此不进行总结！")

        return results


# ============================================================================
# 知识库内容压缩中间件
# ============================================================================
class KnowledgeCompressionMiddleware(BaseCompressionMiddleware):
    """知识库内容压缩中间件：通过内容哈希缓存复用，避免重复压缩。

    Args:
        knowledge_compressor_func: 知识库压缩函数，签名为 Callable[[list, str, Any], Any]
            - 参数1: provided_chat_history - 聊天历史
            - 参数2: query - 用户查询
            - 参数3: context - 待压缩的知识库内容
            - 返回: 压缩后的内容
        token_limit: Token 限制，超过则触发压缩
        token_margin: Token 余量
    """

    def __init__(
        self,
        *,
        knowledge_compressor_func: Optional[Callable[[list, str, Any], Any]] = None,
        token_limit: Optional[int] = None,
        token_margin: int = 100,
    ) -> None:
        super().__init__(token_limit=token_limit, token_margin=token_margin)
        self.knowledge_compressor_func = knowledge_compressor_func

    @staticmethod
    def _compute_hash(content: Any) -> str:
        if content is None:
            return ""
        if not isinstance(content, str):
            content = repr(content)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        logger.debug("KnowledgeCompressionMiddleware Start")
        # 检查是否存在 context
        if not ("context" in ctx.variables and ctx.variables.get("context")):
            logger.debug("KnowledgeCompressionMiddleware 当前不存在 context 无需压缩")
            next()
            return
        # 获取 缓存的 state
        state = _ensure_compression_state(ctx)
        # 内容变更检测：一旦变更，清理旧缓存。
        cur_hash = self._compute_hash(ctx.variables.get("context"))
        if cur_hash and cur_hash != state.knowledge_hash:
            state.knowledge_hash = cur_hash
            state.knowledge_cache = None
            state.knowledge_compressed = False
        # 已压缩且命中缓存：后续 ReAct 循环直接复用缓存。
        if state.knowledge_compressed and state.knowledge_cache and cur_hash == state.knowledge_hash:
            ctx.variables["context"] = state.knowledge_cache
            next()
            return
        # 检查是否超限
        if not self._is_overflow(ctx):
            next()
            return
        # 检查是否有知识库压缩函数
        if not self.knowledge_compressor_func:
            logger.warning("KnowledgeCompressionMiddleware, 未提供压缩函数，跳过知识库内容压缩")
            next()
            return
        # 执行压缩流程
        provided_chat_history = ctx.metadata.get("provided_chat_history", [])
        logger.info("=====>Token 超限，尝试压缩知识库知识内容以减少 token 使用")
        original_tokens = self._estimate_tokens(ctx, str(ctx.variables["context"]))
        compressed_context = self.knowledge_compressor_func(
            provided_chat_history,
            ctx.variables.get("query", ""),
            ctx.variables["context"],
        )
        compressed_tokens = self._estimate_tokens(ctx, str(compressed_context))
        self._record_compression(ctx, "知识库", original_tokens - compressed_tokens)
        state.knowledge_cache = compressed_context
        state.knowledge_compressed = True
        ctx.variables["context"] = compressed_context
        next()


# ============================================================================
# 工具输出压缩 - Prompt 模板
# ============================================================================
_TOOL_OUTPUT_COMMON_COMPRESSOR_SYS_PROMPT = (
    "对提供给你的内容进行摘要总结，要求不能丢失关键信息。直接返回你总结后的摘要即可，不要返回其他任何内容！"
)
_TOOL_OUTPUT_COMMON_COMPRESSOR_USR_PROMPT = env.from_string("提供给你的内容如下：```{{content}}```")

_TOOL_OUTPUT_SPECIFIC_COMPRESSOR_SYS_PROMPT = env.from_string(
    """
你是一个工具调用结果相关性判断与摘要生成器。你的任务是判断 {{candidate_tool_name}} 工具的调用结果是否能够**部分或全部回答用户最新提问**。

请遵循以下规则：

1. **相关性判断标准**：
   - 只要工具结果中包含**可用于回答用户最新提问中任何一个子问题或信息点的内容**，无论信息是否完整、是否需要推理、是否隐藏在结构化数据中，都视为"可以回答"。
   - 允许通过**语义推断、数值计算、上下文关联或常识理解**从工具结果中得出答案，不要求原文与提问完全一致。

2. **摘要要求**：
   - 仅提取与用户最新提问直接相关的内容。
   - 摘要必须**言简意赅，保留回答所需的关键信息**（如数值、名称、时间、状态、因果关系等）。
   - 避免复制大段原始数据，优先提炼成自然语言短句。

3. **输出规则**：
   - 如果工具结果**能提供任何有助于回答提问的信息** → 返回**摘要**。
   - 只有当工具结果**完全不包含任何相关信息、或信息完全无法用于回答提问时** → 返回："无效的工具调用"。

4. **特别注意**：
   - 为了让你可以更好地理解用户最新提问，我还会提供给你一段会话历史以供参考，格式如下：[HumanMessage(content='xxx'), AIMessage(content='xxx'), ...]
     其中"HumanMessage"表示用户历史提问，"AIMessage"表示智能聊天系统的历史回答。
   - 会话历史仅用于帮助理解当前提问的上下文，你的判断对象是**用户最新提问**与**工具调用结果**之间的相关性。
   - 工具结果可能包含冗余、噪声或结构化字段（如JSON日志、API响应），请聚焦其中**潜在有用的部分**。
   - **宁可保留一条模糊但可能相关的信息，也不要轻易判定为"无效"**。

直接返回摘要内容或"无效的工具调用"，不要输出任何解释、前缀、格式标记或额外说明。
"""
)

_TOOL_OUTPUT_SPECIFIC_COMPRESSOR_USR_PROMPT = env.from_string(
    "提供给你参考的会话历史内容如下：```{{provided_chat_history}}```"
    "\n\n\n给你的 {{candidate_tool_name}} 工具的调用结果如下：```{{candidate_tool_result}}```"
    "\n\n\n用户最新提问如下：```{{query}}```"
)


# ============================================================================
# 工具输出压缩器
# ============================================================================
class ToolOutputCompressor:
    """工具输出压缩器。

    提供并发压缩工具输出的能力，可作为 ToolOutputCompressionMiddleware 的 tool_output_compressor_func 使用。

    Args:
        llm: 用于压缩的 LLM 实例
        compressor_type: 压缩模式，"specific"（带上下文）或 "common"（简单总结），默认为 "specific"
        common_sys_prompt: common 模式的系统提示词，默认使用内置模板
        common_usr_prompt: common 模式的用户提示词模板（Jinja2），需包含 {{content}} 变量
        specific_sys_prompt: specific 模式的系统提示词模板（Jinja2），需包含 {{candidate_tool_name}} 变量
        specific_usr_prompt: specific 模式的用户提示词模板（Jinja2），需包含 {{provided_chat_history}}、{{query}}、{{candidate_tool_name}}、{{candidate_tool_result}} 变量
    """

    def __init__(
        self,
        llm: Any,
        *,
        compressor_type: str = "specific",
        common_sys_prompt: Optional[str] = None,
        common_usr_prompt: Optional[Template] = None,
        specific_sys_prompt: Optional[Template] = None,
        specific_usr_prompt: Optional[Template] = None,
    ) -> None:
        self.llm = llm
        self.compressor_type = compressor_type
        # common_sys_prompt 是字符串类型
        self.common_sys_prompt = (
            common_sys_prompt if common_sys_prompt is not None else _TOOL_OUTPUT_COMMON_COMPRESSOR_SYS_PROMPT
        )
        # 其他是 Template 类型
        self.common_usr_prompt = (
            common_usr_prompt if common_usr_prompt is not None else _TOOL_OUTPUT_COMMON_COMPRESSOR_USR_PROMPT
        )
        self.specific_sys_prompt = (
            specific_sys_prompt if specific_sys_prompt is not None else _TOOL_OUTPUT_SPECIFIC_COMPRESSOR_SYS_PROMPT
        )
        self.specific_usr_prompt = (
            specific_usr_prompt if specific_usr_prompt is not None else _TOOL_OUTPUT_SPECIFIC_COMPRESSOR_USR_PROMPT
        )

    @retry(max_retries=5, max_seconds=3600)
    def llm_intermediate_step_compressor(
        self,
        provided_chat_history: Any,
        query: str,
        tool_name: str,
        tool_result: Any,
    ) -> str:
        """压缩单个工具的输出（保持与旧版本方法名一致）。"""
        tool_result_str = tool_result if isinstance(tool_result, str) else str(tool_result)

        if self.compressor_type == "common":
            sys_prompt = self.common_sys_prompt
            usr_prompt = self.common_usr_prompt.render(content=tool_result_str)
        elif self.compressor_type == "specific":
            sys_prompt = self.specific_sys_prompt.render(candidate_tool_name=tool_name)
            usr_prompt = self.specific_usr_prompt.render(
                provided_chat_history=provided_chat_history,
                query=query,
                candidate_tool_name=tool_name,
                candidate_tool_result=tool_result_str,
            )
        else:
            raise ValueError(f"不支持的工具调用结果压缩方式：{self.compressor_type}")

        messages: List[BaseMessage] = [
            SystemMessage(content=sys_prompt),
            HumanMessage(content=usr_prompt),
        ]

        resp = self.llm.invoke(messages)
        resp_content = resp.content

        # 如果触发了混元的特殊回复，则不进行压缩
        if resp_content == HUNYUAN_SPECIFIC_RESPONSE:
            logger.debug(f"工具 {tool_name} 触发混元特殊回复，不压缩")
            return tool_result_str

        logger.debug(f"工具 {tool_name} 压缩完成: {len(tool_result_str)} -> {len(resp_content)}")
        return resp_content

    def llm_intermediate_step_compressor_parallel(
        self,
        provided_chat_history: Any,
        query: str,
        tool_msg_positions: List[Tuple[int, ToolMessage]],
    ) -> List[Optional[str]]:
        """并发执行工具输出压缩（保持与旧版本方法名一致）。

        Args:
            provided_chat_history: 聊天历史
            query: 用户查询
            tool_msg_positions: ToolMessage 的索引位置

        Returns:
            压缩结果列表，与 tool_msg_positions 一一对应，失败的位置为 None
        """
        # 并发压缩
        futures = {
            _compression_executor.submit(
                self.llm_intermediate_step_compressor,
                provided_chat_history,
                query,
                (tool_msg.name or "unknown"),
                tool_msg.content,
            ): idx
            for idx, (_, tool_msg) in enumerate(tool_msg_positions)
        }

        results: List[Optional[str]] = [None] * len(tool_msg_positions)
        try:
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.warning(
                        f"调用 LLM 来对工具调用结果进行压缩总结时，LLM 调用失败，索引 {idx}，错误：{e}。因此该内容不进行总结。"
                    )
        except Exception as e:
            logger.warning(f"调用 LLM 来对工具调用结果进行压缩总结时，LLM 调用失败，错误：{e}。因此不进行总结。")

        return results

    def __call__(
        self,
        provided_chat_history: Any,
        query: str,
        tool_msg_positions: List[Tuple[int, ToolMessage]],
    ) -> List[Optional[str]]:
        """并发压缩工具输出（可作为 tool_output_compressor_func 使用）。

        Args:
            provided_chat_history: 聊天历史
            query: 用户查询
            tool_msg_positions: ToolMessage 的索引位置

        Returns:
            压缩结果列表，与 tool_msg_positions 一一对应，失败的位置为 None
        """
        return self.llm_intermediate_step_compressor_parallel(
            provided_chat_history=provided_chat_history,
            query=query,
            tool_msg_positions=tool_msg_positions,
        )


# ============================================================================
# 工具输出压缩中间件基类
# ============================================================================
class BaseToolOutputCompressionMiddleware(BaseCompressionMiddleware):
    """工具输出压缩中间件基类：提供共享的辅助方法和核心压缩逻辑。

    Args:
        tool_output_compressor_func: 工具输出压缩函数
        token_limit: Token 限制，超过则触发压缩
        token_margin: Token 余量

    需要在 ctx.metadata 中提供:
    - tool_messages: list[BaseMessage] - 工具消息列表
    - provided_chat_history: list - 用于压缩的聊天历史
    """

    def __init__(
        self,
        *,
        tool_output_compressor_func: Optional[
            Callable[[Any, str, List[Tuple[int, ToolMessage]]], List[Optional[str]]]
        ] = None,
        token_limit: Optional[int] = None,
        token_margin: int = 100,
    ) -> None:
        super().__init__(token_limit=token_limit, token_margin=token_margin)
        self.tool_output_compressor_func = tool_output_compressor_func

    # -------------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------------
    @staticmethod
    def _get_query(ctx: ProcessorContext) -> str:
        """获取用户 query。"""
        query = ctx.variables.get("query")
        if isinstance(query, str) and query:
            return query

        chat_history = ctx.metadata.get("chat_history")
        if isinstance(chat_history, list) and chat_history:
            last = chat_history[-1]
            content = getattr(last, "content", "")
            return content if isinstance(content, str) else str(content)

        raw = ctx.state.get("input", "")
        return raw if isinstance(raw, str) else str(raw)

    @staticmethod
    def _get_tool_messages(ctx: ProcessorContext) -> Optional[List[BaseMessage]]:
        """获取 tool_messages。"""
        tool_messages = ctx.metadata.get("tool_messages")
        if isinstance(tool_messages, list) and tool_messages:
            return tool_messages
        return None

    @staticmethod
    def _tool_output_len(tool_messages: List[BaseMessage]) -> int:
        """计算工具输出的总字符长度。"""
        parts: List[str] = []
        for m in tool_messages:
            if isinstance(m, ToolMessage):
                content = m.content
                if content is not None:
                    parts.append(content if isinstance(content, str) else str(content))
        return len("".join(parts))

    @staticmethod
    def _collect_tool_msg_positions(
        tool_messages: List[BaseMessage],
    ) -> List[Tuple[int, ToolMessage]]:
        """收集 ToolMessage 的索引位置。"""
        positions: List[Tuple[int, ToolMessage]] = []
        for idx, m in enumerate(tool_messages):
            if isinstance(m, ToolMessage):
                positions.append((idx, m))
        return positions

    # -------------------------------------------------------------------------
    # 核心压缩逻辑
    # -------------------------------------------------------------------------
    def _compress_with_deduplication(
        self,
        ctx: ProcessorContext,
        tool_messages: List[BaseMessage],
        tool_msg_positions: List[Tuple[int, ToolMessage]],
        state: CompressionState,
    ) -> bool:
        """带去重的工具输出压缩（避免重复压缩已处理过的工具输出）。

        Args:
            ctx: 处理器上下文
            tool_messages: 工具消息列表
            tool_msg_positions: ToolMessage 的索引位置
            state: 压缩状态

        Returns:
            是否执行了压缩
        """
        # 检查是否有压缩函数
        if not self.tool_output_compressor_func:
            logger.warning("BaseToolOutputCompressionMiddleware, 未提供压缩函数，跳过工具输出压缩")
            return False

        # 过滤出尚未压缩的 ToolMessage
        uncompressed_positions: List[Tuple[int, ToolMessage]] = []
        for pos, tool_msg in tool_msg_positions:
            tool_call_id = tool_msg.tool_call_id
            if tool_call_id and tool_call_id in state.tool_output_compressed_ids:
                continue  # 已压缩过，跳过
            uncompressed_positions.append((pos, tool_msg))

        if not uncompressed_positions:
            logger.debug("所有工具输出已压缩，跳过")
            return False

        provided_chat_history = ctx.metadata.get("provided_chat_history", [])
        query = self._get_query(ctx)

        # 估算压缩前的 token 数
        original_tokens = sum(self._estimate_tokens(ctx, str(tm.content)) for _, tm in uncompressed_positions)

        # 调用压缩函数
        results = self.tool_output_compressor_func(
            provided_chat_history,
            query,
            uncompressed_positions,
        )

        # 以新的 ToolMessage 列表回写，避免修改原始 state.messages
        new_tool_messages: List[BaseMessage] = list(tool_messages)
        compressed_tokens = 0
        for i, (pos, tool_msg) in enumerate(uncompressed_positions):
            compressed = results[i]
            if compressed is None:
                compressed_tokens += self._estimate_tokens(ctx, str(tool_msg.content))
                continue

            # 使用 copy 保留原 ToolMessage 的其他属性（如 additional_kwargs、artifact 等）
            new_tool_msg = copy.copy(tool_msg)
            new_tool_msg.content = compressed
            new_tool_messages[pos] = new_tool_msg
            compressed_tokens += self._estimate_tokens(ctx, compressed)

            # 记录已压缩的 tool_call_id
            if tool_msg.tool_call_id:
                state.tool_output_compressed_ids.add(tool_msg.tool_call_id)

        self._record_compression(ctx, "工具结果", original_tokens - compressed_tokens)
        ctx.metadata["tool_messages"] = new_tool_messages
        state.tool_output_compressed = True

        return True


# ============================================================================
# 工具输出长度压缩中间件（基于字符长度阈值）
# ============================================================================
class ToolOutputLengthCompressionMiddleware(BaseToolOutputCompressionMiddleware):
    """工具输出长度压缩中间件：当工具输出总字符长度超过阈值时触发压缩。

    参数说明：
    - tool_output_compress_thrd: 工具输出字符长度阈值，超过则触发压缩
    - tool_output_compressor_func: 工具输出压缩函数
    """

    def __init__(
        self,
        *,
        tool_output_compress_thrd: int = 5000,
        tool_output_compressor_func: Optional[
            Callable[[Any, str, List[Tuple[int, ToolMessage]]], List[Optional[str]]]
        ] = None,
    ) -> None:
        super().__init__(tool_output_compressor_func=tool_output_compressor_func)
        self.tool_output_compress_thrd = tool_output_compress_thrd

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        """中间件入口：基于字符长度的压缩。"""
        logger.debug("ToolOutputLengthCompressionMiddleware __call__")

        tool_messages = self._get_tool_messages(ctx)
        if tool_messages and self._tool_output_len(tool_messages) > self.tool_output_compress_thrd:
            logger.debug(
                f"ToolOutputLengthCompressionMiddleware, {self._tool_output_len(tool_messages)}, {self.tool_output_compress_thrd}"
            )
            tool_msg_positions = self._collect_tool_msg_positions(tool_messages)
            if tool_msg_positions:
                state = _ensure_compression_state(ctx)
                self._compress_with_deduplication(
                    ctx,
                    tool_messages,
                    tool_msg_positions,
                    state,
                )
                logger.info("=====>工具调用结果过长，尝试压缩工具调用结果以减少 token 使用。")
        next()


# ============================================================================
# 工具输出 Token 压缩中间件（基于 Token 超限）
# ============================================================================
class ToolOutputTokenCompressionMiddleware(BaseToolOutputCompressionMiddleware):
    """工具输出 Token 压缩中间件：当 Token 超限时触发压缩。

    参数说明：
    - tool_output_compressor_func: 工具输出压缩函数
    - token_limit: Token 限制，超过则触发压缩
    - token_margin: Token 余量
    """

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        """中间件入口：基于 Token 超限的压缩。"""
        logger.debug("ToolOutputTokenCompressionMiddleware __call__")

        if not self._is_overflow(ctx):
            next()
            return

        tool_messages = self._get_tool_messages(ctx)
        if not tool_messages:
            next()
            return

        tool_msg_positions = self._collect_tool_msg_positions(tool_messages)
        if not tool_msg_positions:
            next()
            return

        state = _ensure_compression_state(ctx)

        # 如果所有工具输出都已压缩过，不重复压缩
        all_compressed = all(
            (tool_msg.tool_call_id and tool_msg.tool_call_id in state.tool_output_compressed_ids)
            for _, tool_msg in tool_msg_positions
        )
        if all_compressed:
            next()
            return

        self._compress_with_deduplication(
            ctx,
            tool_messages,
            tool_msg_positions,
            state,
        )

        next()


# ============================================================================
# 聊天历史压缩
# ============================================================================
class ChatHistoryCompressionMiddleware(BaseCompressionMiddleware):
    """聊天历史压缩中间件：累积移除并渐进式执行，不修改原始 state.messages。

    Args:
        token_limit: Token 限制，超过则触发压缩
        token_margin: Token 余量
    """

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        try:
            chat_history = ctx.variables.get("chat_history")
            if not isinstance(chat_history, list) or not chat_history:
                logger.warning("ChatHistoryCompressionMiddleware 当前没有聊天历史")
                next()
                return

            state = _ensure_compression_state(ctx)
            # 先应用历史累计移除量（确保跨 ReAct 循环可复用）
            removed = max(0, int(state.chat_history_removed or 0))
            chat_history = list(chat_history)[removed:] if removed else list(chat_history)
            ctx.variables["chat_history"] = chat_history

            if not self._is_overflow(ctx):
                next()
                return

            original_tokens = sum(self._estimate_tokens(ctx, str(getattr(msg, "content", ""))) for msg in chat_history)

            while chat_history and self._is_overflow(ctx):
                chat_history.pop(0)
                state.chat_history_removed += 1
            ctx.variables["chat_history"] = chat_history

            compressed_tokens = sum(
                self._estimate_tokens(ctx, str(getattr(msg, "content", ""))) for msg in chat_history
            )
            self._record_compression(ctx, "历史对话", original_tokens - compressed_tokens)

            if self._is_overflow(ctx):
                logger.warning(
                    f"已尝试抛除会话历史，但仍然超过 token 限制。（限制: {self.token_limit}，余量: {self.token_margin}）"
                )
                err_msg = (
                    "已尝试按优先级压缩上下文，但仍然超过 token 限制，无法回答问题，请尝试其他 LLM。"
                    f"（当前 token 数为: {self._try_get_token_len(ctx)}，支持的 token 数为: {self.token_limit}，设置的 token limit margin 为: {self.token_margin},）"
                )
                raise RuntimeError(err_msg)

            next()
        finally:
            # ChatHistoryCompressionMiddleware 是压缩链最后一个中间件，
            # 在所有出口点聚合推送压缩活动消息（含异常路径）。
            self._dispatch_compress_activity(ctx)
