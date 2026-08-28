"""wxbot 视图层的后台执行与会话终态测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from aidev_agent.services.messages_handler import ConsumerPreemptedError
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
