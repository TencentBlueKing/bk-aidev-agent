"""Render persisted approval decisions, never infer approval from a resume event."""

from aidev_agent.services.agent.approval import ApprovalStateHandler
from aidev_bkplugin.services.agent_session import SessionManager

from .approval_cards import ApprovalCancelAction, approval_task_id, build_approval_result_card


def approval_result_messages(session_code: str, interrupt_ids: list[str], username: str) -> list[dict]:
    """Read as the original user and match the exact resumed approvals, including old ones.

    A session can already be waiting for another approval or question by the time
    this consumer runs. Reading only its latest interrupt would report the wrong
    decision. No callback tokens, candidate approvers or tool arguments leave here.
    """
    if not interrupt_ids:
        return []
    records = SessionManager(username=username).list_session_contents(session_code)
    if not isinstance(records, list):
        raise ValueError("Invalid approval history response")
    requested = set(interrupt_ids)
    found = set()
    decisions = {}
    for record in records:
        if not isinstance(record, dict) or record.get("role") != "interrupt":
            continue
        if record.get("session_code", session_code) != session_code:
            continue
        interrupts = ApprovalStateHandler._extract_interrupts_from_content(record.get("content"))
        for interrupt in interrupts:
            if not isinstance(interrupt, dict) or interrupt.get("id") not in requested:
                continue
            found.add(interrupt["id"])
            if interrupt.get("reason") != "aidev:tool_approval":
                continue
            status = ApprovalStateHandler._extract_builtin_property(record).get("approve_result")
            if status not in ("approved", "rejected", "cancelled"):
                raise ValueError("Approval decision is not persisted yet")
            decision = {"approve_result": status, "interrupts": [interrupt]}
            previous = decisions.setdefault(interrupt["id"], decision)
            if previous != decision:
                raise ValueError("Conflicting approval decision records")
    if requested - found:
        raise ValueError("Resumed interrupt history is not available yet")

    messages = []
    for interrupt_id in sorted(decisions):
        result = decisions[interrupt_id]
        if result["approve_result"] == "cancelled":
            continue  # Cancellation is already acknowledged on the clicked card.
        action = ApprovalCancelAction(session_code, interrupt_id)
        card = build_approval_result_card(action, approval_task_id(action), result=result)
        if card is None:
            raise ValueError("Approval decision has no renderable ticket")
        # This is a new notice, not a remote replacement of the original card.
        card.pop("task_id", None)
        messages.append({"msgtype": "template_card", "template_card": card})
    return messages
