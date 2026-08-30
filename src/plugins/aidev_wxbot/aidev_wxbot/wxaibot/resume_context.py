"""Resolve the original turn from the matching persisted interrupt, never create one."""

import json


def latest_interrupt_record(manager, session_code: str) -> dict | None:
    for item in reversed(manager.list_session_contents(session_code)):
        if item.get("role") == "user":
            # A newer user input must not be mistaken for the interrupted turn.
            break
        if item.get("role") != "interrupt":
            continue
        content = item.get("content")
        if isinstance(content, str):
            try:
                content = json.loads(content)
            except (ValueError, TypeError):
                raise ValueError("Invalid interrupt content") from None
        if not isinstance(content, dict):
            raise ValueError("Invalid interrupt content")
        return {**item, "content": content}
    return None


def original_interrupt_record(manager, session_code: str, interrupt_id: str) -> dict:
    item = latest_interrupt_record(manager, session_code)
    if item:
        content = item["content"]
        interrupts = content.get("interrupts") or (content.get("outcome") or {}).get("interrupts") or []
        if (item.get("property") or {}).get("turn_id") and any(
            isinstance(i, dict) and i.get("id") == interrupt_id for i in interrupts
        ):
            return item
    raise ValueError("Original interrupt turn is missing or superseded")


def original_interrupt_turn(manager, session_code: str, interrupt_id: str) -> str:
    record = original_interrupt_record(manager, session_code, interrupt_id)
    return record["property"]["turn_id"]
