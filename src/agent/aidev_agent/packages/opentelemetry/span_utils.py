import contextlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from langchain_core.messages import (
    BaseMessage,
    messages_to_dict,
)
from langchain_core.outputs import (
    ChatGeneration,
    ChatGenerationChunk,
    Generation,
    GenerationChunk,
    LLMResult,
)
from opentelemetry.context.context import Context
from opentelemetry.trace.span import Span

from aidev_agent.config import BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH, BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH

from .metrics import extract_token_usage as extract_metric_token_usage
from .utils import CallbackFilteredJSONEncoder, _set_span_attribute, extract_token_usage


def truncate_span_attribute(value: str, max_length: int) -> str:
    """按 Gateway 口径从尾部保留指定长度的属性值。"""
    return value if len(value) <= max_length else value[-max_length:]


@dataclass
class SpanHolder:
    """管理 Span 及其层级关系"""

    span: Span
    token: Optional[Any]  # context token
    context: Optional[Context]
    children: List[UUID]  # 子 Span 的 run_id 列表
    entity_name: Optional[str]
    entity_path: str
    start_time: float = field(default_factory=time.time)


def _set_content_attributes(
    span: Span,
    *,
    content_key: str,
    original_length_key: str,
    truncated_key: str,
    value: str,
    max_attribute_length: int,
) -> None:
    original_length = len(value)
    truncated = original_length > max_attribute_length
    _set_span_attribute(span, content_key, truncate_span_attribute(value, max_attribute_length))
    _set_span_attribute(span, original_length_key, original_length)
    _set_span_attribute(span, truncated_key, truncated)


def _message_type_to_role(message_type: str) -> str:
    """把 LangChain 消息 type 映射为 OTel 官方 role。"""
    if message_type == "human":
        return "user"
    elif message_type == "system":
        return "system"
    elif message_type == "ai":
        return "assistant"
    elif message_type in ("tool", "function"):
        return "tool"
    else:
        return message_type


def _content_to_parts(content) -> list:
    """把 LangChain 消息 content（str 或逐 block 列表）转成 OTel parts。"""
    if isinstance(content, str):
        return [{"type": "text", "content": content}] if content else []
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                if block:
                    parts.append({"type": "text", "content": block})
            elif isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "text":
                    text = block.get("text", "")
                    if text:
                        parts.append({"type": "text", "content": text})
                elif block_type == "image_url":
                    url = (block.get("image_url") or {}).get("url", "")
                    if url:
                        parts.append({"type": "uri", "modality": "image", "uri": url})
                elif block_type == "image":
                    parts.append(
                        {
                            "type": "blob",
                            "modality": "image",
                            "mime_type": block.get("media_type", block.get("mime_type", "")),
                            "content": block.get("data", ""),
                        }
                    )
                else:
                    parts.append({"type": "text", "content": json.dumps(block, cls=CallbackFilteredJSONEncoder)})
            else:
                parts.append({"type": "text", "content": str(block)})
        return parts
    return [{"type": "text", "content": str(content)}] if content else []


def _tool_calls_to_parts(tool_calls) -> list:
    """把 LangChain 工具调用转成 OTel tool_call parts。"""
    parts = []
    if not tool_calls:
        return parts
    for tc in tool_calls:
        tc_dict = dict(tc)
        tool_id = tc_dict.get("id", "")
        tool_name = tc_dict.get("name", tc_dict.get("function", {}).get("name", ""))
        tool_args = tc_dict.get("args", tc_dict.get("function", {}).get("arguments"))
        if isinstance(tool_args, str):
            with contextlib.suppress(json.JSONDecodeError, TypeError):
                tool_args = json.loads(tool_args)
        part = {"type": "tool_call", "id": tool_id, "name": tool_name}
        if tool_args is not None:
            part["arguments"] = tool_args
        parts.append(part)
    return parts


def _chat_message_to_parts_dict(msg: BaseMessage) -> dict:
    """把单条 LangChain 消息转为 OTel parts 模型消息字典。"""
    role = _message_type_to_role(msg.type)
    parts = []
    if role == "tool" and hasattr(msg, "tool_call_id"):
        content_str = (
            msg.content if isinstance(msg.content, str) else json.dumps(msg.content, cls=CallbackFilteredJSONEncoder)
        )
        parts = [{"type": "tool_call_response", "id": msg.tool_call_id, "response": content_str}]
    else:
        parts = _content_to_parts(msg.content)
        tool_calls = (
            getattr(msg, "tool_calls", None)
            if hasattr(msg, "tool_calls")
            else (msg.additional_kwargs or {}).get("tool_calls")
        )
        if role == "assistant" and tool_calls:
            parts.extend(_tool_calls_to_parts(tool_calls))
    return {"role": role, "parts": parts}


