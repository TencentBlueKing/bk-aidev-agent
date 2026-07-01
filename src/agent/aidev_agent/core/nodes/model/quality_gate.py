# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueIDev) available.
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

import enum
import logging

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, SystemMessage

from aidev_agent.packages.langgraph.streaming.utils import conditional_dispatch_custom_event

from .pydantic_models import (
    ProcessorContext,
    RecoveryNudgeError,
    RecoveryPrefillError,
    RecoveryRetryError,
    TruncationError,
)
from .utils import (
    detect_thinking_exhaustion,
    extract_text_from_content,
    has_content_after_think_block,
    has_inline_thinking,
    has_prior_tool_results,
    is_truncated,
    strip_think_blocks,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 质量门禁常量
# ---------------------------------------------------------------------------

RECOVERY_NUDGE_PROMPT = (
    "You just executed tool calls but returned an empty response. "
    "Please process the tool results above and continue with the task."
)

TRUNCATION_CONTINUE_PROMPT = (
    "Your previous response was truncated. Continue exactly where you left off. Do not restart or repeat prior text."
)

THINKING_EXHAUSTED_MESSAGE = (
    "Model used all output tokens on reasoning with none left for the response. "
    "Try increasing max_tokens or lowering reasoning effort."
)


# ---------------------------------------------------------------------------
# 响应路由枚举
# ---------------------------------------------------------------------------


class ResponseRoute(enum.Enum):
    """模型响应质量评估后的路由决策。

    每个枚举成员表示一条明确的后继处理路径，供恢复循环使用。
    """

    # 正常路径
    NORMAL_COMPLETION = "normal_completion"  # 有内容，无工具调用 → 结束对话
    TOOL_EXECUTION = "tool_execution"  # 有工具调用 → 进入工具执行

    # 恢复路径
    RECOVERY_NUDGE = "recovery_nudge"  # 工具后空响应 → 发送提示
    RECOVERY_PREFILL = "recovery_prefill"  # 仅思考响应 → 追加 prefill
    RECOVERY_TRUNCATION = "recovery_truncation"  # 截断响应 → 继续生成
    RECOVERY_RETRY = "recovery_retry"  # 空内容 → 简单重试


# ---------------------------------------------------------------------------
# 质量门禁（可子类化以定制判断逻辑）
# ---------------------------------------------------------------------------


class QualityGate:
    """模型响应质量门禁。

    评估模型响应并决定后续路由（正常完成 / 工具执行 / 各种恢复路径）。
    作为可调用对象（``__call__``）接入 model_chain LCEL 管道。

    可子类化以定制任务完成度判断逻辑——重写以下方法/属性即可，无需重写
    整个路由/恢复流程：

    - ``judgment_sys_prompt``：判断系统提示词
    - ``_judge_task_completion``：调用判断 LLM 评估完成度
    - ``_judge_response_completion``：提取输入/输出并调用判断
    - ``_extract_last_human_input``：提取最后一条用户输入
    """

    # 判断系统提示词——类属性，子类可重写
    judgment_sys_prompt: str = """你是一个任务完成度判断器。我会给你以下信息：
1. 用户的最后一条输入
2. 智能助手的最后一条输出

你需要判断智能助手的输出是否实际完成了用户输入中要求的任务，以便于放行用户继续提问
完成任务的情况如下：
1. 输出详细的报告，回答了用户的问题，或者完成了用户的任务
2. 要求用户补充相关信息，澄清问题等回复
3. 明确指出不能完成用户任务，例如：根据已有知识不能回答问题
4. 其他你认为完成任务了的情况

判断规则：
- 如果助手的输出明确回答了用户的问题或完成了用户要求的任务，判断为"已完成"
- 如果助手的输出明显未完成用户任务（如答非所问、拒绝回答、输出不完整、仅重复用户输入等），判断为"未完成"
- 如果无法确定助手是否完成了任务，判断为"不确定"

请只返回以下三个词中的一个，不要返回任何其他内容：
- 已完成
- 未完成
- 不确定"""

    def __init__(
        self,
        *,
        judge_llm: BaseChatModel | None = None,
        enable_judgment_llm: bool = True,
    ) -> None:
        """初始化质量门禁。

        Args:
            judge_llm: 判断用 LLM 实例。构造一次并复用（避免每次响应重建）。
                为 None 时 fail-open（跳过判断，视为已完成）。
            enable_judgment_llm: 是否在内容响应上调用判断 LLM。关闭后
                ``has_content`` 分支直接返回 ``NORMAL_COMPLETION``，省去
                每次正常响应的额外 LLM 调用。
        """
        self.judge_llm = judge_llm
        self.enable_judgment_llm = enable_judgment_llm

    # ------------------------------------------------------------------
    # 任务完成度判断（SRE3-6-35B-A3B-nothinking judge，fail-open 语义）
    # ------------------------------------------------------------------

    def _extract_last_human_input(self, messages: list[BaseMessage]) -> str | None:
        """从消息列表中逆向提取最后一条 HumanMessage 的文本。"""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return extract_text_from_content(msg.content)
        return None

    def _judge_task_completion(
        self,
        judgment_llm,
        last_user_input: str,
        last_model_output: str,
        *,
        enable_custom_event: bool = True,
    ) -> bool:
        """调用判断模型评估任务是否完成。fail-open：无法确定未完成则返回 True。

        Args:
            judgment_llm: 用于判断的 LLM 实例
            last_user_input: 最后一条用户输入文本
            last_model_output: 最后一条模型输出文本（已剔除 think 块）
            enable_custom_event: 是否派发 custom_event（用于 SSE 流期间
                切换 ``front_end_display``，避免判断 LLM 的流式输出写入 DB
                或显示给前端）。

        Returns:
            True 表示任务已完成（或无法确定未完成），False 表示明确未完成
        """
        if not judgment_llm or not last_user_input or not last_model_output:
            return True  # fail-open

        usr_prompt = (
            f"用户最后一条输入：\n```\n{last_user_input}\n```\n\n"
            f"智能助手最后一条输出：\n```\n{last_model_output}\n```\n\n"
            f"请判断智能助手是否完成了用户的任务。"
        )
        messages = [
            SystemMessage(content=self.judgment_sys_prompt),
            HumanMessage(content=usr_prompt),
        ]
        # 判断 LLM 调用期间关闭前端显示/DB 写入，避免判断输出污染会话流。
        # 使用 try/finally 确保异常路径下也恢复 front_end_display=True。
        conditional_dispatch_custom_event(
            "custom_event",
            {"front_end_display": False},
            enable_custom_event=enable_custom_event,
        )
        try:
            resp = judgment_llm.invoke(messages)
            result = (resp.content or "").strip()
            # fail-open：只有明确"未完成"才返回 False
            return "未完成" not in result
        except Exception:
            logger.warning("judgment LLM call failed, fail-open", exc_info=True)
            return True
        finally:
            conditional_dispatch_custom_event(
                "custom_event",
                {"front_end_display": True},
                enable_custom_event=enable_custom_event,
            )

    def _judge_response_completion(
        self,
        response: AnyMessage,
        working_messages: list[BaseMessage],
        *,
        enable_custom_event: bool = True,
    ) -> bool:
        """提取最后用户输入和模型输出，调用判断 LLM。fail-open 语义。

        Args:
            enable_custom_event: 是否派发 custom_event（透传给 _judge_task_completion）。

        Returns:
            True 表示任务已完成（或无法确定未完成），False 表示明确未完成
        """
        if self.judge_llm is None:
            return True  # fail-open：未配置判断 LLM，跳过判断
        last_user_input = self._extract_last_human_input(working_messages)
        last_model_output = extract_text_from_content(response.content)
        if last_model_output:
            last_model_output = strip_think_blocks(last_model_output)
        return self._judge_task_completion(
            self.judge_llm,
            last_user_input,
            last_model_output,
            enable_custom_event=enable_custom_event,
        )

    # ------------------------------------------------------------------
    # 响应校验
    # ------------------------------------------------------------------

    def validate_response(self, ctx: ProcessorContext) -> ResponseRoute:
        """评估模型响应质量并确定后继路由。

        返回一个 ``ResponseRoute`` 枚举成员，表示模型节点应采取的下一步操作。

        路由决策顺序（由高到低优先级）：
        1. 有工具调用 → TOOL_EXECUTION
        2. 有有效内容 → NORMAL_COMPLETION（若启用判断 LLM，需先通过完成度判断）
        3. 工具后空响应 → RECOVERY_NUDGE
        4. 仅思考响应 → RECOVERY_PREFILL
        5. 截断响应 → RECOVERY_TRUNCATION
        6. 空内容 → RECOVERY_RETRY
        7. 恢复选项耗尽 → NORMAL_COMPLETION
        """
        response = ctx.response
        recovery = ctx.model_chain_state
        working_messages = ctx.messages

        # 1. 截断的工具调用 → 需要重建 chain 并重试。
        #    必须在通用 tool_calls 检查之前处理，否则截断的工具调用会被误判为正常工具执行。
        if (
            response.tool_calls
            and is_truncated(response)
            and recovery.truncated_tool_call_retries < recovery.max_truncated_tool_call_retries
        ):
            logger.info(
                "Recovery: truncated tool call (retry %d/%d)",
                recovery.truncated_tool_call_retries + 1,
                recovery.max_truncated_tool_call_retries,
            )
            return ResponseRoute.RECOVERY_TRUNCATION

        # 2. 有工具调用 → 正常工具执行路径。
        if response.tool_calls:
            return ResponseRoute.TOOL_EXECUTION

        # 3. 有有效内容 → 正常完成。
        #    参照 hermes-agent 的 map_finish_reason(None) → "stop" 行为：
        #    如果模型输出有 content 但没有 finish_reason，仍然视为正常完成。
        content = response.content or ""
        has_content = (isinstance(content, str) and has_content_after_think_block(content)) or (
            isinstance(content, list) and len(content) > 0
        )
        if has_content:
            if self.enable_judgment_llm and not self._judge_response_completion(
                response,
                working_messages,
                enable_custom_event=ctx.metadata.get("enable_custom_event", True),
            ):
                return ResponseRoute.RECOVERY_RETRY
            return ResponseRoute.NORMAL_COMPLETION

        # 从这里开始：消息没有可用内容。

        # 4. 工具后提示。
        if (
            has_prior_tool_results(working_messages)
            and not recovery.post_tool_empty_retried
            and not (isinstance(content, str) and has_inline_thinking(content))
        ):
            logger.info("Recovery: post-tool empty response, sending nudge")
            return ResponseRoute.RECOVERY_NUDGE

        # 5. 仅思考：有推理内容但无文本输出。
        has_reasoning = bool(getattr(response, "reasoning_content", None))
        if (
            has_reasoning
            or (
                isinstance(content, str) and has_inline_thinking(content) and not has_content_after_think_block(content)
            )
        ) and recovery.thinking_prefill_retries < recovery.max_thinking_prefill_retries:
            logger.info(
                "Recovery: thinking-only response (prefill retry %d/%d)",
                recovery.thinking_prefill_retries + 1,
                recovery.max_thinking_prefill_retries,
            )
            return ResponseRoute.RECOVERY_PREFILL

        # 6. 截断：finish_reason == "length"。
        if is_truncated(response) and recovery.length_continue_retries < recovery.max_truncation_retries:
            logger.info(
                "Recovery: truncated response (retry %d/%d)",
                recovery.length_continue_retries + 1,
                recovery.max_truncation_retries,
            )
            return ResponseRoute.RECOVERY_TRUNCATION

        # 7. 空内容重试。
        if recovery.empty_content_retries < recovery.max_empty_retries:
            logger.info(
                "Recovery: empty content (retry %d/%d)",
                recovery.empty_content_retries + 1,
                recovery.max_empty_retries,
            )
            return ResponseRoute.RECOVERY_RETRY

        # 8. 终端：已耗尽所有恢复选项。
        logger.warning("Recovery: all recovery options exhausted, ending")
        return ResponseRoute.NORMAL_COMPLETION

    # ------------------------------------------------------------------
    # 质量门禁执行（ctx 进 ctx 出，供 model_chain LCEL 管道使用）
    # ------------------------------------------------------------------

    def __call__(self, ctx: ProcessorContext) -> ProcessorContext:
        """评估模型响应质量并决定后续路由。

        根据 validate_response 的返回结果应用恢复操作并抛出对应异常，
        或正常返回以终止循环。
        """
        response = ctx.response

        # 非 AIMessage 直接结束
        if not isinstance(response, AIMessage):
            return ctx

        route = self.validate_response(ctx)

        # 终端路由：正常返回，不抛异常
        if route == ResponseRoute.NORMAL_COMPLETION:
            return ctx
        if route == ResponseRoute.TOOL_EXECUTION:
            return ctx

        # 工具后空响应 → 发送提示
        if route == ResponseRoute.RECOVERY_NUDGE:
            ctx.messages.append(AIMessage(content="(empty)"))
            ctx.messages.append(HumanMessage(content=RECOVERY_NUDGE_PROMPT))
            ctx.model_chain_state.post_tool_empty_retried = True
            raise RecoveryNudgeError(response)

        # 仅思考响应 → 追加 prefill
        if route == ResponseRoute.RECOVERY_PREFILL:
            ctx.messages.append(
                AIMessage(
                    content=response.content or "",
                    response_metadata={"finish_reason": "incomplete"},
                )
            )
            ctx.model_chain_state.thinking_prefill_retries += 1
            raise RecoveryPrefillError(response)

        # 截断响应 → 继续或重建 chain
        if route == ResponseRoute.RECOVERY_TRUNCATION:
            content = response.content or ""

            # 思考预算耗尽
            if isinstance(content, str) and detect_thinking_exhaustion(content):
                logger.warning("Recovery: thinking-budget exhaustion detected")
                ctx.response = AIMessage(content=THINKING_EXHAUSTED_MESSAGE)
                return ctx

            # 工具调用截断：设置 max_tokens_override，下次 _call_llm 会使用增强的 max_tokens
            if response.tool_calls:
                ctx.model_chain_state.truncated_tool_call_retries += 1
                multiplier = min(ctx.model_chain_state.truncated_tool_call_retries + 1, 3)
                boosted_max_tokens = min(32768, multiplier * 8192)
                logger.info(
                    "Recovery: truncated tool call (retry %d/%d), boosting max_tokens to %d",
                    ctx.model_chain_state.truncated_tool_call_retries,
                    ctx.model_chain_state.max_truncated_tool_call_retries,
                    boosted_max_tokens,
                )
                ctx.model_chain_state.max_tokens_override = boosted_max_tokens
            else:
                # 仅文本截断：追加临时内容 + 续行提示
                ctx.model_chain_state.length_continue_retries += 1
                ctx.messages.append(
                    AIMessage(
                        content=content,
                        response_metadata={"finish_reason": "incomplete"},
                    )
                )
                ctx.messages.append(HumanMessage(content=TRUNCATION_CONTINUE_PROMPT))

            raise TruncationError(response)

        # 空内容重试
        if route == ResponseRoute.RECOVERY_RETRY:
            ctx.model_chain_state.empty_content_retries += 1
            logger.info(
                "Recovery retry: empty_content_retries=%d/%d",
                ctx.model_chain_state.empty_content_retries,
                ctx.model_chain_state.max_empty_retries,
            )
            raise RecoveryRetryError(response)

        # 兜底：终止
        return ctx
