# -*- coding: utf-8 -*-
"""WxBot 流式协议适配层：LlmChunkMsg、stream_msg、CHUNK_FLUSH_THRESHOLD 回归。需在具备 Django + aidev_wxbot 环境中运行。"""

from unittest.mock import patch

import pytest

try:
    import django  # noqa: F401
    from django.conf import settings

    from aidev_wxbot.wxaibot.constants import QUEUE_EXPIRES_MS
    from aidev_wxbot.wxaibot.context import (
        CHUNK_FLUSH_THRESHOLD,
        ContextGenerator,
        LlmChunkMsg,
        _normalize_url,
        stream_msg,
    )

    _wxbot_available = True
except ImportError:
    _wxbot_available = False
    CHUNK_FLUSH_THRESHOLD = 50
    LlmChunkMsg = None
    settings = None
    stream_msg = None


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        ("", ""),
        (
            "https://approval.example.com/ticket?id=123&name=a b",
            "https://approval.example.com/ticket?id=123&name=a%20b",
        ),
        (
            "https://approval.example.com/#/ticket/ticketInfo?type=ticket&ticketId=123",
            "https://approval.example.com/#/ticket/ticketInfo?type=ticket&ticketId=123",
        ),
        (
            "https://approval.example.com/#/ticket?name=审批 单&ticketId=123",
            "https://approval.example.com/#/ticket?name=%E5%AE%A1%E6%89%B9%20%E5%8D%95&ticketId=123",
        ),
        (
            "https://approval.example.com/#/ticket?value=a%26b%3Dc%3Fd&ticketId=123",
            "https://approval.example.com/#/ticket?value=a%26b%3Dc%3Fd&ticketId=123",
        ),
        ("/#/ticket?type=ticket&ticketId=123", "/#/ticket?type=ticket&ticketId=123"),
    ],
)
def test_normalize_url_preserves_route_and_query_delimiters(raw_url, expected):
    assert _normalize_url(raw_url) == expected
    assert _normalize_url(expected) == expected


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
class TestStreamMsg:
    """stream_msg 返回结构符合 wx 轮询协议"""

    def test_returns_stream_msgtype_and_finish(self):
        out = stream_msg("内容", True, "sid_123")
        assert out["msgtype"] == "stream"
        assert out["stream"]["id"] == "sid_123"
        assert out["stream"]["finish"] is True
        assert out["stream"]["content"] == "内容"

    def test_msg_items_are_exposed_only_on_terminal_frame(self):
        items = [{"msgtype": "image", "image": {"base64": "data", "md5": "digest"}}]

        assert "msg_item" not in stream_msg("处理中", False, "sid_123", items)["stream"]
        assert stream_msg("完成", True, "sid_123", items)["stream"]["msg_item"] == items
        assert "msg_item" not in stream_msg("完成", True, "sid_123", [])["stream"]


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
class TestConversationIsolation:
    @staticmethod
    def _payload(*, user_id: str, msg_id: str, chat_id: str | None = None) -> dict:
        payload = {
            "msgtype": "text",
            "msgid": msg_id,
            "chattype": "group" if chat_id else "single",
            "from": {"userid": user_id},
            "text": {"content": "hello"},
        }
        if chat_id:
            payload["chatid"] = chat_id
        return payload

    @patch("aidev_wxbot.wxaibot.context.BkAiDevApi.convert_to_rtx")
    def test_single_chats_use_sender_as_group_id(self, convert_to_rtx):
        convert_to_rtx.side_effect = lambda user_id: {"userid": f"rtx-{user_id}"}

        first = ContextGenerator(self._payload(user_id="u1", msg_id="m1")).generate()
        second = ContextGenerator(self._payload(user_id="u2", msg_id="m2")).generate()

        assert first.group_id == "rtx-u1"
        assert second.group_id == "rtx-u2"
        assert first.group_id != second.group_id

    @patch("aidev_wxbot.wxaibot.context.BkAiDevApi.convert_to_rtx")
    def test_group_chat_uses_chat_id_for_shared_conversation(self, convert_to_rtx):
        convert_to_rtx.side_effect = lambda user_id: {"userid": f"rtx-{user_id}"}

        first = ContextGenerator(self._payload(user_id="u1", msg_id="m1", chat_id="chat-1")).generate()
        second = ContextGenerator(self._payload(user_id="u2", msg_id="m2", chat_id="chat-1")).generate()

        assert first.group_id == "chat-1"
        assert second.group_id == "chat-1"


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
class TestLlmChunkMsg:
    """LlmChunkMsg 适配 think/content/docs/is_finish"""

    def test_docs_content_empty_when_no_docs(self):
        msg = LlmChunkMsg(stream_id="s1")
        assert msg.docs_content == ""

    def test_docs_content_formats_docs(self):
        msg = LlmChunkMsg(
            stream_id="s1",
            docs=[{"display_name": "A", "path": "/a"}, {"display_name": "B", "path": "/b"}],
        )
        text = msg.docs_content
        assert "A" in text and "/a" in text
        assert "B" in text and "/b" in text

    def test_wxaibot_msg_json_from_cache_returns_latest_snapshot_within_limit(self):
        class StubRabbitMQClient:
            def __init__(self):
                self.messages = [
                    {"body": {"content": "a", "think_content": "", "is_finish": False, "docs": []}},
                    {"body": {"content": "ab", "think_content": "", "is_finish": False, "docs": []}},
                    {"body": {"content": "abc", "think_content": "", "is_finish": False, "docs": []}},
                ]

            def get_queue_info(self, queue_name):
                return {"message_count": len(self.messages)} if self.messages else {"message_count": 0}

            def get_message(self, queue_name, auto_ack=True):
                if not self.messages:
                    return None
                return self.messages.pop(0)

            def delete_queue(self, queue_name):
                raise AssertionError("delete_queue should not be called for unfinished snapshots")

        settings.MAX_MESSAGE_TIME = 300
        msg = LlmChunkMsg(stream_id="sid_9999999999")

        out = msg.wxaibot_msg_json_from_cache(StubRabbitMQClient())

        assert out["stream"]["finish"] is False
        assert out["stream"]["content"] == "abc"

    def test_wxaibot_msg_json_from_cache_stops_at_finish_and_appends_docs(self):
        class StubRabbitMQClient:
            def __init__(self):
                self.messages = [
                    {"body": {"content": "a", "think_content": "", "is_finish": False, "docs": []}},
                    {
                        "body": {
                            "content": "ab",
                            "think_content": "",
                            "is_finish": True,
                            "docs": [{"display_name": "doc", "path": "/doc"}],
                        }
                    },
                    {"body": {"content": "abc", "think_content": "", "is_finish": False, "docs": []}},
                ]
                self.deleted_queue = None

            def get_queue_info(self, queue_name):
                return {"message_count": len(self.messages)} if self.messages else {"message_count": 0}

            def get_message(self, queue_name, auto_ack=True):
                if not self.messages:
                    return None
                return self.messages.pop(0)

            def delete_queue(self, queue_name):
                self.deleted_queue = queue_name

        rabbitmq_client = StubRabbitMQClient()
        settings.MAX_MESSAGE_TIME = 300
        msg = LlmChunkMsg(stream_id="sid_9999999999")

        out = msg.wxaibot_msg_json_from_cache(rabbitmq_client)

        assert out["stream"]["finish"] is True
        assert out["stream"]["content"].startswith("ab")
        assert "[doc](/doc)" in out["stream"]["content"]
        assert rabbitmq_client.deleted_queue == "sid_9999999999"

    def test_wxaibot_msg_json_from_cache_limits_think_only_backlog_to_ten_rounds(self):
        class StubRabbitMQClient:
            def __init__(self):
                self.messages = [
                    {
                        "body": {
                            "content": "",
                            "think_content": f"think-{index}",
                            "is_finish": False,
                            "docs": [],
                        }
                    }
                    for index in range(12)
                ]
                self.get_message_calls = 0

            def get_queue_info(self, queue_name):
                return {"message_count": len(self.messages)} if self.messages else {"message_count": 0}

            def get_message(self, queue_name, auto_ack=True):
                self.get_message_calls += 1
                if not self.messages:
                    return None
                return self.messages.pop(0)

            def delete_queue(self, queue_name):
                raise AssertionError("delete_queue should not be called for think-only backlog")

        rabbitmq_client = StubRabbitMQClient()
        settings.MAX_MESSAGE_TIME = 300
        msg = LlmChunkMsg(stream_id="sid_9999999999")

        out = msg.wxaibot_msg_json_from_cache(rabbitmq_client)

        assert out["stream"]["finish"] is False
        assert out["stream"]["content"] == "<think>think-9</think>"
        assert rabbitmq_client.get_message_calls == 10

    def test_wxaibot_msg_json_from_cache_deletes_queue_on_timeout_and_consume_error(self):
        """超时和消费异常分支均应安全删除队列，防止泄漏"""

        class TrackDeleteRabbitMQClient:
            def __init__(self, messages=None, get_message_error=False):
                self.deleted_queue = None
                self.messages = messages or []
                self._get_message_error = get_message_error

            def get_queue_info(self, queue_name):
                message_count = 1 if self._get_message_error else len(self.messages)
                return {"message_count": message_count}

            def get_message(self, queue_name, auto_ack=True):
                if self._get_message_error:
                    raise RuntimeError("connection reset")
                if not self.messages:
                    return None
                return self.messages.pop(0)

            def delete_queue(self, queue_name):
                self.deleted_queue = queue_name

        # 超时场景
        settings.MAX_MESSAGE_TIME = 1
        stream_id = f"sid_{int(__import__('time').time()) - 10}"
        client = TrackDeleteRabbitMQClient()
        out = LlmChunkMsg(stream_id=stream_id).wxaibot_msg_json_from_cache(client)
        assert out["stream"]["finish"] is True
        assert client.deleted_queue == stream_id

        # 消费异常场景
        settings.MAX_MESSAGE_TIME = 300
        client = TrackDeleteRabbitMQClient(get_message_error=True)
        out = LlmChunkMsg(stream_id="sid_9999999999").wxaibot_msg_json_from_cache(client)
        assert out["stream"]["finish"] is True
        assert client.deleted_queue == "sid_9999999999"

    def test_append_to_cache_declares_queue_with_expires(self):
        """declare_queue 应携带 x-expires 参数"""

        class StubRabbitMQClient:
            def __init__(self):
                self.declared_queue_args = None

            def declare_queue(self, queue_name, **kwargs):
                self.declared_queue_args = kwargs
                return True

            def publish_message(self, exchange, queue_name, message_data):
                return True

        rabbitmq_client = StubRabbitMQClient()
        msg = LlmChunkMsg(stream_id="sid_test", content="hello")
        msg.append_to_cache(rabbitmq_client)

        assert rabbitmq_client.declared_queue_args["arguments"]["x-expires"] == QUEUE_EXPIRES_MS

    def test_terminal_message_prepares_images_before_publishing(self):
        class StubRabbitMQClient:
            def declare_queue(self, *_args, **_kwargs):
                return True

            def publish_message(self, _exchange, _queue_name, message_data):
                self.message_data = message_data
                return True

        client = StubRabbitMQClient()
        items = [{"msgtype": "image", "image": {"base64": "data", "md5": "digest"}}]
        msg = LlmChunkMsg(stream_id="sid_test", content="带图回答", is_finish=True)

        with patch(
            "aidev_wxbot.wxaibot.image_reply.prepare_callback_image_reply",
            return_value=("处理后回答", items),
        ) as prepare:
            msg.append_to_cache(client)

        prepare.assert_called_once_with("带图回答")
        assert client.message_data["content"] == "处理后回答"
        assert client.message_data["msg_items"] == items

    def test_terminal_message_with_existing_items_is_not_prepared_twice(self):
        class StubRabbitMQClient:
            def declare_queue(self, *_args, **_kwargs):
                return True

            def publish_message(self, _exchange, _queue_name, message_data):
                self.message_data = message_data
                return True

        client = StubRabbitMQClient()
        items = [{"msgtype": "image", "image": {"base64": "data", "md5": "digest"}}]
        msg = LlmChunkMsg(stream_id="sid_test", content="处理后回答", is_finish=True, msg_items=items)

        with patch("aidev_wxbot.wxaibot.image_reply.prepare_callback_image_reply") as prepare:
            msg.append_to_cache(client)

        prepare.assert_not_called()
        assert client.message_data["msg_items"] == items

    def test_cache_roundtrip_exposes_items_only_for_terminal_snapshot(self):
        items = [{"msgtype": "image", "image": {"base64": "data", "md5": "digest"}}]

        class StubRabbitMQClient:
            def __init__(self, finish):
                self.message = {
                    "body": {
                        "content": "回答",
                        "think_content": "",
                        "is_finish": finish,
                        "docs": [],
                        "msg_items": items,
                    }
                }

            def get_queue_info(self, _queue_name):
                return {"message_count": 1}

            def get_message(self, _queue_name, auto_ack=True):
                message, self.message = self.message, None
                return message

            def delete_queue(self, _queue_name):
                return None

        settings.MAX_MESSAGE_TIME = 300
        unfinished = LlmChunkMsg(stream_id="sid_9999999999").wxaibot_msg_json_from_cache(StubRabbitMQClient(False))
        finished = LlmChunkMsg(stream_id="sid_9999999999").wxaibot_msg_json_from_cache(StubRabbitMQClient(True))

        assert "msg_item" not in unfinished["stream"]
        assert finished["stream"]["msg_item"] == items

    def test_queue_expiry_always_outlives_configured_message_timeout(self, monkeypatch):
        class StubRabbitMQClient:
            def __init__(self):
                self.declared_queue_args = None

            def declare_queue(self, queue_name, **kwargs):
                self.declared_queue_args = kwargs
                return True

            def publish_message(self, exchange, queue_name, message_data):
                return True

        monkeypatch.setattr(settings, "MAX_MESSAGE_TIME", 600)
        rabbitmq_client = StubRabbitMQClient()

        LlmChunkMsg(stream_id="sid_test", content="hello").append_to_cache(rabbitmq_client)

        assert rabbitmq_client.declared_queue_args["arguments"]["x-expires"] == 660000

    def test_timeout_requests_agent_cancel_before_deleting_queue(self, monkeypatch):
        events = []

        class TrackRabbitMQClient:
            def delete_queue(self, queue_name):
                events.append(("delete", queue_name))

        monkeypatch.setattr(settings, "MAX_MESSAGE_TIME", 1)
        monkeypatch.setattr(
            "aidev_wxbot.wxaibot.context.stream_registry.cancel",
            lambda stream_id: events.append(("cancel", stream_id)) or True,
        )
        stream_id = f"sid_{int(__import__('time').time()) - 10}"

        out = LlmChunkMsg(stream_id=stream_id).wxaibot_msg_json_from_cache(TrackRabbitMQClient())

        assert out["stream"]["finish"] is True
        assert events == [("cancel", stream_id), ("delete", stream_id)]


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
class TestChunkFlushThreshold:
    """协议常量用于桥接层刷新策略"""

    def test_threshold_positive(self):
        assert CHUNK_FLUSH_THRESHOLD >= 1
