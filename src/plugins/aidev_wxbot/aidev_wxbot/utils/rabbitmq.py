import json
import logging
import threading
import time
from contextlib import contextmanager
from functools import wraps
from queue import Empty, Queue
from typing import Any, Callable, Dict, Optional

import pika
from django.conf import settings
from pika.exceptions import ChannelClosedByBroker

# 设置pika库的日志级别为ERROR
pika_logger = logging.getLogger("pika")
pika_logger.setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class ConnectionPool:
    """RabbitMQ连接池"""

    def __init__(self, max_connections=10):
        self.max_connections = max_connections
        self.connections = Queue(maxsize=max_connections)
        self.connection_params = None
        self._lock = threading.Lock()
        self._created_connections = 0

    def set_connection_params(self, params):
        """设置连接参数"""
        self.connection_params = params

    def get_connection(self):
        """获取连接"""
        try:
            # 尝试从池中获取连接
            connection = self.connections.get_nowait()
            if connection and not connection.is_closed:
                # 检查连接是否真正可用
                try:
                    # 尝试创建一个临时通道来测试连接
                    test_channel = connection.channel()
                    test_channel.close()
                    return connection
                except Exception as e:
                    logger.warning(f"连接健康检查失败，创建新连接: {e}")
                    # 连接不可用，减少计数并创建新连接
                    with self._lock:
                        self._created_connections -= 1
                    try:
                        connection.close()
                    except Exception:
                        pass
                    return self._create_connection()
            else:
                # 连接已关闭，减少计数并创建新连接
                if connection:
                    with self._lock:
                        self._created_connections -= 1
                return self._create_connection()
        except Empty:
            # 池中没有连接，创建新连接
            return self._create_connection()

    def return_connection(self, connection):
        """归还连接到池"""
        if connection and not connection.is_closed:
            try:
                self.connections.put_nowait(connection)
            except Exception as e:
                # 池已满，关闭连接
                logger.exception(e)
                connection.close()
        else:
            # 连接已关闭，减少计数
            with self._lock:
                self._created_connections -= 1

    def _create_connection(self):
        """创建新连接"""
        with self._lock:
            if self._created_connections >= self.max_connections:
                raise Exception("连接池已满")

            try:
                connection = pika.BlockingConnection(self.connection_params)
                self._created_connections += 1
                return connection
            except Exception as e:
                logger.error(f"创建连接失败: {e}")
                raise

    def close_all(self):
        """关闭所有连接"""
        while not self.connections.empty():
            try:
                connection = self.connections.get_nowait()
                if connection and not connection.is_closed:
                    connection.close()
            except Exception as e:
                logger.exception(e)
        self._created_connections = 0


def with_connection_retry(max_retries=3, retry_delay=0.5):
    """装饰器工厂：使用连接池中的连接，支持自定义重试参数"""

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                connection = None
                channel = None
                try:
                    connection = self.connection_pool.get_connection()
                    channel = connection.channel()
                    # 将channel作为第一个参数传递给方法
                    result = func(self, channel, *args, **kwargs)
                    logger.debug(f"操作成功 (尝试 {attempt + 1}/{max_retries})")
                    return result

                except (
                    ConnectionResetError,
                    ConnectionError,
                    OSError,
                    pika.exceptions.StreamLostError,
                    pika.exceptions.ConnectionClosed,
                    pika.exceptions.ChannelClosedByBroker,
                ) as e:
                    last_exception = e
                    logger.warning(f"连接/通道错误 (尝试 {attempt + 1}/{max_retries}): {e}")

                    # 连接相关错误，清理连接并重试
                    if channel:
                        try:
                            channel.close()
                        except Exception:
                            pass
                    if connection:
                        try:
                            connection.close()
                        except Exception:
                            pass
                        # 不要将失效的连接放回池中
                        connection = None

                    if attempt < max_retries - 1:
                        sleep_time = retry_delay * (2**attempt)  # 指数退避
                        logger.info(f"等待 {sleep_time:.2f} 秒后重试...")
                        time.sleep(sleep_time)
                        continue

                except Exception as e:
                    # 非连接相关的错误，不重试
                    logger.error(f"执行操作时出错 (不重试): {e}")
                    raise
                finally:
                    if channel and not channel.is_closed:
                        try:
                            channel.close()
                        except Exception as e:
                            logger.debug(f"关闭通道时出错: {e}")
                    if connection:
                        self.connection_pool.return_connection(connection)

            # 所有重试都失败了
            logger.error(f"操作失败，已达到最大重试次数: {max_retries}")
            raise last_exception

        return wrapper

    return decorator


