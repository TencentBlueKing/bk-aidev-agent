"""在长耗时等待的同步边界释放连接，不跨线程或重放数据库操作。"""

import asyncio
from logging import getLogger

try:
    from django.conf import settings
    from django.db import connections
except ImportError:
    connections = None
    settings = None

logger = getLogger(__name__)


def release_idle_connections() -> None:
    """只释放当前线程已建立的自动提交连接，保留 atomic 和手动事务。"""
    if connections is None or settings is None or not settings.configured:
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        # 异步 ORM 的连接属于工作线程，必须在工作线程边界清理。
        return
    for database in connections.all(initialized_only=True):
        if database.connection is None or database.in_atomic_block or not database.get_autocommit():
            continue
        try:
            database.close()
        except Exception:
            logger.warning("释放空闲数据库连接失败：alias=%s", database.alias, exc_info=True)
