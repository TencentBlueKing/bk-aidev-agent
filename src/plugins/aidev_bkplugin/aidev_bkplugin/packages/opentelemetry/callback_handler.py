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
from aidev_agent.services.pydantic_models import ExecuteKwargs
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.trace import Span, SpanKind, Status, StatusCode, set_span_in_context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from aidev_bkplugin.packages.opentelemetry.span_utils import (
    SpanHolder,
    set_chat_request,
    set_chat_response,
    set_llm_request,
)
from aidev_bkplugin.packages.opentelemetry.utils import (
    _safe_attach_context,
    _safe_detach_context,
    _sanitize_metadata_value,
    _set_span_attribute,
    dont_throw,
)

logger = logging.getLogger(__name__)
SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY = "suppress_language_model_instrumentation"
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
        self.context_token = None  # 用于保存 context token，在 root span 创建时设置
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
        if self.parent_context is not None:
            # 没有父 run_id，但存在上游传播的 Trace Context
            ctx = self.parent_context
        else:
            # 都没有，使用当前 context
            ctx = None

        if self.debug:
            attributes["debug.thread_id"] = threading.current_thread().name

        # 创建 Span
        self.root_span = self.tracer.start_span(
            name="agent.execution",
            context=ctx,
            kind=SpanKind.SERVER,
            attributes=attributes or {},
        )

        # 安全地附加到 context
        token = _safe_attach_context(self.root_span)
        # _set_span_attribute(span, "entity.path", entity_path)
        # 保存 context token 的引用，用于 on_bk_agent_end 清理
        self.context_token = token

    @dont_throw
    def on_bk_agent_end(self, **kwargs: Any) -> None:
        """蓝鲸 Agent 结束回调，作为整个 Agent 执行的出口

        正常结束时在这里补充最终统计信息并关闭根 Span。
        """
        # 结束时间（北京时间）
        now = datetime.now(pytz.timezone(TIMEZONE))
        end_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        end_time_unix_nano = int(now.timestamp() * 1_000_000_000)

        # 设置根 Span 的最终属性
        self.root_span.set_attribute("agent.status", "completed")
        self.root_span.set_attribute("agent.end_time", end_time_str)
        self.root_span.set_attribute("agent.end_time_unix_nano", end_time_unix_nano)

        # 设置状态为成功
        self.root_span.set_status(Status(StatusCode.OK))

        # 使用 _end_span 结束根 Span
        self.root_span.end()
        _safe_detach_context(self.context_token)


