import os
import threading
import time

import pytest
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.messages_handler.constants import EOD_CHUNK
from aidev_agent.services.messages_handler.redis import RedisMessageHandler


class _FakePipeline:
    def __init__(self, commands):
        self.commands = commands

    def xadd(self, *args, **kwargs):
        self.commands.append("XADD")
        return self

    def expire(self, *args, **kwargs):
        self.commands.append("EXPIRE")
        return self

    def zadd(self, *args, **kwargs):
        self.commands.append("ZADD")
        return self

    def execute(self):
        self.commands.append("EXEC")
        return [b"1-0", True, 1, True]


class _CapabilityClient:
    def __init__(self, version="6.2.20"):
        self.version = version
        self.commands = []

    def execute_command(self, command, *args):
        self.commands.append(command)
        if command == "HELLO":
            return [b"server", b"redis", b"version", self.version.encode()]
        raise AssertionError(command)

    def set(self, *args, **kwargs):
        self.commands.append("SET")
        return True

    def getdel(self, *args, **kwargs):
        self.commands.append("GETDEL")
        return b"probe"

    def pipeline(self, transaction=True):
        self.commands.extend(["MULTI"] if transaction else [])
        return _FakePipeline(self.commands)

    def xread(self, *args, **kwargs):
        self.commands.append("XREAD")
        return [(b"stream", [(b"1-0", {b"data": b"probe"})])]

    def eval(self, *args, **kwargs):
        self.commands.append("EVAL")
        return 1

    def delete(self, *args, **kwargs):
        self.commands.append("DEL")
        return len(args)


class _SignalClient:
    def __init__(self):
        self.values = {}
        self.get_calls = 0

    def set(self, key, value, **kwargs):
        self.values[key] = value
        return True

    def get(self, key):
        self.get_calls += 1
        return self.values.get(key)

    def getdel(self, key):
        return self.values.pop(key, None)

    def delete(self, *keys):
        deleted = 0
        for key in keys:
            deleted += key in self.values
            self.values.pop(key, None)
        return deleted

    def eval(self, script, numkeys, key, expected, replacement=None):
        if self.values.get(key) != expected:
            return 0
        if replacement is None:
            del self.values[key]
        else:
            self.values[key] = replacement
        return 1


class TestRedisMessageHandlerCapabilities:
    @pytest.mark.parametrize(
        ("response", "expected"),
        [
            ([b"server", b"redis", b"version", b"6.2.20"], (6, 2, 20)),
            ({"server": "redis", "version": "7.2.15"}, (7, 2, 15)),
        ],
    )
    def test_parse_hello_response(self, response, expected):
        assert RedisMessageHandler._parse_hello_response(response) == expected

    def test_validate_server_uses_only_data_commands(self):
        handler = object.__new__(RedisMessageHandler)
        handler._client = _CapabilityClient()

        assert handler._validate_server() == (6, 2, 20)
        forbidden_commands = {"INFO", "CONFIG", "COMMAND", "SCAN", "MONITOR"}
        assert forbidden_commands.isdisjoint(handler._client.commands)

    def test_validate_server_rejects_redis_before_62(self):
        handler = object.__new__(RedisMessageHandler)
        handler._client = _CapabilityClient(version="6.0.16")

        with pytest.raises(RuntimeError, match="requires Redis >= 6.2.0"):
            handler._validate_server()

    @pytest.mark.parametrize(
        ("stream_id", "expected"),
        [("0-0", 0), (b"1786085215988-12", 1786085215988000012)],
    )
    def test_cursor_round_trip(self, stream_id, expected):
        cursor = RedisMessageHandler._encode_cursor(stream_id)
        assert cursor == expected
        assert RedisMessageHandler._decode_cursor(cursor) == (
            stream_id.decode() if isinstance(stream_id, bytes) else stream_id
        )


