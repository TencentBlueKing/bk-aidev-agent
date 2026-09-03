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
from aidev_agent.core.ag_ui.types import RunFinishedOutcomeType
from aidev_agent.enums import ActivityType, PromptRole, SessionsStatus
from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_REASON,
    TOOL_APPROVAL_REASON,
    get_side_effect,
    register_side_effect,
)
from aidev_agent.services.event_handlers.base import BaseSessionWriter

logger = getLogger(__name__)


def _approval_worker_factory(session_code: str, username: str | None, graph_thread_id: str | None, interrupts: list):
    """构造 approval 后台续流 worker（D-10 注册表装配点）。

    worker 实现 ``aidev_bkplugin.services.approval_resume.start_approval_resume_worker``
    为仓库外模块，**函数级延迟导入兜底**（避免
    agui_writer -> approval_resume -> agent_builder -> ... 循环依赖），
    符合 harness 红线（本模块不 import core/services/api 反向依赖）。

    Args:
        session_code: 会话 code。
        username: 用户名。
        graph_thread_id: 图线程 id。
        interrupts: 全部 interrupts 列表（透传 worker）。

    Returns:
        可调用的 worker（调用即启动后台续流）。
    """

    def _start() -> None:
        from aidev_bkplugin.services.approval_resume import start_approval_resume_worker

        start_approval_resume_worker(session_code, username, graph_thread_id, interrupts)

    return _start


