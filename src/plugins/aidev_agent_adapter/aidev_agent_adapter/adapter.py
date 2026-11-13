"""ACP 客户端与可续传的 AG-UI 事件输出，不包含 Channel Server 协议。"""

import asyncio
from contextlib import AsyncExitStack, suppress

from acp import PROTOCOL_VERSION, RequestError, spawn_agent_process, text_block
from acp.schema import ClientCapabilities, RequestPermissionResponse

from .config_sync import Snapshot, private_directory
from .events import EventMapper
from .journal import Journal
from .models import Settings


class Adapter:
    def __init__(self, settings: Settings, snapshot: Snapshot):
        self.settings = settings
        self.snapshot = snapshot
        self.journal = Journal(settings.root / "journal", settings.identity)
        self._stack = AsyncExitStack()
        self._connection = None
        self._sessions: dict[str, str] = {}
        self._active: tuple[str, EventMapper] | None = None
        self._tasks: dict[str, asyncio.Task] = {}
        self._serial = asyncio.Lock()
        self._closed = False
        self._broken = False
        self._mapping_failed = asyncio.Event()

    async def _connect(self) -> None:
        if self._broken:
            raise RuntimeError("ACP connection quarantined; restart adapter and use a new thread")
        if self._connection is not None:
            return
        command = self.settings.command or [self.settings.engine, "acp"]
        home = private_directory(self.settings.root / "engine-home")
        environment = {
            "HOME": str(home),
            **self.settings.engine_env,
            **self.snapshot.environment,
            "OPENCLAW_HIDE_BANNER": "1",
            "OPENCLAW_SUPPRESS_NOTES": "1",
        }
        self._connection, _ = await self._stack.enter_async_context(
            spawn_agent_process(
                self,
                *command,
                env=environment,
                cwd=self.snapshot.workspace,
                transport_kwargs={"stderr": asyncio.subprocess.DEVNULL},
            )
        )
        await self._connection.initialize(protocol_version=PROTOCOL_VERSION, client_capabilities=ClientCapabilities())

    async def request_permission(self, session_id, tool_call, options, **kwargs):
        # 第一版不提供自动授权；后续由 Channel 接入显式用户确认。
        return RequestPermissionResponse(outcome={"outcome": "cancelled"})

    async def session_update(self, session_id, update, **kwargs) -> None:
        if self._active and self._active[0] == session_id:
            try:
                self._active[1].update(update)
            except Exception:
                self._mapping_failed.set()

    async def ext_method(self, method, params):
        raise RequestError.method_not_found(method)

    async def ext_notification(self, method, params) -> None:
        pass

    def on_connect(self, conn) -> None:
        pass

    async def submit(self, run_id: str, thread_id: str, text: str) -> None:
        if self._closed:
            raise RuntimeError("adapter closed")
        if not text or len(text.encode()) > 1024 * 1024:
            raise ValueError("prompt must be nonempty and at most 1 MiB")
        request = {
            "text": text,
            "revision": self.snapshot.revision,
            "command": self.settings.command,
            "engine_env": self.settings.engine_env,
        }
        if len(self._tasks) >= self.settings.max_pending_runs and not self.journal.contains(run_id):
            raise RuntimeError("adapter request queue is full")
        if self.journal.claim(run_id, thread_id, request):
            self._tasks[run_id] = asyncio.create_task(self._execute(run_id, thread_id, text))
            self._tasks[run_id].add_done_callback(lambda task: self._tasks.pop(run_id, None))

    async def events(self, run_id: str, after: int = 0):
        """断开消费者不会取消执行；携带原 run_id 和 cursor 再次调用即可续传。"""
        while True:
            batch = self.journal.replay(run_id, after)
            for envelope in batch:
                after = envelope["sequence"]
                yield envelope
            if batch:
                continue
            if self.journal.terminal(run_id):
                return
            await asyncio.sleep(0.05)

    async def _execute(self, run_id: str, thread_id: str, text: str) -> None:
        try:
            async with self._serial:
                await self._run_locked(run_id, thread_id, text)
        except asyncio.CancelledError:
            # 取消发生在获取串行锁之前，也需要完整 RUN_STARTED / RUN_ERROR。
            self.journal.abort(run_id, "CANCELLED_BEFORE_DISPATCH", "Request cancelled before dispatch")
            raise

    async def _run_locked(self, run_id: str, thread_id: str, text: str) -> None:
        mapper = EventMapper(self.journal, run_id, thread_id)
        self._mapping_failed.clear()
        try:
            if thread_id not in self._sessions and self.journal.has_thread(thread_id, run_id):
                self.journal.abort(run_id, "SESSION_NOT_RECOVERABLE", "ACP session context cannot be recovered")
                return
            async with asyncio.timeout(self.settings.prompt_timeout):
                await self._connect()
                if thread_id not in self._sessions:
                    session = await self._connection.new_session(cwd=str(self.snapshot.workspace), mcp_servers=[])
                    self._sessions[thread_id] = session.session_id
                session_id = self._sessions[thread_id]
                self._active = (session_id, mapper)
                self._mapping_failed.clear()
                self.journal.mark_dispatched(run_id)
                response = await self._prompt(session_id, text)
                mapper.finish(response.stop_reason)
        except asyncio.CancelledError:
            self._broken = True
            self.journal.abort(run_id, "EXECUTION_UNKNOWN", "ACP execution cancelled; outcome unknown")
            raise
        except Exception:
            self._broken = True
            code = "EVENT_MAPPING_FAILED" if self._mapping_failed.is_set() else "EXECUTION_UNKNOWN"
            self.journal.abort(run_id, code, "ACP execution interrupted; outcome unknown")
        finally:
            # cancel、断连和子进程清理完成后才允许下一个任务取得串行锁。
            if self._broken:
                if self._active and self._connection:
                    with suppress(Exception):
                        await asyncio.wait_for(self._connection.cancel(session_id=self._active[0]), timeout=2)
                try:
                    await self._stack.aclose()
                finally:
                    self._connection = None
                    self._active = None
            else:
                self._active = None

    async def _prompt(self, session_id: str, text: str):
        prompt = asyncio.create_task(self._connection.prompt(session_id=session_id, prompt=[text_block(text)]))
        failed = asyncio.create_task(self._mapping_failed.wait())
        try:
            await asyncio.wait({prompt, failed}, return_when=asyncio.FIRST_COMPLETED)
            if self._mapping_failed.is_set():
                raise RuntimeError("ACP event conversion failed")
            return await prompt
        finally:
            for task in (prompt, failed):
                if not task.done():
                    task.cancel()
            await asyncio.gather(prompt, failed, return_exceptions=True)

    async def cancel(self, run_id: str) -> None:
        task = self._tasks.get(run_id)
        if task and not task.done():
            # 只取消目标任务；由持有串行锁的任务向 ACP 发送 cancel。
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            self.journal.abort(run_id, "CANCELLED_BEFORE_DISPATCH", "Request cancelled before dispatch")

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        run_ids = list(self._tasks)
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            for run_id in run_ids:
                self.journal.abort(run_id, "EXECUTION_UNKNOWN", "Adapter stopped")
            await self._stack.aclose()
        finally:
            self.journal.close()
