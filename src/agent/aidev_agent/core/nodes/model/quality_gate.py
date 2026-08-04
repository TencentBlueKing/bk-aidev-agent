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
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage

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
    judgment_sys_prompt: str = """
## 角色
你是一个任务完成度判断器。你需要判断智能助手在本轮交互中，是否已经完成用户最后一条输入所提出的任务。
你会获得以下信息：
1. 用户的最后一条输入
2. 智能助手回答过程中调用的工具及其参数
3. 智能助手的最后一条输出
## 任务要求
以下情况判断为“已完成”：
1. 智能助手已经明确回答用户的问题
2. 智能助手已经执行用户要求的动作，并且最终回复了用户的要求
3. 智能助手要求用户补充完成任务所必需的信息，或提出合理的澄清问题
4. 智能助手明确说明由于能力、权限或信息限制而无法完成
5. 核心任务已经完成，但助手又附加了说明、建议、追问或其他内容
以下情况判断为“未完成”：
1. 智能助手没有回答或执行用户要求的核心任务
2. 输出答非所问，且工具调用也没有完成任务
3. 仅复述用户输入，没有产生实际回答或动作
4. 声称将要执行任务，但实际上没有回答，也没有调用工具执行
5. 输出明显中断，核心结果缺失
以下情况判断为“不确定”：
1. 无法从工具参数或输出中判断工具是否实际实现了用户要求
2. 用户需求本身存在关键歧义，无法判断当前行为是否满足要求
3. 提供的信息不足以确定任务是否完成
特别规则:
1. 判断“是否完成”时，应关注用户原始要求中的最小核心目标
2. 不要把助手自行扩展出来的后续任务，当成用户原始任务的一部分
3. 不要要求用户必须回答助手提出的问题，才认为“提出问题”这一任务完成
4. 如果工具调用与最后文本输出冲突，应优先判断用户要求的核心动作是否已在工具调用中完成
5. 输出质量一般、存在冗余或包含无关内容，不等于任务未完成；只有核心任务没有实现时，才判断为“未完成”

请只返回以下三个词中的一个，不要返回任何其他内容：
- 已完成
- 未完成
- 不确定

## 输入
用户最后一条输入： 
```
{last_user_input}
```

{tool_calls_text}

智能助手最后一条输出：
```
{last_model_output}
```
"""

    def __init__(
        self,
        *,
        judge_llm: BaseChatModel | None = None,
        enable_judge_response: bool = True,
    ) -> None:
        """初始化质量门禁。

        Args:
            judge_llm: 判断用 LLM 实例。构造一次并复用（避免每次响应重建）。
                为 None 时 fail-open（跳过判断，视为已完成）。
            enable_judge_response: 是否启用任务完成度评估。关闭后
                ``has_content`` 分支直接返回 ``NORMAL_COMPLETION``，省去
                每次正常响应的额外判断 LLM 调用。
        """
        self.judge_llm = judge_llm
        self.enable_judge_response = enable_judge_response

    # ------------------------------------------------------------------
    # 任务完成度判断（SRE3-6-35B-A3B-nothinking judge，fail-open 语义）
    # ------------------------------------------------------------------

    def _extract_last_human_input(self, messages: list[BaseMessage]) -> str | None:
        """从消息列表中逆向提取最后一条 HumanMessage 的文本。"""
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return extract_text_from_content(msg.content)
        return None

    def _extract_tool_calls_since_last_human(self, messages: list[BaseMessage]) -> list[dict]:
        """从消息列表中提取最后一次 HumanMessage 之后发生的工具调用信息。

        只提取工具名称和参数，不包含工具返回结果。
        从最后一条 HumanMessage 开始向后扫描，收集之后所有 AIMessage 中的 tool_calls。

        Returns:
            工具调用列表，每个元素为 ``{"name": str, "args": dict}``
        """
        # 找到最后一条 HumanMessage 的索引
        last_human_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                last_human_idx = i
                break

        if last_human_idx == -1:
            return []

        # 从 HumanMessage 之后开始收集所有 AIMessage 中的 tool_calls
        tool_calls: list[dict] = []
        for msg in messages[last_human_idx + 1 :]:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls.append({"name": tc.get("name", ""), "args": tc.get("args", {})})
        return tool_calls

    def _judge_task_completion(
        self,
        judgment_llm,
        last_user_input: str,
        last_model_output: str,
        *,
        tool_calls: list[dict] | None = None,
        enable_custom_event: bool = True,
    ) -> bool:
        """调用判断模型评估任务是否完成。fail-open：无法确定未完成则返回 True。

        Args:
            judgment_llm: 用于判断的 LLM 实例
            last_user_input: 最后一条用户输入文本
            last_model_output: 最后一条模型输出文本（已剔除 think 块）
            tool_calls: 最后一次用户提问到 AI 回答期间调用的工具及参数列表，
                每个元素为 ``{"name": str, "args": dict}``，不包含工具结果
            enable_custom_event: 是否派发 custom_event（用于 SSE 流期间
                切换 ``front_end_display``，避免判断 LLM 的流式输出写入 DB
                或显示给前端）。

        Returns:
            True 表示任务已完成（或无法确定未完成），False 表示明确未完成
        """
        if not judgment_llm or not last_user_input or not last_model_output:
            return True  # fail-open

        # 构建工具调用信息文本
        tool_calls_text = ""
        if tool_calls:
            tool_lines = []
            for tc in tool_calls:
                tool_lines.append(f"- {tc['name']}({tc['args']})")
            tool_calls_text = "调用的工具及参数：\n" + "\n".join(tool_lines) + "\n\n"

        prompt = self.judgment_sys_prompt.format(
            last_user_input=last_user_input, tool_calls_text=tool_calls_text, last_model_output=last_model_output
        )
        # 判断 LLM 调用期间关闭前端显示/DB 写入，避免判断输出污染会话流。
        # 使用 try/finally 确保异常路径下也恢复 front_end_display=True。
        conditional_dispatch_custom_event(
            "custom_event",
            {"front_end_display": False},
            enable_custom_event=enable_custom_event,
        )
        try:
            resp = judgment_llm.invoke(prompt)
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
        """提取最后用户输入、工具调用信息和模型输出，调用判断 LLM。fail-open 语义。

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
        tool_calls = self._extract_tool_calls_since_last_human(working_messages)
        return self._judge_task_completion(
            self.judge_llm,
            last_user_input,
            last_model_output,
            tool_calls=tool_calls,
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
            and recovery.truncated_tool_call_retries < recovery.max_retries
        ):
            logger.info(
                "Recovery: truncated tool call (retry %d/%d)",
                recovery.truncated_tool_call_retries + 1,
                recovery.max_retries,
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
            if self.enable_judge_response and not self._judge_response_completion(
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
        ) and recovery.thinking_prefill_retries < recovery.max_retries:
            logger.info(
                "Recovery: thinking-only response (prefill retry %d/%d)",
                recovery.thinking_prefill_retries + 1,
                recovery.max_retries,
            )
            return ResponseRoute.RECOVERY_PREFILL

        # 6. 截断：finish_reason == "length"。
        if is_truncated(response) and recovery.length_continue_retries < recovery.max_retries:
            logger.info(
                "Recovery: truncated response (retry %d/%d)",
                recovery.length_continue_retries + 1,
                recovery.max_retries,
            )
            return ResponseRoute.RECOVERY_TRUNCATION

        # 7. 空内容重试。
        if recovery.empty_content_retries < recovery.max_retries:
            logger.info(
                "Recovery: empty content (retry %d/%d)",
                recovery.empty_content_retries + 1,
                recovery.max_retries,
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
                    ctx.model_chain_state.max_retries,
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
                ctx.model_chain_state.max_retries,
            )
            raise RecoveryRetryError(response)

        # 兜底：终止
        return ctx
