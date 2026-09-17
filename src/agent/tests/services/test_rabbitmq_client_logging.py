import logging

from aidev_agent.services.messages_handler.rabbitmq import (
    _PikaExpectedDisconnectFilter,
    configure_amqp_client_logging,
)


def _record(level: int, message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="pika.adapters.utils.io_services_utils",
        level=level,
        pathname="",
        lineno=0,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_pika_connection_reset_is_demoted_to_warning():
    record = _record(
        logging.ERROR,
        "Unexpected connection close detected: ConnectionResetError(104, 'Connection reset by peer')",
    )

    assert _PikaExpectedDisconnectFilter().filter(record) is True
    assert record.levelno == logging.WARNING
    assert record.levelname == "WARNING"


def test_pika_handshake_timeout_stays_error():
    record = _record(logging.ERROR, "AMQPConnectorStackTimeout: timeout while connecting")

    assert _PikaExpectedDisconnectFilter().filter(record) is True
    assert record.levelno == logging.ERROR


def test_configure_amqp_client_logging_hides_broker_info():
    configure_amqp_client_logging()

    assert logging.getLogger("pika").level == logging.WARNING
    assert logging.getLogger("rstream").level == logging.WARNING
