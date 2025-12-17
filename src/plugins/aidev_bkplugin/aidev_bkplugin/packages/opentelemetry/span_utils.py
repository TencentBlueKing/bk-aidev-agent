import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional, List, Union, Dict
from uuid import UUID

from langchain_core.messages import (
    BaseMessage, messages_to_dict,
)
from langchain_core.outputs import (
    LLMResult, Generation, ChatGeneration, GenerationChunk, ChatGenerationChunk,
)
from opentelemetry.context.context import Context
from opentelemetry.trace.span import Span

from aidev_bkplugin.packages.opentelemetry.utils import _set_span_attribute, CallbackFilteredJSONEncoder


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


def set_request_params(span, kwargs, span_holder: SpanHolder):
    if not span.is_recording():
        return
    # 设置请求的名称模型
    for model_tag in ("model", "model_id", "model_name"):
        if (model := kwargs.get(model_tag)) is not None:
            span_holder.request_model = model
            break
        elif (
            model := (kwargs.get("invocation_params") or {}).get(model_tag)
        ) is not None:
            span_holder.request_model = model
            break
    else:
        model = "unknown"
    _set_span_attribute(span, "gen_ai.request.model", model)
    _set_span_attribute(span, "gen_ai.response.model", model)
    # 设置请求的相关参数
    params = (
        kwargs["invocation_params"].get("params") or kwargs["invocation_params"]
        if "invocation_params" in kwargs
        else kwargs
    )
    _set_span_attribute(span, "gen_ai.request.max_tokens", params.get("max_tokens") or params.get("max_new_tokens"),)
    _set_span_attribute(span, "gen_ai.request.temperature", params.get("temperature"))
    _set_span_attribute(span, "gen_ai.request.top_p", params.get("top_p"))
    # 设置请求使用的工具
    tools = kwargs.get("invocation_params", {}).get("tools", []) + kwargs.get("invocation_params", {}).get("functions", [])
    tools_desc = [
        {
            "name": tool.get("function", tool).get("name"),
            "description": tool.get("function", tool).get("description"),
            "parameters": tool.get("function", tool).get("parameters"),
        }
        for tool in tools
    ]
    _set_span_attribute(span, "gen_ai.request.tools", json.dumps(tools_desc))


def set_llm_request(
    span: Span,
    serialized: dict[str, Any],
    prompts: list[str],
    kwargs: Any,
    span_holder: SpanHolder,
) -> None:
    set_request_params(span, kwargs, span_holder)
    for i, msg in enumerate(prompts):
        _set_span_attribute(
            span,
            f"llm.input" if i == 0 else f"llm.input{i}",
            json.dumps(msg)
        )


def set_chat_request(
    span: Span,
    serialized: dict[str, Any],
    messages: list[list[BaseMessage]],
    kwargs: Any,
    span_holder: SpanHolder,
) -> None:
    # 本部分由于做训练数据收集
    # 收集模型基本的配置：名称/核心参数/工具
    set_request_params(span, kwargs, span_holder)
    # 收集 prompt
    for i, message in enumerate(messages):
        _set_span_attribute(
            span,
            "llm.input" if i == 0 else f"llm.output{i}",
            json.dumps(messages_to_dict(message))
        )


def generation_to_dict(generation: Union[Generation, ChatGeneration, GenerationChunk, ChatGenerationChunk]):
    ret: Dict[str, Any] = { "role":  generation.type }
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
            tool_call_list.append({
                "id": tool_call_dict.get("id"),
                "name": tool_call_dict.get("function", {}).get("name") or tool_call_dict.get("name"),
                "arguments": json.dumps(tool_call_dict.get("function", {}).get("arguments") or tool_call_dict.get("args"), cls=CallbackFilteredJSONEncoder)
            })
        if tool_call_list:
            ret["tool_call"] = tool_call_list
    return ret

def set_chat_response(span: Span, response: LLMResult) -> None:
    for i, generations in enumerate(response.generations):
        _set_span_attribute(
            span,
            f"llm.output" if i == 0 else f"llm.output{i}",
            json.dumps([generation_to_dict(generation) for generation in generations])
        )
