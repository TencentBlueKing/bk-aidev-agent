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


def configure_database(path):
    os.environ["MESSAGE_HANDLER_TYPE"] = "inmemory"
    import django
    from django.conf import settings

    from tests import settings as test_settings

    values = {key: getattr(test_settings, key) for key in dir(test_settings) if key.isupper()}
    values.update(APP_CODE="app", AIDEV_DATABASE_EVENTS_ENABLED=True)
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


def build_web_application(events, execution_count):
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

    def application(environ, start_response):
        raw = environ["wsgi.input"].read(int(environ["CONTENT_LENGTH"]))
        request = Request(APIRequestFactory().post("/chat/", json.loads(raw), format="json"), parsers=[JSONParser()])
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


def web_process(path, events, status, execution_count):
    from wsgiref.simple_server import WSGIRequestHandler, make_server

    class QuietHandler(WSGIRequestHandler):
        def log_message(self, *_args):
            pass

    try:
        configure_database(path)
        application = build_web_application(events, execution_count)
        with make_server("127.0.0.1", 0, application, handler_class=QuietHandler) as server:
            status.put(("ready", server.server_port, os.getpid()))
            server.timeout = 20
            server.handle_request()
        status.put(("done", os.getpid()))
    except Exception:
        status.put(("error", traceback.format_exc()))
        raise


def wxbot_process(path, sent, status, expected_messages):
    try:
        configure_database(path)
        from aidev_wxbot.wxaibot.database_delivery import DatabaseResumeConsumer

        count = 0

        async def send(target, body):
            nonlocal count
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
            raise TimeoutError("wxbot did not receive expected result")

        with patch(
            "aidev_bkplugin.services.agent_helpers.AgentHelper.build_session_detail_url",
            side_effect=lambda session: f"https://agent.example.com/?session={session}",
        ):
            asyncio.run(consume())
        status.put(("done", os.getpid()))
    except Exception:
        status.put(("error", traceback.format_exc()))
        raise
