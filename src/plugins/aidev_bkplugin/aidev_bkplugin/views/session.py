# -*- coding: utf-8 -*-

from aidev_agent.enums import ChannelType
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.messages_handler.constants import TimeoutConfig
from aidev_agent.services.messages_handler.factory import message_handler_factory
from blueapps.core.exceptions import ClientBlueException
from rest_framework.decorators import action
from rest_framework.parsers import FileUploadParser
from rest_framework.views import Response

from aidev_bkplugin.constants import AGUI_PROTOCOL_VERSION, DEFAULT_SESSION_PAGE, DEFAULT_SESSION_PAGE_SIZE
from aidev_bkplugin.services.agent_config import AgentConfigFetcher
from aidev_bkplugin.utils import is_local_dev
from aidev_bkplugin.views.base import PluginResourceManager, PluginViewSet, client, logger


def _parse_positive_int(value, default):
    """将分页参数解析为正整数，缺失或非法（非数字、小于 1）时回退默认值"""
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 1 else default


class ChatSessionViewSet(PluginViewSet):
    session_type: str = "dev" if is_local_dev() else "agent"

    @property
    def channel_type(self):
        """会话创建/查询入口的默认渠道"""
        return ChannelType.POPUP.value

    def list(self, request):
        params = {
            "session_type": self.session_type,
            "protocol_version": AGUI_PROTOCOL_VERSION,
        }
        page = request.query_params.get("page")
        page_size = request.query_params.get("page_size")
        # 兼容旧前端：仅当显式传入 page 或 page_size 时启用分页，否则保持数组返回
        has_pagination = page is not None or page_size is not None
        if has_pagination:
            params["page"] = _parse_positive_int(page, DEFAULT_SESSION_PAGE)
            params["page_size"] = _parse_positive_int(page_size, DEFAULT_SESSION_PAGE_SIZE)
        result = client.api.list_chat_session(headers={"X-BKAIDEV-USER": request.user.username}, params=params)
        data = result["data"]
        if not isinstance(data, dict):
            # 旧后端未分页（返回数组）：在 Agent 侧过滤协议版本
            data = [each for each in data if each.get("protocol_version") == AGUI_PROTOCOL_VERSION]
        return Response(data=data)

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = client.api.batch_delete_chat_session(json=request.data)
        return Response(data=result["data"])

    def create(self, request):
        data = {
            "channel_type": self.channel_type,
            **request.data,
            "protocol_version": AGUI_PROTOCOL_VERSION,
            "session_type": self.session_type,
        }
        result = client.api.create_chat_session(json=data, headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        result = client.api.update_chat_session(path_params={"session_code": pk}, json=request.data)
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        result = client.api.retrieve_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    @action(["POST"], url_path="ai_rename", detail=True)
    def ai_rename(self, request, pk, **kwargs):
        result = client.api.rename_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    @action(["GET"], url_path="is_resume", detail=True)
    def is_resume(self, request, pk, **kwargs):
        logger.info(f"[is_resume][agent] 收到轮询请求, pk={pk}, kwargs={kwargs}, request_path={request.path}")
        result = client.api.is_resume_session(path_params={"session_code": pk})
        # is_resume_session 返回 True/False（收到回调即为 True）
        data = result.get("data", False)
        is_resume = bool(data) if isinstance(data, (bool, int)) else False
        return Response(data=is_resume)

    @action(
        ["POST"],
        url_path="upload/(?P<file_name>.+)",
        detail=True,
        parser_classes=[FileUploadParser],
    )
    def upload(self, request, pk, file_name, **kwargs):
        if not request.data.get("file", None):
            raise ClientBlueException(message="file is required")
        _data = dict(
            path_params={"session_code": pk, "file_name": file_name},
            data=request.data.get("file", None).read(),
            keep_data=True,
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": f'attachment; filename="{file_name}"',
            },
        )
        logger.info(f"upload_chat_session_file data: {_data}")
        result = client.api.upload_chat_session_file(
            **_data,
        )
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        result = client.api.destroy_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])


