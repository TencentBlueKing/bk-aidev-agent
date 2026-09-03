"""wxbot Agent 取消注册表测试。"""

from unittest.mock import patch

from aidev_wxbot.wxaibot.stream_registry import StreamRegistry


def test_stream_registry_cancels_exact_registered_run():
    registry = StreamRegistry()
    registry.register("stream-1", "session-1")
    registry.set_run_id("stream-1", "run-1")

    with patch(
        "aidev_wxbot.wxaibot.stream_registry.GeneratorStreamingHelper.cancel",
        return_value=True,
    ) as cancel:
        assert registry.cancel("stream-1")

    cancel.assert_called_once_with("session-1", run_id="run-1")
    assert registry.is_cancel_requested("stream-1")
    registry.unregister("stream-1")
    assert not registry.is_cancel_requested("stream-1")


def test_stream_registry_delivers_cancel_when_agent_registers_late():
    registry = StreamRegistry()
    assert not registry.cancel("stream-1")

    with patch(
        "aidev_wxbot.wxaibot.stream_registry.GeneratorStreamingHelper.cancel",
        return_value=True,
    ) as cancel:
        assert registry.register("stream-1", "session-1")

    cancel.assert_called_once_with("session-1", run_id=None)
