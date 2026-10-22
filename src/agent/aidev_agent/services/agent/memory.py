"""Automatic personal-memory binding for the standard SDK chat entry point."""

import hashlib
import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage

from aidev_agent.core.tools.memory import PersonalMemoryRuntime, is_complete_ai_message, message_timestamp
from aidev_agent.utils.message_metadata import assistant_source_text, is_complete_finish_reason
from aidev_agent.utils.message_text import strip_think_blocks

logger = logging.getLogger(__name__)
MEMORY_REQUEST_TIMEOUT = 2


def history_timestamp(data: dict) -> str | None:
    return (
        message_timestamp((data.get("builtin_property") or {}).get("source_timestamp"))
        or (message_timestamp(data.get("created_at")) if data.get("role") != "assistant" else None)
        or message_timestamp(data.get("timestamp"))
    )


def completed_history(history, session_id: str) -> list[dict]:
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
    if not isinstance(agent_code, str) or not agent_code.strip():
        return None
    if not manager or not isinstance(username, str) or not username.strip() or not session_id:
        return None
    if not all(
        callable(getattr(manager, name, None)) for name in ["memory_schemas", "memory_tool", "complete_memory_round"]
    ):
        return None
    try:
        schemas = manager.memory_schemas(username=username, agent_code=agent_code, timeout=MEMORY_REQUEST_TIMEOUT)
        if not isinstance(schemas, dict) or schemas.get("enabled") is not True:
            return None
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
    for record in history or []:
        data = record.model_dump() if hasattr(record, "model_dump") else record
        if isinstance(data, dict):
            stamp = history_timestamp(data)
            if stamp is not None:
                return datetime.fromisoformat(stamp).date().isoformat()
    return datetime.now(timezone.utc).date().isoformat()
