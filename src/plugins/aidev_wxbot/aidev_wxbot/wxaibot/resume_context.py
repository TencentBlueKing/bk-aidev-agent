"""Resolve the original turn from the matching persisted interrupt, never create one."""

import json


def original_interrupt_turn(manager, session_code: str, interrupt_id: str) -> str:
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
                break
        if not isinstance(content, dict):
            break
        interrupts = content.get("interrupts") or (content.get("outcome") or {}).get("interrupts") or []
        turn_id = (item.get("property") or {}).get("turn_id")
        if turn_id and any(isinstance(i, dict) and i.get("id") == interrupt_id for i in interrupts):
            return turn_id
        break
    raise ValueError("Original interrupt turn is missing or superseded")
