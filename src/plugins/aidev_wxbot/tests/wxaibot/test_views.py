"""wxbot 视图层的后台执行、内置命令与会话终态测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.services.messages_handler import ConsumerPreemptedError
from aidev_wxbot.wxaibot.constants import HELP_REPLY, STOP_NO_ACTIVE_REPLY
from aidev_wxbot.wxaibot.views import WxAiBotViewSet, WxBotAgentRequest


def test_reply_text_submits_prepared_request_with_username():
    view = object.__new__(WxAiBotViewSet)
    request = WxBotAgentRequest("query", "stream-1", "user-1", "group-1")
    view.prepare_agent_request = MagicMock(return_value=(None, request))
    view._start_async_processing = MagicMock(return_value=True)

    response = view._reply_text({})

    view._start_async_processing.assert_called_once_with("query", "stream-1", request)
    assert response["stream"]["id"] == "stream-1"


def test_start_async_processing_accepts_prepared_request_username():
    view = object.__new__(WxAiBotViewSet)
    view._process_ai_request_async = MagicMock()
    executor = MagicMock()
    executor.submit.return_value = True
    request = WxBotAgentRequest("query", "stream-1", "user-1", "group-1")

    with patch("aidev_wxbot.wxaibot.views.get_agent_executor", return_value=executor):
        submitted = view._start_async_processing("query", "stream-1", request)

    assert submitted
    executor.submit.assert_called_once_with(
        view._process_ai_request_async,
        "query",
        "stream-1",
        "user-1",
        "group-1",
    )


def test_start_async_processing_rejects_when_executor_is_full():
    view = object.__new__(WxAiBotViewSet)
    executor = MagicMock()
    executor.submit.return_value = False
    context = SimpleNamespace(sender_id="user-1", group_id="group-1")

    with patch("aidev_wxbot.wxaibot.views.get_agent_executor", return_value=executor):
        submitted = view._start_async_processing("query", "stream-1", context)

    assert not submitted
    executor.submit.assert_called_once()


def test_preempted_request_writes_terminal_message_to_its_own_stream():
    view = object.__new__(WxAiBotViewSet)
    view._get_or_create_thread_id = MagicMock(return_value="thread-1")
    strategy = MagicMock()
    strategy.execute.side_effect = ConsumerPreemptedError("replaced")

    with (
        patch("aidev_wxbot.wxaibot.views.resolve_strategy", return_value=strategy),
        patch("aidev_wxbot.wxaibot.views.LlmChunkMsg") as chunk_cls,
    ):
        view._process_ai_request_async("query", "stream-old", "user-1", "group-1")

    chunk_cls.assert_called_once_with(
        content="当前会话已有新请求，原请求已结束",
        is_finish=True,
        stream_id="stream-old",
    )
    chunk_cls.return_value.append_to_cache.assert_called_once()


def test_legacy_callback_still_executes_strategy_with_rabbitmq_bridge():
    view = object.__new__(WxAiBotViewSet)
    view._get_or_create_thread_id = MagicMock(return_value="thread-1")
    strategy = MagicMock()

    with (
        patch("aidev_wxbot.wxaibot.views.resolve_strategy", return_value=strategy),
        patch("aidev_wxbot.wxaibot.views.rabbitmq_client") as rabbitmq,
    ):
        view._process_ai_request_async("query", "legacy-stream", "user-1", "group-1")

    strategy.execute.assert_called_once_with(
        content="query",
        stream_id="legacy-stream",
        username="user-1",
        thread_id="thread-1",
        group_id="group-1",
        rabbitmq_client=rabbitmq,
    )


class TestBuiltinCommands:
    """内置命令在单聊、@机器人、兜底解析三条路径上必须表现一致。"""

    @pytest.fixture
    def view(self):
        view = object.__new__(WxAiBotViewSet)
        view._new_conversation = MagicMock(return_value={"msgtype": "stream", "new": True})
        return view

    @pytest.fixture
    def context(self):
        return SimpleNamespace(sender_id="user-1", group_id="group-1")

    @pytest.mark.parametrize("cmd", ["/new", "会话", "新会话"])
    def test_new_conversation_commands(self, view, context, cmd):
        assert view._resolve_builtin_command(cmd, "s1", context) == {"msgtype": "stream", "new": True}
        view._new_conversation.assert_called_once_with("group-1", "user-1", "s1")

    def test_callback_keeps_one_session_per_group(self, view):
        """回调侧不变：整群仍共享一个 thread_id，按人隔离只发生在长连接。"""
        assert view._session_scope("group-1", "user-1") == "group-1"

    @pytest.mark.parametrize("cmd", ["/help", "帮助"])
    def test_help_returns_static_terminal_reply(self, view, context, cmd):
        response = view._resolve_builtin_command(cmd, "s1", context)
        assert response["stream"]["content"] == HELP_REPLY
        assert response["stream"]["finish"] is True

    @pytest.mark.parametrize("cmd", ["/stop", "停止"])
    def test_stop_without_active_stream_says_so(self, view, context, cmd):
        """回调路径没有进程内流登记，只能如实回复，不能假装停住了。"""
        response = view._resolve_builtin_command(cmd, "s1", context)
        assert response["stream"]["content"] == STOP_NO_ACTIVE_REPLY
        assert response["stream"]["finish"] is True

    def test_normal_input_falls_through_to_agent(self, view, context):
        assert view._resolve_builtin_command("查一下昨天的日志", "s1", context) is None

    def test_single_chat_routes_command(self, view, context):
        response, content = view._handle_single_chat("/help", "s1", context)
        assert response["stream"]["content"] == HELP_REPLY
        assert content == ""

    def test_mention_routes_command(self, view, context):
        response, content = view._process_mention("@bot /help", len("@bot"), "s1", context)
        assert response["stream"]["content"] == HELP_REPLY
        assert content == ""

    def test_mention_fallback_routes_command(self, view, context):
        """未配置 WAXIBOT_NAME 时走兜底解析，命令同样要生效。"""
        response, content = view._process_mention_fallback("@某机器人 /help", "s1", context)
        assert response["stream"]["content"] == HELP_REPLY
        assert content == ""
