"""Resume output → new WeCom messages on the owning connection's event loop.

Only channel notices and the final rendered output cross the bounded queue. Network
failure never restarts the Agent or prevents its remaining output being saved.
This process-local adapter is not an outbox for external approval callbacks.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator

from .direct_stream import AgentStream, iter_direct_stream_frames

logger = logging.getLogger(__name__)
_DONE = object()


def markdown_parts(content: str, limit: int = 4000) -> Iterator[str]:
    """Split UTF-8 without cutting a code point; every part is a new message."""
    part, size = [], 0
    for char in content:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            yield "".join(part)
            part, size = [], 0
        part.append(char)
        size += width
    if part:
        yield "".join(part)


class ResumeDelivery:
    def __init__(
        self,
        send: Callable[[dict], Awaitable[None]],
        *,
        resume_type: str,
        paused: bool = False,
    ):
        self._loop = asyncio.get_running_loop()
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=8)
        self._send = send
        self._closed = False
        self._resume_type = resume_type
        self._sending_allowed = asyncio.Event()
        if not paused:
            self._sending_allowed.set()
        self.task = asyncio.create_task(self._consume_messages())

    def _on_ready(self) -> None:
        # The updated approval card already confirms cancellation; READY still
        # remains available to other listeners without sending another notice.
        if self._resume_type == "tool_approval":
            return
        self._enqueue({"msgtype": "markdown", "markdown": {"content": "答案已接收，正在继续原会话。"}})

    def _enqueue(self, body: object) -> None:
        if self._closed or self._loop.is_closed():
            return
        try:
            self._loop.call_soon_threadsafe(self._offer, body)
        except RuntimeError:
            self._closed = True

    def _offer(self, body: object) -> None:
        if self._closed:
            return
        try:
            self._queue.put_nowait(body)
        except asyncio.QueueFull:
            logger.error("event=wxbot_resume_delivery_failed reason=queue_full")
            self.close()

    def consume(self, output, session_code: str, interrupt_id: str, turn_id: str = "", *, thread_id: str = "") -> None:
        ready = False

        def on_run_started(run_id: str) -> None:
            nonlocal ready
            if ready or not run_id:
                return
            ready = True
            self._on_ready()

        last = None
        try:
            for frame in iter_direct_stream_frames(
                AgentStream("chat", output, session_code, resume_interrupt_id=interrupt_id),
                interrupt_id,
                on_run_started,
            ):
                if frame.finish:
                    last = frame
        finally:
            # Persistence/finalization must run even if channel rendering fails.
            for _ in output:
                pass
        if last is not None:
            if last.content:
                self._enqueue({"msgtype": "markdown", "markdown": {"content": last.content}})
            if last.template_card:
                self._enqueue({"msgtype": "template_card", "template_card": last.template_card})

    def failed(self) -> None:
        self._enqueue({"msgtype": "markdown", "markdown": {"content": "会话恢复未完成，请返回原会话查看或继续。"}})

    def finish(self) -> None:
        self._enqueue(_DONE)

    def activate(self) -> None:
        self._sending_allowed.set()

    def close(self) -> None:
        self._closed = True
        self.task.cancel()

    async def _consume_messages(self) -> None:
        try:
            await self._sending_allowed.wait()
            while True:
                body = await self._queue.get()
                if body is _DONE:
                    return
                if body.get("msgtype") == "markdown":
                    for part in markdown_parts(body["markdown"]["content"]):
                        await self._send({"msgtype": "markdown", "markdown": {"content": part}})
                else:
                    await self._send(body)
        except Exception as error:
            logger.error("event=wxbot_resume_delivery_failed error_type=%s", type(error).__name__)
        finally:
            self._closed = True
