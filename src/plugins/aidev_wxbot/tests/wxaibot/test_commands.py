"""企业微信会话控制指令测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_wxbot.wxaibot.constants import (
    HELP_MESSAGE,
    NEW_CONVERSATION_MESSAGE,
    NO_ACTIVE_CONVERSATION_MESSAGE,
    STOP_CONVERSATION_MESSAGE,
)
from aidev_wxbot.wxaibot.stream import consume_chat_stream
from aidev_wxbot.wxaibot.views import AgentSession, WxAiBotViewSet


def _stream_content(response: dict) -> tuple[str, bool]:
    stream = response["stream"]
    return stream["content"], stream["finish"]


class TestSessionCommands:
    def test_help_returns_command_summary_without_starting_agent(self):
        view = WxAiBotViewSet()

        response, remaining = view._handle_single_chat("/help", "stream-help", SimpleNamespace(group_id="e2e-user"))

        assert remaining == ""
        assert _stream_content(response) == (HELP_MESSAGE, True)

    def test_new_alias_creates_a_fresh_session(self, monkeypatch):
        manager = MagicMock()
        manager.get.side_effect = AgentSession.DoesNotExist
        monkeypatch.setattr(AgentSession, "objects", manager)
        view = WxAiBotViewSet()

        response, remaining = view._handle_single_chat("/new", "stream-new", SimpleNamespace(group_id="e2e-user"))

        assert remaining == ""
        assert _stream_content(response) == (NEW_CONVERSATION_MESSAGE, True)
        created = manager.create.call_args.kwargs
        assert created["group_id"] == "e2e-user"
        assert created["thread_id"].startswith("e2e-user_")

    def test_stop_requests_cross_process_cancellation(self, monkeypatch):
        session = SimpleNamespace(
            thread_id="e2e-user_thread",
            active_session_code="platform-session-code",
            refresh_from_db=MagicMock(),
        )
        manager = MagicMock()
        manager.get.return_value = session
        monkeypatch.setattr(AgentSession, "objects", manager)
        handler = MagicMock()
        factory = MagicMock()
        factory.get.return_value = handler
        monkeypatch.setattr("aidev_wxbot.wxaibot.views.message_handler_factory", factory)
        cancel = MagicMock(return_value=True)
        monkeypatch.setattr("aidev_wxbot.wxaibot.views.GeneratorStreamingHelper.cancel", cancel)
        view = WxAiBotViewSet()

        response, remaining = view._handle_single_chat("/stop", "stream-stop", SimpleNamespace(group_id="e2e-user"))

        assert remaining == ""
        assert _stream_content(response) == (STOP_CONVERSATION_MESSAGE, True)
        cancel.assert_called_once_with("platform-session-code", message_handler=handler)

    def test_stop_without_session_is_idempotent(self, monkeypatch):
        manager = MagicMock()
        manager.get.side_effect = AgentSession.DoesNotExist
        monkeypatch.setattr(AgentSession, "objects", manager)
        view = WxAiBotViewSet()

        response = view._stop_conversation("e2e-user", "stream-stop")

        assert _stream_content(response) == (NO_ACTIVE_CONVERSATION_MESSAGE, True)

    @pytest.mark.parametrize("command", ["/help", "/new", "/stop"])
    def test_group_mention_fallback_routes_commands(self, monkeypatch, command):
        expected = {"/help": HELP_MESSAGE, "/new": NEW_CONVERSATION_MESSAGE, "/stop": STOP_CONVERSATION_MESSAGE}
        view = WxAiBotViewSet()
        monkeypatch.setattr(
            view,
            "_new_conversation",
            lambda _group_id, stream_id: {
                "msgtype": "stream",
                "stream": {"id": stream_id, "finish": True, "content": NEW_CONVERSATION_MESSAGE},
            },
        )
        monkeypatch.setattr(
            view,
            "_stop_conversation",
            lambda _group_id, stream_id: {
                "msgtype": "stream",
                "stream": {"id": stream_id, "finish": True, "content": STOP_CONVERSATION_MESSAGE},
            },
        )

        response, remaining = view._process_mention_fallback(
            f"@机器人 {command}", "stream-group", SimpleNamespace(group_id="e2e-group")
        )

        assert remaining == ""
        assert _stream_content(response) == (expected[command], True)


def test_cancelled_agent_stream_emits_visible_terminal_frame():
    class RabbitMQStub:
        def __init__(self):
            self.messages = []

        def declare_queue(self, *_args, **_kwargs):
            return True

        def publish_message(self, _exchange, _queue_name, message):
            self.messages.append(message)
            return True

    rabbitmq = RabbitMQStub()
    generator = iter(['data: {"type":"RUN_FINISHED","runId":"cancelled"}\n\n'])

    consume_chat_stream(generator, "stream_9999999999", 0, rabbitmq)

    assert rabbitmq.messages[-1]["content"] == "生成已停止"
    assert rabbitmq.messages[-1]["is_finish"] is True
