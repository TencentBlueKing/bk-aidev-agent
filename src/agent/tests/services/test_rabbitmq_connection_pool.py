import os
import threading
import time
from dataclasses import dataclass, field

import pika
import pytest
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQConnectionPool


@dataclass
class FakeConnection:
    number: int
    is_open: bool = True
    closed: bool = False
    fail_validation: bool = False
    operation_threads: list[int] = field(default_factory=list)

    def process_data_events(self, time_limit: float = 0) -> None:
        self.operation_threads.append(threading.get_ident())
        if self.fail_validation:
            raise RuntimeError("validation failed")

    def close(self) -> None:
        self.operation_threads.append(threading.get_ident())
        self.closed = True
        self.is_open = False


class FakeConnectionPool(RabbitMQConnectionPool):
    def __init__(self, pool_size: int = 2, connection_timeout: float = 0.01):
        super().__init__("amqp://unused", pool_size, connection_timeout)
        self.connections: list[FakeConnection] = []
        self.create_errors: list[Exception] = []

    def _create_connection(self) -> FakeConnection:
        if self.create_errors:
            raise self.create_errors.pop(0)
        connection = FakeConnection(len(self.connections) + 1)
        self.connections.append(connection)
        return connection


class TestRabbitMQConnectionPool:
    def test_normal_operations_keep_connection_count_and_churn_bounded(self):
        pool = FakeConnectionPool(pool_size=2)

        for _ in range(100):
            with pool.connection():
                pass

        assert len(pool.connections) == 1
        assert pool.created_count == 1
        assert pool.available_count == 1
        assert pool._generation == 0
        pool.close()

    def test_exhausted_pool_rotates_once_and_recovers(self, caplog):
        pool = FakeConnectionPool(pool_size=2, connection_timeout=0.005)
        stale = [pool.get_connection() for _ in range(pool.pool_size)]

        replacement = pool.get_connection()

        assert pool._generation == 1
        assert pool.created_count == 1
        assert len(pool.connections) == 3
        assert "Rotated exhausted RabbitMQ connection pool" in caplog.text
        assert "thread_name" in caplog.text

        for connection in stale:
            pool.release_connection(connection)
            assert connection.closed is True
        pool.release_connection(replacement)
        assert pool.available_count == 1
        pool.close()

    def test_normal_contention_waits_for_release_without_extra_connections(self):
        pool = FakeConnectionPool(pool_size=2, connection_timeout=0.2)
        held = [pool.get_connection() for _ in range(pool.pool_size)]
        acquired = []

        def borrow() -> None:
            acquired.append(pool.get_connection())

        thread = threading.Thread(target=borrow)
        thread.start()
        time.sleep(0.02)

        assert acquired == []
        assert len(pool.connections) == 2
        pool.release_connection(held.pop())
        thread.join()

        assert pool._generation == 0
        assert len(pool.connections) == 2
        for connection in [*held, *acquired]:
            pool.release_connection(connection)
        pool.close()

    def test_concurrent_waiters_do_not_rotate_generation_repeatedly(self):
        pool = FakeConnectionPool(pool_size=2, connection_timeout=0.01)
        stale = [pool.get_connection() for _ in range(pool.pool_size)]
        replacements = []

        def borrow() -> None:
            replacements.append(pool.get_connection())

        threads = [threading.Thread(target=borrow) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert pool._generation == 1
        assert pool.created_count == 2
        assert len(pool.connections) == 4
        for connection in [*stale, *replacements]:
            pool.release_connection(connection)
        pool.close()

    def test_second_rotation_is_blocked_until_old_generation_drains(self):
        pool = FakeConnectionPool(pool_size=2, connection_timeout=0.005)
        oldest = [pool.get_connection() for _ in range(pool.pool_size)]
        current = [pool.get_connection() for _ in range(pool.pool_size)]

        with pytest.raises(TimeoutError, match="Failed to get connection"):
            pool.get_connection()

        assert pool._generation == 1
        assert len(pool.connections) == 4

        for connection in oldest:
            pool.release_connection(connection)
        assert pool._rotation_in_flight is False
        for connection in current:
            pool.release_connection(connection)
        pool.close()

    def test_invalid_idle_connection_is_explicitly_closed(self):
        pool = FakeConnectionPool()
        with pool.connection() as connection:
            pass
        connection.fail_validation = True

        replacement = pool.get_connection()

        assert connection.closed is True
        assert replacement is not connection
        assert pool.created_count == 1
        pool.release_connection(replacement)
        pool.close()

    def test_body_exception_discards_current_generation_connection(self):
        pool = FakeConnectionPool()

        with pytest.raises(ValueError, match="body failed"), pool.connection() as connection:
            raise ValueError("body failed")

        assert connection.closed is True
        assert pool.created_count == 0
        assert pool.available_count == 0
        pool.close()

    def test_connection_creation_retries_and_reports_leases(self, caplog):
        pool = FakeConnectionPool()
        pool.create_errors = [OSError("first"), OSError("second")]

        with pool.connection():
            pass

        assert "attempt 1/3" in caplog.text
        assert "attempt 2/3" in caplog.text
        assert "leases=[]" in caplog.text
        pool.close()

    def test_blocked_timeout_matches_pool_timeout(self, monkeypatch):
        captured = {}

        def create_connection(params):
            captured["params"] = params
            return FakeConnection(1)

        monkeypatch.setattr(pika, "BlockingConnection", create_connection)
        pool = RabbitMQConnectionPool("amqp://guest:guest@localhost/", connection_timeout=2.5)

        connection = pool.get_connection()

        assert captured["params"].heartbeat == 60
        assert captured["params"].blocked_connection_timeout == 2.5
        pool.release_connection(connection)
        pool.close()

    def test_pool_state_resets_when_worker_pid_changes(self, monkeypatch):
        pool = FakeConnectionPool()
        with pool.connection():
            pass
        first = pool.connections[0]
        monkeypatch.setattr(os, "getpid", lambda: pool._pid + 1)

        with pool.connection() as second:
            pass

        assert second is not first
        assert len(pool.connections) == 2
        assert pool._generation == 0
        assert pool.created_count == 1
        pool.close()

    def test_close_rejects_new_connections_and_active_old_connection_can_release(self):
        pool = FakeConnectionPool()
        connection = pool.get_connection()

        pool.close()

        with pytest.raises(RuntimeError, match="Connection pool is closed"):
            pool.get_connection()
        pool.release_connection(connection)
        assert connection.closed is True
        assert pool.created_count == 0
