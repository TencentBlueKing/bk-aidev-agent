import contextlib
from unittest.mock import MagicMock

import pika
import pytest
from aidev_agent.services.messages_handler.rabbitmq import _RabbitMQConsumerMixin


class _StoppedProbe(_RabbitMQConsumerMixin):
    def __init__(self, channel):
        self._channel = channel

    @contextlib.contextmanager
    def _with_channel(self):
        yield self._channel


class TestIsStopped:
    @pytest.mark.parametrize(
        ("exc", "expect_warning"),
        [
            (pika.exceptions.ChannelClosedByBroker(404, "NOT_FOUND - no queue"), False),
            (pika.exceptions.ChannelClosedByBroker(406, "PRECONDITION_FAILED"), True),
            (RuntimeError("channel failed"), True),
        ],
    )
    def test_is_stopped_treats_missing_queue_as_false(self, caplog, exc, expect_warning):
        channel = MagicMock()
        channel.queue_declare.side_effect = exc
        with caplog.at_level("WARNING"):
            assert _StoppedProbe(channel).is_stopped("new_session") is False
        assert ("stopped queue" in caplog.text) is expect_warning
        assert "Error declaring stopped queue" not in caplog.text

    def test_is_stopped_when_signal_present(self):
        channel = MagicMock()
        channel.basic_get.return_value = (MagicMock(), None, b'{"stopped": true}')
        assert _StoppedProbe(channel).is_stopped("new_session") is True
        channel.basic_reject.assert_called_once()
