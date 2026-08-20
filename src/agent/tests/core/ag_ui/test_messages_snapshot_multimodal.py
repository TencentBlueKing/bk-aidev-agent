# -*- coding: utf-8 -*-
"""MESSAGES_SNAPSHOT 多模态 content 格式单测。"""

import asyncio
import json

from unittest.mock import MagicMock

import pytest
from ag_ui.core import EventType
from ag_ui.encoder import EventEncoder
from langchain_core.messages import HumanMessage

from aidev_agent.core.ag_ui.types import MessageSnapshotEventExtend
from aidev_agent.core.ag_ui.utils import (
    convert_agui_multimodal_to_langchain,
    langchain_messages_to_agui,
    parse_multimodal_content,
)
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.services.agent.chat import ChatCompletionAgent


MULTIMODAL_CONTENT = [
    {
        "filename": "upload_file_1785756353687_fjdwe7.jpeg",
        "mime_type": "image/jpeg",
        "type": "binary",
        "url": "https://example.com/files/upload_file.jpeg/",
    },
    {"type": "text", "text": "图片内容是啥"},
]


@pytest.mark.parametrize(
    "raw_content",
    [
        MULTIMODAL_CONTENT,
        json.dumps(MULTIMODAL_CONTENT, ensure_ascii=False),
    ],
    ids=["list", "json_string"],
)
def test_langchain_messages_to_agui_keeps_multimodal_array(raw_content):
    """历史多模态消息转换后 content 必须为数组，不能是 JSON 字符串。"""
    message = HumanMessage(id="user-1", content=raw_content)
    agui_message = langchain_messages_to_agui([message])[0]

    assert isinstance(agui_message.content, list)
    assert agui_message.content[0].type == "binary"
    assert agui_message.content[0].filename == "upload_file_1785756353687_fjdwe7.jpeg"
    assert agui_message.content[0].mime_type == "image/jpeg"
    assert agui_message.content[1].type == "text"
    assert agui_message.content[1].text == "图片内容是啥"


def test_messages_snapshot_sse_encodes_multimodal_as_array():
    """MESSAGES_SNAPSHOT SSE 载荷中 user content 应为结构化数组。"""
    agui_messages = langchain_messages_to_agui(
        [HumanMessage(id="user-1", content=json.dumps(MULTIMODAL_CONTENT, ensure_ascii=False))]
    )
    encoded = EventEncoder().encode(
        MessageSnapshotEventExtend(type=EventType.MESSAGES_SNAPSHOT, messages=agui_messages)
    )
    payload = json.loads(encoded.removeprefix("data: ").strip())

    user_message = payload["messages"][0]
    assert user_message["role"] == "user"
    assert isinstance(user_message["content"], list)
    assert user_message["content"][0]["type"] == "binary"
    assert user_message["content"][0]["filename"] == "upload_file_1785756353687_fjdwe7.jpeg"
    assert user_message["content"][1]["type"] == "text"


def test_agui_binary_round_trip_preserves_binary_semantics():
    """AG-UI 回放不得在模型出站前把所有附件伪装成图片。"""
    agui_content = langchain_messages_to_agui([HumanMessage(id="user-1", content=MULTIMODAL_CONTENT)])[0].content

    assert convert_agui_multimodal_to_langchain(agui_content) == [
        {
            "type": "binary",
            "mime_type": "image/jpeg",
            "url": "https://example.com/files/upload_file.jpeg/",
            "data": None,
            "filename": "upload_file_1785756353687_fjdwe7.jpeg",
            "id": None,
        },
        {"type": "text", "text": "图片内容是啥"},
    ]


def test_chat_history_to_langchain_parses_json_string_multimodal():
    """DB 落库的 JSON 字符串多模态 content 应在历史转换时被解析。"""
    chat_prompt = ChatPrompt(
        id="1",
        role="user",
        content=json.dumps(MULTIMODAL_CONTENT, ensure_ascii=False),
    )
    agent = MagicMock()
    messages = ChatCompletionAgent._chat_history_to_langchain_messages(agent, [chat_prompt])

    assert isinstance(messages[0].content, list)
    assert messages[0].content[0]["type"] == "binary"


def test_history_binary_image_is_normalized_before_llm_request():
    """历史中的事故格式图片在模型边界必须转换为 image_url。"""
    content = [
        {
            "type": "binary",
            "mimeType": "application/octet-stream",
            "url": "https://example.com/files/upload_file.png/",
            "filename": "image.png",
        }
    ]
    history = ChatCompletionAgent._chat_history_to_langchain_messages(
        MagicMock(), [ChatPrompt(id="1", role="user", content=json.dumps(content))]
    )
    model = ChatModel.get_setup_instance(model="test", base_url="https://llm-gateway.example.com/v1")
    try:
        payload = model._get_request_payload(history)
    finally:
        asyncio.run(model.http_async_client.aclose())

    assert payload["messages"][0]["content"] == [
        {"type": "image_url", "image_url": {"url": "https://example.com/files/upload_file.png/"}}
    ]


def test_parse_multimodal_content_rejects_plain_text():
    assert parse_multimodal_content("纯文本") is None
