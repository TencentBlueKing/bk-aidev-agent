# -*- coding: utf-8 -*-
"""MESSAGES_SNAPSHOT 应还原 reasoning，LLM 入口应排除。"""

import json

from ag_ui.core import EventType
from ag_ui.encoder import EventEncoder

from aidev_agent.core.ag_ui.types import MessageSnapshotEventExtend, ReasoningLangChainMessage
from aidev_agent.core.ag_ui.utils import langchain_messages_to_agui, parse_reasoning_content_value
from aidev_agent.enums import PromptRole
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.services.agent.chat import ChatCompletionAgent


def _reasoning_history() -> list[ChatPrompt]:
    # 平台 session_context 已解析 JSON；SDK 侧只接收 list / 纯文本
    return [
        ChatPrompt(id="u1", role="user", content="查天气"),
        ChatPrompt(
            id="rsn_lc1",
            role=PromptRole.REASONING.value,
            content=["先分析用户意图", "再选择工具"],
            builtin_property={"message_id": "rsn_lc1", "duration": 2.5},
        ),
        ChatPrompt(id="a1", role="assistant", content="北京今天晴"),
    ]


def _build_messages_snapshot(agent: ChatCompletionAgent):
    return langchain_messages_to_agui(agent.convert_history_to_messages())


def test_parse_reasoning_content_normalizes_types():
    assert parse_reasoning_content_value(["步骤一", "步骤二"]) == ["步骤一", "步骤二"]
    assert parse_reasoning_content_value("纯文本思考") == ["纯文本思考"]
    assert parse_reasoning_content_value(None) == []


def test_messages_snapshot_includes_reasoning_with_duration():
    agent = ChatCompletionAgent(chat_history=_reasoning_history())
    snapshot = _build_messages_snapshot(agent)
    assert [each.role for each in snapshot] == ["user", "reasoning", "assistant"]
    reasoning = snapshot[1]
    assert reasoning.content == ["先分析用户意图", "再选择工具"]
    assert reasoning.duration == 2.5


def test_llm_entry_excludes_reasoning():
    agent = ChatCompletionAgent(chat_history=_reasoning_history())
    llm_messages = agent._filter_messages_for_llm(agent.convert_history_to_messages())
    assert not any(isinstance(each, ReasoningLangChainMessage) for each in llm_messages)
    assert [each.content for each in llm_messages] == ["查天气", "北京今天晴"]


def test_messages_snapshot_sse_reasoning_payload():
    agent = ChatCompletionAgent(chat_history=_reasoning_history())
    encoded = EventEncoder().encode(
        MessageSnapshotEventExtend(
            type=EventType.MESSAGES_SNAPSHOT,
            messages=_build_messages_snapshot(agent),
        )
    )
    payload = json.loads(encoded.removeprefix("data: ").strip())
    reasoning = payload["messages"][1]
    assert reasoning["role"] == "reasoning"
    assert reasoning["content"] == ["先分析用户意图", "再选择工具"]
    assert reasoning["duration"] == 2.5
