# -*- coding: utf-8 -*-
"""共享事件构造纯函数模块，供 SSE 侧（AidevAGUIAgent）与 DB 侧（BaseSessionWriter）统一调用。

消除两侧在审批判定、工具增强、ToolResult 构造、thinking 状态机判定、ModelEnd payload 构造上的重复实现。
"""

import json
import uuid
from typing import Any

from ag_ui.core import EventType

from aidev_agent.core.nodes.tool.approval_wrapper import is_approval_configured

from .events import ExtendToolCallResultEvent
from .types import ExtendFunctionCall, ExtendToolCall

# 仅有tool_calls、无文本输出的 assistant 消息使用的占位符 content。
# 首帧 MESSAGES_SNAPSHOT（历史还原）与 interrupt 终态回放需将其归一化为 ""，
# 与前端读接口（session_content / session）的展示语义保持一致。
TOOL_CALLING_PLACEHOLDER = "正在调用工具..."


def is_tool_approval_required(tool_call_name: str, tools: dict[str, Any]) -> bool:
    """检查工具调用是否需要审批。

    Args:
        tool_call_name: 工具调用名称
        tools: 工具名→工具对象映射（SSE 侧 _tool_mapping 或 DB 侧 _tools_mapping）
    """
    _tool = tools.get(tool_call_name)
    return is_approval_configured(_tool)


def enhance_tool_call(tool_call_name: str, tools: dict[str, Any]) -> dict[str, Any]:
    """为工具调用注入 description 和 mcp_name。

    Args:
        tool_call_name: 工具调用名称
        tools: 工具名→工具对象映射

    Returns:
        dict 含 description + mcp_name 键，供 ExtendToolCallStartEvent 或 ExtendFunctionCall 使用
    """
    _tool = tools.get(tool_call_name)
    return {
        "description": _tool.description if _tool else "",
        "mcp_name": _tool.metadata.get("mcp_name", "") if _tool and _tool.metadata else "",
    }


def build_tool_result_event(tool_msg: Any, is_immediate: bool = False) -> ExtendToolCallResultEvent:
    """从 ToolMessage 构造 ExtendToolCallResultEvent。

    Args:
        tool_msg: LangGraph ToolMessage 对象
        is_immediate: True 表示子 Agent 中间步骤（duration=None, is_error=False, skip_db=True）；
                     False 表示正常工具完成（从 additional_kwargs 取 duration，从 status/error 推导 is_error，skip_db=False）

    Returns:
        ExtendToolCallResultEvent 事件对象，携带 additional_metadata（完整 additional_kwargs dict 副本）
        与 skip_db（is_immediate=True 时为 True，供 DB 侧跳过写入，per D-06/D-07）
    """
    content = tool_msg.content
    if not isinstance(content, str):
        content = str(content) if content else ""

    if is_immediate:
        duration = None
        is_error = False
        skip_db = True
    else:
        duration = tool_msg.additional_kwargs.get("duration", None)
        is_error = getattr(tool_msg, "status", None) == "error" or bool(getattr(tool_msg, "error", None))
        skip_db = False

    return ExtendToolCallResultEvent(
        type=EventType.TOOL_CALL_RESULT,
        tool_call_id=tool_msg.tool_call_id,
        message_id=tool_msg.id or str(uuid.uuid4()),
        content=content,
        role="tool",
        duration=duration,
        is_error=is_error,
        additional_metadata=dict(tool_msg.additional_kwargs),
        skip_db=skip_db,
    )


def should_end_thinking(thinking_process: dict | None, reasoning_data: dict | None) -> bool:
    """判断是否应结束当前 thinking 过程。

    SSE 侧 agent.py:528 逻辑：reasoning_data 为 None 且 thinking_process 非空时结束。
    """
    return reasoning_data is None and thinking_process is not None


def should_switch_thinking_step(thinking_process: dict | None, reasoning_data: dict | None) -> bool:
    """判断是否应切换 thinking step（先 End 当前再 Start 新的）。

    SSE 侧 agent.py:844-847 逻辑：thinking_process 非空且 index 不同时切换。
    """
    if not thinking_process:
        return False
    if not reasoning_data:
        return False
    current_index = thinking_process.get("index")
    new_index = reasoning_data.get("index")
    return current_index is not None and new_index is not None and current_index != new_index


