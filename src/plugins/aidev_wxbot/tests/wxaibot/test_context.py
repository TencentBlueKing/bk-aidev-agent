# -*- coding: utf-8 -*-
"""WxBot 流式协议适配层：LlmChunkMsg、stream_msg、CHUNK_FLUSH_THRESHOLD 回归。需在具备 Django + aidev_wxbot 环境中运行。"""

import pytest

try:
    import django  # noqa: F401
    from aidev_wxbot.wxaibot.context import CHUNK_FLUSH_THRESHOLD, LlmChunkMsg, stream_msg

    _wxbot_available = True
except ImportError:
    _wxbot_available = False
    CHUNK_FLUSH_THRESHOLD = 50
    LlmChunkMsg = None
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


@pytest.mark.skipif(not _wxbot_available, reason="Django and aidev_wxbot required")
class TestChunkFlushThreshold:
    """协议常量用于桥接层刷新策略"""

    def test_threshold_positive(self):
        assert CHUNK_FLUSH_THRESHOLD >= 1
