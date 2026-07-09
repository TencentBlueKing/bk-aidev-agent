"""BaseSessionWriter.commit_hook 单元测试。

commit_hook 用于「落库后」把已落库 messageId 集合通知给上层（如 RabbitMQ prune），
仅当本次事件产生新的落库消息时触发。纯内存 writer，不依赖 RabbitMQ。
"""

from ag_ui.core import EventType, TextMessageContentEvent, TextMessageEndEvent

from aidev_agent.services.event_handlers.base import BaseSessionWriter


class _RecordingWriter(BaseSessionWriter):
    def __init__(self, **kwargs):
        super().__init__(session_code="s", **kwargs)

    def _do_create_content(self, payload: dict, headers: dict) -> int:
        return 1

    def _do_update_content(self, content_id: int, payload: dict, headers: dict) -> None:
        pass


class _PersistOnEndWriter(_RecordingWriter):
    """把 TEXT_MESSAGE_END 当作落库点（测试用），以驱动 commit_hook。"""

    def handle_text_message_end(self, event) -> None:
        self._written_message_ids.add(event.message_id)


class TestCommitHook:
    def test_hook_fires_after_persist_with_committed_ids(self):
        seen: list[set[str]] = []
        writer = _PersistOnEndWriter()
        writer.commit_hook = lambda committed: seen.append(set(committed))

        writer(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id="mid-1"))

        assert seen == [{"mid-1"}]

    def test_hook_not_fired_without_new_persist(self):
        """content 事件只累积内存、不落库 → 不触发 hook。"""
        seen: list = []
        writer = _RecordingWriter()
        writer.commit_hook = lambda committed: seen.append(committed)

        writer(TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id="x", delta="a"))

        assert seen == []

    def test_no_hook_is_safe(self):
        writer = _PersistOnEndWriter()  # commit_hook 默认 None
        writer(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id="mid-1"))
        assert "mid-1" in writer._written_message_ids

    def test_hook_exception_is_swallowed(self):
        """hook 抛异常不得影响主落库流程。"""

        def boom(_committed):
            raise RuntimeError("prune failed")

        writer = _PersistOnEndWriter()
        writer.commit_hook = boom
        writer(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id="mid-1"))
        assert "mid-1" in writer._written_message_ids

    def test_hook_receives_accumulating_committed_set(self):
        seen: list[set[str]] = []
        writer = _PersistOnEndWriter()
        writer.commit_hook = lambda committed: seen.append(set(committed))

        writer(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id="mid-1"))
        writer(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id="mid-2"))

        assert seen == [{"mid-1"}, {"mid-1", "mid-2"}]
