# -*- coding: utf-8 -*-
"""同一 Trace 内「相同工具 + 相同参数」连续重复调用的检测、拒绝与终止。

判定键 = 工具名 + 参数指纹（规范化 JSON）。判定键在同一 run 的消息历史里连续出现
时累计次数：前 ``T`` 次放行真实执行，第 ``T+1`` 至 ``T+F`` 次拒绝并以失败反馈回给
模型，第 ``T+F+1`` 次直接终止本次 run。

拒绝不进入工具本体或内层执行 wrapper（无副作用、不审批、不计时），但会以 duration=0 的结果
被最外层事件 wrapper 正常派发一次，并在 Trace 上留下一条以 ERROR 结束的 ``tool.execution`` span，
让「循环拒绝」可按既有 ``span_name='tool.execution'`` + ``error.type`` 口径统计。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from langchain_core.callbacks import AsyncCallbackManager, CallbackManager
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.prebuilt.tool_node import AsyncToolCallWrapper, ToolCall, ToolCallRequest, ToolCallWrapper
from langgraph.types import Command

from .timer_wrapper import _apply_timing_metadata

logger = logging.getLogger(__name__)

# 判定结论
ALLOW = "allow"
REJECT = "reject"
TERMINATE = "terminate"

# 终止原因文案：会话侧与调度层按该关键字归因「工具循环调用拒绝」
TERMINATION_MESSAGE = "任务因工具循环调用被中断"
TRUNCATED_SUFFIX = "……（内容过长，已截断）"


class ToolLoopRejection(RuntimeError):
    """被拒绝调用的错误载体，仅用于 span 的 ``error.type``（取值 ``ToolLoopRejection``）。"""


class ToolLoopTerminationError(RuntimeError):
    """连续重复达到 ``T+F+1`` 次时抛出，越过 ToolNode 兜底直接终止 run。"""


@dataclass(frozen=True)
class LoopGuardPolicy:
    """循环守卫策略。

    Attributes:
        repeat_limit: 允许真实执行的次数 ``T``，必须 >= 1。
        feedback_rounds: 拒绝后允许返回的失败反馈次数 ``F``，必须 >= 0。
        result_limit: 拒绝反馈中「最后一次真实返回内容」的摘要长度上限。
    """

    repeat_limit: int = 3
    feedback_rounds: int = 2
    result_limit: int = 10000


@dataclass(frozen=True)
class _LoopDecision:
    """一次调用的判定结论。

    Attributes:
        action: ``allow`` / ``reject`` / ``terminate``。
        repeat_count: 含本次在内的连续调用次数。
        last_result: 该判定键最近一次真实执行返回的 ToolMessage，可能为 None。
    """

    action: str
    repeat_count: int = 0
    last_result: ToolMessage | None = None


def fingerprint(args: Any) -> str | None:
    """计算参数的规范化 JSON 指纹。

    对象键排序、紧凑分隔符、字符串原样；``null`` 与缺失字段的差异天然保留，
    ``1`` 与 ``"1"`` 因类型不同而不同。不可 JSON 化时返回 None，调用方按「不判定」处理。

    Args:
        args: 工具调用参数。

    Returns:
        规范化 JSON 字符串；无法序列化时为 None。
    """
    try:
        return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        return None


def _call_key(call: ToolCall) -> tuple[str, str | None]:
    return str(call.get("name") or ""), fingerprint(call.get("args") or {})


def _extract_messages(state: Any, messages_key: str) -> list[AnyMessage]:
    """从工具节点拿到的状态里取出消息列表。"""
    if isinstance(state, dict):
        return state.get(messages_key) or []
    if isinstance(state, (list, tuple)):
        return state if isinstance(state, list) else list(state)
    return list(getattr(state, messages_key, None) or [])


@dataclass
class _Slot:
    """计数序列中的一项：同一 AIMessage 内同判定键折叠为一项。"""

    key: tuple[str, str | None]
    tool_call_ids: set[str]


def _iter_slots(messages: list[AnyMessage]) -> Iterator[_Slot]:
    """反向按需读取计数窗口，同一 assistant 批次的判定键折叠为一次。"""
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            return
        if not isinstance(message, AIMessage) or not message.tool_calls:
            continue
        batch: dict[tuple[str, str | None], _Slot] = {}
        for tool_call in message.tool_calls:
            key = _call_key(tool_call)
            if key not in batch:
                batch[key] = _Slot(key=key, tool_call_ids=set())
            if tool_call.get("id"):
                batch[key].tool_call_ids.add(tool_call["id"])
        yield from reversed(list(batch.values()))


def _scan(
    messages: Any,
    call: ToolCall,
    messages_key: str = "messages",
    allowed_limit: int | None = None,
) -> tuple[int, ToolMessage | None]:
    """返回连续出现次数与「最近一次真实执行」的返回结果。

    ``allowed_limit`` 为允许真实执行的次数；连续段内序号不小于它的调用都被拒绝，
    其 ToolMessage 是拒绝反馈而非真实结果，不能作为摘要来源。传 None 时仅计数；
    放行调用也不扫描历史结果，只有达到拒绝阈值后才查找摘要。
    """
    history = _extract_messages(messages, messages_key)
    current_key = _call_key(call)
    if current_key[1] is None:
        return 0, None

    slots = _iter_slots(history)
    call_id = call.get("id")
    # slots 从新到旧迭代；any 消费到当前调用所在 slot 后短路，剩余项从此前的调用开始。
    # 缺少 ID 或未找到时，将当前调用视为追加在历史末尾，重新迭代以统计已有历史。
    if not call_id or not any(call_id in slot.tool_call_ids for slot in slots):
        slots = _iter_slots(history)

    segment: list[_Slot] = []
    for slot in slots:
        if slot.key != current_key:
            break
        segment.append(slot)

    count = len(segment)
    if allowed_limit is None or count < allowed_limit:
        return count, None
    executed_ids = set().union(*(slot.tool_call_ids for slot in segment[-allowed_limit:]))
    for message in reversed(history):
        if isinstance(message, HumanMessage):
            break
        if isinstance(message, ToolMessage) and message.tool_call_id in executed_ids:
            return count, message
    return count, None


def _build_rejection_feedback(call: ToolCall, decision: _LoopDecision, policy: LoopGuardPolicy) -> str:
    """构造拒绝反馈：工具名、已连续次数、拒绝结论、末次返回摘要、后续引导。"""
    tool_name = call.get("name") or ""
    repeat_count = decision.repeat_count
    last_result = decision.last_result
    last_summary = str(last_result.content) if last_result is not None else "（未能取到历史返回内容）"
    if policy.result_limit > 0 and len(last_summary) > policy.result_limit:
        last_summary = last_summary[: policy.result_limit] + TRUNCATED_SUFFIX
    return (
        f"工具 {tool_name} 以相同参数已连续调用 {repeat_count} 次且未产生新结果，"
        f"本次调用已被拒绝执行（未实际调用工具）。\n"
        f"工具名：{tool_name}\n"
        f"已连续调用次数：{repeat_count}\n"
        f"最后一次真实返回内容摘要：\n{last_summary}\n"
        f"请改用其他工具、调整调用参数，或直接结束任务并向用户说明当前进展；"
        f"继续以相同参数调用将被中断。"
    )


def _build_termination_message(call: ToolCall, decision: _LoopDecision, policy: LoopGuardPolicy) -> str:
    tool_name = call.get("name") or ""
    return (
        f"{TERMINATION_MESSAGE}：工具 {tool_name} 以相同参数连续调用已达 {decision.repeat_count} 次"
        f"（真实执行 {policy.repeat_limit} 次，拒绝反馈 {policy.feedback_rounds} 次），"
        f"循环未收敛，本次任务终止。"
    )


def _rejection_payload(call: ToolCall, tool: Any) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """复刻 ``BaseTool.run`` 的回调载荷，保证 ``tool.name`` / ``tool.input`` 与真实调用同格式。"""
    serialized = {"name": call.get("name") or "", "description": getattr(tool, "description", "") or ""}
    inputs = call.get("args") or {}
    return serialized, str(inputs), inputs


def _emit_rejection_span_sync(config: dict | None, call: ToolCall, tool: Any, feedback: str) -> None:
    """同步路径：为被拒绝的调用派发一条以 ERROR 结束的工具 span。"""
    callbacks = (config or {}).get("callbacks")
    if not callbacks:
        return
    try:
        serialized, input_str, inputs = _rejection_payload(call, tool)
        manager = CallbackManager.configure(callbacks)
        run_manager = manager.on_tool_start(
            serialized,
            input_str,
            run_id=uuid4(),
            inputs=inputs,
            tool_call_id=call.get("id"),
            name=call.get("name"),
        )
        run_manager.on_tool_error(ToolLoopRejection(feedback))
    except Exception as error:  # noqa: BLE001 - span 派发失败不得影响拒绝结果
        logger.warning("[ToolLoopGuard] 拒绝调用的工具 span 派发失败: %s", error)


async def _emit_rejection_span_async(config: dict | None, call: ToolCall, tool: Any, feedback: str) -> None:
    """异步路径：语义与同步版本一致。"""
    callbacks = (config or {}).get("callbacks")
    if not callbacks:
        return
    try:
        serialized, input_str, inputs = _rejection_payload(call, tool)
        manager = AsyncCallbackManager.configure(callbacks)
        run_manager = await manager.on_tool_start(
            serialized,
            input_str,
            run_id=uuid4(),
            inputs=inputs,
            tool_call_id=call.get("id"),
            name=call.get("name"),
        )
        await run_manager.on_tool_error(ToolLoopRejection(feedback))
    except Exception as error:  # noqa: BLE001 - span 派发失败不得影响拒绝结果
        logger.warning("[ToolLoopGuard] 拒绝调用的工具 span 派发失败: %s", error)


def _decide(request: ToolCallRequest, policy: LoopGuardPolicy, messages_key: str) -> _LoopDecision:
    try:
        count, last_result = _scan(request.state, request.tool_call, messages_key, policy.repeat_limit)
    except Exception as error:  # noqa: BLE001 - 判定失败不得阻断工具调用主链路
        logger.warning("[ToolLoopGuard] 重复调用判定失败，本次按放行处理: %s", error)
        return _LoopDecision(action=ALLOW)
    repeat_count = count + 1
    if count < policy.repeat_limit:
        return _LoopDecision(action=ALLOW, repeat_count=repeat_count)
    if count < policy.repeat_limit + policy.feedback_rounds:
        return _LoopDecision(action=REJECT, repeat_count=repeat_count, last_result=last_result)
    return _LoopDecision(action=TERMINATE, repeat_count=repeat_count, last_result=last_result)


def _reject(request: ToolCallRequest, feedback: str) -> ToolMessage:
    """构造拒绝结果，并按「不计时」口径（duration=0）补齐元数据与 id。

    结果事件由链首事件 wrapper 统一派发，这里只写元数据，避免同一调用派发两次。
    """
    message = ToolMessage(
        content=feedback,
        name=request.tool_call.get("name"),
        tool_call_id=request.tool_call["id"],
        status="error",
    )
    _apply_timing_metadata(request, message, duration=0, include_description=False)
    return message


def build_loop_guard_sync_wrapper(policy: LoopGuardPolicy, messages_key: str = "messages") -> ToolCallWrapper:
    def wrapper(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        if request.tool is None:
            return execute(request)
        decision = _decide(request, policy, messages_key)
        if decision.action == TERMINATE:
            raise ToolLoopTerminationError(_build_termination_message(request.tool_call, decision, policy))
        if decision.action == REJECT:
            feedback = _build_rejection_feedback(request.tool_call, decision, policy)
            _emit_rejection_span_sync(request.runtime.config, request.tool_call, request.tool, feedback)
            return _reject(request, feedback)
        return execute(request)

    return wrapper


def build_loop_guard_async_wrapper(policy: LoopGuardPolicy, messages_key: str = "messages") -> AsyncToolCallWrapper:
    async def wrapper(
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        if request.tool is None:
            return await execute(request)
        decision = _decide(request, policy, messages_key)
        if decision.action == TERMINATE:
            raise ToolLoopTerminationError(_build_termination_message(request.tool_call, decision, policy))
        if decision.action == REJECT:
            feedback = _build_rejection_feedback(request.tool_call, decision, policy)
            await _emit_rejection_span_async(request.runtime.config, request.tool_call, request.tool, feedback)
            return _reject(request, feedback)
        return await execute(request)

    return wrapper


__all__ = [
    "LoopGuardPolicy",
    "ToolLoopTerminationError",
    "build_loop_guard_sync_wrapper",
    "build_loop_guard_async_wrapper",
]
