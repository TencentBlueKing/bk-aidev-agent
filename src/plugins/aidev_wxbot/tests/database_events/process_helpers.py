"""Spawn-safe fixtures: actual HTTP Web process + separate durable wxbot consumer.

Only auth/platform/model execution and the external WeCom socket are fakes.
The view, AgentBuilder event injection, AgentExecutor, core streaming producer,
database publisher/leases and wxbot AG-UI renderer/consumer are production code.
"""

import asyncio
import json
import logging
import os
import sys
import time
import traceback
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.apps import AppConfig


class AidevBkpluginTestConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_bkplugin"
    label = "aidev_bkplugin"


class AidevWxbotTestConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "aidev_wxbot"
    label = "aidev_wxbot"


def configure_database(path):
    os.environ["MESSAGE_HANDLER_TYPE"] = "inmemory"
    import django
    from aidev_agent.config import settings as agent_settings
    from aidev_wxbot import settings as wxbot_settings
    from django.conf import settings

    agent_settings.set("BKAI_DATABASE_EVENTS_ENABLED", True)
    app_config_module = "aidev_wxbot_test_app_configs"
    sys.modules.setdefault(app_config_module, sys.modules[__name__])
    values = {key: getattr(wxbot_settings, key) for key in dir(wxbot_settings) if key.isupper()}
    values.update(
        SECRET_KEY="aidev-wxbot-test-secret",
        USE_TZ=True,
        INSTALLED_APPS=[
            "django.contrib.contenttypes",
            "django.contrib.auth",
            f"{app_config_module}.AidevBkpluginTestConfig",
            f"{app_config_module}.AidevWxbotTestConfig",
        ],
        MIDDLEWARE=[],
        ROOT_URLCONF="aidev_bkplugin.urls",
        APP_CODE="app",
    )
    values.update(
        BK_APIGW_MANAGER_URL_TMPL="https://{api_name}.example.invalid",
        AIDEV_GATEWAY_NAME="test",
        BK_APIGW_STAGE="test",
        BKPAAS_APP_CODE="app",
        BKPAAS_APP_SECRET="test-only",
    )
    values["DATABASES"] = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": path, "OPTIONS": {"timeout": 15}}
    }
    settings.configure(**values)
    django.setup()
    logging.disable(logging.CRITICAL)
    framework = MagicMock()
    framework.kit.decorators.inject_user_token = lambda func: func
    sys.modules.setdefault("bk_plugin_framework", framework)
    sys.modules.setdefault("bk_plugin_framework.kit", framework.kit)
    sys.modules.setdefault("bk_plugin_framework.kit.decorators", framework.kit.decorators)


def runtime_events(question=False):
    terminal = {"type": "RUN_FINISHED", "runId": "run-original", "threadId": "graph-original"}
    if question:
        terminal["outcome"] = {
            "type": "interrupt",
            "interrupts": [
                {
                    "id": "next-question",
                    "reason": "aidev:user_question",
                    "metadata": {
                        "status": "pending",
                        "type": "ask_user_question",
                        "questions": [
                            {
                                "question": "请选择查询范围",
                                "multiSelect": False,
                                "options": [{"label": "订单"}, {"label": "支付"}],
                            }
                        ],
                    },
                }
            ],
        }
    return [
        {"type": "RUN_STARTED", "runId": "run-original", "threadId": "graph-original"},
        {"type": "TEXT_MESSAGE_START", "messageId": "reply-original", "role": "assistant"},
        {"type": "TEXT_MESSAGE_CONTENT", "messageId": "reply-original", "delta": "审批已完成，继续查询。"},
        {"type": "TEXT_MESSAGE_END", "messageId": "reply-original"},
        terminal,
    ]


def approval_record(status="approved"):
    return {
        "session_code": "session-original",
        "role": "interrupt",
        "property": {"builtin_property": {"approve_result": status}},
        "content": {
            "outcome": {
                "type": "success",
                "interrupts": [
                    {
                        "id": "approval-original",
                        "reason": "aidev:tool_approval",
                        "metadata": {
                            "ticket": {
                                "title": "执行工具需要审批",
                                "sn": "DE001",
                                "submit_time": "2026-08-31T00:00:00Z",
                                "url": "https://approval.example.com/DE001",
                                "approvers": ["candidate-not-actual-approver"],
                            }
                        },
                    }
                ],
            },
        },
    }


