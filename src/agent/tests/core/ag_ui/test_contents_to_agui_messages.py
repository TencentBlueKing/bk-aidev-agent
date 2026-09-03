# -*- coding: utf-8 -*-
"""contents 原始落库记录 → AG-UI ExtendMessage 转换函数专项单测。

镜像前端 ``transferMessageApi2Message``（http/transform/message.ts:92）语义，
覆盖各 role 分支 + 嵌套 camelCase 手工映射 + 异常容错（Wave 0 缺口补全）。
"""

import json

from aidev_agent.core.ag_ui.types import (
    ExtendActivityMessage,
    ExtendAssistantMessage,
    ExtendBaseMessage,
    ExtendInfoMessage,
    ExtendInterruptMessage,
    ExtendSystemMessage,
    ExtendToolMessage,
    ExtendUserMessage,
    ReasoningMessage,
)
from aidev_agent.core.ag_ui.utils import contents_to_agui_messages


def test_contents_to_agui_user_text() -> None:
    """user 纯文本：content 字符串 → ExtendUserMessage。"""
    records = [{"id": "u1", "role": "user", "content": "hello", "status": "complete"}]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendUserMessage)
    assert messages[0].content == "hello"
    assert messages[0].role == "user"
    assert messages[0].status == "complete"


def test_contents_to_agui_user_multimodal_json() -> None:
    """user 多模态：content 为 JSON 字符串数组 → 解析为 InputContent 数组，binary 项 mimeType。"""
    content = json.dumps(
        [
            {"type": "text", "text": "看图"},
            {
                "type": "binary",
                "mime_type": "image/png",
                "url": "http://x/a.png",
                "id": "img1",
                "data": "",
                "filename": "a.png",
            },
        ]
    )
    records = [{"id": "u2", "role": "user", "content": content, "status": "complete"}]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendUserMessage)
    assert isinstance(messages[0].content, list)
    # ExtendUserMessage.content 为 List[InputContent]（pydantic 模型，非 dict），
    # 嵌套 binary 项的 mime_type 字段在 SSE 序列化时经 to_camel 输出为 mimeType。
    assert messages[0].content[0].type == "text"
    assert messages[0].content[0].text == "看图"
    assert messages[0].content[1].type == "binary"
    assert messages[0].content[1].mime_type == "image/png"


def test_contents_to_agui_user_multimodal_list_not_json() -> None:
    """user 多模态：content 已是 Python list（非字符串）→ 直接映射，不报错。"""
    records = [
        {
            "id": "u3",
            "role": "user",
            "content": [
                {"type": "binary", "mime_type": "image/jpeg", "url": "http://x/b.jpg"},
                {"type": "text", "text": "描述"},
            ],
            "status": "complete",
        }
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendUserMessage)
    assert isinstance(messages[0].content, list)
    assert messages[0].content[0].type == "binary"
    assert messages[0].content[0].mime_type == "image/jpeg"
    assert messages[0].content[1].type == "text"


def test_contents_to_agui_assistant_keeps_think_html() -> None:
    """assistant 含 think HTML：content 原样保留（不剥离 <think> 块）。"""
    records = [{"id": "a1", "role": "assistant", "content": "<think>推理</think>最终答案", "status": "complete"}]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendAssistantMessage)
    assert messages[0].content == "<think>推理</think>最终答案"


def test_contents_to_agui_tool_maps_tool_call_id() -> None:
    """tool：tool_call_id 从记录读取，duration 透传。"""
    records = [
        {"id": "t1", "role": "tool", "content": "结果", "tool_call_id": "call-1", "duration": 1.5, "status": "complete"}
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendToolMessage)
    assert messages[0].tool_call_id == "call-1"
    assert messages[0].duration == 1.5
    assert messages[0].content == "结果"


def test_contents_to_agui_activity_knowledge_rag_camelcase() -> None:
    """activity 知识库召回：嵌套 referenceDocument/originFileUrl camelCase 手工映射。"""
    records = [
        {
            "id": "act1",
            "role": "activity",
            "activity_type": "knowledge_rag",
            "content": {
                "content": "召回文本",
                "reference_document": [
                    {"name": "doc", "origin_file_url": "http://x/doc.pdf", "url": "http://x/doc.pdf"}
                ],
            },
            "status": "complete",
        }
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendActivityMessage)
    assert messages[0].activity_type == "knowledge_rag"
    content = messages[0].content
    assert isinstance(content, dict)
    assert content["referenceDocument"][0]["originFileUrl"] == "http://x/doc.pdf"
    assert content["referenceDocument"][0]["name"] == "doc"


