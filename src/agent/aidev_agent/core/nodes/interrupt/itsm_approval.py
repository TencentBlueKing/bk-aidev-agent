# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import logging
from typing import Any, List

from langchain_core.callbacks import dispatch_custom_event
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.types import Command

from aidev_agent.core.ag_ui.types import LangGraphEventTypes
from aidev_agent.core.nodes.tool.approval_wrapper import (
    get_tool_call_approval_record_from_state,
    identify_message_approval_targets,
    request_approval_decision,
    update_tool_call_approval_record,
)

logger = logging.getLogger(__name__)


class ItsmApprovalStrategy:
    """approval 中断策略 —— 完整复刻原 11.1 ``_check`` 的 approval 逻辑。

    多 target 逐个审批语义：单次 ``interrupt`` 调用只触发一次
    ``request_approval_decision`` → 内部 ``interrupt()``（第一个 pending target），
    图暂停。续流时重新进入 ``approval_check`` 节点，本策略再次运行，
    已处理 target 被跳过，处理下一个 pending target。for 循环通过
    ``continue`` 跳过已处理 target，实现跨续流的逐个审批。

    策略实例除 ``self._tool_map``（构造时不变）外不缓存跨调用状态（D-09）。
    """

    reason = "aidev:tool_approval"

    def __init__(self, tools: List[BaseTool]):
        self._tool_map = {tool.name: tool for tool in tools}

    def interrupt(self, state: dict, config: RunnableConfig) -> Command | None:
        """approval 中断策略主入口（复刻 11.1 ``_check`` approval 逻辑）。

        ``make_interrupt_node`` 已做 D-04 前置检查（messages 非空且末尾
        为含 tool_calls 的 AIMessage），本方法直接从提取 execute_kwargs 开始。

        Returns:
            ``None``：无 approval_targets（让 UserQuestionStrategy 尝试，D-05）。
            ``Command``：所有 target 处理完，``Command(update={"messages":
            [updated_message]}, goto="pv_node")``。

        Raises:
            GraphInterrupt: 第一个 pending target 走 ``request_approval_decision``
                → 内部 ``interrupt()`` 抛出，图暂停。
        """
        last_message = state["messages"][-1]

        _cfg_execute_kwargs = config.get("configurable", {}).get("execute_kwargs")
        _is_resuming = bool(getattr(_cfg_execute_kwargs, "resume", None)) if _cfg_execute_kwargs else False

        # 提取 resume 列表中所有 interruptId，
        # 用于精确判断某个 target 是否属于本次续流恢复的对象。
        _resume_interrupt_ids: set[str] = set()
        if _is_resuming:
            _resume_items = getattr(_cfg_execute_kwargs, "resume", None) or []
            if isinstance(_resume_items, dict):
                _resume_items = [_resume_items]
            for item in _resume_items:
                interrupt_id = (
                    item.get("interruptId", "") if isinstance(item, dict) else getattr(item, "interruptId", "")
                )
                if interrupt_id:
                    _resume_interrupt_ids.add(interrupt_id)

        approval_targets = identify_message_approval_targets(last_message.tool_calls, self._tool_map)
        if not approval_targets:
            return None  # D-05：让 UserQuestionStrategy 尝试

        messages = state.get("messages", [])
        # 收集本轮对话（最后一条 HumanMessage 之后）已有审批终态的 (tool_code, args) → status，
        # 同一轮中同工具同参数复用已有审批结果（如工具执行失败后 model 自动重试）。
        _finalized_tool_signatures: dict[str, str] = {}
        if _is_resuming:
            _turn_start = 0
            for i in range(len(messages) - 1, -1, -1):
                if isinstance(messages[i], HumanMessage):
                    _turn_start = i + 1
                    break
            for msg in messages[_turn_start:]:
                if not isinstance(msg, AIMessage):
                    continue
                approval_map = msg.additional_kwargs.get("tool_approval", {})
                if not isinstance(approval_map, dict):
                    continue
                for tc in msg.tool_calls or []:
                    record = approval_map.get(tc.get("id", ""))
                    if isinstance(record, dict) and record.get("status") in ("approved", "rejected"):
                        code = record.get("toolCode") or tc.get("name", "")
                        sig = f"{code}::{json.dumps(tc.get('args', {}), sort_keys=True)}"
                        _finalized_tool_signatures[sig] = record["status"]

        updated_message = last_message
        for target in approval_targets:
            existing_record = get_tool_call_approval_record_from_state(state, target.target_id)
            existing_status = existing_record.get("status") if isinstance(existing_record, dict) else None

            if existing_status == "approved":
                continue
            if existing_status == "rejected":
                continue

            # 同轮次同工具同参数已有审批终态，直接复用结果
            _target_sig = f"{target.target_code}::{json.dumps(target.args or {}, sort_keys=True)}"
            _prior_status = _finalized_tool_signatures.get(_target_sig)
            if _prior_status:
                updated_message = update_tool_call_approval_record(
                    updated_message, target, status=_prior_status, interrupt_payload=None
                )
                continue

            interrupt_holder: dict[str, dict] = {}

            def _emit_interrupt(payload: dict[str, Any]) -> None:
                interrupt_holder["payload"] = payload
                dispatch_custom_event(
                    LangGraphEventTypes.OnInterrupt.value,
                    payload,
                    config=config,
                )

            # 判断当前 target 是否属于本次续流恢复：
            # interrupt_id 格式为 "int-approval-{target_id}-{suffix}"，
            # 用 startswith 精确匹配避免 :1 误匹配 :10。
            _approval_id_prefix = f"int-approval-{target.target_id}-"
            _target_is_resuming = _is_resuming and any(
                interrupt_id.startswith(_approval_id_prefix) for interrupt_id in _resume_interrupt_ids
            )

            approved = request_approval_decision(
                target,
                execute_kwargs=_cfg_execute_kwargs,
                is_resuming=_target_is_resuming,
                on_interrupt=_emit_interrupt,
                interrupt_payload=existing_record.get("interrupt") if isinstance(existing_record, dict) else None,
            )
            status = "approved" if approved else "rejected"
            # 实时更新签名集合，供同一次节点执行中后续 target 复用
            _finalized_tool_signatures[_target_sig] = status
            updated_message = update_tool_call_approval_record(
                updated_message,
                target,
                status=status,
                interrupt_payload=interrupt_holder.get("payload")
                or (existing_record.get("interrupt") if isinstance(existing_record, dict) else None),
            )
        return Command(update={"messages": [updated_message]}, goto="pv_node")


__all__ = ["ItsmApprovalStrategy"]
