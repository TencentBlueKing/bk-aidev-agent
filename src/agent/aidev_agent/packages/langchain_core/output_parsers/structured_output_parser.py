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
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.output_parsers.json import parse_json_markdown
from langchain_core.outputs import ChatGeneration, Generation

logger = logging.getLogger(__name__)

# ============================================================================
# 常量定义（从 langchain_classic 中移植）
# ============================================================================

OUTPUT_PARSER_ERR_MSG = "无法从 LLM 输出内容中解析出要求的 JSON BLOB，本次工具调用或结论解析失败。"
ACTION_INPUT_ERR_MSG = """要求LLM返回的 $JSON_BLOB 中的 $TOOL_INPUT 务必是个字典，
即务必同时指定参数名和参数值，而不要只指定参数值。但是LLM却只指定了其参数值，而没有指定参数名！工具调用失败！"""

# Final Answer 前缀/后缀用于 fallback 解析
FINAL_ANSWER_PREFIXES = [
    '```\n{\n  "action": "Final Answer",\n  "action_input": "',
    '```json\n{\n  "action": "Final Answer",\n  "action_input": "',
    """```\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    """```json\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    '```json\\n\\n{\n  \\"action\\": \\"Final Answer\\",\n  \\"action_input\\": \\"',
    """```json\n{\n  \"action\": \"Final Answer\",\n  \"action_input\": \"""",
    # 匹配 "action_input" 的值为 {...} 的情况，例如用户问"用json格式给我输出不同排序算法的对比"
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


# ============================================================================
# 工具函数（从 langchain_classic 中移植）
# ============================================================================


def remove_thinking_process(resp_content: str) -> str:
    """
    移除 DeepSeek R1 系列模型输出中的思考过程。

    Args:
        resp_content: 模型输出的原始内容

    Returns:
        移除思考过程后的内容
    """
    if resp_content.startswith("<think>\n") and "\n</think>\n\n" in resp_content:
        return resp_content.split("\n</think>\n\n")[-1]
    return resp_content


def is_deepseek_r1_series_models(llm: BaseChatModel) -> bool:
    """
    判断是否是 DeepSeek R1 系列模型。

    Args:
        llm: 语言模型实例

    Returns:
        是否是 DeepSeek R1 系列模型
    """
    model_name = getattr(llm, "model_name", "") or getattr(llm, "model", "") or ""
    return "deepseek-r1" in model_name.lower()


# ============================================================================
# 结构化输出解析器
# ============================================================================


class StructuredOutputToToolMessageParser(BaseOutputParser[AIMessage]):
    """
    将结构化 JSON 输出解析为带有 tool_calls 的 AIMessage。

    当模型不支持原生 function calling 时，使用此解析器将结构化输出
    转换为 LangGraph 标准的工具调用格式，以便 ToolNode 能够正确执行。

    参考 EnhancedJSONAgentOutputParser 的实现，支持：
    1. DeepSeek R1 系列模型的思考过程移除
    2. 使用 parse_json_markdown 进行更健壮的 JSON 解析
    3. 并行工具调用支持（返回多个 tool_calls）
    4. Final Answer 检测和处理
    5. action_input 类型校验（必须是 dict）
    6. 前缀/后缀 fallback 解析

    注意：
    - 此解析器不校验工具是否存在，工具存在性校验由 ToolNode 负责
    - 当 action_input 格式错误时，返回 name="invalid_tool" 的工具调用
    - _handle_tool_call 始终返回带 tool_calls 的 AIMessage

    支持的 JSON 格式：
    {
        "action": "tool_name",
        "action_input": {...}
    }
    或并行调用：
    [
        {"action": "tool1", "action_input": {...}},
        {"action": "tool2", "action_input": {...}}
    ]
    """

    llm: Optional[BaseChatModel] = None
    enable_parallel_tool_calls: bool = False

    class Config:
        arbitrary_types_allowed = True

    @property
    def _type(self) -> str:
        """返回解析器类型标识。"""
        return "structured_output_to_tool_message_parser"

    def parse_result(self, result: List[Generation], *, partial: bool = False) -> AIMessage:
        """
        解析 Generation 列表，提取工具调用信息并转换为 tool_calls 格式。

        重写此方法以支持 ChatGeneration（包含 AIMessage）的情况。

        Args:
            result: Generation 列表
            partial: 是否为部分解析

        Returns:
            带有 tool_calls 的 AIMessage，如果没有工具调用则返回原消息
        """
        if not result:
            raise OutputParserException("No generation result to parse")

        generation = result[0]

        # 处理 ChatGeneration（包含 AIMessage）
        if isinstance(generation, ChatGeneration):
            message = generation.message
            if isinstance(message, AIMessage):
                content = message.content
                if content and isinstance(content, str):
                    return self._parse_content(content)
                return message
            # 非 AIMessage 情况，尝试解析 text
            return self.parse(generation.text)

        # 处理普通 Generation
        return self.parse(generation.text)

    def parse(self, text: str) -> AIMessage:
        """
        解析文本内容，提取工具调用信息并转换为 tool_calls 格式。

        Args:
            text: 模型输出的文本

        Returns:
            带有 tool_calls 的 AIMessage，如果没有工具调用则返回原消息
        """
        if not text:
            return AIMessage(content="")

        return self._parse_content(text)

    def _parse_content(self, content: str) -> AIMessage:
        """
        解析内容，提取工具调用信息并转换为 tool_calls 格式。

        Args:
            content: 模型输出的内容

        Returns:
            带有 tool_calls 的 AIMessage，如果没有工具调用则返回原消息
        """
        cur_time = datetime.now(pytz.utc).astimezone(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %f")
        logger.info(f"=====> [StructuredOutputToToolMessageParser] [{cur_time}] 原始输出: {content[:500]}...")

        # DeepSeek R1 系列模型：移除思考过程
        text = content
        if self.llm and is_deepseek_r1_series_models(self.llm):
            text = remove_thinking_process(text)
            logger.info(f"=====> [StructuredOutputToToolMessageParser] [{cur_time}] 移除思考过程后: {text[:500]}...")

        try:
            # 使用 parse_json_markdown 进行更健壮的 JSON 解析
            response = parse_json_markdown(text)
            logger.info(f"=====> [StructuredOutputToToolMessageParser] [{cur_time}] 解析结果: {response}")

            # 处理并行工具调用
            if isinstance(response, list):
                if len(response) > 1 and self.enable_parallel_tool_calls:
                    return self._handle_parallel_tool_calls(response, content)
                else:
                    # 只用一个的时候 或 不支持并行调用时，只取第一个
                    logger.warning(
                        "Got multiple action responses but parallel calls disabled, using first: %s", response
                    )
                    response = response[0]

            # 处理 Final Answer
            if self._is_final_answer(response):
                return self._handle_final_answer(response, content)

            # 处理工具调用
            return self._handle_tool_call(response, content)

        except Exception as e:
            logger.warning(f"=====> [StructuredOutputToToolMessageParser] [{cur_time}] 解析异常: {e}")

            # Fallback: 尝试通过前缀/后缀匹配 Final Answer
            final_answer = self._extract_final_answer_by_prefix(text)
            if final_answer is not None:
                return AIMessage(content=final_answer)

            # 解析失败，返回原消息内容
            logger.warning(f"=====> [StructuredOutputToToolMessageParser] [{cur_time}] 无法解析，返回原消息")
            return AIMessage(content=content)

    def _handle_parallel_tool_calls(self, response: List[Dict], original_content: str) -> AIMessage:
        """
        处理并行工具调用。

        注意：此方法不校验工具是否存在，工具存在性校验由 ToolNode 负责。
        这样可以确保当模型调用不存在的工具时，ToolNode 能返回错误信息。

        Args:
            response: 解析后的工具调用列表
            original_content: 原始输出内容

        Returns:
            带有多个 tool_calls 的 AIMessage
        """
        tool_calls = []
        errors = []

        for tool_call_data in response:
            tool_name = tool_call_data.get("action")
            tool_input = tool_call_data.get("action_input")

            # Final Answer 不能与工具调用混合
            if tool_name == "Final Answer":
                logger.warning("Cannot mix Final Answer with tool calls in parallel mode")
                errors.append("工具 'Final Answer' 不能与其他工具调用混合使用")
                continue

            if not tool_name:
                logger.warning("工具调用缺少 action 字段")
                errors.append("工具调用缺少 action 字段")
                continue

            # 校验 action_input 必须是 dict
            if tool_input is None:
                tool_input = {}
            elif isinstance(tool_input, str):
                logger.warning(f"action_input 应为 dict 而非 str: {tool_input}")
                # 对于字符串类型的 action_input，创建带特殊标识的工具调用
                # 让 ToolNode 返回错误信息
                tool_calls.append(
                    {
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "name": "invalid_tool",
                        "args": {"error": ACTION_INPUT_ERR_MSG, "original_input": tool_input},
                    }
                )
                continue

            # 不再校验工具是否存在，让 ToolNode 处理
            tool_calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": tool_name,
                    "args": tool_input if isinstance(tool_input, dict) else {},
                }
            )

        if not tool_calls:
            # 如果没有有效的工具调用，返回包含错误信息的消息
            error_msg = "; ".join(errors) if errors else "无法解析有效的工具调用"
            return AIMessage(content=f"{original_content}\n\n[解析错误] {error_msg}")

        return AIMessage(
            content=original_content,
            tool_calls=tool_calls,
        )

    def _handle_final_answer(self, response: Dict, original_content: str) -> AIMessage:
        """
        处理 Final Answer。

        Args:
            response: 解析后的响应
            original_content: 原始输出内容

        Returns:
            不带 tool_calls 的 AIMessage（表示结束）
        """
        action_input = response.get("action_input", "")

        # 如果 action_input 是 dict，转为 JSON 字符串
        if isinstance(action_input, dict):
            action_input = json.dumps(action_input, ensure_ascii=False, indent=4)

        # Final Answer 返回不带 tool_calls 的消息，让 LangGraph 知道应该结束
        return AIMessage(content=str(action_input))

    def _handle_tool_call(self, response: Dict, original_content: str) -> AIMessage:
        """
        处理单个工具调用。

        注意：
        1. 此方法不校验工具是否存在，工具存在性校验由 ToolNode 负责
        2. 始终返回带 tool_calls 的 AIMessage，即使 action_input 格式错误

        Args:
            response: 解析后的响应
            original_content: 原始输出内容

        Returns:
            带有 tool_calls 的 AIMessage（始终包含 tool_calls）
        """
        tool_name = response.get("action")
        tool_input = response.get("action_input")

        if not tool_name:
            return AIMessage(content=original_content)

        # 校验 action_input 必须是 dict
        if tool_input is None:
            tool_input = {}
        elif isinstance(tool_input, str):
            logger.warning(f"{ACTION_INPUT_ERR_MSG} 收到的 action_input: {tool_input}")
            # 返回带特殊标识的工具调用，让 ToolNode 返回错误信息
            # 这样模型能在 ReAct loop 中看到错误并修正
            tool_calls = [
                {
                    "id": f"call_{uuid.uuid4().hex[:8]}",
                    "name": "invalid_tool",
                    "args": {"error": ACTION_INPUT_ERR_MSG, "original_input": tool_input},
                }
            ]
            return AIMessage(
                content=original_content,
                tool_calls=tool_calls,
            )

        # 不再校验工具是否存在，让 ToolNode 处理
        # 构建 tool_calls
        tool_calls = [
            {
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "name": tool_name,
                "args": tool_input if isinstance(tool_input, dict) else {},
            }
        ]

        return AIMessage(
            content=original_content,
            tool_calls=tool_calls,
        )

    def _is_final_answer(self, data: Any) -> bool:
        """
        检查是否是 Final Answer。

        Args:
            data: 解析后的数据

        Returns:
            是否是 Final Answer
        """
        if not isinstance(data, dict):
            return False
        action = data.get("action") or data.get("tool")
        return action == "Final Answer"

    def _extract_final_answer_by_prefix(self, text: str) -> Optional[str]:
        """
        通过前缀/后缀匹配提取 Final Answer（fallback 机制）。

        参考 EnhancedJSONAgentOutputParser 的实现。

        Args:
            text: 原始文本

        Returns:
            提取的 Final Answer 内容，如果未找到则返回 None
        """
        for final_answer_prefix, final_answer_suffix in zip(FINAL_ANSWER_PREFIXES, FINAL_ANSWER_SUFFIXES):
            if final_answer_prefix in text:
                try:
                    final_answer_content = text.split(final_answer_prefix)[-1]
                    if final_answer_suffix and len(final_answer_suffix) > 0:
                        final_answer_content = final_answer_content[: -len(final_answer_suffix)]
                    return final_answer_content
                except Exception:
                    continue
        return None


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