# services 层装配点（D-10）：挂载 approval reason → 后台续流 worker factory。
# 不在 packages 包内注册（对齐 CODEBUDDY 约束：aidev_bkplugin 延迟导入注册在
# services 层装配点）。注册幂等（dict 覆盖）。
register_side_effect(TOOL_APPROVAL_REASON, _approval_worker_factory)


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
        task_id: int | str = "",
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

    def _merge_artifacts_into_last_assistant(self, artifacts: list, value: dict) -> bool:
        """API 链路: 把 artifacts 合并进本会话最近一条 assistant 消息的 property.artifacts。
        通过 get_chat_session_contents 拉整会话列表(天然全量, 无 SQL), 内存取最近 assistant,
        合并去重后经 _do_update_content 回写; 找不到 assistant 或异常时返回 False, 交由基类兜底建 activity。"""
        headers = {"X-BKAIDEV-USER": self.username} if self.username else {}
        try:
            contents = (
                self.client.api.get_chat_session_contents(
                    params={"session_code": self.session_code},
                    headers=headers,
                ).get("data")
                or []
            )
            assistant = self._pick_last_assistant(contents)
            if assistant is None:
                return False
            prop = assistant.get("property") or {}
            if not isinstance(prop, dict):
                prop = {}
            self._merge_artifacts_into_property(prop, artifacts)
            self._do_update_content(
                content_id=assistant.get("id"),
                payload={"property": prop},
                headers=headers,
            )
            return True
        except Exception:
            logger.exception("API 合并 artifacts 到 assistant 失败: session_code=%s", self.session_code)
            return False

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

        SSE 层不写 DB，ask_user_question 的 DB 终态由 agent 侧 ChatCompletionAgent.execute()
        前置派发的会话回写事件负责，与 approval 路径一致。
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

            # D-10 查表化：遍历全部 interrupts 的 reason（全量语义，非只看 first_reason），
            # 命中 side_effects 注册表则调对应 worker factory 启动后台续流 worker。
            # ask_user_question 中断由前端直接续流，不注册 side_effect，天然跳过。
            for interrupt in interrupts:
                reason = interrupt.get("reason") if isinstance(interrupt, dict) else None
                factory = get_side_effect(reason)
                if factory is None:
                    continue
                try:
                    # worker 实现（aidev_bkplugin）在 factory 内部做函数级延迟导入兜底，
                    # 避免 agui_writer -> approval_resume -> agent_builder -> ... 循环依赖
                    worker = factory(self.session_code, self.username, graph_thread_id, interrupts)
                    if callable(worker):
                        worker()
                except Exception:
                    logger.exception(
                        "[AGUISessionWriter] 触发后台续流失败: session_code=%s, reason=%s",
                        self.session_code,
                        reason,
                    )
            return

        self._clear_pending_interrupt_context()

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

    def _flush_deferred_tool_call_fallback(self, tool_call_id: str, tool_name: str | None = None) -> None:
        """续流场景下补充写入审批 tool_call（覆写基类空实现，D-12 / D-07）。

        续流时新实例内存无 ``_deferred_approval_tool_calls``，经
        :meth:`_fetch_tool_call_reconstruction` 从 DB 定位并重建
        assistant.tool_calls，补充写入审批 tool_call（补 tool_call_id /
        tool_name / arguments，实现续流回填缺口）。

        Args:
            tool_call_id: 工具调用 ID
            tool_name: 工具名称
        """
        reconstruction = self._fetch_tool_call_reconstruction(tool_call_id, tool_name)
        if reconstruction is None:
            logger.info(
                "[handle_tool_finish] 续流回填 tool_call: 无 DB 命中，跳过。tool_call_id=%s",
                tool_call_id,
            )
            return
        # D-07: 消费完整 merged_property（保留 message_id 等既有键 + 补 type 键），
        # 与内存路径 merge（base._flush_deferred_tool_call）逐字段一致，不再只写 tool_calls。
        content_id, merged_property = reconstruction
        self._safe_call(
            self._do_update_content,
            tool_call_id,
            "update_deferred_tool_call_fallback",
            content_id=content_id,
            payload={
                "property": {
                    "builtin_property": merged_property,
                },
            },
            headers=self._get_headers(),
        )

    def _fetch_tool_call_reconstruction(
        self,
        tool_call_id: str,
        tool_name: str | None = None,
    ) -> tuple[int, dict] | None:
        """从 DB 查询并重建审批 tool_call 的 assistant 记录（续流回填查询步骤）。

        续流时新实例内存无 ``_deferred_approval_tool_calls``，经
        ``get_chat_session_contents`` 拉全量会话记录：

        1. 定位与 ``tool_call_id`` 匹配的 interrupt 记录
           （``builtin_property.tool_call_id`` 匹配），从其 content 提取
           ``toolArgs`` 与 ``toolName``（审批中断 enrich 后已落库，见 D-12 / D-06）。
        2. 定位最近一条 role=assistant 记录，将审批 tool_call
           （``{id, type, function: {name, arguments, ...}}`` OpenAI 嵌套形态）追加到其
           ``tool_calls``（builtin_property 优先，生产返回的 property 不含
           builtin_property 时回退记录顶层账本字段）。
        3. name 恢复链（D-06，根因 A）：主源 ``tool_name``（事件字段，真实工具名）→
           兜底 interrupt 卡片 ``metadata.toolName`` → 兜底 ``_tools_mapping`` 反查；
           任何源取不到时 ``name=""``（绝不再回退到 ``tool_call_id``）。
        4. 返回 ``(assistant_content_id, merged_property)`` 供
           :meth:`_flush_deferred_tool_call_fallback` 回写。
           ``merged_property`` 为完整 builtin_property（展开保留既有键如 ``message_id``
           + 追加后的 ``tool_calls``，D-07 对齐内存路径 merge；tool_call 补 ``type`` 键
           对齐 immediate 形态）。

        无法定位（无匹配 assistant / interrupt）时返回 None（fallback 跳过回写）。

        Args:
            tool_call_id: 工具调用 ID。
            tool_name: 工具名称（重建 tool_call 用，主源）。

        Returns:
            ``(assistant_content_id, merged_property)``；无法定位时返回 None。
        """
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
            logger.exception("[AGUISessionWriter] 续流回填查询会话记录失败: session_code=%s", self.session_code)
            return None

        # 1. 定位匹配 tool_call_id 的 interrupt 记录，提取 toolArgs 与 toolName
        tool_args: dict[str, Any] = {}
        interrupt_tool_name: str | None = None
        for item in contents:
            if item.get("role") != PromptRole.INTERRUPT.value:
                continue
            candidate = self._extract_tool_args_from_interrupt(item, tool_call_id)
            if candidate is not None:
                tool_args, interrupt_tool_name = candidate
                break

        # 2. 定位最近一条 assistant 记录
        assistant = None
        for item in reversed(contents):
            if item.get("role") != PromptRole.ASSISTANT.value:
                continue
            assistant = item
            break
        if assistant is None:
            logger.info(
                "[AGUISessionWriter] 续流回填: 未找到 assistant 记录，跳过。tool_call_id=%s",
                tool_call_id,
            )
            return None

        assistant_prop = assistant.get("property") or {}
        if not isinstance(assistant_prop, dict):
            assistant_prop = {}
        assistant_builtin = assistant_prop.get("builtin_property") or {}
        if not isinstance(assistant_builtin, dict):
            assistant_builtin = {}
        # 生产 get_chat_session_contents 返回的 property 不含 builtin_property，
        # tool_calls 为记录顶层账本字段（单账本形状）——builtin_property 优先，
        # 缺失/为空时回退顶层（对齐 ag_ui/utils._read_field 读序），否则
        # existing_tool_calls 恒为空，幂等检查失效且既有 tool_calls 会丢。
        existing_tool_calls = assistant_builtin.get("tool_calls") or []
        if not isinstance(existing_tool_calls, list):
            existing_tool_calls = []
        if not existing_tool_calls:
            top_level_calls = assistant.get("tool_calls")
            if isinstance(top_level_calls, list):
                existing_tool_calls = top_level_calls
        # 幂等：已含匹配 tool_call_id 则不重复追加
        if any(tc.get("id") == tool_call_id for tc in existing_tool_calls if isinstance(tc, dict)):
            logger.info(
                "[AGUISessionWriter] 续流回填: tool_call 已存在，跳过。tool_call_id=%s",
                tool_call_id,
            )
            return None

        # D-06: name 恢复链（根因 A 修复）——主源事件 tool_name（真实工具名，
        # 经 base.py handle_tool_call_result 透传 ToolMessage.name），兜底
        # interrupt 卡片 metadata.toolName，再兜底 _tools_mapping 反查。
        # 任何源取不到时 name=""（绝不再回退到 tool_call_id，T-45-01）。
        name = ""
        if tool_name:
            name = tool_name
        elif interrupt_tool_name:
            name = interrupt_tool_name
        else:
            mapped_tool = self._tools_mapping.get(tool_call_id)
            if mapped_tool is not None:
                name = getattr(mapped_tool, "name", "") or ""

        merged_tool_calls = list(existing_tool_calls)
        # D-07: 补 type 键，对齐 immediate 形态（event_builders.py:127-135
        # ExtendToolCall.model_dump() 含 id/type/function 三键）。
        merged_tool_calls.append(
            {
                "id": tool_call_id,
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(tool_args, ensure_ascii=False) if tool_args else "{}",
                },
            }
        )
        logger.info(
            "[AGUISessionWriter] 续流回填 tool_call: assistant_content_id=%s, tool_call_id=%s, name=%s, args_keys=%s",
            assistant.get("id"),
            tool_call_id,
            name,
            list(tool_args.keys()),
        )
        # D-07: 展开保留既有键（对齐 base._flush_deferred_tool_call 内存 merge
        # ``{**existing_property, "tool_calls": merged}``），保留 message_id 等键；
        # 既有 tool_calls 若读自顶层账本字段，此处随之并入 builtin_property 写回。
        merged_property = {**assistant_builtin, "tool_calls": merged_tool_calls}
        return assistant.get("id"), merged_property

    @staticmethod
    def _extract_tool_args_from_interrupt(item: dict, tool_call_id: str) -> tuple[dict[str, Any], str | None] | None:
        """从 interrupt 记录的 content 提取匹配 tool_call_id 的 toolArgs 与 toolName（D-12 / D-06）。

        扫描 interrupt content 中 reason 匹配（或 toolCallId 匹配）的 interrupt，
        返回其 ``metadata.toolArgs``（enrich 后已落库）与 ``metadata.toolName``。
        找不到返回 None。

        Args:
            item: interrupt 会话内容记录（role=interrupt）。
            tool_call_id: 目标工具调用 ID。

        Returns:
            ``(toolArgs, toolName)`` 元组；无法定位返回 None。
            toolName 为审批卡片 enrich 已落库的 ``metadata.toolName``（可能缺失，None）。
        """
        raw = item.get("content")
        if not raw:
            return None
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError):
            return None
        interrupts = (data.get("outcome") or {}).get("interrupts") or []
        for intr in interrupts:
            if not isinstance(intr, dict):
                continue
            # D-15：同时认审批（TOOL_APPROVAL_REASON）与 ask_user（ASK_USER_QUESTION_REASON）
            # 两种 reason——ask_user 的 toolArgs 经 prepare enrich 落 metadata.toolArgs
            # （{"questions": [...]}，镜像 approval）。WR-03 收紧匹配保持：必须中断且
            # toolCallId / id 与目标一致（不再把 toolCallId 为 None 的历史/脏数据记录
            # 视为恒匹配，避免取错 toolArgs 污染续流后的 LLM 上下文）。
            if intr.get("reason") not in (TOOL_APPROVAL_REASON, ASK_USER_QUESTION_REASON):
                continue
            if intr.get("toolCallId") != tool_call_id and intr.get("id") != tool_call_id:
                continue
            metadata = intr.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("toolArgs"), dict):
                return metadata["toolArgs"], metadata.get("toolName")
            if isinstance(intr.get("toolArgs"), dict):
                return intr["toolArgs"], None
        return None

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

    def update_flow_agent_info(self, task_id: int | str) -> None:
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