def build_tool_calls_with_approval_filter(output_message: Any, tools_mapping: dict[str, Any]) -> tuple[list, list]:
    """从模型输出中构建 tool_calls 列表，将需要审批的工具分离出来延迟写入。

    从 base.py:_build_tool_calls_with_approval_filter 迁移为模块级纯函数，
    tools_mapping 替代原 self._tools_mapping 实例状态。

    Args:
        output_message: AIMessage（模型输出）
        tools_mapping: 工具名→工具对象映射（SSE 侧 self._tool_mapping 或 DB 侧 self._tools_mapping）

    Returns:
        (immediate_tool_calls, deferred_tool_calls)
        - immediate_tool_calls: 不需要审批的工具调用，立即写入
        - deferred_tool_calls: 需要审批的工具调用，待审批通过执行后补充写入
    """
    immediate_tool_calls = []
    deferred_tool_calls = []
    for each in output_message.tool_calls or []:
        _tool = tools_mapping.get(each["name"])
        tool_call_dict = ExtendToolCall(
            id=each["id"],
            function=ExtendFunctionCall(
                name=each["name"],
                arguments=json.dumps(each["args"]),
                description=_tool.description if _tool else "",
                mcp_name=_tool.metadata.get("mcp_name", "") if _tool and _tool.metadata else "",
            ),
        ).model_dump()

        if is_approval_configured(_tool):
            deferred_tool_calls.append(tool_call_dict)
        else:
            immediate_tool_calls.append(tool_call_dict)
    return immediate_tool_calls, deferred_tool_calls


def resolve_content(
    content: str, tool_calls: list, reasoning_content: str | None, *, has_deferred_tool_calls: bool = False
) -> str:
    """解析最终回复内容。

    从 base.py:_resolve_content 迁移为模块级纯函数，逻辑完全一致，无实例状态依赖。

    对于 DeepSeek reasoning 模型，最终回复可能在 reasoning_content 而不是 content。
    当有 tool_calls 时，content 为空是正常的（AI 只是调用工具）。
    当没有 tool_calls 且 content 为空时，尝试使用 reasoning_content 作为回复内容。

    Args:
        content: 原始回复内容
        tool_calls: 立即写入的 tool_calls 列表
        reasoning_content: reasoning 内容（如 deepseek-reasoner）
        has_deferred_tool_calls: 是否有延迟写入的审批 tool_calls
    """
    content_stripped = content.strip() if content else ""

    if not content_stripped and has_deferred_tool_calls:
        # 所有 tool_calls 都是审批延迟的，工具尚未执行，避免把 reasoning_content 误当作 assistant 内容
        return ""
    if not content_stripped and not tool_calls and reasoning_content:
        # reasoning 模型的最终回复在 reasoning_content 中
        return reasoning_content
    elif not content_stripped and tool_calls:
        # 有立即写入的 tool_calls 但 content 为空/只有空白字符，使用一个有意义的占位符
        return TOOL_CALLING_PLACEHOLDER
    elif not content_stripped:
        # 没有 tool_calls 也没有内容，使用空字符串（可能会失败）
        return ""
    return content_stripped


def build_model_end_payload(output_message: Any, tools_mapping: dict[str, Any]) -> dict[str, Any]:
    """构造 ChatModelEnd CustomEvent.value 的扁平 dict payload。

    整合 build_tool_calls_with_approval_filter + resolve_content 的全部逻辑，SSE 侧调用此函数
    构造 CustomEvent.value，DB 侧直接读 payload 不再二次推导（D-03/D-04）。

    Args:
        output_message: AIMessage（模型输出，OnChatModelEnd 事件的 data.output）
        tools_mapping: 工具名→工具对象映射

    Returns:
        扁平 dict，含 message_id / content / tool_calls / deferred_tool_calls /
        reasoning_content / reasoning_duration
    """
    tool_calls, deferred_tool_calls = build_tool_calls_with_approval_filter(output_message, tools_mapping)

    reasoning_content = output_message.additional_kwargs.get("reasoning_content")

    content = resolve_content(
        output_message.content,
        tool_calls,
        reasoning_content,
        has_deferred_tool_calls=bool(deferred_tool_calls),
    )

    reasoning_duration = output_message.additional_kwargs.get("reasoning_time", 0)
    message_id = output_message.id

    return {
        "message_id": message_id,
        "content": content,
        "tool_calls": tool_calls,
        "deferred_tool_calls": deferred_tool_calls,
        "reasoning_content": reasoning_content,
        "reasoning_duration": reasoning_duration,
    }
