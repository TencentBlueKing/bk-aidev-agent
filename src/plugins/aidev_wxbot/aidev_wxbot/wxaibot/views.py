"""
Django REST Framework implementation for aidev_wxbot.
"""

import json
import threading
import time
import uuid
from logging import getLogger

import requests
from django.conf import settings
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from .context import ContextGenerator, LlmChunkMsg, stream_msg
from .decryption import WXBizJsonMsgCrypt
from ..api.bkaidev import BkAiDevApi
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
            return {"rtx_token": settings.WXAIBOT_TOKEN, "rtx_encoding_aes_key": settings.WXAIBOT_ENCODING_AES_KEY}
        else:
            configs = [
                item for item in BkAiDevApi().retrieve_agent_channel_configs("rtx") if item["channel_type"] == "rtx"
            ]
            if not configs:
                raise Exception("请先在AI开发平台配置企业智能机器人渠道")
            return configs[0]["config"]

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
        return stream_msg("", True, uuid.uuid4().hex)

    def _reply_text(self, payload: dict) -> dict:
        """处理文本消息"""
        content = payload["text"]["content"]
        rtx_name = settings.WAXIBOT_NAME
        if content.startswith(f"@{rtx_name}"):
            content = content[len(f"@{rtx_name}") :].strip()

        current_context = ContextGenerator(payload).generate()
        agent_apigw_name = settings.BKPAAS_BK_PLUGIN_APIGW_NAME
        # 生成流式响应ID
        stream_id = current_context.msg_id + "_" + str(int(time.time()))

        logger.info(f"reply_text: current_context=>{current_context}")

        # 启动后台线程处理实际的AI请求
        thread = threading.Thread(
            target=self._process_ai_request_async,
            args=(content, stream_id, agent_apigw_name, current_context.sender_id),
            daemon=True,
        )
        thread.start()

        # 立即返回"正在思考中...."的消息
        return stream_msg("正在思考中...", False, stream_id)

    def _process_ai_request_async(self, content: str, stream_id: str, agent_apigw_name: str, username: str):
        """异步处理AI请求的后台方法"""
        try:
            start_time = time.time()
            first_response_time = None
            chat_root = (
                settings.BK_API_URL_TMPL.format(api_name=agent_apigw_name)
                + "/"
                + "prod"
                + "/bk_plugin/openapi/agent/chat_completion/"
            )
            response = requests.post(
                chat_root,
                headers={
                    "Content-Type": "application/json",
                    "X-Bkapi-Authorization": json.dumps(
                        {"bk_app_code": settings.BKPAAS_APP_CODE, "bk_app_secret": settings.BKPAAS_APP_SECRET}
                    ),
                    "X-BKAIDEV-USER": username,
                },
                json={
                    "input": content,
                    "execute_kwargs": {"stream": True},
                },
                stream=True,
            )

            docs = []
            buffer = ""  # 用于缓存不完整的数据
            if response.status_code != 200:
                llm_chunk = LlmChunkMsg(
                    content=f"请求出错\n{response.text}\n请联系管理员查看！", is_finish=True, stream_id=stream_id
                )
                llm_chunk.append_to_cache(rabbitmq_client)
                return
            llm_chunk = LlmChunkMsg(content="", is_finish=False, stream_id=stream_id)
            added_content = ""
            think_content = ""
            for chunk in response.iter_content(chunk_size=1024):  # 设置合适的chunk大小
                if chunk:
                    try:
                        chunk_str = chunk.decode("utf-8")
                        buffer += chunk_str
                        lines = buffer.split("\n")
                        buffer = lines[-1]

                        for line in lines[:-1]:
                            line = line.strip()
                            if not line:
                                continue
                            if line == "data: [DONE]":
                                continue
                            if line.startswith("data: "):
                                data_content = line[6:]
                                if not data_content:
                                    continue
                                chunk_json = json.loads(data_content)
                                if first_response_time is None:
                                    first_response_time = time.time()
                                    elapsed_time = first_response_time - start_time
                                    logger.info(
                                        f"stream_id:{stream_id} 从请求开始到第一次收到流式响应耗时: {elapsed_time:.3f} 秒"
                                    )

                                event_type = chunk_json.get("event", "")
                                if event_type == "text":
                                    if chunk_json.get("content") == "正在思考...":
                                        continue
                                    added_content += chunk_json.get("content", "")
                                    if think_content:
                                        llm_chunk.think_content = llm_chunk.think_content + think_content
                                        llm_chunk.append_to_cache(rabbitmq_client)
                                        think_content = ""
                                    if len(added_content) > 50:
                                        llm_chunk.content = llm_chunk.content + added_content
                                        llm_chunk.append_to_cache(rabbitmq_client)
                                        added_content = ""
                                elif event_type == "reference_doc":
                                    documents = chunk_json.get("documents", [])
                                    for doc_info in documents:
                                        if "metadata" in doc_info:
                                            docs.append(doc_info["metadata"])
                                    continue
                                elif event_type == "think":
                                    if chunk_json.get("content") == "正在思考...":
                                        continue
                                    if not think_content:
                                        # 如果思考内容是空的，就先清空一次内容，解决显示问题。
                                        empty_llm_chunk = LlmChunkMsg(stream_id=stream_id)
                                        empty_llm_chunk.append_to_cache(rabbitmq_client)
                                    think_content += chunk_json.get("content", "")
                                    if len(think_content) > 50:
                                        llm_chunk.think_content = llm_chunk.think_content + think_content
                                        llm_chunk.append_to_cache(rabbitmq_client)
                                        think_content = ""
                                else:
                                    logger.info(f"stream_id:{stream_id} 未知的事件类型: {event_type}")
                    except Exception as e:
                        logger.error(f"stream_id:{stream_id} 处理 chunk 时发生错误: {e}")

                        # 发生错误时，写入错误信息到流中
                        error_chunk = LlmChunkMsg(
                            content=f"处理请求时发生错误: {str(e)}", is_finish=True, stream_id=stream_id
                        )
                        try:
                            error_chunk.append_to_cache(rabbitmq_client)
                        except Exception as cache_e:
                            logger.error(f"stream_id:{stream_id} 写入错误信息到缓存失败: {cache_e}")
                        return
            llm_chunk.content = llm_chunk.content + added_content
            llm_chunk.is_finish = True
            llm_chunk.docs = docs
            llm_chunk.append_to_cache(rabbitmq_client)

        except Exception as e:
            logger.exception(f"stream_id:{stream_id} 异步处理AI请求失败: {e}")

            # 发生异常时，写入错误信息到流中
            error_chunk = LlmChunkMsg(content=f"请求处理失败: {str(e)}", is_finish=True, stream_id=stream_id)
            try:
                error_chunk.append_to_cache(rabbitmq_client)
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
