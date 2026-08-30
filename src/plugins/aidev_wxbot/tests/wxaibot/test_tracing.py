"""企微消息链路的 span、跨任务上下文与敏感信息边界。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aidev_agent.utils.tracing import get_current_trace_id
from aidev_wxbot.api.bkaidev import BkAiDevApi
from aidev_wxbot.wxaibot import tracing
from aidev_wxbot.wxaibot.context import ContextGenerator
from aidev_wxbot.wxaibot.direct_stream import AgentStream
from opentelemetry.trace import StatusCode

from .test_long_connection import ThreadExecutor, _service, long_connection_module


def _frame(index=1):
    return {
        "body": {
            "msgtype": "text",
            "msgid": f"message-{index}",
            "chattype": "single",
            "from": {"userid": f"private-user-{index}"},
            "text": {"content": "private-content"},
        }
    }


def _spans(exporter, name):
    return [span for span in exporter.get_finished_spans() if span.name == name]


class TestWxBotSpan:
    @pytest.mark.parametrize("error", [RuntimeError("secret-token"), asyncio.CancelledError("secret-token")])
    def test_exception_is_redacted_and_context_restored(self, wxbot_spans, error):
        with pytest.raises(type(error)), tracing.wxbot_span("operation"):
            raise error
        span = wxbot_spans.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR
        assert span.attributes["error.type"] == type(error).__name__
        assert "secret-token" not in span.to_json()
        assert not span.events
        assert get_current_trace_id() is None

    def test_missing_otel_is_noop(self, monkeypatch):
        monkeypatch.setattr(tracing, "trace", None)
        with tracing.received_message_span(_frame()), tracing.wxbot_span("noop") as span:
            tracing.record_failure(span, RuntimeError("private"))
            tracing.record_ack(span, {"errcode": 0})
        assert not tracing.message_trace_active.get()

    def test_disabled_tracer_preserves_business_exception(self, monkeypatch):
        monkeypatch.setattr(tracing, "get_agent_tracer", lambda _: None)
        error = RuntimeError("business-error")
        with pytest.raises(RuntimeError) as caught, tracing.wxbot_span("disabled"):
            raise error
        assert caught.value is error

    @pytest.mark.parametrize("fallback", [False, True])
    def test_identity_conversion_records_fallback_without_identity(self, wxbot_spans, fallback):
        result = RuntimeError("private-error") if fallback else {"userid": "private-rtx"}
        with tracing.received_message_span(_frame()), patch.object(BkAiDevApi, "convert_to_rtx") as convert:
            convert.side_effect = result if fallback else None
            convert.return_value = result
            context = ContextGenerator(_frame()["body"]).generate()
        span = _spans(wxbot_spans, "wxbot.identity.convert_to_rtx")[0]
        assert span.attributes["wxbot.identity.fallback"] == fallback
        assert (span.status.status_code == StatusCode.ERROR) == fallback
        assert context.sender_id == ("private-user-1" if fallback else "private-rtx")
        assert "private" not in span.to_json()

    @pytest.mark.parametrize(
        "method,argument", [("convert_to_rtx", "private-id"), ("retrieve_agent_channel_configs", "rtx")]
    )
    def test_platform_call_propagates_trace_headers(self, wxbot_spans, method, argument):
        api = BkAiDevApi()
        api.api = MagicMock()
        with tracing.received_message_span(_frame()):
            trace_id = get_current_trace_id()
            getattr(api, method)(argument)
        headers = api.api.call_action.call_args.kwargs["headers"]
        assert headers["traceparent"].split("-")[1] == trace_id
        assert "private" not in str(headers)


class TestWxBotSendSpan:
    async def test_card_retry_records_ack_and_not_payload(self, wxbot_spans, monkeypatch):
        service = _service()
        service._client.send_message = AsyncMock(side_effect=[RuntimeError("errcode=45009 private"), {"errcode": 0}])
        monkeypatch.setattr(long_connection_module.asyncio, "sleep", AsyncMock())
        await service._send_template_card(_frame(), {"url": "https://private.example/?token=private"})
        span = _spans(wxbot_spans, "wxbot.approval_card.send")[0]
        assert span.attributes["wecom.send.attempts"] == 2
        assert span.attributes["wecom.send.retries"] == 1
        assert span.attributes["wecom.ack.errcode"] == 0
        assert span.attributes["wecom.ack.received"] is True
        assert span.events[0].attributes["wecom.ack.errcode"] == 45009
        assert span.status.status_code != StatusCode.ERROR
        assert "private" not in span.to_json()

    async def test_disconnected_wait_and_no_agent_reexecution(self, wxbot_spans, monkeypatch):
        service = _service()
        service._client.is_connected = False
        service._client.send_message = AsyncMock(return_value={"errcode": 0})

        async def reconnect(_delay):
            service._client.is_connected = True

        monkeypatch.setattr(long_connection_module.asyncio, "sleep", reconnect)
        await service._send_template_card(_frame(), {})
        span = _spans(wxbot_spans, "wxbot.approval_card.send")[0]
        assert span.attributes["wecom.disconnected_wait_ms"] >= 0
        assert span.attributes["wecom.send.attempts"] == 1
        service._client.send_message.assert_awaited_once()

    async def test_card_cancellation_closes_span(self, wxbot_spans):
        service = _service()
        entered = asyncio.Event()

        async def blocked_send(*_args):
            entered.set()
            await asyncio.Event().wait()

        service._client.send_message = blocked_send
        task = asyncio.create_task(service._send_template_card(_frame(), {}))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        span = _spans(wxbot_spans, "wxbot.approval_card.send")[0]
        assert span.attributes["wxbot.outcome"] == "cancelled"
        assert span.status.status_code == StatusCode.ERROR

    async def test_card_final_failure_records_error(self, wxbot_spans, monkeypatch):
        service = _service()
        service._client.send_message = AsyncMock(side_effect=RuntimeError("errcode=40001 private"))
        clock = iter([0, 0, 301])
        monkeypatch.setattr(long_connection_module, "time", SimpleNamespace(monotonic=lambda: next(clock)))
        monkeypatch.setattr(long_connection_module.asyncio, "sleep", AsyncMock())
        with pytest.raises(RuntimeError):
            await service._send_template_card(_frame(), {})
        span = _spans(wxbot_spans, "wxbot.approval_card.send")[0]
        assert span.attributes["wecom.ack.errcode"] == 40001
        assert span.status.status_code == StatusCode.ERROR
        assert "private" not in span.to_json()

    @pytest.mark.parametrize("operation", ["reply", "welcome", "approval_card.update"])
    async def test_non_stream_reply_waits_for_ack(self, wxbot_spans, operation):
        send = AsyncMock(return_value={"errcode": 0})
        await _service()._send_once(f"wxbot.{operation}", send)
        span = wxbot_spans.get_finished_spans()[0]
        assert span.attributes["wecom.ack.received"] is True
        send.assert_awaited_once()


class TestWxBotMessageTrace:
    @pytest.fixture
    def service(self, monkeypatch):
        service = _service()
        service.trace_stages = {"prepare": {}, "agent": {}, "send": {}}

        def prepare(payload):
            ctx = ContextGenerator(payload).generate()
            service.trace_stages["prepare"][ctx.sender_id] = get_current_trace_id()
            return None, SimpleNamespace(
                content="query", stream_id=ctx.msg_id, username=ctx.sender_id, group_id=ctx.group_id
            )

        approval = 'data: {"type":"RUN_FINISHED","outcome":{"type":"interrupt","interrupts":'
        approval += '[{"id":"approval-1","reason":"aidev:tool_approval","metadata":{}}]}}\n'

        def open_stream(**kwargs):
            from aidev_bkplugin.services.agent_execution import build_execute_kwargs

            headers = build_execute_kwargs({"stream": True}, kwargs["username"]).caller_trace_context
            service.trace_stages["agent"][kwargs["username"]] = headers["traceparent"].split("-")[1]
            return AgentStream("chat", iter([approval]), "private-session")

        async def send(target, _body):
            service.trace_stages["send"][target] = get_current_trace_id()
            return {"errcode": 0}

        strategy = MagicMock()
        strategy.open_stream.side_effect = open_stream
        service._view.prepare_agent_request.side_effect = prepare
        service._client.send_message = AsyncMock(side_effect=send)
        monkeypatch.setattr(BkAiDevApi, "convert_to_rtx", lambda _, user: {"userid": user})
        monkeypatch.setattr(long_connection_module, "resolve_strategy", lambda _: strategy)
        monkeypatch.setattr(long_connection_module, "get_agent_executor", lambda: ThreadExecutor())
        monkeypatch.setattr(long_connection_module, "get_agent_cleanup_executor", lambda: ThreadExecutor())
        monkeypatch.setattr("aidev_wxbot.wxaibot.approval_cards.AgentHelper.build_session_detail_url", lambda _: "")
        return service

    async def test_parallel_messages_share_context_only_with_their_own_card(self, wxbot_spans, service):
        with tracing.wxbot_span("unrelated"):
            unrelated_id = get_current_trace_id()
            await asyncio.gather(*(service._handle_frame(_frame(index)) for index in range(10)))
        tasks = [active.task for active in service._active_streams.values()]
        await asyncio.gather(*tasks)
        receives = _spans(wxbot_spans, "wxbot.message.receive")
        trace_ids = {span.context.trace_id for span in receives}
        assert len(trace_ids) == 10
        assert int(unrelated_id, 16) not in trace_ids
        for name in (
            "wxbot.identity.convert_to_rtx",
            "wxbot.long_connection.session",
            "wxbot.agent.stream",
            "wxbot.approval_card.build",
            "wxbot.reply_stream",
            "wxbot.approval_card.send",
        ):
            spans = _spans(wxbot_spans, name)
            assert len(spans) == 10, name
            assert {span.context.trace_id for span in spans} == trace_ids, name
        assert service._client.send_message.await_count == 10
        assert service.trace_stages["prepare"] == service.trace_stages["agent"] == service.trace_stages["send"]
        assert get_current_trace_id() is None
        assert not tracing.message_trace_active.get()

    async def test_session_span_includes_slow_card_ack(self, wxbot_spans, service):
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_ack(*_args):
            entered.set()
            await release.wait()
            return {"errcode": 0}

        service._client.send_message = slow_ack
        await service._handle_frame(_frame())
        task = service._active_streams["message-1"].task
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert not _spans(wxbot_spans, "wxbot.long_connection.session")
        finally:
            release.set()
            await task
        session = _spans(wxbot_spans, "wxbot.long_connection.session")[0]
        card = _spans(wxbot_spans, "wxbot.approval_card.send")[0]
        assert card.parent.span_id == session.context.span_id
        assert session.end_time >= card.end_time

    async def test_shutdown_cancels_active_send_and_finishes_spans(self, wxbot_spans, service):
        entered = asyncio.Event()

        async def blocked_ack(*_args):
            entered.set()
            await asyncio.Event().wait()

        service._client.send_message = blocked_ack
        await service._handle_frame(_frame())
        await asyncio.wait_for(entered.wait(), 1)
        await service._cancel_active_stream("message-1", reason="shutdown")
        for name in ("wxbot.approval_card.send", "wxbot.long_connection.session"):
            assert _spans(wxbot_spans, name)[0].attributes["wxbot.outcome"] == "cancelled"
        assert not service._active_streams

    async def test_immediate_reply_retains_receive_context_without_agent(self, wxbot_spans, service):
        service._view.prepare_agent_request.side_effect = None
        service._view.prepare_agent_request.return_value = ({"msgtype": "text", "text": {"content": "help"}}, None)
        service._client.reply = AsyncMock(return_value={"errcode": 0})
        await service._handle_frame(_frame())
        root = _spans(wxbot_spans, "wxbot.message.receive")[0]
        reply = _spans(wxbot_spans, "wxbot.message.reply")[0]
        assert root.context.trace_id == reply.context.trace_id
        assert not _spans(wxbot_spans, "wxbot.agent.stream")

    async def test_busy_reply_is_not_attached_to_occupied_session(self, wxbot_spans, service):
        service._group_streams["private-user-1"] = "existing"
        service._active_streams["existing"] = SimpleNamespace(username="private-user-1")
        with tracing.wxbot_span("occupied"):
            occupied_trace = get_current_trace_id()
            await service._handle_frame(_frame())
        reply = _spans(wxbot_spans, "wxbot.reply_stream")[0]
        assert reply.context.trace_id != int(occupied_trace, 16)
        assert not _spans(wxbot_spans, "wxbot.agent.stream")