class BkAidevAgentCallbackHandler(BaseCallbackHandler):
    """
    基于 LangChain 的 Callback 机制实现对于 BkAidevAgent 的相关信息统计
    """

    def __init__(
        self,
        tracer: trace.Tracer,
        parent_trace_context: Optional[Dict[str, str]] = None,
        *,
        enabled: bool = True,
        enable_traces: bool = True,
        debug: bool = False,
        max_attribute_length: int = 4096,
    ):
        """
        初始化 Trace 收集器

        Args:
            tracer: OpenTelemetry Tracer 实例
            parent_trace_context: 父级 Trace Context (用于跨服务传播)
            enabled: 是否启用追踪，默认 True
            enable_traces: 是否启用 traces，默认 True
            debug: 是否为调试状态
            max_attribute_length: 属性值最大长度，默认 4096
        """
        super().__init__()

        self.tracer = tracer
        # 配置项
        self.enabled = enabled
        self.enable_traces = enable_traces
        self.debug = debug
        self.max_attribute_length = max_attribute_length

        # Span 管理 - 使用 SpanHolder 管理完整的 Span 层级
        self.root_span: Optional[Span] = None
        self._root_run_id: Optional[UUID] = None  # 根 Span 的 run_id
        self.spans: Dict[UUID, SpanHolder] = {}  # 使用 UUID 管理所有 Span
        self._current_workflow_run_id: Optional[UUID] = None  # 当前顶层 workflow 链的 run_id，用于挂载自定义 span

        # 工具调用计数器
        self.tool_call_counter = 0
        self.rag_call_counter = 0

        # Trace Context 传播
        self.parent_trace_context = parent_trace_context
        self.parent_context = None
        self.context_token = None  # 用于保存 context token，在 root span 创建时设置
        self._setup_trace_context()

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
        if metadata is not None:
            current_association_properties = context_api.get_value("association_properties") or {}
            # Sanitize metadata values to ensure they're compatible with OpenTelemetry
            sanitized_metadata = {k: _sanitize_metadata_value(v) for k, v in metadata.items() if v is not None}
            try:
                context_api.attach(
                    context_api.set_value(
                        "association_properties",
                        {**current_association_properties, **sanitized_metadata},
                    )
                )
            except Exception:
                # If setting association properties fails, continue without them
                # This doesn't affect the core span functionality
                pass

        # 确定父级 Context
        if parent_run_id and parent_run_id in self.spans:
            # 有父 Span，使用父 Span 的 context
            ctx = set_span_in_context(self.spans[parent_run_id].span)
        elif self.parent_context is not None:
            # 没有父 run_id，但存在上游传播的 Trace Context
            ctx = self.parent_context
        else:
            # 都没有，使用当前 context
            ctx = None

        attributes = attributes or {}
        if self.debug:
            attributes["debug.thread_id"] = threading.current_thread().name

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
        # 关闭所有child的 span，由于这是一个树结构，所以每一个 span 只会被关闭一次
        for child_id in self.spans[run_id].children:
            if child_id in self.spans:
                child_span = self.spans[child_id].span
                if child_span.end_time is None:  # avoid warning on ended spans
                    child_span.end()
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
        try:
            token = context_api.attach(context_api.set_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY, True))
        except Exception:
            token = None

        self.spans[run_id] = SpanHolder(span, token, None, [], None, entity_path)
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
    def on_chain_start(
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

        根据是否有父级 Span，创建 workflow 或 task 类型的 Chain Span
        """
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        name = self._get_name_from_callback(serialized, **kwargs)

        is_top_level = parent_run_id is None or parent_run_id not in self.spans
        span_kind = "workflow" if is_top_level else "task"
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

    @dont_throw
    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Agent 链执行结束 - 结束 Chain Span"""
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span_holder = self.spans[run_id]
        span = span_holder.span
        span.set_status(Status(StatusCode.OK))
        # 如果当前结束的是顶层 workflow 链，则清理标记
        if self._current_workflow_run_id == run_id:
            self._current_workflow_run_id = None

        self._end_span(span, run_id)
        if parent_run_id is None:
            try:
                context_api.attach(context_api.set_value(SUPPRESS_LANGUAGE_MODEL_INSTRUMENTATION_KEY, False))
            except Exception:
                # If context reset fails, it's not critical for functionality
                pass

    @dont_throw
    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Agent 链执行出错

        注意：GeneratorExit 在 LangChain 流式执行中表示上游正常关闭流，
        不视为业务错误，这里直接忽略。
        """
        # 忽略 GeneratorExit
        if isinstance(error, GeneratorExit):  # type: ignore[name-defined]
            logger.debug("Ignore GeneratorExit in on_chain_error (stream closed)")
            return

        # 如果是顶层 chain 且错误影响到根 Span，需要特殊处理
        is_top_level = parent_run_id is None or parent_run_id not in self.spans

        if is_top_level and self.root_span:
            # 顶层 chain 错误，也标记根 Span 为失败
            try:
                self.root_span.set_attribute("agent.status", "failed")
                self.root_span.set_status(Status(StatusCode.ERROR, str(error)))
                self.root_span.record_exception(error)
                self.root_span.end()

                logger.debug(
                    "Root span ended with error: error=%s",
                    error,
                )
            except Exception as e:
                logger.error(f"Failed to handle root span error: {e}", exc_info=True)
            finally:
                # 清理 context
                self._safe_detach_context(self.context_token)
                self.context_token = None
                self.root_span = None

        # 处理 Chain Span 本身的错误
        self._handle_error(error, run_id, parent_run_id, **kwargs)

        # 清理当前 workflow run_id 标记
        if self._current_workflow_run_id == run_id:
            self._current_workflow_run_id = None

    @dont_throw
    def on_chat_model_start(
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
        set_chat_request(span, serialized, messages, kwargs, self.spans[run_id])

    @dont_throw
    def on_llm_start(
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
        set_llm_request(span, serialized, prompts, kwargs, self.spans[run_id])

    @dont_throw
    def on_llm_end(
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
        if response.llm_output is not None:
            model_name = response.llm_output.get("model_name") or response.llm_output.get("model_id")
            if model_name is not None:
                _set_span_attribute(span, "gen_ai.response.model", model_name or "unknown")
            id = response.llm_output.get("id")
            if id is not None and id != "":
                _set_span_attribute(span, "gen_ai.response.id", id)

        # 提取响应内容
        set_chat_response(span, response)
        # 设置状态为成功
        span.set_status(Status(StatusCode.OK))
        self._end_span(span, run_id)

    @dont_throw
    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用出错 - 标记 LLM Span 为错误"""
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    def on_tool_start(
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

    @dont_throw
    def on_tool_end(
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
        span.set_attribute("tool.output", output)
        span.set_attribute("tool.execution_status", "success")
        span.set_status(Status(StatusCode.OK))
        self._end_span(span, run_id)

    @dont_throw
    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """工具调用出错 - 标记 Tool Span 为错误"""
        if not self.enabled or not self.enable_traces:
            return
        span = self._get_span(run_id)
        span.set_attribute("tool.execution_status", "failed")
        span.set_attribute("tool.error_message", traceback.format_exc())
        # 使用统一的错误处理
        self._handle_error(error, run_id, parent_run_id, **kwargs)

    @dont_throw
    def on_agent_error(
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
    def on_retriever_error(
        self,
        error: Exception,
        *,
        run_id: UUID,
        parent_run_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        """Run when retriever errors."""
        self._handle_error(error, run_id, parent_run_id, **kwargs)
