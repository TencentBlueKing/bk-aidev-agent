# -*- coding: utf-8 -*-
"""BKAI 远程后端：通过 API 网关直调子智能体。

调用模式：
- execute(task): 带 session_code，一次性任务模式
- execute(member): 带 session_code，多轮会话模式

execute() 统一处理 task 和 member 两种调用模式。

Client 注入设计：
- Client 在 spec 构造时创建并注入到 spec.params["client"]（由 ChatAgentBuilder.build_subagents 注入）
- BkAiBackend 从 spec.params["client"] 获取 Client，不负责构造
- 用户可注入自定义 client（其他 bkai 鉴权方式），无需修改 BkAiBackend

鉴权设计：
- Client 通过 X-Bkapi-Authorization header 携带用户态 access_token
- 鉴权由 Client 构造方在创建时统一注入
- BkAiBackend 无需手动设置鉴权 header
"""

from __future__ import annotations

import uuid
from logging import getLogger
from typing import Any

from aidev_agent.api.bk_agent import Client as BkAgentApiClient
from aidev_agent.config import settings
from aidev_agent.core.tools.a2a_tools.types import AgentResult, AgentSpec, ExitReason
from aidev_agent.core.tools.a2a_tools.utils import (
    build_enriched_result,
    consume_sse_stream,
    extract_child_execute_kwargs,
)
from aidev_agent.pydantic_models import ExecuteKwargs

logger = getLogger(__name__)


