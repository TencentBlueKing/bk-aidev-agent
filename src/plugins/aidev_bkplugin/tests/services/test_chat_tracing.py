from unittest.mock import MagicMock, patch

from aidev_bkplugin.services import chat_tracing


def test_chat_request_span_uses_application_module_tracer():
    view = MagicMock()
    request = MagicMock(headers={})
    handler = MagicMock(return_value="response")

    with (
        patch("aidev_bkplugin.services.chat_tracing.trace_headers", return_value={"traceparent": "active"}),
        patch("aidev_bkplugin.services.chat_tracing.recording_span") as recording_span,
    ):
        result = chat_tracing.chat_request_span(handler)(view, request)

    assert result == "response"
    recording_span.assert_called_once_with(
        "bkplugin.chat.request",
        kind=chat_tracing.SpanKind.INTERNAL if chat_tracing.SpanKind else None,
        record_exception=False,
        use_global_tracer=True,
    )
