"""Automatic personal-memory binding for the standard SDK chat entry point."""

import hashlib
import json
import logging
import threading
import time
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage

from aidev_agent.core.tools.memory import PersonalMemoryRuntime, is_complete_ai_message, message_timestamp
from aidev_agent.utils.message_metadata import assistant_source_text, is_complete_finish_reason
from aidev_agent.utils.message_text import strip_think_blocks

logger = logging.getLogger(__name__)
MEMORY_REQUEST_TIMEOUT = 2
# 平台判定未启用或探测失败后，在该时长内不再为同一智能体与用户重复探测；启用结果不缓存。
POLICY_DISABLED_TTL = 60
POLICY_FAILURE_TTL = 30
POLICY_CACHE_MAX_ENTRIES = 4096

_policy_suppressed_until: dict[tuple, float] = {}
_policy_lock = threading.Lock()


def _policy_key(manager, username: str, agent_code: str) -> tuple:
    """返回探测抑制的缓存键，包含 manager 类型、租户与应用，避免不同租户的同名智能体互相影响。"""
    return (
        type(manager).__qualname__,
        getattr(manager, "tenant_id", None),
        getattr(manager, "app_code", None),
        agent_code,
        username,
    )


def _policy_suppressed(key: tuple) -> bool:
    """判断该键当前是否处于探测抑制期，过期条目顺带删除。"""
    with _policy_lock:
        until = _policy_suppressed_until.get(key)
        if until is None:
            return False
        if until > time.monotonic():
            return True
        del _policy_suppressed_until[key]
        return False


def _suppress_policy(key: tuple, ttl: float) -> None:
    """记录探测抑制期；条目数达到上限时先清理过期条目，仍满则淘汰最早写入的条目。"""
    now = time.monotonic()
    with _policy_lock:
        _policy_suppressed_until.pop(key, None)
        if len(_policy_suppressed_until) >= POLICY_CACHE_MAX_ENTRIES:
            for stale in [item for item, until in _policy_suppressed_until.items() if until <= now]:
                del _policy_suppressed_until[stale]
        while len(_policy_suppressed_until) >= POLICY_CACHE_MAX_ENTRIES:
            del _policy_suppressed_until[next(iter(_policy_suppressed_until))]
        _policy_suppressed_until[key] = now + ttl


def history_timestamp(data: dict) -> str | None:
    """从一条宿主历史记录中解析消息时间，返回归一化 ISO 字符串或 `None`。

    优先取 `builtin_property.source_timestamp`；非 assistant 消息可回退到 `created_at`
    （assistant 的落库时间不等于模型完成时间，故不使用），最后回退到 `timestamp`。
    """
    return (
        message_timestamp((data.get("builtin_property") or {}).get("source_timestamp"))
        or (message_timestamp(data.get("created_at")) if data.get("role") != "assistant" else None)
        or message_timestamp(data.get("timestamp"))
    )


def completed_history(history, session_id: str) -> list[dict]:
    """把宿主会话历史转换为个人记忆可用的已完成消息快照。

    仅保留文本非空的 user/assistant 消息；assistant 消息若状态未完成、含工具调用、被标记为
    非记忆来源或 `finish_reason` 不完整则跳过，并优先使用 `source_text`、剔除推理块。
    消息 ID 依次取 `builtin_property.message_id`、记录 `id`，都缺失时按会话、序号、角色和
    文本哈希生成稳定的 `host-` ID。无可解析时间、`status` 不为 `complete` 且未标记
    `memory_source_complete=True` 的 assistant 消息也会被排除。
    """
    snapshot = []
    for index, record in enumerate(history or []):
        data = record.model_dump() if hasattr(record, "model_dump") else record
        if not isinstance(data, dict) or data.get("role") not in {"user", "assistant"}:
            continue
        text = data.get("content")
        if not isinstance(text, str) or not text:
            continue
        builtin = data.get("builtin_property") or {}
        if data["role"] == "assistant" and (
            data.get("status") not in {None, "", "complete"}
            or builtin.get("tool_calls")
            or builtin.get("memory_source_complete") is False
            or not is_complete_finish_reason(builtin.get("finish_reason"))
        ):
            continue
        identity = json.dumps([session_id, index, data["role"], text], ensure_ascii=False)
        # The database primary key differs from the host/model message identity.
        message_id = str(
            builtin.get("message_id") or data.get("id") or "host-" + hashlib.sha256(identity.encode()).hexdigest()
        )
        if data["role"] == "assistant" and isinstance(builtin.get("source_text"), str):
            text = builtin["source_text"]
        if data["role"] == "assistant":
            text = strip_think_blocks(text, preserve_whitespace=True)
            if not text.strip():
                continue
        item = {"message_id": message_id, "role": data["role"], "text": text, "complete": True}
        stamp = history_timestamp(data)
        if (
            data["role"] == "assistant"
            and stamp is None
            and data.get("status") != "complete"
            and builtin.get("memory_source_complete") is not True
        ):
            continue
        if stamp is not None:
            item["timestamp"] = stamp
        snapshot.append(item)
    return snapshot


