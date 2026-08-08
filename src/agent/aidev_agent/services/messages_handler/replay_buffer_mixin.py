import threading
from typing import Any, ClassVar

from .constants import EOD_CHUNK


class ReplayBufferMixin:
    """RabbitMQ / Redis replay backend 共用的协议帧缓冲能力。"""

    SSE_PUBLISH_CHUNK_MAX_BYTES: ClassVar[int]
    _eod_commit_events: dict[str, set[threading.Event]]
    _eod_commit_events_lock: threading.Lock

    @classmethod
    def _coalesce_sse_messages(cls, messages: list[Any]) -> list[Any]:
        """合并相邻 SSE 帧，减少物理消息数并保持原始协议字节流。"""
        coalesced_messages: list[Any] = []
        sse_parts: list[str] = []
        sse_size = 0

        def flush_sse_parts() -> None:
            nonlocal sse_size
            if not sse_parts:
                return
            coalesced_messages.append("".join(sse_parts))
            sse_parts.clear()
            sse_size = 0

        for message in messages:
            if not isinstance(message, str) or not message.startswith("data: "):
                flush_sse_parts()
                coalesced_messages.append(message)
                continue

            message_size = len(message.encode("utf-8"))
            if sse_parts and sse_size + message_size > cls.SSE_PUBLISH_CHUNK_MAX_BYTES:
                flush_sse_parts()
            if message_size > cls.SSE_PUBLISH_CHUNK_MAX_BYTES:
                coalesced_messages.append(message)
                continue
            sse_parts.append(message)
            sse_size += message_size

        flush_sse_parts()
        return coalesced_messages

    @staticmethod
    def _expand_sse_messages(messages: list[Any]) -> list[Any]:
        """将合并的 SSE 字节流还原为调用方原有的逐帧消息。"""
        expanded_messages: list[Any] = []
        for message in messages:
            if not isinstance(message, str) or not message.startswith("data: ") or "\n\ndata: " not in message:
                expanded_messages.append(message)
                continue

            parts = message.split("\n\n")
            if parts[-1] or any(not part.startswith("data: ") for part in parts[:-1]):
                expanded_messages.append(message)
                continue
            expanded_messages.extend(f"{part}\n\n" for part in parts[:-1])
        return expanded_messages

    def register_eod_commit_event(self, thread_id: str, event: threading.Event) -> None:
        """注册 EOD 提交确认事件，供 producer 等待最终 flush 结果。"""
        with self._eod_commit_events_lock:
            self._eod_commit_events.setdefault(thread_id, set()).add(event)

    def unregister_eod_commit_event(self, thread_id: str, event: threading.Event) -> None:
        """移除尚未被 EOD 成功提交消费的确认事件。"""
        with self._eod_commit_events_lock:
            events = self._eod_commit_events.get(thread_id)
            if events is None:
                return
            events.discard(event)
            if not events:
                self._eod_commit_events.pop(thread_id, None)

    def _notify_eod_committed(self, thread_id: str, messages: list[Any]) -> None:
        """仅在包含 EOD 的完整批次成功提交后通知 producer。"""
        if EOD_CHUNK not in messages:
            return
        with self._eod_commit_events_lock:
            events = self._eod_commit_events.pop(thread_id, set())
        for event in events:
            event.set()
