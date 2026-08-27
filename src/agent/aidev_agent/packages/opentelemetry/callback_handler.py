# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import logging
import threading
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

import orjson
import pytz
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, set_span_in_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from aidev_agent.pydantic_models import ExecuteKwargs

from .metrics import AgentMetrics, get_agent_metrics
from .metrics import extract_token_usage as extract_metric_token_usage
from .span_utils import (
    SpanHolder,
    set_chat_request,
    set_chat_response,
    set_llm_request,
)
from .utils import (
    _safe_attach_context,
    _safe_detach_context,
    _set_span_attribute,
    dont_throw,
    extract_token_usage,
)

logger = logging.getLogger(__name__)
TIMEZONE = "Asia/Shanghai"
try:
    AGENT_SDK_VERSION = version("aidev_agent")
except PackageNotFoundError:
    try:
        AGENT_SDK_VERSION = version("bkaidev_agent_framework")
    except PackageNotFoundError:
        AGENT_SDK_VERSION = "unknown"
except Exception as e:  # noqa: BLE001
    logger.warning(f"Failed to get aidev_agent version: {e}")
    AGENT_SDK_VERSION = "unknown"


class BkAidevAgentInjector:
    """
    BkAidevAgent 启动的时候注入，用于标记本次请求的基本信息
    基本信息包含：
    1. agent.info.*：智能体的基本信息
    2. agent.session.*：本次 session 的单轮对话的基本信息
    """

    def __init__(
        self,
        tracer: trace.Tracer,
        parent_trace_context: Optional[Dict[str, str]] = None,
        *,
        debug: bool = False,
    ):
        """
        初始化 Trace 收集器

        Args:
            tracer: OpenTelemetry Tracer 实例
            parent_trace_context: 父级 Trace Context (用于跨服务传播)
            debug: 是否为调试状态
        """
        super().__init__()
        self.tracer = tracer
        # Trace Context 传播
        self.parent_context = None
        self._setup_trace_context(parent_trace_context)
        # AiDev
        self.root_span = None
        self.debug = debug

    def _setup_trace_context(self, parent_trace_context):
        """
        设置 Trace Context

        如果有父级 Trace Context,则从中提取 trace_id 和 parent_span_id
        """
        if not parent_trace_context:
            return
        try:
            # 使用 W3C Trace Context 传播器解析上游 context
            propagator = TraceContextTextMapPropagator()
            self.parent_context = propagator.extract(carrier=parent_trace_context)
            logger.debug(f"Extracted parent trace context: {parent_trace_context}")
        except Exception as e:
            logger.warning(f"Failed to extract parent trace context: {e}")
            self.parent_context = None

    @dont_throw
    def on_bk_agent_start(
        self,
        inputs: Dict[str, Any],
        execute_kwargs: ExecuteKwargs = None,
        agent_info: Dict[str, Any] = None,
        **kwargs: Any,
    ) -> None:
        """蓝鲸 Agent 开始回调，作为整个 Agent 执行的入口

        这里负责创建根 Span（agent.execution），并上报会话级别和模型级别的关键信息。
        """
        # 时间信息（北京时间）
        now = datetime.now(pytz.timezone(TIMEZONE))
        start_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        start_time_unix_nano = int(now.timestamp() * 1_000_000_000)

        # Agent 配置信息
        agent_info = agent_info or {}
        agent_id = agent_info.get("agent_id", "unknown")
        agent_code = agent_info.get("agent_code", "unknown")
        agent_name = agent_info.get("agent_name", "unknown")
        agent_type = agent_info.get("agent_type", "unknown")
        agent_service_catalogue = agent_info.get("service_catalogue", "unknown")
        agent_updated_by = agent_info.get("updated_by", "unknown")
        # 服务入口级别的属性
        attributes = {
            "agent.info.id": agent_id,
            "agent.info.code": agent_code,
            "agent.info.name": agent_name,
            "agent.info.sdk_version": AGENT_SDK_VERSION,
            "agent.info.type": agent_type,
            "agent.info.service_catalogue": agent_service_catalogue,
            "agent.info.updated_by": agent_updated_by,
            "agent.info.agent_info": orjson.dumps(agent_info),
            "agent.session.session_code": execute_kwargs.session_code,
            "agent.session.executor": execute_kwargs.executor,
            "agent.session.input": str(inputs),
            "agent.session.start_time": start_time_str,
            "agent.session.start_time_unix_nano": start_time_unix_nano,
            "agent.session.caller_bk_app_code": execute_kwargs.caller_bk_app_code,
            "agent.session.caller_bk_biz_env": execute_kwargs.caller_bk_biz_env,
            "agent.session.caller_bk_biz_id": execute_kwargs.caller_bk_biz_id,
            "agent.session.caller_executor": execute_kwargs.caller_executor,
            "agent.session.caller_order_type": execute_kwargs.caller_order_type,
        }
        # 如果存在上游传播的 Trace Context，则使用它，否则使用当前 context
        ctx = self.parent_context if self.parent_context is not None else None

        if self.debug:
            attributes["debug.thread_id"] = threading.current_thread().name

        # 创建 Span
        self.root_span = self.tracer.start_span(
            name="agent.execution",
            context=ctx,
            kind=SpanKind.SERVER,
            attributes=attributes or {},
        )

        # 不在此处 attach root span 到全局 context
        # 原因：在流式场景下，on_bk_agent_start 和 on_bk_agent_end 可能在不同线程上执行
        # （HTTP 线程 vs producer 线程），ContextVar 是线程隔离的，跨线程 detach 无效
        # attach/detach 由调用方（instrumentor.py）在同一线程内完成

    @dont_throw
    def on_bk_agent_end(self, error: Optional[Exception] = None, **kwargs: Any) -> None:
        """蓝鲸 Agent 结束回调，作为整个 Agent 执行的出口

        正常结束时在这里补充最终统计信息并关闭根 Span。
        如果传入 error 参数，则标记为失败状态。

        Args:
            error: 可选的异常对象，如果传入则标记 Span 为错误状态
            **kwargs: 其他参数
        """
        # 结束时间（北京时间）
        now = datetime.now(pytz.timezone(TIMEZONE))
        end_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        end_time_unix_nano = int(now.timestamp() * 1_000_000_000)

        # 设置根 Span 的最终属性
        _set_span_attribute(self.root_span, "agent.end_time", end_time_str)
        _set_span_attribute(self.root_span, "agent.end_time_unix_nano", end_time_unix_nano)

        # debug 模式下记录结束线程名，便于排查跨线程结束 root span 的场景
        # （例如：start 在 HTTP 线程、end 由 LangChain callback 在 producer 线程触发）
        if self.debug:
            _set_span_attribute(self.root_span, "debug.end_thread_id", threading.current_thread().name)

        if error is not None:
            # 执行过程中发生异常，标记为失败
            _set_span_attribute(self.root_span, "agent.status", "failed")
            _set_span_attribute(self.root_span, "agent.error_message", str(error))
            self.root_span.set_status(Status(StatusCode.ERROR, str(error)))
            self.root_span.record_exception(error)
        else:
            # 正常结束，标记为成功
            _set_span_attribute(self.root_span, "agent.status", "completed")
            self.root_span.set_status(Status(StatusCode.OK))

        # 结束根 Span（detach 由 instrumentor.py 负责）
        self.root_span.end()


