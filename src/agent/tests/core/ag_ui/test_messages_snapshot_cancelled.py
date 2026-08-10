# -*- coding: utf-8 -*-
"""MESSAGES_SNAPSHOT 对 fail/error 消息的还原。"""

import json

from ag_ui.core import EventType
from ag_ui.encoder import EventEncoder

from aidev_agent.core.ag_ui.types import MessageSnapshotEventExtend
from aidev_agent.core.ag_ui.utils import langchain_messages_to_agui
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.utils.event import RunId


def _failed_history(status: str = "error", content: str = RunId.CANCELLED_MESSAGE):
    return [
        ChatPrompt(id="1", role="user", content="分析图片"),
        ChatPrompt(id="2", role="assistant", content=content, builtin_property={"status": status}),
    ]


def _build_messages_snapshot(agent: ChatCompletionAgent):
    """与 chat._stream 中 body['messages'] 组装一致。"""
    return langchain_messages_to_agui(agent.convert_history_to_messages())


def test_messages_snapshot_entry_includes_user_cancelled():
    agent = ChatCompletionAgent(chat_history=_failed_history())
    snapshot = _build_messages_snapshot(agent)
    assert [each.role for each in snapshot] == ["user", "assistant"]
    assert snapshot[-1].content == RunId.CANCELLED_MESSAGE
    assert snapshot[-1].status == "error"


def test_messages_snapshot_entry_includes_fail_status():
    agent = ChatCompletionAgent(chat_history=_failed_history(status="fail", content="模型调用失败"))
    snapshot = _build_messages_snapshot(agent)
    assert [each.role for each in snapshot] == ["user", "assistant"]
    assert snapshot[-1].content == "模型调用失败"
    assert snapshot[-1].status == "error"


def test_llm_entry_keeps_cancelled_and_orphan_user_messages():
    """取消轮与连续 user 均保留入模，不再整轮剔除。"""
    cancelled_history = _failed_history() + [ChatPrompt(id="3", role="user", content="换个问题")]
    agent = ChatCompletionAgent(chat_history=cancelled_history)
    llm_messages = agent._filter_messages_for_llm(agent.convert_history_to_messages())
    assert [each.content for each in llm_messages] == ["分析图片", RunId.CANCELLED_MESSAGE, "换个问题"]

    orphan_history = [
        ChatPrompt(id="1", role="user", content="孤立提问"),
        ChatPrompt(id="2", role="user", content="新问题"),
    ]
    agent = ChatCompletionAgent(chat_history=orphan_history)
    llm_messages = agent._filter_messages_for_llm(agent.convert_history_to_messages())
    assert [each.content for each in llm_messages] == ["孤立提问", "新问题"]


def test_messages_snapshot_sse_includes_user_cancelled():
    agent = ChatCompletionAgent(chat_history=_failed_history())
    encoded = EventEncoder().encode(
        MessageSnapshotEventExtend(
            type=EventType.MESSAGES_SNAPSHOT,
            messages=_build_messages_snapshot(agent),
        )
    )
    payload = json.loads(encoded.removeprefix("data: ").strip())
    assert payload["messages"][-1]["role"] == "assistant"
    assert payload["messages"][-1]["content"] == RunId.CANCELLED_MESSAGE
    assert payload["messages"][-1]["status"] == "error"
