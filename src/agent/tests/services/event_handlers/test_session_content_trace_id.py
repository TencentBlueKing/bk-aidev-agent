# -*- coding: utf-8 -*-
"""会话内容落库时给 property.trace_id 盖章。

trace_id 与 turn_id 并列：turn_id 标识一轮 user-ai 对话，trace_id 标识这轮实际执行的
调用链，两者一起才能从一条会话记录直接跳到 APM。

trace_id 不像 turn_id 那样逐层透传，而是在写入时读当前 span——OTel context 本来就跟着
执行走（producer 线程显式 copy_context，跨进程有 caller_trace_context）。因此这里的
用例都围绕「有没有活跃 span」来组织。
"""

import pytest
from ag_ui.core import CustomEvent, EventType
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from aidev_agent.core.ag_ui.types import SessionPersistenceEventNames
from aidev_agent.enums import PromptRole
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.utils.tracing import current_trace_id


@pytest.fixture(scope="module", autouse=True)
def _tracer_provider():
    """全局 provider 只能设一次；不挂 exporter，用例只关心 trace id 是否有效。"""
    if not isinstance(trace.get_tracer_provider(), TracerProvider):
        trace.set_tracer_provider(TracerProvider())


class _MockApi:
    def __init__(self):
        self.created: list[dict] = []
        self.updated: list[dict] = []

    def create_chat_session_content(self, json, headers):
        self.created.append(json)
        return {"data": {"id": len(self.created)}}

    def update_chat_session_content(self, path_params, json, headers):
        self.updated.append(json)
        return {"data": {"id": path_params["id"]}}


class _MockClient:
    def __init__(self):
        self.api = _MockApi()


def _writer(turn_id: str = "turn-1") -> AGUISessionWriter:
    return AGUISessionWriter(
        session_code="s-trace-1",
        client=_MockClient(),
        username="test",
        tools=[],
        turn_id=turn_id,
    )


class TestAssistantContent:
    def test_trace_id_is_stamped_alongside_turn_id(self):
        writer = _writer()

        with trace.get_tracer(__name__).start_as_current_span("agent.execution"):
            expected = current_trace_id()
            writer._create_session_content(
                message_id="m-1",
                role=PromptRole.ASSISTANT.value,
                content="hi",
                status="complete",
                builtin_property={"message_id": "m-1"},
            )

        prop = writer.client.api.created[0]["property"]
        assert prop["trace_id"] == expected
        assert prop["turn_id"] == "turn-1"

    def test_no_active_span_leaves_the_key_out_entirely(self):
        """宁可没有这个 key，也不要写个空串——查 APM 时空串比缺失更容易误导。"""
        writer = _writer()

        writer._create_session_content(
            message_id="m-1",
            role=PromptRole.ASSISTANT.value,
            content="hi",
            status="complete",
            builtin_property={"message_id": "m-1"},
        )

        assert "trace_id" not in writer.client.api.created[0]["property"]

    def test_updates_carry_the_trace_id_too(self):
        """流式回复先建后更，只盖 create 的话最终落库记录反而丢了 trace_id。"""
        writer = _writer()

        with trace.get_tracer(__name__).start_as_current_span("agent.execution"):
            expected = current_trace_id()
            writer._update_session_content(
                content_id=1,
                message_id="m-1",
                content="hi there",
                builtin_property={"message_id": "m-1"},
            )

        assert writer.client.api.updated[0]["property"]["trace_id"] == expected


class TestUserContent:
    def test_user_record_shares_the_trace_id_with_the_reply(self):
        """一轮对话的 user 与 assistant 必须同 trace，否则只能查到半截链路。"""
        writer = _writer()
        event = CustomEvent(
            type=EventType.CUSTOM,
            name=SessionPersistenceEventNames.UserInputSaved,
            value={"content": "我要回家", "turn_id": "turn-1"},
        )

        with trace.get_tracer(__name__).start_as_current_span("agent.execution"):
            expected = current_trace_id()
            writer.handle_user_input_saved(event)
            writer._create_session_content(
                message_id="m-1",
                role=PromptRole.ASSISTANT.value,
                content="hi",
                status="complete",
                builtin_property={"message_id": "m-1"},
            )

        user_prop, assistant_prop = (record["property"] for record in writer.client.api.created)
        assert user_prop["trace_id"] == assistant_prop["trace_id"] == expected


class TestCurrentTraceId:
    def test_returns_a_32_hex_id_inside_a_span(self):
        with trace.get_tracer(__name__).start_as_current_span("agent.execution"):
            assert len(current_trace_id()) == 32

    def test_returns_empty_outside_any_span(self):
        assert current_trace_id() == ""
