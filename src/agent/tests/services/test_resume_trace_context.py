"""Resume envelopes retain the entry context even when stream consumption is deferred."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from aidev_agent.core.ag_ui.types import AgentInput
from aidev_agent.services.agent.chat import ChatCompletionAgent

pytest.importorskip("opentelemetry.trace")

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


def _span(identity, sampled=True):
    return trace.NonRecordingSpan(
        trace.SpanContext(
            trace_id=identity,
            span_id=identity,
            is_remote=False,
            trace_flags=trace.TraceFlags(int(sampled)),
            trace_state=trace.TraceState([("vendor", str(identity))]),
        )
    )


class TestResumeTraceContext:
    @pytest.fixture
    def case(self, monkeypatch):
        from aidev_agent.services.agent import chat

        helper = Mock()
        helper.stream.side_effect = lambda *a, **kw: iter(())
        factory = Mock(return_value=helper)
        monkeypatch.setattr(chat, "GeneratorStreamingHelper", factory)
        manager = Mock()
        manager.get_agent_code.return_value = "app"
        manager.event_publishing_enabled.return_value = True
        agent = SimpleNamespace(
            resource_manager=manager,
            event_handler=SimpleNamespace(session_code="session", turn_id="turn"),
            _build_resume_aware_producer=Mock(return_value=iter(())),
            _on_complete=Mock(),
        )
        request = AgentInput(
            thread_id="graph",
            run_id="run",
            messages=[],
            state={},
            forwarded_props={"command": {"resume": [{"interruptId": "approval"}]}},
        )
        return SimpleNamespace(agent=agent, request=request, factory=factory, helper=helper, manager=manager)

    @staticmethod
    def stream(case, **kwargs):
        return ChatCompletionAgent._stream_with_queue(case.agent, Mock(), case.request, **kwargs)

    @pytest.mark.parametrize("sampled", [False, True])
    @pytest.mark.parametrize("in_worker", [False, True])
    def test_deferred_consumption_keeps_full_entry_context(self, case, sampled, in_worker):
        expected = {}
        with trace.use_span(_span(1, sampled)):
            TraceContextTextMapPropagator().inject(expected)
            stream = self.stream(case, resume=True)
        case.factory.assert_not_called()
        case.manager.publish_event.assert_not_called()
        with trace.use_span(_span(2)):
            if in_worker:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(list, stream).result()
            else:
                list(stream)
            assert trace.get_current_span().get_span_context().trace_id == 2
        observer = case.factory.call_args.kwargs["producer_observer"]
        observer.on_chunk('data: {"type":"RUN_STARTED","runId":"run"}')
        observer.on_complete()
        assert case.manager.publish_event.call_count == 2
        for call in case.manager.publish_event.call_args_list:
            assert call.args[0].value["traceContext"] == expected
        case.helper.prepare_run.assert_called_once_with("run")
        assert case.agent._build_resume_aware_producer.call_args.kwargs["producer_observer"] is observer

    def test_interleaved_requests_do_not_share_context(self, case):
        streams = []
        for identity in (1, 2):
            with trace.use_span(_span(identity)):
                streams.append(self.stream(case, resume=True))
        observers = []
        for stream in reversed(streams):
            list(stream)
            observers.append(case.factory.call_args.kwargs["producer_observer"])
        assert observers[0] is not observers[1]
        for observer, identity in zip(observers, (2, 1)):
            carrier = observer._value["traceContext"]
            parent = TraceContextTextMapPropagator().extract(carrier)
            assert trace.get_current_span(parent).get_span_context().trace_id == identity

    def test_abandoned_stream_never_starts_queue_or_publishes(self, case):
        with trace.use_span(_span(1)):
            stream = self.stream(case, resume=True)
        stream.close()
        case.factory.assert_not_called()
        case.agent._build_resume_aware_producer.assert_not_called()
        case.manager.publish_event.assert_not_called()

    @pytest.mark.parametrize("otel_available", [False, True])
    def test_missing_entry_context_does_not_adopt_consumer_context(self, case, monkeypatch, otel_available):
        from aidev_agent.services import resume_events

        if not otel_available:
            monkeypatch.setattr(resume_events, "TraceContextTextMapPropagator", None)
        with trace.use_span(trace.INVALID_SPAN):
            stream = self.stream(case, resume=True)
        with trace.use_span(_span(2)):
            list(stream)
        observer = case.factory.call_args.kwargs["producer_observer"]
        assert observer._value.get("traceContext") == ({} if otel_available else None)

    @pytest.mark.parametrize(
        "resume,attach_only,enabled,session_code",
        [
            (False, False, True, "session"),
            (True, True, True, "session"),
            (True, False, False, "session"),
            (True, False, True, ""),
        ],
    )
    def test_non_publishing_paths_remain_lazy(self, case, resume, attach_only, enabled, session_code):
        case.manager.event_publishing_enabled.return_value = enabled
        case.agent.event_handler.session_code = session_code
        stream = self.stream(case, resume=resume, attach_only=attach_only)
        case.factory.assert_not_called()
        list(stream)
        assert case.factory.call_args.kwargs["producer_observer"] is None
        case.manager.publish_event.assert_not_called()
