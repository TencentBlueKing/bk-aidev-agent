"""Flow 失败节点重试/跳过卡片：签名绑定与首个可操作失败节点选取。"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any
from urllib.parse import urlsplit

from aidev_bkplugin.services.agent_helpers import AgentHelper
from django.core import signing

from .constants import CARD_SIGNATURE_MAX_AGE
from .context import _normalize_url

_PREFIX = "flow_node:"
_SALT = "aidev.wxbot.flow_node.v1"
_MAX_ACTION_FIELD_LENGTH = 256
_FAILED_NODE_STATES = frozenset({"FAILED"})
_OPERATIONS = frozenset({"retry", "skip"})


@dataclass(frozen=True, slots=True)
class FlowNodeAction:
    """企微重试/跳过按钮携带的最小操作上下文。"""

    session_code: str
    task_id: str
    node_id: str
    operation: str
    node_name: str = ""
    target: str = field(default="", compare=False)


def _node_actions(node: dict) -> tuple[bool, bool]:
    """读取节点 retryable/skippable；两字段都缺失时按均可操作兜底。"""
    has_retry = "retryable" in node
    has_skip = "skippable" in node
    if not has_retry and not has_skip:
        return True, True
    return bool(node.get("retryable")), bool(node.get("skippable"))


def pick_first_actionable_failed_node(nodes) -> tuple[str, dict, bool, bool] | None:
    """按平台节点顺序取第一个可重试或可跳过的 FAILED 节点。"""
    if not isinstance(nodes, dict):
        return None
    for raw_id, info in nodes.items():
        if not isinstance(info, dict) or info.get("state") not in _FAILED_NODE_STATES:
            continue
        node_id = str(info.get("id") or raw_id or "")
        if not node_id:
            continue
        retryable, skippable = _node_actions(info)
        if retryable or skippable:
            return node_id, info, retryable, skippable
    return None


def flow_card_task_id(action: FlowNodeAction) -> str:
    digest = hashlib.sha256(f"{action.session_code}\0{action.task_id}\0{action.node_id}".encode()).hexdigest()[:24]
    return f"flow_{digest}"


def encode_flow_event_key(action: FlowNodeAction) -> str:
    return _PREFIX + signing.dumps(asdict(action), salt=_SALT, compress=True)


def decode_flow_event_key(key: str) -> FlowNodeAction | None:
    if not isinstance(key, str) or not key.startswith(_PREFIX) or len(key) > 2048:
        return None
    try:
        data = signing.loads(key[len(_PREFIX) :], salt=_SALT, max_age=CARD_SIGNATURE_MAX_AGE)
        action = FlowNodeAction(**data)
    except (signing.BadSignature, ValueError, TypeError):
        return None
    values = asdict(action)
    if not all(isinstance(value, str) and len(value) <= _MAX_ACTION_FIELD_LENGTH for value in values.values()):
        return None
    if not action.session_code or not action.task_id or not action.node_id:
        return None
    if action.operation not in _OPERATIONS:
        return None
    return action


def bind_flow_target(card: dict, target: str) -> dict:
    """把按钮签名绑定到原会话接收方，避免转发后改写回复目标。"""
    result = copy.deepcopy(card)
    for button in result.get("button_list") or []:
        action = decode_flow_event_key(button.get("key", ""))
        if action is not None:
            button["key"] = encode_flow_event_key(replace(action, target=target))
    return result


def build_flow_action_card(*, session_code: str, task_id: str, nodes) -> dict[str, Any] | None:
    """任务失败后，为第一个可操作失败节点生成重试/跳过卡片。"""
    if not session_code or not task_id or task_id == "未知":
        return None
    picked = pick_first_actionable_failed_node(nodes)
    if picked is None:
        return None
    node_id, info, retryable, skippable = picked
    node_name = _plain_text(info.get("name") or node_id, 64)
    session_url = _safe_url(AgentHelper.build_session_detail_url(session_code))
    base = FlowNodeAction(
        session_code=session_code,
        task_id=str(task_id),
        node_id=node_id,
        operation="retry",
        node_name=node_name,
    )
    card: dict[str, Any] = {
        "card_type": "button_interaction",
        "main_title": {
            "title": "节点执行失败",
            "desc": node_name,
        },
        "sub_title_text": "可重试或跳过该节点后继续流程。",
        "horizontal_content_list": [
            {"keyname": "任务ID", "value": _plain_text(task_id, 64)},
            {"keyname": "节点", "value": node_name},
        ],
        "task_id": flow_card_task_id(base),
    }
    card["card_action"] = {"type": 1, "url": session_url} if session_url else {"type": 0}
    buttons = []
    if retryable:
        buttons.append(
            {
                "text": "重试",
                "style": 1,
                "key": encode_flow_event_key(replace(base, operation="retry")),
            }
        )
    if skippable:
        buttons.append(
            {
                "text": "跳过",
                "style": 2,
                "key": encode_flow_event_key(replace(base, operation="skip")),
            }
        )
    if not buttons:
        return None
    card["button_list"] = buttons
    return card


def build_flow_action_result_card(action: FlowNodeAction, task_id: str, *, ok: bool) -> dict[str, Any] | None:
    """点击后把操作区换成不可点的结果文案。"""
    if task_id != flow_card_task_id(action):
        return None
    if ok:
        label = "已重试" if action.operation == "retry" else "已跳过"
    else:
        label = "操作失败"
    session_url = _safe_url(AgentHelper.build_session_detail_url(action.session_code))
    node_name = _plain_text(action.node_name or action.node_id, 64)
    card: dict[str, Any] = {
        "card_type": "text_notice",
        "main_title": {
            "title": "节点执行失败",
            "desc": node_name,
        },
        "sub_title_text": f"已选择{label}。",
        "horizontal_content_list": [
            {"keyname": "任务ID", "value": _plain_text(action.task_id, 64)},
            {"keyname": "节点", "value": node_name},
        ],
        "jump_list": [{"type": 0, "title": label}],
        "task_id": task_id,
    }
    card["card_action"] = {"type": 1, "url": session_url} if session_url else {"type": 0}
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
