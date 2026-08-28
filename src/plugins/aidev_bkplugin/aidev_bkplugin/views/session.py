# -*- coding: utf-8 -*-

from aidev_agent.enums import ChannelType
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.messages_handler.constants import TimeoutConfig
from aidev_agent.services.messages_handler.factory import message_handler_factory
from aidev_agent.services.sandbox_pv_files import (
    SandboxFileError,
    SandboxFileInvalidArgumentError,
    SandboxFileInvalidRequestError,
    SandboxFileNotFoundError,
    SandboxPvFileService,
)
from bkapi_client_core.exceptions import HTTPResponseError
from blueapps.core.exceptions import ClientBlueException
from django.conf import settings
from django.http import HttpResponse
from rest_framework.decorators import action
from rest_framework.parsers import FileUploadParser
from rest_framework.views import Response

from aidev_bkplugin.constants import AGUI_PROTOCOL_VERSION, DEFAULT_SESSION_PAGE, DEFAULT_SESSION_PAGE_SIZE
from aidev_bkplugin.services.agent_config import AgentConfigFetcher
from aidev_bkplugin.utils import is_local_dev
from aidev_bkplugin.views.base import PluginResourceManager, PluginViewSet, logger


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
            "channel_type": self.channel_type,
        }
        page = request.query_params.get("page")
        page_size = request.query_params.get("page_size")
        # 兼容旧前端：仅当显式传入 page 或 page_size 时启用分页，否则保持数组返回
        has_pagination = page is not None or page_size is not None
        if has_pagination:
            params["page"] = _parse_positive_int(page, DEFAULT_SESSION_PAGE)
            params["page_size"] = _parse_positive_int(page_size, DEFAULT_SESSION_PAGE_SIZE)
        result = self.client.api.list_chat_session(headers={"X-BKAIDEV-USER": request.user.username}, params=params)
        data = result["data"]
        if not isinstance(data, dict):
            # 旧后端未分页（返回数组）：在 Agent 侧过滤协议版本
            data = [each for each in data if each.get("protocol_version") == AGUI_PROTOCOL_VERSION]
        return Response(data=data)

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = self.client.api.batch_delete_chat_session(json=request.data)
        return Response(data=result["data"])

    def create(self, request):
        data = {
            "channel_type": self.channel_type,
            **request.data,
            "protocol_version": AGUI_PROTOCOL_VERSION,
            "session_type": self.session_type,
        }
        result = self.client.api.create_chat_session(json=data, headers={"X-BKAIDEV-USER": request.user.username})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        result = self.client.api.update_chat_session(path_params={"session_code": pk}, json=request.data)
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        result = self.client.api.retrieve_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    @action(["POST"], url_path="ai_rename", detail=True)
    def ai_rename(self, request, pk, **kwargs):
        result = self.client.api.rename_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    @action(["GET"], url_path="is_resume", detail=True)
    def is_resume(self, request, pk, **kwargs):
        logger.info(f"[is_resume][agent] 收到轮询请求, pk={pk}, kwargs={kwargs}, request_path={request.path}")
        result = self.client.api.is_resume_session(path_params={"session_code": pk})
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
        result = self.client.api.upload_chat_session_file(
            **_data,
        )
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        result = self.client.api.destroy_chat_session(path_params={"session_code": pk})
        return Response(data=result["data"])

    # ------------------------------------------------------------------
    # 会话沙箱 PV 文件（SDK 前端直连 PaaS 沙箱文件接口）
    # ------------------------------------------------------------------

    @staticmethod
    def _pv_exc_to_response(exc: SandboxFileError) -> Response:
        """沙箱文件异常 → HTTP 响应。"""
        if isinstance(exc, SandboxFileNotFoundError):
            status_code = 404
        elif isinstance(exc, (SandboxFileInvalidArgumentError, SandboxFileInvalidRequestError)):
            status_code = 400
        else:
            status_code = 500
        return Response(data={"message": str(exc)}, status=status_code)

    def _check_session_owner(self, request, session_code: str, require_access: bool = False) -> None:
        """校验 session 归属

        改为实例方法：归属校验须走 ``self.client`` 的用户态凭证，静态方法拿不到按请求构造的 client。
        :param require_access: 是否校验会话归属。默认 False
        """
        if not require_access:
            return
        username = request.user.username
        try:
            self.client.api.retrieve_chat_session(
                path_params={"session_code": session_code},
                headers={"X-BKAIDEV-USER": username},
            )
        except HTTPResponseError as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", 500)
            if status_code in (403, 404):
                raise ClientBlueException(
                    message=f"无权访问会话 {session_code} 或会话不存在",
                    code=str(status_code),
                )
            raise

    def _make_pv_file_service(self, request) -> SandboxPvFileService:
        # username 优先级：request.user.username(apigw请求+前端请求) → X-BKAIDEV-USER header 兜底
        username = request.user.username if hasattr(request, "user") else ""
        if not username:
            username = request.META.get("HTTP_X_BKAIDEV_USER", "")
        rm = PluginResourceManager(username=username)

        # 用户ticket获取优先级：
        # 1) cookie[BKAUTH_BACKEND_TYPE]：前端浏览器同域直调场景
        # 2) HTTP_AIDEV_TICKET header：cookie 缺失时的手动兜底
        # 3) access_token：apigw 场景，用 username 通过 bkoauth 换取
        ticket_key = getattr(settings, "BKAUTH_BACKEND_TYPE", "bk_ticket")
        bk_ticket = request.COOKIES.get(ticket_key, "") or request.META.get("HTTP_AIDEV_TICKET", "")
        executor_info = {
            "app_code": settings.BK_APP_CODE,
            "app_secret": settings.BK_APP_SECRET,
            "executor": username,
            "bk_ticket_key": ticket_key,
            "bk_ticket_value": bk_ticket,
        }
        if not bk_ticket:
            if username:
                access_token = rm.resolve_access_token(username)
                if access_token:
                    executor_info["access_token"] = access_token
                    logger.info(
                        "[pv_files] cookie ticket empty, fallback to access_token: user=%s, path=%s",
                        username,
                        request.path,
                    )
                else:
                    logger.warning(
                        "[pv_files] no valid user credential (ticket/access_token): "
                        "user=%s, path=%s; downstream PaaS will reject",
                        username,
                        request.path,
                    )
            else:
                logger.warning(
                    "[pv_files] no username (jwt user empty & no X-BKAIDEV-USER header): "
                    "path=%s; downstream PaaS will reject",
                    request.path,
                )

        return SandboxPvFileService(resource_manager=rm, executor_info=executor_info)

    @action(["GET"], url_path="pv_files", detail=True)
    def pv_files(self, request, pk, **kwargs):
        self._check_session_owner(request, pk, require_access=False)
        svc = self._make_pv_file_service(request)
        params = request.query_params
        try:
            data = svc.list_files(
                session_code=pk,
                path=params.get("path", ""),
                since=None,
                until=None,
            )
        except SandboxFileError as exc:
            return self._pv_exc_to_response(exc)
        return Response(data=data)

    @action(["GET"], url_path="pv_files/stat", detail=True)
    def pv_files_stat(self, request, pk, **kwargs):
        self._check_session_owner(request, pk, require_access=False)
        path = request.query_params.get("path", "")
        if not path:
            raise ClientBlueException(message="path is required")
        try:
            data = self._make_pv_file_service(request).stat_file(session_code=pk, path=path)
        except SandboxFileError as exc:
            return self._pv_exc_to_response(exc)
        return Response(data=data)

    @action(["GET"], url_path="pv_files/preview", detail=True)
    def pv_files_preview(self, request, pk, **kwargs):
        self._check_session_owner(request, pk, require_access=False)
        path = request.query_params.get("path", "")
        if not path:
            raise ClientBlueException(message="path is required")
        max_bytes = _parse_positive_int(request.query_params.get("max_bytes"), 65536)
        try:
            content, truncated = self._make_pv_file_service(request).preview_file(
                session_code=pk, path=path, max_bytes=max_bytes
            )
        except SandboxFileError as exc:
            return self._pv_exc_to_response(exc)
        response = HttpResponse(content, content_type="text/plain; charset=utf-8")
        response["X-Truncated"] = "true" if truncated else "false"
        return response

    @action(["GET"], url_path="pv_files/download_url", detail=True)
    def pv_files_download_url(self, request, pk, **kwargs):
        self._check_session_owner(request, pk, require_access=False)
        path = request.query_params.get("path", "")
        if not path:
            raise ClientBlueException(message="path is required")
        expires_in = _parse_positive_int(request.query_params.get("expires_in"), 600)
        try:
            data = self._make_pv_file_service(request).get_download_url(
                session_code=pk, path=path, expires_in=expires_in
            )
        except SandboxFileError as exc:
            return self._pv_exc_to_response(exc)
        return Response(data=data)


