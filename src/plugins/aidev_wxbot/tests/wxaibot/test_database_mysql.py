"""显式 opt-in 的隔离 MySQL 5.7 连接恢复测试，不读取应用数据库配置。

准备仅绑定本机的临时 MySQL 5.7，空密码及数据库 wxbot_recovery_test。
测试环境需安装 PyMySQL。通过 WXBOT_TEST_MYSQL_PORT 指定临时实例端口后，
从插件 Makefile 运行；测试入口使用与平台 PatchFeatures 相同的 5.7 版本门槛。
"""

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aidev_wxbot.wxaibot import views
from aidev_wxbot.wxaibot.database import run_with_database_connections
from django.db import InterfaceError, connections
from django.db.utils import ConnectionHandler

pytestmark = pytest.mark.skipif(not os.getenv("WXBOT_TEST_MYSQL_PORT"), reason="requires isolated MySQL 5.7")


@pytest.fixture
def mysql_session_store(monkeypatch, django_db_blocker):
    import pymysql

    pymysql.install_as_MySQLdb()
    from django.db.backends.mysql.features import DatabaseFeatures

    # 独立插件测试不加载平台的 PatchFeatures；仅复用其最低版本声明，
    # 不替换驱动、真实版本查询、SQL 执行或连接状态判断。
    monkeypatch.setattr(DatabaseFeatures, "minimum_database_version", (5, 7))
    alias = "wxbot_recovery_test"
    config = ConnectionHandler(
        {
            "default": {
                "ENGINE": "django.db.backends.mysql",
                "HOST": "127.0.0.1",
                "PORT": int(os.environ["WXBOT_TEST_MYSQL_PORT"]),
                "USER": "root",
                "PASSWORD": "",
                "NAME": "wxbot_recovery_test",
                "CONN_MAX_AGE": None,
                "OPTIONS": {"connect_timeout": 3, "read_timeout": 3, "write_timeout": 3},
            }
        }
    ).databases["default"]
    monkeypatch.setitem(connections.databases, alias, config)
    manager = views.AgentSession.objects.db_manager(alias)
    monkeypatch.setattr(views.AgentSession, "objects", manager)
    context = SimpleNamespace(msg_id="test-message", sender_id="test-user", group_id="test-user")
    monkeypatch.setattr(views.ContextGenerator, "generate", lambda _self: context)
    view = object.__new__(views.WxAiBotViewSet)
    with django_db_blocker.unblock():
        connection = connections[alias]
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), DATABASE()")
            version, name = cursor.fetchone()
        assert version.startswith("5.7.") and name == "wxbot_recovery_test"
        with connection.schema_editor() as editor:
            editor.create_model(views.AgentSession)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                try:
                    yield SimpleNamespace(alias=alias, manager=manager, view=view, pool=pool, context=context)
                finally:
                    pool.submit(lambda: connections[alias].close()).result()
        finally:
            with connection.schema_editor() as editor:
                editor.delete_model(views.AgentSession)
            connection.close()
            del connections[alias]


def _close_socket_with_error(alias):
    connection = connections[alias]
    connection.ensure_connection()
    connection.connection._force_close()
    with pytest.raises(InterfaceError) as raised, connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    assert raised.value.args == (0, "")
    assert connection.errors_occurred
    return threading.get_ident()


def _disconnect_without_error_flag(alias, mode):
    connection = connections[alias]
    connection.ensure_connection()
    old_id = _select_connection_id(alias)
    if mode == "socket_closed":
        connection.connection._force_close()
    else:
        controller = connection.copy(alias="disconnect_controller")
        try:
            with controller.cursor() as cursor:
                cursor.execute("KILL CONNECTION %s", [old_id])
        finally:
            controller.close()
    assert not connection.errors_occurred
    assert not connection.health_check_enabled
    assert connection.close_at is None
    return threading.get_ident(), old_id


@pytest.mark.parametrize("mode", ["socket_closed", "server_closed"])
def test_first_new_recovers_without_prior_failed_query(mysql_session_store, mode):
    store = mysql_session_store
    worker_id, old_id = store.pool.submit(_disconnect_without_error_flag, store.alias, mode).result()
    response, request = store.pool.submit(run_with_database_connections, _prepare, store.view, "/new").result()
    assert response["stream"]["content"] == "已创建新会话，请输入咨询内容" and request is None
    assert store.manager.count() == 1
    assert store.pool.submit(threading.get_ident).result() == worker_id
    new_id = store.pool.submit(_select_connection_id, store.alias).result()
    assert new_id != old_id


