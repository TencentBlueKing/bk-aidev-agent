import json
import multiprocessing
import queue
from contextlib import contextmanager
from urllib.request import ProxyHandler, Request, build_opener

import pytest
from aidev_agent.events import AIDEV_CHAT_RESUME_FAILED, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_READY
from aidev_bkplugin.models import EventDelivery
from aidev_bkplugin.services.database_event_bus import DatabaseEventBus
from django.db import connection

from .process_helpers import polling_process, runtime_events, web_process, wxbot_process


@contextmanager
def processes(*workers):
    try:
        yield
    finally:
        for worker in workers:
            if worker.pid is not None:
                worker.join(timeout=25)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(timeout=5)


@pytest.fixture
def process_case(transactional_db):
    import hashlib
    from types import SimpleNamespace

    subscriber = "wxbot:" + hashlib.sha256(b"bot-original").hexdigest()
    for name in (AIDEV_CHAT_RESUME_READY, AIDEV_CHAT_RESUME_FINISHED, AIDEV_CHAT_RESUME_FAILED):
        DatabaseEventBus("app").subscribe(
            subscriber,
            name,
            "session-original",
            property={
                "username": "author",
                "target": "original-group",
                "sessionCode": "session-original",
            },
        )
    ctx = multiprocessing.get_context("spawn")
    return SimpleNamespace(
        ctx=ctx,
        path=connection.settings_dict["NAME"],
        executions=ctx.Value("i", 0),
        web_status=ctx.Queue(),
        wx_status=ctx.Queue(),
        sent=ctx.Queue(),
    )


@pytest.mark.parametrize("stream,question,offline", [(True, False, False), (False, False, False), (True, True, True)])
def test_platform_http_callback_and_wxbot_receive_same_resume_once(process_case, stream, question, offline):
    case = process_case
    web = case.ctx.Process(
        target=web_process, args=(case.path, runtime_events(question), case.web_status, case.executions)
    )
    wx = case.ctx.Process(target=wxbot_process, args=(case.path, case.sent, case.wx_status, 3 if question else 2))
    with processes(web, wx):
        web.start()
        ready = case.web_status.get(timeout=20)
        assert ready[0] == "ready", ready
        if not offline:
            wx.start()
        response = call_web(ready[1], stream)
        assert "审批已完成，继续查询。" in response
        assert case.web_status.get(timeout=20)[0] == "done"
        if offline:
            assert EventDelivery.objects.filter(status="pending").count() == 2
            wx.start()
        assert case.wx_status.get(timeout=25)[0] == "done"
        assert_delivered_messages(case, ready[2], question)
        assert EventDelivery.objects.filter(status="delivered").count() == 2


def assert_delivered_messages(case, web_pid, question):
    target, body, wx_pid = case.sent.get(timeout=2)
    assert target == "original-group"
    assert body["template_card"]["jump_list"] == [{"type": 0, "title": "审批已通过"}]
    assert "button_list" not in body["template_card"] and "task_id" not in body["template_card"]
    target, body, _ = case.sent.get(timeout=2)
    assert target == "original-group" and "审批已完成，继续查询。" in body["markdown"]["content"]
    assert wx_pid != web_pid and case.executions.value == 1
    if question:
        assert case.sent.get(timeout=2)[1]["template_card"]["card_type"] == "vote_interaction"


def call_web(port, stream, traceparent="", approved=True):
    data = {
        "session_code": "session-original",
        "resume": [{"interruptId": "approval-original", "status": "resolved", "payload": {"approved": approved}}],
        "execute_kwargs": {"stream": stream},
    }
    request = Request(
        f"http://127.0.0.1:{port}/chat/",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json", "traceparent": traceparent},
    )
    with build_opener(ProxyHandler({})).open(request, timeout=20) as response:
        return response.read().decode()


@pytest.mark.parametrize("approved", [True, False])
def test_http_trace_survives_separate_web_and_wxbot_processes(process_case, approved):
    case = process_case
    records = case.ctx.Queue()
    web = case.ctx.Process(
        target=web_process, args=(case.path, runtime_events(), case.web_status, case.executions, records)
    )
    wx = case.ctx.Process(
        target=wxbot_process,
        args=(case.path, case.sent, case.wx_status, 2, records, "approved" if approved else "rejected"),
    )
    with processes(web, wx):
        web.start()
        ready = case.web_status.get(timeout=20)
        assert ready[0] == "ready", ready
        wx.start()
        call_web(ready[1], True, "00-" + "1" * 32 + "-" + "2" * 16 + "-01", approved)
        assert case.web_status.get(timeout=20)[0] == "done"
        assert case.wx_status.get(timeout=25)[0] == "done"
    assert_trace_records(records)
    assert EventDelivery.objects.filter(status="delivered").count() == 2
    assert case.executions.value == 1
    card = case.sent.get(timeout=2)[1]["template_card"]
    assert card["jump_list"][0]["title"] == ("审批已通过" if approved else "审批已拒绝")


@pytest.mark.parametrize("approved", [True, False])
def test_polling_trace_survives_separate_web_and_wxbot_processes(process_case, approved):
    case = process_case
    records = case.ctx.Queue()
    web = case.ctx.Process(
        target=polling_process, args=(case.path, case.web_status, case.executions, records, approved)
    )
    wx = case.ctx.Process(
        target=wxbot_process,
        args=(case.path, case.sent, case.wx_status, 2, records, "approved" if approved else "rejected"),
    )
    with processes(web, wx):
        wx.start()
        web.start()
        result = case.web_status.get(timeout=25)
        assert result[0] == "done", result
        result = case.wx_status.get(timeout=25)
        assert result[0] == "done", result
    assert_trace_records(records, entry_name="bkplugin.approval.resume")
    assert EventDelivery.objects.filter(status="delivered").count() == 2
    assert case.executions.value == 1
    card = case.sent.get(timeout=2)[1]["template_card"]
    assert card["jump_list"][0]["title"] == ("审批已通过" if approved else "审批已拒绝")


def assert_trace_records(records, entry_name="bkplugin.chat.request"):
    spans = []
    while True:
        try:
            spans.append(records.get(timeout=0.2))
        except queue.Empty:
            break
    expected = {
        entry_name,
        "database_event.publish",
        "database_event.claim",
        "wxbot.event.consume",
        "wxbot.resume.send",
    }
    assert expected <= {span["name"] for span in spans}
    assert all(span["trace_id"] == "1" * 32 for span in spans)
    entry = next(span for span in spans if span["name"] == entry_name)
    assert entry["parent_id"] == int("2" * 16, 16)
    consumers = {span["span_id"] for span in spans if span["name"] == "wxbot.event.consume"}
    assert all(span["parent_id"] in consumers for span in spans if span["name"] == "wxbot.resume.send")
