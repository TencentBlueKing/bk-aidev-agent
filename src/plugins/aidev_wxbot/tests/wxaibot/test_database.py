"""后台线程的 Django 连接清理必须包围实际执行，且不能重试业务。"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from aidev_wxbot.wxaibot import database
from django.db import InterfaceError, OperationalError

from .test_long_connection import StreamDrain, _service


@pytest.fixture
def existing_connection(monkeypatch):
    connection = MagicMock(in_atomic_block=False)
    connection.get_autocommit.return_value = True
    connection.wrap_database_errors = nullcontext()
    monkeypatch.setattr(database, "close_old_connections", MagicMock())
    monkeypatch.setattr("django.db.connections.all", MagicMock(return_value=[connection]))
    return connection


@pytest.mark.parametrize("error", [None, InterfaceError(0, ""), OperationalError(2013, "lost connection")])
def test_scope_checks_existing_socket_before_business(existing_connection, error):
    connection = existing_connection
    cursor = connection.connection.cursor.return_value
    cursor.execute.side_effect = error
    operation = MagicMock(return_value="result")
    assert database.run_with_database_connections(operation) == "result"
    cursor.execute.assert_called_once_with("SELECT 1")
    assert connection.close.call_count == (error is not None)
    operation.assert_called_once_with()


def test_failed_probe_is_discarded_before_business_runs(existing_connection):
    connection = existing_connection
    connection.connection.cursor.return_value.execute.side_effect = InterfaceError(0, "")

    def operation():
        connection.close.assert_called_once_with()

    database.run_with_database_connections(operation)


@pytest.mark.parametrize("disconnect", [False, True])
def test_sqlite_probe_preserves_or_replaces_existing_connection(monkeypatch, django_db_blocker, tmp_path, disconnect):
    from django.db.utils import ConnectionHandler

    handler = ConnectionHandler({"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": tmp_path / "probe.db"}})
    connection = handler["default"]
    monkeypatch.setattr(database.connections, "all", lambda **_kw: [connection])
    connection.settings_dict["CONN_MAX_AGE"] = None
    with django_db_blocker.unblock():
        connection.ensure_connection()
        raw = connection.connection
        if disconnect:
            raw.close()
        try:
            with database.database_connection_scope(), connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                assert cursor.fetchone() == (1,)
                assert (connection.connection is raw) == (not disconnect)
        finally:
            connection.close()


@pytest.mark.parametrize("state", ["unopened", "atomic", "manual_transaction"])
def test_scope_does_not_probe_unopened_or_transaction_connections(existing_connection, state):
    connection = existing_connection
    raw = connection.connection
    if state == "unopened":
        connection.connection = None
    elif state == "atomic":
        connection.in_atomic_block = True
    else:
        connection.get_autocommit.return_value = False
    assert database.run_with_database_connections(lambda: "result") == "result"
    raw.cursor.assert_not_called()
    connection.close.assert_not_called()


@pytest.mark.parametrize("failed", [False, True])
def test_cleanup_wraps_worker_call_without_retry(monkeypatch, failed):
    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append(("clean", threading.get_ident())))

    def operation():
        events.append(("call", threading.get_ident()))
        if failed:
            raise InterfaceError(0, "")
        return "result"

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(database.run_with_database_connections, operation)
        if failed:
            with pytest.raises(InterfaceError):
                future.result()
        else:
            assert future.result() == "result"
    assert [name for name, _ in events] == ["clean", "call", "clean"]
    assert len({ident for _, ident in events}) == 1
    assert events[0][1] != threading.get_ident()


async def test_message_prepare_cleanup_stays_in_worker(monkeypatch):
    service = _service()
    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append(threading.get_ident()))
    service._view.prepare_agent_request.side_effect = lambda _payload: (
        events.append(threading.get_ident()) or {},
        None,
    )
    service._dispatch_immediate_response = AsyncMock()
    await service._handle_frame({"body": {"msgtype": "text"}})
    assert len(events) == 3
    assert len(set(events)) == 1
    assert events[0] != threading.get_ident()


async def test_other_message_cleanup_stays_in_worker(monkeypatch):
    service = _service()
    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append(threading.get_ident()))
    service._view._reply_wxaibot.side_effect = lambda _payload: events.append(threading.get_ident()) or {}
    service._dispatch_immediate_response = AsyncMock()
    await service._handle_frame({"body": {"msgtype": "image"}})
    assert len(events) == 3 and len(set(events)) == 1
    assert events[0] != threading.get_ident()


@pytest.mark.parametrize("failed", [False, True])
def test_legacy_callback_worker_is_cleaned_even_when_error_is_caught(monkeypatch, failed):
    from aidev_wxbot.wxaibot import views

    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append("clean"))
    monkeypatch.setattr(views, "LlmChunkMsg", MagicMock())
    view = object.__new__(views.WxAiBotViewSet)
    view._get_or_create_thread_id = MagicMock(return_value="thread")
    execute = MagicMock(side_effect=InterfaceError(0, "") if failed else lambda **_kw: None)
    monkeypatch.setattr(views, "resolve_strategy", lambda _user: MagicMock(execute=execute))
    view._process_ai_request_async("test", "test-stream", "test-user", "test-group")
    assert events == ["clean", "clean"]
    assert execute.call_count == 1


@pytest.mark.parametrize("failed", [False, True])
def test_producer_cleanup_covers_agent_iteration(monkeypatch, failed):
    service = _service()
    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append("clean"))

    def produce(*_args):
        events.append("iterate")
        if failed:
            raise InterfaceError(0, "")

    service._produce_agent_frames = produce
    if failed:
        with pytest.raises(InterfaceError):
            service._produce_direct_stream(None, None, None, None)
    else:
        service._produce_direct_stream(None, None, None, None)
    assert events == ["clean", "iterate", "clean"]


@pytest.mark.parametrize("failed", [False, True])
def test_drain_cleanup_runs_after_generator_close(monkeypatch, failed):
    service = _service()
    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append("clean"))

    def frames():
        try:
            events.append("iterate")
            if failed:
                raise InterfaceError(0, "")
            yield "frame"
        finally:
            events.append("generator_closed")

    drain = StreamDrain("test-stream")
    service._drain_stream_frames(frames(), drain)
    assert drain.completed.is_set()
    assert events == ["clean", "iterate", "generator_closed", "clean"]


async def test_cancel_cleanup_wraps_identity_and_operation(monkeypatch, approval_card_case):
    from aidev_wxbot.wxaibot import long_connection

    service = _service()
    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append("clean"))
    service._view.resolve_event_username.side_effect = lambda _payload: events.append("identity") or "user"
    dispatch = MagicMock(side_effect=lambda *_args: events.append("cancel") or {})
    monkeypatch.setattr(long_connection, "dispatch_user_operation", dispatch)
    await service._handle_frame({"body": approval_card_case.event})
    assert events == ["clean", "identity", "clean", "clean", "cancel", "clean"]
    assert dispatch.call_count == 1


async def test_question_identity_cleanup_stays_in_worker(monkeypatch, question_case):
    from aidev_wxbot.wxaibot import long_connection
    from aidev_wxbot.wxaibot.question_cards import encode_question_key, question_task_id

    service, events = _service(), []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append(("clean", threading.get_ident())))
    service._view.resolve_event_username.side_effect = (
        lambda _: events.append(("identity", threading.get_ident())) or "alice"
    )
    monkeypatch.setattr(long_connection, "prepare_question_submission", lambda *_: SimpleNamespace())
    monkeypatch.setattr(long_connection, "submit_question_resume", lambda *_: "busy")
    service._new_resume_delivery = MagicMock()
    service._send_resume_message = AsyncMock()
    action = question_case.action
    payload = {
        "from": {"userid": action.target},
        "event": {
            "eventtype": "template_card_event",
            "template_card_event": {
                "event_key": encode_question_key(action),
                "task_id": question_task_id(action),
            },
        },
    }
    assert await service._handle_question_card_event({"body": payload}, payload)
    assert [name for name, _ in events] == ["clean", "identity", "clean"]
    assert len({ident for _, ident in events}) == 1 and events[0][1] != threading.get_ident()


async def test_cancelling_awaiter_keeps_cleanup_in_worker(monkeypatch):
    started, release, finished = threading.Event(), threading.Event(), threading.Event()
    events = []
    monkeypatch.setattr(database, "close_old_connections", lambda: events.append("clean"))

    def operation():
        started.set()
        release.wait(2)
        events.append("done")

    def worker():
        try:
            database.run_with_database_connections(operation)
        finally:
            finished.set()

    task = asyncio.create_task(asyncio.to_thread(worker))
    while not started.is_set():
        await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    assert await asyncio.to_thread(finished.wait, 2)
    assert events == ["clean", "done", "clean"]
