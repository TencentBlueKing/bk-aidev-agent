# -*- coding: utf-8 -*-
"""MESSAGES_SNAPSHOT 快照还原单测。

覆盖四类场景：
- fail/error 消息的还原（含用户取消）；
- 多模态 user content 的结构化数组编码；
- reasoning 消息的还原（LLM 入口排除）；
- createdAt 全量回传（且不进入模型 payload）。

快照数据源为 lossless ChatPrompt 单账本（chat_history），经
``contents_to_agui_messages`` 编码；LLM 入口沿用 convert 链（chat_history）。
"""

import json

import pytest
from ag_ui.core import EventType
from ag_ui.encoder import EventEncoder
from aidev_agent.core.ag_ui.types import MessageSnapshotEventExtend, ReasoningLangChainMessage
from aidev_agent.core.ag_ui.utils import parse_multimodal_content, parse_reasoning_content_value
from aidev_agent.core.nodes.model.chat_history_assembly import (
    _chat_history_to_langchain_messages,
    convert_chat_history_to_messages,
)
from aidev_agent.enums import PromptRole
from aidev_agent.pydantic_models import ChatPrompt
from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.utils.event import RunId
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai.chat_models.base import _convert_message_to_dict


def _build_messages_snapshot(agent: ChatCompletionAgent):
    """与 chat._stream 中 body['messages'] 组装一致（读单账本编码）。"""
    return agent._build_snapshot_agui_messages()


def _encode_snapshot_payload(messages):
    """编码 MESSAGES_SNAPSHOT 事件并解析 SSE 载荷。"""
    encoded = EventEncoder().encode(MessageSnapshotEventExtend(type=EventType.MESSAGES_SNAPSHOT, messages=messages))
    return json.loads(encoded.removeprefix("data: ").strip())


# ---------------------------------------------------------------------------
# fail/error 消息还原
# ---------------------------------------------------------------------------


def _failed_ledger(status: str = "error", content: str = RunId.CANCELLED_MESSAGE):
    """快照数据源：含 fail/error assistant 记录的 ChatPrompt 单账本（chat_history）。"""
    return [
        ChatPrompt(id="1", role="user", content="分析图片"),
        ChatPrompt(id="2", role="assistant", content=content, builtin_property={"status": status}),
    ]


def test_messages_snapshot_entry_includes_user_cancelled():
    agent = ChatCompletionAgent(chat_history=_failed_ledger())
    snapshot = _build_messages_snapshot(agent)
    assert [each.role for each in snapshot] == ["user", "assistant"]
    assert snapshot[-1].content == RunId.CANCELLED_MESSAGE
    assert snapshot[-1].status == "error"


def test_messages_snapshot_entry_includes_fail_status():
    agent = ChatCompletionAgent(chat_history=_failed_ledger(status="fail", content="模型调用失败"))
    snapshot = _build_messages_snapshot(agent)
    assert [each.role for each in snapshot] == ["user", "assistant"]
    assert snapshot[-1].content == "模型调用失败"
    assert snapshot[-1].status == "error"


def test_llm_entry_keeps_cancelled_and_orphan_user_messages():
    """取消轮与连续 user 均保留入模，不再整轮剔除。"""
    cancelled_history = _failed_ledger() + [ChatPrompt(id="3", role="user", content="换个问题")]
    agent = ChatCompletionAgent(chat_history=cancelled_history)
    llm_messages = agent._filter_messages_for_llm(
        convert_chat_history_to_messages(
            agent.chat_history,
            model_context_options=agent.model_context_options,
            support_vision=agent.support_vision,
            model_name=agent.model_name,
            agent_info=agent.agent_info,
            generating_keyword=agent.generating_keyword,
            files=agent.files,
        )
    )
    assert [each.content for each in llm_messages] == ["分析图片", RunId.CANCELLED_MESSAGE, "换个问题"]

    orphan_history = [
        ChatPrompt(id="1", role="user", content="孤立提问"),
        ChatPrompt(id="2", role="user", content="新问题"),
    ]
    agent = ChatCompletionAgent(chat_history=orphan_history)
    llm_messages = agent._filter_messages_for_llm(
        convert_chat_history_to_messages(
            agent.chat_history,
            model_context_options=agent.model_context_options,
            support_vision=agent.support_vision,
            model_name=agent.model_name,
            agent_info=agent.agent_info,
            generating_keyword=agent.generating_keyword,
            files=agent.files,
        )
    )
    assert [each.content for each in llm_messages] == ["孤立提问", "新问题"]


def test_messages_snapshot_sse_includes_user_cancelled():
    agent = ChatCompletionAgent(chat_history=_failed_ledger())
    payload = _encode_snapshot_payload(_build_messages_snapshot(agent))
    assert payload["messages"][-1]["role"] == "assistant"
    assert payload["messages"][-1]["content"] == RunId.CANCELLED_MESSAGE
    assert payload["messages"][-1]["status"] == "error"


# ---------------------------------------------------------------------------
# 多模态 content 格式
# ---------------------------------------------------------------------------

