import json
import logging
import time
import uuid
from typing import Any

from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field

from aidev_wxbot.api.bkaidev import BkAiDevApi
from aidev_wxbot.context import Context, Message
from aidev_wxbot.context.message import MsgType

logger = logging.getLogger(__name__)


def stream_msg(content, is_finish, stream_id):
    return {
        "msgtype": "stream",
        "stream": {
            "id": stream_id,
            "finish": is_finish,
            "content": content,
        },
    }


class LlmChunkMsg(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    is_finish: bool = Field(default=False)
    docs: list[dict] = Field(default_factory=list)
    content: str = Field(default_factory=str)
    stream_id: str = Field(default_factory=str)
    think_content: str = Field(default_factory=str)

    @property
    def docs_content(self):
        if self.docs:
            content = "\n当前回答参考的文档如下:\n"
            for index, doc in enumerate(self.docs):
                display_name = doc["display_name"]
                path = doc["path"]
                content += f"[{index + 1}][{display_name}]({path})\n"
            return content
        else:
            return ""

    def append_to_cache(self, rabbitmq_client):
        """将消息内容发送到RabbitMQ队列"""
        try:
            queue_name = self.stream_id

            # 准备消息数据
            message_data = {
                "content": self.content,
                "think_content": self.think_content,
                "is_finish": self.is_finish,
                "docs": self.docs,
                "timestamp": time.time(),
            }

            # 使用独立的连接发送消息，避免并发冲突
            rabbitmq_client.declare_queue(queue_name, durable=False, auto_delete=False)
            success = rabbitmq_client.publish_message("", queue_name, message_data)
            if success:
                logger.debug(f"消息已发送到队列 {queue_name}, is_finish: {self.is_finish}")
            else:
                logger.error(f"发送消息到队列 {queue_name} 失败")

        except Exception as e:
            logger.error(f"append_to_cache 出错: {e}, stream_id: {self.stream_id}")
            raise e

    def wxaibot_msg_json_from_cache(self, rabbitmq_client):
        """从RabbitMQ队列读取消息内容"""
        try:
            queue_name = self.stream_id
            is_finish = False
            stream_time = int(self.stream_id.split("_")[1])

            # 检查消息是否超时
            if time.time() - stream_time > settings.MAX_MESSAGE_TIME:  # 消息时间太久
                return stream_msg("消息超时！请重新发送！", True, self.stream_id)

            # 等待队列中有消息
            for i in range(3):  # 队列里还没消息
                queue_info = rabbitmq_client.get_queue_info(queue_name)
                if queue_info and queue_info.get("message_count", 0) > 0:
                    break
                else:
                    logger.info(f"stream_id:{self.stream_id} 消息还未有第一次回复...")
                    time.sleep(1)
            else:
                return stream_msg("正在思考中....", is_finish, self.stream_id)

            # 读取消息
            for i in range(30):  # 最多尝试30次
                try:
                    message_info = rabbitmq_client.get_message(queue_name, auto_ack=True)
                    if message_info:
                        message_data = message_info["body"]
                        content = message_data.get("content", "")
                        thinking_content = message_data.get("think_content", "")
                        if thinking_content:
                            content = f"<think>{thinking_content}</think>{content}"
                        if message_data.get("is_finish", False):
                            try:
                                rabbitmq_client.delete_queue(queue_name)
                                logger.debug(f"stream_id:{self.stream_id} 队列 {queue_name} 已删除")
                                self.docs = message_data.get("docs", [])
                                content += self.docs_content
                            except Exception as e:
                                logger.error(f"stream_id:{self.stream_id} 删除队列 {queue_name} 失败: {e}")
                        logger.info(f"stream_id:{self.stream_id} 回复的内容: {content}")
                        return stream_msg(content, message_data.get("is_finish", False), self.stream_id)
                    else:
                        time.sleep(0.3)
                except Exception as e:
                    logger.error(f"stream_id:{self.stream_id} 读取队列消息出错: {e}")
                    return stream_msg("读取消息失败，请重试", True, self.stream_id)
        except Exception as e:
            logger.error(f"stream_id:{self.stream_id} wxaibot_msg_json_from_cache 出错: {e}")
            return stream_msg("读取消息失败，请重试", True, self.stream_id)


class WxWorkAiBotContext(Context):
    origin_dict: Any = Field(default={})
    stream_id: str = Field(default="")
    msg_id: str = Field(default="")


class ContextGenerator:
    """
    分析原始信息，生成Context

    参看utils/context/__init__.py定义的Context类。
    """

    def __init__(self, payload: dict):
        self.payload = payload
        self.max_recursion = 3

    def generate(self) -> WxWorkAiBotContext:
        logger.info(f"企微传递的参数是 {json.dumps(self.payload, ensure_ascii=False)}")
        sender_code = self.payload.get("from", {}).get("userid")
        try:
            sender_id = BkAiDevApi().convert_to_rtx(sender_code)["userid"]
        except Exception as e:
            logger.error(f"convert_to_rtx 出错: {e}")
            sender_id = sender_code
        from_type = self.payload.get("chattype")
        chat_id = self.payload.get("chatid")
        ctx_data = {
            "msg_id": self.payload.get("msgid", uuid.uuid4().hex),
            "from_type": from_type,
            "sender_id": sender_id,
            "sender_code": sender_code,
            "to_me": True,
            "origin_dict": self.payload,
            "group_id": chat_id if chat_id else sender_id,
        }

        ctx = WxWorkAiBotContext(**ctx_data)
        message = Message()
        origin_msg_type = self.payload["msgtype"]
        ctx.message = getattr(self, f"_{origin_msg_type}_create")(message, self.payload)
        return ctx

    def _text_create(self, message: Message, payload: dict):
        content = payload["text"]["content"]
        message.msg_type = MsgType.Text.value
        message.text = content
        return message

    def _event_create(self, message: Message, payload: dict):
        message.msg_type = MsgType.Event.value
        message.event = payload.get("event").get("eventtype")
        message.event_key = payload.get("event").get("template_card_event").get("event_key")
        message.text = ""
        message.wxaibot_template_card_event = payload.get("event", {}).get("template_card_event")
        return message

    def _stream_create(self, message: Message, payload: dict):
        message.msg_type = MsgType.Stream.value
        message.stream_id = payload.get("stream").get("id")
        return message
