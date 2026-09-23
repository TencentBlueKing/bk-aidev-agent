# -*- coding: utf-8 -*-
"""AG-UI 终态回写状态单测。"""

from unittest.mock import MagicMock

from ag_ui.core import EventType, RunErrorEvent

from aidev_agent.services.event_handlers.base import BaseSessionWriter


class _TestSessionWriter(BaseSessionWriter):
    """测试用最小会话回写器。"""

    def _do_create_content(self, payload, headers):  # noqa: ARG002
        return None


def test_run_error_persists_error_status():
    """RUN_ERROR 的落库状态应与 AG-UI 前端的 error 状态一致。"""
    writer = _TestSessionWriter(session_code="session-error")
    writer._create_session_content = MagicMock()

    writer.handle_run_error(RunErrorEvent(type=EventType.RUN_ERROR, message="执行失败"))

    payload = writer._create_session_content.call_args.kwargs
    assert payload["role"] == "assistant"
    assert payload["status"] == "error"
