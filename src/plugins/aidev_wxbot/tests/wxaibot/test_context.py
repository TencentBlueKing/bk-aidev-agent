# -*- coding: utf-8 -*-
"""WxBot 流式协议适配层：LlmChunkMsg、stream_msg、CHUNK_FLUSH_THRESHOLD 回归。需在具备 Django + aidev_wxbot 环境中运行。"""

import pytest

try:
    import django  # noqa: F401
    from aidev_wxbot.wxaibot.context import CHUNK_FLUSH_THRESHOLD, LlmChunkMsg, stream_msg
    from django.conf import settings

    _wxbot_available = True
except ImportError:
    _wxbot_available = False
    CHUNK_FLUSH_THRESHOLD = 50
    LlmChunkMsg = None
    settings = None
    stream_msg = None


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
class TestStreamMsg:
    """stream_msg 返回结构符合 wx 轮询协议"""

    def test_returns_stream_msgtype_and_finish(self):
        out = stream_msg("内容", True, "sid_123")
        assert out["msgtype"] == "stream"
        assert out["stream"]["id"] == "sid_123"
        assert out["stream"]["finish"] is True
        assert out["stream"]["content"] == "内容"


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


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
class TestChunkFlushThreshold:
    """协议常量用于桥接层刷新策略"""

    def test_threshold_positive(self):
        assert CHUNK_FLUSH_THRESHOLD >= 1
