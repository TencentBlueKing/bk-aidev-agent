# -*- coding: utf-8 -*-
"""``set_chat_request`` / ``set_llm_request`` / ``set_chat_response`` 单元测试。

覆盖 finish_reasons 提取与 OTel parts 模型写入（gen_ai.input.messages / gen_ai.output.messages）。
"""

import json

import pytest
from aidev_agent.config import BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH, BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH
from aidev_agent.packages.opentelemetry.span_utils import (
    SpanHolder,
    _message_type_to_role,
    get_model_name_for_response,
    set_chat_request,
    set_chat_response,
    set_llm_request,
    set_tool_request,
    set_tool_response,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture
def span_and_attributes():
    """给出一个可记录属性的 span，返回 (span, attributes 读取函数)。"""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer(__name__).start_as_current_span("llm.generate") as span:
        yield span, lambda: span.attributes


def _make_response(finish_reasons):
    """按给定 finish_reason 列表构造 LLMResult（None 表示 generation_info 不带该键）。"""
    generations = [
        ChatGeneration(
            message=AIMessage(content="答案"),
            generation_info=None if reason is None else {"finish_reason": reason},
        )
        for reason in finish_reasons
    ]
    return LLMResult(generations=[generations])


@pytest.mark.parametrize(
    "finish_reasons, expected",
    [(["stop"], ["stop"]), (["stop", "stop"], ["stop", "stop"]), (["length", "tool_calls"], ["length", "tool_calls"])],
)
def test_set_chat_response_writes_finish_reasons(span_and_attributes, finish_reasons, expected):
    """Test 1: finish_reason 与每个 generation 一一对应按序写入 gen_ai.response.finish_reasons"""
    span, attributes = span_and_attributes
    set_chat_response(span, _make_response(finish_reasons))
    assert list(attributes()["gen_ai.response.finish_reasons"]) == expected


@pytest.mark.parametrize("finish_reasons", [[None], [None, None], []])
def test_set_chat_response_skips_finish_reasons_when_missing(span_and_attributes, finish_reasons):
    """Test 2: 无 finish_reason 时不写该属性且不抛异常"""
    span, attributes = span_and_attributes
    set_chat_response(span, _make_response(finish_reasons))
    assert "gen_ai.response.finish_reasons" not in attributes()


def _make_response_with_metadata(llm_output=None, generation_info=None):
    """构造带 llm_output / 首 generation 的 generation_info 的 LLMResult。"""
    return LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案"), generation_info=generation_info)]],
        llm_output=llm_output,
    )


# `llm_output={}`：llm_output 非 None 但取不到值时回落 generation_info（现有用例只覆盖 `llm_output=None`）
@pytest.mark.parametrize(
    "llm_output, generation_info, expected",
    [
        ({"model_name": "qwen3"}, None, "qwen3"),  # llm_output 主源
        ({"model_id": "deepseek-v4"}, None, "deepseek-v4"),  # model_id 回落
        (None, {"model_name": "hy3"}, "hy3"),  # llm_output 为 None，流式 generation_info 回落
        ({}, {"model_name": "hy3"}, "hy3"),  # `{}` 与 None 等效，仍回落 generation_info
        ({}, None, None),  # 两源皆无 -> None
    ],
)
def test_get_model_name_for_response(llm_output, generation_info, expected):
    """llm_output 优先、流式回落 generation_info、两源皆无返回 None"""
    response = _make_response_with_metadata(llm_output=llm_output, generation_info=generation_info)
    assert get_model_name_for_response(response) == expected


def test_set_chat_response_metadata_from_llm_output(span_and_attributes):
    """非流式路径：model/id 取 llm_output，无 ttfc → stream=False 且 ttfc 空串，status=completed"""
    span, attributes = span_and_attributes
    set_chat_response(span, _make_response_with_metadata(llm_output={"model_name": "qwen3", "id": "chatcmpl-9"}))
    assert attributes()["gen_ai.response.model"] == "qwen3"
    assert attributes()["gen_ai.response.id"] == "chatcmpl-9"
    assert attributes()["gen_ai.request.stream"] is False
    assert attributes()["gen_ai.response.time_to_first_chunk"] == ""
    assert attributes()["gen_ai.response.status"] == "completed"


