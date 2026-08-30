"""AG-UI 工具审批到企微模板卡片的转换。"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import zlib
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from aidev_agent.core.nodes.tool.approval_wrapper import TOOL_APPROVAL_REASON
from aidev_bkplugin.services.agent_helpers import AgentHelper

from .context import _normalize_url

_CANCEL_EVENT_PREFIX = "approval_cancel:"
_MAX_ACTION_FIELD_LENGTH = 256


@dataclass(frozen=True, slots=True)
class ApprovalCancelAction:
    """企微取消审批按钮携带的最小操作上下文。"""

    session_code: str
    interrupt_id: str


def build_pending_approval_card(event: dict, session_code: str) -> dict[str, Any] | None:
    """把第一个待审批中断转成企微按钮交互卡片。

    当前 Agent 每次只挂起一个审批 target；若协议未来同时返回多个中断，后续中断会在
    本次审批恢复后依次出现，因此卡片只展示第一个待处理项。
    """
    outcome = event.get("outcome") or {}
    if not isinstance(outcome, dict) or outcome.get("type") != "interrupt":
        return None

    for interrupt in outcome.get("interrupts") or []:
        if not isinstance(interrupt, dict) or interrupt.get("reason") != TOOL_APPROVAL_REASON:
            continue
        return _build_pending_card(interrupt, session_code)
    return None


def approval_task_id(action: ApprovalCancelAction) -> str:
    digest = hashlib.sha256(f"{action.session_code}\0{action.interrupt_id}".encode()).hexdigest()[:24]
    return f"approval_{digest}"


def encode_cancel_event_key(action: ApprovalCancelAction) -> str:
    """生成无持久缓存依赖的按钮 key；平台仍会按点击用户做对象级鉴权。"""
    payload = json.dumps([action.session_code, action.interrupt_id], ensure_ascii=False, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(zlib.compress(payload.encode())).decode().rstrip("=")
    return f"{_CANCEL_EVENT_PREFIX}{encoded}"


def decode_cancel_event_key(event_key: str) -> ApprovalCancelAction | None:
    """解析本服务生成的取消按钮 key；非审批按钮返回 ``None``。"""
    if not event_key.startswith(_CANCEL_EVENT_PREFIX):
        return None
    encoded = event_key.removeprefix(_CANCEL_EVENT_PREFIX)
    try:
        compressed = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(compressed, 2049)
        if len(raw) > 2048 or decompressor.unconsumed_tail or not decompressor.eof:
            return None
        values = json.loads(raw)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError, zlib.error):
        return None
    if not isinstance(values, list) or len(values) != 2 or not all(isinstance(value, str) for value in values):
        return None
    session_code, interrupt_id = values
    if not session_code or not interrupt_id:
        return None
    if len(session_code) > _MAX_ACTION_FIELD_LENGTH or len(interrupt_id) > _MAX_ACTION_FIELD_LENGTH:
        return None
    return ApprovalCancelAction(session_code=session_code, interrupt_id=interrupt_id)


def build_cancel_result_card(action: ApprovalCancelAction, task_id: str, *, result: Any) -> dict[str, Any] | None:
    """用平台返回的原审批详情更新操作区；信息不完整时保留企微原卡片。

    ``ok=False`` 也可能表示审批已经结束，应展示实际结果而非“取消失败”。
    不用取消按钮的点击人或候选 approvers 冒充实际审批人。
    """
    if not isinstance(result, dict) or task_id != approval_task_id(action):
        return None
    status = result.get("approve_result")
    if not isinstance(status, str):
        return None
    status_text = {
        "cancelled": "已取消",
        "approved": "审批已通过",
        "rejected": "审批已拒绝",
    }.get(status)
    if status_text is None:
        return None

    interrupts = result.get("interrupts")
    if not isinstance(interrupts, list):
        return None
    for interrupt in interrupts:
        if not isinstance(interrupt, dict) or interrupt.get("id") != action.interrupt_id:
            continue
        metadata = interrupt.get("metadata")
        if (
            interrupt.get("reason") != TOOL_APPROVAL_REASON
            or not isinstance(metadata, dict)
            or not isinstance(metadata.get("ticket"), dict)
        ):
            return None
        card = _build_pending_card(interrupt, action.session_code)
        # 通知卡支持原有详情字段，用不可点击的底部文字代替取消按钮。
        card["card_type"] = "text_notice"
        card.pop("button_list", None)
        card["jump_list"] = [{"type": 0, "title": status_text}]
        return card
    return None


def _build_pending_card(interrupt: dict, session_code: str) -> dict[str, Any]:
    metadata = interrupt.get("metadata") or {}
    ticket = metadata.get("ticket") or {} if isinstance(metadata, dict) else {}
    if not isinstance(ticket, dict):
        ticket = {}

    title = _plain_text(ticket.get("title") or interrupt.get("message") or "工具执行需要人工审批", 128)
    ticket_sn = _plain_text(ticket.get("sn") or interrupt.get("ticketSn") or "", 64)
    submit_time = _plain_text(ticket.get("submit_time") or "", 64)
    approval_url = _safe_url(ticket.get("url"))
    session_url = _safe_url(AgentHelper.build_session_detail_url(session_code))

    card: dict[str, Any] = {
        "card_type": "button_interaction",
        "main_title": {
            "title": title,
            "desc": "点击卡片查看单据详情" if approval_url else "请在审批系统中处理",
        },
        "sub_title_text": "审批完成后系统将继续执行。",
    }
    horizontal_content_list = []
    if ticket_sn:
        horizontal_content_list.append({"keyname": "单据编号", "value": ticket_sn})
    if submit_time:
        horizontal_content_list.append({"keyname": "提交时间", "value": submit_time})
    if horizontal_content_list:
        card["horizontal_content_list"] = horizontal_content_list

    detail_url = approval_url or session_url
    if detail_url:
        card["card_action"] = {"type": 1, "url": detail_url}

    interrupt_id = str(interrupt.get("id") or "")
    if session_code and interrupt_id:
        action = ApprovalCancelAction(session_code=session_code, interrupt_id=interrupt_id)
        card["button_list"] = [
            {
                "text": "取消审批",
                "style": 2,
                "key": encode_cancel_event_key(action),
            }
        ]
        card["task_id"] = approval_task_id(action)
    return card


def _plain_text(value: Any, limit: int) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))
    return " ".join(text.split())[:limit]


def _safe_url(value: Any) -> str:
    raw_url = str(value or "")
    if not raw_url:
        return ""
    parsed = urlsplit(raw_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return _normalize_url(raw_url)
