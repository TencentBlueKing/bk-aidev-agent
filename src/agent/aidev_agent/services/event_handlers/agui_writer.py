# -*- coding: utf-8 -*-
"""AG-UI 会话回写器 - API 方式

通过 BKAidev API 将 Agent 事件回写到平台数据库。
适用于插件、第三方应用等需要通过 API 访问平台的场景。
"""

from logging import getLogger
from typing import Any

from aidev_agent.api.bkaidev_client.client import Client
from aidev_agent.enums import SessionsStatus
from aidev_agent.services.event_handlers.base import BaseSessionWriter

logger = getLogger(__name__)


class AGUISessionWriter(BaseSessionWriter):
    """AG-UI 会话回写器（API 方式）

    通过 BKAidev API Client 将 Agent 事件回写到平台。

    Example:
        ```python
        from aidev_agent.api.bkaidev_client.client import Client
        from aidev_agent.services.event_handlers import AGUISessionWriter

        client = Client(...)
        writer = AGUISessionWriter(
            session_code="xxx",
            client=client,
            username="admin",
            tools=tools,  # 可选，用于获取工具描述信息
        )

        # 作为 event_handler 传入 ChatCompletionAgent
        agent = ChatCompletionAgent(
            ...,
            event_handler=writer,
        )
        ```
    """

    def __init__(
        self,
        session_code: str,
        client: Client,
        username: str = "",
        tools: list | None = None,
    ):
        """初始化 API 回写器

        Args:
            session_code: 会话标识
            client: BKAidev API 客户端
            username: 用户名
            tools: 工具列表，用于获取工具描述信息
        """
        super().__init__(session_code=session_code, username=username, tools=tools)
        self.client = client
        # 缓存 session_property，避免 update_flow_agent_info 每次都额外 GET
        self._cached_session_property: dict | None = None

    def _do_create_content(self, payload: dict[str, Any], headers: dict[str, str]) -> int | None:
        """通过 API 创建会话内容
        Returns:
            创建成功时返回记录 ID，解析失败时返回 None
        """
        logger.info("开始创建会话内容: session_code=%s, payload=%s, headers=%s", self.session_code, payload, headers)
        result = self.client.api.create_chat_session_content(json=payload, headers=headers)
        data = result.get("data", {})
        content_id = data.get("id") if isinstance(data, dict) else None
        if content_id is not None:
            logger.info("创建会话内容成功: content_id=%s", content_id)
        return content_id

    def _do_update_content(self, content_id: int, payload: dict[str, Any], headers: dict[str, str]) -> None:
        """通过 API 更新已有的会话内容"""
        logger.info("开始更新会话内容: content_id=%s, payload=%s, headers=%s", content_id, payload, headers)
        self.client.api.update_chat_session_content(
            path_params={"id": content_id},
            json=payload,
            headers=headers,
        )

    def set_streaming_started(self) -> None:
        """标记流式传输开始（会话状态设为 running）"""
        self._update_session_status(SessionsStatus.RUNNING.value)

    def set_streaming_finished(self) -> None:
        """
        标记流式传输结束
        根据是否被取消选择不同的结束状态：
        - 正常完成：会话状态设为 finished
        - 用户取消/暂停：会话状态设为 cancelled
        """
        if self._is_cancelled:
            self._update_session_status(SessionsStatus.CANCELLED.value)
        else:
            self._update_session_status(SessionsStatus.FINISHED.value)

    def _update_session_status(self, status: str) -> None:
        """更新会话状态（内部方法）

        Args:
            status: 会话状态，如 "running", "finished"
        """
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        try:
            logger.info("开始更新会话状态: session_code=%s, status=%s", self.session_code, status)
            result = self.client.api.update_chat_session(
                path_params={"session_code": self.session_code},
                json={"status": status},
                headers=headers,
            )
            logger.info("会话状态更新成功: session_code=%s, status=%s, result=%s", self.session_code, status, result)
        except Exception:
            logger.exception("会话状态更新失败: session_code=%s, status=%s", self.session_code, status)

    def update_flow_agent_info(self, task_id: str) -> None:
        """更新 session 中的 Flow Agent task_id

        通过 session_property.flow_info 持久化 task_id 到 session 元数据，
        前端切回 session 时通过 GET /session/{session_code}/ 即可获取。
        后端 ChatSession 模型中，flow_info 保存在 property (ChatSessionProperty) 内：
            property.flow_info = SessionFlowInfo(flow_id, task_id, flow_version)
        更新接口通过 session_property 字段写入。

        首次调用时会 GET session 并缓存 session_property，后续调用直接使用缓存，
        避免每次都产生额外的 GET 请求。

        Args:
            task_id: bkflow 任务 ID
        """
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        try:
            logger.info(
                "更新 flow_agent task_id: session_code=%s, task_id=%s",
                self.session_code,
                task_id,
            )
            # 1. 首次调用时获取并缓存 session_property，保留 flow_info 中已有的 flow_id / flow_version 等字段
            if self._cached_session_property is None:
                try:
                    session_data = self.client.api.retrieve_chat_session(
                        path_params={"session_code": self.session_code},
                        headers=headers,
                    ).get("data", {})
                    self._cached_session_property = session_data.get("session_property", {}) or {}
                except Exception:
                    logger.warning("获取 session property 失败，将直接覆盖: session_code=%s", self.session_code)
                    self._cached_session_property = {}

            # 2. 合并更新 task_id 到 flow_info
            current_flow_info = self._cached_session_property.get("flow_info", {}) or {}
            current_flow_info["task_id"] = task_id
            self._cached_session_property["flow_info"] = current_flow_info

            # 3. 通过 session_property 字段整体更新回去（保留所有已有字段）
            self.client.api.update_chat_session(
                path_params={"session_code": self.session_code},
                json={
                    "session_property": self._cached_session_property,
                },
                headers=headers,
            )
            logger.info(
                "更新 flow_agent task_id 成功: session_code=%s, task_id=%s, session_property=%s",
                self.session_code,
                task_id,
                self._cached_session_property,
            )
        except Exception:
            logger.exception("更新 flow_agent task_id 失败: session_code=%s, task_id=%s", self.session_code, task_id)
