# -*- coding: utf-8 -*-
"""工具加载模式（``ExecuteKwargs.mode``）的装配期过滤。

本模块是 ``mode`` 语义的**唯一实现点**：``ReActAgentBuilder._prepare_agent_tools``
在收集完所有工具后调用 :func:`filter_tools_by_loading_mode` 裁剪一次，模型节点与
ToolNode 共用同一列表；命令级审批的开关由 :func:`command_approval_allowed` 给出，
在装配期直接改写安全配置（review 处置档降为 ``block``），而不是作为参数透传到
``enforce_command_security``。

判定口径（不新增人工维护的工具名单）：

- ask 类工具：工具名属于内置 ask 提问工具名集合，当前仅 ``ask_user_question``。
- 带审批工具：复用 :func:`~aidev_agent.packages.interrupt_manager.approval.is_approval_configured`
  （读 ``tool.metadata["approval"]``），与 ``approval_wrapper`` 等既有链路同源。
- 外部 MCP / 第三方工具不参与推断，按普通工具处理。
"""

from __future__ import annotations

import logging
from typing import List

from langchain_core.tools import BaseTool

from aidev_agent.packages.interrupt_manager import ASK_USER_QUESTION_TOOL_NAME, is_approval_configured

logger = logging.getLogger(__name__)

#: 内置 ask 类提问工具名集合；新增内置 ask 工具时在此登记。
ASK_TOOL_NAMES: frozenset[str] = frozenset({ASK_USER_QUESTION_TOOL_NAME})

MODE_DEFAULT = "default"
MODE_DONT_INTERRUPT = "dontInterrupt"
MODE_DONT_ASK = "dontAsk"

#: 需要剔除 ask 类工具的 mode。
_MODES_WITHOUT_ASK: frozenset[str] = frozenset({MODE_DONT_INTERRUPT, MODE_DONT_ASK})


def _is_ask_tool(tool: BaseTool) -> bool:
    return getattr(tool, "name", None) in ASK_TOOL_NAMES


def filter_tools_by_loading_mode(tools: List[BaseTool], mode: str) -> List[BaseTool]:
    """按工具加载模式裁剪装配期工具集合。

    - ``default``：不做任何过滤，**原样返回入参列表**（不拷贝），保证与变更前逐项一致。
    - ``dontAsk``：仅移除 ask 类工具；带审批工具与 ``execute`` 保留。
    - ``dontInterrupt``：移除 ask 类工具与全部带生效审批配置的工具；``execute`` 与其余
      无中断能力的工具保留（命令级审批由 :func:`command_approval_allowed` 判定，
      在装配期改写安全配置关闭）。
    - 其它取值（理论上被 ``ExecuteKwargs`` 的 ``Literal`` 拒绝）：按 ``default`` 处理，不裁剪。

    Args:
        tools: 装配期已收集的完整工具列表。
        mode: ``ExecuteKwargs.mode`` 的取值。

    Returns:
        过滤后的工具列表；``default`` 时与 ``tools`` 是同一对象。
    """
    if mode == MODE_DEFAULT or mode not in _MODES_WITHOUT_ASK:
        return tools

    kept: List[BaseTool] = []
    dropped: list[str] = []
    for tool in tools:
        if _is_ask_tool(tool):
            dropped.append(getattr(tool, "name", "<unnamed>"))
            continue
        if mode == MODE_DONT_INTERRUPT and is_approval_configured(tool):
            dropped.append(getattr(tool, "name", "<unnamed>"))
            continue
        kept.append(tool)

    if dropped:
        logger.info("[tool-loading-mode] mode=%s 已剔除工具: %s", mode, dropped)
    return kept


def command_approval_allowed(mode: str) -> bool:
    """该 mode 下是否允许发起命令级审批。

    仅 ``dontInterrupt`` 返回 ``False``（装配期把 review 处置档降为 ``block``，
    灰名单命令 fail-closed 直接拒绝，不创建 ITSM 单）；
    ``default`` / ``dontAsk`` 以及未知取值返回 ``True``，保持既有审批链路。
    """
    return mode != MODE_DONT_INTERRUPT
