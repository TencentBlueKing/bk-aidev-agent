"""Django 请求周期之外的同步后台任务数据库连接边界。"""

from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from typing import ParamSpec, TypeVar

from django.db import DatabaseError, InterfaceError, close_old_connections, connections

P = ParamSpec("P")
T = TypeVar("T")


def _close_unusable_connections() -> None:
    """探测当前线程已有连接，覆盖尚未被 Django 标记的断连。"""
    for connection in connections.all(initialized_only=True):
        if connection.connection is None or connection.in_atomic_block or not connection.get_autocommit():
            continue
        try:
            # 直接探测旧 socket，不用 PyMySQL ping 的隐式重连，避免跳过
            # Django 新连接的会话初始化；也不为未使用的数据库建立连接。
            with connection.wrap_database_errors, closing(connection.connection.cursor()) as cursor:
                cursor.execute("SELECT 1")
        except (DatabaseError, InterfaceError):
            connection.close()


@contextmanager
def database_connection_scope() -> Iterator[None]:
    """在实际 ORM 工作线程清理过期/失效连接，不重试任何业务操作。

    Django 连接按线程隔离，不能在事件循环中替其他线程清理。任务结束即使
    异常被内部捕获，也要检查连接状态，避免下一次复用同一线程时持续失败。
    在请求/任务边界（事务外）使用。入口探测已有连接，保留健康连接的复用；
    探测成功后仍可能断连，业务异常原样交给调用方，不重放业务。
    """
    try:
        close_old_connections()
        _close_unusable_connections()
        yield
    finally:
        close_old_connections()


def run_with_database_connections(function: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """供 ``to_thread`` 调用；懒生成器需在 scope 内完成迭代而非仅创建。"""
    with database_connection_scope():
        return function(*args, **kwargs)
