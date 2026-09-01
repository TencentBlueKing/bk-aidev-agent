"""Encrypted HTTP callback → worker → queue → polling, without live services."""

import copy
import json
from collections import defaultdict
from types import SimpleNamespace
from unittest.mock import MagicMock, PropertyMock
from urllib.parse import urlencode

import pytest
from aidev_wxbot.wxaibot import views
from aidev_wxbot.wxaibot.decryption import WXBizJsonMsgCrypt
from aidev_wxbot.wxaibot.direct_stream import AgentStream
from aidev_wxbot.wxaibot.strategies import ChatAgentStrategy
from aidev_wxbot.wxaibot.stream import consume_chat_stream
from django.test import RequestFactory


class MemoryQueue:
    def __init__(self):
        self.messages = defaultdict(list)
        self.deleted = []

    def declare_queue(self, *_args, **_kwargs):
        return True

    def publish_message(self, _exchange, queue, body):
        self.messages[queue].append({"body": copy.deepcopy(body)})
        return True

    def get_queue_info(self, queue):
        return {"message_count": len(self.messages[queue])}

    def get_message(self, queue, auto_ack=True):
        return self.messages[queue].pop(0) if self.messages[queue] else None

    def delete_queue(self, queue):
        self.messages.pop(queue, None)
        self.deleted.append(queue)


def sse(events):
    return iter(f"data: {json.dumps(event, ensure_ascii=False)}\n\n" for event in events)


@pytest.fixture
def polling_case(monkeypatch, settings):
    config = {"rtx_token": "synthetic-test-token", "rtx_encoding_aes_key": "A" * 43}
    crypt = WXBizJsonMsgCrypt(config["rtx_token"], config["rtx_encoding_aes_key"], "")
    monkeypatch.setattr(views.WxAiBotViewSet, "wxbot_config", PropertyMock(return_value=config))
    monkeypatch.setattr(views.WxAiBotViewSet, "_get_or_create_thread_id", lambda *_: "original-thread")
    monkeypatch.setattr("aidev_wxbot.wxaibot.context.BkAiDevApi.convert_to_rtx", lambda *_, **__: {"userid": "alice"})
    queue, executor, strategy = MemoryQueue(), MagicMock(), ChatAgentStrategy()
    monkeypatch.setattr(views, "rabbitmq_client", queue)
    monkeypatch.setattr(views, "get_agent_executor", lambda: executor)
    monkeypatch.setattr(views, "resolve_strategy", lambda *_: strategy)
    settings.MAX_MESSAGE_TIME = 300

    def post(payload, *, tamper=False):
        ret, envelope = crypt.EncryptMsg(json.dumps(payload), "test-nonce", "1234567890")
        assert ret == 0
        encrypted = json.loads(envelope)
        query = {
            "msg_signature": encrypted["msgsignature"],
            "timestamp": encrypted["timestamp"],
            "nonce": encrypted["nonce"],
        }
        if tamper:
            query["msg_signature"] = "invalid-signature"
        request = RequestFactory().post("/callback/?" + urlencode(query), encrypted, content_type="application/json")
        response = views.WxAiBotViewSet().callback(request)
        if response.status_code != 200:
            return response
        reply = json.loads(response.content)
        ret, plain = crypt.DecryptMsg(reply, reply["msgsignature"], reply["timestamp"], reply["nonce"])
        assert ret == 0
        return json.loads(plain)

    return SimpleNamespace(queue=queue, executor=executor, strategy=strategy, post=post)


@pytest.mark.parametrize("error", [False, True])
def test_encrypted_text_request_and_poll_return_terminal_reply(polling_case, error):
    case = polling_case
    events = [{"type": "RUN_STARTED", "runId": "run-1"}, {"type": "TEXT_MESSAGE_CONTENT", "delta": "查询完成"}]
    events.append({"type": "RUN_ERROR", "message": "test failure"} if error else {"type": "RUN_FINISHED"})
    case.strategy.open_stream = MagicMock(return_value=AgentStream("chat", sse(events), "session-1"))
    response = case.post(
        {"msgtype": "text", "msgid": "m1", "from": {"userid": "alice"}, "text": {"content": "1A；2BC"}}
    )
    assert not response["stream"]["finish"]
    callback, *args = case.executor.submit.call_args.args
    callback(*args)
    result = case.post({"msgtype": "stream", "stream": {"id": response["stream"]["id"]}})
    assert result["stream"]["finish"]
    assert ("test failure" if error else "查询完成") in result["stream"]["content"]
    assert case.strategy.open_stream.call_args.kwargs["content"] == "1A；2BC"
    assert case.strategy.open_stream.call_args.kwargs["thread_id"] == "original-thread"
    assert case.queue.deleted == [response["stream"]["id"]]