def _prepare(view, command):
    return view.prepare_agent_request({"msgtype": "text", "text": {"content": command}})


def _connection_is_reusable(alias):
    connection = connections[alias]
    # PyMySQL ping 可原地重连；清理后的结果允许关闭，或已恢复且无错误标记。
    return connection.connection is None or (not connection.errors_occurred and connection.connection.open)


@pytest.mark.parametrize("command", ["/new", "新会话", "会话"])
def test_stale_connection_repeated_failure_then_recovery(mysql_session_store, command):
    store = mysql_session_store
    worker_id = store.pool.submit(_close_socket_with_error, store.alias).result()
    for _ in range(2):
        response, request = store.pool.submit(_prepare, store.view, command).result()
        assert response["stream"]["content"] == "服务暂时不可用" and request is None
    assert store.manager.count() == 0
    for _ in range(2):
        response, request = store.pool.submit(run_with_database_connections, _prepare, store.view, command).result()
        assert response["stream"]["content"] == "已创建新会话，请输入咨询内容" and request is None
    assert store.manager.count() == 1
    assert store.pool.submit(threading.get_ident).result() == worker_id
    response, request = store.pool.submit(run_with_database_connections, _prepare, store.view, "hello").result()
    assert response is None and request.content == "hello"
    thread_id = store.pool.submit(
        run_with_database_connections, store.view._get_or_create_thread_id, "test-user"
    ).result()
    assert thread_id == store.manager.get(group_id="test-user").thread_id


def test_in_task_failure_is_cleaned_before_next_request(mysql_session_store):
    store = mysql_session_store

    def failing_request():
        _close_socket_with_error(store.alias)
        return _prepare(store.view, "/new")

    response, _ = store.pool.submit(run_with_database_connections, failing_request).result()
    assert response["stream"]["content"] == "服务暂时不可用"
    assert store.pool.submit(_connection_is_reusable, store.alias).result()
    response, _ = store.pool.submit(run_with_database_connections, _prepare, store.view, "/new").result()
    assert response["stream"]["content"] == "已创建新会话，请输入咨询内容"
    assert store.manager.count() == 1


def _select_connection_id(alias):
    with connections[alias].cursor() as cursor:
        cursor.execute("SELECT CONNECTION_ID()")
        return cursor.fetchone()[0]


@pytest.mark.parametrize("max_age", [None, 0])
def test_connection_reuse_respects_max_age(mysql_session_store, max_age):
    store = mysql_session_store
    connections.databases[store.alias]["CONN_MAX_AGE"] = max_age
    ids = [
        store.pool.submit(run_with_database_connections, _select_connection_id, store.alias).result() for _ in range(2)
    ]
    assert (ids[0] == ids[1]) == (max_age is None)
    assert store.pool.submit(lambda: connections[store.alias].connection is None).result() == (max_age == 0)


def _long_connection_service(store, monkeypatch, settings, chat_type):
    from aidev_wxbot.wxaibot import long_connection

    from .test_long_connection import _service

    # The legacy long-connection tests load this subclass with a stub base.
    class DatabaseView(long_connection._LongConnectionViewSet, views.WxAiBotViewSet):
        pass

    service = _service()
    service._view = object.__new__(DatabaseView)
    service._view._service = service
    service._dispatch_immediate_response = AsyncMock()
    settings.WAXIBOT_NAME = "test-bot"
    store.context.group_id = "test-user" if chat_type == "single" else "test-group"
    scope = service._view._session_scope(store.context.group_id, store.context.sender_id)

    async def to_worker(function, *args):
        return await asyncio.get_running_loop().run_in_executor(store.pool, partial(function, *args))

    monkeypatch.setattr(long_connection.asyncio, "to_thread", to_worker)
    return service, scope


@pytest.mark.parametrize("chat_type", ["single", "group"])
async def test_long_connection_new_recovers_in_actual_worker(mysql_session_store, monkeypatch, settings, chat_type):
    store = mysql_session_store
    service, scope = _long_connection_service(store, monkeypatch, settings, chat_type)
    worker_id = store.pool.submit(_close_socket_with_error, store.alias).result()
    for _ in range(2):
        content = "/new" if chat_type == "single" else "@test-bot /new"
        frame = {"body": {"msgtype": "text", "chattype": chat_type, "text": {"content": content}}}
        await service._handle_frame(frame)
        response = service._dispatch_immediate_response.call_args.args[2]
        assert response["stream"]["content"] == "已创建新会话，请输入咨询内容"
    assert store.pool.submit(lambda: store.manager.filter(group_id=scope).count()).result() == 1
    assert store.pool.submit(threading.get_ident).result() == worker_id
