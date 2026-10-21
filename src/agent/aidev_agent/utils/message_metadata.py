"""Completion metadata shared by current responses and persisted history."""


def is_complete_finish_reason(value) -> bool:
    return str(value or "").lower() not in {"length", "max_tokens", "content_filter", "incomplete"}