def build_web_application(events, execution_count, *, polling_record=None):
    from aidev_agent.core.ag_ui.types import AgentInput
    from aidev_agent.pydantic_models import ChatPrompt
    from aidev_agent.services.agent.chat import ChatCompletionAgent
    from aidev_agent.services.event_handlers.base import BaseSessionWriter
    from aidev_agent.services.messages_handler import InMemoryQueueMessageHandler
    from aidev_agent.services.messages_handler.factory import message_handler_factory
    from aidev_bkplugin.views.chat import ChatCompletionViewSet
    from rest_framework.parsers import JSONParser
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    message_handler_factory.replace_defaults(InMemoryQueueMessageHandler())

    class Runtime:
        async def run(self, _input):
            execution_count.value += 1
            for event in events:
                await asyncio.sleep(0.005)
                yield "data: " + json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n\n"

    class Agent(ChatCompletionAgent):
        def _stream(self, _agent, _cfg, _state, _messages, execute_kwargs):
            input = AgentInput(
                thread_id="graph-original",
                run_id="run-original",
                messages=[],
                state={},
                forwarded_props={"command": {"resume": execute_kwargs.resume}},
            )
            return self._stream_with_queue(Runtime(), input, resume=True)

        def execute(self, execute_kwargs):
            if execute_kwargs.stream:
                return self._stream(None, None, {}, [], execute_kwargs)
            return self._invoke_resume_with_events(None, {"configurable": {}}, {}, [], execute_kwargs)

    def factory(**kwargs):
        return Agent(
            thread_id="graph-original",
            resource_manager=kwargs["resource_manager"],
            event_handler=kwargs["event_handler"],
            chat_history=[ChatPrompt(role="user", content="query")],
        )

    writer = MagicMock(spec=BaseSessionWriter)
    writer.session_code, writer.turn_id = "session-original", "turn-original"
    rm = MagicMock()
    rm.get_agent_code.return_value = "app"
    rm.event_publishing_enabled.return_value = False

    if polling_record is not None:

        def run_polling():
            from aidev_agent.services.agent.approval import ApprovalStateHandler
            from aidev_bkplugin.services.approval_resume import _approval_resume_worker

            # Only the platform query/model are faked; use the real polling
            # worker, approval reader, builder, executor and lazy event producer.
            with (
                patch.object(ApprovalStateHandler, "check_resume", return_value=True),
                patch.object(ApprovalStateHandler, "_get_latest_interrupt_record", return_value=polling_record),
                patch("aidev_bkplugin.services.agent_builder.LLMOverrideResourceManager", return_value=rm),
                patch("aidev_bkplugin.services.agent_builder.AgentInstanceFactory.build_agent", side_effect=factory),
                patch("aidev_bkplugin.services.agent_builder.AGUISessionWriter", return_value=writer),
                patch("aidev_bkplugin.services.agent_builder.AgentHelper.get_checkpointer", return_value=None),
            ):
                _approval_resume_worker("session-original", "author", "graph-original", [{"id": "approval-original"}])

        return run_polling

    def application(environ, start_response):
        raw = environ["wsgi.input"].read(int(environ["CONTENT_LENGTH"]))
        http_request = APIRequestFactory().post(
            "/chat/", json.loads(raw), format="json", HTTP_TRACEPARENT=environ.get("HTTP_TRACEPARENT", "")
        )
        request = Request(http_request, parsers=[JSONParser()])
        request.user = SimpleNamespace(username="author")
        view = ChatCompletionViewSet()
        view.request = request
        with (
            patch.object(view, "get_username", return_value="author"),
            patch.object(view, "get_resource_manager", return_value=rm),
            patch.object(view, "_resolve_chat_turn_id", return_value="turn-original"),
            patch("aidev_bkplugin.services.agent_builder.AgentInstanceFactory.build_agent", side_effect=factory),
            patch("aidev_bkplugin.services.agent_builder.AGUISessionWriter", return_value=writer),
            patch("aidev_bkplugin.services.agent_builder.AgentHelper.get_checkpointer", return_value=None),
            patch(
                "aidev_bkplugin.services.agent_config.AgentConfigFetcher.get_info", return_value={"agent_type": "chat"}
            ),
        ):
            response = view.create(request)
            start_response("200 OK", [("Content-Type", "application/json")])
            if getattr(response, "streaming", False):
                yield from response.streaming_content
            else:
                yield json.dumps(response.data, ensure_ascii=False).encode()

    return application