class TestRedisMessageHandlerRunSignals:
    @pytest.fixture
    def handler(self):
        handler = object.__new__(RedisMessageHandler)
        handler._client = _SignalClient()
        handler._queue_ttl_seconds = 3600
        handler._cancel_check_cache = {}
        handler._cancel_check_cache_lock = threading.Lock()
        return handler

    def test_cancel_signal_is_scoped_to_current_run(self, handler):
        thread_id = "run-scoped-cancel"
        handler.set_cancel_signal(thread_id, run_id="run-old")

        assert handler.check_cancel_signal(thread_id, run_id="run-old")
        assert not handler.check_cancel_signal(thread_id, run_id="run-current")

        handler.clear_cancel_signal(thread_id, run_id="run-current")
        assert handler.check_cancel_signal(thread_id, run_id="run-old")

        handler.clear_cancel_signal(thread_id, run_id="run-old")
        assert not handler.check_cancel_signal(thread_id, run_id="run-old")

    def test_negative_cancel_checks_are_rate_limited(self, handler, monkeypatch):
        now = [100.0]
        monkeypatch.setattr("aidev_agent.services.messages_handler.redis.time.monotonic", lambda: now[0])
        thread_id = "rate-limited-cancel"

        assert not handler.check_cancel_signal(thread_id, run_id="run-current")
        assert not handler.check_cancel_signal(thread_id, run_id="run-current")
        assert handler._client.get_calls == 1

        handler._client.set(handler._cancel_signal_key(thread_id), b"run-current", ex=30)
        assert not handler.check_cancel_signal(thread_id, run_id="run-current")
        now[0] += handler.CANCEL_CHECK_MIN_INTERVAL
        assert handler.check_cancel_signal(thread_id, run_id="run-current")
        assert handler._client.get_calls == 2

    def test_legacy_cancel_signal_matches_scoped_run(self, handler):
        thread_id = "legacy-cancel"
        handler._client.set(handler._cancel_signal_key(thread_id), b"1", ex=30)

        assert handler.check_cancel_signal(thread_id, run_id="run-current")
        assert handler._client.get(handler._cancel_signal_key(thread_id)) == b"run-current"
        assert not handler.check_cancel_signal(thread_id, run_id="run-next")
        handler.clear_cancel_signal(thread_id, run_id="run-current")
        assert not handler.check_cancel_signal(thread_id, run_id="run-current")

    def test_replay_log_is_scoped_to_current_run(self, handler):
        thread_id = "run-scoped-replay"
        assert handler.replay_belongs_to_run(thread_id, "rolling-upgrade-run")
        handler.bind_replay_run(thread_id, "run-old")

        assert handler.replay_belongs_to_run(thread_id, "run-old")
        assert not handler.replay_belongs_to_run(thread_id, "run-current")

    def test_cancelled_notification_does_not_consume_other_run(self, handler):
        thread_id = "run-scoped-notification"
        handler.notify_consumer_cancelled(thread_id, run_id="run-old")

        assert not handler.wait_for_consumer_cancelled(thread_id, timeout=0.01, run_id="run-current")
        assert handler.wait_for_consumer_cancelled(thread_id, timeout=0.2, run_id="run-old")

        handler.notify_consumer_cancelled(thread_id, run_id="run-current")
        assert handler.wait_for_consumer_cancelled(thread_id, timeout=0.2, run_id="run-current")

    def test_new_run_cleanup_preserves_registered_consumer_and_stop_signals(self, handler):
        thread_id = "preserve-active-run-state"
        cleanup_keys = handler._session_data_keys(thread_id)

        assert handler._active_consumers_key(thread_id) not in cleanup_keys
        assert handler._cancel_signal_key(thread_id) not in cleanup_keys
        assert handler._cancelled_signal_key(thread_id) not in cleanup_keys


