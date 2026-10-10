"""Automatic personal-memory binding for the standard SDK chat entry point."""

import hashlib
import json
import logging
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, HumanMessage

from aidev_agent.core.tools.memory import PersonalMemoryRuntime

logger = logging.getLogger(__name__)
MEMORY_REQUEST_TIMEOUT = 2


def completed_history(history, session_id: str) -> list[dict]:
    snapshot = []
    for index, record in enumerate(history or []):
        data = record.model_dump() if hasattr(record, "model_dump") else record
        if not isinstance(data, dict) or data.get("role") not in {"user", "assistant"}:
            continue
        text = data.get("content")
        if not isinstance(text, str) or not text:
            continue
        if data["role"] == "assistant" and (
            data.get("status") not in {None, "", "complete"} or (data.get("builtin_property") or {}).get("tool_calls")
        ):
            continue
        identity = json.dumps([session_id, index, data["role"], text], ensure_ascii=False)
        message_id = str(data.get("id") or "host-" + hashlib.sha256(identity.encode()).hexdigest())
        snapshot.append({"message_id": message_id, "role": data["role"], "text": text, "complete": True})
    return snapshot


def automatic_personal_memory(manager, username: str, session_id: str, history, messages):
    if not manager or not isinstance(username, str) or not username.strip() or not session_id:
        return None
    if not all(
        callable(getattr(manager, name, None)) for name in ["memory_schemas", "memory_tool", "complete_memory_round"]
    ):
        return None
    try:
        schemas = manager.memory_schemas(username=username, timeout=MEMORY_REQUEST_TIMEOUT)
        snapshot = completed_history(history, session_id)
        # Preserve the full host ledger; legacy hosts may omit the current user input.
        known = {(item["role"], item["text"]) for item in snapshot}
        visible = (
            messages if not history else [message for message in messages if isinstance(message, HumanMessage)][-1:]
        )
        for message in visible:
            role = "user" if isinstance(message, HumanMessage) else "assistant"
            if (
                not isinstance(message, (HumanMessage, AIMessage))
                or not message.id
                or not isinstance(message.content, str)
            ):
                continue
            if isinstance(message, AIMessage) and message.tool_calls:
                continue
            if (role, message.content) not in known:
                snapshot.append({"message_id": message.id, "role": role, "text": message.content, "complete": True})
        context = {
            "username": username,
            "session_id": session_id,
            "session_date": session_date(history),
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
        timestamp = data.get("created_at") if isinstance(data, dict) else None
        if isinstance(timestamp, datetime):
            return timestamp.date().isoformat()
        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).date().isoformat()
            except ValueError:
                continue
    return datetime.now(timezone.utc).date().isoformat()
