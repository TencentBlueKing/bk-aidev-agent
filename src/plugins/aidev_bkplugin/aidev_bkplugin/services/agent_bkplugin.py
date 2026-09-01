# -*- coding: utf-8 -*-
"""标准运维插件 Agent 编排。

公开用法::

    runner = build_bkplugin_runner(...)
    output  = runner.execute()  # 同步：返回 Chat / Flow 输出
    storage = runner.dispatch_async()  # 流式：投递 Celery 后返回 POLL storage

文件结构：
    1. 模块辅助函数（``resolve_executor_username`` 等）
    2. Runner 基类（``BkpluginAgentRunner``）与 Chat / Flow 两个子类
    3. 工厂函数（``build_bkplugin_runner``）
"""

from __future__ import annotations

import logging
import threading
import uuid
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentBuildType, AgentType, ChannelType, PromptRole, SessionsStatus
from aidev_agent.packages.resource_manager.agent import AgentResourceManager
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.common_agent import common_agent_factory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.messages_handler import RetryableHeartbeatTimeoutError
from aidev_agent.utils.local import request_local
from django.contrib.auth import get_user_model

from .agent_config import AgentConfigFetcher
from .agent_execution import AgentExecutor, build_execute_kwargs
from .agent_helpers import AgentHelper
from .agent_session import SessionManager
from ..enums import PluginPollTaskState
from ..views.base import PluginResourceManager

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. 模块辅助函数
# ---------------------------------------------------------------------------


def resolve_executor_username(executor: str | None) -> str | None:
    """从插件 ``context.data.executor`` 解析用户名。"""
    if not executor:
        return None
    user = get_user_model().objects.filter(username=executor).first()
    if not user:
        return None
    try:
        req = getattr(request_local, "request", None)
        if req is not None:
            req.user = user
    except Exception:
        logger.debug("skip request_local.user: no request context", exc_info=True)
    return user.username


def normalize_execute_kwargs(execute_kwargs: dict | None, *, session_code: str | None = None) -> dict:
    """归一化插件 execute_kwargs，补入 session_code 并修正字段类型。"""
    data = dict(execute_kwargs or {})
    if session_code:
        data["session_code"] = session_code
    if data.get("caller_bk_biz_id"):
        data["caller_bk_biz_id"] = int(data["caller_bk_biz_id"])
    return data


def prepend_role_prompts_to_chat_context(
    chat_context: list[dict],
    *,
    username: str | None = None,
    version: str | None = None,
) -> list[dict]:
    """将平台 role_prompts 前置到 chat 上下文（不入库，仅参与 Agent 执行）。"""
    role_contents = AgentConfigFetcher.get_role_info(username=username or "", version=version)
    if not role_contents:
        return list(chat_context)
    role_context = [{"role": each.role, "content": each.content} for each in role_contents]
    return role_context + list(chat_context)


def build_chat_agent_for_session(
    *,
    session_code: str,
    chat_context: list[dict],
    username: str | None,
    version: str | None = None,
    turn_id: str = "",
    channel_type: str | None = None,
):
    """构建带 AG-UI 回写器的 Chat Agent 实例（供同步执行与 Celery worker 共用）。

    :param channel_type: 调用渠道类型（如 ``ChannelType.BKPLUGIN.value``），透传到 SDK 的
        ``TokenUsageCallbackHandler`` metadata，便于 token usage 上报落表时区分渠道。
    """
    user = username or ""
    event_handler = AGUISessionWriter(
        session_code=session_code,
        client=AgentHelper.get_client(),
        username=user,
        turn_id=turn_id,
    )
    resource_manager = AgentResourceManager(username=user) if user else None
    return AgentInstanceFactory.build_agent(
        build_type=AgentBuildType.DIRECT,
        session_code=session_code,
        session_context_data=chat_context,
        agent_cls=common_agent_factory.get(),
        checkpointer=AgentHelper.get_checkpointer(),
        event_handler=event_handler,
        resource_manager=resource_manager,
        username=user,
        version=version,
        channel_type=channel_type or ChannelType.BKPLUGIN.value,
    )


