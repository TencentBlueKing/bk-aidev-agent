# -*- coding: utf-8 -*-
"""工具结果内容层面的错误信号判定。

工具的异常路径（抛错、MCP ``isError``、连接断裂、超时）由 LangChain 回调的
``on_tool_error`` 表达；但「未抛异常、结果正文却以错误信号开头」的路径不会触发
异常回调，需要按内容前缀单独判定。节点层（ToolMessage 状态）与回调层（span 状态）
共用本模块的同一个函数，避免两处口径漂移。
"""

from __future__ import annotations

from typing import Any

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


__all__ = ["is_error_content"]