class ChatSessionContentViewSet(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = client.api.create_chat_session_content(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])

    @action(["GET"], url_path="content", detail=False)
    def content(self, request, **kwargs):
        result = client.api.get_chat_session_contents(params=request.query_params)
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        result = client.api.destroy_chat_session_content(path_params={"id": pk})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        result = client.api.update_chat_session_content(path_params={"id": pk}, json=request.data)
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = client.api.batch_delete_chat_session_content(json=request.data)
        return Response(data=result["data"])

    @action(["POST"], url_path="stop", detail=False)
    def stop(self, request):
        username = request.user.username
        session_code = request.data.get("session_code", "")

        # 获取 message_handler 用于清理
        message_handler = message_handler_factory.get()

        # 停止 agent 侧的流式生产者
        if session_code:
            # 1. 发送取消信号（进程内 + 跨进程）
            GeneratorStreamingHelper.cancel(session_code)

            # 2. 等待 SSE 消费者真正退出（收到 CANCELLED_CHUNK 并完成 mark_stopped）
            #    正常情况下几百毫秒内完成，超时则降级为当前行为
            stream_finished = False
            if hasattr(message_handler, "wait_for_consumer_cancelled"):
                try:
                    stream_finished = message_handler.wait_for_consumer_cancelled(
                        session_code,
                        timeout=TimeoutConfig.STOP_WAIT_STREAM_FINISH_TIMEOUT,
                    )
                    if stream_finished:
                        logger.info(f"Stream finished confirmed for session_code={session_code}")
                    else:
                        logger.warning(
                            f"Timeout waiting for stream to finish for session_code={session_code}, "
                            f"proceeding with stop anyway"
                        )
                except Exception as e:
                    logger.exception(f"Error waiting for stream finish: {e}")

            # 3. 如果等待超时（消费者可能已崩溃），兜底标记 stopped
            if not stream_finished and hasattr(message_handler, "mark_stopped"):
                message_handler.mark_stopped(session_code)

            # 4. 清理 cancelled 信号（避免残留）
            if hasattr(message_handler, "clear_cancelled_signal"):
                try:
                    message_handler.clear_cancelled_signal(session_code)
                except Exception as e:
                    logger.exception(f"Error clearing cancelled signal: {e}")

        # 5. 如果是 flow 类型智能体，额外调用 flow agent stop 接口撤销 bkflow 任务（不可恢复）
        #    用户点击「停止」→ revoke（任务变为 REVOKED/FAILED），不可恢复
        if session_code:
            try:
                agent_info = AgentConfigFetcher.get_info(username=username)
                if agent_info.get("agent_type") == "flow":
                    logger.info(f"Flow agent detected, revoking flow task for session_code={session_code}")
                    rm = PluginResourceManager(username=username)
                    revoke_result = rm.stop_flow_agent_task(session_code=session_code)
                    logger.info(f"[FLOW_AGENT] revoke 调用成功: session_code={session_code}, result={revoke_result}")
                    # revoke 后更新 session 中的 flow_agent_status 为 failed
                    try:
                        client.api.update_chat_session(
                            path_params={"session_code": session_code},
                            json={"flow_agent_status": "failed"},
                            headers={"X-BKAIDEV-USER": username},
                        )
                    except Exception as e:
                        logger.exception(
                            f"Error updating flow_agent_status after revoke: session_code={session_code}, error={e}"
                        )
            except Exception as e:
                logger.exception(f"Error revoking flow agent task: session_code={session_code}, error={e}")

        result = client.api.stop_chat_session_content(json=request.data, headers={"X-BKAIDEV-USER": username})

        return Response(data=result["data"])


class ChatSessionContentFeedbackViewSet(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = client.api.create_feedback(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])

    @action(["GET"], url_path="reasons", detail=False)
    def reasons(self, request, **kwargs):
        result = client.api.get_feedback_reasons(params=request.query_params)
        return Response(data=result["data"])


class ChatSessionShareView(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = client.api.share_chat_session(
            json=request.data,
            headers={"X-BKAIDEV-USER": username},
        )
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        result = client.api.get_shared_chat(
            path_params={"share_token": pk},
        )
        return Response(data=result["data"])
