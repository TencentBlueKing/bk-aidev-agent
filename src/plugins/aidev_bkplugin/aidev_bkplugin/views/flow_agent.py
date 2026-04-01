# -*- coding: utf-8 -*-

from logging import getLogger

from blueapps.core.exceptions import ClientBlueException
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.views import Response

from aidev_bkplugin.services.agent import build_execute_kwargs
from aidev_bkplugin.utils import bkaidev_api_client, get_flow_agent_client

from .builtin import IgnoreClientContentNegotiation, PluginViewSet

logger = getLogger(__name__)


class FlowAgentViewSet(PluginViewSet):
    """Flow Agent 视图集

    提供六个接口：
    1. POST   /flow_agent/start/                          - 启动 Flow Agent 任务
    2. GET    /flow_agent/{task_id}/task_info/             - 获取任务信息
    3. GET    /flow_agent/{task_id}/task_node_info/{node_id}/ - 获取任务节点信息
    4. POST   /flow_agent/stop/                           - 停止 Flow Agent 任务
    5. POST   /flow_agent/pause/                          - 暂停 Flow Agent 任务
    6. POST   /flow_agent/resume/                         - 恢复 Flow Agent 任务
    """

    # 使用自定义内容协商，支持流式响应
    content_negotiation_class = IgnoreClientContentNegotiation

    @staticmethod
    def _get_username(request: Request) -> str:
        """从请求中提取 username，兜底从请求体或 header 获取"""
        username = request.user.username
        if not username:
            username = request.data.get("username", "") or request.META.get("HTTP_X_BKAIDEV_USER", "")
        return username

    @staticmethod
    def _handle_api_error(action_name: str, err: Exception) -> None:
        """统一的 API 异常处理：记录日志并抛出 ClientBlueException"""
        logger.exception("FlowAgentViewSet %s error: %s", action_name, err)
        message = getattr(err, "message", str(err))
        raise ClientBlueException(message=message)

    def _session_code_action(
        self, request: Request, action_name: str, client_method_name: str
    ) -> Response:
        """stop / pause / resume 三个操作的通用执行逻辑

        Args:
            request: DRF 请求对象
            action_name: 操作名称，用于日志记录（如 "stop"、"pause"、"resume"）
            client_method_name: flow agent client 上要调用的方法名
                （如 "stop_flow_agent_task"、"pause_flow_agent_task"）
        """
        username = self._get_username(request)
        session_code = request.data.get("session_code", "")

        try:
            client, headers = get_flow_agent_client(username)
            method = getattr(client, client_method_name)
            result = method(
                session_code=session_code,
                headers=headers,
            )
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
        username = self._get_username(request)
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

            flow_client, headers = get_flow_agent_client(username)
            result = flow_client.start_flow_agent(
                data=flow_start_params,
                headers=headers,
            )
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
        username = self._get_username(request)

        try:
            result = bkaidev_api_client.get_flow_agent_task_info(
                task_id=task_id,
                headers={"X-BKAIDEV-USER": username},
            )
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
        username = self._get_username(request)

        try:
            result = bkaidev_api_client.get_flow_agent_task_node_info(
                task_id=task_id,
                node_id=node_id,
                headers={"X-BKAIDEV-USER": username},
            )
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