def test_set_chat_response_metadata_from_generation_info(span_and_attributes):
    """流式路径：model/id/ttfc 取首 generation 的 generation_info（llm_output 为 None）"""
    span, attributes = span_and_attributes
    response = _make_response_with_metadata(
        generation_info={"model_name": "served-model", "id": "chatcmpl-1", "time_to_first_chunk": 0.25}
    )
    set_chat_response(span, response)
    assert attributes()["gen_ai.response.model"] == "served-model"
    assert attributes()["gen_ai.response.id"] == "chatcmpl-1"
    assert attributes()["gen_ai.request.stream"] is True
    assert attributes()["gen_ai.response.time_to_first_chunk"] == 0.25
    assert attributes()["gen_ai.response.status"] == "completed"


def test_set_chat_response_metadata_prefers_llm_output(span_and_attributes):
    """两来源同时存在时 llm_output 优先"""
    span, attributes = span_and_attributes
    response = _make_response_with_metadata(
        llm_output={"model_id": "by-model-id"},
        generation_info={"model_name": "served-model", "id": "chatcmpl-1"},
    )
    set_chat_response(span, response)
    assert attributes()["gen_ai.response.model"] == "by-model-id"
    assert attributes()["gen_ai.response.id"] == "chatcmpl-1"


def test_set_chat_response_metadata_skips_empty_model_and_id(span_and_attributes):
    """两来源均无值时 model/id 键不写（不覆盖请求期值），stream/status 仍恒写入"""
    span, attributes = span_and_attributes
    set_chat_response(span, _make_response_with_metadata())
    assert "gen_ai.response.model" not in attributes()
    assert "gen_ai.response.id" not in attributes()
    assert attributes()["gen_ai.request.stream"] is False
    assert attributes()["gen_ai.response.status"] == "completed"


def _make_response_with_response_metadata(response_metadata):
    """构造 v2 聚合形状：generation_info 缺失，元数据落在 message.response_metadata。"""
    return LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案", response_metadata=response_metadata))]],
    )


def test_set_chat_response_metadata_from_response_metadata(span_and_attributes):
    """v2 聚合形状：generation_info 缺失时 model/id/ttfc 回落 message.response_metadata"""
    span, attributes = span_and_attributes
    response = _make_response_with_response_metadata(
        {"model_name": "served-model", "id": "chatcmpl-2", "time_to_first_chunk": 0.5}
    )
    set_chat_response(span, response)
    assert attributes()["gen_ai.response.model"] == "served-model"
    assert attributes()["gen_ai.response.id"] == "chatcmpl-2"
    assert attributes()["gen_ai.request.stream"] is True
    assert attributes()["gen_ai.response.time_to_first_chunk"] == 0.5


def test_set_chat_response_prefers_llm_output_over_response_metadata(span_and_attributes):
    """llm_output 与 response_metadata 同时存在时 llm_output 胜出"""
    span, attributes = span_and_attributes
    response = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="答案", response_metadata={"model_name": "v2"}))]],
        llm_output={"model_name": "v1", "id": "chatcmpl-v1"},
    )
    set_chat_response(span, response)
    assert attributes()["gen_ai.response.model"] == "v1"
    assert attributes()["gen_ai.response.id"] == "chatcmpl-v1"


@pytest.mark.parametrize("finish_reason, expected", [("stop", ["stop"]), (None, None)])
def test_set_chat_response_finish_reasons_falls_back_to_response_metadata(span_and_attributes, finish_reason, expected):
    """v2 聚合形状：finish_reason 回落 message.response_metadata，无值时不上报该属性"""
    span, attributes = span_and_attributes
    response = _make_response_with_response_metadata({"finish_reason": finish_reason})
    set_chat_response(span, response)
    if expected is None:
        assert "gen_ai.response.finish_reasons" not in attributes()
    else:
        assert list(attributes()["gen_ai.response.finish_reasons"]) == expected


def _make_holder(span):
    """构造 request 路径所需的 SpanHolder（token/context/children 非本测试关注项）。"""
    return SpanHolder(span=span, token=None, context=None, children=[], entity_name=None, entity_path="")


