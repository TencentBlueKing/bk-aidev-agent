# -*- coding: utf-8 -*-
"""interrupt_manager 读路径工具（43-03 迁移承载）。

本模块承载迁移自 ``core/ag_ui/utils.py:762-827`` 的两个中断读取工具：

- :func:`unwrap_interrupt_source` —— 从 RUN_FINISHED 事件解包出 ``interrupt[0]``。
- :func:`get_interrupt_value` —— 从 interrupt 对象/dict 按多个候选 key 查找值，
  保留多候选嵌套（metadata.ticket / approval / target / execution）兼容历史 DB 记录。

``camel_to_snake`` 等其余 AG-UI 工具保留在 ``core/ag_ui/utils.py``（未迁移），
本包只承载中断读取路径。

Harness 依赖方向：本模块仅依赖标准库 ``typing``，无跨层 import。
"""

from __future__ import annotations

from typing import Any


def unwrap_interrupt_source(source: Any) -> Any:  # nosemgrep: aidev-no-bare-any
    """从 RUN_FINISHED 事件中解包出 interrupt[0]。

    Args:
        source: RUN_FINISHED 事件 dict 或任意来源。

    Returns:
        解包后的 ``interrupt[0]``；若结构不识别则原样返回 ``source``。
    """
    if not isinstance(source, dict) or source.get("type") != "RUN_FINISHED":
        return source

    outcome = source.get("outcome")
    if not isinstance(outcome, dict) or outcome.get("type") != "interrupt":
        return source

    interrupts = outcome.get("interrupts") or []
    if interrupts:
        return interrupts[0]
    return source


def get_interrupt_value(source: Any, *keys: str) -> Any:  # nosemgrep: aidev-no-bare-any
    """从 interrupt 对象/dict 中按多个候选 key 查找值。

    读路径保留多候选兼容历史 DB 记录：优先在 ``metadata.ticket`` /
    ``metadata.approval`` / ``metadata.target`` / ``metadata.execution`` 嵌套块
    查找，其次 ``metadata`` 顶层，再次 source 顶层 / 对象属性。

    Args:
        source: interrupt 来源（RUN_FINISHED 事件 / LangGraph Interrupt 对象 / dict）。
        *keys: 候选 key 列表，按序查找。

    Returns:
        命中的值；全部未命中返回 ``None``。
    """
    source = unwrap_interrupt_source(source)
    # LangGraph Interrupt 对象：实际 payload 在 source.value 中，
    # 需要解包后才能按 dict 方式查找 callbackToken、metadata 等字段
    original_source = source
    if not isinstance(source, dict) and hasattr(source, "value"):
        inner = source.value
        if isinstance(inner, dict):
            source = inner

    metadata = {}
    raw_metadata = source.get("metadata") if isinstance(source, dict) else getattr(source, "metadata", None)
    if isinstance(raw_metadata, dict):
        metadata = raw_metadata

    nested_candidates = []
    if isinstance(metadata.get("ticket"), dict):
        nested_candidates.append(metadata["ticket"])
    if isinstance(metadata.get("approval"), dict):
        nested_candidates.append(metadata["approval"])
    if isinstance(metadata.get("target"), dict):
        nested_candidates.append(metadata["target"])
    if isinstance(metadata.get("execution"), dict):
        nested_candidates.append(metadata["execution"])

    for candidate in nested_candidates:
        for key in keys:
            if key in candidate and candidate[key] is not None:
                return candidate[key]

    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]

    for key in keys:
        if isinstance(source, dict):
            if key in source and source[key] is not None:
                return source[key]
        else:
            value = getattr(source, key, None)
            if value is not None:
                return value

    # 兜底：对于 Interrupt 对象（source 已被替换为 value），
    # 仍尝试从原始对象的属性中查找（如 Interrupt.id）
    if original_source is not source:
        for key in keys:
            value = getattr(original_source, key, None)
            if value is not None:
                return value
    return None


def interrupt_id_of(intr: Any) -> str | None:
    """提取 interrupt 对象/值形态的 id（归一化前的原始对象安全）。

    优先 ``intr.id``（LangGraph Interrupt 真实 id，replay 稳定），次取
    ``value.id`` / ``value.interruptId``（旧记录兼容）。无 id 返回 None。
    """
    value = getattr(intr, "value", intr)
    if isinstance(value, dict):
        return getattr(intr, "id", None) or value.get("id") or value.get("interruptId") or None
    return getattr(intr, "id", None) or None


def terminal_interrupt_ids_from_messages(messages: Any) -> set[str]:  # nosemgrep: aidev-no-bare-any
    """从 DB 统一消息模型（messages）推导已终态 interrupt id 集合。

    迁移自 ``core/ag_ui/agent.py`` 的 ``_terminal_interrupt_ids`` 逻辑（46-03，
    on_resume 改收 messages 后由其内部推导未解决中断）。以 interruptmessage
    记录（chat_history 落库形态）的终态标记识别「已完成」：``outcome.type ==
    "success"``（ask_user 回答/跳过路径改写）或元素 ``metadata.status ∈
    {resolved, cancelled, approved, rejected}``。messages 为空返回空集合。
    """
    terminal: set[str] = set()
    if not messages:
        return terminal
    terminal_statuses = {"resolved", "cancelled", "approved", "rejected"}
    for msg in messages:
        content = getattr(msg, "content", None)
        if not isinstance(content, dict):
            continue
        outcome = content.get("outcome")
        if not isinstance(outcome, dict):
            continue
        interrupts = outcome.get("interrupts")
        if not isinstance(interrupts, list):
            continue
        outcome_success = outcome.get("type") == "success"
        for intr in interrupts:
            if not isinstance(intr, dict):
                continue
            intr_id = intr.get("id")
            if not intr_id:
                continue
            status = (intr.get("metadata") or {}).get("status")
            if outcome_success or status in terminal_statuses:
                terminal.add(intr_id)
    return terminal


__all__ = [
    "unwrap_interrupt_source",
    "get_interrupt_value",
    "interrupt_id_of",
    "terminal_interrupt_ids_from_messages",
]