# ---------------------------------------------------------------------------
# 2. Runner 基类与 Chat / Flow 子类
# ---------------------------------------------------------------------------


class BkpluginAgentRunner(ABC):
    """单次插件调用的 Agent 编排基类。

    职责：
        - ``execute()``：同步运行并返回 Agent 输出；
        - ``dispatch_async()``：投递 Celery 后台任务，返回 POLL storage；
        - ``run_worker()``：Celery worker 入口（对应 ``dispatch_async()`` 投递的任务）；
        - ``invoke_agent()``：子类实现真正调用 Chat / Flow Agent 的逻辑。
    """

    agent_type: ClassVar[AgentType]

    def __init__(
        self,
        *,
        execute_kwargs: dict,
        input_text: str | None = None,
        username: str | None = None,
        plugin_context: list | None = None,
        parsed_ek: ExecuteKwargs | None = None,
    ):
        self.execute_kwargs = execute_kwargs
        self.input_text = input_text
        self.username = username
        self.plugin_context = plugin_context or []
        self._parsed_ek = parsed_ek or build_execute_kwargs(execute_kwargs, username)

    # ----- 公开接口 -----

    @property
    def session_code(self) -> str:
        """``execute()`` / ``dispatch_async()`` 调用后生效。"""
        return self._parsed_ek.session_code or ""

    @abstractmethod
    def _do_execute(self) -> str:
        """子类实现：实际同步执行 Agent。"""

    @abstractmethod
    def _do_dispatch_async(self) -> dict:
        """子类实现：实际投递 Celery 任务。"""

    def execute(self) -> str:
        """同步执行 Agent，返回最终 AI 回复字符串；异常时写回失败状态 。"""
        try:
            return self._do_execute()
        except RetryableHeartbeatTimeoutError:
            logger.warning(
                "[Bkplugin] skip session terminal update for retryable consumer heartbeat timeout session_code=%s",
                self.session_code or "",
                exc_info=True,
            )
            raise
        except Exception as e:
            logger.exception("[Bkplugin] execute error: %s", e)
            session_code = self.session_code or ""
            if session_code:
                try:
                    SessionManager(self.username or "").save_stream_failure(
                        session_code,
                        f"Agent 执行异常: {e}",
                        turn_id=self._parsed_ek.turn_id or "",
                    )
                except Exception:
                    logger.exception("[Bkplugin] save_stream_failure also failed for session_code=%s", session_code)
            raise

    def dispatch_async(self) -> dict:
        """投递 Celery 后台任务并返回 POLL storage；投递失败时写回失败状态 。"""
        try:
            return self._do_dispatch_async()
        except Exception as e:
            logger.exception("[Bkplugin] dispatch_async failed: %s", e)
            session_code = self.session_code or ""
            if session_code:
                try:
                    SessionManager(self.username or "").save_stream_failure(
                        session_code,
                        f"后台任务投递失败: {e}",
                        turn_id=self._parsed_ek.turn_id or "",
                    )
                except Exception:
                    logger.exception("[Bkplugin] save_stream_failure also failed for session_code=%s", session_code)
            raise

    def run_worker(
        self,
        session_code: str,
        execute_payload: dict,
        *,
        chat_context: list[dict] | None = None,
    ) -> None:
        """Celery worker 入口：业务异常写失败；可重试消费异常保持 session 原状态。"""
        logger.info(
            "[Bkplugin] run_worker enter session_code=%s turn_id=%s thread=%s",
            session_code,
            execute_payload.get("turn_id") or "",
            threading.current_thread().name,
        )
        try:
            self.invoke_agent(session_code, execute_payload, chat_context=chat_context or [])
        except RetryableHeartbeatTimeoutError:
            logger.warning(
                "[Bkplugin] skip session terminal update for retryable consumer heartbeat timeout "
                "session_code=%s turn_id=%s",
                session_code,
                execute_payload.get("turn_id") or "",
                exc_info=True,
            )
        except Exception as e:
            logger.exception("[Bkplugin] worker error session_code=%s", session_code)
            manager = SessionManager(self.username or "")
            # 幂等保护：心跳超时误报时 producer 实际已完成（session=FINISHED），
            # 不应再覆盖为 FAILED。仅当 session 仍处于非终态时才写失败，
            # 避免覆盖已确定的终态（FINISHED/CANCELLED/FAILED）。
            try:
                current_status = str(manager.retrieve_session(session_code).get("status") or "")
            except Exception:
                logger.exception(
                    "[Bkplugin] retrieve_session failed before save_stream_failure session_code=%s",
                    session_code,
                )
                current_status = ""
            if current_status in (
                SessionsStatus.FINISHED.value,
                SessionsStatus.CANCELLED.value,
                SessionsStatus.FAILED.value,
            ):
                logger.warning(
                    "[Bkplugin] skip save_stream_failure: session already %s "
                    "(likely heartbeat-timeout false positive) session_code=%s exc=%r",
                    current_status,
                    session_code,
                    e,
                )
                return
            manager.save_stream_failure(
                session_code,
                f"Agent 执行异常: {e}",
                turn_id=execute_payload.get("turn_id") or "",
            )

    # ----- 子类实现 -----

    @abstractmethod
    def invoke_agent(
        self,
        session_code: str,
        execute_payload: dict,
        *,
        chat_context: list[dict] | None = None,
    ) -> None:
        """子类实现：实际调用 Chat / Flow Agent；Flow 忽略 chat_context。"""

    # ----- 编排 helpers -----

    def _prepare_execution_context(self) -> tuple[str, str, ExecuteKwargs, SessionManager]:
        """准备 SessionManager 与会话轮次上下文。"""
        ek = self._parsed_ek
        manager = SessionManager(self.username or "")
        thread_id = ek.session_code or str(uuid.uuid4())
        session_code, turn_id = manager.prepare_session_turn(
            thread_id,
            input_text=self.input_text or "",
            turn_id=ek.turn_id,
            channel_type=ChannelType.BKPLUGIN.value,
        )
        ek.session_code = session_code
        ek.turn_id = turn_id
        return session_code, turn_id, ek, manager

    def _merge_execute_payload(self, ek: ExecuteKwargs, turn_id: str, **extra: Any) -> dict:
        """合并插件原始 execute_kwargs 与本轮 execute 字段，供 Celery 或 Flow 启动使用。"""
        return {**self.execute_kwargs, **ek.model_dump(exclude_none=True), "turn_id": turn_id, **extra}

    def _enqueue_background(
        self,
        session_code: str,
        turn_id: str,
        execute_payload: dict,
        *,
        chat_context: list[dict] | None = None,
    ) -> dict:
        """投递 Celery 并返回 POLL storage。"""
        from ..tasks import run_bkplugin_background_agent_task

        execute_payload["stream"] = True
        run_bkplugin_background_agent_task.delay(
            session_code=session_code,
            execute_payload=execute_payload,
            username=self.username,
            agent_type_value=self.agent_type.value,
            chat_context=chat_context or [],
        )
        return {
            "session_code": session_code,
            "turn_id": turn_id,
            "plugin_username": self.username or "",
            "agent_type": self.agent_type.value,
        }


