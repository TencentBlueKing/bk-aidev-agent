"""不同 Message Handler 的消费者心跳超时策略。"""

import pytest
from aidev_agent.services.messages_handler.constants import HEARTBEAT_TIMEOUT
from aidev_agent.services.messages_handler.in_memory import InMemoryQueueMessageHandler
from aidev_agent.services.messages_handler.rabbitmq import RabbitMQMessageHandler
from aidev_agent.services.messages_handler.rabbitmq_stream import RabbitMQStreamMessageHandler
from aidev_agent.services.messages_handler.redis import RedisMessageHandler


@pytest.mark.parametrize(
    ("handler_class", "expected_timeout"),
    [
        (InMemoryQueueMessageHandler, HEARTBEAT_TIMEOUT),
        (RedisMessageHandler, HEARTBEAT_TIMEOUT),
        (RabbitMQStreamMessageHandler, HEARTBEAT_TIMEOUT),
        (RabbitMQMessageHandler, 60.0),
    ],
)
def test_consumer_heartbeat_timeout_is_handler_specific(handler_class, expected_timeout):
    handler = object.__new__(handler_class)

    assert expected_timeout == handler.CONSUMER_HEARTBEAT_TIMEOUT
