import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from aidev_agent.events import AIDEV_CHAT_RESUME_READY
from aidev_wxbot.wxaibot.resume_delivery import ResumeDelivery, markdown_parts


def sse(events):
    return iter(f"data: {json.dumps(event)}\n\n" for event in events)


@pytest.mark.parametrize("resume_type, message_count", [("tool_approval", 1), ("ask_user_question", 2)])
async def test_resume_notice_does_not_change_ready_event_or_final_reply(resume_type, message_count):
    send = AsyncMock()
    delivery = ResumeDelivery(send, resume_type=resume_type)
    ready = []
    delivery._bus.subscribe(AIDEV_CHAT_RESUME_READY, ready.append)
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
    assert len(bodies) == message_count
    assert len(ready) == 1 and ready[0].value["resumeType"] == resume_type
    assert "hello" in bodies[-1]["markdown"]["content"]
    if resume_type == "ask_user_question":
        assert "答案已接收" in bodies[0]["markdown"]["content"]
    assert all(body["msgtype"] == "markdown" for body in bodies)


async def test_resume_interrupt_sends_question_card(question_case):
    send = AsyncMock()
    delivery = ResumeDelivery(send, resume_type="tool_approval")
    events = [{"type": "RUN_STARTED", "runId": "r1"}, question_case.event]
    await asyncio.to_thread(delivery.consume, sse(events), "session-1", "approval-1", "turn-1")
    delivery.finish()
    await delivery.task
    assert send.call_args.args[0]["template_card"]["card_type"] == "vote_interaction"


@pytest.mark.parametrize("native", [True, False])
async def test_resumed_question_always_displays_full_text_and_chat_reply_hint(question_case, native):
    from aidev_wxbot.wxaibot.direct_stream import AgentStream, iter_direct_stream_frames

    question = question_case.interrupt["metadata"]["questions"][0]
    question["options"][0]["description"] = "必须保留的选项说明"
    if not native:
        question["question"] *= 20
    frame = list(iter_direct_stream_frames(AgentStream("chat", sse([question_case.event]), "s1"), "stream"))[-1]
    assert frame.pending_question and frame.finish and not frame.failed
    assert bool(frame.template_card) == native
    assert question["question"] in frame.content and "必须保留的选项说明" in frame.content
    assert "直接在企微回复" in frame.content and "点击卡片回到" not in frame.content


async def test_network_failure_does_not_stop_agent_drain(caplog):
    consumed = []

    def output():
        yield 'data: {"type":"RUN_STARTED","runId":"r1"}\n\n'
        yield 'data: {"type":"TEXT_MESSAGE_CONTENT","delta":"reply"}\n\n'
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
    assert send.call_count == 1
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