class ChatSessionContentViewSet(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = self.client.api.create_chat_session_content(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])

    @action(["GET"], url_path="content", detail=False)
    def content(self, request, **kwargs):
        result = self.client.api.get_chat_session_contents(params=request.query_params)
        return Response(data=result["data"])

    def destroy(self, request, pk, **kwargs):
        result = self.client.api.destroy_chat_session_content(path_params={"id": pk})
        return Response(data=result["data"])

    def update(self, request, pk, **kwargs):
        result = self.client.api.update_chat_session_content(path_params={"id": pk}, json=request.data)
        return Response(data=result["data"])

    @action(["POST"], url_path="batch_delete", detail=False)
    def batch_delete(self, request):
        result = self.client.api.batch_delete_chat_session_content(json=request.data)
        return Response(data=result["data"])

    @action(["POST"], url_path="stop", detail=False)
    def stop(self, request):
        username = request.user.username
        session_code = request.data.get("session_code", "")
        run_id = request.data.get("run_id") or None

        # 获取 message_handler 用于清理
        message_handler = message_handler_factory.get()
        producer_active = None

        # 停止 agent 侧的流式生产者
        if session_code:
            # 在发送 cancel 前记录 producer 状态；发送后 producer 可能立即退出，无法区分
            # “本次被停止”与“请求到达前已无 producer”两种场景。
            try:
                producer_active = bool(message_handler.has_active_producer(session_code))
            except Exception:
                logger.exception(f"Error checking active producer for session_code={session_code}")

            # 1. 先清理上一轮完成通知，避免误消费旧通知
            if hasattr(message_handler, "clear_cancelled_signal"):
                try:
                    message_handler.clear_cancelled_signal(session_code, run_id=run_id)
                except Exception as e:
                    logger.exception(f"Error clearing stale cancelled signal: {e}")

            # 2. 发送取消信号（进程内 + 跨进程）
            GeneratorStreamingHelper.cancel(session_code, message_handler=message_handler, run_id=run_id)

            # 3. 等待 SSE 消费者真正退出（收到取消终态与 EOD）
            #    正常情况下几百毫秒内完成，超时则降级为当前行为
            stream_finished = False
            if hasattr(message_handler, "wait_for_consumer_cancelled"):
                try:
                    stream_finished = message_handler.wait_for_consumer_cancelled(
                        session_code,
                        timeout=TimeoutConfig.STOP_WAIT_STREAM_FINISH_TIMEOUT,
                        run_id=run_id,
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

            # 4. 如果等待超时（如工具仍在执行），保留 stopped 标记；
            #    真正的取消完成通知仍由消费者在收到 EOD 后发送。
            if not stream_finished and hasattr(message_handler, "mark_stopped"):
                message_handler.mark_stopped(session_code)

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
                        self.client.api.update_chat_session(
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

        platform_payload = request.data.copy()
        platform_payload.pop("run_id", None)
        if producer_active is not None:
            platform_payload["producer_active"] = producer_active
        result = self.client.api.stop_chat_session_content(json=platform_payload, headers={"X-BKAIDEV-USER": username})

        return Response(data=result["data"])


class ChatSessionContentFeedbackViewSet(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = self.client.api.create_feedback(json=request.data, headers={"X-BKAIDEV-USER": username})
        return Response(data=result["data"])

    @action(["GET"], url_path="reasons", detail=False)
    def reasons(self, request, **kwargs):
        result = self.client.api.get_feedback_reasons(params=request.query_params)
        return Response(data=result["data"])


class ChatSessionShareView(PluginViewSet):
    def create(self, request):
        username = request.user.username
        result = self.client.api.share_chat_session(
            json=request.data,
            headers={"X-BKAIDEV-USER": username},
        )
        return Response(data=result["data"])

    def retrieve(self, request, pk, **kwargs):
        result = self.client.api.get_shared_chat(
            path_params={"share_token": pk},
        )
        return Response(data=result["data"])
