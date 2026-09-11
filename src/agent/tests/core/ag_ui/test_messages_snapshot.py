# -*- coding: utf-8 -*-
"""MESSAGES_SNAPSHOT 快照还原单测。

覆盖四类场景：
- fail/error 消息的还原（含用户取消）；
- 多模态 user content 的原样保留；
- reasoning 消息的还原（LLM 入口排除）；
- createdAt 位于 builtin_property 内回传（且不进入模型 payload）。

快照数据源为 lossless ChatPrompt 单账本（chat_history），**原样透传**（经
``_to_ledger_dict`` 归一为 dict）而不经 AG-UI 消息转换器：不做 role 归一 /
camelCase 改名 / status 映射 / multimodal 重排。LLM 入口沿用 convert 链。
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
    """与 chat._stream 中 body['messages'] 组装一致（读单账本原样透传）。"""
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
    assert [each["role"] for each in snapshot] == ["user", "assistant"]
    assert snapshot[-1]["content"] == RunId.CANCELLED_MESSAGE
    assert snapshot[-1]["builtin_property"]["status"] == "error"


@pytest.mark.parametrize(
    "status, content",
    [
        ("error", RunId.CANCELLED_MESSAGE),
        ("fail", "模型调用失败"),
    ],
)
def test_messages_snapshot_entry_keeps_platform_status(status, content):
    """原始平台域 status 原样透传，不做归一。"""
    agent = ChatCompletionAgent(chat_history=_failed_ledger(status=status, content=content))
    snapshot = _build_messages_snapshot(agent)
    assert [each["role"] for each in snapshot] == ["user", "assistant"]
    assert snapshot[-1]["content"] == content
    assert snapshot[-1]["builtin_property"]["status"] == status


def _llm_contents(agent: ChatCompletionAgent):
    """把账本经 convert 链送入 LLM 入口视图，返回各条 content。"""
    return [
        each.content
        for each in agent._filter_messages_for_llm(
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
    ]


def test_llm_entry_keeps_cancelled_and_orphan_user_messages():
    """取消轮与连续 user 均保留入模，不再整轮剔除。"""
    cancelled_history = _failed_ledger() + [ChatPrompt(id="3", role="user", content="换个问题")]
    cancelled_agent = ChatCompletionAgent(chat_history=cancelled_history)
    assert _llm_contents(cancelled_agent) == ["分析图片", RunId.CANCELLED_MESSAGE, "换个问题"]

    orphan_agent = ChatCompletionAgent(
        chat_history=[
            ChatPrompt(id="1", role="user", content="孤立提问"),
            ChatPrompt(id="2", role="user", content="新问题"),
        ]
    )
    assert _llm_contents(orphan_agent) == ["孤立提问", "新问题"]


def test_messages_snapshot_sse_includes_user_cancelled():
    agent = ChatCompletionAgent(chat_history=_failed_ledger())
    payload = _encode_snapshot_payload(_build_messages_snapshot(agent))
    assert payload["messages"][-1]["role"] == "assistant"
    assert payload["messages"][-1]["content"] == RunId.CANCELLED_MESSAGE
    assert payload["messages"][-1]["builtin_property"]["status"] == "error"


# ---------------------------------------------------------------------------
# 多模态 content 原样保留
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


def test_messages_snapshot_keeps_multimodal_list_as_is():
    """列表形态多模态 content 原样透传，mime_type 不会被改名为 mimeType。"""
    agent = ChatCompletionAgent(chat_history=_multimodal_ledger(MULTIMODAL_CONTENT))
    message = agent._build_snapshot_agui_messages()[0]

    assert message["content"] == MULTIMODAL_CONTENT
    assert message["content"][0]["mime_type"] == "image/jpeg"
    assert "mimeType" not in message["content"][0]


def test_messages_snapshot_keeps_multimodal_json_string_as_is():
    """JSON 字符串形态多模态 content 不解析为数组，原样透传给前端。"""
    raw = json.dumps(MULTIMODAL_CONTENT, ensure_ascii=False)
    agent = ChatCompletionAgent(chat_history=_multimodal_ledger(raw))
    payload = _encode_snapshot_payload(agent._build_snapshot_agui_messages())

    user_message = payload["messages"][0]
    assert user_message["role"] == "user"
    assert user_message["content"] == raw
    assert isinstance(user_message["content"], str)


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
    assert [each["role"] for each in snapshot] == ["user", "reasoning", "assistant"]
    reasoning = snapshot[1]
    assert reasoning["content"] == ["先分析用户意图", "再选择工具"]
    assert reasoning["builtin_property"]["duration"] == 2.5
    assert "duration" not in reasoning


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
    assert reasoning["builtin_property"]["duration"] == 2.5


# ---------------------------------------------------------------------------
# createdAt 回传
# ---------------------------------------------------------------------------


def test_messages_snapshot_includes_created_at_for_all_roles():
    created_at_values = [
        "2026-08-13T10:00:00+00:00",
        "2026-08-13T10:01:00+00:00",
        "2026-08-13T10:05:00+00:00",
    ]
    agent = ChatCompletionAgent(
        chat_history=[
            ChatPrompt(
                id="user-1", role="user", content="第一轮提问", builtin_property={"created_at": created_at_values[0]}
            ),
            ChatPrompt(
                id="assistant-1",
                role="assistant",
                content="第一轮回答",
                builtin_property={"created_at": created_at_values[1]},
            ),
            ChatPrompt(
                id="user-2", role="user", content="本轮提问", builtin_property={"created_at": created_at_values[2]}
            ),
        ]
    )

    payload = _encode_snapshot_payload(agent._build_snapshot_agui_messages())

    assert [each["builtin_property"]["created_at"] for each in payload["messages"]] == created_at_values
    assert all("createdAt" not in each for each in payload["messages"])


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
