# -*- coding: utf-8 -*-
"""Session 管理。

封装 chat session 的取/建、内容持久化；底层 client 取自构造时注入的 ``resource_manager``，
未注入时回落 ``resource_manager()`` 全局单例（应用态），不直接依赖
``aidev_agent.api.bk_aidev.BKAidevApi``。
"""

from __future__ import annotations

import hashlib
import uuid
from logging import getLogger
from typing import Iterable

from aidev_agent.enums import ChannelType, ChatContentStatus, PromptRole, SessionsStatus
from aidev_agent.packages.resource_manager import ResourceManagerProtocol
from aidev_agent.packages.resource_manager.registry import resource_manager as resource_manager_factory
from aidev_agent.pydantic_models import ChatPrompt
from django.conf import settings

from ..constants import AGUI_PROTOCOL_VERSION
from ..enums import PluginPollTaskState

logger = getLogger(__name__)

STALE_SESSION_THRESHOLD_SECONDS = 1800  # 30 分钟


class SessionManager:
    """会话管理：取/建 session、持久化 chat history、保存 AI 回复。

    所有 HTTP 调用经由 ``self.resource_manager.get_client()``，业务侧 import 上不再耦合
    ``BKAidevApi``；用户名通过 ``X-BKAIDEV-USER`` header 透传给后端识别用户。

    ``resource_manager`` 由调用方（通常是 view 层的 ``get_resource_manager()``）按请求注入；
    缺省时回落全局单例，此时为纯应用态、不带用户 ``access_token``。
    """

    def __init__(
        self,
        username: str,
        agent_code: str | None = None,
        resource_manager: ResourceManagerProtocol | None = None,
    ):
        self.username = username
        self.agent_code = agent_code or settings.APP_CODE
        self.resource_manager = resource_manager or resource_manager_factory()

    @staticmethod
    def generate_session_code(username: str, agent_code: str, thread_id: str) -> str:
        """``MD5(username:agent_code:thread_id)``，确保 session_code 长度固定且对相同三元组稳定。"""
        raw_string = f"{username}:{agent_code}:{thread_id}"
        return hashlib.md5(raw_string.encode()).hexdigest()

    def _client(self):
        return self.resource_manager.get_client()

    def _user_headers(self) -> dict:
        return {"X-BKAIDEV-USER": self.username}

    def get_or_create_by_session_code(
        self,
        session_code: str,
        session_name="新会话",
        is_temporary=None,
        channel_type: str = ChannelType.POPUP.value,
    ) -> str:
        """根据 ``thread_id`` 取回或创建 session_code（幂等）。

        使用平台 get_or_create 幂等接口，替代 retrieve+create 两步操作。
        """
        self.resource_manager.get_or_create_session(
            session_code=session_code,
            session_name=session_name,
            protocol_version=AGUI_PROTOCOL_VERSION,
            is_temporary=is_temporary,
            channel_type=channel_type,
            headers=self._user_headers(),
        )
        return session_code

    def get_or_create_by_thread_id(
        self,
        thread_id: str,
        channel_type: str = ChannelType.POPUP.value,
    ) -> str:
        """根据 ``thread_id`` 取回或创建 session_code（幂等）。

        使用平台 get_or_create 幂等接口，替代 retrieve+create 两步操作。
        解决 falsy data 边界问题（原 retrieve 返回 data 为 null/空时跳过创建）。
        """
        session_code = self.generate_session_code(self.username, self.agent_code, thread_id)
        return self.get_or_create_by_session_code(session_code, channel_type=channel_type)

    def save_content(
        self,
        session_code: str,
        role: str,
        content: str,
        *,
        extra: dict | None = None,
        status: str = "success",
        turn_id: str = "",
    ) -> dict:
        """保存单条会话内容到 BKAidev；返回后端 ``data`` 字段。"""
        if role == PromptRole.USER.value and not turn_id:
            turn_id = uuid.uuid4().hex
        data: dict = {"session_code": session_code, "role": role, "content": content, "status": status}
        if extra:
            data["extra"] = extra
        if turn_id:
            data["property"] = {"turn_id": turn_id}
        client = self._client()
        result = client.api.create_chat_session_content(json=data, headers=self._user_headers())
        saved = result.get("data", {})
        if turn_id:
            saved.setdefault("property", {}).setdefault("turn_id", turn_id)
        return saved

    def update_session_status(self, session_code: str, status: str) -> None:
        """更新会话状态，用于标准运维插件后台任务兜底结束态。"""
        self._client().api.update_chat_session(
            path_params={"session_code": session_code},
            json={"status": status},
            headers=self._user_headers(),
        )

    def retrieve_session(self, session_code: str) -> dict:
        result = self._client().api.retrieve_chat_session(
            path_params={"session_code": session_code},
            headers=self._user_headers(),
        )
        return result.get("data") or {}

    def get_flow_info(self, session_code: str) -> dict:
        """读取 ``session_property.flow_info``（流程智能体执行信息），不存在时返回空 dict。"""
        session_property = self.retrieve_session(session_code).get("session_property") or {}
        return session_property.get("flow_info") or {}

    def set_flow_resume_pending(
        self,
        session_code: str,
        pending: bool,
        *,
        action: str | None = None,
    ) -> None:
        """设置/清除 flow agent 续流标记 ``session_property.flow_info.resume_pending``。

        采用 read-modify-write：先取出整个 ``session_property``，仅叠加
        ``flow_info.resume_pending``，保留 ``task_id`` / ``flow_id`` 等已有字段后整体回写，
        避免 PUT 覆盖语义清掉其他元数据。

        ``action`` 用于记录本次置位/清除对应的续流动作（如 ``"retry"`` / ``"skip"``）：
        - ``pending=True`` 且传入 ``action``：写入 ``flow_info.resume_action``，供下一次
          ``chat_completion`` 续流时构造 ``flow_agent_restart`` / ``flow_agent_update`` 事件。
        - ``pending=False`` 默认清空 ``resume_action``（一次性消费语义），保持与
          ``resume_pending`` 状态机一致；若显式希望保留旧值，可传 ``action=""``（None 走默认清空）。
        """
        session_property = self.retrieve_session(session_code).get("session_property") or {}
        flow_info = session_property.get("flow_info") or {}
        flow_info["resume_pending"] = pending
        if pending:
            if action is not None:
                flow_info["resume_action"] = action
        else:
            # 清除续流标记时同步清空 action，避免下一轮被误读
            flow_info["resume_action"] = ""
        session_property["flow_info"] = flow_info
        self._client().api.update_chat_session(
            path_params={"session_code": session_code},
            json={"session_property": session_property},
            headers=self._user_headers(),
        )

    def save_chat_history(self, session_code: str, chat_history: Iterable[ChatPrompt] | None) -> None:
        """按顺序持久化 ``chat_history``；部分失败时记录错误但不中断循环。"""
        errors: list[tuple[int, str]] = []
        for i, prompt in enumerate(chat_history or []):
            try:
                self.save_content(session_code=session_code, role=prompt.role, content=prompt.content)
            except Exception as e:
                errors.append((i, str(e)))
                logger.warning("save_chat_history item %d failed: %s", i, e)
        if errors:
            logger.error(
                "save_chat_history completed with %d failures: session_code=%s",
                len(errors),
                session_code,
            )

    def save_ai_response(self, session_code: str, result: dict, *, turn_id: str = "") -> None:
        """从非流式 LLM 响应中提取 ``choices[0].delta.content`` 并写回。"""
        content = ""
        has_tool_calls = False
        if "choices" in result and result["choices"]:
            delta = result["choices"][0].get("delta", {})
            content = delta.get("content", "")
            has_tool_calls = bool(delta.get("tool_calls"))
        if content:
            self.save_content(session_code=session_code, role=PromptRole.AI.value, content=content, turn_id=turn_id)
        elif has_tool_calls:
            # tool_calls 场景：AI 仅调用工具不产生文本，写入占位消息
            self.save_content(
                session_code=session_code, role=PromptRole.AI.value, content="正在调用工具...", turn_id=turn_id
            )

    def list_session_contents(self, session_code: str) -> list[dict]:
        result = self._client().api.get_chat_session_contents(
            params={"session_code": session_code},
            headers=self._user_headers(),
        )
        return result.get("data") or []

    def prepare_session_turn(
        self,
        thread_id: str,
        *,
        input_text: str = "",
        turn_id: str = "",
        channel_type: str = ChannelType.POPUP.value,
    ) -> tuple[str, str]:
        """取/建 session，必要时落库本轮 user，返回 ``session_code`` 与 ``turn_id``。"""
        session_code = self.get_or_create_by_thread_id(thread_id, channel_type=channel_type)
        if input_text:
            saved = self.save_content(
                session_code=session_code,
                role=PromptRole.USER.value,
                content=input_text,
                turn_id=turn_id,
            )
            turn_id = ((saved.get("property") or {}).get("turn_id") if isinstance(saved, dict) else "") or turn_id
        elif not turn_id:
            # 用户消息已由前端/SDK 落库、本轮无 input 时，继承最近一条 user 的 turn_id
            for item in reversed(self.list_session_contents(session_code)):
                if item.get("role") != PromptRole.USER.value:
                    continue
                turn_id = (item.get("property") or {}).get("turn_id") or ""
                if turn_id:
                    break
        return session_code, turn_id or uuid.uuid4().hex

    def save_stream_failure(self, session_code: str, error_message: str, *, turn_id: str = "") -> None:
        self.save_content(
            session_code=session_code,
            role=PromptRole.ASSISTANT.value,
            content=error_message,
            status=ChatContentStatus.ERROR.value,
            turn_id=turn_id,
        )
        self.update_session_status(session_code, SessionsStatus.FAILED.value)

    def poll_task_state(self, session_code: str, *, turn_id: str = "") -> tuple[PluginPollTaskState, str]:
        """查询本轮 Agent 是否结束。返回 (state, detail)。

        插件 2.0 以 ``session.status`` 判断单轮会话状态。
        """
        status = str(self.retrieve_session(session_code).get("status") or "")
        if status in (SessionsStatus.PENDING.value, SessionsStatus.RUNNING.value):
            return PluginPollTaskState.RUNNING, ""
        if status in (SessionsStatus.FAILED.value, SessionsStatus.CANCELLED.value):
            # 取回 save_stream_failure 写入的实际异常内容，避免 UI 只显示通用 "Agent 执行失败"
            return PluginPollTaskState.FAILED, self._last_output(
                self.list_session_contents(session_code),
                turn_id=turn_id,
                statuses=(ChatContentStatus.ERROR.value,),
            ) or "Agent 执行失败"
        if status == SessionsStatus.FINISHED.value:
            return PluginPollTaskState.SUCCESS, self._last_output(
                self.list_session_contents(session_code),
                turn_id=turn_id,
                statuses=(ChatContentStatus.COMPLETE.value, ChatContentStatus.SUCCESS.value),
            )
        return PluginPollTaskState.RUNNING, ""

    @staticmethod
    def _last_output(
        items: list[dict],
        *,
        turn_id: str = "",
        statuses: tuple[str, ...],
    ) -> str:
        """取最后一条指定 status 的 assistant/ai 内容；有 ``turn_id`` 时仅取同轮消息。

        FINISHED 取 COMPLETE/SUCCESS 的正常回复；FAILED/CANCELLED 取 ERROR 的实际异常
        （save_stream_failure 写入），避免上层只看到通用 "Agent 执行失败"。
        """
        assistant_roles = (PromptRole.ASSISTANT.value, PromptRole.AI.value)
        for item in reversed(items):
            if item.get("role") not in assistant_roles:
                continue
            if turn_id and (item.get("property") or {}).get("turn_id") != turn_id:
                continue
            if item.get("status") not in statuses:
                continue
            text = str(item.get("content") or "").strip()
            if text:
                return text
        return ""
