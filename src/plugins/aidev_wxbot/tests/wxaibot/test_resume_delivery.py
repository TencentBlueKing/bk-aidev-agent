import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from aidev_wxbot.wxaibot.resume_delivery import ResumeDelivery, markdown_parts


def sse(events):
    return iter(f"data: {json.dumps(event)}\n\n" for event in events)


@pytest.mark.parametrize("resume_type", ["tool_approval", "ask_user_question"])
async def test_resume_sends_start_then_final_new_message(resume_type):
    send = AsyncMock()
    delivery = ResumeDelivery(send, resume_type=resume_type)
    events = [
        {"type": "RUN_STARTED", "runId": "r1"},
        {"type": "RUN_STARTED", "runId": "r1"},
        {"type": "TEXT_MESSAGE_CONTENT", "delta": "hello"},
        {"type": "RUN_FINISHED"},
    ]
    await asyncio.to_thread(delivery.consume, sse(events), "s1", "i1", "t1")
    delivery.finish()
    await delivery.task
    bodies = [call.args[0] for call in send.call_args_list]
    assert len(bodies) == 2
    assert "正在继续原会话" in bodies[0]["markdown"]["content"]
    assert "hello" in bodies[1]["markdown"]["content"]
    assert all(body["msgtype"] == "markdown" for body in bodies)


async def test_resume_interrupt_sends_question_card(question_case):
    send = AsyncMock()
    delivery = ResumeDelivery(send, resume_type="tool_approval")
    events = [{"type": "RUN_STARTED", "runId": "r1"}, question_case.event]
    await asyncio.to_thread(delivery.consume, sse(events), "session-1", "approval-1", "turn-1")
    delivery.finish()
    await delivery.task
    assert send.call_args.args[0]["template_card"]["card_type"] == "vote_interaction"


async def test_network_failure_does_not_stop_agent_drain(caplog):
    consumed = []

    def output():
        yield 'data: {"type":"RUN_STARTED","runId":"r1"}\n\n'
        yield 'data: {"type":"RUN_FINISHED"}\n\n'
        consumed.append("saved")

    delivery = ResumeDelivery(AsyncMock(side_effect=RuntimeError("secret-error")), resume_type="tool_approval")
    await asyncio.to_thread(delivery.consume, output(), "s1", "i1")
    delivery.finish()
    await delivery.task
    assert consumed == ["saved"]
    assert "secret-error" not in caplog.text
    assert "wxbot_resume_delivery_failed" in caplog.text


async def test_close_unregisters_and_does_not_send():
    send = AsyncMock()
    delivery = ResumeDelivery(send, resume_type="ask_user_question")
    delivery.close()
    delivery.failed()
    delivery.finish()
    await asyncio.gather(delivery.task, return_exceptions=True)
    send.assert_not_called()
    assert not delivery._bus._handlers


def test_utf8_message_split_is_lossless_and_bounded():
    text = "你好🙂" * 2000
    parts = list(markdown_parts(text))
    assert "".join(parts) == text
    assert all(0 < len(part.encode()) <= 4000 for part in parts)


@pytest.mark.parametrize("reason", ["aidev:tool_approval", "aidev:user_question"])
async def test_old_interrupt_terminal_replay_does_not_end_new_reply(reason):
    send = AsyncMock()
    delivery = ResumeDelivery(send, resume_type="tool_approval")
    replay = {"type": "RUN_FINISHED", "outcome": {"type": "success", "interrupts": [{"id": "i1", "reason": reason}]}}
    events = [
        replay,
        {"type": "RUN_STARTED", "runId": "new-run"},
        {"type": "TEXT_MESSAGE_CONTENT", "delta": "new answer"},
        {"type": "RUN_FINISHED"},
    ]
    await asyncio.to_thread(delivery.consume, sse(events), "s1", "i1", "t1")
    delivery.finish()
    await delivery.task
    assert send.call_count == 2
    assert "new answer" in send.call_args.args[0]["markdown"]["content"]


async def test_paused_delivery_waits_for_card_update():
    send = AsyncMock()
    delivery = ResumeDelivery(send, resume_type="ask_user_question", paused=True)
    delivery.failed()
    delivery.finish()
    await asyncio.sleep(0)
    send.assert_not_called()
    delivery.activate()
    await delivery.task
    send.assert_called_once()