class BkAidevAgentCallbackHandler(AsyncCallbackHandler):
    """
    基于 LangChain 的 Callback 机制实现对于 BkAidevAgent 的相关信息统计
    """

    run_inline = True  # 确保 callback 在当前 context 中直接执行，而非通过 asyncio.gather/create_task
    # 这样 _safe_attach_context 修改的 ContextVar 对后续 node 执行可见

    def __init__(
        self,
        tracer: trace.Tracer,
        parent_trace_context: Optional[Dict[str, str]] = None,
        *,
        enabled: bool = True,
        enable_traces: bool = True,
        enable_metrics: bool = False,
        debug: bool = False,
        max_attribute_length: int = 4096,
        agent_id: Optional[str] = None,
        agent_code: Optional[str] = None,
        agent_name: Optional[str] = None,
        agent_sdk_version: Optional[str] = None,
        session_code: Optional[str] = None,
        caller_executor: Optional[str] = None,
        injector: Optional["BkAidevAgentInjector"] = None,
        start_inputs: Any = None,
        start_execute_kwargs: Optional[ExecuteKwargs] = None,
        start_agent_info: Optional[Dict[str, Any]] = None,
        metric_recorder: Optional[AgentMetrics] = None,
    ):
        """
        初始化 Trace 收集器

        Args:
            tracer: OpenTelemetry Tracer 实例
            parent_trace_context: 父级 Trace Context (用于跨服务传播)
            enabled: 是否启用追踪，默认 True
            enable_traces: 是否启用 traces，默认 True
            enable_metrics: 是否启用 metrics，默认 False
            debug: 是否为调试状态
            max_attribute_length: 属性值最大长度，默认 4096
            agent_id: agent.info.id
            agent_code: agent.info.code
            agent_name: agent.info.name
            agent_sdk_version: agent.info.sdk_version
            session_code: agent.session.session_code
            caller_executor: agent.session.caller_executor
            injector: 可选的 BkAidevAgentInjector 实例。本 handler 会在顶层 chain
                首次触发时调用 ``injector.on_bk_agent_start``，并在顶层 chain
                end/error 时调用 ``injector.on_bk_agent_end``，保证 root span 的
                完整生命周期都跟随真正执行 Agent 的线程（流式场景下为 producer 线程，
                非流式场景下为 HTTP 线程）。这样 HTTP 请求线程被 gunicorn kill 不会
                丢失 trace 上报，且 start/end 在同线程，避免跨线程 ContextVar 问题。
            start_inputs: 顶层 chain 首次触发时传给 ``injector.on_bk_agent_start``
                的 ``inputs`` 参数（通常是用户输入文本）。由 instrumentor 在 wrap
                ``_get_agent`` 时提取并快照，延迟到执行线程上的 start 时机使用。
            start_execute_kwargs: 同上，``ExecuteKwargs`` 快照。
            start_agent_info: 同上，``agent_info`` 字典快照（已剔除 ``otel_info``）。
        """
        super().__init__()

        self.tracer = tracer
        # 配置项
        self.enabled = enabled
        self.enable_traces = enable_traces
        self.enable_metrics = enable_metrics
        self.debug = debug
        self.max_attribute_length = max_attribute_length

        # Agent / Session 基础信息，会注入到所有 span 中
        self._agent_id = agent_id
        self._agent_code = agent_code
        self._agent_name = agent_name
        self._session_code = session_code
        self._caller_executor = caller_executor

        # Span 管理 - 使用 SpanHolder 管理完整的 Span 层级
        self._injector: Optional[BkAidevAgentInjector] = injector
        # injector 是否已被本 handler 触发过 start（幂等保护）
        self._injector_started: bool = False
        # 注入器侧 root span 是否已被本 handler 主动结束（幂等保护，避免重复 end）
        self._injector_ended: bool = False
        # 顶层 chain 首次触发时延迟调用 on_bk_agent_start 所需的入参快照
        self._start_inputs: Any = start_inputs
        self._start_execute_kwargs: Optional[ExecuteKwargs] = start_execute_kwargs
        self._start_agent_info: Optional[Dict[str, Any]] = start_agent_info
        # 顶层 chain start 时把 root span 重新 attach 为当前 active context 的 token；
        # 由 on_chain_end / on_chain_error 在顶层 detach。
        # 目的：让 LangchainInstrumentor 等"取当前 active ctx 作为父"的自动插桩
        # 把它们的顶层 span 直接挂在 root span 下，而不是被覆盖到 chain.workflow 之下。
        self._root_attach_token: Any = None
        self._root_run_id: Optional[UUID] = None  # 根 Span 的 run_id
        self.spans: Dict[UUID, SpanHolder] = {}  # 使用 UUID 管理所有 Span
        self._current_workflow_run_id: Optional[UUID] = None  # 当前顶层 workflow 链的 run_id，用于挂载自定义 span

        # 工具调用计数器
        self.tool_call_counter = 0
        self.rag_call_counter = 0
        self.agent_iteration_counter = 0

        # Metric state uses monotonic clocks and contains no session/user data.
        self._metrics = metric_recorder or (get_agent_metrics() if enable_metrics else None)
        self._metric_agent_attributes = AgentMetrics.agent_attributes(agent_code, agent_name, agent_sdk_version)
        self._agent_started_at: float | None = None
        self._llm_started_at: Dict[UUID, float] = {}
        self._llm_active_attributes: Dict[UUID, Dict[str, str]] = {}
        self._llm_first_chunk_seen: set[UUID] = set()
        self._tool_started_at: Dict[UUID, float] = {}
        self._tool_metric_attributes: Dict[UUID, Dict[str, str]] = {}
        self._active_llm_operation_count = 0
        self._active_tool_operation_count = 0
        self._agent_phase: str | None = None
        self._agent_phase_started_at: float | None = None
        self._agent_first_token_seen = False

        # Token 用量累加计数器（一个 handler 生命周期 = 一轮 Agent 执行，与 root span 对齐）
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._total_total_tokens = 0

        # Trace Context 传播
        self.parent_trace_context = parent_trace_context
        self.parent_context = None
        self._setup_trace_context()

    @property
    def root_span(self) -> Optional[Span]:
        """兼容旧引用：root_span 实际由持有的 injector 管理。

        若未注入 injector（独立使用 handler 的场景），返回 None；同时保留
        setter 行为以兼容 ``self.root_span = None`` 的清理写法。
        """
        return self._injector.root_span if self._injector else None

    @root_span.setter
    def root_span(self, value: Optional[Span]) -> None:
        if self._injector is not None:
            self._injector.root_span = value

    def _finalize_injector(self, error: Optional[Exception] = None) -> None:
        """结束 injector 的 root span（幂等）。

        通常在以下时机调用：
        - 顶层 chain 正常结束（``on_chain_end``）
        - 顶层 chain 异常结束（``on_chain_error``）
        - 顶层 chain 因流式上游关闭而抛 GeneratorExit（视为正常结束）
        """
        if self._injector_ended:
            return
        self._transition_agent_phase("finalizing")
        self._finish_active_metric_operations()
        try:
            if self._injector is not None:
                self._injector.on_bk_agent_end(error=error)
        finally:
            try:
                if self._metrics is not None and self._agent_started_at is not None:
                    started_at = self._agent_started_at
                    self._agent_started_at = None
                    try:
                        self._metrics.record_agent(
                            duration=time.monotonic() - started_at,
                            iteration_count=self.agent_iteration_counter,
                            attributes=self._metric_agent_attributes,
                            error=error,
                        )
                    finally:
                        try:
                            self._finish_agent_phase()
                        finally:
                            self._metrics.record_active_agent(-1, self._metric_agent_attributes)
            finally:
                self._injector_ended = True

    def _operation_phase(self) -> str:
        if self._active_llm_operation_count and self._active_tool_operation_count:
            return "mixed"
        if self._active_tool_operation_count:
            return "tool"
        if self._active_llm_operation_count:
            return "llm"
        return "processing"

    def _transition_agent_phase(self, phase: str, *, now: float | None = None) -> None:
        if self._metrics is None or self._agent_started_at is None or self._agent_phase == phase:
            return
        transitioned_at = now if now is not None else time.monotonic()
        previous_phase = self._agent_phase
        previous_started_at = self._agent_phase_started_at
        self._agent_phase = phase
        self._agent_phase_started_at = transitioned_at
        if previous_phase is not None and previous_started_at is not None:
            self._metrics.record_agent_phase_duration(
                max(0, transitioned_at - previous_started_at),
                previous_phase,
                self._metric_agent_attributes,
            )
            self._metrics.record_agent_phase_active(-1, previous_phase, self._metric_agent_attributes)
        self._metrics.record_agent_phase_active(1, phase, self._metric_agent_attributes)

    def _finish_agent_phase(self) -> None:
        if self._metrics is None or self._agent_phase is None:
            return
        finished_at = time.monotonic()
        phase = self._agent_phase
        phase_started_at = self._agent_phase_started_at
        self._agent_phase = None
        self._agent_phase_started_at = None
        if phase_started_at is not None:
            self._metrics.record_agent_phase_duration(
                max(0, finished_at - phase_started_at),
                phase,
                self._metric_agent_attributes,
            )
        self._metrics.record_agent_phase_active(-1, phase, self._metric_agent_attributes)

    def _finish_active_metric_operations(self) -> None:
        """Balance active operation gauges when a child callback never reaches its terminal hook."""
        if self._metrics is None:
            return
        for attributes in self._llm_active_attributes.values():
            self._metrics.record_active_llm(-1, attributes)
        for attributes in self._tool_metric_attributes.values():
            self._metrics.record_active_tool(-1, attributes)
        self._llm_active_attributes.clear()
        self._tool_metric_attributes.clear()
        self._llm_started_at.clear()
        self._tool_started_at.clear()
        self._llm_first_chunk_seen.clear()
        self._active_llm_operation_count = 0
        self._active_tool_operation_count = 0

    def _llm_metric_attributes(self, run_id: UUID, response_model: str | None = None) -> Dict[str, str]:
        attrs = dict(self._metric_agent_attributes)
        holder = self.spans.get(run_id)
        request_model = getattr(holder, "request_model", None) if holder is not None else None
        attrs["gen_ai.request.model"] = str(request_model or "unknown")
        attrs["gen_ai.response.model"] = str(response_model or request_model or "unknown")
        return attrs

    def _detach_root_attach_token(self) -> None:
        """detach 顶层 chain start 时为对外可见的 active context attach 的 root span token。

        必须在结束 chain span（``_end_span``，其内部会 detach chain 自己的 token）**之前**
        调用，以满足 OTel context 栈式 attach 的 LIFO 顺序约束。幂等。
        """
        if self._root_attach_token is None:
            return
        try:
            _safe_detach_context(self._root_attach_token)
        except Exception:  # noqa: BLE001
            logger.debug("Failed to detach root attach token", exc_info=True)
        finally:
            self._root_attach_token = None

    def _setup_trace_context(self):
        """
        设置 Trace Context

        如果有父级 Trace Context,则从中提取 trace_id 和 parent_span_id
        """
        if not self.parent_trace_context:
            return

        try:
            # 使用 W3C Trace Context 传播器解析上游 context
            propagator = TraceContextTextMapPropagator()
            self.parent_context = propagator.extract(carrier=self.parent_trace_context)
            logger.debug(f"Extracted parent trace context: {self.parent_trace_context}")
        except Exception as e:
            logger.warning(f"Failed to extract parent trace context: {e}")
            self.parent_context = None

    @staticmethod
    def _get_name_from_callback(
        serialized: dict[str, Any],
        _tags: Optional[list[str]] = None,
        _metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """Get the name to be used for the span. Based on heuristic. Can be extended."""
        if serialized and "kwargs" in serialized and serialized["kwargs"].get("name"):
            return serialized["kwargs"]["name"]
        if kwargs.get("name"):
            return kwargs["name"]
        if serialized.get("name"):
            return serialized["name"]
        if "id" in serialized:
            return serialized["id"][-1]

        return "unknown"

    def _get_span(self, run_id: UUID) -> Optional[Span]:
        return self.spans[run_id].span

    def _create_span(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID],
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        entity_name: str = "",
        entity_path: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> Span:
        """
        统一的 Span 创建方法，支持完整的层级管理

        Args:
            run_id: LangChain 回调的 run_id
            parent_run_id: 父级 run_id
            name: Span 名称
            kind: Span 类型
            attributes: Span 属性
            entity_name: 实体名称
            entity_path: 实体路径

        Returns:
            创建的 Span
        """
        # 确定父级 Context
        if parent_run_id and parent_run_id in self.spans:
            # 有父 Span，使用父 Span 的 context
            ctx = set_span_in_context(self.spans[parent_run_id].span)
        elif self._injector is not None and self._injector.root_span is not None:
            # 顶层 span（无 LangChain 父 run_id）：优先以本服务的 root span 作为父，
            # 让 chain.workflow 等顶层 span 直接挂在 ``agent.execution`` 下。
            # 注：injector.root_span 在 on_chain_start 顶层路径里已被本 handler 创建。
            ctx = set_span_in_context(self._injector.root_span)
        elif self.parent_context is not None:
            # 没有 root span（独立使用 handler 的场景），但存在上游传播的 Trace Context
            ctx = self.parent_context
        else:
            # 都没有，使用当前 context
            ctx = None

        attributes = attributes or {}
        if self.debug:
            attributes["debug.thread_id"] = threading.current_thread().name

        # 注入 Agent / Session 基础信息到所有 span
        if self._agent_id is not None:
            attributes["agent.info.id"] = self._agent_id
        if self._agent_code is not None:
            attributes["agent.info.code"] = self._agent_code
        if self._agent_name is not None:
            attributes["agent.info.name"] = self._agent_name
        if self._session_code is not None:
            attributes["agent.session.session_code"] = self._session_code
        if self._caller_executor is not None:
            attributes["agent.session.caller_executor"] = self._caller_executor

        # 创建 Span
        span = self.tracer.start_span(
            name=name,
            context=ctx,
            kind=kind,
            attributes=attributes or {},
        )

        # 安全地附加到 context
        token = _safe_attach_context(span)
        _set_span_attribute(span, "entity.path", entity_path)

        # 创建 SpanHolder
        self.spans[run_id] = SpanHolder(
            span=span,
            token=token,
            context=None,
            children=[],
            entity_name=entity_name,
            entity_path=entity_path,
            start_time=time.time(),
        )

        # 记录父子关系
        if parent_run_id and parent_run_id in self.spans:
            self.spans[parent_run_id].children.append(run_id)

        return span

    def _end_span(self, span: Span, run_id: UUID) -> None:
        """
        统一的 Span 结束方法

        Args:
            run_id: 要结束的 Span 的 run_id
        """
        # 关闭所有 child 的 span，并 detach 它们的 context token
        for child_id in self.spans[run_id].children:
            if child_id in self.spans:
                child_holder = self.spans[child_id]
                if child_holder.token is not None:
                    _safe_detach_context(child_holder.token)
                child_span = child_holder.span
                if child_span.end_time is None:  # avoid warning on ended spans
                    child_span.end()
                del self.spans[child_id]
        # detach 当前 span 的 context token
        span.end()
        token = self.spans[run_id].token
        if token:
            _safe_detach_context(token)

        del self.spans[run_id]

    def _handle_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """
        统一的错误处理逻辑

        Args:
            error: 错误对象
            run_id: 当前 Span 的 run_id
            parent_run_id: 父级 run_id
        """
        if not self.enabled or not self.enable_traces:
            return
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span = self.spans[run_id].span
        span.set_status(Status(StatusCode.ERROR, str(error)))
        span.record_exception(error)
        self._end_span(span, run_id)

    def _create_llm_span(
        self,
        run_id: UUID,
        parent_run_id: Optional[UUID],
        name: str,
        metadata: Optional[dict[str, Any]] = None,
        serialized: Optional[dict[str, Any]] = None,
    ) -> Span:
        entity_path = self.get_entity_path(parent_run_id)

        span = self._create_span(
            run_id,
            parent_run_id,
            f"{name}",
            kind=SpanKind.CLIENT,
            entity_path=entity_path,
            metadata=metadata,
        )
        return span

    @contextmanager
    def create_custom_span(
        self,
        name: str,
        *,
        parent_run_id: Optional[UUID] = None,
        attributes: Optional[Dict[str, Any]] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_span: Optional[Span] = None,
    ):
        """通用 Span 上下文管理器，支持 with 语法创建子 Span。

        示例:
            with collector.span_context("custom.span", attributes={"k": "v"}) as span:
                ...
        """
        if parent_run_id is None:
            parent_run_id = self._current_workflow_run_id
        span = None
        run_id = uuid4()
        try:
            span = self._create_span(
                run_id=run_id,
                parent_run_id=parent_run_id,
                name=name,
                kind=kind,
                attributes=attributes or {},
            )
            yield span
            # 正常结束标记为 OK
            span.set_status(Status(StatusCode.OK))
        except Exception as e:  # noqa: BLE001
            if span is not None:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise
        finally:
            if span is not None:
                self._end_span(span, run_id)

    def get_entity_path(self, parent_run_id: Optional[UUID]) -> str:
        """获取父级的 entity_path"""
        if not parent_run_id or parent_run_id not in self.spans:
            return ""

        parent_span = self.spans[parent_run_id]
        if parent_span.entity_path == "":
            return f"{parent_span.entity_name}"
        else:
            return f"{parent_span.entity_path}.{parent_span.entity_name}"

    @dont_throw
    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Agent 链开始执行 - 创建 Chain Span

        顶层 chain 首次触发时，本回调还会承担 Agent 级 root span 的创建职责：
        在执行线程上调用 ``injector.on_bk_agent_start``，并把 root span attach 为
        当前 active context。这是把 ``agent.execution`` 的整个生命周期都收敛到执行
        线程的关键一步——start/end 同线程，避免 ContextVar 跨线程失效。
        """
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        name = self._get_name_from_callback(serialized, **kwargs)

        is_top_level = parent_run_id is None or parent_run_id not in self.spans
        span_kind = "workflow" if is_top_level else "task"

        # 顶层 chain 首次触发：先在执行线程上启动 injector 得到 root span。
        # 之后 _create_span 才能通过 self._injector.root_span 把 chain span 挂在 root 下。
        if is_top_level and not self._injector_started:
            if self._metrics is not None:
                self._agent_started_at = time.monotonic()
                self._metrics.record_agent_started(self._metric_agent_attributes)
                self._metrics.record_active_agent(1, self._metric_agent_attributes)
                self._transition_agent_phase("processing", now=self._agent_started_at)
            try:
                if self._injector is not None:
                    self._injector.on_bk_agent_start(
                        inputs=self._start_inputs,
                        execute_kwargs=self._start_execute_kwargs,
                        agent_info=self._start_agent_info,
                    )
            except Exception:  # noqa: BLE001
                logger.debug("Failed to call injector.on_bk_agent_start", exc_info=True)
            finally:
                self._injector_started = True

        attributes = {
            "chain.name": str(name),
            "chain.type": span_kind,
            "chain.is_top_level": is_top_level,
        }
        self._create_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            name=f"chain.{span_kind}",
            kind=SpanKind.INTERNAL,
            attributes=attributes,
            entity_name=str(name),
            entity_path="",
        )
        if is_top_level:
            # 记录当前顶层 workflow 链的 run_id，供 create_span 使用
            self._current_workflow_run_id = run_id
            # 在 chain span attach 之上，再 attach root span 让其成为当前 active context。
            # 这样后续在同一线程上启动、依赖"当前 active ctx 作为父"的自动插桩 span
            # （典型如 ``opentelemetry.instrumentation.langchain.LangchainInstrumentor``
            # 在顶层 ``start_span`` 时不传 context 的 traceloop workflow span）会以 root 为父，
            # 而不是被压到 ``chain.workflow`` 之下。
            # 注意：栈式 attach 会覆盖此前的 active；on_chain_end / on_chain_error 顶层
            # 必须在结束 chain span 之前 detach 该 token，保持栈平衡。
            if self._injector is not None and self._injector.root_span is not None:
                try:
                    self._root_attach_token = context_api.attach(set_span_in_context(self._injector.root_span))
                except Exception:  # noqa: BLE001
                    logger.debug("Failed to re-attach root span on top-level chain start", exc_info=True)
                    self._root_attach_token = None

    @dont_throw
    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Agent 链执行结束 - 结束 Chain Span

        若本 handler 持有 injector，且当前结束的是顶层 workflow 链，则在此处
        触发 ``injector.on_bk_agent_end()``。该回调由 LangChain 在真正驱动
        Runnable 的线程上调用（流式场景下为 producer 线程），从而保证 root span
        能正确闭合，不受 HTTP 请求线程被 kill 的影响。
        """
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span_holder = self.spans[run_id]
        span = span_holder.span
        span.set_status(Status(StatusCode.OK))
        # 判断当前结束的是否为顶层 workflow 链
        is_top_level_workflow = self._current_workflow_run_id == run_id
        if is_top_level_workflow:
            self._current_workflow_run_id = None
            # 顶层 chain：先 detach 在 on_chain_start 顶层时 attach 的 root span context
            # （栈式 attach 必须按 LIFO 顺序 detach，否则 _end_span 内的 detach 会把栈搞乱）
            self._detach_root_attach_token()

        self._end_span(span, run_id)

        # 顶层 workflow 结束 → 在当前线程结束 root span（与执行 Agent 同线程）
        if is_top_level_workflow:
            self._write_session_totals()  # 在 _finalize_injector 之前
            self._finalize_injector()

    @dont_throw
    async def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Agent 链执行出错

        注意：GeneratorExit 在 LangChain 流式执行中表示上游正常关闭流，
        不视为业务错误。若持有 injector，则将其作为"正常结束"处理 root span，
        避免因流被关闭而导致 root span 永不结束。
        """
        # GeneratorExit：上游正常关流，按"成功"处理
        if isinstance(error, GeneratorExit):  # type: ignore[name-defined]
            logger.debug("Ignore GeneratorExit in on_chain_error (stream closed)")
            # 若是顶层 chain 的关流，需要把 root span 也收尾，避免泄露
            is_top_level = parent_run_id is None or parent_run_id not in self.spans
            if is_top_level:
                self._detach_root_attach_token()
                self._write_session_totals()  # 在 _finalize_injector 之前（流式关流视为成功）
                self._finalize_injector()
            return

        # 如果是顶层 chain 且错误影响到根 Span，需要特殊处理
        is_top_level = parent_run_id is None or parent_run_id not in self.spans

        if is_top_level:
            # 顶层 chain 错误：先 detach root attach（保持栈平衡），再统一走 injector 收尾
            self._detach_root_attach_token()
            self._write_session_totals()  # 在 _finalize_injector(error=error) 之前
            self._finalize_injector(error=error)

        # 处理 Chain Span 本身的错误
        self._handle_error(error, run_id, parent_run_id, **kwargs)

        # 清理当前 workflow run_id 标记
        if self._current_workflow_run_id == run_id:
            self._current_workflow_run_id = None

    @dont_throw
    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        *,
        run_id: UUID,
        tags: Optional[list[str]] = None,
        parent_run_id: Optional[UUID] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Run when Chat Model starts running."""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        span = self._create_llm_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            name="chat_model.generate",
            metadata=metadata,
            serialized=serialized,
        )
        set_chat_request(
            span,
            serialized,
            messages,
            kwargs,
            self.spans[run_id],
            max_attribute_length=self.max_attribute_length,
        )
        if self._metrics is not None:
            self.agent_iteration_counter += 1
            self._llm_started_at[run_id] = time.monotonic()
            active_attributes = self._llm_metric_attributes(run_id)
            self._llm_active_attributes[run_id] = active_attributes
            self._metrics.record_active_llm(1, active_attributes)
            self._active_llm_operation_count += 1
            self._transition_agent_phase(self._operation_phase())

    @dont_throw
    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 开始调用 - 创建 LLM Span"""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        # 创建 LLM Span
        span = self._create_llm_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            name="llm.generate",
            serialized=serialized,
        )
        set_llm_request(
            span,
            serialized,
            prompts,
            kwargs,
            self.spans[run_id],
            max_attribute_length=self.max_attribute_length,
        )
        if self._metrics is not None:
            self.agent_iteration_counter += 1
            self._llm_started_at[run_id] = time.monotonic()
            active_attributes = self._llm_metric_attributes(run_id)
            self._llm_active_attributes[run_id] = active_attributes
            self._metrics.record_active_llm(1, active_attributes)
            self._active_llm_operation_count += 1
            self._transition_agent_phase(self._operation_phase())

    @dont_throw
    async def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Record TTFT once; token contents are intentionally not metric labels."""
        if self._metrics is None or run_id in self._llm_first_chunk_seen:
            return
        started_at = self._llm_started_at.get(run_id)
        if started_at is None:
            return
        self._llm_first_chunk_seen.add(run_id)
        first_token_at = time.monotonic()
        self._metrics.record_first_llm_chunk(first_token_at - started_at, self._llm_metric_attributes(run_id))
        if not self._agent_first_token_seen and self._agent_started_at is not None:
            self._agent_first_token_seen = True
            self._metrics.record_agent_first_token(
                first_token_at - self._agent_started_at,
                self._metric_agent_attributes,
            )

    @dont_throw
    async def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用结束 - 结束 LLM Span"""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        span = self._get_span(run_id)
        model_name = None
        if response.llm_output is not None:
            model_name = response.llm_output.get("model_name") or response.llm_output.get("model_id")
            if model_name is not None:
                _set_span_attribute(span, "gen_ai.response.model", model_name or "unknown")
            id = response.llm_output.get("id")
            if id is not None and id != "":
                _set_span_attribute(span, "gen_ai.response.id", id)

        # token usage 提取 + 累加 + 设 LLM span 属性（D-01/D-02/D-04）
        usage = extract_token_usage(response)
        if usage is not None:
            _set_span_attribute(span, "gen_ai.usage.input_tokens", usage["input_tokens"])
            _set_span_attribute(span, "gen_ai.usage.output_tokens", usage["output_tokens"])
            _set_span_attribute(span, "gen_ai.usage.total_tokens", usage["total_tokens"])
            # 扩展字段：官方扁平化 semconv 命名（D-03 Claude's Discretion 决议，research_open_questions A1），仅当模型返回时设置
            if usage.get("cached_tokens") is not None:
                _set_span_attribute(span, "gen_ai.usage.cache_read.input_tokens", usage["cached_tokens"])
            if usage.get("reasoning_tokens") is not None:
                _set_span_attribute(span, "gen_ai.usage.reasoning.output_tokens", usage["reasoning_tokens"])
            # 累加到实例计数器（D-04；提取失败时 usage 为 None 不计入）
            self._total_input_tokens += usage["input_tokens"]
            self._total_output_tokens += usage["output_tokens"]
            self._total_total_tokens += usage["total_tokens"]

        # 提取响应内容
        set_chat_response(span, response, max_attribute_length=self.max_attribute_length)
        metric_usage = extract_metric_token_usage(response)
        if metric_usage:
            _set_span_attribute(
                span,
                "gen_ai.usage.cache_creation.input_tokens",
                metric_usage["cache_creation_input_tokens"],
            )
            _set_span_attribute(
                span,
                "gen_ai.usage.cache_read.input_tokens",
                metric_usage["cache_read_input_tokens"],
            )
        started_at = self._llm_started_at.pop(run_id, None)
        if self._metrics is not None and started_at is not None:
            duration = time.monotonic() - started_at
            try:
                self._metrics.record_llm(
                    duration=duration,
                    attributes=self._llm_metric_attributes(run_id, model_name),
                )
            finally:
                active_attributes = self._llm_active_attributes.pop(run_id, None)
                if active_attributes is not None:
                    self._metrics.record_active_llm(-1, active_attributes)
                    self._active_llm_operation_count = max(0, self._active_llm_operation_count - 1)
                    self._transition_agent_phase(self._operation_phase())
        self._llm_first_chunk_seen.discard(run_id)
        # 设置状态为成功
        span.set_status(Status(StatusCode.OK))
        self._end_span(span, run_id)

    def _write_session_totals(self) -> None:
        """把本轮 token 累加值写入 root span 汇总属性（必须在 _finalize_injector 之前调用）。"""
        root = self.root_span
        if root is None:
            return
        _set_span_attribute(root, "agent.session.total_input_tokens", self._total_input_tokens)
        _set_span_attribute(root, "agent.session.total_output_tokens", self._total_output_tokens)
        _set_span_attribute(root, "agent.session.total_tokens", self._total_total_tokens)

    @dont_throw
    async def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用出错 - 标记 LLM Span 为错误"""
        started_at = self._llm_started_at.pop(run_id, None)
        if self._metrics is not None and started_at is not None:
            duration = time.monotonic() - started_at
            try:
                self._metrics.record_llm(
                    duration=duration,
                    attributes=self._llm_metric_attributes(run_id),
                    error=error,
                )
            finally:
                active_attributes = self._llm_active_attributes.pop(run_id, None)
                if active_attributes is not None:
                    self._metrics.record_active_llm(-1, active_attributes)
                    self._active_llm_operation_count = max(0, self._active_llm_operation_count - 1)
                    self._transition_agent_phase(self._operation_phase())
        self._llm_first_chunk_seen.discard(run_id)
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """工具调用开始 - 创建 Tool Span"""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        self.tool_call_counter += 1
        tool_name = self._get_name_from_callback(serialized, kwargs=kwargs)
        attributes = {
            "tool.name": tool_name,
            "tool.call_index": self.tool_call_counter,
            "tool.input": input_str,
        }
        self._create_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            name="tool.execution",
            kind=SpanKind.INTERNAL,
            attributes=attributes,
        )
        if self._metrics is not None:
            self._tool_started_at[run_id] = time.monotonic()
            metric_attributes = {
                **self._metric_agent_attributes,
                "gen_ai.tool.name": tool_name,
                "gen_ai.tool.type": "function",
            }
            self._tool_metric_attributes[run_id] = metric_attributes
            self._metrics.record_active_tool(1, metric_attributes)
            self._active_tool_operation_count += 1
            self._transition_agent_phase(self._operation_phase())

    @dont_throw
    async def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """工具调用结束 - 结束 Tool Span 或 RAG Span"""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span = self._get_span(run_id)
        _set_span_attribute(span, "tool.output", output)
        _set_span_attribute(span, "tool.execution_status", "success")
        started_at = self._tool_started_at.pop(run_id, None)
        metric_attributes = self._tool_metric_attributes.pop(run_id, None)
        if self._metrics is not None and metric_attributes is not None:
            try:
                if started_at is not None:
                    duration = time.monotonic() - started_at
                    self._metrics.record_tool(duration, metric_attributes)
            finally:
                self._metrics.record_active_tool(-1, metric_attributes)
                self._active_tool_operation_count = max(0, self._active_tool_operation_count - 1)
                self._transition_agent_phase(self._operation_phase())
        span.set_status(Status(StatusCode.OK))
        self._end_span(span, run_id)

    @dont_throw
    async def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """工具调用出错 - 标记 Tool Span 为错误"""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span = self._get_span(run_id)
        _set_span_attribute(span, "tool.execution_status", "failed")
        _set_span_attribute(span, "tool.error_message", traceback.format_exc())
        started_at = self._tool_started_at.pop(run_id, None)
        metric_attributes = self._tool_metric_attributes.pop(run_id, None)
        if self._metrics is not None and metric_attributes is not None:
            try:
                if started_at is not None:
                    duration = time.monotonic() - started_at
                    self._metrics.record_tool(duration, metric_attributes, error=error)
            finally:
                self._metrics.record_active_tool(-1, metric_attributes)
                self._active_tool_operation_count = max(0, self._active_tool_operation_count - 1)
                self._transition_agent_phase(self._operation_phase())
        # 使用统一的错误处理
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    async def on_agent_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when agent errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    async def on_retriever_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when retriever errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)
