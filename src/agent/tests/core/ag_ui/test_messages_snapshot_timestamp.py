# -*- coding: utf-8 -*-
"""MESSAGES_SNAPSHOT 全量回传 createdAt，且不进入模型 payload。"""

import json

from ag_ui.core import EventType
from ag_ui.encoder import EventEncoder
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai.chat_models.base import _convert_message_to_dict

from aidev_agent.core.ag_ui.types import MessageSnapshotEventExtend
from aidev_agent.core.ag_ui.utils import langchain_messages_to_agui
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.services.agent.chat import ChatCompletionAgent


def test_messages_snapshot_includes_created_at_for_all_roles():
    agent = ChatCompletionAgent(
        chat_history=[
            ChatPrompt(
                id="user-1",
                role="user",
                content="第一轮提问",
                builtin_property={"created_at": "2026-08-13T10:00:00+00:00"},
            ),
            ChatPrompt(
                id="assistant-1",
                role="assistant",
                content="第一轮回答",
                builtin_property={"created_at": "2026-08-13T10:01:00+00:00"},
            ),
            ChatPrompt(
                id="user-2",
                role="user",
                content="本轮提问",
                builtin_property={"created_at": "2026-08-13T10:05:00+00:00"},
            ),
        ]
    )

    agui_messages = langchain_messages_to_agui(agent.convert_history_to_messages())
    payload = json.loads(
        EventEncoder()
        .encode(MessageSnapshotEventExtend(type=EventType.MESSAGES_SNAPSHOT, messages=agui_messages))
        .removeprefix("data: ")
        .strip()
    )

    assert payload["messages"][0]["createdAt"] == "2026-08-13T10:00:00+00:00"
    assert payload["messages"][1]["createdAt"] == "2026-08-13T10:01:00+00:00"
    assert payload["messages"][2]["createdAt"] == "2026-08-13T10:05:00+00:00"


def test_created_at_is_not_sent_to_openai_payload():
    user = HumanMessage(
        content="主机 bk18 告警分析",
        additional_kwargs={"created_at": "2026-08-13T10:05:00+00:00"},
    )
    assistant = AIMessage(
        content="告警已收敛",
        additional_kwargs={"created_at": "2026-08-13T10:06:00+00:00"},
    )
    tool = ToolMessage(
        content="ok",
        tool_call_id="tc-1",
        additional_kwargs={"created_at": "2026-08-13T10:05:30+00:00"},
    )

    for message in (user, assistant, tool):
        payload = _convert_message_to_dict(message)
        assert "created_at" not in payload
        assert "createdAt" not in payload