def test_contents_to_agui_activity_reference_document_camelcase() -> None:
    """activity reference_document：content 为引用数组，逐项 origin_file_url→originFileUrl 映射。"""
    records = [
        {
            "id": "act2",
            "role": "activity",
            "activity_type": "reference_document",
            "content": [
                {"name": "doc-a", "origin_file_url": "http://x/a.pdf", "url": "http://x/a.pdf"},
                {"name": "doc-b", "origin_file_url": "http://x/b.pdf", "url": "http://x/b.pdf"},
            ],
            "status": "complete",
        }
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendActivityMessage)
    assert messages[0].activity_type == "reference_document"
    content = messages[0].content
    assert isinstance(content, list)
    assert content[0]["originFileUrl"] == "http://x/a.pdf"
    assert content[0]["name"] == "doc-a"
    assert content[0]["url"] == "http://x/a.pdf"
    assert content[1]["originFileUrl"] == "http://x/b.pdf"
    assert content[1]["name"] == "doc-b"
    assert content[1]["url"] == "http://x/b.pdf"


def test_contents_to_agui_interrupt_passthrough() -> None:
    """interrupt：content/name 原样透传。"""
    records = [
        {
            "id": "int1",
            "role": "interrupt",
            "content": {"outcome": {"type": "interrupt", "interrupts": [{"interruptId": "i1"}]}},
            "name": "approve",
            "status": "complete",
        }
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendInterruptMessage)
    assert messages[0].content == {"outcome": {"type": "interrupt", "interrupts": [{"interruptId": "i1"}]}}
    assert messages[0].name == "approve"


