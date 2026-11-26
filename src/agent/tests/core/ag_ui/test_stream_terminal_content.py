import pytest
from ag_ui.core import EventType
from aidev_agent.core.ag_ui.agent import LangGraphAgent
from langchain_core.messages import AIMessageChunk


@pytest.mark.asyncio
@pytest.mark.parametrize("final_deltas", [[("91", "stop")], [("91", None), ("", "stop")]])
async def test_final_text_delta_is_emitted_before_message_end(final_deltas):
    agent = LangGraphAgent(name="test", graph=None)
    agent.active_run = {"id": "run"}
    events = []
    for text, reason in [("73", None), *final_deltas]:
        chunk = AIMessageChunk(id="message", content=text, response_metadata={"finish_reason": reason})
        event = {"data": {"chunk": chunk}, "metadata": {}}
        events.extend([item async for item in agent._handle_on_chat_model_stream_event(event)])

    events.extend([item async for item in agent._handle_on_chat_model_end_event({"data": {}})])
    assert [item.type for item in events] == [
        EventType.TEXT_MESSAGE_START,
        EventType.TEXT_MESSAGE_CONTENT,
        EventType.TEXT_MESSAGE_CONTENT,
        EventType.TEXT_MESSAGE_END,
    ]
    assert "".join(item.delta for item in events if item.type == EventType.TEXT_MESSAGE_CONTENT) == "7391"
