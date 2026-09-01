import threading
from dataclasses import dataclass, field

import pika
import pytest
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQConnectionPool


@dataclass
class FakeConnection:
    number: int
    creator_thread_id: int = field(default_factory=threading.get_ident)
    is_open: bool = True
    closed_by_thread_id: int | None = None
    fail_validation: bool = False

    def process_data_events(self, time_limit: float = 0) -> None:
        if self.fail_validation:
            raise RuntimeError("validation failed")

    def close(self) -> None:
        self.closed_by_thread_id = threading.get_ident()
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
    def test_connection_is_created_and_closed_in_borrower_thread(self):
        pool = FakeConnectionPool()

        with pool.connection() as connection:
            assert connection.creator_thread_id == threading.get_ident()
            assert pool.created_count == 1

        assert connection.closed_by_thread_id == connection.creator_thread_id
        assert pool.created_count == 0
        assert pool.available_count == 0

    def test_explicit_reuse_keeps_connection_in_owner_thread(self):
        pool = FakeConnectionPool()

        with pool.connection(reuse=True) as first:
            pass
        with pool.connection(reuse=True) as second:
            pass

        assert second is first
        assert pool.available_count == 1
        pool.close()
        assert first.closed_by_thread_id == first.creator_thread_id

    def test_sequential_threads_do_not_reuse_connection(self):
        pool = FakeConnectionPool(pool_size=1)
        observations = []

        def worker() -> None:
            with pool.connection(reuse=True) as connection:
                observations.append((connection.number, connection.creator_thread_id, threading.get_ident()))

        for _ in range(2):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join()

        assert [item[0] for item in observations] == [1, 2]
        assert all(creator == borrower for _, creator, borrower in observations)
        assert len(pool.connections) == 2

    def test_configured_pool_size_does_not_block_new_borrower(self):
        pool = FakeConnectionPool(pool_size=2)
        held = [pool.get_connection() for _ in range(pool.pool_size)]

        extra = pool.get_connection()

        assert pool.created_count == 3
        assert len(pool._lease_snapshot()) == 3
        for connection in [*held, extra]:
            pool.release_connection(connection)
        assert pool.created_count == 0
        assert pool.available_count == 0

    def test_invalid_connection_is_closed_and_removed_from_lease(self):
        pool = FakeConnectionPool()
        connection = pool.get_connection()
        connection.fail_validation = True

        pool.release_connection(connection)

        assert connection.is_open is False
        assert connection.closed_by_thread_id == threading.get_ident()
        assert pool.created_count == 0
        assert pool.available_count == 0

    def test_connection_cannot_be_released_from_another_thread(self):
        pool = FakeConnectionPool()
        connection = pool.get_connection()
        errors = []

        def release_from_other_thread() -> None:
            with pytest.raises(RuntimeError, match="must be released by its owner thread") as exc_info:
                pool.release_connection(connection)
            errors.append(str(exc_info.value))

        thread = threading.Thread(target=release_from_other_thread)
        thread.start()
        thread.join()

        assert errors
        assert connection.is_open is True
        pool.release_connection(connection)
        assert pool.created_count == 0

    def test_body_exception_closes_connection_without_retry(self):
        pool = FakeConnectionPool()

        with pytest.raises(ValueError, match="body failed"), pool.connection():
            raise ValueError("body failed")

        assert len(pool.connections) == 1
        assert pool.connections[0].is_open is False
        assert pool.created_count == 0

    def test_connection_creation_retries_and_reports_active_leases(self, caplog):
        pool = FakeConnectionPool()
        pool.create_errors = [OSError("first"), OSError("second")]

        with pool.connection() as connection:
            assert connection.number == 1

        assert "attempt 1/3" in caplog.text
        assert "attempt 2/3" in caplog.text
        assert "active=0 leases=[]" in caplog.text

    def test_create_connection_aligns_blocked_timeout_with_acquire_timeout(self, monkeypatch):
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

    def test_close_rejects_new_connections_but_owner_can_release_active_one(self):
        pool = FakeConnectionPool()
        connection = pool.get_connection()

        pool.close()

        with pytest.raises(RuntimeError, match="Connection pool is closed"):
            pool.get_connection()
        pool.release_connection(connection)
        assert connection.is_open is False
        assert pool.created_count == 0
