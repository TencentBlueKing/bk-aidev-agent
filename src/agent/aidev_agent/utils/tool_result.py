# -*- coding: utf-8 -*-
"""工具结果内容层面的错误信号判定。

工具的异常路径（抛错、MCP ``isError``、连接断裂、超时）由 LangChain 回调的
``on_tool_error`` 表达；但「未抛异常、结果正文却以错误信号开头」的路径不会触发
异常回调，需要按内容前缀单独判定。节点层（ToolMessage 状态）与回调层（span 状态）
共用本模块的同一个函数，避免两处口径漂移。
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest

from aidev_agent.packages.interrupt_manager.approval import TOOL_APPROVAL_REJECTED_KEY

# 工具返回内容里的错误信号前缀：仅认前缀，正文中部或尾部出现不判失败。
ERROR_RESULT_MARKER = "[ERROR]"


def is_error_content(content: Any) -> bool:
    """判断工具结果正文是否以错误信号开头。

    只对字符串结果生效；结构化 / 多模态结果（list、dict 等）不做内容匹配，
    沿用既有结果处理路径。比较前去掉前导空白，避免缩进或空行导致漏判。

    Args:
        content: 工具结果正文，可能是字符串、块列表或任意结构化结果。

    Returns:
        正文以 ``[ERROR]`` 开头时为 True，其余一律 False。
    """
    return isinstance(content, str) and content.lstrip().startswith(ERROR_RESULT_MARKER)


def build_tool_rejection_message(
    request: ToolCallRequest,
    reason: str,
    *,
    skip_persistence: bool = False,
) -> ToolMessage:
    """构造「工具未执行」的拒绝结果。

    Args:
        request: 当前工具调用请求，取其 ``tool_call_id`` 与真实工具名。
        reason: 拒绝原因，作为消息正文返回给模型。
        skip_persistence: 审批类拒绝置 True，在 ``additional_kwargs`` 打语义标记，
            供持久化层跳过落库；hook 拒绝保持 False。

    Returns:
        ``status="error"`` 的 ``ToolMessage``。
    """
    tool_call = request.tool_call
    tool = request.tool
    additional_kwargs = {TOOL_APPROVAL_REJECTED_KEY: True} if skip_persistence else {}
    return ToolMessage(
        content=reason,
        tool_call_id=tool_call.get("id") or "",
        name=tool.name if tool is not None else tool_call.get("name") or "",
        status="error",
        additional_kwargs=additional_kwargs,
    )


__all__ = ["build_tool_rejection_message", "is_error_content"]
