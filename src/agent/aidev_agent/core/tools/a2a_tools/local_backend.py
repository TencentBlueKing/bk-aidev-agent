# -*- coding: utf-8 -*-
from __future__ import annotations

import dataclasses
import uuid
from logging import getLogger
from typing import Any

from aidev_agent.config import settings
from aidev_agent.core.tools.a2a_tools.types import AgentResult, AgentSpec, ExitReason
from aidev_agent.core.tools.a2a_tools.utils import (
    build_enriched_result,
    consume_sse_stream,
    extract_child_execute_kwargs,
)
from aidev_agent.enums import SessionsStatus

logger = getLogger(__name__)

_ERR_MISSING_AGENT_INSTANCE = "Missing agent_cls in spec.params"
_ERR_MISSING_CTX = "Missing ctx in spec.params"
_ERR_EMPTY_SESSION_CODE = "session_code must not be empty for LocalBackend"
_ERR_EMPTY_RESOURCE_MANAGER = "ctx.resource_manager must not be empty for LocalBackend"


class LocalBackend:
    """Local 本地后端：基于 ``agent_cls + ctx`` 构建并同步执行子 Agent。

    需要的 ``spec.params``：

    - ``agent_cls``：Agent 类（如 ``ChatCompletionAgent``），由
      ``ChatAgentBuilder.build_subagents`` 在构造 ``AgentSpec`` 时填充。
      LocalBackend 在运行时通过 ``agent_cls()`` 创建实例再 ``build(ctx)``。
    - ``ctx``：``AgentBuildContext``，用于装配子 Agent。

    运行时 kwargs：

    - ``config``：父 Agent 的 ``RunnableConfig``，从中获取 ``execute_kwargs`` 和 ``executor``。
    - ``session_code``：会话标识；必须非空（由调用方 Task/Member 保证）。
    """

    def new_session(self, spec: AgentSpec, **kwargs: Any) -> str:
        """创建新会话，返回 uuid4 hex 字符串。"""
        return uuid.uuid4().hex

    def execute(
        self, spec: AgentSpec, message: str, *, session_code: str = "", config: Any = None, **kwargs: Any
    ) -> AgentResult:
        """执行子 Agent 调用（统一入口 + 可观测性）。

        执行流程：
        1. 校验 session_code / agent_cls / ctx / rm 必须存在
        2. 从 config 获取 execute_kwargs 和 executor，构造子 Agent execute_kwargs
        3. 准备平台 session（创建、保存用户输入、加载历史）
        4. 更新 event_handler 的 session_code
        5. 注入 session_code + session_context_data 到 ctx
        6. 实例化 agent_cls 并 build 子 Agent（历史消息由 build 内部管道处理）
        7. 执行子 Agent
        8. 更新 session 状态为 FINISHED

        Args:
            spec: Agent 规格，``params`` 必须含 ``agent_cls`` / ``ctx``
            message: 发给子 Agent 的消息文本
            session_code: 会话标识；必须非空（由调用方 Task/Member 保证）
            config: RunnableConfig，从中获取 execute_kwargs 和 executor
            **kwargs: 运行时参数（``progress_callback`` 等）

        Returns:
            AgentResult 标准化富结果（不可变 Pydantic 模型）
        """
        # 1. session_code 必须非空
        if not session_code:
            raise ValueError(_ERR_EMPTY_SESSION_CODE)

        # 2. 从 spec.params 获取 agent_cls、ctx
        # 通过 agent_cls 和 ctx 构造子 Agent, 子Agent和父Agent运行在同一个环境中
        # 由SDK开发者注入 agent_cls, 并且保证 agent_cls 的安全性，本处不做约束
        # checkpointer 和父Agent共享，默认使用 django orm 持久化到数据库中
        # 对话列表除了持久化到数据库，同时还通过 rm 回写平台或者文件，使用 session_code 区分不同会话
        agent_cls = spec.params.get("agent_cls")
        if agent_cls is None:
            raise ValueError(_ERR_MISSING_AGENT_INSTANCE)
        ctx = spec.params.get("ctx")
        if ctx is None:
            raise ValueError(_ERR_MISSING_CTX)
        rm = getattr(ctx, "resource_manager", None)
        if not rm:
            raise ValueError(_ERR_EMPTY_RESOURCE_MANAGER)

        # 3. 从 config 获取 execute_kwargs 和 executor，构造子 Agent execute_kwargs
        # executor 从构造好的 ExecuteKwargs 取（与 BkAiBackend 一致；由 model_copy() 继承自父 ek）
        # invoke_timeout 由 spec.timeout_seconds 注入（BkAiBackend 不传，超时由 HTTP 层控制）
        # caller_bk_app_code 从 spec.params 取（与 BkAiBackend 一致；provider 不通过 kwargs 传该字段）
        caller_bk_app_code = spec.params.get("caller_bk_app_code", "")
        state = kwargs.get("state")
        child_execute_kwargs = extract_child_execute_kwargs(
            config,
            state=state,
            session_code=session_code,
            caller_bk_app_code=caller_bk_app_code,
            invoke_timeout=spec.timeout_seconds,
        )
        executor = child_execute_kwargs.executor or ""

        # 4. 准备性工作，从 BkAi 平台获取对话历史
        # 步骤 4-7 都会修改平台 session 状态（_prepare_session 内部置 RUNNING），
        # 任一步失败必须由下方 try 的 except 分支兜底为 FAILED，否则 session 残留 RUNNING
        try:
            session_context_data = self._prepare_session(rm, spec.name, session_code, message, executor)
            progress_callback = kwargs.get("progress_callback")

            # 5. 更新 event_handler session_code（AGUISessionWriter 由 ChatAgentBuilder 构造）
            event_handler = getattr(ctx, "event_handler", None)
            if event_handler:
                event_handler.session_code = session_code

            # 6. 注入 session_code + session_context_data 到 ctx
            ctx = dataclasses.replace(ctx, session_code=session_code, session_context_data=session_context_data)

            # 7. 实例化 agent_cls 并 build（历史消息由 build 内部管道处理）
            agent_instance = agent_cls()
            subagent = agent_instance.build(ctx)
            # 8. 执行子 Agent
            result_text, events, tool_count = self._run_subagent(
                subagent,
                execute_kwargs=child_execute_kwargs,
                progress_callback=progress_callback,
            )

            # 10. 更新 session 状态为 FINISHED
            try:
                rm.update_session_status(session_code, SessionsStatus.FINISHED.value)
            except Exception as exc:
                logger.warning("LocalBackend update session status to FINISHED failed: %s", exc, exc_info=True)

            return build_enriched_result(
                status="completed",
                agent_name=spec.name,
                agent_type=spec.backend_type,
                summary=result_text,
                tool_calls=tool_count,
                exit_reason=ExitReason.COMPLETED.value,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("LocalBackend.execute failed for %s: %s", spec.name, exc)
            try:
                rm.update_session_status(session_code, SessionsStatus.FAILED.value)
            except Exception:
                logger.warning("LocalBackend update session status to FAILED failed: %s", session_code)
            raise

    # ==================== 内部方法 ====================
    def _prepare_session(
        self, resource_manager: Any, agent_name: str, session_code: str, message: str, executor: str
    ) -> list[dict]:
        """准备平台 session：创建、保存用户输入、加载历史。

        执行流程：
        1. 通过 resource_manager 创建/获取平台 Session（幂等）
        2. 设置 session 状态为 RUNNING
        3. 保存用户输入到 session_content
        4. 从平台加载历史会话上下文（包含刚写入的用户消息），过滤 system 角色

        返回的平台原始上下文列表（``session_context_data``）将通过
        ``ctx.session_context_data`` 传入 ``ChatCompletionAgent.build(ctx)``，
        复用 ``ChatAgentBuilder.build_chat_history`` → ``convert_chat_history_to_messages``
        管道完成转换，无需在本层重复实现。

        Args:
            resource_manager: resource_manager 实例
            agent_name: Agent 名称
            session_code: 会话标识
            message: 用户输入消息
            executor: 执行人用户名

        Returns:
            session_context_data 列表
        """
        session_context_data: list[dict] = []

        headers = {"X-BKAIDEV-USER": executor}
        session_type = "dev" if settings.BKPAAS_ENVIRONMENT.lower() in {"dev", "development"} else "agent"
        resource_manager.get_or_create_session(
            session_code=session_code,
            session_name=f"local-{agent_name}-session",
            protocol_version="v2",
            is_temporary=settings.BKAI_A2A_SESSION_TEMPORARY,
            session_type=session_type,
            headers=headers,
        )
        resource_manager.update_session_status(session_code, SessionsStatus.RUNNING.value)

        resource_manager.save_session_content(
            session_code=session_code,
            role="user",
            content=message,
        )

        context = resource_manager.get_chat_session_context(session_code) or []
        session_context_data = [each for each in context if each.get("role", "") != "system"]

        return session_context_data

    def _run_subagent(
        self,
        subagent: Any,
        *,
        execute_kwargs: Any,
        progress_callback: Any = None,
    ) -> tuple[str, list[dict[str, Any]], int]:
        """流式执行子 Agent，收集文本结果、事件列表和工具调用次数。

        execute_kwargs 由 execute() 中 extract_child_execute_kwargs 处理好传入，
        已包含 stream=True、persist_input=True、session_code、invoke_timeout 等字段。
        本方法不再修改 execute_kwargs，仅负责执行和事件收集。

        流式循环（解析/累积/心跳/error raise/tool_count 递增）委托给
        ``consume_sse_stream`` 公共函数，与 BkAiBackend 共用同一套逻辑。本方法
        仅负责：
        - 调用 ``subagent.execute`` 拿到流式结果
        - 非流式返回的兜底（兼容 mock 返回 dict / str 的场景，tool_count=0）

        异常处理：本方法不捕获异常（含 consume_sse_stream 抛出的 error 事件
        RuntimeError），直接向上抛出，由 execute() 的统一 except 处理。

        Args:
            subagent: 已 build 的子 Agent（messages 已含当前用户消息）
            execute_kwargs: 由 execute() 处理好的 ExecuteKwargs
            progress_callback: 心跳回调

        Returns:
            ``(result_text, events_list, tool_count)``：文本、事件列表、
            TOOL_CALL_START 事件累计次数
        """
        result = subagent.execute(execute_kwargs)

        # 兼容非流式返回（mock 可能返回 dict），无事件可统计 → tool_count=0
        if not hasattr(result, "__iter__") or isinstance(result, (dict, str)):
            return self._extract_text(result), [], 0

        return consume_sse_stream(result, progress_callback=progress_callback, emit_elapsed=False)

    @staticmethod
    def _extract_text(result: Any) -> str:
        """从 ``subagent.execute`` 的非流式返回中提取文本。

        非流式返回格式（见 ``ChatCompletionAgent._execute`` chat.py:168-175）：
        ``{"choices": [{"delta": {"role": "assistant", "content": <text>}}], ...}``

        兼容 ``str`` 返回（旧协议）和未识别格式（返回空字符串）。

        Args:
            result: ``subagent.execute`` 的返回值

        Returns:
            提取出的文本，无法识别时返回空字符串
        """
        if isinstance(result, dict):
            choices = result.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if isinstance(content, str):
                    return content
        if isinstance(result, str):
            return result
        return ""
