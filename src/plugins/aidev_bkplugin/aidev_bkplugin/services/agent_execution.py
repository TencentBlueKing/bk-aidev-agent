# -*- coding: utf-8 -*-
"""HTTP Chat API 执行辅助。

- ``build_execute_kwargs``：入参标准化（serializer / 插件共用）。
- ``AgentExecutor``：同步执行 + SSE 聚合写回（``wrap_generator``，供 builtin view 使用）。
- 标准运维插件 1.0 / 2.0 编排见 ``agent_bkplugin``。
"""

from __future__ import annotations

import json
from logging import getLogger

from aidev_agent.enums import ChatContentStatus, PromptRole, StreamEventType
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent import ChatCompletionAgent
from aidev_agent.services.event_handlers.base import BaseSessionWriter

# OpenTelemetry 是可选 extras（pip install aidev-bkplugin[opentelemetry]）。
# 未安装时 trace context 注入降级为 no-op，其余流程不受影响。
try:
    from opentelemetry import trace
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
except ImportError:
    trace = None
    TraceContextTextMapPropagator = None

from .agent_builder import AgentBuilder
from .agent_session import SessionManager

logger = getLogger(__name__)


def build_execute_kwargs(_execute_kwargs: dict, username: str | None = None) -> ExecuteKwargs:
    """``dict`` → ``ExecuteKwargs``，并补齐 caller_/executor 等字段；按需注入 OTel trace context。"""
    execute_kwargs = ExecuteKwargs.model_validate(_execute_kwargs)
    execute_kwargs.caller_bk_biz_env = execute_kwargs.caller_bk_biz_env or "domestic_biz"
    execute_kwargs.caller_bk_app_code = execute_kwargs.caller_bk_app_code or "bkaidev"
    execute_kwargs.executor = execute_kwargs.executor or username or "anonymous"
    execute_kwargs.caller_executor = execute_kwargs.caller_executor or username or "anonymous"
    execute_kwargs.caller_order_type = execute_kwargs.caller_order_type or "ai_chat"
    if not execute_kwargs.caller_trace_context and trace is not None:
        current_span = trace.get_current_span()
        if current_span is not None and current_span.get_span_context().is_valid:
            carrier: dict[str, str] = {}
            propagator = TraceContextTextMapPropagator()
            propagator.inject(carrier, context=trace.set_span_in_context(current_span))
            execute_kwargs.caller_trace_context = carrier
    return execute_kwargs