def test_invalid_callback_signature_does_not_run_agent(polling_case):
    response = polling_case.post({"msgtype": "text", "text": {"content": "do not run"}}, tamper=True)
    assert response.status_code != 200
    polling_case.executor.submit.assert_not_called()


@pytest.mark.parametrize("command", ["/title 日志排障", "/web", "/help"])
def test_encrypted_session_command_does_not_start_a_worker(polling_case, monkeypatch, command):
    manager = MagicMock(agent_code="test-agent")
    manager.generate_session_code.return_value = "session-1"
    manager.retrieve_session.return_value = {"session_name": "old"}
    monkeypatch.setattr(views, "SessionManager", lambda **_: manager)
    monkeypatch.setattr(
        views.AgentSession.objects,
        "get",
        lambda **_: SimpleNamespace(thread_id="original-thread", is_session_valid=lambda: True),
    )
    monkeypatch.setattr(
        views.AgentHelper, "build_session_detail_url", lambda *_, **__: "https://agent.example.com/session-1"
    )
    result = polling_case.post({"msgtype": "text", "from": {"userid": "alice"}, "text": {"content": command}})
    assert result["stream"]["finish"]
    polling_case.executor.submit.assert_not_called()
    if command.startswith("/title"):
        manager.update_session_name.assert_called_once_with("session-1", "日志排障")
        assert "已修改" in result["stream"]["content"]
    elif command == "/web":
        assert "https://agent.example.com/session-1" in result["stream"]["content"]
    else:
        assert "/title" in result["stream"]["content"] and "/web" in result["stream"]["content"]


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="HTTP polling does not render approval/Ask-user outcomes yet"
)
@pytest.mark.parametrize("reason", ["aidev:user_question", "aidev:tool_approval"])
def test_polling_interrupt_should_expose_pending_interaction(polling_case, question_case, reason):
    question_case.interrupt["reason"] = reason
    consume_chat_stream(sse([question_case.event]), "m1_9999999999", 0, polling_case.queue)
    response = polling_case.post({"msgtype": "stream", "stream": {"id": "m1_9999999999"}})
    assert response.get("template_card") or response["stream"]["content"]


@pytest.mark.xfail(
    strict=True, raises=AssertionError, reason="HTTP callback does not dispatch template card submissions yet"
)
@pytest.mark.parametrize("kind", ["question", "approval"])
def test_polling_card_click_should_update_card(polling_case, question_case, approval_card_case, kind):
    from aidev_wxbot.wxaibot.question_cards import encode_question_key, question_task_id

    payload = approval_card_case.event
    if kind == "question":
        payload = {
            "msgtype": "event",
            "from": {"userid": "alice"},
            "event": {
                "eventtype": "template_card_event",
                "template_card_event": {
                    "event_key": encode_question_key(question_case.action),
                    "task_id": question_task_id(question_case.action),
                    "selected_items": question_case.selected,
                },
            },
        }
    response = polling_case.post(payload)
    assert response.get("response_type") == "update_template_card"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="HTTP polling still reads run_id instead of AG-UI runId")
def test_polling_reads_actual_agui_run_id(polling_case):
    from ag_ui.core.events import RunStartedEvent
    from ag_ui.encoder import EventEncoder

    seen = []
    encoded = EventEncoder().encode(RunStartedEvent(thread_id="thread-1", run_id="run-1"))
    consume_chat_stream(iter([encoded]), "m1_9999999999", 0, polling_case.queue, on_run_started=seen.append)
    assert seen == ["run-1"]
