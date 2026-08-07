# -*- coding: utf-8 -*-
"""MESSAGES_SNAPSHOT 入口应包含用户已取消，LLM 上下文应排除。"""

import json

from ag_ui.core import EventType
from ag_ui.encoder import EventEncoder

from aidev_agent.core.ag_ui.types import MessageSnapshotEventExtend
from aidev_agent.core.ag_ui.utils import langchain_messages_to_agui
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.utils.event import RunId


def _cancelled_history() -> list[ChatPrompt]:
    return [
        ChatPrompt(id="1", role="user", content="分析图片"),
        ChatPrompt(id="2", role="assistant", content=RunId.CANCELLED_MESSAGE),
    ]


def _build_messages_snapshot(agent: ChatCompletionAgent):
    """与 chat._stream 中 MESSAGES_SNAPSHOT 入口一致。"""
    return langchain_messages_to_agui(
        agent._chat_history_to_langchain_messages(agent._convert_contents(agent.chat_history))
    )


def test_messages_snapshot_entry_includes_user_cancelled():
    agent = ChatCompletionAgent(chat_history=_cancelled_history())
    snapshot = _build_messages_snapshot(agent)
    assert [each.role for each in snapshot] == ["user", "assistant"]
    assert snapshot[-1].content == RunId.CANCELLED_MESSAGE


def test_convert_history_excludes_user_cancelled_for_llm():
    agent = ChatCompletionAgent(chat_history=_cancelled_history())
    llm_messages = agent.convert_history_to_messages()
    assert len(llm_messages) == 1
    assert llm_messages[0].content == "分析图片"


def test_messages_snapshot_sse_includes_user_cancelled():
    agent = ChatCompletionAgent(chat_history=_cancelled_history())
    encoded = EventEncoder().encode(
        MessageSnapshotEventExtend(
            type=EventType.MESSAGES_SNAPSHOT,
            messages=_build_messages_snapshot(agent),
        )
    )
    payload = json.loads(encoded.removeprefix("data: ").strip())
    assert payload["messages"][-1]["role"] == "assistant"
    assert payload["messages"][-1]["content"] == RunId.CANCELLED_MESSAGE