@pytest.fixture
def redis_62_handler(monkeypatch):
    redis_url = os.getenv("AIDEV_TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("AIDEV_TEST_REDIS_URL is not configured")
    monkeypatch.setenv("MESSAGE_REDIS_URL", redis_url)
    RedisMessageHandler._instance = None
    handler = RedisMessageHandler()
    yield handler
    handler.close()
    RedisMessageHandler._instance = None


@pytest.mark.e2e
class TestRedisMessageHandlerIntegration:
    @staticmethod
    def _stream_run(handler, thread_id, run_id, chunks):
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        cancel_event = helper.prepare_run(run_id)
        return list(
            helper.stream(
                iter(chunks),
                expected_run_id=run_id,
                cancel_event=cancel_event,
            )
        )

    @staticmethod
    def _cleanup_completed_replay(handler, thread_id, consumer_id):
        if consumer_id is not None:
            handler.release_consumer(thread_id, consumer_id)
        handler.mark_completed(thread_id)
        handler.clear(thread_id)
        handler.release_producer(thread_id)

    def test_redis_62_multi_reader_replay(self, redis_62_handler):
        thread_id = "redis-handler-integration"
        handler = redis_62_handler

        try:
            assert handler.server_version[:2] == (6, 2)
            assert handler.acquire_producer(thread_id) is True
            assert handler.acquire_producer(thread_id) is False

            consumer_a = handler.acquire_consumer(thread_id)
            consumer_b = handler.acquire_consumer(thread_id)
            first = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"a"}\n\n'
            second = 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"b"}\n\n'
            handler.put(thread_id, first)
            handler.put(thread_id, second)
            handler.flush(thread_id)

            messages_a, offset_a = handler.get_messages_since(thread_id, 0, timeout=1.0)
            messages_b, offset_b = handler.get_messages_since(thread_id, 0, timeout=1.0)
            assert messages_a == messages_b == [first, second]
            assert offset_a == offset_b

            committed = threading.Event()
            handler.register_eod_commit_event(thread_id, committed)
            handler.put(thread_id, EOD_CHUNK)
            handler.flush(thread_id)
            handler.mark_completed(thread_id)
            tail_a, _ = handler.get_messages_since(thread_id, offset_a, timeout=1.0)
            tail_b, _ = handler.get_messages_since(thread_id, offset_b, timeout=1.0)
            assert tail_a == tail_b == [EOD_CHUNK]
            assert committed.is_set()
            assert handler.has_pending_messages(thread_id) is True
        finally:
            handler.release_consumer(thread_id, consumer_a)
            handler.release_consumer(thread_id, consumer_b)
            handler.clear(thread_id)
            handler.release_producer(thread_id)

    def test_completed_replay_expiry_is_refreshed_by_consumer_heartbeat(self, redis_62_handler, monkeypatch):
        thread_id = "redis-handler-completed-replay-ttl"
        handler = redis_62_handler
        consumer_id = None
        monkeypatch.setattr(handler, "_completed_stream_ttl_seconds", 2)
        try:
            handler.clear(thread_id)
            assert handler.acquire_producer(thread_id)
            handler.bind_replay_run(thread_id, "run-current")
            handler.put(thread_id, "replay-event")
            handler.flush(thread_id)
            consumer_id = handler.acquire_consumer(thread_id)
            handler.notify_consumer_cancelled(thread_id, run_id="run-current")

            assert handler.arm_completed_replay_expiry(thread_id)
            assert handler._client.exists(handler._cancelled_signal_key(thread_id))
            handler.release_producer(thread_id)

            time.sleep(1.2)
            handler.check_consumer(thread_id, consumer_id)
            time.sleep(1.2)
            assert handler._client.exists(handler._stream_key(thread_id))

            handler.release_consumer(thread_id, consumer_id)
            consumer_id = None
            time.sleep(2.2)
            assert not handler._client.exists(handler._stream_key(thread_id))
        finally:
            self._cleanup_completed_replay(handler, thread_id, consumer_id)

    @pytest.mark.parametrize("message_count", [100])
    def test_flushes_when_buffer_reaches_limit(self, redis_62_handler, message_count):
        thread_id = "redis-handler-flush-limit"
        handler = redis_62_handler
        try:
            assert handler.acquire_producer(thread_id) is True
            messages = [f"event-{index}" for index in range(message_count)]
            for message in messages:
                handler.put(thread_id, message)
            replayed, _ = handler.get_messages_since(thread_id, 0, timeout=1.0)
            assert replayed == messages
        finally:
            handler.clear(thread_id)
            handler.release_producer(thread_id)

    def test_daemon_flushes_within_interval(self, redis_62_handler):
        thread_id = "redis-handler-flush-interval"
        handler = redis_62_handler
        try:
            assert handler.acquire_producer(thread_id) is True
            handler.put(thread_id, "event-from-daemon")
            replayed, _ = handler.get_messages_since(thread_id, 0, timeout=1.0)
            assert replayed == ["event-from-daemon"]
        finally:
            handler.clear(thread_id)
            handler.release_producer(thread_id)

    def test_cross_process_cancel_before_stream_reset_is_preserved(self, redis_62_handler):
        thread_id = "redis-handler-early-cancel"
        run_id = "run-current"
        handler = redis_62_handler
        handler.clear(thread_id)
        helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
        cancel_event = helper.prepare_run(run_id)

        try:
            # 模拟 stop 请求落到另一个 worker：只写 Redis，不设置本进程 Event。
            assert handler.set_cancel_signal(thread_id, run_id=run_id)
            chunks = list(
                helper.stream(
                    iter(["must-not-be-emitted"]),
                    expected_run_id=run_id,
                    cancel_event=cancel_event,
                )
            )

            assert "must-not-be-emitted" not in chunks
            assert handler.wait_for_consumer_cancelled(thread_id, timeout=1.0, run_id=run_id)
        finally:
            handler.clear(thread_id)
            handler.release_producer(thread_id)

    def test_new_run_after_cancel_does_not_replay_stopped_run(self, redis_62_handler):
        thread_id = "redis-handler-new-run-after-cancel"
        handler = redis_62_handler
        handler.clear(thread_id)

        try:
            assert handler.set_cancel_signal(thread_id)
            cancelled_chunks = self._stream_run(handler, thread_id, "run-cancelled", ["must-not-be-emitted"])
            assert "must-not-be-emitted" not in cancelled_chunks
            assert not handler._client.exists(handler._cancel_signal_key(thread_id))
            assert handler._client.exists(handler._stream_key(thread_id))
            assert not handler.replay_belongs_to_run(thread_id, "run-next")

            next_chunks = self._stream_run(handler, thread_id, "run-next", ["next-run-output"])
            assert "next-run-output" in next_chunks
        finally:
            handler.clear(thread_id)
            handler.release_producer(thread_id)

    def test_refresh_with_new_run_id_replays_active_producer(self, redis_62_handler):
        thread_id = "redis-handler-refresh-active-producer"
        handler = redis_62_handler
        handler.clear(thread_id)

        try:
            assert handler.acquire_producer(thread_id)
            handler.bind_replay_run(thread_id, "run-original")
            handler.put(thread_id, "original-run-output")
            handler.put(thread_id, EOD_CHUNK)
            handler.flush(thread_id)

            helper = GeneratorStreamingHelper(handler, thread_id=thread_id)
            replayed = list(
                helper.stream(
                    iter(["must-not-start-second-producer"]),
                    expected_run_id="run-created-by-refresh",
                )
            )

            assert "original-run-output" in replayed
            assert "must-not-start-second-producer" not in replayed
        finally:
            handler.clear(thread_id)
            handler.release_producer(thread_id)