class BkpluginChat(BkpluginAgentRunner):
    agent_type = AgentType.CHAT

    def __init__(self, *, chat_history: list[dict], **kwargs):
        super().__init__(**kwargs)
        self.chat_history = chat_history

    def _do_execute(self) -> str:
        session_code, turn_id, ek, manager = self._prepare_execution_context()
        ek.stream = False
        agent_instance = build_chat_agent_for_session(
            session_code=session_code,
            chat_context=self._build_chat_context(),
            username=self.username,
            version=ek.version,
            turn_id=turn_id,
            channel_type=ChannelType.BKPLUGIN.value,
        )
        result = AgentExecutor(manager).execute_with_save(agent_instance, ek, session_code, turn_id=turn_id)
        return self._extract_chat_output(result)

    @staticmethod
    def _extract_chat_output(result: Any) -> str:
        """从非流式 ``execute_with_save`` 结果中取 ``choices[0].delta.content``。"""
        if isinstance(result, str):
            return result
        if not isinstance(result, dict):
            return str(result or "")
        return result["choices"][0]["delta"]["content"]

    def _do_dispatch_async(self) -> dict:
        session_code, turn_id, ek, _ = self._prepare_execution_context()
        return self._enqueue_background(
            session_code,
            turn_id,
            self._merge_execute_payload(ek, turn_id),
            chat_context=self._build_chat_context(),
        )

    def invoke_agent(
        self,
        session_code: str,
        execute_payload: dict,
        *,
        chat_context: list[dict] | None = None,
    ) -> None:
        turn_id = execute_payload.get("turn_id") or ""
        manager = SessionManager(self.username or "")
        ek = build_execute_kwargs(execute_payload, self.username)
        agent = build_chat_agent_for_session(
            session_code=session_code,
            chat_context=chat_context or [],
            username=self.username,
            version=ek.version,
            turn_id=turn_id,
            channel_type=ChannelType.BKPLUGIN.value,
        )
        AgentExecutor.run_agent_to_completion(agent, ek, session_code, manager, turn_id=turn_id)

    def _build_chat_context(self) -> list[dict]:
        context_data = [
            {"role": each["role"], "content": each["content"]}
            for each in (self.chat_history or [])
            if each.get("content")
        ]
        if self.input_text:
            last = context_data[-1] if context_data else None
            if not last or last.get("role") != PromptRole.USER.value or last.get("content") != self.input_text:
                context_data.append({"role": PromptRole.USER.value, "content": self.input_text})
        return prepend_role_prompts_to_chat_context(
            context_data,
            username=self.username,
            version=self._parsed_ek.version,
        )


