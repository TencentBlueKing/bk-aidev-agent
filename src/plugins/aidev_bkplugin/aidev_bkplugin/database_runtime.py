"""在实际 ORM 线程获取游标前回收失效连接，不重放业务 SQL。"""

from functools import wraps

from django.db.backends.base.base import BaseDatabaseWrapper


def install_database_connection_guard() -> None:
    """为所有数据库 alias 和 ORM 线程安装一次连接预检。"""
    original = BaseDatabaseWrapper._cursor
    if getattr(original, "_aidev_connection_guard", False):
        return

    @wraps(original)
    def guarded_cursor(database, *args, **kwargs):
        database.validate_thread_sharing()
        if database.connection is not None and not database.in_atomic_block:
            # 直接探测驱动连接，避免 Django 游标递归和 pymysql ping 自动重连。
            with database.wrap_database_errors:
                try:
                    with database.connection.cursor() as probe:
                        probe.execute("SELECT 1")
                except database.Database.Error:
                    database.close()
        return original(database, *args, **kwargs)

    guarded_cursor._aidev_connection_guard = True
    BaseDatabaseWrapper._cursor = guarded_cursor
