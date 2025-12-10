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

import json
import logging
import threading
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Dict, List, Optional, Union
from uuid import UUID, uuid4

from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.context import _RUNTIME_CONTEXT
from opentelemetry.instrumentation.utils import _SUPPRESS_INSTRUMENTATION_KEY
from opentelemetry.trace import Span, SpanKind, Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from aidev_bkplugin.packages.opentelemetry.utils import dont_throw

logger = logging.getLogger(__name__)


@dataclass
class SpanHolder:
    """管理 Span 及其层级关系"""

    span: Span
    token: Optional[Any]  # context token
    children: List[UUID]  # 子 Span 的 run_id 列表
    entity_name: Optional[str]
    entity_path: str
    start_time: float  # 用于计算持续时间


def _sanitize_metadata_value(value: Any) -> Any:
    """Convert metadata values to OpenTelemetry-compatible types."""
    if value is None:
        return None
    if isinstance(value, (bool, str, bytes, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [str(_sanitize_metadata_value(v)) for v in value]
    # Convert other types to strings
    return str(value)


def _set_span_attribute(span: Span, key: str, value: Any) -> None:
    if value is not None:
        if value != "":
            span.set_attribute(key, value)
        else:
            span.set_attribute(key, "")


def set_request_params(span, kwargs):
    if not span.is_recording():
        return

    for model_tag in ("model", "model_id", "model_name"):
        if (model := kwargs.get(model_tag)) is not None:
            break
        elif (model := (kwargs.get("invocation_params") or {}).get(model_tag)) is not None:
            break
    else:
        model = "unknown"

    _set_span_attribute(span, "gen_ai.request.model", model)
    # response is not available for LLM requests (as opposed to chat)
    _set_span_attribute(span, "gen_ai.response.model", model)

    if "invocation_params" in kwargs:
        params = kwargs["invocation_params"].get("params") or kwargs["invocation_params"]
    else:
        params = kwargs

    _set_span_attribute(
        span,
        "gen_ai.request.max_tokens",
        params.get("max_tokens") or params.get("max_new_tokens"),
    )
    _set_span_attribute(span, "gen_ai.request.temperature", params.get("temperature"))
    _set_span_attribute(span, "gen_ai.request.top_p", params.get("top_p"))

    tools = kwargs.get("invocation_params", {}).get("tools", [])
    for i, tool in enumerate(tools):
        tool_function = tool.get("function", tool)
        _set_span_attribute(
            span,
            f"llm.request.functions.{i}.name",
            tool_function.get("name"),
        )
        _set_span_attribute(
            span,
            f"llm.request.functions.{i}.description",
            tool_function.get("description"),
        )
        _set_span_attribute(
            span,
            f"llm.request.functions.{i}.parameters",
            json.dumps(tool_function.get("parameters", tool.get("input_schema"))),
        )


class BkAidevAgentCallbackHandler(BaseCallbackHandler):
    """
    Agent Trace 数据收集器

    基于 LangChain 的 Callback 机制实现
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
        # 当前顶层 workflow 链的 run_id，用于挂载自定义 span
        self._current_workflow_run_id: Optional[UUID] = None

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
        """
        获取指定 run_id 的 Span

        Args:
            run_id: run_id

        Returns:
            Span 或 None
        """
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
            parent_span = self.spans[parent_run_id].span
            ctx = trace.set_span_in_context(parent_span)
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
        token = self._safe_attach_context(span)
        _set_span_attribute(span, "entity.path", entity_path)

        # 创建 SpanHolder
        self.spans[run_id] = SpanHolder(
            span=span,
            token=token,
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
        for child_id in self.spans[run_id].children:
            if child_id in self.spans:
                child_span = self.spans[child_id].span
                if child_span.end_time is None:  # avoid warning on ended spans
                    child_span.end()
        span.end()
        token = self.spans[run_id].token
        if token:
            self._safe_detach_context(token)

        del self.spans[run_id]

    def _safe_attach_context(self, span: Span):
        """
        安全地将 span 附加到 context,处理异步场景下的潜在失败

        Args:
            span: 要附加的 Span

        Returns:
            context token 用于后续 detach,失败时返回 None
        """
        try:
            # 使用 contextvars 的底层 API 来避免异步上下文问题
            return _RUNTIME_CONTEXT.attach(trace.set_span_in_context(span))
        except RuntimeError as e:
            # 在异步上下文中调用可能失败: "You cannot call this from an async context"
            # 这是预期的行为,静默处理
            logger.debug(f"Context attach failed in async context (expected): {e}")
            return None
        except Exception as e:
            # 其他意外错误
            logger.debug(f"Context attach failed: {e}")
            return None

    def _safe_detach_context(self, token):
        """
        安全地分离 context token,不会导致应用崩溃

        此方法实现了一个故障安全的 context 分离,处理异步/并发场景中
        context token 可能失效的所有已知边缘情况

        Args:
            token: context token
        """
        if not token:
            return

        try:
            # 直接使用 runtime context 避免 context_api.detach() 的错误日志
            from opentelemetry.context import _RUNTIME_CONTEXT

            _RUNTIME_CONTEXT.detach(token)
        except RuntimeError as e:
            # 在异步上下文中调用可能失败: "You cannot call this from an async context"
            # 这是预期的行为,静默处理
            logger.debug(f"Context detach failed in async context (expected): {e}")
        except Exception as e:
            # Context detach 在异步场景下可能失败,这是预期的行为
            # 常见场景:
            # 1. Token 在一个 async task/thread 中创建,在另一个中 detach
            # 2. Context 已经被其他进程 detach
            # 3. Token 由于 context 切换而失效
            # 4. 高并发场景下的竞态条件
            #
            # 这是安全的,因为 span 本身已经正确结束,追踪数据已正确捕获
            logger.debug(f"Context detach failed: {e}")

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

    @contextmanager
    def create_custom_span(
        self,
        name: str,
        *,
        attributes: Optional[Dict[str, Any]] = None,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_span: Optional[Span] = None,
    ):
        """通用 Span 上下文管理器，支持 with 语法创建子 Span。

        示例:
            with collector.span_context("custom.span", attributes={"k": "v"}) as span:
                ...
        """
        if not self.enabled or not self.enable_traces:
            # Trace 关闭时，直接作为空上下文运行
            yield None
            return

        # 确定父级：优先使用显式传入的 parent_span，其次使用当前顶层 workflow span，
        # 再使用当前上下文中的 span，最后回退到 root_span
        parent = parent_span
        # 优先使用当前顶层 workflow span 作为父级（对应 chain.workflow）
        if parent is None and self._current_workflow_run_id and self._current_workflow_run_id in self.spans:
            parent = self.spans[self._current_workflow_run_id].span

        if parent is None:
            try:
                current_span = trace.get_current_span()
                if current_span is not None and current_span.get_span_context().is_valid:
                    parent = current_span
                else:
                    parent = self.root_span
            except Exception:
                parent = self.root_span

        ctx = trace.set_span_in_context(parent) if parent is not None else None

        span = None
        token = None
        try:
            span = self.tracer.start_span(
                name=name,
                context=ctx,
                kind=kind,
                attributes=attributes or {},
            )
            # 将该 span 设为当前 active span，使后续自动插桩产生的 span 挂在其下
            token = self._safe_attach_context(span)
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
                span.end()
            if token:
                self._safe_detach_context(token)

    def get_entity_path(self, parent_run_id: Optional[UUID]) -> str:
        """获取父级的 entity_path"""
        if not parent_run_id or parent_run_id not in self.spans:
            return ""

        parent_span = self.spans[parent_run_id]
        if parent_span.entity_path == "":
            return ""
        elif parent_span.entity_path == "":
            return f"{parent_span.entity_name}"
        else:
            return f"{parent_span.entity_path}.{parent_span.entity_name}"

    @dont_throw
    def on_bk_agent_start(
        self,
        inputs: Dict[str, Any],
        session_code="unknown",
        call_system_bk_app_code="unknown",
        call_system_ai_type="unknown",
        executor="anonymous",
        model_name="unknown",
        knowledge_bases=None,
        knowledge_items=None,
        tools=None,
        agent_info=None,
        **kwargs: Any,
    ) -> None:
        """蓝鲸 Agent 开始回调，作为整个 Agent 执行的入口

        这里负责创建根 Span（agent.execution），并上报会话级别和模型级别的关键信息。
        """
        if not self.enabled or not self.enable_traces:
            return

        # 避免重复创建根 Span（例如多次调用 on_bk_agent_start）
        if self.root_span is not None:
            logger.debug("on_bk_agent_start called but root_span already exists, skip creating new span")
            return

        try:
            # 时间信息（北京时间）
            tz_cn = timezone(timedelta(hours=8))
            now = datetime.now(tz_cn)
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
            # SDK 版本
            try:
                agent_sdk_version = version("aidev_agent")
            except PackageNotFoundError:
                try:
                    agent_sdk_version = version("bkaidev_agent_framework")
                except PackageNotFoundError:
                    agent_sdk_version = "unknown"
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Failed to get aidev_agent version: {e}")
                agent_sdk_version = "unknown"

            # 服务入口级别的属性
            attributes = {
                # Agent 配置
                "agent.info.id": agent_id,
                "agent.info.code": agent_code,
                "agent.info.name": agent_name,
                "agent.info.sdk_version": agent_sdk_version,
                "agent.info.type": agent_type,
                "agent.info.service_catalogue": agent_service_catalogue,
                "agent.info.updated_by": agent_updated_by,
                # 会话维度
                "agent.session.session_code": session_code,
                "agent.session.call_system_bk_app_code": call_system_bk_app_code,
                "agent.session.call_system_ai_type": call_system_ai_type,
                "agent.session.executor": executor,
                "agent.session.input": str(inputs),
                "agent.session.start_time": start_time_str,
                "agent.session.start_time_unix_nano": start_time_unix_nano,
                # 模型与配置维度(标准Agent)
                "agent.info.model_id": model_name,
                "agent.info.knowledge_bases": knowledge_bases or [],
                "agent.info.knowledge_items": knowledge_items or [],
                "agent.info.tools": tools or [],
                # 调用者维度
                "agent.session.caller_bk_app_code": kwargs.get("caller_bk_app_code", ""),
                "agent.session.caller_bk_biz_env": kwargs.get("caller_bk_biz_env", ""),
                "agent.session.caller_bk_biz_id": kwargs.get("caller_bk_biz_id", ""),
                "agent.session.caller_executor": kwargs.get("caller_executor", ""),
                "agent.session.caller_order_type": kwargs.get("caller_order_type", ""),
                "agent.session.caller_trace_id": kwargs.get("caller_trace_id", ""),
            }
            # 如果在本地开发调试阶段, 提供更多信息便于开发者进行 trace 追踪
            if self.debug:
                attributes["agent_info"] = agent_info

            # 生成根 Span 的 run_id
            self._root_run_id = uuid4()

            # 使用 _create_span 创建服务入口 Span（支持从父级上下文继承 trace_id）
            self.root_span = self._create_span(
                run_id=self._root_run_id,
                parent_run_id=None,
                name="agent.execution",
                kind=SpanKind.SERVER,
                attributes=attributes,
            )

            # 保存 context token 的引用，用于 on_bk_agent_end 清理
            self.context_token = self.spans[self._root_run_id].token

            logger.debug(
                "Root span created and set as active context: session_code=%s, trace_id=%s",
                session_code,
                format(self.root_span.get_span_context().trace_id, "032x"),
            )
        except Exception as e:
            logger.error(f"Failed to handle bk agent start: {e}", exc_info=True)

    @dont_throw
    def on_bk_agent_end(self, **kwargs: Any) -> None:
        """蓝鲸 Agent 结束回调，作为整个 Agent 执行的出口

        正常结束时在这里补充最终统计信息并关闭根 Span。
        """
        if not self.enabled or not self.enable_traces or not self.root_span:
            return

        try:
            # 结束时间（北京时间）
            tz_cn = timezone(timedelta(hours=8))
            now = datetime.now(tz_cn)
            end_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
            end_time_unix_nano = int(now.timestamp() * 1_000_000_000)

            # 设置根 Span 的最终属性
            self.root_span.set_attribute("agent.status", "completed")
            self.root_span.set_attribute("agent.tool_total_calls", self.tool_call_counter)
            self.root_span.set_attribute("agent.rag_calls", self.rag_call_counter)
            self.root_span.set_attribute("agent.end_time", end_time_str)
            self.root_span.set_attribute("agent.end_time_unix_nano", end_time_unix_nano)

            # 设置状态为成功
            self.root_span.set_status(Status(StatusCode.OK))

            # 使用 _end_span 结束根 Span
            self._end_span(self.root_span, self._root_run_id)
        except Exception as e:
            logger.error(f"Failed to handle bk agent end: {e}", exc_info=True)
        finally:
            # 清理入口 span 状态
            self.root_span = None
            self._root_run_id = None
            self.context_token = None

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
        if not self.enabled or not self.enable_traces:
            return

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
        if not self.enabled or not self.enable_traces:
            return
        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span_holder = self.spans[run_id]
        span = span_holder.span
        span.set_status(Status(StatusCode.OK))
        # 如果当前结束的是顶层 workflow 链，则清理标记
        if self._current_workflow_run_id == run_id:
            self._current_workflow_run_id = None
        self._end_span(span, run_id)

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
        if not self.enabled or not self.enable_traces:
            return

        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return

        # 创建 LLM Span
        attributes = {
            "llm.input": prompts,
        }
        span = self._create_span(
            run_id=run_id,
            parent_run_id=parent_run_id,
            name="llm.generate",
            kind=SpanKind.CLIENT,
            attributes=attributes,
        )
        set_request_params(span, kwargs)

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
        if not self.enabled or not self.enable_traces:
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
        response_text = ""
        tool_calls = ""
        additional_kwargs = ""
        if response.generations and len(response.generations) > 0:
            if len(response.generations[0]) > 0:
                response_text = response.generations[0][0].text
                message = response.generations[0][0].message

                if hasattr(message, "tool_calls") and message.tool_calls:
                    tool_calls = message.tool_calls
                if hasattr(message, "additional_kwargs") and message.additional_kwargs:
                    additional_kwargs = message.additional_kwargs

        # 设置输出属性
        span.set_attribute("llm.output", self._truncate(response_text))
        span.set_attribute("llm.tool_calls", str(tool_calls))
        span.set_attribute("llm.additional_kwargs", str(additional_kwargs))

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
        if not self.enabled or not self.enable_traces:
            return

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
            name=f"tool.{tool_name}",
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
        if not self.enabled or not self.enable_traces:
            return

        if context_api.get_value(_SUPPRESS_INSTRUMENTATION_KEY):
            return
        span = self._get_span(run_id)
        span.set_attribute("tool.output", self._truncate(output))
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

    def _truncate(self, text: str, max_length: Optional[int] = None) -> str:
        """
        截断文本到指定长度

        Args:
            text: 原始文本
            max_length: 最大长度,默认使用配置中的值

        Returns:
            截断后的文本
        """
        if not text:
            return ""

        max_length = max_length or self.max_attribute_length

        if len(text) <= max_length:
            return text

        return text[:max_length] + "...(truncated)"

    def get_trace_context(self) -> Optional[Dict[str, str]]:
        """
        获取当前的 Trace Context (用于向下游传播)

        Returns:
            Trace Context 字典,格式: {"traceparent": "00-trace_id-span_id-01"}
        """
        if not self.root_span:
            return None

        try:
            # 使用 W3C Trace Context 传播器导出 context
            propagator = TraceContextTextMapPropagator()
            carrier = {}
            propagator.inject(carrier, context=trace.set_span_in_context(self.root_span))
            return carrier
        except Exception as e:
            logger.error(f"Failed to get trace context: {e}", exc_info=True)
            return None