@pytest.mark.parametrize(
    "msg, role",
    [
        (HumanMessage(content="hi"), "user"),
        (SystemMessage(content="sys"), "system"),
        (AIMessage(content="hi"), "assistant"),
    ],
)
def test_set_chat_request_parts_structure(span_and_attributes, msg, role):
    """chat 输入按 [{role, parts}] 写入，role 映射正确且 text 落在 parts[0]"""
    span, attributes = span_and_attributes
    set_chat_request(span, {}, [[msg]], {}, _make_holder(span))
    messages = json.loads(attributes()["gen_ai.input.messages"])
    assert messages == [{"role": role, "parts": [{"type": "text", "content": msg.content}]}]


def test_set_chat_request_tool_message_uses_tool_call_response(span_and_attributes):
    """tool 角色且带 tool_call_id 的输入消息使用 tool_call_response part"""
    span, attributes = span_and_attributes
    msg = ToolMessage(content="res", tool_call_id="c1")
    set_chat_request(span, {}, [[msg]], {}, _make_holder(span))
    messages = json.loads(attributes()["gen_ai.input.messages"])
    assert messages == [{"role": "tool", "parts": [{"type": "tool_call_response", "id": "c1", "response": "res"}]}]


def test_set_chat_request_flattens_groups(span_and_attributes):
    """嵌套消息组扁平化为平铺 parts 消息数组"""
    span, attributes = span_and_attributes
    msgs = [[HumanMessage(content="a"), AIMessage(content="b")]]
    set_chat_request(span, {}, msgs, {}, _make_holder(span))
    messages = json.loads(attributes()["gen_ai.input.messages"])
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert [m["parts"][0]["content"] for m in messages] == ["a", "b"]


@pytest.mark.parametrize(
    "kwargs, expected_level",
    [
        ({"invocation_params": {"params": {"reasoning_effort": "high"}}}, "high"),  # 嵌套 params 解包
        ({"invocation_params": {"params": {"reasoning": "think"}}}, "think"),  # 嵌套 params 内 reasoning 键
        ({"invocation_params": {"reasoning_effort": "medium"}}, "medium"),  # invocation_params 顶层
        ({"reasoning_effort": "low"}, "low"),  # 裸 kwargs 兜底
        ({"invocation_params": {"params": {"max_tokens": 100}}}, ""),  # 有参数无 reasoning 键 -> 空串
        ({}, ""),  # 空 kwargs -> 空串
    ],
)
def test_set_chat_request_writes_reasoning_level(span_and_attributes, kwargs, expected_level):
    """chat 请求采样期写 gen_ai.request.reasoning.level：reasoning_effort/reasoning 双键取，取不到空串"""
    span, attributes = span_and_attributes
    set_chat_request(span, {}, [[HumanMessage(content="hi")]], kwargs, _make_holder(span))
    assert attributes()["gen_ai.request.reasoning.level"] == expected_level


@pytest.mark.parametrize("kwargs, expected", [({"invocation_params": {"stream": True}}, True), ({}, None)])
def test_set_chat_request_declares_stream_from_invocation_params(span_and_attributes, kwargs, expected):
    """请求期仅声明 invocation_params.stream（有键才写）；无该键时不写，留待响应期实化"""
    span, attributes = span_and_attributes
    set_chat_request(span, {}, [[HumanMessage(content="hi")]], kwargs, _make_holder(span))
    if expected is None:
        assert "gen_ai.request.stream" not in attributes()
    else:
        assert attributes()["gen_ai.request.stream"] is expected


def test_set_llm_request_parts_structure(span_and_attributes):
    """llm/prompt 输入映射为单条 user text part"""
    span, attributes = span_and_attributes
    set_llm_request(span, {}, ["你好"], {}, _make_holder(span))
    messages = json.loads(attributes()["gen_ai.input.messages"])
    assert messages == [{"role": "user", "parts": [{"type": "text", "content": "你好"}]}]


def test_set_chat_response_output_parts(span_and_attributes):
    """chat 输出为 assistant text part 数组"""
    span, attributes = span_and_attributes
    response = LLMResult(generations=[[ChatGeneration(message=AIMessage(content="答案"))]])
    set_chat_response(span, response)
    assert json.loads(attributes()["gen_ai.output.messages"]) == [
        {"role": "assistant", "parts": [{"type": "text", "content": "答案"}]}
    ]


