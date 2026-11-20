"""Stream 创建前持久登记回收任务；worker 重启后继续处理同一 vhost 的任务。"""

import json
import logging
import math
import threading
import time

import pika

logger = logging.getLogger(__name__)


class StreamCleanupQueue:
    NAME = "aidev_agent.stream_cleanup.v1"
    POLL_SECONDS = 10

    def __init__(self, handler):
        self.handler = handler
        self.queue_name = self.NAME
        self.stop_event = threading.Event()
        self.thread = None
        self.lock = threading.Lock()

    def start(self):
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.stop_event.clear()
                self.thread = threading.Thread(target=self._run, daemon=True, name="Stream-Recovery")
                self.thread.start()

    def remember(self, stream):
        if not stream.startswith(self.handler.STREAM_PREFIX) or stream == self.handler.STREAM_PREFIX:
            raise ValueError("Expected a dedicated SDK Stream name")
        with self.handler._with_channel() as channel:
            channel.queue_declare(self.queue_name, durable=True)
            channel.confirm_delivery()
            self._publish(channel, stream)

    def _publish(self, channel, stream):
        due = time.time() + self.handler.QUEUE_TTL_MS / 1000
        channel.basic_publish(
            "",
            self.queue_name,
            json.dumps([due, stream]).encode(),
            mandatory=True,
            properties=pika.BasicProperties(delivery_mode=2),
        )

    def _run(self):
        while not self.stop_event.is_set():
            try:
                # 独立连接持有未确认任务；检查期间常规数据面仍可使用完整连接池。
                connection = self.handler._create_dedicated_connection()
                try:
                    channel = connection.channel()
                    channel.queue_declare(self.queue_name, durable=True)
                    channel.tx_select()
                    while not self.stop_event.is_set():
                        delay = self._step(channel)
                        connection.process_data_events(time_limit=0)
                        self.stop_event.wait(min(delay, self.POLL_SECONDS))
                finally:
                    if connection.is_open:
                        connection.close()
            except Exception:
                logger.exception("Stream cleanup worker will reconnect")
                self.stop_event.wait(self.POLL_SECONDS)

    def _step(self, channel):
        method, _, body = channel.basic_get(self.queue_name, auto_ack=False)
        if method is None:
            return self.POLL_SECONDS
        try:
            due, stream = json.loads(body)
            if not isinstance(due, (int, float)) or not math.isfinite(due):
                raise ValueError("Invalid due time")
            prefix = self.handler.STREAM_PREFIX
            if not isinstance(stream, str) or not stream.startswith(prefix) or stream == prefix:
                raise ValueError("Invalid stream name")
        except (ValueError, TypeError, OverflowError):
            logger.warning("Discarding malformed Stream cleanup ticket")
            channel.basic_ack(method.delivery_tag)
            channel.tx_commit()
            return 0
        remaining = due - time.time()
        if remaining > 0:
            channel.basic_nack(method.delivery_tag, requeue=True)
            channel.tx_commit()
            return remaining

        try:
            complete = self.handler._reap_if_idle(stream[len(self.handler.STREAM_PREFIX) :], recovery=True)
        except Exception:
            logger.exception("Stream cleanup check failed; retaining ticket for %s", stream)
            complete = False
        if not complete:
            self._publish(channel, stream)
        # 续票和旧票确认在同一队列、同一事务；崩溃时不会丢任务。
        channel.basic_ack(method.delivery_tag)
        channel.tx_commit()
        return 0
