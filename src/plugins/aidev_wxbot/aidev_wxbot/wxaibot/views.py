"""
Django REST Framework implementation for aidev_wxbot.
"""

import json
import time
import uuid
from dataclasses import dataclass
from logging import getLogger

from aidev_agent.packages.resource_manager import resource_manager
from aidev_agent.services.messages_handler import ConsumerPreemptedError
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from .channel_config import find_rtx_channel, get_channel_config
from .constants import (
    EMPTY_INPUT_PROMPT,
    GROUP_CHAT_TYPE,
    HELP_CMDS,
    HELP_REPLY,
    NEW_CONVERSATION_CMDS,
    STOP_CMDS,
    STOP_NO_ACTIVE_REPLY,
    WRONG_MENTION_PROMPT,
)
from .context import ContextGenerator, LlmChunkMsg, WxWorkAiBotContext, stream_msg, text_msg
from .decryption import WXBizJsonMsgCrypt
from .execution import get_agent_executor
from .models import AgentSession
from .strategies import resolve_strategy
from ..api.bkaidev import BkAiDevApi
from ..context.message import MsgType
from ..utils.rabbitmq import rabbitmq_client

logger = getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WxBotAgentRequest:
    """已完成企微消息校验、可交给 Agent 的请求。"""

    content: str
    stream_id: str
    username: str
    group_id: str


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

        channel = find_rtx_channel(BkAiDevApi().retrieve_agent_channel_configs("rtx"))
        if not channel:
            raise Exception("请先在AI开发平台配置企业智能机器人渠道")
        config = get_channel_config(channel)
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
                agent_config = resource_manager().get_agent_config(settings.BKPAAS_APP_CODE)
                if agent_config.opening_mark:
                    return text_msg(agent_config.opening_mark)
        except Exception as e:
            logger.exception(f"处理事件消息失败: {e}")
        return stream_msg("", True, uuid.uuid4().hex)

    def _session_scope(self, group_id: str, username: str) -> str:
        """会话轮换的作用域键，即 ``AgentSession`` 这张表的主键。

        回调按群共享一个 thread_id；长连接覆写为按人，见其子类说明。
        """
        return group_id

    def _get_or_create_thread_id(self, scope: str) -> str:
        """
        获取或创建thread_id

        Args:
            scope: 会话作用域键，由 ``_session_scope`` 给出

        Returns:
            str: thread_id
        """
        try:
            # 尝试获取现有会话
            agent_session = AgentSession.objects.get(group_id=scope)

            # 检查会话是否有效（30分钟内）
            if agent_session.is_session_valid(timeout_minutes=30):
                # 每条消息都会命中，放 INFO 没有信息量
                logger.debug(f"scope:{scope} 使用现有会话 thread_id:{agent_session.thread_id}")
                # 更新最后会话时间
                agent_session.update_session()
                return agent_session.thread_id
            else:
                # 会话已过期，生成新的thread_id
                new_thread_id = f"{scope}_{int(time.time())}"
                agent_session.update_session(thread_id=new_thread_id)
                logger.info(f"scope:{scope} 会话已过期，生成新的 thread_id:{new_thread_id}")
                return new_thread_id

        except AgentSession.DoesNotExist:
            # 创建新会话
            new_thread_id = f"{scope}_{int(time.time())}"
            AgentSession.objects.create(group_id=scope, thread_id=new_thread_id, last_session_time=timezone.now())
            logger.info(f"scope:{scope} 创建新会话 thread_id:{new_thread_id}")
            return new_thread_id

    def _reply_text(self, payload: dict) -> dict:
        """
        处理文本消息，启动异步 AI 请求线程并立即返回流式占位响应。
        """
        response, request = self.prepare_agent_request(payload)
        if response is not None:
            return response
        if request is None:
            return stream_msg("服务暂时不可用", True, "")
        if not self._start_async_processing(request.content, request.stream_id, request):
            return stream_msg("当前请求较多，请稍后重试", True, request.stream_id)
        return stream_msg("正在思考中...", False, request.stream_id)

    def prepare_agent_request(self, payload: dict) -> tuple[dict | None, WxBotAgentRequest | None]:
        """解析企微文本消息，但不启动 Agent；长连接与 callback 共用。"""
        stream_id = ""
        try:
            # 提取并验证必要字段
            text_data = payload.get("text", {})
            content = text_data.get("content", "")
            chat_type = payload.get("chattype", "single")
            # 生成上下文和 stream_id
            current_context = ContextGenerator(payload).generate()
            stream_id = f"{current_context.msg_id}_{int(time.time())}"
            logger.debug(
                f"[WxAiBot] 收到消息 | chat_type={chat_type}, sender={current_context.sender_id}, stream_id={stream_id}"
            )
            # 根据聊天类型分发处理，获取处理后的内容或立即返回的响应
            if chat_type == GROUP_CHAT_TYPE:
                result, content = self._handle_group_chat(content, stream_id, current_context)
            else:
                result, content = self._handle_single_chat(content, stream_id, current_context)
            # 如果需要立即返回（如提示信息）
            if result is not None:
                return result, None
            # 处理引用消息
            content = self._process_quote(payload, content)
            return None, WxBotAgentRequest(
                content=content,
                stream_id=stream_id,
                username=current_context.sender_id,
                group_id=current_context.group_id,
            )

        except (KeyError, AttributeError) as e:
            logger.error(f"[WxAiBot] 消息格式错误: {e}")
            return stream_msg("消息格式错误", True, stream_id), None
        except Exception as e:
            logger.exception(f"[WxAiBot] 处理异常: {e}")
            return stream_msg("服务暂时不可用", True, stream_id), None

    def _handle_single_chat(self, content: str, stream_id: str, context: WxWorkAiBotContext) -> tuple[dict | None, str]:
        """
        处理单聊场景。
        """
        stripped = content.strip()
        if not stripped:
            return stream_msg(EMPTY_INPUT_PROMPT, True, stream_id), ""
        if command := self._resolve_builtin_command(stripped, stream_id, context):
            return command, ""
        return None, content

    def _handle_group_chat(self, content: str, stream_id: str, context: WxWorkAiBotContext) -> tuple[dict | None, str]:
        """
        处理群聊场景。必须@本机器人才会响应。
        """
        rtx_name = getattr(settings, "WAXIBOT_NAME", "")
        if not content.startswith("@"):
            return stream_msg("", True, stream_id), ""
        # 精确匹配@本机器人
        if rtx_name and content.startswith(f"@{rtx_name}"):
            return self._process_mention(content, len(f"@{rtx_name}"), stream_id, context)
        # 配置了机器人名但@的是其他人
        if rtx_name:
            return stream_msg(WRONG_MENTION_PROMPT, True, stream_id), ""
        # 未配置机器人名，智能解析
        return self._process_mention_fallback(content, stream_id, context)

    def _process_mention(
        self, content: str, prefix_len: int, stream_id: str, context: WxWorkAiBotContext
    ) -> tuple[dict | None, str]:
        """
        处理@机器人的内容提取。
        """
        user_input = content[prefix_len:].strip()
        if not user_input:
            return stream_msg(EMPTY_INPUT_PROMPT, True, stream_id), ""
        if command := self._resolve_builtin_command(user_input, stream_id, context):
            return command, ""
        return None, user_input

    def _process_mention_fallback(
        self, content: str, stream_id: str, context: WxWorkAiBotContext
    ) -> tuple[dict | None, str]:
        """
        兜底处理：未配置 WAXIBOT_NAME 时，智能解析@内容。
        """
        # 去掉@，按第一个空格分割
        at_content = content[1:]
        parts = at_content.split(" ", 1)
        if len(parts) < 2:
            # 只有@机器人名，没有用户输入
            return stream_msg(EMPTY_INPUT_PROMPT, True, stream_id), ""
        user_input = parts[1].strip()
        if not user_input:
            return stream_msg(EMPTY_INPUT_PROMPT, True, stream_id), ""
        if command := self._resolve_builtin_command(user_input, stream_id, context):
            return command, ""
        return None, user_input

    def _resolve_builtin_command(self, user_input: str, stream_id: str, context: WxWorkAiBotContext) -> dict | None:
        """命中内置命令则返回终态响应，否则返回 None 交给 Agent。

        单聊、@机器人、未配置机器人名的兜底解析三条路径共用本入口，避免命令集
        在某一条路径上漏掉。
        """
        if user_input in NEW_CONVERSATION_CMDS:
            return self._new_conversation(context.group_id, context.sender_id, stream_id)
        if user_input in HELP_CMDS:
            return stream_msg(HELP_REPLY, True, stream_id)
        if user_input in STOP_CMDS:
            return self.stop_generation(context.group_id, context.sender_id, stream_id)
        return None

    def stop_generation(self, group_id: str, username: str, stream_id: str) -> dict:
        """中止该发起人正在生成的回复。

        HTTP 回调没有进程内的活跃流登记（企微靠轮询取结果，进程间也不共享状态），
        因此基类只能如实回复「没有正在生成的回复」；长连接服务覆写本方法接上登记簿。
        """
        return stream_msg(STOP_NO_ACTIVE_REPLY, True, stream_id)

    def _process_quote(self, payload: dict, content: str) -> str:
        """
        处理引用消息，将引用内容与用户输入合并。

        Args:
            payload: 消息 payload
            content: 当前用户输入内容

        Returns:
            合并后的内容
        """
        quote_data = payload.get("quote", {}).get("text", {})
        quote_content = quote_data.get("content")

        if not quote_content:
            return content

        merged = self._build_quoted_input(quote_content, content)
        logger.debug(f"[WxAiBot] 合并引用消息 | original_len={len(content)}, merged_len={len(merged)}")
        return merged

    def _start_async_processing(
        self,
        content: str,
        stream_id: str,
        context: WxWorkAiBotContext | WxBotAgentRequest,
    ) -> bool:
        """
        启动异步线程处理 AI 请求。

        Args:
            content: 处理后的用户输入
            stream_id: 流式响应 ID
            context: 消息上下文
        """
        username = context.username if isinstance(context, WxBotAgentRequest) else context.sender_id
        logger.debug(f"[WxAiBot] 启动异步处理 | stream_id={stream_id}, content_len={len(content)}, sender={username}")

        submitted = get_agent_executor().submit(
            self._process_ai_request_async,
            content,
            stream_id,
            username,
            context.group_id,
        )
        if not submitted:
            logger.warning(
                "event=wxbot_agent_overload stream_id=%s sender=%s group_id=%s",
                stream_id,
                username,
                context.group_id,
            )
        return submitted

    @staticmethod
    def _build_quoted_input(quote_content: str, user_content: str) -> str:
        """将引用内容与用户输入合并，去除 think 标签后作为上下文前缀。"""
        if quote_content.startswith("<think>\n") and "\n</think>\n\n" in quote_content:
            quote_content = quote_content.split("\n</think>\n\n", 1)[-1]
        return f"引用内容：「{quote_content}」\n\n{user_content}"

    def _new_conversation(self, group_id: str, username: str, stream_id: str) -> dict:
        """
        创建新会话

        Args:
            group_id: 群组ID
            username: 发起人
            stream_id: 流式响应ID

        Returns:
            dict: 返回消息
        """
        scope = self._session_scope(group_id, username)
        # 生成新的thread_id
        new_thread_id = f"{scope}_{int(time.time())}"

        try:
            # 尝试获取现有会话并更新
            agent_session = AgentSession.objects.get(group_id=scope)
            agent_session.update_session(thread_id=new_thread_id)
            logger.info(f"scope:{scope} 更新会话 thread_id:{new_thread_id}")
        except AgentSession.DoesNotExist:
            # 创建新会话
            AgentSession.objects.create(group_id=scope, thread_id=new_thread_id, last_session_time=timezone.now())
            logger.info(f"scope:{scope} 创建新会话 thread_id:{new_thread_id}")

        return stream_msg("已创建新会话，请输入咨询内容", True, stream_id)

    def _process_ai_request_async(self, content: str, stream_id: str, username: str, group_id: str):
        """异步处理 AI 请求：根据 agent_type 选择策略，执行并桥接到 RabbitMQ。

        使用策略模式将 Chat Agent / Flow Agent 的处理逻辑解耦，
        views 层只负责会话管理和线程调度，不关心具体 Agent 实现。
        """
        try:
            logger.debug(f"[WxAiBot] 发送至Agent | stream_id:{stream_id}, content_len={len(content)}")
            thread_id = self._get_or_create_thread_id(self._session_scope(group_id, username))
            strategy = resolve_strategy(username)
            strategy.execute(
                content=content,
                stream_id=stream_id,
                username=username,
                thread_id=thread_id,
                group_id=group_id,
                rabbitmq_client=rabbitmq_client,
            )
        except ConsumerPreemptedError:
            logger.info("event=wxbot_stream_preempted stream_id=%s group_id=%s", stream_id, group_id)
            try:
                LlmChunkMsg(
                    content="当前会话已有新请求，原请求已结束",
                    is_finish=True,
                    stream_id=stream_id,
                ).append_to_cache(rabbitmq_client)
            except Exception as cache_e:
                logger.error(f"stream_id:{stream_id} 写入抢占终态失败: {cache_e}")
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
