# -*- coding: utf-8 -*-
"""只读回答流的 HTTP 行为；完整插件路由在独立集成环境中验证。"""

import json
from types import SimpleNamespace

import pytest
from aidev_bkplugin.views import answer_stream as view_mod
from django.test import RequestFactory, override_settings


def _schedule(state, storage):
    return SimpleNamespace(state=state, data=json.dumps({"context": {"storage": storage}}))


def _request(method="get"):
    return getattr(RequestFactory(), method)("/answer_stream/t1/")


def _events(response):
    text = b"".join(response.streaming_content).decode("utf-8")
    return [
        (block.split("\n")[0][len("event: ") :], json.loads(block.split("\n")[1][len("data: ") :]))
        for block in text.strip().split("\n\n")
    ]


def test_not_found(mocker):
    mocker.patch.object(view_mod, "_load_schedule", return_value=None)
    response = view_mod.answer_stream(_request(), "t1")
    assert response.status_code == 404
    assert json.loads(response.content) == {"result": False, "reason": "not_found"}


def test_not_polling(mocker):
    mocker.patch.object(view_mod, "_load_schedule", return_value=_schedule(3, {"session_code": "s1"}))
    response = view_mod.answer_stream(_request(), "t1")
    assert response.status_code == 409


@pytest.mark.parametrize("data", [None, [], {"context": {"storage": {"session_code": ["s1"]}}}])
def test_invalid_schedule_returns_unsupported(data, mocker):
    mocker.patch.object(view_mod, "_load_schedule", return_value=SimpleNamespace(state=2, data=json.dumps(data)))
    response = view_mod.answer_stream(_request(), "t1")
    assert response.status_code == 409
    assert json.loads(response.content)["result"] is False


def test_finished_returns_history(mocker):
    storage = {"session_code": "s1", "turn_id": "u1", "plugin_username": "admin"}
    mocker.patch.object(view_mod, "_load_schedule", return_value=_schedule(4, storage))
    load = mocker.patch.object(
        view_mod,
        "_load_contents",
        return_value=[{"role": "reasoning", "content": ["想"], "duration": 10, "property": {"turn_id": "u1"}}],
    )
    response = view_mod.answer_stream(_request(), "t1")
    assert response.status_code == 200
    assert response["Content-Type"] == "text/event-stream; charset=utf-8"
    assert response["X-Accel-Buffering"] == "no"
    assert response["Cache-Control"] == "no-cache"
    events = _events(response)
    assert events[0] == ("ready", {"output_key": "output"})
    assert ("agui", {"type": "THINKING_TEXT_MESSAGE_CONTENT", "delta": "想"}) in events
    assert events[-1] == ("end", {"reason": "history"})
    assert load.call_args.args[0].username == "admin"


def test_finished_history_load_failed(mocker):
    storage = {"session_code": "s1", "turn_id": "u1"}
    mocker.patch.object(view_mod, "_load_schedule", return_value=_schedule(4, storage))
    mocker.patch.object(view_mod, "_load_contents", side_effect=RuntimeError("boom"))
    response = view_mod.answer_stream(_request(), "t1")
    assert response.status_code == 409
    assert json.loads(response.content)["reason"] == "execution finished"


def test_handler_without_replay(mocker):
    mocker.patch.object(view_mod, "_load_schedule", return_value=_schedule(2, {"session_code": "s1"}))
    handler = mocker.Mock(supports_replay_from_start=mocker.Mock(return_value=False))
    mocker.patch(
        "aidev_agent.services.messages_handler.factory.message_handler_factory.get",
        return_value=handler,
    )
    response = view_mod.answer_stream(_request(), "t1")
    assert response.status_code == 409
    assert json.loads(response.content)["reason"] == "message handler does not support cross-process replay"


def test_running_stream_is_read_only(mocker):
    mocker.patch.object(view_mod, "_load_schedule", return_value=_schedule(2, {"session_code": "s1"}))
    handler = mocker.Mock()
    handler.has_pending_messages.return_value = True
    handler.get_messages_since.return_value = (
        [
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "hello"}',
            "<END_OF_STREAM>",
        ],
        2,
    )
    mocker.patch.object(view_mod, "_get_handler", return_value=handler)
    response = view_mod.answer_stream(_request(), "t1")
    assert _events(response) == [
        ("ready", {"output_key": "output"}),
        ("agui", {"type": "TEXT_MESSAGE_CONTENT", "delta": "hello"}),
        ("end", {"reason": "completed"}),
    ]
    assert {call[0] for call in handler.mock_calls} == {"has_pending_messages", "get_messages_since"}


def test_stream_error_finishes_connection(mocker):
    mocker.patch.object(view_mod, "_load_schedule", return_value=_schedule(2, {"session_code": "s1"}))
    mocker.patch.object(view_mod, "_get_handler", return_value=mocker.Mock())

    def broken_stream(*args):
        yield 'event: ready\ndata: {"output_key": "output"}\n\n'
        raise RuntimeError("queue unavailable")

    mocker.patch.object(view_mod, "stream_answer", side_effect=broken_stream)
    response = view_mod.answer_stream(_request(), "t1")
    assert _events(response)[-1] == ("end", {"reason": "error"})


def test_history_stream_error_finishes_connection(mocker):
    storage = {"session_code": "s1", "turn_id": "u1"}
    mocker.patch.object(view_mod, "_load_schedule", return_value=_schedule(4, storage))
    mocker.patch.object(view_mod, "_load_contents", return_value=[None])
    response = view_mod.answer_stream(_request(), "t1")
    assert response.status_code == 200
    assert _events(response) == [("ready", {"output_key": "output"}), ("end", {"reason": "error"})]


def test_stream_settings():
    with override_settings(
        ANSWER_STREAM_OUTPUT_KEY="answer",
        ANSWER_STREAM_MAX_SECONDS=60,
        ANSWER_STREAM_EVENT_TYPES=["TEXT_MESSAGE_CONTENT"],
    ):
        config = view_mod._stream_settings()
    assert config.output_key == "answer"
    assert config.max_duration == 60
    assert config.event_types == frozenset({"TEXT_MESSAGE_CONTENT"})


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_only_get_allowed(method, mocker):
    load = mocker.patch.object(view_mod, "_load_schedule")
    response = view_mod.answer_stream(_request(method), "t1")
    assert response.status_code == 405
    load.assert_not_called()


def test_login_exempt():
    assert getattr(view_mod.answer_stream, "login_exempt", False) is True
