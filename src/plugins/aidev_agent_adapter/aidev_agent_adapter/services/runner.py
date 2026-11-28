"""由用户沙箱发起管控连接，每个业务会话使用独立的 WSS。"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from opentelemetry import context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake, InvalidStatus

from .adapter import Adapter

logger = logging.getLogger(__name__)
HEARTBEAT_INTERVAL = 15.0
_PROPAGATOR = TraceContextTextMapPropagator()


class DirectConnection(connect):
    def process_redirect(self, exc):
        # Registration credentials are valid only for the configured Channel origin.
        return exc


async def send_frame(socket, kind: str, **fields: Any) -> None:
    await socket.send(json.dumps({"type": kind, **fields}, ensure_ascii=False))


def origin(url: str) -> tuple[str, int]:
    target = urlsplit(url)
    if target.scheme != "wss" or not target.hostname or target.username or target.password or target.fragment:
        raise ValueError("expected a secure Channel URL")
    return target.hostname, target.port or 443


async def serve_session(
    adapter: Adapter,
    url: str,
    session: str,
    ticket: str,
    epoch: int,
    carrier: dict[str, str] | None = None,
) -> None:
    async with DirectConnection(url, max_size=2**21) as socket:
        await send_frame(
            socket, "session.register", session_code=session, ticket=ticket, epoch=epoch, **(carrier or {})
        )
        registered = json.loads(await asyncio.wait_for(socket.recv(), 15))
        if registered.get("type") != "session.ready" or registered.get("epoch") != epoch:
            raise ValueError("session registration rejected")

        async def stream(run_id: str, after: int) -> None:
            async for envelope in adapter.events(run_id, after):
                await send_frame(socket, "session.event", **envelope)

        sender: asyncio.Task | None = None
        try:
            async for raw in socket:
                frame = json.loads(raw)
                kind = frame["type"]
                if kind == "session.close":
                    return
                if kind == "event.ack":
                    continue
                run_id = frame["run_id"]
                if kind == "chat.cancel":
                    if adapter.journal.belongs_to(run_id, session):
                        await adapter.cancel(run_id)
                    continue
                if kind not in {"chat.submit", "chat.resume"}:
                    raise ValueError("unsupported session frame")
                if sender and not sender.done():
                    await send_frame(socket, "session.busy", run_id=run_id)
                    continue
                if sender:
                    await sender
                if kind == "chat.submit":
                    parent = _PROPAGATOR.extract(frame)
                    token = context.attach(parent)
                    try:
                        await adapter.submit(run_id, session, frame["text"], queued_ns=frame.get("queued_ns"))
                    finally:
                        context.detach(token)
                if not adapter.journal.belongs_to(run_id, session):
                    await send_frame(socket, "session.unknown", run_id=run_id)
                    continue
                after = frame.get("after", 0)
                if type(after) is not int or after < 0:
                    raise ValueError("invalid replay cursor")
                sender = asyncio.create_task(stream(run_id, after))
        finally:
            if sender:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)


async def _open_session(
    adapter: Adapter,
    sessions: dict[str, asyncio.Task],
    expected_origin: tuple[str, int],
    epoch: int,
    frame: dict[str, Any],
    finish_cb,
) -> None:
    session = frame["session_code"]
    if origin(frame["url"]) != expected_origin:
        raise ValueError("session origin mismatch")
    task = sessions.get(session)
    if task and not task.done():
        # Session tickets belong to a connection epoch.
        if task.get_name() == str(epoch):
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    carrier = {k: frame[k] for k in ("traceparent", "tracestate") if k in frame}
    sessions[session] = asyncio.create_task(
        serve_session(adapter, frame["url"], session, frame["ticket"], epoch, carrier),
        name=str(epoch),
    )
    sessions[session].add_done_callback(lambda done, key=session: finish_cb(key, done))


async def serve_runner(adapter: Adapter, url: str, ticket_file: Path, sandbox_id: str) -> None:
    expected_origin = origin(url)
    sessions: dict[str, asyncio.Task] = {}
    startup_parent = os.environ.get("AIDEV_STARTUP_TRACEPARENT")

    def finish(key: str, done: asyncio.Task) -> None:
        if sessions.get(key) is done:
            sessions.pop(key)
        if not done.cancelled() and done.exception() is not None:
            logger.warning("Session connection closed before completion: error=%s", type(done.exception()).__name__)

    delay = 1
    try:
        while True:
            try:
                async with DirectConnection(url, max_size=65536) as socket:
                    await send_frame(
                        socket,
                        "runner.register",
                        sandbox_id=sandbox_id,
                        ticket=ticket_file.read_text(encoding="utf-8").strip(),
                        **({"traceparent": startup_parent} if startup_parent else {}),
                    )
                    ready = json.loads(await asyncio.wait_for(socket.recv(), 15))
                    if ready.get("type") != "runner.ready":
                        raise ValueError("runner registration rejected")
                    startup_parent = None
                    epoch = ready["epoch"]
                    delay = 1
                    loop = asyncio.get_running_loop()
                    next_heartbeat = loop.time() + HEARTBEAT_INTERVAL
                    while True:
                        remaining = next_heartbeat - loop.time()
                        if remaining <= 0:
                            await send_frame(socket, "runner.heartbeat", epoch=epoch)
                            next_heartbeat = loop.time() + HEARTBEAT_INTERVAL
                            continue
                        try:
                            raw = await asyncio.wait_for(socket.recv(), remaining)
                        except TimeoutError:
                            continue
                        frame = json.loads(raw)
                        if frame.get("epoch") != epoch or frame.get("type") != "session.open":
                            continue
                        await _open_session(adapter, sessions, expected_origin, epoch, frame, finish)
            except InvalidStatus as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", 0)
                if status_code >= 500 or status_code == 429:
                    logger.warning("Runner handshake transient HTTP %s; retrying in %ss", status_code, delay)
                    await asyncio.sleep(delay)
                    delay = min(30, delay * 2)
                    continue
                raise
            except (ConnectionClosed, InvalidHandshake, OSError, TimeoutError) as exc:
                logger.warning("Runner connection interrupted (%s); retrying in %ss", type(exc).__name__, delay)
                await asyncio.sleep(delay)
                delay = min(30, delay * 2)
    finally:
        pending = list(sessions.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