class AgentExecutor:
    """``ChatCompletionAgent`` 执行 + 自动写回 AI 回复。

    - 流式：返回包装后的生成器，消费完成（或异常 / 取消）时把汇总内容写回 session。
    - 非流式：同步执行，写回 ``choices[0].delta.content``。
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    def execute_with_save(
        self,
        agent_instance: ChatCompletionAgent,
        execute_kwargs: ExecuteKwargs,
        session_code: str,
        *,
        turn_id: str = "",
    ):
        if execute_kwargs.stream:
            generator = agent_instance.execute(execute_kwargs)
            event_handler = getattr(agent_instance, "event_handler", None)
            # AG-UI 流式由 BaseSessionWriter 按事件落库；legacy 流式在 wrap_generator 结束时汇总写回
            if isinstance(event_handler, BaseSessionWriter) and not execute_kwargs.legacy_streaming:
                return generator
            return self.wrap_generator(generator, session_code, turn_id=turn_id)
        result = agent_instance.execute(execute_kwargs)
        # 非流式 ainvoke 不经过 AG-UI 事件分发，必须显式写回 assistant
        self.session_manager.save_ai_response(session_code, result, turn_id=turn_id)
        event_handler = getattr(agent_instance, "event_handler", None)
        if isinstance(event_handler, BaseSessionWriter) and hasattr(event_handler, "set_streaming_finished"):
            event_handler.set_streaming_finished()
        return result

    @classmethod
    def run_agent_to_completion(
        cls,
        agent_instance: ChatCompletionAgent,
        execute_kwargs: ExecuteKwargs,
        session_code: str,
        session_manager: SessionManager,
        *,
        turn_id: str = "",
    ):
        """执行 agent 直至结束；会话终态由 Agent 流完成回调统一写入。"""
        # 后台 drain（for _ in out: pass，无 SSE 下游）：标记为 background_only，
        # 使消费者读到 EOD 时不立即清理队列，保留缓存历史供前端在清理窗口内接管续流。
        execute_kwargs.background_only = True
        handler = getattr(agent_instance, "event_handler", None)
        if execute_kwargs.stream and isinstance(handler, BaseSessionWriter):
            if turn_id:
                handler.turn_id = turn_id
            if hasattr(handler, "set_streaming_started"):
                handler.set_streaming_started()
        out = cls(session_manager).execute_with_save(
            agent_instance,
            execute_kwargs,
            session_code,
            turn_id=turn_id,
        )
        if execute_kwargs.stream:
            for _ in out:
                pass
        return out

    def wrap_generator(self, generator, session_code: str, *, turn_id: str = ""):
        """SSE 数据格式约定：

        - ``event=think``：思考过程
        - ``event=text``：实际回复内容
        - ``event=error``：错误信息（错误文本在 ``message`` 字段）
        - ``event=reference_doc``：知识库引用文档
        """
        message_parts: list[tuple[str, object]] = []
        current_event_type: str | None = None
        current_content: list[str] = []
        has_error = False
        generator_failed = False

        def _flush_current_content():
            nonlocal current_event_type, current_content
            if current_event_type and current_content:
                message_parts.append((current_event_type, "".join(current_content)))
            current_content = []

        try:
            for chunk in generator:
                yield chunk
                if not chunk.startswith("data: ") or chunk.strip() == "data: [DONE]":
                    continue
                try:
                    data = json.loads(chunk[6:])
                except json.JSONDecodeError:
                    logger.info(f"JSON解析失败: {chunk}")
                    continue

                event_type = data.get("event", "")
                content = data.get("content", "")
                cover = data.get("cover", "")

                if cover:
                    message_parts = []
                    current_content = []

                if event_type != current_event_type:
                    _flush_current_content()
                    current_event_type = event_type

                if (
                    event_type == StreamEventType.THINK.value
                    and content
                    or event_type == StreamEventType.TEXT.value
                    and content
                ):
                    current_content.append(content)
                elif event_type == StreamEventType.ERROR.value:
                    error_message = data.get("message")
                    current_content.append(error_message)
                    has_error = True
                elif event_type == StreamEventType.REFERENCE_DOC.value:
                    docs = data.get("documents", [])
                    if isinstance(docs, list) and docs:
                        message_parts.append((StreamEventType.REFERENCE_DOC.value, docs))
        except Exception:
            generator_failed = True
            raise
        finally:
            _flush_current_content()

            handlers = {
                StreamEventType.THINK.value: self.format_think_content,
                StreamEventType.TEXT.value: lambda x: x,
                StreamEventType.ERROR.value: lambda x: x,
                StreamEventType.REFERENCE_DOC.value: self.format_reference_docs,
            }

            final_content_parts: list[str] = []
            for event_type, content in message_parts:
                handler = handlers.get(event_type)
                if handler and content:
                    final_content_parts.append(handler(content))

            if final_content_parts:
                self.session_manager.save_content(
                    session_code=session_code,
                    role=PromptRole.AI.value,
                    content="".join(final_content_parts),
                    status=ChatContentStatus.ERROR.value if has_error else ChatContentStatus.SUCCESS.value,
                    turn_id=turn_id,
                )
            elif generator_failed:
                # 生成器异常且无任何内容时，写入错误状态
                self.session_manager.save_stream_failure(session_code, "Agent 执行异常，未能生成回复", turn_id=turn_id)

    @classmethod
    def format_think_content(cls, content: str) -> str:
        """流式聚合阶段：把思考内容包装为前端可折叠 HTML（持久化前的内容编码契约）。"""
        return (
            f'<section class="think-head click-close closed">'
            f'<i class="ai-ui-sdk-icon ai-ui-sdk-sikao"></i>已完成思考'
            f'<i class="ai-ui-sdk-icon ai-ui-sdk-angle-up"></i>'
            f"</section>"
            f'<section class="think-body">{content}</section>'
        )

    @classmethod
    def format_reference_docs(cls, documents: list) -> str:
        """流式聚合阶段：把知识库引用文档包装为前端可折叠 HTML 列表（持久化前的内容编码契约）。"""
        if not documents:
            return ""

        html_content = (
            f'<section class="knowledge-head click-close">'
            f'<svg class="ai-ui-sdk-wenzhang"><use href="#ai-ui-sdk-wenzhang"></use></svg>'
            f"找到 {len(documents)} 篇资料参考"
            f'<i class="ai-ui-sdk-icon ai-ui-sdk-angle-up"></i>'
            f'</section><ul class="knowledge-body">'
        )

        for doc in documents:
            metadata = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            path = metadata.get("path", "")
            file_path = metadata.get("file_path", "")
            display_name = metadata.get("display_name", "")
            preview_path = metadata.get("preview_path", "")

            title = display_name or (file_path.split("/")[-1] if file_path else "")
            text_path = preview_path or path

            html_content += (
                f'<li class="knowledge-item">'
                f'<i class="ai-ui-sdk-icon ai-ui-sdk-zhishiku"></i>'
                f'<a href="{text_path}" title="{title} ({text_path})" target="_blank" '
                f'class="knowledge-link g-flex-truncate">{title}</a>'
                f'<a href="{path}" title="预览原文" target="_blank" class="knowledge-link hover-show">'
                f'<i class="ai-ui-sdk-icon ai-ui-sdk-yanjing-kejian"></i></a>'
                f"</li>"
            )

        html_content += "</ul>"
        return html_content

    @classmethod
    def run_chat_completion_with_thread_id(
        cls,
        thread_id: str,
        input_text: str,
        username: str,
        execute_kwargs: ExecuteKwargs,
        channel_type: str | None = None,
        save_content: bool = True,
        transient_system_prompt: str | None = None,
        enable_query_clarification: bool | None = None,
        temperature: float | None = None,
        retry_strategy: str | None = None,
    ):
        """通过 ``thread_id`` 统一执行 ChatCompletion 并自动处理会话保存。

        供 builtin view 与 wxbot 共用，避免 HTTP 自调用。

        :param channel_type: 调用渠道（如 ``api`` / ``popup`` / ``bkplugin`` / ``rtx``），
            透传到 SDK 用于 token usage 渠道分类；不传时按空处理（不上报渠道）。
        :param transient_system_prompt: 仅参与本轮执行、不写入会话存储的系统提示词。
        :param enable_query_clarification: 按调用渠道覆盖查询澄清开关；不传时沿用智能体配置。
        :param temperature: 按调用渠道覆盖模型温度；不传时沿用智能体配置。
        """
        if not input_text:
            raise ValueError("input_text is required when using thread_id")

        builder_kwargs = {"username": username, "temperature": temperature}
        if retry_strategy is not None:
            builder_kwargs["retry_strategy"] = retry_strategy
        builder = AgentBuilder(**builder_kwargs)
        agent_instance, session_code = builder.by_thread_id(
            thread_id=thread_id,
            input_text=input_text,
            save_content=save_content,
            version=execute_kwargs.version,
            channel_type=channel_type,
        )
        if transient_system_prompt:
            agent_instance.chat_history.insert(
                0,
                ChatPrompt(role=PromptRole.SYSTEM.value, content=transient_system_prompt),
            )
        if enable_query_clarification is not None:
            agent_instance.knowledge_query_options.enable_query_clarification = enable_query_clarification
        turn_id = builder.turn_id
        execute_kwargs.session_code = session_code
        if hasattr(execute_kwargs, "turn_id"):
            execute_kwargs.turn_id = turn_id
        handler = getattr(agent_instance, "event_handler", None)
        if execute_kwargs.stream and isinstance(handler, BaseSessionWriter):
            if turn_id:
                handler.turn_id = turn_id
            if hasattr(handler, "set_streaming_started"):
                handler.set_streaming_started()
        result = cls(builder.session_manager).execute_with_save(
            agent_instance,
            execute_kwargs,
            session_code,
            turn_id=turn_id,
        )
        return result, session_code