def web_process(path, events, status, execution_count, trace_records=None):
    from wsgiref.simple_server import WSGIRequestHandler, make_server

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, *_args):
            pass

    try:
        configure_database(path)
        published = configure_tracing(trace_records) if trace_records is not None else None
        application = build_web_application(events, execution_count)
        with make_server("127.0.0.1", 0, application, handler_class=QuietHandler) as server:
            status.put(("ready", server.server_port, os.getpid()))
            server.timeout = 20
            server.handle_request()
        if published is not None and not published.wait(5):
            raise TimeoutError("Web producer did not finish publishing")
        status.put(("done", os.getpid()))
    except Exception:
        status.put(("error", traceback.format_exc()))
        raise


def polling_process(path, status, execution_count, trace_records, approved):
    try:
        configure_database(path)
        published = configure_tracing(trace_records)
        record = approval_record("approved" if approved else "rejected")
        record["property"]["builtin_property"]["approval_trace_context"] = {
            "traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01"
        }
        build_web_application(runtime_events(), execution_count, polling_record=record)()
        # EOD can wake the drain before the producer's final publish callback.
        # A real Web server stays alive; this short-lived fixture must too.
        if not published.wait(5):
            raise TimeoutError("Polling producer did not finish publishing")
        status.put(("done", os.getpid()))
    except Exception:
        status.put(("error", traceback.format_exc()))
        raise


def wxbot_process(path, sent, status, expected_messages, trace_records=None, approval="approved"):
    try:
        configure_database(path)
        from aidev_wxbot.wxaibot.database_delivery import DatabaseResumeConsumer

        if trace_records is not None:
            configure_tracing(trace_records)

        count = 0

        async def send(target, body):
            nonlocal count
            if trace_records is not None:
                await traced_send(target, body)
            sent.put((target, body, os.getpid()))
            count += 1

        async def consume():
            consumer = DatabaseResumeConsumer("app", "bot-original", send)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                await consumer.consume_once()
                if count >= expected_messages:
                    return
                await asyncio.sleep(0.025)
            from aidev_bkplugin.models import EventDelivery
            from asgiref.sync import sync_to_async

            states = await sync_to_async(list)(
                EventDelivery.objects.values("status", "error_type", "progress", "attempts")
            )
            raise TimeoutError(f"wxbot sent {count}/{expected_messages}; delivery states={states}")

        with (
            patch(
                "aidev_bkplugin.services.agent_helpers.AgentHelper.build_session_detail_url",
                side_effect=lambda session: f"https://agent.example.com/?session={session}",
            ),
            patch(
                "aidev_wxbot.wxaibot.approval_notifications.SessionManager.list_session_contents",
                return_value=[approval_record(approval)],
            ),
        ):
            asyncio.run(consume())
        status.put(("done", os.getpid()))
    except Exception:
        status.put(("error", traceback.format_exc()))
        raise


def configure_tracing(records):
    import threading

    from aidev_agent.utils.tracing import set_agent_tracer
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

    published = threading.Event()

    class QueueExporter(SpanExporter):
        def export(self, spans):
            for span in spans:
                records.put(
                    {
                        "name": span.name,
                        "trace_id": format(span.context.trace_id, "032x"),
                        "span_id": span.context.span_id,
                        "parent_id": span.parent.span_id if span.parent else None,
                    }
                )
                if (
                    span.name == "database_event.publish"
                    and span.attributes.get("event.name") == "AIDEV_CHAT_RESUME_FINISHED"
                ):
                    published.set()
            return SpanExportResult.SUCCESS

    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(QueueExporter()))
    set_agent_tracer(provider.get_tracer("cross-process-test"))
    return published


async def traced_send(target, body):
    """Use the production send span, with only the external socket/ACK replaced."""
    from unittest.mock import AsyncMock

    # Polling transport is unrelated to the long-connection sender under test.
    with patch.dict(sys.modules, {"aidev_wxbot.utils.rabbitmq": MagicMock()}):
        from aidev_wxbot.wxaibot.long_connection import WxAiBotLongConnectionService
    from aidev_wxbot.wxaibot.tracing import record_ack

    async def send_with_retry(send, span, _event):
        record_ack(span, await send())

    service = SimpleNamespace(
        _shutdown_requested=False,
        _send_with_retry=send_with_retry,
        _client=SimpleNamespace(send_message=AsyncMock(return_value={"errcode": 0})),
    )
    await WxAiBotLongConnectionService._send_resume_message(service, target, body)
