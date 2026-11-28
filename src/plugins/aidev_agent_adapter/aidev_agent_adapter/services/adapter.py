"""ACP 客户端与可续传的 AG-UI 事件输出，不包含 Channel Server 协议。"""

import asyncio
import logging
import re
import time
from contextlib import AsyncExitStack, suppress
from pathlib import Path

from acp import PROTOCOL_VERSION, RequestError, spawn_agent_process, text_block
from acp.schema import ClientCapabilities, RequestPermissionResponse
from opentelemetry import metrics, trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .config_sync import Snapshot
from .journal import Journal
from ..packages.storage import private_directory
from ..protocols.events import EventMapper
from ..protocols.models import Settings

logger = logging.getLogger(__name__)
SESSION_VOLUME = Path("/app/.storage/session")
_PROPAGATOR = TraceContextTextMapPropagator()
_METER = metrics.get_meter(__name__)
_ACP_RUNS = _METER.create_counter(
    "aidev_adapter_acp_runs",
    unit="1",
    description="Total ACP runs executed by the sandbox adapter",
)
_ACP_RUN_DURATION = _METER.create_histogram(
    "aidev_adapter_acp_run_duration",
    unit="s",
    description="ACP run execution duration in seconds",
)


class Adapter:
    def __init__(self, settings: Settings, snapshot: Snapshot):
        self.settings = settings
        self.snapshot = snapshot
        self._run_signals: dict[str, set[asyncio.Event]] = {}
        self.journal = Journal(settings.root / "journal", settings.identity, on_event=self._notify_run)
        self._stack = AsyncExitStack()
        self._connection = None
        self._process = None
        self._sessions: dict[str, str] = {}
        self._active: dict[str, tuple[EventMapper, asyncio.Event]] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._thread_locks: dict[str, asyncio.Lock] = {}
        self._connect_lock = asyncio.Lock()
        self._closed = False
        self._unrecoverable: set[str] = set()

    async def __aenter__(self) -> "Adapter":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    def _notify_run(self, run_id: str) -> None:
        for signal in self._run_signals.get(run_id, ()):
            signal.set()

    def session_directory(self, thread_id: str) -> Path:
        if not self.settings.mounted_storage:
            return self.snapshot.workspace
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", thread_id):
            raise ValueError("invalid session code")
        return private_directory(SESSION_VOLUME / thread_id)

    async def _reset_dead_connection(self) -> None:
        if self._connection is not None and self._process is not None and self._process.returncode is not None:
            self._connection = None
            self._process = None
            # 底层 ACP 进程退出后，内存中旧会话句柄全部失效，允许新会话重新建连。
            self._unrecoverable.update(self._sessions.keys())
            self._sessions.clear()
            with suppress(Exception):
                await self._stack.aclose()
            self._stack = AsyncExitStack()

    async def _connect(self) -> None:
        await self._reset_dead_connection()
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
        async with AsyncExitStack() as startup:
            connection, process = await startup.enter_async_context(
                spawn_agent_process(
                    self,
                    *command,
                    env=environment,
                    cwd=Path("/app/workspace") if self.settings.mounted_storage else self.snapshot.workspace,
                    transport_kwargs={"stderr": asyncio.subprocess.DEVNULL},
                )
            )
            await connection.initialize(protocol_version=PROTOCOL_VERSION, client_capabilities=ClientCapabilities())
            self._stack.push_async_callback(startup.pop_all().aclose)
        self._connection = connection
        self._process = process

    async def _ensure_connected(self):
        async with self._connect_lock:
            await self._connect()
            return self._connection

    async def request_permission(self, session_id, tool_call, options, **kwargs):
        # 第一版不提供自动授权；后续由 Channel 接入显式用户确认。
        return RequestPermissionResponse(outcome={"outcome": "cancelled"})

    async def session_update(self, session_id, update, **kwargs) -> None:
        active = self._active.get(session_id)
        if active:
            mapper, mapping_failed = active
            try:
                mapper.update(update)
            except Exception as exc:
                logger.warning("ACP event mapping failed: session_id=%s error=%s", session_id, type(exc).__name__)
                mapping_failed.set()

    async def ext_method(self, method, params):
        raise RequestError.method_not_found(method)

    async def ext_notification(self, method, params) -> None:
        pass

    def on_connect(self, conn) -> None:
        pass

    async def submit(self, run_id: str, thread_id: str, text: str, *, queued_ns: int | None = None) -> None:
        if self._closed:
            raise RuntimeError("adapter closed")
        if not text or len(text.encode("utf-8")) > 1024 * 1024:
            raise ValueError("prompt must be nonempty and at most 1 MiB")
        # 幂等指纹仅绑定稳定业务请求语义，不含每次重启随机生成的 engine_env。
        request = {
            "text": text,
            "revision": self.snapshot.revision,
            "command": self.settings.command,
        }
        if len(self._tasks) >= self.settings.max_pending_runs and not self.journal.contains(run_id):
            raise RuntimeError("adapter request queue is full")
        if self.journal.claim(run_id, thread_id, request):
            now = time.time_ns()
            start = queued_ns if type(queued_ns) is int and 0 < queued_ns <= now else now
            self._tasks[run_id] = asyncio.create_task(self._execute(run_id, thread_id, text, start))
            self._tasks[run_id].add_done_callback(lambda task: self._tasks.pop(run_id, None))

    async def events(self, run_id: str, after: int = 0):
        """断开消费者不会取消执行；每消费者独立 Event，防止重连并发丢失唤醒或泄漏。"""
        signal = asyncio.Event()
        waiters = self._run_signals.setdefault(run_id, set())
        waiters.add(signal)
        try:
            while True:
                signal.clear()
                batch = self.journal.replay(run_id, after)
                for envelope in batch:
                    after = envelope["sequence"]
                    yield envelope
                if batch:
                    continue
                if self.journal.terminal(run_id):
                    return
                with suppress(TimeoutError):
                    await asyncio.wait_for(signal.wait(), timeout=0.5)
        finally:
            waiters.discard(signal)
            if not waiters:
                self._run_signals.pop(run_id, None)

    async def _execute(self, run_id: str, thread_id: str, text: str, queued_ns: int) -> None:
        tracer = trace.get_tracer(__name__)
        queue_span = tracer.start_span("turn.queue", start_time=queued_ns, attributes={"aidev.run.id": run_id})
        ended = False
        lock = self._thread_locks.setdefault(thread_id, asyncio.Lock())
        try:
            async with lock:
                queue_span.end()
                ended = True
                with tracer.start_as_current_span("agent.run", attributes={"aidev.run.id": run_id}):
                    await self._run_locked(run_id, thread_id, text)
        except asyncio.CancelledError:
            # 取消发生在获取串行锁之前，也需要完整 RUN_STARTED / RUN_ERROR。
            self.journal.abort(run_id, "CANCELLED_BEFORE_DISPATCH", "Request cancelled before dispatch")
            raise
        finally:
            if not ended:
                queue_span.end()
            if not lock.locked() and not getattr(lock, "_waiters", None):
                self._thread_locks.pop(thread_id, None)

    async def _run_locked(self, run_id: str, thread_id: str, text: str) -> None:
        mapper = EventMapper(self.journal, run_id, thread_id)
        mapping_failed = asyncio.Event()
        entry = (mapper, mapping_failed)
        connection = None
        session_id = None
        started = time.monotonic()
        outcome = "error"
        span = trace.get_current_span()
        span.set_attribute("aidev.engine", self.settings.engine)
        try:
            if thread_id in self._unrecoverable or (
                thread_id not in self._sessions and self.journal.has_thread(thread_id, run_id)
            ):
                outcome = "unrecoverable"
                span.set_status(trace.StatusCode.ERROR)
                self.journal.abort(run_id, "SESSION_NOT_RECOVERABLE", "ACP session context cannot be recovered")
                return
            async with asyncio.timeout(self.settings.prompt_timeout):
                connection = await self._ensure_connected()
                if thread_id not in self._sessions:
                    session = await connection.new_session(cwd=str(self.session_directory(thread_id)), mcp_servers=[])
                    self._sessions[thread_id] = session.session_id
                session_id = self._sessions[thread_id]
                self._active[session_id] = entry
                self.journal.mark_dispatched(run_id)
                response = await self._prompt(connection, session_id, text, mapping_failed)
                mapper.finish(response.stop_reason)
                outcome = "completed"
        except asyncio.CancelledError:
            outcome = "cancelled"
            self._unrecoverable.add(thread_id)
            span.set_status(trace.StatusCode.ERROR)
            self.journal.abort(run_id, "EXECUTION_UNKNOWN", "ACP execution cancelled; outcome unknown")
            raise
        except Exception as exc:
            self._unrecoverable.add(thread_id)
            span.set_status(trace.StatusCode.ERROR)
            code = "EVENT_MAPPING_FAILED" if mapping_failed.is_set() else "EXECUTION_UNKNOWN"
            outcome = code.lower()
            logger.warning("ACP run failed: run_id=%s code=%s error=%s", run_id, code, type(exc).__name__)
            self.journal.abort(run_id, code, "ACP execution interrupted; outcome unknown")
        finally:
            span.set_attribute("aidev.run.outcome", outcome)
            attrs = {"engine": self.settings.engine, "outcome": outcome}
            _ACP_RUNS.add(1, attrs)
            _ACP_RUN_DURATION.record(time.monotonic() - started, attrs)
            if session_id is not None:
                if self._active.get(session_id) is entry:
                    self._active.pop(session_id, None)
                if thread_id in self._unrecoverable and connection is not None and connection is self._connection:
                    with suppress(Exception):
                        await asyncio.wait_for(connection.cancel(session_id=session_id), timeout=2)

    async def _prompt(self, connection, session_id: str, text: str, mapping_failed: asyncio.Event):
        carrier: dict[str, str] = {}
        if self.settings.engine == "openclaw":
            _PROPAGATOR.inject(carrier)
        prompt = asyncio.create_task(
            connection.prompt(
                session_id=session_id,
                prompt=[text_block(text)],
                **carrier,
            )
        )
        failed = asyncio.create_task(mapping_failed.wait())
        try:
            await asyncio.wait({prompt, failed}, return_when=asyncio.FIRST_COMPLETED)
            if mapping_failed.is_set():
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
