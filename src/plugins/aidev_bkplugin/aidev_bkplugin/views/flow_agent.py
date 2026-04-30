# -*- coding: utf-8 -*-

from logging import getLogger

from blueapps.core.exceptions import ClientBlueException
from django.http.response import StreamingHttpResponse
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.views import Response

from aidev_agent.config import settings as agent_settings
from aidev_agent.services.agent.flow import FlowAgentCompletionAgent
from aidev_bkplugin.services.agent import build_execute_kwargs
from aidev_bkplugin.views.base import IgnoreClientContentNegotiation, PluginViewSet, PluginResourceManager

logger = getLogger(__name__)


class FlowAgentViewSet(PluginViewSet):
    """Flow Agent 视图集

    提供八个接口：
    1. POST   /flow_agent/start/                              - 启动 Flow Agent 任务
    2. GET    /flow_agent/{task_id}/task_info/                 - 获取任务信息
    3. GET    /flow_agent/{task_id}/task_node_info/{node_id}/  - 获取任务节点信息
    4. POST   /flow_agent/stop/                               - 停止 Flow Agent 任务
    5. POST   /flow_agent/pause/                              - 暂停 Flow Agent 任务
    6. POST   /flow_agent/resume/                             - 恢复 Flow Agent 任务
    7. POST   /flow_agent/{session_code}/node/{node_id}/retry/ - 重试任务节点（返回 SSE 流）
    8. POST   /flow_agent/{session_code}/node/{node_id}/skip/  - 跳过任务节点（返回 SSE 流）

    接口 7/8 在节点操作成功后，会恢复 SSE 轮询流，前端可持续接收后续任务状态。
    """

    # 使用自定义内容协商，支持流式响应
    content_negotiation_class = IgnoreClientContentNegotiation

    @staticmethod
    def _handle_api_error(action_name: str, err: Exception) -> None:
        """统一的 API 异常处理：记录日志并抛出 ClientBlueException"""
        logger.exception("FlowAgentViewSet %s error: %s", action_name, err)
        message = getattr(err, "message", str(err))
        raise ClientBlueException(message=message)

    def _session_code_action(self, request: Request, action_name: str, client_method_name: str) -> Response:
        """stop / pause / resume 三个操作的通用执行逻辑

        Args:
            request: DRF 请求对象
            action_name: 操作名称，用于日志记录（如 "stop"、"pause"、"resume"）
            client_method_name: ResourceManagerBase 上要调用的方法名
                （如 "stop_flow_agent_task"、"pause_flow_agent_task"）
        """
        username = self.get_username()
        session_code = request.data.get("session_code", "")

        try:
            rm = PluginResourceManager(username=username)
            method = getattr(rm, client_method_name)
            result = method(session_code=session_code)
            return Response(data=result)
        except Exception as err:
            self._handle_api_error(action_name, err)

    @action(detail=False, methods=["POST"], url_path="start")
    def start(self, request: Request):
        """启动 Flow Agent 任务

        POST /flow_agent/start/

        请求体：
        {
            "session_code": "xxx",         // 可选，会话标识
            "context": [...],              // 可选，上下文信息
            "execute_kwargs": {            // 可选，执行参数
                "executor": "user123",
                "timeout": 300
            }
        }

        响应：
        {
            "task_id": 789012
        }
        """
        username = self.get_username()
        session_code = request.data.get("session_code", "")
        context = request.data.get("context", [])
        execute_kwargs_data = request.data.get("execute_kwargs", {})

        try:
            flow_start_params = {
                "session_code": session_code,
            }
            if context:
                flow_start_params["context"] = context
            if execute_kwargs_data:
                execute_kwargs = build_execute_kwargs(execute_kwargs_data, username)
                flow_start_params["execute_kwargs"] = {
                    "executor": execute_kwargs.executor,
                }
                if execute_kwargs_data.get("timeout"):
                    flow_start_params["execute_kwargs"]["timeout"] = execute_kwargs_data["timeout"]

            rm = PluginResourceManager(username=username)
            result = rm.start_flow_agent(data=flow_start_params)
            return Response(data=result)
        except Exception as err:
            self._handle_api_error("start", err)

    @action(detail=True, methods=["GET"], url_path="task_info")
    def task_info(self, request: Request, pk=None):
        """获取 Flow Agent 任务信息

        GET /flow_agent/{task_id}/task_info/

        路径参数：
            task_id: bkflow 任务 ID

        响应示例：
        {
            "task_id": 943095,
            "task_name": "xxx_20260317100357",
            "task_state": "FAILED",
            "nodes": {...},
            "statistics": {...},
            "task_outputs": [...]
        }
        """
        task_id = pk
        username = self.get_username()

        try:
            rm = PluginResourceManager(username=username)
            result = rm.get_flow_agent_task_info(task_id=task_id)
            return Response(data=result)
        except Exception as err:
            self._handle_api_error("task_info", err)

    @action(detail=True, methods=["GET"], url_path="task_node_info/(?P<node_id>[^/.]+)")
    def task_node_info(self, request: Request, pk=None, node_id=None):
        """获取 Flow Agent 任务节点信息

        GET /flow_agent/{task_id}/task_node_info/{node_id}/

        路径参数：
            task_id: bkflow 任务 ID
            node_id: 节点 ID

        响应示例：
        {
            "task_id": 943095,
            "node_id": "ne56746104da3a758d43386fc5786064",
            "basic_info": {...},
            "inputs": {...},
            "outputs": [...],
            "plugin_output": [...]
        }
        """
        task_id = pk
        username = self.get_username()

        try:
            rm = PluginResourceManager(username=username)
            result = rm.get_flow_agent_task_node_info(task_id=task_id, node_id=node_id)
            return Response(data=result)
        except Exception as err:
            self._handle_api_error("task_node_info", err)

    @action(detail=False, methods=["POST"], url_path="stop")
    def stop(self, request: Request):
        """停止 Flow Agent 任务

        POST /flow_agent/stop/

        请求体：
        {
            "session_code": "xxx"    // 会话 session code
        }

        响应：
        {
            "success": true
        }
        """
        return self._session_code_action(request, "stop", "stop_flow_agent_task")

    @action(detail=False, methods=["POST"], url_path="pause")
    def pause(self, request: Request):
        """暂停 Flow Agent 任务

        POST /flow_agent/pause/

        请求体：
        {
            "session_code": "xxx"    // 会话 session code
        }

        响应：
        {
            "success": true
        }
        """
        return self._session_code_action(request, "pause", "pause_flow_agent_task")

    @action(detail=False, methods=["POST"], url_path="resume")
    def resume(self, request: Request):
        """恢复 Flow Agent 任务

        POST /flow_agent/resume/

        请求体：
        {
            "session_code": "xxx"    // 会话 session code
        }

        响应：
        {
            "success": true
        }
        """
        return self._session_code_action(request, "resume", "resume_flow_agent_task")

    def _node_action_with_resume(self, request: Request, pk, node_id: str, action_name: str, client_method_name: str):
        """节点操作（retry/skip）+ 恢复轮询 SSE 流的通用逻辑

        操作成功后，构建 FlowAgentCompletionAgent 以 task_id 跳过 start，
        直接进入轮询，将后续任务状态通过 SSE 流式推送给前端。

        Args:
            request: DRF 请求对象
            pk: 路径参数，即 session_code
            node_id: 节点 ID
            action_name: 操作名称（"retry" / "skip"），用于日志和事件
            client_method_name: resource_manager 上要调用的方法名
        """
        session_code = pk
        username = self.get_username()
        task_id = request.data.get("task_id")

        if task_id is None:
            raise ClientBlueException(message="task_id is required for node retry/skip")

        try:
            # 1. 调用平台 API 执行节点操作（通过 PluginResourceManager 走 resource_manager 协议）
            resource_manager = PluginResourceManager(username=username)
            method = getattr(resource_manager, client_method_name)
            result = method(session_code=session_code, node_id=node_id)
            logger.info(
                "[FLOW_AGENT] Node %s success: session_code=%s, node_id=%s, task_id=%s, result=%s",
                action_name, session_code, node_id, task_id, result,
            )
        except Exception as err:
            self._handle_api_error(f"{action_name}_node", err)

        # 2. 操作成功，恢复 SSE 轮询流
        try:
            poll_interval = float(request.data.get("poll_interval", agent_settings.FLOW_AGENT_POLL_INTERVAL))
            poll_timeout = float(request.data.get("poll_timeout", agent_settings.FLOW_AGENT_POLL_TIMEOUT))

            agent_instance = FlowAgentCompletionAgent(
                resource_manager=resource_manager,
                session_code=session_code,
                task_id=str(task_id),
                resume_from_node=action_name,
                poll_interval=poll_interval,
                poll_timeout=poll_timeout,
            )

            generator = agent_instance.execute()
            return self._streaming_response(generator, session_code=session_code)
        except Exception as err:
            logger.exception(
                "[FLOW_AGENT] Failed to resume polling after %s: session_code=%s, task_id=%s, error=%s",
                action_name, session_code, task_id, err,
            )
            self._handle_api_error(f"{action_name}_node_resume", err)

    def _streaming_response(self, generator, session_code: str = ""):
        """构建 SSE 流式响应"""
        sr = StreamingHttpResponse(generator)
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        sr.headers["content-type"] = "text/event-stream"
        if session_code:
            sr.headers["x-bkaidev-agent-session-code"] = session_code
        return sr

    @action(detail=True, methods=["POST"], url_path="node/(?P<node_id>[^/.]+)/retry")
    def retry_node(self, request: Request, pk=None, node_id=None):
        """重试 Flow Agent 任务节点

        POST /flow_agent/{session_code}/node/{node_id}/retry/

        路径参数：
            session_code: 会话 session code
            node_id: 节点 ID

        请求体：
        {
            "task_id": 12345,              // 必填，BKFlow 任务 ID
            "poll_interval": 2.0,          // 可选，轮询间隔（秒）
            "poll_timeout": 3600.0         // 可选，轮询超时（秒）
        }

        响应：SSE 流（text/event-stream），包含 flow_agent_restart + 后续轮询事件
        """
        return self._node_action_with_resume(request, pk, node_id, "retry", "retry_flow_agent_node")

    @action(detail=True, methods=["POST"], url_path="node/(?P<node_id>[^/.]+)/skip")
    def skip_node(self, request: Request, pk=None, node_id=None):
        """跳过 Flow Agent 任务节点

        POST /flow_agent/{session_code}/node/{node_id}/skip/

        路径参数：
            session_code: 会话 session code
            node_id: 节点 ID

        请求体：
        {
            "task_id": 12345,              // 必填，BKFlow 任务 ID
            "poll_interval": 2.0,          // 可选，轮询间隔（秒）
            "poll_timeout": 3600.0         // 可选，轮询超时（秒）
        }

        响应：SSE 流（text/event-stream），包含 flow_agent_restart + 后续轮询事件
        """
        return self._node_action_with_resume(request, pk, node_id, "skip", "skip_flow_agent_node")