def automatic_personal_memory(manager, username: str, session_id: str, history, messages, *, agent_code: str = ""):
    """为标准 SDK 对话入口自动构建个人记忆运行时，不可用时返回 `None` 以降级为普通对话。

    要求 `agent_code`、`username`、`session_id` 有效且 `manager` 实现三个记忆接口；平台返回
    `enabled` 不为 `True` 时不启用。会合并已完成历史快照与本轮可见消息（有历史时仅补最后一条
    用户输入），并以 best-effort 模式和 `MEMORY_REQUEST_TIMEOUT` 超时创建运行时、预先生成工具。
    平台判定未启用时 `POLICY_DISABLED_TTL` 秒内、探测失败时 `POLICY_FAILURE_TTL` 秒内不再重复探测，
    因此开启记忆最多延迟该时长生效。任何异常只记录告警并返回 `None`，不阻断对话。
    """
    if not isinstance(agent_code, str) or not agent_code.strip():
        return None
    if not manager or not isinstance(username, str) or not username.strip() or not session_id:
        return None
    if not all(
        callable(getattr(manager, name, None)) for name in ["memory_schemas", "memory_tool", "complete_memory_round"]
    ):
        return None
    key = _policy_key(manager, username, agent_code)
    if _policy_suppressed(key):
        return None
    try:
        schemas = manager.memory_schemas(username=username, agent_code=agent_code, timeout=MEMORY_REQUEST_TIMEOUT)
    except Exception as error:
        _suppress_policy(key, POLICY_FAILURE_TTL)
        logger.warning("Personal memory unavailable; continuing chat: %s", type(error).__name__)
        return None
    if not isinstance(schemas, dict) or schemas.get("enabled") is not True:
        _suppress_policy(key, POLICY_DISABLED_TTL)
        return None
    try:
        records = [record.model_dump() if hasattr(record, "model_dump") else record for record in history or []]
        snapshot = completed_history(records, session_id)
        # Preserve the full host ledger; legacy hosts may omit the current user input.
        known = {(item["role"], item["message_id"]) for item in snapshot}
        # Model inputs retain DB IDs while the ledger exposes canonical source IDs.
        # Both identify existing records, including records excluded from evidence.
        known.update(
            (record.get("role"), str(identity))
            for record in records
            if isinstance(record, dict)
            for identity in [record.get("id"), (record.get("builtin_property") or {}).get("message_id")]
            if identity
        )
        visible = (
            messages if not records else [message for message in messages if isinstance(message, HumanMessage)][-1:]
        )
        for message in visible:
            role = "user" if isinstance(message, HumanMessage) else "assistant"
            if (
                not isinstance(message, (HumanMessage, AIMessage))
                or not message.id
                or not isinstance(message.content, str)
            ):
                continue
            if isinstance(message, AIMessage) and not is_complete_ai_message(message):
                continue
            if (role, message.id) not in known:
                metadata = message.response_metadata
                stamp = (
                    message_timestamp(metadata.get("source_timestamp"))
                    or message_timestamp(metadata.get("created_at"))
                    or message_timestamp(metadata.get("timestamp"))
                    or history_timestamp(message.additional_kwargs)
                )
                if role == "assistant" and stamp is None and metadata.get("memory_source_complete") is not True:
                    continue
                text = assistant_source_text(message) if role == "assistant" else message.content
                item = {"message_id": message.id, "role": role, "text": text, "complete": True}
                # Missing history time is unknown, not the time of this request.
                if stamp is not None:
                    item["timestamp"] = stamp
                snapshot.append(item)
        context = {
            "username": username,
            "agent_code": agent_code,
            "session_id": session_id,
            "session_date": session_date(records),
            "messages": snapshot,
        }
        runtime = PersonalMemoryRuntime(
            lambda config: context,
            manager=manager,
            schemas=schemas,
            best_effort=True,
            request_timeout=MEMORY_REQUEST_TIMEOUT,
            merge_state_history=False,
        )
        runtime.make_tools()
        return runtime
    except Exception as error:
        logger.warning("Personal memory unavailable; continuing chat: %s", type(error).__name__)
        return None


def session_date(history) -> str:
    """返回会话日期（`YYYY-MM-DD`）：取历史中第一条可解析时间的消息日期，无可用时间时取当前 UTC 日期。"""
    for record in history or []:
        data = record.model_dump() if hasattr(record, "model_dump") else record
        if isinstance(data, dict):
            stamp = history_timestamp(data)
            if stamp is not None:
                return datetime.fromisoformat(stamp).date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()
