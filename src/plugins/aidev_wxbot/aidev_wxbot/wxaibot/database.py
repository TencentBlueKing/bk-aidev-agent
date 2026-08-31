"""Django 请求周期之外的同步后台任务数据库连接边界。"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import ParamSpec, TypeVar

from django.db import close_old_connections

P = ParamSpec("P")
T = TypeVar("T")


@contextmanager
def database_connection_scope() -> Iterator[None]:
    """在实际 ORM 工作线程清理过期/失效连接，不重试任何业务操作。

    Django 连接按线程隔离，不能在事件循环中替其他线程清理。任务结束即使
    异常被内部捕获，也要检查连接状态，避免下一次复用同一线程时持续失败。
    保留 Django 的连接复用策略，不无条件关闭健康连接。
    """
    try:
        close_old_connections()
        yield
    finally:
        close_old_connections()


def run_with_database_connections(function: Callable[P, T], /, *args: P.args, **kwargs: P.kwargs) -> T:
    """供 ``to_thread`` 调用；懒生成器需在 scope 内完成迭代而非仅创建。"""
    with database_connection_scope():
        return function(*args, **kwargs)