def with_connection(func):
    """装饰器：使用连接池中的连接，默认重试参数"""
    return with_connection_retry(max_retries=3, retry_delay=0.5)(func)


class RabbitMQClient:
    """RabbitMQ客户端类，用于与RabbitMQ进行交互"""

    def __init__(self, max_connections=10):
        """初始化RabbitMQ客户端"""
        self.host = settings.RABBITMQ_HOST
        self.port = settings.RABBITMQ_PORT
        self.username = settings.RABBITMQ_USER
        self.password = settings.RABBITMQ_PASSWORD
        self.vhost = settings.RABBITMQ_VHOST

        # 初始化连接池
        self.connection_pool = ConnectionPool(max_connections)
        self.connection_pool.set_connection_params(self._get_connection_parameters())

        # 线程锁，用于保护关键操作
        self._lock = threading.Lock()

    def _get_connection_parameters(self) -> pika.ConnectionParameters:
        """获取连接参数"""
        credentials = pika.PlainCredentials(self.username, self.password)
        return pika.ConnectionParameters(
            host=self.host,
            port=self.port,
            virtual_host=self.vhost,
            credentials=credentials,
            heartbeat=600,
            blocked_connection_timeout=300,
        )

    @contextmanager
    def get_connection(self):
        """上下文管理器，自动管理连接"""
        connection = None
        channel = None
        try:
            connection = self.connection_pool.get_connection()
            channel = connection.channel()
            yield channel
        except Exception as e:
            logger.error(f"获取连接时出错: {e}")
            raise
        finally:
            if channel and not channel.is_closed:
                try:
                    channel.close()
                except Exception as e:
                    logger.exception(e)
            if connection:
                self.connection_pool.return_connection(connection)

    def close_all_connections(self):
        """关闭所有连接"""
        self.connection_pool.close_all()

    def reset_connection_pool(self):
        """重置连接池，用于处理连接问题"""
        try:
            logger.info("正在重置 RabbitMQ 连接池...")
            self.close_all_connections()
            # 重新初始化连接池
            self.connection_pool = ConnectionPool(self.connection_pool.max_connections)
            self.connection_pool.set_connection_params(self._get_connection_parameters())
            logger.info("RabbitMQ 连接池重置完成")
        except Exception as e:
            logger.error(f"重置连接池失败: {e}")

    def health_check(self) -> bool:
        """健康检查，测试连接是否正常"""
        try:
            with self.get_connection() as channel:
                # 尝试声明一个临时队列来测试连接
                test_queue = f"health_check_{int(time.time())}"
                channel.queue_declare(queue=test_queue, durable=False, auto_delete=True)
                channel.queue_delete(queue=test_queue)
                return True
        except Exception as e:
            logger.error(f"健康检查失败: {e}")
            return False

    @with_connection_retry(max_retries=5, retry_delay=0.3)
    def declare_queue(
        self,
        channel,
        queue_name: str,
        durable: bool = True,
        exclusive: bool = False,
        auto_delete: bool = False,
        arguments: Optional[Dict] = None,
    ) -> bool:
        """声明队列"""
        try:
            channel.queue_declare(
                queue=queue_name,
                durable=durable,
                exclusive=exclusive,
                auto_delete=auto_delete,
                arguments=arguments or {},
            )
            logger.debug(f"队列 '{queue_name}' 声明成功")
            return True
        except Exception as e:
            logger.error(f"声明队列 '{queue_name}' 失败: {e}")
            raise  # 让装饰器处理重试逻辑

    @with_connection_retry(max_retries=5, retry_delay=0.3)
    def declare_exchange(
        self,
        channel,
        exchange_name: str,
        exchange_type: str = "direct",
        durable: bool = True,
        auto_delete: bool = False,
        arguments: Optional[Dict] = None,
    ) -> bool:
        """声明交换机"""
        try:
            channel.exchange_declare(
                exchange=exchange_name,
                exchange_type=exchange_type,
                durable=durable,
                auto_delete=auto_delete,
                arguments=arguments or {},
            )
            logger.debug(f"交换机 '{exchange_name}' 声明成功")
            return True
        except Exception as e:
            logger.error(f"声明交换机 '{exchange_name}' 失败: {e}")
            raise  # 让装饰器处理重试逻辑

    @with_connection
    def bind_queue(self, channel, queue_name: str, exchange_name: str, routing_key: str = "") -> bool:
        """绑定队列到交换机"""
        try:
            channel.queue_bind(exchange=exchange_name, queue=queue_name, routing_key=routing_key)
            logger.info(f"队列 '{queue_name}' 绑定到交换机 '{exchange_name}' 成功")
            return True
        except Exception as e:
            logger.error(f"绑定队列失败: {e}")
            return False

    @with_connection_retry(max_retries=5, retry_delay=0.3)
    def publish_message(
        self, channel, exchange: str, routing_key: str, message: Any, properties: Optional[pika.BasicProperties] = None
    ) -> bool:
        """发布消息"""
        try:
            # 如果消息不是字符串，则转换为JSON
            if not isinstance(message, str):
                message = json.dumps(message, ensure_ascii=False)

            # 设置默认属性
            if properties is None:
                properties = pika.BasicProperties(
                    delivery_mode=2,  # 持久化消息
                    content_type="application/json",
                )

            channel.basic_publish(exchange=exchange, routing_key=routing_key, body=message, properties=properties)
            logger.debug(f"消息发布成功: exchange='{exchange}', routing_key='{routing_key}'")
            return True
        except Exception as e:
            logger.error(f"发布消息失败: {e}")
            raise e  # 让装饰器处理重试逻辑

    @with_connection
    def consume_messages(
        self, channel, queue_name: str, callback: Callable, auto_ack: bool = False, prefetch_count: int = 1
    ):
        """消费消息"""
        try:
            # 设置QoS
            channel.basic_qos(prefetch_count=prefetch_count)

            # 包装回调函数
            def wrapped_callback(ch, method, properties, body):
                try:
                    # 尝试解析JSON消息
                    try:
                        message = json.loads(body.decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        message = body.decode("utf-8")

                    # 调用用户回调函数
                    result = callback(ch, method, properties, message)

                    # 如果不是自动确认且回调返回True，则手动确认
                    if not auto_ack and result is not False:
                        ch.basic_ack(delivery_tag=method.delivery_tag)

                except Exception as e:
                    logger.error(f"处理消息时出错: {e}")
                    if not auto_ack:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

            channel.basic_consume(queue=queue_name, on_message_callback=wrapped_callback, auto_ack=auto_ack)

            logger.debug(f"开始消费队列 '{queue_name}' 的消息...")
            channel.start_consuming()

        except KeyboardInterrupt:
            logger.debug("收到中断信号，停止消费消息")
            channel.stop_consuming()
        except Exception as e:
            logger.error(f"消费消息失败: {e}")

    @with_connection_retry(max_retries=5, retry_delay=0.3)
    def get_message(self, channel, queue_name: str, auto_ack: bool = False) -> Optional[Dict]:
        """获取单条消息"""
        try:
            method, properties, body = channel.basic_get(queue=queue_name, auto_ack=auto_ack)

            if method is None:
                return None

            # 尝试解析JSON消息
            try:
                message = json.loads(body.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                message = body.decode("utf-8")

            return {"method": method, "properties": properties, "body": message}
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            raise  # 让装饰器处理重试逻辑

    @with_connection
    def ack_message(self, channel, delivery_tag: int) -> bool:
        """确认消息"""
        try:
            channel.basic_ack(delivery_tag=delivery_tag)
            return True
        except Exception as e:
            logger.error(f"确认消息失败: {e}")
            return False

    @with_connection
    def nack_message(self, channel, delivery_tag: int, requeue: bool = True) -> bool:
        """拒绝消息"""
        try:
            channel.basic_nack(delivery_tag=delivery_tag, requeue=requeue)
            return True
        except Exception as e:
            logger.error(f"拒绝消息失败: {e}")
            return False

    @with_connection
    def purge_queue(self, channel, queue_name: str) -> bool:
        """清空队列"""
        try:
            channel.queue_purge(queue=queue_name)
            logger.debug(f"队列 '{queue_name}' 已清空")
            return True
        except Exception as e:
            logger.error(f"清空队列失败: {e}")
            return False

    @with_connection_retry(max_retries=3, retry_delay=0.5)
    def delete_queue(self, channel, queue_name: str, if_unused: bool = False, if_empty: bool = False) -> bool:
        """删除队列"""
        try:
            channel.queue_delete(queue=queue_name, if_unused=if_unused, if_empty=if_empty)
            logger.debug(f"队列 '{queue_name}' 已删除")
            return True
        except Exception as e:
            logger.error(f"删除队列失败: {e}")
            raise  # 让装饰器处理重试逻辑

    @with_connection_retry(max_retries=5, retry_delay=0.3)
    def get_queue_info(self, channel, queue_name: str) -> Optional[Dict]:
        """获取队列信息"""
        try:
            method = channel.queue_declare(queue=queue_name, passive=True)
            return {
                "queue": queue_name,
                "message_count": method.method.message_count,
                "consumer_count": method.method.consumer_count,
            }
        except ChannelClosedByBroker as e:
            if e.reply_text.startswith("NOT_FOUND"):
                return None
            logger.error(f"获取队列信息失败: {e}")
            raise  # 让装饰器处理重试逻辑
        except Exception as e:
            logger.error(f"获取队列信息失败: {e}")
            raise  # 让装饰器处理重试逻辑


# 创建全局实例
rabbitmq_client = RabbitMQClient()


# 便捷函数
def publish_to_queue(queue_name: str, message: Any, durable: bool = True) -> bool:
    """发布消息到队列的便捷函数"""
    try:
        # 声明队列
        rabbitmq_client.declare_queue(queue_name, durable=durable)
        # 发布消息
        return rabbitmq_client.publish_message("", queue_name, message)
    except Exception as e:
        logger.error(f"发布消息到队列失败: {e}")
        return False


def publish_to_exchange(
    exchange_name: str, routing_key: str, message: Any, exchange_type: str = "direct", durable: bool = True
) -> bool:
    """发布消息到交换机的便捷函数"""
    try:
        # 声明交换机
        rabbitmq_client.declare_exchange(exchange_name, exchange_type, durable=durable)
        # 发布消息
        return rabbitmq_client.publish_message(exchange_name, routing_key, message)
    except Exception as e:
        logger.error(f"发布消息到交换机失败: {e}")
        return False


def consume_from_queue(queue_name: str, callback: Callable, auto_ack: bool = False, prefetch_count: int = 1):
    """从队列消费消息的便捷函数"""
    try:
        # 声明队列
        rabbitmq_client.declare_queue(queue_name)
        # 开始消费
        rabbitmq_client.consume_messages(queue_name, callback, auto_ack, prefetch_count)
    except Exception as e:
        logger.error(f"消费队列消息失败: {e}")