def test_contents_to_agui_info_and_reasoning() -> None:
    """info：content 字符串；reasoning：content list/JSON 字符串 → ReasoningMessage。"""
    records = [
        {"id": "info1", "role": "info", "content": "系统提示", "status": "complete"},
        {
            "id": "re1",
            "role": "reasoning",
            "content": json.dumps(["思考", "过程"]),
            "duration": 2.0,
            "status": "complete",
        },
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 2
    assert isinstance(messages[0], ExtendInfoMessage)
    assert messages[0].content == "系统提示"
    assert isinstance(messages[1], ReasoningMessage)
    assert messages[1].content == ["思考", "过程"]
    assert messages[1].duration == 2.0


def test_contents_to_agui_system_guide_role() -> None:
    """system/guide：content 原样保留（不丢弃），role 透传。"""
    records = [
        {"id": "s1", "role": "system", "content": "系统指令", "status": "complete"},
        {"id": "g1", "role": "guide", "content": "引导语", "status": "complete"},
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 2
    assert isinstance(messages[0], ExtendSystemMessage)
    assert messages[0].content == "系统指令"
    assert messages[0].role == "system"
    assert messages[1].content == "引导语"


def test_contents_to_agui_malformed_record_does_not_raise() -> None:
    """异常容错：缺 role / 非法 JSON content 不抛异常，坏记录安全跳过/降级。"""
    records = [
        {"id": "bad1", "content": "no role here"},
        {"id": "ok1", "role": "user", "content": "正常消息", "status": "complete"},
        {"id": "bad2", "role": "user", "content": "{invalid json", "status": "complete"},
    ]
    messages = contents_to_agui_messages(records)

    # 缺 role 的 bad1 被跳过；ok1 与 bad2（非法 JSON 文本按纯文本保留）两条均存活。
    # 精确断言 ==2 并逐 id 校验，防止回归静默丢弃合法记录仍被 >=1 放过。
    # （ExtendMessage 为 Annotated 判别联合，运行时 isinstance 需用基类 ExtendBaseMessage 检查）
    assert len(messages) == 2
    assert all(isinstance(m, ExtendBaseMessage) for m in messages)
    assert {m.id for m in messages} == {"ok1", "bad2"}
    assert any(m.id == "ok1" and m.content == "正常消息" for m in messages)
    assert any(m.id == "bad2" and m.content == "{invalid json" for m in messages)


def test_contents_to_agui_assistant_nested_tool_calls() -> None:
    """assistant tool_calls：落库 OpenAI 嵌套 ``function`` 形态 → 正确读取 name/arguments。"""
    records = [
        {
            "id": "a-tc1",
            "role": "assistant",
            "content": "",
            "status": "complete",
            "tool_calls": [
                {
                    "id": "call_7f44449500da47ce84830c9e",
                    "type": "function",
                    "function": {
                        "name": "ask_user_question",
                        "mcp_name": "",
                        "arguments": '{"questions": [{"header": "问题 1", "question": "您今天心情怎么样？"}]}',
                        "description": "",
                    },
                }
            ],
        }
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendAssistantMessage)
    assert messages[0].tool_calls is not None
    assert len(messages[0].tool_calls) == 1
    tc = messages[0].tool_calls[0]
    # 嵌套 function 形态的 name/arguments 必须被读取，而非顶层缺失时静默置空（CR-02）
    assert tc.function.name == "ask_user_question"
    assert len(tc.function.arguments) > 2
    assert "questions" in tc.function.arguments


def test_contents_to_agui_platform_status_domain() -> None:
    """平台 status 域（success/fail/loading/pending）→ AG-UI 域归一化，不抛异常（CR-01）。"""
    records = [
        {"id": "st-success", "role": "tool", "content": "ok", "status": "success"},
        {"id": "st-fail", "role": "tool", "content": "boom", "status": "fail"},
        {"id": "st-loading", "role": "assistant", "content": "", "status": "loading"},
        {"id": "st-pending", "role": "user", "content": "hi", "status": "pending"},
        {"id": "st-unknown", "role": "user", "content": "hi2", "status": "bogus-status"},
    ]
    messages = contents_to_agui_messages(records)

    by_id = {m.id: m for m in messages}
    assert len(by_id) == 5
    assert by_id["st-success"].status == "complete"
    # fail → error：tool 分支 error 时 content 置空并写入 error 字段
    assert by_id["st-fail"].status == "error"
    assert by_id["st-fail"].content == ""
    assert by_id["st-fail"].error == "boom"
    assert by_id["st-loading"].status == "streaming"
    assert by_id["st-pending"].status == "pending"
    assert by_id["st-unknown"].status == "complete"


def test_contents_to_agui_ai_and_pause_normalize_to_assistant() -> None:
    """ai/pause → assistant（两域统一）：role 归一 assistant，content 原样保留。"""
    records = [
        {"id": "ai1", "role": "ai", "content": "AI 回复内容", "status": "complete"},
        {"id": "p1", "role": "pause", "content": "暂停等待用户输入", "status": "complete"},
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 2
    for message in messages:
        assert isinstance(message, ExtendAssistantMessage)
        assert message.role == "assistant"
    assert messages[0].content == "AI 回复内容"
    assert messages[1].content == "暂停等待用户输入"


def test_contents_to_agui_user_image_becomes_multimodal() -> None:
    """user-image：提取 Markdown 图片链接为 binary/InputContent 多模态形态 → ExtendUserMessage。"""
    records = [
        {
            "id": "img1",
            "role": "user-image",
            "content": "![file](http://example.com/files/a.png/file.png)",
            "status": "complete",
        }
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendUserMessage)
    assert messages[0].role == "user"
    assert isinstance(messages[0].content, list)
    assert messages[0].content[0].type == "binary"
    assert messages[0].content[0].url == "http://example.com/files/a.png/file.png"
    # 提取失败（非法 Markdown 图片链接）时不抛错阻塞快照，content 原样保留
    records_bad = [{"id": "img2", "role": "user-image", "content": "没有图片链接的纯文本", "status": "complete"}]
    bad = contents_to_agui_messages(records_bad)
    assert len(bad) == 1
    assert bad[0].content == "没有图片链接的纯文本"


def test_contents_to_agui_assistant_artifacts_from_builtin_property() -> None:
    """assistant artifacts：从 builtin_property 显式读取，归入 property["artifacts"]。"""
    records = [
        {
            "id": "a-art1",
            "role": "assistant",
            "content": "生成了文件",
            "builtin_property": {
                "artifacts": [{"outputId": "out-1", "type": "file", "name": "报告.pdf", "size": 1024}]
            },
            "status": "complete",
        },
        # 无 artifacts 时不写 property
        {"id": "a-plain", "role": "assistant", "content": "无产物", "status": "complete"},
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 2
    assert messages[0].property == {
        "artifacts": [{"outputId": "out-1", "type": "file", "name": "报告.pdf", "size": 1024}]
    }
    assert messages[1].property is None


def test_contents_to_agui_chatprompt_shape_status_and_tool_calls() -> None:
    """ChatPrompt 单账本形状：status/tool_calls 从 builtin_property 读取。"""
    records = [
        {
            "id": "cp1",
            "role": "assistant",
            "content": "",
            "builtin_property": {
                "status": "success",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city": "广州"}'},
                    }
                ],
            },
        }
    ]
    messages = contents_to_agui_messages(records)

    assert len(messages) == 1
    assert isinstance(messages[0], ExtendAssistantMessage)
    assert messages[0].status == "complete"  # success → complete
    assert messages[0].tool_calls is not None
    assert messages[0].tool_calls[0].function.name == "get_weather"