MULTIMODAL_CONTENT = [
    {
        "filename": "upload_file_1785756353687_fjdwe7.jpeg",
        "mime_type": "image/jpeg",
        "type": "binary",
        "url": "https://example.com/files/upload_file.jpeg/",
    },
    {"type": "text", "text": "图片内容是啥"},
]


def _multimodal_ledger(raw_content):
    """快照数据源：含多模态 user 记录的 ChatPrompt 单账本。"""
    return [{"id": "user-1", "role": "user", "content": raw_content, "status": "complete"}]


@pytest.mark.parametrize(
    "raw_content",
    [
        MULTIMODAL_CONTENT,
        json.dumps(MULTIMODAL_CONTENT, ensure_ascii=False),
    ],
    ids=["list", "json_string"],
)
def test_messages_snapshot_keeps_multimodal_array(raw_content):
    """历史多模态消息转换后 content 必须为数组，不能是 JSON 字符串。"""
    agent = ChatCompletionAgent(chat_history=_multimodal_ledger(raw_content))
    agui_message = agent._build_snapshot_agui_messages()[0]

    assert isinstance(agui_message.content, list)
    assert agui_message.content[0].type == "binary"
    assert agui_message.content[0].filename == "upload_file_1785756353687_fjdwe7.jpeg"
    assert agui_message.content[0].mime_type == "image/jpeg"
    assert agui_message.content[1].type == "text"
    assert agui_message.content[1].text == "图片内容是啥"


def test_messages_snapshot_sse_encodes_multimodal_as_array():
    """MESSAGES_SNAPSHOT SSE 载荷中 user content 应为结构化数组。"""
    agent = ChatCompletionAgent(chat_history=_multimodal_ledger(json.dumps(MULTIMODAL_CONTENT, ensure_ascii=False)))
    payload = _encode_snapshot_payload(agent._build_snapshot_agui_messages())

    user_message = payload["messages"][0]
    assert user_message["role"] == "user"
    assert isinstance(user_message["content"], list)
    assert user_message["content"][0]["type"] == "binary"
    assert user_message["content"][0]["filename"] == "upload_file_1785756353687_fjdwe7.jpeg"
    assert user_message["content"][1]["type"] == "text"


def test_chat_history_to_langchain_parses_json_string_multimodal():
    """DB 落库的 JSON 字符串多模态 content 应在历史转换时被解析。"""
    chat_prompt = ChatPrompt(
        id="1",
        role="user",
        content=json.dumps(MULTIMODAL_CONTENT, ensure_ascii=False),
    )
    messages = _chat_history_to_langchain_messages([chat_prompt])

    assert isinstance(messages[0].content, list)
    assert messages[0].content[0]["type"] == "binary"


def test_parse_multimodal_content_rejects_plain_text():
    assert parse_multimodal_content("纯文本") is None


# ---------------------------------------------------------------------------
# reasoning 消息还原
# ---------------------------------------------------------------------------


def _reasoning_ledger() -> list[ChatPrompt]:
    """快照数据源：含 reasoning 记录的 ChatPrompt 单账本（chat_history）。"""
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


def test_parse_reasoning_content_normalizes_types():
    assert parse_reasoning_content_value(["步骤一", "步骤二"]) == ["步骤一", "步骤二"]
    assert parse_reasoning_content_value("纯文本思考") == ["纯文本思考"]
    assert parse_reasoning_content_value(None) == []


def test_messages_snapshot_includes_reasoning_with_duration():
    agent = ChatCompletionAgent(chat_history=_reasoning_ledger())
    snapshot = _build_messages_snapshot(agent)
    assert [each.role for each in snapshot] == ["user", "reasoning", "assistant"]
    reasoning = snapshot[1]
    assert reasoning.content == ["先分析用户意图", "再选择工具"]
    assert reasoning.duration == 2.5


def test_llm_entry_excludes_reasoning():
    agent = ChatCompletionAgent(chat_history=_reasoning_ledger())
    llm_messages = agent._filter_messages_for_llm(
        convert_chat_history_to_messages(
            agent.chat_history,
            model_context_options=agent.model_context_options,
            support_vision=agent.support_vision,
            model_name=agent.model_name,
            agent_info=agent.agent_info,
            generating_keyword=agent.generating_keyword,
            files=agent.files,
        )
    )
    assert not any(isinstance(each, ReasoningLangChainMessage) for each in llm_messages)
    assert [each.content for each in llm_messages] == ["查天气", "北京今天晴"]


def test_messages_snapshot_sse_reasoning_payload():
    agent = ChatCompletionAgent(chat_history=_reasoning_ledger())
    payload = _encode_snapshot_payload(_build_messages_snapshot(agent))
    reasoning = payload["messages"][1]
    assert reasoning["role"] == "reasoning"
    assert reasoning["content"] == ["先分析用户意图", "再选择工具"]
    assert reasoning["duration"] == 2.5


# ---------------------------------------------------------------------------
# createdAt 回传
# ---------------------------------------------------------------------------


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

    payload = _encode_snapshot_payload(agent._build_snapshot_agui_messages())

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