def set_request_params(span, kwargs, span_holder: SpanHolder):
    # Metrics still need the request model when tracing is disabled and the
    # callback receives a non-recording span.
    for model_tag in ("model", "model_id", "model_name"):
        if (model := kwargs.get(model_tag)) is not None or (
            model := (kwargs.get("invocation_params") or {}).get(model_tag)
        ) is not None:
            span_holder.request_model = model
            break
    else:
        model = "unknown"
    if not span.is_recording():
        return
    # 设置请求的名称模型
    _set_span_attribute(span, "gen_ai.request.model", model)
    # 设置请求的相关参数
    params = (
        kwargs["invocation_params"].get("params") or kwargs["invocation_params"]
        if "invocation_params" in kwargs
        else kwargs
    )
    _set_span_attribute(
        span,
        "gen_ai.request.max_tokens",
        params.get("max_tokens") or params.get("max_new_tokens"),
    )
    _set_span_attribute(span, "gen_ai.request.temperature", params.get("temperature"))
    _set_span_attribute(span, "gen_ai.request.top_p", params.get("top_p"))
    # gen_ai.request.stream：请求期仅声明配置值，实际调用模式在响应期按首 chunk 实化
    if "stream" in params:
        _set_span_attribute(span, "gen_ai.request.stream", bool(params["stream"]))
    # gen_ai.request.reasoning.level：值取发给 provider 的 reasoning 原串，
    # reasoning_effort 与 reasoning 双键兜底；取不到写空串保证键恒存在
    _set_span_attribute(
        span,
        "gen_ai.request.reasoning.level",
        params.get("reasoning_effort") or params.get("reasoning") or "",
    )
    # 工具定义：官方 gen_ai.tool.definitions（semconv gen-ai / ToolDefinitions schema）。
    # 官方 schema 必填 type 与 name，type 恒为 "function"；
    # description 与 parameters 属可选字段，官方「不建议默认上报」，
    # 此处为训练数据收集需要刻意保留，属有意为之的偏离。
    # OTel 属性模型不支持对象序列（utils 会把 list 内各项 str 化），
    # 故按官方允许的降级形态以 JSON 字符串承载。
    tools = kwargs.get("invocation_params", {}).get("tools", []) + kwargs.get("invocation_params", {}).get(
        "functions", []
    )
    tools_desc = [
        {
            "type": "function",
            "name": tool.get("function", tool).get("name"),
            "description": tool.get("function", tool).get("description"),
            "parameters": tool.get("function", tool).get("parameters"),
        }
        for tool in tools
    ]
    _set_span_attribute(span, "gen_ai.tool.definitions", json.dumps(tools_desc))


def set_llm_request(
    span: Span,
    serialized: dict[str, Any],
    prompts: list[str],
    kwargs: Any,
    span_holder: SpanHolder,
    max_attribute_length: int = BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH,
) -> None:
    set_request_params(span, kwargs, span_holder)
    for i, msg in enumerate(prompts):
        value = json.dumps(msg)
        _set_span_attribute(
            span,
            "llm.input" if i == 0 else f"llm.input{i}",
            truncate_span_attribute(value, max_attribute_length),
        )
    _set_content_attributes(
        span,
        content_key="gen_ai.input.messages",
        original_length_key="llm.input_original_length",
        truncated_key="llm.input_truncated",
        value=json.dumps(
            [{"role": "user", "parts": [{"type": "text", "content": p}]} for p in prompts],
            cls=CallbackFilteredJSONEncoder,
        ),
        max_attribute_length=max_attribute_length,
    )