def test_set_chat_response_output_tool_call_parts(span_and_attributes):
    """带 tool_calls 的 assistant 输出产生 tool_call part"""
    span, attributes = span_and_attributes
    message = AIMessage(content="", tool_calls=[{"name": "t", "args": {"a": 1}, "id": "c1", "type": "tool_call"}])
    set_chat_response(span, LLMResult(generations=[[ChatGeneration(message=message)]]))
    parts = json.loads(attributes()["gen_ai.output.messages"])[0]["parts"]
    assert {"type": "tool_call", "id": "c1", "name": "t", "arguments": {"a": 1}} in parts


def test_set_chat_request_truncation_semantics(span_and_attributes):
    """超长输入仍经 truncate_span_attribute，original_length/truncated 语义不变"""
    span, attributes = span_and_attributes
    long_text = "x" * (BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH + 100)
    set_chat_request(span, {}, [[HumanMessage(content=long_text)]], {}, _make_holder(span))
    attrs = attributes()
    assert attrs["llm.input_original_length"] > BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH
    assert attrs["llm.input_truncated"] is True
    assert len(attrs["llm.input"]) <= BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH
    assert len(attrs["gen_ai.input.messages"]) <= BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH


def test_set_tool_request_writes_base_and_gen_ai_keys(span_and_attributes):
    """工具请求装配：基础键 + gen_ai 键 + description 经上限截断"""
    span, attributes = span_and_attributes
    long_description = "x" * (BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH + 100)
    set_tool_request(
        span,
        {"description": long_description},
        "1+1",
        {"tool_call_id": "call-1"},
        None,
        tool_name="calculator",
        call_index=3,
    )
    attrs = attributes()
    assert attrs["tool.name"] == "calculator"
    assert attrs["tool.call_index"] == 3
    assert attrs["tool.input"] == "1+1"
    assert attrs["gen_ai.tool.name"] == "calculator"
    assert attrs["gen_ai.tool.type"] == "function"
    assert attrs["gen_ai.tool.call.id"] == "call-1"
    assert attrs["gen_ai.tool.call.arguments"] == "1+1"
    assert attrs["gen_ai.tool.description"] == long_description[-BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH:]


def test_set_tool_request_skips_absent_optional_keys(span_and_attributes):
    """无 tool_call_id → 空串兜底；serialized 无 description → 该键不写"""
    span, attributes = span_and_attributes
    set_tool_request(span, {}, "1+1", {}, None, tool_name="calculator", call_index=1)
    attrs = attributes()
    assert attrs["gen_ai.tool.call.id"] == ""
    assert "gen_ai.tool.description" not in attrs


@pytest.mark.parametrize(
    "metadata, expected, absent",
    [
        (
            {"mcp_name": "resource", "mcp_transport": "streamable_http"},
            {
                "tool.type": "mcp",
                "rpc.system.name": "jsonrpc",
                "mcp.method.name": "tools/call",
                "mcp.server.name": "resource",
                "mcp.transport": "streamable_http",
            },
            ["tool.code", "mcp.tool.name"],
        ),
        ({"mcp_name": "resource"}, {"mcp.transport": "unknown"}, ["tool.code"]),
        ({"tool_code": "get_ticket"}, {"tool.type": "http_api", "tool.code": "get_ticket"}, ["rpc.system.name"]),
        (None, {}, ["tool.type", "tool.code", "rpc.system.name"]),
    ],
)
def test_set_tool_request_metadata_branches(span_and_attributes, metadata, expected, absent):
    """metadata 分支：mcp 五键（tool.type/rpc.system.name/mcp.method.name/mcp.server.name/mcp.transport，transport 兜底 unknown）/ http_api 两键 / 无分支仅基础键"""
    span, attributes = span_and_attributes
    set_tool_request(span, {}, "{}", {}, metadata, tool_name="search", call_index=1)
    attrs = attributes()
    assert {key: attrs[key] for key in expected} == expected
    assert all(key not in attrs for key in absent)


