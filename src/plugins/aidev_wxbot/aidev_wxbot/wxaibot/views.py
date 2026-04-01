"""
Django REST Framework implementation for aidev_wxbot.
"""

import json
import threading
import time
import uuid
from logging import getLogger

from ag_ui.core.events import EventType
from aidev_agent.api.bk_aidev import BKAidevApi
from aidev_agent.services.config_manager import AgentConfigManager
from aidev_bkplugin.services.agent import build_execute_kwargs, run_chat_completion_with_thread_id
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from .context import ContextGenerator, LlmChunkMsg, stream_msg,CHUNK_FLUSH_THRESHOLD,text_msg
from .decryption import WXBizJsonMsgCrypt
from .models import AgentSession
from .strategies import resolve_strategy
from ..api.bkaidev import BkAiDevApi
from ..context.message import MsgType
from ..utils.rabbitmq import rabbitmq_client

logger = getLogger(__name__)


class WxAiBotViewSet(ViewSet):
    """微信AI机器人的DRF ViewSet"""

    # 微信回调接口不需要DRF认证，使用微信自己的签名验证
    authentication_classes = []
    permission_classes = []

    @property
    def wxbot_config(self):
        if settings.WXAIBOT_TOKEN and settings.WXAIBOT_ENCODING_AES_KEY:
            return {
                "rtx_token": settings.WXAIBOT_TOKEN,
                "rtx_encoding_aes_key": settings.WXAIBOT_ENCODING_AES_KEY,
                "contact": "智能体管理员",
            }

        # 从AI开发平台获取配置
        configs = [item for item in BkAiDevApi().retrieve_agent_channel_configs("rtx") if item["channel_type"] == "rtx"]
        if not configs:
            raise Exception("请先在AI开发平台配置企业智能机器人渠道")
        config = configs[0]["config"] or {}
        if not config.get("contact"):
            config["contact"] = "智能体管理员"
        return config

    def _reply_wxaibot(self, payload: dict) -> dict:
        """处理微信AI机器人的回复逻辑"""
        msg_type = payload["msgtype"]
        if msg_type == "text":
            return_msg = self._reply_text(payload)
        elif msg_type == "event":
            return_msg = self._reply_event(payload)
        elif msg_type == "stream":
            stream_id = payload["stream"]["id"]
            return_msg = self._reply_stream(stream_id)
        else:
            return_msg = {
                "msgtype": "stream",
                "stream": {
                    "id": f"stream_queue_{uuid.uuid4().hex}",
                    "finish": True,
                    "content": "您输入的内容我无法识别呢~",
                },
            }
        return return_msg

    @staticmethod
    def _reply_stream(stream_id: str) -> dict:
        """处理流式响应"""
        try:
            # 从队列中取出单个元素
            llm_chunk = LlmChunkMsg(stream_id=stream_id)
            return_msg = llm_chunk.wxaibot_msg_json_from_cache(rabbitmq_client)
            if llm_chunk.is_finish:
                logger.info(f"stream_id:{stream_id} 流式响应结束")
            return return_msg
        except Exception as e:
            logger.exception(f"stream_id:{stream_id} 获取流式响应失败: {e}")
            return stream_msg("回答失败！", True, stream_id)

    def _reply_event(self, payload: dict) -> dict:
        """处理事件消息"""
        try:
            context = ContextGenerator(payload).generate()
            if context.message.event == MsgType.EnterChat.value:
                agent_config = AgentConfigManager.get_config(settings.BKPAAS_APP_CODE, BKAidevApi.get_client())
                if agent_config.opening_mark:
                    return text_msg(agent_config.opening_mark)
        except Exception as e:
            logger.exception(f"处理事件消息失败: {e}")
        return stream_msg("", True, uuid.uuid4().hex)

    def _get_or_create_thread_id(self, group_id: str) -> str:
        """
        获取或创建thread_id

        Args:
            group_id: 群组ID

        Returns:
            str: thread_id
        """
        try:
            # 尝试获取现有会话
            agent_session = AgentSession.objects.get(group_id=group_id)

            # 检查会话是否有效（30分钟内）
            if agent_session.is_session_valid(timeout_minutes=30):
                logger.info(f"group_id:{group_id} 使用现有会话 thread_id:{agent_session.thread_id}")
                # 更新最后会话时间
                agent_session.update_session()
                return agent_session.thread_id
            else:
                # 会话已过期，生成新的thread_id
                new_thread_id = f"{group_id}_{int(time.time())}"
                agent_session.update_session(thread_id=new_thread_id)
                logger.info(f"group_id:{group_id} 会话已过期，生成新的 thread_id:{new_thread_id}")
                return new_thread_id

        except AgentSession.DoesNotExist:
            # 创建新会话
            new_thread_id = f"{group_id}_{int(time.time())}"
            AgentSession.objects.create(group_id=group_id, thread_id=new_thread_id, last_session_time=timezone.now())
            logger.info(f"group_id:{group_id} 创建新会话 thread_id:{new_thread_id}")
            return new_thread_id

    def _reply_text(self, payload: dict) -> dict:
        """处理文本消息，启动异步 AI 请求线程并立即返回流式占位响应。"""
        content = payload["text"]["content"]
        rtx_name = settings.WAXIBOT_NAME
        if content.startswith(f"@{rtx_name}"):
            content = content[len(f"@{rtx_name}") :].strip()
        current_context = ContextGenerator(payload).generate()
        stream_id = current_context.msg_id + "_" + str(int(time.time()))
        if content.strip() in ["会话", "新会话"]:
            return self._new_conversation(current_context.group_id, stream_id)

        quote_content = payload.get("quote", {}).get("text", {}).get("content", None)
        if quote_content:
            content = self._build_quoted_input(quote_content, content)

        logger.info(
            f"[WxAiBot] _reply_text: sender={current_context.sender_id}, "
            f"group={current_context.group_id}, content_len={len(content)}"
        )

        thread = threading.Thread(
            target=self._process_ai_request_async,
            args=(content, stream_id, current_context.sender_id, current_context.group_id),
            daemon=True,
        )
        thread.start()

        return stream_msg("正在思考中...", False, stream_id)

    @staticmethod
    def _build_quoted_input(quote_content: str, user_content: str) -> str:
        """将引用内容与用户输入合并，去除 think 标签后作为上下文前缀。"""
        if quote_content.startswith("<think>\n") and "\n</think>\n\n" in quote_content:
            quote_content = quote_content.split("\n</think>\n\n", 1)[-1]
        return f"引用内容：「{quote_content}」\n\n{user_content}"

    def _new_conversation(self, group_id: str, stream_id: str) -> dict:
        """
        创建新会话

        Args:
            group_id: 群组ID
            stream_id: 流式响应ID

        Returns:
            dict: 返回消息
        """
        # 生成新的thread_id
        new_thread_id = f"{group_id}_{int(time.time())}"

        try:
            # 尝试获取现有会话并更新
            agent_session = AgentSession.objects.get(group_id=group_id)
            agent_session.update_session(thread_id=new_thread_id)
            logger.info(f"group_id:{group_id} 更新会话 thread_id:{new_thread_id}")
        except AgentSession.DoesNotExist:
            # 创建新会话
            AgentSession.objects.create(group_id=group_id, thread_id=new_thread_id, last_session_time=timezone.now())
            logger.info(f"group_id:{group_id} 创建新会话 thread_id:{new_thread_id}")

        return stream_msg("已创建新会话，请输入咨询内容", True, stream_id)

    def _process_ai_request_async(self, content: str, stream_id: str, username: str, group_id: str):
        """异步处理 AI 请求：根据 agent_type 选择策略，执行并桥接到 RabbitMQ。

        使用策略模式将 Chat Agent / Flow Agent 的处理逻辑解耦，
        views 层只负责会话管理和线程调度，不关心具体 Agent 实现。
        """
        try:
            thread_id = self._get_or_create_thread_id(group_id)
            strategy = resolve_strategy(username)
            strategy.execute(
                content=content,
                stream_id=stream_id,
                username=username,
                thread_id=thread_id,
                group_id=group_id,
                rabbitmq_client=rabbitmq_client,
            )
        except Exception as e:
            logger.exception(f"stream_id:{stream_id} 异步处理AI请求失败: {e}")
            try:
                LlmChunkMsg(
                    content=f"请求处理失败: {str(e)}",
                    is_finish=True,
                    stream_id=stream_id,
                ).append_to_cache(rabbitmq_client)
            except Exception as cache_e:
                logger.error(f"stream_id:{stream_id} 写入错误信息到缓存失败: {cache_e}")

    @action(detail=False, methods=["get", "post"], url_path="callback")
    def callback(self, request: Request) -> HttpResponse:
        """处理微信回调请求（GET用于URL验证，POST用于消息回调）"""
        if request.method == "GET":
            return self._verify_url(request)
        elif request.method == "POST":
            return self._message_callback(request)

    def _verify_url(self, request: Request) -> HttpResponse:
        """处理 GET 请求（验证 URL）"""
        crypt = WXBizJsonMsgCrypt(self.wxbot_config["rtx_token"], self.wxbot_config["rtx_encoding_aes_key"], "")
        msg_signature = request.GET.get("msg_signature")
        timestamp = request.GET.get("timestamp")
        nonce = request.GET.get("nonce")
        echostr = request.GET.get("echostr")

        ret, echostr = crypt.VerifyURL(msg_signature, timestamp, nonce, echostr)
        logger.info(echostr)
        if ret != 0:
            logger.error("URL 验证失败")
            return Response({"error": "验证失败"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return HttpResponse(echostr)

    def _message_callback(self, request: Request) -> HttpResponse:
        """处理 POST 请求（消息回调）"""
        crypt = WXBizJsonMsgCrypt(self.wxbot_config["rtx_token"], self.wxbot_config["rtx_encoding_aes_key"], "")
        msg_signature = request.GET.get("msg_signature")
        timestamp = request.GET.get("timestamp")
        nonce = request.GET.get("nonce")

        post_data = json.loads(request.body.decode("utf-8"))
        logger.info(f"请求消息回调 {post_data}, msg_signature={msg_signature}, timestamp={timestamp}, nonce={nonce}")
        ret, decrypt_post_json_data = crypt.DecryptMsg(post_data, msg_signature, timestamp, nonce)
        if ret != 0:
            logger.error("消息内容解密失败")
            return Response({"error": "解密失败"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        post_json = json.loads(decrypt_post_json_data)
        logger.info(f"企微发送的消息\n=============\n{post_json}")
        return_msg = self._reply_wxaibot(post_json)
        ret, wxbot_encrypt_msg = crypt.EncryptMsg(json.dumps(return_msg, ensure_ascii=False), nonce, timestamp)
        logger.info(f"返回的消息\n=============\n{return_msg}")
        return HttpResponse(content=wxbot_encrypt_msg, content_type="text/plain")
