# -*- coding: utf-8 -*-
"""上下文压缩内部 LLM 调用的模型事件在 AG-UI 消费端被丢弃。"""

import asyncio

import pytest
from aidev_agent.core.ag_ui.agent import LangGraphAgent
from aidev_agent.core.ag_ui.types import CONTEXT_COMPRESSION_TAG
from langchain_core.messages import AIMessage, AIMessageChunk


def _make_agent() -> LangGraphAgent:
    agent = LangGraphAgent.__new__(LangGraphAgent)
    agent.front_end_display = True
    agent.messages_in_process = {"run-1": None}
    agent.active_run = {"id": "run-1", "thread_id": "t-1", "has_function_streaming": False, "has_text_output": False}
    agent._tool_mapping = {}
    return agent


def _event(event_type: str, tags: list[str]) -> dict:
    data = (
        {"chunk": AIMessageChunk(content="无效的工具调用", id="m-1")}
        if event_type == "on_chat_model_stream"
        else {"output": AIMessage(content="无效的工具调用")}
    )
    return {"event": event_type, "tags": tags, "metadata": {}, "data": data, "run_id": "r"}


async def _collect(agent: LangGraphAgent, event: dict) -> list:
    return [ev async for ev in agent._handle_single_event(event, {})]


@pytest.mark.parametrize("event_type", ["on_chat_model_stream", "on_chat_model_end"])
@pytest.mark.parametrize("tags, suppressed", [([CONTEXT_COMPRESSION_TAG], True), ([], False)])
def test_handle_single_event(event_type, tags, suppressed):
    events = asyncio.run(_collect(_make_agent(), _event(event_type, tags)))
    assert (events == []) is suppressed