class BkpluginFlow(BkpluginAgentRunner):
    agent_type = AgentType.FLOW

    def _do_execute(self) -> str:
        session_code, turn_id, execute_payload = self._prepare_flow_payload()
        execute_payload["stream"] = False
        self.invoke_agent(session_code, execute_payload, chat_context=[])
        state, detail = SessionManager(self.username or "").poll_task_state(session_code, turn_id=turn_id)
        if state == PluginPollTaskState.FAILED:
            raise ValueError(detail or "Agent 执行失败")
        return detail or ""

    def _do_dispatch_async(self) -> dict:
        session_code, turn_id, execute_payload = self._prepare_flow_payload()
        return self._enqueue_background(session_code, turn_id, execute_payload)

    def _prepare_flow_payload(self) -> tuple[str, str, dict]:
        session_code, turn_id, ek, _ = self._prepare_execution_context()
        execute_payload = self._merge_execute_payload(ek, turn_id, agent_type=self.agent_type.value)
        execute_payload["flow_start_params"] = self._build_flow_start_params(session_code)
        return session_code, turn_id, execute_payload

    def invoke_agent(
        self,
        session_code: str,
        execute_payload: dict,
        *,
        chat_context: list[dict] | None = None,
    ) -> None:
        user = self.username or ""
        params = dict(execute_payload.get("flow_start_params") or {})
        params["session_code"] = session_code
        params.setdefault("channel_type", ChannelType.BKPLUGIN.value)
        turn_id = execute_payload.get("turn_id") or ""
        handler = AGUISessionWriter(
            session_code=session_code,
            client=AgentHelper.get_client(),
            username=user,
            turn_id=turn_id,
        )
        agent = AgentInstanceFactory.build_agent(
            agent_type=AgentType.FLOW,
            build_type=AgentBuildType.DIRECT,
            session_code=session_code,
            session_context_data=[],
            event_handler=handler,
            username=user,
            flow_resource_manager=PluginResourceManager(username=user),
            task_id=params.get("task_id") or execute_payload.get("task_id"),
            flow_start_params=params,
            poll_interval=execute_payload.get("poll_interval") or agent_settings.FLOW_AGENT_POLL_INTERVAL,
            poll_timeout=execute_payload.get("poll_timeout") or agent_settings.FLOW_AGENT_POLL_TIMEOUT,
            channel_type=ChannelType.BKPLUGIN.value,
        )
        # Flow 始终走 AG-UI 事件流；构造带 stream=True 的 ek 以触发 writer 会话状态收尾
        ek = build_execute_kwargs({**execute_payload, "stream": True}, self.username)
        manager = SessionManager(user)
        AgentExecutor.run_agent_to_completion(agent, ek, session_code, manager, turn_id=turn_id)

    def _build_flow_start_params(self, session_code: str) -> dict:
        params: dict = {"session_code": session_code}
        if self.plugin_context:
            params["context"] = self.plugin_context
        flow_exec = {"executor": self._parsed_ek.executor}
        if self.execute_kwargs.get("timeout") is not None:
            flow_exec["timeout"] = self.execute_kwargs["timeout"]
        params["execute_kwargs"] = flow_exec
        return params


