"""取消由操作发起方续流；审批通过和拒绝保留后台自动续流。"""

from unittest.mock import MagicMock

import pytest
from aidev_bkplugin.services import approval_resume as mod


@pytest.mark.parametrize("status", ["cancelled", "approved", "rejected"])
def test_polling_does_not_duplicate_explicit_cancellation(monkeypatch, status):
    handler = MagicMock()
    handler.check_resume.return_value = True
    handler.fetch_approve_result.return_value = {"approve_result": status}
    monkeypatch.setattr(mod, "ApprovalStateHandler", MagicMock(return_value=handler))
    builder = MagicMock()
    executor = MagicMock()
    executor.return_value.execute_with_save.return_value = iter([])
    monkeypatch.setattr(mod, "AgentBuilder", builder)
    monkeypatch.setattr(mod, "AgentExecutor", executor)
    monkeypatch.setattr(mod, "SessionManager", MagicMock())
    mod._approval_resume_worker(
        "session-1", "alice", "graph-1", [{"id": "approval-1", "reason": "aidev:tool_approval"}]
    )
    assert builder.call_count == (0 if status == "cancelled" else 1)
    assert executor.return_value.execute_with_save.call_count == (0 if status == "cancelled" else 1)
    if status == "cancelled":
        return
    kwargs = executor.return_value.execute_with_save.call_args.args[1]
    assert kwargs.caller_bk_app_code == "bkaidev"
    assert kwargs.caller_bk_biz_env == "domestic_biz"
    assert kwargs.caller_order_type == "ai_chat"
    assert kwargs.executor == "alice"
    assert kwargs.caller_executor == "alice"