class BkAiBackend:
    """BKAI 远程后端：通过 API 网关直调子智能体。

    通过 execute() 统一处理 task 和 member 两种调用模式（session_code 总是非空）。
    Phase 23: execute() 改为流式执行，收集 SSE 事件统计 api_calls。
    Phase 29: session_code 总是非空（由 provider 生成），移除所有 if session_code 条件分支；
    execute_kwargs 从 config.configurable.execute_kwargs 获取并修改关键字段。
    零参构造（D-07），运行时依赖通过 execute kwargs 注入（D-08）。
    Client 从 spec.params["client"] 获取，不负责构造，无 fallback。

    鉴权由 Client session 的 X-Bkapi-Authorization header 统一处理，
    BkAiBackend 无需手动设置鉴权相关 header。
    """

    def new_session(self, spec: AgentSpec, **kwargs: Any) -> str:
        """创建新会话，返回 uuid4 hex 字符串。"""
        return uuid.uuid4().hex

    def execute(
        self, spec: AgentSpec, message: str, *, session_code: str = "", config: Any = None, **kwargs: Any
    ) -> AgentResult:
        """通过流式请求调用子智能体（task / member 统一入口）。

        异常处理：本方法不捕获执行异常，任何 RuntimeError / HTTP 错误 / SSE
        error 事件直接向上抛出，由 ToolNode 的 ``default_tool_call_handler``
        统一转换为 error ToolMessage。本方法仅返回成功路径的 completed 结果。

        Args:
            spec: Agent 规格，params 中需包含 client
            message: 发送给子 Agent 的消息
            session_code: 会话 code；必须非空
            config: RunnableConfig，从中获取 execute_kwargs 和 executor
            **kwargs: 运行时参数（``progress_callback`` / ``state`` 等）

        Returns:
            AgentResult 标准化富结果（不可变 Pydantic 模型，仅 completed）

        Raises:
            ValueError: session_code 为空或 client 缺失/类型不符时
            RuntimeError: SSE 流式过程中收到 type=="error" 事件
            Exception: HTTP 请求失败、网络异常等由 _run_subagent 抛出
        """
        # 1. session_code 必须非空
        if not session_code:
            raise ValueError("session_code must not be empty for BkAiBackend")

        # 2. 内联 _get_client 逻辑
        client = spec.params.get("client")
        if not client:
            raise ValueError(f"Missing 'client' in spec.params for agent {spec.name}")
        # 构造侧负责构造 Client, 并且构造时进行注入 token
        # 注入 token 为用户在当前应用的 access_token, 包含用户信息和当前Agent信息
        # 被调用侧网关将进行鉴权，判断是否用户有权限调用对应Agent
        # 当前 Agent 调用子Agent仅仅允许由上层注入，目前仅通过 bkai 平台配置可信任的Agent，bkai 不允许自动发现
        if not isinstance(client, BkAgentApiClient):
            raise ValueError(
                f"Invalid 'client' in spec.params for agent {spec.name}: "
                f"expected BkAgentApiClient, got {type(client).__name__}"
            )

        # 3. 从 config 获取 execute_kwargs 和 executor，构造子 Agent execute_kwargs
        caller_bk_app_code = spec.params.get("caller_bk_app_code", "")
        state = kwargs.get("state")
        child_execute_kwargs = extract_child_execute_kwargs(
            config, state=state, session_code=session_code, caller_bk_app_code=caller_bk_app_code
        )
        # 暂时关闭 bkai 下的 pv 能力，paas 支持以后再开启
        child_execute_kwargs.sandbox_pv_id = None

        # 4. 获取 executor（ExecuteKwargs 对象属性访问）
        executor = child_execute_kwargs.executor or ""

        # 5. 条件执行 _prepare_session
        should_prepare_session = spec.params.get("should_prepare_session", False)
        if should_prepare_session:
            self._prepare_session(client, session_code, f"sa-{session_code[:8]}", message, executor=executor)

        # 6. 获取 should_openapi_chat_completion
        should_openapi = spec.params.get("should_openapi_chat_completion", False)

        # 7. 流式执行 — 异常不在此捕获，由上层 ToolNode 的 default_tool_call_handler
        #    统一处理（转为 error ToolMessage）。本方法仅负责正常路径返回 completed 结果。
        progress_callback = kwargs.pop("progress_callback", None)
        result_text, events, tool_count = self._run_subagent(
            client,
            spec,
            message,
            session_code=session_code,
            execute_kwargs=child_execute_kwargs,
            should_openapi_chat_completion=should_openapi,
            progress_callback=progress_callback,
            **kwargs,
        )
        return build_enriched_result(
            status="completed",
            agent_name=spec.name,
            agent_type=spec.backend_type,
            summary=result_text,
            tool_calls=tool_count,
            exit_reason=ExitReason.COMPLETED.value,
        )

    def _prepare_session(
        self,
        client: Any,
        session_code: str,
        session_name: str,
        message: str,
        *,
        executor: str = "",
    ) -> None:
        """准备远端子智能体的 session：创建 session + 保存 user 消息。

        与 LocalBackend._prepare_session 类似，但通过远端 client API 操作（非 resource_manager）。
        BkAiBackend 不负责保存 assistant 消息（远端子 Agent 自行管理）。
        也不负责加载历史上下文（远端子 Agent 自行管理）。

        Args:
            client: 已构造好的 Client 实例（通过 spec.params["client"] 获取）
            session_code: 预生成的 session code（UUID hex）
            session_name: session 显示名称
            message: 用户输入消息
            executor: 执行人用户名
        """
        # 创建远端 session（幂等：若 session 已存在，后端返回 200）
        try:
            res = client.create_session(
                data={
                    "is_temporary": settings.BKAI_A2A_SESSION_TEMPORARY,
                    "session_code": session_code,
                    "session_name": session_name,
                },
                headers={"X-BKAIDEV-USER": executor},
            )
            logger.info("BkAiBackend _prepare_session create_session success: %s", res)
        except Exception as exc:
            logger.warning("BkAiBackend _prepare_session create_session failed: %s", exc, exc_info=True)

        # 保存 user 消息到远端 session_content
        try:
            client.save_session_content(data={"session_code": session_code, "role": "user", "content": message})
        except Exception as exc:
            logger.warning("BkAiBackend _prepare_session save_session_content failed: %s", exc, exc_info=True)

    # ---------- 内部方法 ----------
    @staticmethod
    def _get_verify_ssl() -> bool:
        """根据运行环境决定是否验证 SSL 证书（D-01/D-02）。

        读取 ``settings.BKPAAS_ENVIRONMENT``，当值为 dev/development 时返回 False（内网开发环境），
        其他值返回 True（生产/staging 环境，安全优先）。

        Returns:
            True 表示验证 SSL 证书，False 表示跳过验证
        """
        return settings.BKPAAS_ENVIRONMENT.lower() not in {"dev", "development"}

    def _run_subagent(
        self,
        client: Any,
        spec: AgentSpec,
        message: str,
        *,
        session_code: str = "",
        execute_kwargs: ExecuteKwargs,
        should_openapi_chat_completion: bool = False,
        progress_callback: Any = None,
        **kwargs: Any,
    ) -> tuple[str, list[dict[str, Any]], int]:
        """通过 Client 的 API 操作发送流式请求并收集结果。

        优先使用 operation.request 方法发送流式请求，返回 requests.Response 后
        迭代 SSE 事件。根据 should_openapi_chat_completion 选择 private 或 openapi 端点。

        本方法负责：
        - 构造 payload 并发起 HTTP 流式请求
        - 管理 resp 生命周期（try/finally close）
        - 委托 ``consume_sse_stream`` 完成 SSE 解析/事件累积/心跳/error raise/tool_count 递增

        与 ``LocalBackend._run_subagent`` 同名同职责（流式执行子 Agent 并收集结果），
        差异在于本方法通过远端 HTTP client 获取流，Local 通过本地 subagent.execute 获取流。

        Args:
            client: 已构造好的 Client 实例
            spec: Agent 规格
            message: 发送给子 Agent 的消息
            session_code: 会话 code
            execute_kwargs: 已构造的 ExecuteKwargs 对象（由 execute 传入），
                本方法在构造 HTTP payload 时调 ``model_dump()`` 序列化为 dict
            should_openapi_chat_completion: 使用 openapi 端点
            progress_callback: 可选，用于发送 subagent.heartbeat 事件
            **kwargs: 运行时依赖

        Returns:
            ``(result_text, events, tool_count)``：拼接的文本结果、完整事件列表、
            TOOL_CALL_START 事件累计次数
        """
        payload: dict[str, Any] = {
            "input": message,
            "execute_kwargs": execute_kwargs.model_dump(),
            "session_code": session_code,
            "session_temporary": settings.BKAI_A2A_SESSION_TEMPORARY,
        }

        # 根据 should_openapi_chat_completion 选择对应的 Operation
        chat_op = client.openapi_chat_completion if should_openapi_chat_completion else client.private_chat_completion

        resp = chat_op.request(
            json=payload,
            timeout=spec.timeout_seconds,
            verify=self._get_verify_ssl(),
            stream=True,
        )
        resp.raise_for_status()

        # 流式循环（解析/累积/心跳/error raise）委托给 consume_sse_stream 公共函数，
        # 与 LocalBackend._run_subagent 共用同一套逻辑。emit_elapsed=True 保留
        # elapsed_seconds 字段供远程路径做超时监控。resp 生命周期由本方法管理。
        try:
            return consume_sse_stream(
                resp.iter_lines(decode_unicode=False),
                progress_callback=progress_callback,
                emit_elapsed=True,
            )
        finally:
            resp.close()