def set_chat_request(
    span: Span,
    serialized: dict[str, Any],
    messages: list[list[BaseMessage]],
    kwargs: Any,
    span_holder: SpanHolder,
    max_attribute_length: int = BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH,
) -> None:
    # 本部分由于做训练数据收集
    # 收集模型基本的配置：名称/核心参数/工具
    set_request_params(span, kwargs, span_holder)
    # 收集 prompt
    for i, message in enumerate(messages):
        value = json.dumps(messages_to_dict(message))
        _set_span_attribute(
            span,
            "llm.input" if i == 0 else f"llm.output{i}",
            truncate_span_attribute(value, max_attribute_length),
        )
    _set_content_attributes(
        span,
        content_key="gen_ai.input.messages",
        original_length_key="llm.input_original_length",
        truncated_key="llm.input_truncated",
        value=json.dumps(
            [_chat_message_to_parts_dict(msg) for group in messages for msg in group],
            cls=CallbackFilteredJSONEncoder,
        ),
        max_attribute_length=max_attribute_length,
    )


def set_tool_request(
    span: Span,
    serialized: dict[str, Any],
    input_str: str,
    kwargs: Any,
    metadata: Optional[Dict[str, Any]],
    *,
    tool_name: str,
    call_index: int,
    max_attribute_length: int = BKAI_AGENT_MAX_INPUT_ATTRIBUTE_LENGTH,
) -> None:
    """把工具调用回调载荷装配为 tool span 属性（调用期一次性写入）。"""
    # 官方 tool 语义属性与既有 tool.* 并存，描述按输入上限截断防长文本膨胀
    _set_span_attribute(span, "gen_ai.tool.name", tool_name)
    tool_description = serialized.get("description") if isinstance(serialized, dict) else None
    if tool_description:
        _set_span_attribute(
            span, "gen_ai.tool.description", truncate_span_attribute(tool_description, max_attribute_length)
        )
    _set_span_attribute(span, "gen_ai.tool.type", "function")
    # 官方 tool.call.*：id 取回调 kwargs 的 tool_call_id（on_tool_end 分发不带该键，故建 span 期写）；
    # arguments/result 平台不吃 object，统一字符串
    _set_span_attribute(span, "gen_ai.tool.call.id", kwargs.get("tool_call_id") or "")
    _set_span_attribute(span, "gen_ai.tool.call.arguments", truncate_span_attribute(input_str, max_attribute_length))
    # 历史兼容 span，不要移除
    _set_span_attribute(span, "tool.name", tool_name)
    _set_span_attribute(span, "tool.call_index", call_index)
    _set_span_attribute(span, "tool.input", truncate_span_attribute(input_str, max_attribute_length))
    metadata = metadata or {}
    if mcp_name := metadata.get("mcp_name"):
        # MCP 工具：在既有 tool.* 之上补充 MCP 语义键，transport 缺失时兜底 "unknown"
        _set_span_attribute(span, "tool.type", "mcp")
        _set_span_attribute(span, "rpc.system.name", "jsonrpc")
        _set_span_attribute(span, "mcp.method.name", "tools/call")
        _set_span_attribute(span, "mcp.server.name", str(mcp_name))
        _set_span_attribute(span, "mcp.transport", str(metadata.get("mcp_transport") or "unknown"))
    elif tool_code := metadata.get("tool_code"):
        # HTTP 接口型工具：以 tool.code 标识调用的接口
        _set_span_attribute(span, "tool.type", "http_api")
        _set_span_attribute(span, "tool.code", str(tool_code))


def set_tool_response(
    span: Span,
    output: Any,
    max_attribute_length: int = BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH,
) -> None:
    """把工具调用结果装配为 tool span 属性（gen_ai.tool.call.result 唯一写入点）。

    output 一律转字符串（dict 输出亦 str()），按输出上限截断；输出为消息对象
    （如审批拒绝返回的 ToolMessage）时只取 content，否则 str() 会把
    name/tool_call_id/status 等元信息一起带进结果文本。
    """
    call_result = getattr(output, "content", output)
    _set_span_attribute(
        span,
        "gen_ai.tool.call.result",
        truncate_span_attribute(str(call_result), max_attribute_length),
    )


