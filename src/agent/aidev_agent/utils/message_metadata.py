"""Completion metadata shared by current responses and persisted history."""

from datetime import datetime, timezone

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage


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
    return text.strip()


def is_complete_finish_reason(value) -> bool:
    return str(value or "").lower() not in {
        "length",
        "max_tokens",
        "content_filter",
        "incomplete",
        "cancelled",
        "stopped",
        "error",
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


def finalize_memory_source(message) -> dict | None:
    """Settle eligibility using the actual transformed output, never raw-text guesses."""
    if not isinstance(message, AIMessage) or not message.response_metadata.pop("memory_source_pending", False):
        return None
    complete = bool(
        not message.tool_calls
        and isinstance(message.content, str)
        and message.content.strip()
        and is_complete_finish_reason(message.response_metadata.get("finish_reason"))
    )
    message.response_metadata["memory_source_complete"] = complete
    result = {"message_id": message.id, "memory_source_complete": complete}
    if complete:
        message.response_metadata["source_text"] = message.content.strip()
        result["source_text"] = message.response_metadata["source_text"]
    return result
