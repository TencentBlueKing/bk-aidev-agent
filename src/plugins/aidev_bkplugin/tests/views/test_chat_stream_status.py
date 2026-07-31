# -*- coding: utf-8 -*-
"""Chat SSE 异常时的会话终态回归测试。"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.parametrize("error", [RuntimeError("生产者心跳超时"), SystemExit("worker abort")])
def test_unexpected_stream_error_does_not_mark_session_finished(monkeypatch, error):
    from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
    from aidev_bkplugin.views.chat import ChatCompletionViewSet

    def failing_stream():
        yield "chunk"
        raise error

    monkeypatch.setattr(GeneratorStreamingHelper, "is_cancelled", lambda _session_code: False)
    event_handler = MagicMock()
    stream = ChatCompletionViewSet()._wrap_streaming_with_status(
        failing_stream(), event_handler, session_code="session-1"
    )

    assert next(stream) == "chunk"
    with pytest.raises(type(error)):
        next(stream)
    event_handler.set_streaming_finished.assert_not_called()


def test_normal_stream_marks_session_finished(monkeypatch):
    from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
    from aidev_bkplugin.views.chat import ChatCompletionViewSet

    monkeypatch.setattr(GeneratorStreamingHelper, "is_cancelled", lambda _session_code: False)
    event_handler = MagicMock()

    assert list(
        ChatCompletionViewSet()._wrap_streaming_with_status(iter(["chunk"]), event_handler, session_code="session-1")
    ) == ["chunk"]
    event_handler.set_streaming_finished.assert_called_once_with()