@pytest.mark.parametrize(
    "output, expected",
    [
        ("42", "42"),
        ({"x": 1}, "{'x': 1}"),
        (ToolMessage(content="审批未通过", name="calculator", tool_call_id="call-1"), "审批未通过"),
    ],
)
def test_set_tool_response(span_and_attributes, output, expected):
    """工具结果装配：一律 str 转换写入 gen_ai.tool.call.result，消息对象只取 content"""
    span, attributes = span_and_attributes
    set_tool_response(span, output)
    assert attributes()["gen_ai.tool.call.result"] == expected


def test_set_tool_response_truncates_to_output_limit(span_and_attributes):
    """超长输出按输出上限从尾部保留"""
    span, attributes = span_and_attributes
    long_output = "x" * (BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH + 100)
    set_tool_response(span, long_output)
    assert attributes()["gen_ai.tool.call.result"] == long_output[-BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH:]


@pytest.mark.parametrize(
    "message_type, expected",
    [("human", "user"), ("ai", "assistant"), ("system", "system"), ("tool", "tool"), ("function", "tool")],
)
def test_message_type_to_role(message_type, expected):
    """LangChain type 到 OTel role 的映射"""
    assert _message_type_to_role(message_type) == expected


@pytest.mark.parametrize(
    "token_usage, expected_input, expected_cache_read, expected_cache_creation",
    [
        # 上报缓存字段：input 为含缓存总数，缓存键写数值，cache_write 与 cache_creation 同值
        (
            {
                "prompt_tokens": 30,
                "completion_tokens": 7,
                "total_tokens": 37,
                "cache_read_input_tokens": 8,
                "cache_creation_input_tokens": 12,
            },
            30,
            8,
            12,
        ),
        # 从未上报缓存字段：缓存三键写空串（与真 0 区分）
        ({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, 10, "", ""),
    ],
)
def test_set_chat_response_writes_usage_attributes(
    span_and_attributes, token_usage, expected_input, expected_cache_read, expected_cache_creation
):
    """set_chat_response 直写 gen_ai.usage.*：input 含缓存不双重计数，缓存 presence 语义，cache_write 双写"""
    span, attributes = span_and_attributes
    set_chat_response(span, _make_response_with_metadata(llm_output={"token_usage": token_usage}))
    assert attributes()["gen_ai.usage.input_tokens"] == expected_input
    assert attributes()["gen_ai.usage.output_tokens"] == token_usage["completion_tokens"]
    assert attributes()["gen_ai.usage.cache_read.input_tokens"] == expected_cache_read
    assert attributes()["gen_ai.usage.cache_creation.input_tokens"] == expected_cache_creation
    assert attributes()["gen_ai.usage.cache_write.input_tokens"] == expected_cache_creation


@pytest.mark.parametrize(
    "tools, expected",
    [
        # OpenAI 信封形：function 子对象内取 name/description/parameters
        (
            [
                {
                    "type": "function",
                    "function": {
                        "name": "calculator",
                        "description": "算数",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ],
            [
                {
                    "type": "function",
                    "name": "calculator",
                    "description": "算数",
                    "parameters": {"type": "object", "properties": {}},
                }
            ],
        ),
        # 扁平形：无 function 信封，直接取顶层字段
        (
            [{"name": "search", "description": "搜索"}],
            [{"type": "function", "name": "search", "description": "搜索", "parameters": None}],
        ),
        # functions 兜底键同样被收集
        (
            {"functions": [{"name": "legacy", "description": "旧式"}]},
            [{"type": "function", "name": "legacy", "description": "旧式", "parameters": None}],
        ),
        # 无工具：仍写空数组 JSON 串，键恒存在
        ({}, []),
    ],
)
def test_set_chat_request_writes_tool_definitions(span_and_attributes, tools, expected):
    """工具定义写官方键 gen_ai.tool.definitions：补必填 type=function，保留 name/description/parameters"""
    span, attributes = span_and_attributes
    invocation_params = tools if isinstance(tools, dict) else {"tools": tools}
    set_chat_request(
        span,
        {},
        [[HumanMessage(content="hi")]],
        {"invocation_params": invocation_params},
        _make_holder(span),
    )
    attrs = attributes()
    assert json.loads(attrs["gen_ai.tool.definitions"]) == expected
    assert "gen_ai.request.tools" not in attrs
