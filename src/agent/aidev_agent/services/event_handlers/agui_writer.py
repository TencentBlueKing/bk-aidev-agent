# -*- coding: utf-8 -*-
"""AG-UI 会话回写器 - API 方式

通过 BKAidev API 将 Agent 事件回写到平台数据库。
适用于插件、第三方应用等需要通过 API 访问平台的场景。
"""

import json
import time
from logging import getLogger
from typing import Any

from aidev_agent.api.bk_aidev import Client
from aidev_agent.core.ag_ui.ask_user_question import (
    ASK_USER_QUESTION_REASON,
    AskUserQuestionOutcomeBuilder,
    build_updated_builtin_property,
    find_pending_interrupt,
)
from aidev_agent.core.ag_ui.types import RunFinishedOutcomeType
from aidev_agent.enums import ActivityType, PromptRole, SessionsStatus
from aidev_agent.services.event_handlers.base import BaseSessionWriter

logger = getLogger(__name__)


class AGUISessionWriter(BaseSessionWriter):
    """AG-UI 会话回写器（API 方式）

    通过 BKAidev API Client 将 Agent 事件回写到平台。

    Example:
        ```python
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

    _SESSION_STATUS_MAX_ATTEMPTS = 3
    _SESSION_STATUS_RETRY_BASE_DELAY = 0.2

    def __init__(
        self,
        session_code: str,
        client: Client,
        username: str = "",
        tools: list | None = None,
        turn_id: str = "",
        task_id: str = "",
    ):
        """初始化 API 回写器

        Args:
            session_code: 会话标识
            client: BKAidev API 客户端
            username: 用户名
            tools: 工具列表，用于获取工具描述信息
            turn_id: 同一次 user-ai 回复的轮次 ID，非空时会写入回写记录的 property.turn_id
            task_id: 本轮 bkflow 任务 ID；retry/skip 时按 content.task_id 绑定已有 activity
        """
        super().__init__(session_code=session_code, username=username, tools=tools, turn_id=turn_id)
        self.client = client
        self.task_id = task_id
        # 缓存 session_property，避免 update_flow_agent_info 每次都额外 GET
        self._cached_session_property: dict | None = None
        self._has_run_error = False

    def handle_flow_agent_result(self, event) -> None:
        # retry/skip resume：一轮对话一个 task_id，先绑定已有 activity 再走基类 update
        if not self._flow_result_content_id and self.task_id:
            self._bind_flow_result_for_resume()
        super().handle_flow_agent_result(event)

    def _bind_flow_result_for_resume(self) -> None:
        """retry/skip：按 content.task_id 定位本轮已有 flow_agent activity"""
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        try:
            contents = (
                self.client.api.get_chat_session_contents(
                    params={"session_code": self.session_code},
                    headers=headers,
                ).get("data")
                or []
            )
        except Exception as err:
            logger.exception("bind flow_agent result failed: session=%s task=%s", self.session_code, self.task_id)
            raise RuntimeError(
                f"resume 回写失败：查询 flow_agent activity 异常，"
                f"session_code={self.session_code}, task_id={self.task_id}"
            ) from err

        for item in reversed(contents):
            prop = item.get("property") or {}
            builtin = prop.get("builtin_property") or {}
            if item.get("role") != PromptRole.ACTIVITY.value or builtin.get("type") != ActivityType.FLOW_AGENT.value:
                continue
            raw = item.get("content")
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw if raw else {}
            except (TypeError, ValueError):
                data = {}
            if isinstance(data, list):
                data = data[0] if data else {}
            record_task_id = str(data.get("task_id", "")) if isinstance(data, dict) else ""
            if record_task_id != str(self.task_id):
                continue

            self._flow_result_content_id = item.get("id")
            self._flow_result_message_id = builtin.get("message_id")
            if not self.turn_id and prop.get("turn_id"):
                self.turn_id = prop["turn_id"]
            return

        raise RuntimeError(
            f"resume 回写失败：未找到 task_id={self.task_id} 的 flow_agent activity，session_code={self.session_code}"
        )

    def handle_run_finished(self, event) -> None:
        """处理 RUN_FINISHED 事件，额外检测中断并触发后台续流。

        ask_user_question 续流首帧 RunFinishedEvent（outcome.type=success）在非
        interrupt 分支通过 _handle_ask_user_question_resume_finished 完成 DB 终态写入。
        """
        super().handle_run_finished(event)

        outcome = getattr(event, "outcome", None)
        # 兼容 outcome 为 dict 或对象的情况
        outcome_type = (
            outcome.get("type") if isinstance(outcome, dict) else getattr(outcome, "type", None) if outcome else None
        )
        if outcome and outcome_type == RunFinishedOutcomeType.INTERRUPT.value:
            graph_thread_id = getattr(event, "thread_id", "")
            interrupts = [
                interrupt.model_dump(by_alias=True) if hasattr(interrupt, "model_dump") else interrupt
                for interrupt in (
                    (outcome.get("interrupts") if isinstance(outcome, dict) else getattr(outcome, "interrupts", []))
                    or []
                )
            ]
            self._set_pending_interrupt_context(graph_thread_id=graph_thread_id, interrupts=interrupts)

            # 仅对 approval 中断启动后台续流 worker。
            # ask_user_question 中断由前端直接续流（用户选择后调 chat_completion），
            # 不需要后台轮询；如果启动 worker 会抢先续流，干扰前端续流。
            first_interrupt = interrupts[0] if interrupts else {}
            first_reason = first_interrupt.get("reason") if isinstance(first_interrupt, dict) else None
            if first_reason == "aidev:tool_approval":
                try:
                    # 延迟导入避免循环依赖：
                    # agui_writer -> approval_resume -> agent_builder -> services.agent -> chat -> event_handlers
                    from aidev_bkplugin.services.approval_resume import start_approval_resume_worker

                    start_approval_resume_worker(self.session_code, self.username, graph_thread_id, interrupts)
                except Exception:
                    logger.exception("[AGUISessionWriter] 触发后台续流失败: session_code=%s", self.session_code)
            else:
                logger.info(
                    "[AGUISessionWriter] 非 approval 中断（reason=%s），跳过后台续流 worker: session_code=%s",
                    first_reason,
                    self.session_code,
                )
            return

        self._clear_pending_interrupt_context()

        # ask_user_question 续流首帧 RunFinishedEvent（outcome.type=success）：
        # 从 event.outcome.interrupts[0] 提取 interrupt_id，
        # 从 event.result 提取 resume_answers，查 DB pending 记录并更新为 resolved 终态。
        if outcome and outcome_type != "interrupt":
            self._handle_ask_user_question_resume_finished(event)

    def _handle_ask_user_question_resume_finished(self, event) -> None:
        """ask_user_question 续流首帧 RunFinishedEvent 的 DB 终态写入。

        从 event.outcome.interrupts[0].id 提取 interrupt_id，
        从 event.result.payload.answers 提取 resume_answers，
        查 DB pending 记录并更新为 resolved 终态。
        """
        # 1. 从 RunFinishedEvent 提取 interrupt_id + resume_answers
        outcome = getattr(event, "outcome", None)
        if isinstance(outcome, dict):
            interrupts = outcome.get("interrupts") or []
        else:
            interrupts = getattr(outcome, "interrupts", []) if outcome else []
        if not interrupts:
            return
        first_interrupt = interrupts[0] if isinstance(interrupts[0], dict) else {}
        if first_interrupt.get("reason") != ASK_USER_QUESTION_REASON:
            return  # 非 ask_user_question，跳过
        interrupt_id = first_interrupt.get("id")
        if not interrupt_id:
            return
        # resume_answers 从 event.result 提取（result 是 _build_result_from_first_interrupt 的 dict）
        result = getattr(event, "result", None)
        resume_answers = []
        if isinstance(result, dict):
            resume_answers = result.get("payload", {}).get("answers") or []

        # 2. DB I/O：查询 session contents
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        try:
            contents = (
                self.client.api.get_chat_session_contents(
                    params={"session_code": self.session_code},
                    headers=headers,
                ).get("data")
                or []
            )
        except Exception:
            logger.exception(
                "[AskUserQuestion] _handle_ask_user_question_resume_finished: 查询 session contents 失败: session_code=%s",
                self.session_code,
            )
            return

        # 3. 协议匹配：找 pending interrupt 记录（纯函数）
        found = find_pending_interrupt(contents, interrupt_id)
        if found is None:
            logger.warning(
                "[AskUserQuestion] _handle_ask_user_question_resume_finished: 未找到 pending interrupt 记录, "
                "message_id=%s, session_code=%s",
                interrupt_id,
                self.session_code,
            )
            return
        content_id, raw_db_content, db_item = found

        # 4. 调用已有 OutcomeBuilder（已在 core/ag_ui）
        upgraded = AskUserQuestionOutcomeBuilder.upgrade_content_to_success(
            raw_db_content, "resolved", resume_answers=resume_answers
        )
        if upgraded is None:
            logger.warning(
                "[AskUserQuestion] _handle_ask_user_question_resume_finished: upgrade_content_to_success 返回 None, content_id=%s",
                content_id,
            )
            return

        # 5. 构造 updated_builtin（纯函数）
        updated_builtin = build_updated_builtin_property(db_item, interrupt_id, "resolved")

        # 6. DB I/O：更新 content
        try:
            self._do_update_content(
                content_id=content_id,
                payload={
                    "content": upgraded,
                    "status": "complete",
                    "property": {
                        "builtin_property": updated_builtin,
                        "turn_id": self.turn_id,
                    },
                },
                headers=headers,
            )
            logger.info(
                "[AskUserQuestion] interrupt 记录更新为 resolved: content_id=%s, message_id=%s, session_code=%s",
                content_id,
                interrupt_id,
                self.session_code,
            )
        except Exception:
            logger.exception(
                "[AskUserQuestion] _handle_ask_user_question_resume_finished: 更新 interrupt 记录失败, content_id=%s, session_code=%s",
                content_id,
                self.session_code,
            )

    def _ensure_session_property_cache(self) -> None:
        if self._cached_session_property is not None:
            return
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        result = self.client.api.retrieve_chat_session(
            path_params={"session_code": self.session_code},
            headers=headers,
        )
        data = result.get("data", {}) if isinstance(result, dict) else {}
        session_property = data.get("session_property", {}) if isinstance(data, dict) else {}
        self._cached_session_property = session_property if isinstance(session_property, dict) else {}

    def _update_session_property(self) -> None:
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        self.client.api.update_chat_session(
            path_params={"session_code": self.session_code},
            json={"session_property": self._cached_session_property or {}},
            headers=headers,
        )

    def _set_pending_interrupt_context(self, *, graph_thread_id: str, interrupts: list[dict[str, Any]]) -> None:
        try:
            self._ensure_session_property_cache()
            self._cached_session_property["pending_interrupt"] = {
                "graph_thread_id": graph_thread_id,
                "interrupts": interrupts,
            }
            self._update_session_property()
        except Exception:
            logger.exception(
                "[AGUISessionWriter] 写入 pending_interrupt 失败: session_code=%s, graph_thread_id=%s",
                self.session_code,
                graph_thread_id,
            )

    def _clear_pending_interrupt_context(self) -> None:
        try:
            self._ensure_session_property_cache()
            if not self._cached_session_property.pop("pending_interrupt", None):
                return
            self._update_session_property()
        except Exception:
            logger.exception("[AGUISessionWriter] 清理 pending_interrupt 失败: session_code=%s", self.session_code)

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
        - 运行错误：会话状态设为 failed
        - 用户取消/暂停：会话状态设为 cancelled
        """
        if self._is_cancelled:
            status = SessionsStatus.CANCELLED.value
        elif self._has_run_error:
            status = SessionsStatus.FAILED.value
        else:
            status = SessionsStatus.FINISHED.value
        self._update_session_status(status, raise_on_failure=True)

    def handle_run_error(self, event) -> None:
        """记录运行错误；会话终态由 EOD 提交后的唯一完成回调统一写入。"""
        super().handle_run_error(event)
        # 中断审批场景下清理 pending_interrupt
        self._clear_pending_interrupt_context()
        if not self._is_cancelled:
            self._has_run_error = True

    def _update_session_status(self, status: str, *, raise_on_failure: bool = False) -> None:
        """更新会话状态（内部方法）

        Args:
            status: 会话状态，如 "running", "finished"
        """
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        for attempt in range(self._SESSION_STATUS_MAX_ATTEMPTS):
            try:
                logger.info(
                    "开始更新会话状态: session_code=%s, status=%s, attempt=%d",
                    self.session_code,
                    status,
                    attempt + 1,
                )
                result = self.client.api.update_chat_session(
                    path_params={"session_code": self.session_code},
                    json={"status": status},
                    headers=headers,
                )
                logger.info(
                    "会话状态更新成功: session_code=%s, status=%s, result=%s", self.session_code, status, result
                )
                return
            except Exception:
                is_last_attempt = attempt == self._SESSION_STATUS_MAX_ATTEMPTS - 1
                if is_last_attempt:
                    logger.exception("会话状态更新失败: session_code=%s, status=%s", self.session_code, status)
                    if raise_on_failure:
                        raise
                    return

                delay = self._SESSION_STATUS_RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "会话状态更新失败，将重试: session_code=%s, status=%s, delay=%.1fs",
                    self.session_code,
                    status,
                    delay,
                    exc_info=True,
                )
                time.sleep(delay)

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