# ---------------------------------------------------------------------------
# 3. 工厂
# ---------------------------------------------------------------------------


def build_bkplugin_runner(
    *,
    chat_history: list[dict] | None = None,
    execute_kwargs: dict,
    input_text: str | None = None,
    username: str | None = None,
    plugin_context: list | None = None,
    agent_type: AgentType | None = None,
) -> BkpluginAgentRunner:
    """构造 Chat / Flow 执行器。

    :param agent_type: 显式指定时跳过主站查询（Celery worker 重建 runner 走这条路径）；
                       不传时按主站 Agent 配置决定。
    """
    parsed_ek = build_execute_kwargs(execute_kwargs, username)
    if agent_type is None:
        agent_config = AgentConfigFetcher.get_info(username=username or "", version=parsed_ek.version)
        try:
            agent_type = AgentType(agent_config.get("agent_type") or AgentType.CHAT.value)
        except ValueError:
            agent_type = AgentType.CHAT

    runner_kwargs = dict(
        execute_kwargs=execute_kwargs,
        input_text=input_text,
        username=username,
        plugin_context=plugin_context,
        parsed_ek=parsed_ek,
    )
    if agent_type is AgentType.FLOW:
        return BkpluginFlow(**runner_kwargs)
    return BkpluginChat(chat_history=chat_history or [], **runner_kwargs)


# ---------------------------------------------------------------------------
# 4. 插件框架适配（鸭子类型，避免反向依赖 ``bk_plugin_framework``）
# ---------------------------------------------------------------------------


def build_bkplugin_runner_from_plugin(inputs: Any, context: Any) -> BkpluginAgentRunner:
    """从插件 ``inputs`` / ``context`` 构造 runner。

    使用鸭子类型，仅访问以下属性：
        - ``inputs.{input, chat_history, context, session_code, execute_kwargs}``
        - ``context.data.executor``
    """
    executor = getattr(getattr(context, "data", None), "executor", None)
    username = resolve_executor_username(executor)
    execute_kwargs = normalize_execute_kwargs(
        getattr(inputs, "execute_kwargs", None),
        session_code=getattr(inputs, "session_code", None),
    )
    return build_bkplugin_runner(
        chat_history=getattr(inputs, "chat_history", None) or [],
        execute_kwargs=execute_kwargs,
        input_text=getattr(inputs, "input", None) or "",
        username=username,
        plugin_context=getattr(inputs, "context", None) or [],
    )


def poll_bkplugin_agent(storage: dict) -> tuple[PluginPollTaskState, str, AgentType]:
    """SSE 2.0 轮询：用 ``dispatch_async()`` 返回的 storage 反查 session 状态。

    后台任务在 ``dispatch_async()`` 时已启动，这里只查询主站。
    """
    session_code = storage.get("session_code") or ""
    if not session_code:
        raise ValueError("poll 缺少 session_code")

    username = storage.get("plugin_username") or None
    try:
        agent_type = AgentType(storage.get("agent_type") or AgentType.CHAT.value)
    except ValueError:
        agent_type = AgentType.CHAT

    state, detail = SessionManager(username or "").poll_task_state(
        session_code,
        turn_id=storage.get("turn_id") or "",
    )
    return state, detail, agent_type


def record_plugin_poll_failure(storage: dict, error_message: str) -> None:
    """SSE 2.0 轮询失败时与后台异常一致：写 error content 并标记 session failed。"""
    session_code = storage.get("session_code") or ""
    if not session_code:
        return
    SessionManager(storage.get("plugin_username") or "").save_stream_failure(
        session_code,
        error_message,
        turn_id=storage.get("turn_id") or "",
    )