def generation_to_dict(generation: Union[Generation, ChatGeneration, GenerationChunk, ChatGenerationChunk]):
    ret: Dict[str, Any] = {"role": generation.type}
    # 获取输出
    content = None
    if hasattr(generation, "text") and generation.text:
        content = generation.text
    elif hasattr(generation, "message") and generation.message and generation.message.content:
        if isinstance(generation.message.content, str):
            content = generation.message.content
        else:
            content = json.dumps(generation.message.content, cls=CallbackFilteredJSONEncoder)
    if content:
        ret["content"] = content
    # 获取 finish_reason
    if generation.generation_info and generation.generation_info.get("finish_reason"):
        ret["finish_reason"] = generation.generation_info.get("finish_reason")
    # 获取 tool_calls
    if hasattr(generation, "message") and generation.message:
        if function_call := generation.message.additional_kwargs.get("function_call"):
            ret["function_call"] = {
                "name": function_call.get("name"),
                "arguments": function_call.get("arguments"),
            }
        # Handle new tool_calls format (multiple tool calls)
        tool_calls = (
            generation.message.tool_calls
            if hasattr(generation.message, "tool_calls")
            else generation.message.additional_kwargs.get("tool_calls")
        )
        if tool_calls is None:
            tool_calls = []
        tool_call_list = []
        for idx, tool_call in enumerate(tool_calls):
            tool_call_dict = dict(tool_call)
            tool_call_list.append(
                {
                    "id": tool_call_dict.get("id"),
                    "name": tool_call_dict.get("function", {}).get("name") or tool_call_dict.get("name"),
                    "arguments": json.dumps(
                        tool_call_dict.get("function", {}).get("arguments") or tool_call_dict.get("args"),
                        cls=CallbackFilteredJSONEncoder,
                    ),
                }
            )
        if tool_call_list:
            ret["tool_call"] = tool_call_list
    return ret


def set_chat_response(
    span: Span,
    response: LLMResult,
    max_attribute_length: int = BKAI_AGENT_MAX_OUTPUT_ATTRIBUTE_LENGTH,
) -> None:
    """响应侧 span 属性唯一写入点。

    覆盖：响应内容与 OTel parts 消息、llm.output*、finish_reasons、响应元数据
    （模型名/响应 id/调用模式/ttfc/状态）、gen_ai.usage.* token 用量。
    """
    output_messages = []
    for generations in response.generations:
        for generation in generations:
            if hasattr(generation, "message") and generation.message and hasattr(generation.message, "type"):
                output_messages.append(_chat_message_to_parts_dict(generation.message))
            else:
                role = "assistant"
                parts = [{"type": "text", "content": generation.text}] if getattr(generation, "text", "") else []
                output_messages.append({"role": role, "parts": parts})
    for i, generations in enumerate(response.generations):
        value = json.dumps([generation_to_dict(generation) for generation in generations])
        _set_span_attribute(
            span,
            "llm.output" if i == 0 else f"llm.output{i}",
            truncate_span_attribute(value, max_attribute_length),
        )
    _set_content_attributes(
        span,
        content_key="gen_ai.output.messages",
        original_length_key="llm.output_original_length",
        truncated_key="llm.output_truncated",
        value=json.dumps(output_messages, cls=CallbackFilteredJSONEncoder),
        max_attribute_length=max_attribute_length,
    )
    _set_finish_reasons(span, response)
    _set_response_metadata(span, response)
    _set_usage_attributes(span, response)


def _set_usage_attributes(span: Span, response: LLMResult) -> None:
    """gen_ai.usage.* 响应侧统一写入点：双提取器口径 + 缓存 presence 语义。

    provider 原始口径（utils 提取器）负责 output/reasoning；归一化口径（metrics
    提取器）负责 input 总量与缓存拆分。两者均为纯函数，可独立重复调用。
    """
    usage = extract_token_usage(response)
    metric_usage = extract_metric_token_usage(response)
    if usage is not None:
        _set_span_attribute(span, "gen_ai.usage.output_tokens", usage["output_tokens"])
        # 扩展字段：官方扁平化 semconv 命名，仅当模型返回时设置
        if usage.get("reasoning_tokens") is not None:
            _set_span_attribute(span, "gen_ai.usage.reasoning.output_tokens", usage["reasoning_tokens"])
    if metric_usage is not None:
        # input_tokens 为含缓存总数（归一化非缓存 + cache_read + cache_creation），
        # 与 provider 计费口径一致（OpenAI prompt/completion 本就含缓存），对齐官方语义：
        # metrics 提取器已把 provider 含缓存总数还原为非缓存分量，三项求和恰好还原 provider
        # 总数（OpenAI prompt_tokens 形状），绝不能再叠加 provider 已含缓存的总数，否则双重计数
        _set_span_attribute(
            span,
            "gen_ai.usage.input_tokens",
            metric_usage["input_tokens"]
            + metric_usage["cache_read_input_tokens"]
            + metric_usage["cache_creation_input_tokens"],
        )
    elif usage is not None:
        # metrics 提取器无结果的罕见场景：回落 provider 原始值，不叠加缓存分量
        _set_span_attribute(span, "gen_ai.usage.input_tokens", usage["input_tokens"])
    # 缓存用量统一由 metrics 提取器负责（读取的 key 最全）。
    # "有原始缓存字段写该值（含 0）、从未出现写空串"：用 presence 信号区分归 0 与真 0，字段恒存在
    if metric_usage is not None and metric_usage.get("has_cache_fields"):
        cache_read = metric_usage["cache_read_input_tokens"]
        cache_creation = metric_usage["cache_creation_input_tokens"]
    else:
        cache_read = cache_creation = ""
    _set_span_attribute(span, "gen_ai.usage.cache_read.input_tokens", cache_read)
    _set_span_attribute(span, "gen_ai.usage.cache_creation.input_tokens", cache_creation)
    # 官方新名与既有 cache_creation 同值双写，旧属性保留
    _set_span_attribute(span, "gen_ai.usage.cache_write.input_tokens", cache_creation)


