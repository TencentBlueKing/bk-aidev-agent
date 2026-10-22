"""Completion metadata shared by current responses and persisted history."""

from datetime import datetime, timezone

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage

from aidev_agent.utils.message_text import strip_think_blocks


def message_timestamp(value):
    """Normalize host timestamps; malformed optional metadata must not break chat."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def assistant_source_timestamp(message, *, generate: bool = False) -> str | None:
    """Keep the original completion time on messages before event/state copies diverge."""
    metadata = message.response_metadata
    stamp = next(
        (
            value
            for key in ("source_timestamp", "created_at", "timestamp")
            if (value := message_timestamp(metadata.get(key)))
        ),
        None,
    )
    if stamp is None and generate:
        stamp = datetime.now(timezone.utc).isoformat()
    if stamp is not None:
        metadata["source_timestamp"] = stamp
    return stamp


def assistant_source_text(message) -> str:
    """Use the same source body for current evidence and ledger-free replay."""
    text = message.response_metadata.get("source_text")
    if not isinstance(text, str):
        text = message.content
    return strip_think_blocks(text, preserve_whitespace=True)


def is_complete_finish_reason(value) -> bool:
    return str(value or "").lower() not in {
        "length",
        "max_tokens",
        "content_filter",
        "incomplete",
        "cancelled",
        "stopped",
        "error",
        "tool_calls",
        "function_call",
    }


class AssistantCompletionTimestamp(BaseCallbackHandler):
    """Stamp the assembled provider output before stream tracers copy or publish it."""

    run_inline = True

    def __init__(self, *, pending_transform: bool = False):
        self.pending_transform = pending_transform

    def on_llm_end(self, response, **kwargs):
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if isinstance(message, AIMessage):
                    assistant_source_timestamp(message, generate=True)
                    if self.pending_transform:
                        message.response_metadata.update(memory_source_pending=True, memory_source_complete=False)


def finalize_memory_source(message, *, accepted: bool = True) -> dict | None:
    """Settle eligibility only after the caller accepts the transformed output."""
    if not isinstance(message, AIMessage) or not message.response_metadata.pop("memory_source_pending", False):
        return None
    text = strip_think_blocks(message.content, preserve_whitespace=True) if isinstance(message.content, str) else ""
    complete = bool(
        accepted
        and not message.tool_calls
        and not message.invalid_tool_calls
        and text.strip()
        and is_complete_finish_reason(message.response_metadata.get("finish_reason"))
    )
    message.response_metadata["memory_source_complete"] = complete
    result = {"message_id": message.id, "memory_source_complete": complete}
    if complete:
        message.response_metadata["source_text"] = text
        result["source_text"] = message.response_metadata["source_text"]
        result["source_timestamp"] = assistant_source_timestamp(message, generate=True)
    return result