def get_model_name_for_response(response: LLMResult) -> Optional[str]:
    """从 LLMResult 解析 served 模型名：llm_output（model_name/model_id）优先，
    流式路径 llm_output 为 None 时回落首 generation 的 generation_info（served
    模型名由末 chunk 携带）。两源皆无返回 None。
    """
    model_name = None
    if response.llm_output is not None:
        model_name = response.llm_output.get("model_name") or response.llm_output.get("model_id")
    if model_name is None:
        generations = response.generations or [[]]
        first_gen = generations[0][0] if generations[0] else None
        model_name = (getattr(first_gen, "generation_info", None) or {}).get("model_name")
    return model_name


def _set_response_metadata(span: Span, response: LLMResult) -> None:
    """响应侧属性唯一写入点：模型名/响应 id/实际调用模式/首 chunk 耗时/结束状态。

    模型名与响应 id 优先取 llm_output（非流式路径），其次 generation_info（v1 流式聚合，
    llm_output 为 None，served 模型名与 provider id 由末 chunk 携带），最后回落
    message.response_metadata（v2 流式聚合，chunk 的 generation_info 被桥接进该字段）；
    三源皆无则跳过，不覆盖请求期值。
    """
    generations = response.generations or [[]]
    first_gen = generations[0][0] if generations[0] else None
    gen_info = getattr(first_gen, "generation_info", None) or {}
    meta = getattr(getattr(first_gen, "message", None), "response_metadata", None) or {}
    llm_output = response.llm_output or {}

    model_name = get_model_name_for_response(response) or meta.get("model_name")
    if model_name:
        _set_span_attribute(span, "gen_ai.response.model", model_name)
    response_id = llm_output.get("id") or gen_info.get("id") or meta.get("id")
    if response_id:
        _set_span_attribute(span, "gen_ai.response.id", response_id)

    # 实际调用模式实化：首 chunk 携带 ttfc 即为流式，覆盖请求期声明的配置值
    ttfc = gen_info.get("time_to_first_chunk")
    if ttfc is None:
        ttfc = meta.get("time_to_first_chunk")
    if ttfc is not None:
        _set_span_attribute(span, "gen_ai.request.stream", True)
        _set_span_attribute(span, "gen_ai.response.time_to_first_chunk", float(ttfc))
    else:
        _set_span_attribute(span, "gen_ai.request.stream", False)
        _set_span_attribute(span, "gen_ai.response.time_to_first_chunk", "")
    # 官方响应状态枚举：正常结束为 completed（failed 由 on_llm_error 写入）
    _set_span_attribute(span, "gen_ai.response.status", "completed")


def _set_finish_reasons(span: Span, response: LLMResult) -> None:
    """把每个 generation 的 finish_reason 按序写入官方数组属性（与 generation 一一对应），缺失则不上报。

    reason 优先取 generation_info（v1 流式聚合），回落 message.response_metadata
    （v2 流式聚合把 chunk 的 generation_info 合并进该字段）。
    """
    finish_reasons: List[str] = []
    for generations in response.generations or []:
        for generation in generations:
            reason = (generation.generation_info or {}).get("finish_reason") or (
                getattr(generation.message, "response_metadata", None) or {}
            ).get("finish_reason")
            if reason:
                finish_reasons.append(reason)
    if finish_reasons:
        _set_span_attribute(span, "gen_ai.response.finish_reasons", finish_reasons)
