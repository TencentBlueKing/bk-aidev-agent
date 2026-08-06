import json
import re
import uuid
from collections.abc import Iterator
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from ag_ui.core import (
    BinaryInputContent,
    TextInputContent,
)
from ag_ui.core.events import (
    BaseEvent,
    EventType,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ThinkingTextMessageContentEvent,
    ThinkingTextMessageEndEvent,
    ThinkingTextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from .events import ExtendToolCallResultEvent, ExtendToolCallStartEvent
from .event_builders import TOOL_CALLING_PLACEHOLDER
from .types import (
    ActivityMessage,
    InfoMessage,
    InterruptMessage,
    LangGraphReasoning,
    ReasoningMessage,
    SchemaKeys,
    State,
)
from .types import (
    ExtendActivityMessage as AGUIActivityMessage,
)
from .types import (
    ExtendAssistantMessage as AGUIAssistantMessage,
)
from .types import (
    ExtendFunctionCall as AGUIFunctionCall,
)
from .types import (
    ExtendInfoMessage as AGUIInfoMessage,
)
from .types import (
    ExtendInterruptMessage as AGUIInterruptMessage,
)
from .types import (
    ExtendMessage as AGUIMessage,
)
from .types import (
    ExtendSystemMessage as AGUISystemMessage,
)
from .types import (
    ExtendToolCall as AGUIToolCall,
)
from .types import (
    ExtendToolMessage as AGUIToolMessage,
)
from .types import (
    ExtendUserMessage as AGUIUserMessage,
)
from ...enums import PromptRole

DEFAULT_SCHEMA_KEYS = ["tools"]


def get_schema_keys(graph, config, constant_schema_keys: list[str]) -> SchemaKeys:
    """独立计算 graph 的 schema keys（11.8: 从 agent.py.get_schema_keys 抽出）。

    接收 graph 和 constant_schema_keys 参数（替代 self.graph / self.constant_schema_keys），
    使 chat.py 可在 agui_entry 构造前直接调用，消除循环依赖。
    """
    try:
        input_schema = graph.get_input_jsonschema(config)
        output_schema = graph.get_output_jsonschema(config)
        config_schema = (
            graph.get_context_jsonschema(config).get("definitions", {}).get("Config", {}).get("properties", {})
        )

        input_schema_keys = list(input_schema["properties"].keys()) if "properties" in input_schema else []
        output_schema_keys = list(output_schema["properties"].keys()) if "properties" in output_schema else []
        config_schema_keys = list(config_schema.keys()) if isinstance(config_schema, dict) else []
        context_schema_keys = []

        if hasattr(graph, "context_schema") and graph.context_schema is not None:
            context_schema = graph.context_schema().schema()
            context_schema_keys = list(context_schema["properties"].keys()) if "properties" in context_schema else []

        return {
            "input": [*input_schema_keys, *constant_schema_keys],
            "output": [*output_schema_keys, *constant_schema_keys],
            "config": config_schema_keys,
            "context": context_schema_keys,
        }
    except Exception:
        return {
            "input": constant_schema_keys,
            "output": constant_schema_keys,
            "config": [],
            "context": [],
        }


def filter_object_by_schema_keys(obj: dict[str, Any], schema_keys: list[str]) -> dict[str, Any]:
    if not obj:
        return {}
    return {k: v for k, v in obj.items() if k in schema_keys}


def get_stream_payload_input(
    *,
    mode: str,
    state: State,
    schema_keys: SchemaKeys,
) -> State | None:
    input_payload = state if mode == "start" else None
    if input_payload and schema_keys and schema_keys.get("input"):
        input_payload = filter_object_by_schema_keys(input_payload, [*DEFAULT_SCHEMA_KEYS, *schema_keys["input"]])
    return input_payload


def stringify_if_needed(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    return json.dumps(item)


def parse_multimodal_content(content: Any) -> list[dict[str, Any]] | None:
    """将多模态 content 归一化为 dict 列表；无法识别时返回 None。"""
    if isinstance(content, list):
        if content and all(isinstance(item, dict) for item in content):
            return content
        return None

    if isinstance(content, str) and content.lstrip().startswith("["):
        try:
            parsed = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None
        if isinstance(parsed, list) and parsed and all(isinstance(item, dict) for item in parsed):
            return parsed
    return None


def convert_langchain_multimodal_to_agui(
    content: list[dict[str, Any]],
) -> list[TextInputContent | BinaryInputContent]:
    """Convert LangChain's multimodal content to AG-UI format."""
    agui_content = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "text":
                agui_content.append(TextInputContent(type="text", text=item.get("text", "")))
            elif item.get("type") == "binary":
                agui_content.append(
                    BinaryInputContent(
                        type="binary",
                        mime_type=item.get("mime_type") or "application/octet-stream",
                        url=item.get("url"),
                        data=item.get("data"),
                        filename=item.get("filename"),
                        id=item.get("id"),
                    )
                )
            elif item.get("type") == "image_url":
                image_url_data = item.get("image_url", {})
                url = image_url_data.get("url", "") if isinstance(image_url_data, dict) else image_url_data

                # Parse data URLs to extract base64 data
                if url.startswith("data:"):
                    # Format: data:mime_type;base64,data
                    parts = url.split(",", 1)
                    header = parts[0]
                    data = parts[1] if len(parts) > 1 else ""
                    mime_type = header.split(":")[1].split(";")[0] if ":" in header else "image/png"

                    agui_content.append(BinaryInputContent(type="binary", mime_type=mime_type, data=data))
                else:
                    # Regular URL or ID
                    agui_content.append(
                        BinaryInputContent(
                            type="binary",
                            mime_type="image/png",  # Default MIME type
                            url=url,
                        )
                    )
    return agui_content


def langchain_messages_to_agui(messages: list[BaseMessage]) -> list[AGUIMessage]:
    agui_messages: list[AGUIMessage] = []
    for message in messages:
        if isinstance(message, HumanMessage):
            # Handle multimodal content
            multimodal = parse_multimodal_content(message.content)
            if multimodal is not None:
                content = convert_langchain_multimodal_to_agui(multimodal)
            else:
                content = stringify_if_needed(resolve_message_content(message.content))

            agui_messages.append(
                AGUIUserMessage(
                    id=str(message.id),
                    role="user",
                    content=content,
                    name=message.name,
                )
            )
        elif isinstance(message, AIMessage):
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    AGUIToolCall(
                        id=str(tc["id"]),
                        type="function",
                        function=AGUIFunctionCall(
                            name=tc["name"],
                            arguments=json.dumps(tc.get("args", {})),
                            description=tc.get("description", ""),
                        ),
                    )
                    for tc in message.tool_calls
                ]

            if message.additional_kwargs.get("reasoning_content"):
                agui_messages.append(
                    ReasoningMessage(
                        id=str(message.id),
                        content=[message.additional_kwargs.get("reasoning_content")],
                        duration=message.additional_kwargs.get("reasoning_time", None),
                    )
                )

            # 占位符归一化：仅有 tool_calls、无文本输出的 assistant 消息 content 为
            # "正在调用工具..."，首帧 MESSAGES_SNAPSHOT 展示时归一化为 ""（与前端读接口一致）；
            # 消息本身及 tool_calls 保留。此归一化置于过滤之后、快照构建之前的最后一环。
            content = stringify_if_needed(resolve_message_content(message.content))
            if content == TOOL_CALLING_PLACEHOLDER:
                content = ""

            # 历史还原：本轮文件产物（经 AIMessage.additional_kwargs 透传），
            # 放到 property["artifacts"]，与 DB 落库结构、前端 IMessageProperty 契约对齐；
            # 仅在存在产物时才写 property，避免污染无产物的历史 assistant 消息。
            artifacts = message.additional_kwargs.get("artifacts")
            message_property = {"artifacts": artifacts} if artifacts else None
            agui_messages.append(
                AGUIAssistantMessage(
                    id=str(message.id),
                    role="assistant",
                    content=content,
                    tool_calls=tool_calls,
                    name=message.name,
                    property=message_property,
                )
            )
        elif isinstance(message, SystemMessage):
            agui_messages.append(
                AGUISystemMessage(
                    id=str(message.id),
                    role="system",
                    content=stringify_if_needed(resolve_message_content(message.content)),
                    name=message.name,
                )
            )
        elif isinstance(message, ToolMessage):
            content = stringify_if_needed(resolve_message_content(message.content))
            agui_messages.append(
                AGUIToolMessage(
                    id=str(message.id),
                    role="tool",
                    content=content if message.status != "error" else "",
                    tool_call_id=message.tool_call_id,
                    error=content if message.status == "error" else None,
                    duration=message.additional_kwargs.get("duration", None),
                )
            )
        elif isinstance(message, InterruptMessage):
            # 必须在 ActivityMessage 分支之前判断：InterruptMessage 继承 ActivityMessage，
            # 否则会被上一分支提前命中。还原为 role=interrupt 的中断/审批卡片，
            # 供 MESSAGES_SNAPSHOT 在前端展示。
            agui_messages.append(
                AGUIInterruptMessage(
                    id=str(message.id),
                    content=message.content,
                    name=message.name,
                )
            )
        elif isinstance(message, ActivityMessage):
            agui_messages.append(
                AGUIActivityMessage(
                    id=str(message.id),
                    content=message.content,
                    activity_type=message.type,
                )
            )
        elif isinstance(message, InfoMessage):
            agui_messages.append(
                AGUIInfoMessage(
                    id=str(message.id),
                    content=message.content,
                )
            )
        else:
            raise TypeError(f"Unsupported message type: {type(message)}")
    return agui_messages


def convert_agui_multimodal_to_langchain(
    content: list[TextInputContent | BinaryInputContent],
) -> list[dict[str, Any]]:
    """Convert AG-UI multimodal content to LangChain's multimodal format."""
    langchain_content = []
    for item in content:
        if isinstance(item, TextInputContent):
            langchain_content.append({"type": "text", "text": item.text})
        elif isinstance(item, BinaryInputContent):
            # LangChain uses image_url format (OpenAI-style)
            content_dict = {"type": "image_url"}

            # Prioritize url, then data, then id
            if item.url:
                content_dict["image_url"] = {"url": item.url}
            elif item.data:
                # Construct data URL from base64 data
                content_dict["image_url"] = {"url": f"data:{item.mime_type};base64,{item.data}"}
            elif item.id:
                # Use id as a reference (some providers may support this)
                content_dict["image_url"] = {"url": item.id}

            langchain_content.append(content_dict)

    return langchain_content


def agui_messages_to_langchain(messages: list[AGUIMessage]) -> list[BaseMessage]:
    langchain_messages = []
    for message in messages:
        role = message.role
        # 确保每条消息都有唯一的 id，避免 LangGraph add_messages reducer 错误地替换消息
        message.id = message.id if (message.id and message.id != "None") else str(uuid.uuid4())
        if role == PromptRole.USER.value:
            # Handle multimodal content
            if isinstance(message.content, str):
                content = message.content
            elif isinstance(message.content, list):
                content = convert_agui_multimodal_to_langchain(message.content)
            else:
                content = str(message.content)

            langchain_messages.append(
                HumanMessage(
                    id=message.id,
                    content=content,
                    name=message.name,
                )
            )
        elif role == PromptRole.ASSISTANT.value:
            tool_calls = []
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    tool_calls.append(
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "args": json.loads(tc.function.arguments)
                            if hasattr(tc, "function") and tc.function.arguments
                            else {},
                            "type": "tool_call",
                        }
                    )
            langchain_messages.append(
                AIMessage(
                    id=message.id,
                    content=message.content or "",
                    tool_calls=tool_calls,
                    name=message.name,
                )
            )
        elif role == PromptRole.SYSTEM.value:
            langchain_messages.append(
                SystemMessage(
                    id=message.id,
                    content=message.content,
                    name=message.name,
                )
            )
        elif role == PromptRole.TOOL.value:
            langchain_messages.append(
                ToolMessage(
                    id=message.id,
                    content=message.content,
                    tool_call_id=message.tool_call_id,
                )
            )
        elif role == PromptRole.INTERRUPT.value:
            # 前端历史回放中带入的 role=interrupt 卡片：还原为 InterruptMessage
            # （继承 ActivityMessage），既进入 state["messages"] 供 MESSAGES_SNAPSHOT
            # 重建与前端展示，又会被 basic_middleware 的 isinstance(ActivityMessage)
            # 过滤剔除，不会进入 LLM 输入。
            langchain_messages.append(
                InterruptMessage(
                    id=message.id,
                    content=message.content if isinstance(message.content, (dict, list)) else {},
                    name=message.name,
                )
            )
        elif role == PromptRole.INFO.value:
            # 前端历史回放中带入的 role=info 系统信息：还原为 InfoMessage，
            # 进入 state["messages"] 供 MESSAGES_SNAPSHOT 重建与前端展示，
            # 但会被 basic_middleware 过滤剔除，不会进入 LLM 输入。
            langchain_messages.append(
                InfoMessage(
                    id=message.id,
                    content=message.content if isinstance(message.content, str) else str(message.content),
                )
            )
        elif role in PromptRole.skip_roles():
            # 跳过 reasoning 消息，它只用于前端展示，不需要发送给 LLM
            continue
        else:
            raise ValueError(f"Unsupported message role: {role}")
    return langchain_messages


def resolve_reasoning_content(chunk: Any) -> LangGraphReasoning | None:
    content = chunk.content
    if not content and not hasattr(chunk, "additional_kwargs"):
        return None

    # Anthropic reasoning response
    if isinstance(content, list) and content and content[0]:
        if not content[0].get("thinking"):
            return None
        return LangGraphReasoning(text=content[0]["thinking"], type="text", index=content[0].get("index", 0))

    # OpenAI  / Deepseek reasoning response
    if hasattr(chunk, "additional_kwargs"):
        reasoning = chunk.additional_kwargs.get("reasoning", {})
        summary = reasoning.get("summary", [])
        if summary:
            data = summary[0]
            if not data or not data.get("text"):
                return None
            return LangGraphReasoning(type="text", text=data["text"], index=data.get("index", 0))

        reasoning_content = chunk.additional_kwargs.get("reasoning_content", {})
        if reasoning_content:
            return LangGraphReasoning(type="text", text=reasoning_content)

    return None


def resolve_message_content(content: Any) -> str | None:
    if not content:
        return None

    if isinstance(content, str):
        return content

    if isinstance(content, list) and content:
        content_text = next(
            (c.get("text") for c in content if isinstance(c, dict) and c.get("type") == "text"),
            None,
        )
        return content_text

    return None


def flatten_user_content(content: Any) -> str:
    """
    Flatten multimodal content into plain text.
    Used for backwards compatibility or when multimodal is not supported.
    """
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, TextInputContent):
                if item.text:
                    parts.append(item.text)
            elif isinstance(item, BinaryInputContent):
                # Add descriptive placeholder for binary content
                if item.filename:
                    parts.append(f"[Binary content: {item.filename}]")
                elif item.url:
                    parts.append(f"[Binary content: {item.url}]")
                else:
                    parts.append(f"[Binary content: {item.mime_type}]")
        return "\n".join(parts)

    return str(content)


def camel_to_snake(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def json_safe_stringify(o):
    if is_dataclass(o):  # dataclasses like Flight(...)
        return asdict(o)
    if hasattr(o, "model_dump"):  # pydantic v2
        return o.model_dump()
    if hasattr(o, "dict"):  # pydantic v1
        return o.dict()
    if hasattr(o, "__dict__"):  # plain objects
        return vars(o)
    if isinstance(o, datetime | date):
        return o.isoformat()
    return str(o)  # last resort


def make_json_safe(value: Any, _seen: set[int] | None = None) -> Any:
    """
    Convert `value` into something that `json.dumps` can always handle.

    Rules (in order):
    - primitives → as-is
    - Enum → its .value (recursively made safe)
    - dict → keys & values made safe
    - list/tuple/set/frozenset → list of safe values
    - dataclasses → asdict() then recurse
    - Pydantic-style models → model_dump()/dict()/to_dict() then recurse
    - objects with __dict__ → vars(obj) then recurse
    - everything else → repr(obj)

    Cycles are detected and replaced with the string "<recursive>".
    """
    if _seen is None:
        _seen = set()

    obj_id = id(value)
    if obj_id in _seen:
        return "<recursive>"

    # --- 1. Primitives -----------------------------------------------------
    if isinstance(value, str | int | float | bool) or value is None:
        return value

    # --- 2. Enum → use underlying value -----------------------------------
    if isinstance(value, Enum):
        return make_json_safe(value.value, _seen)

    # --- 3. Dicts ----------------------------------------------------------
    if isinstance(value, dict):
        _seen.add(obj_id)
        return {make_json_safe(k, _seen): make_json_safe(v, _seen) for k, v in value.items()}

    # --- 4. Iterable containers -------------------------------------------
    if isinstance(value, list | tuple | set | frozenset):
        _seen.add(obj_id)
        return [make_json_safe(v, _seen) for v in value]

    # --- 5. Dataclasses ----------------------------------------------------
    if is_dataclass(value):
        _seen.add(obj_id)
        return make_json_safe(asdict(value), _seen)

    # --- 6. Pydantic-like models (v2: model_dump) -------------------------
    if hasattr(value, "model_dump") and callable(getattr(value, "model_dump")):
        _seen.add(obj_id)
        try:
            return make_json_safe(value.model_dump(), _seen)
        except Exception:
            # fall through to other options
            pass

    # --- 7. Pydantic v1-style / other libs with .dict() -------------------
    if hasattr(value, "dict") and callable(getattr(value, "dict")):
        _seen.add(obj_id)
        try:
            return make_json_safe(value.dict(), _seen)
        except Exception:
            pass

    # --- 8. Generic "to_dict" pattern -------------------------------------
    if hasattr(value, "to_dict") and callable(getattr(value, "to_dict")):
        _seen.add(obj_id)
        try:
            return make_json_safe(value.to_dict(), _seen)
        except Exception:
            pass

    # --- 9. Generic Python objects with __dict__ --------------------------
    if hasattr(value, "__dict__"):
        _seen.add(obj_id)
        try:
            return make_json_safe(vars(value), _seen)
        except Exception:
            pass

    # --- 10. Last resort ---------------------------------------------------
    return repr(value)


def get_reasoning_message_id(message_id: str) -> str:
    """对于思考的内容,需要更新一下messageId格式"""
    return f"reasoning-{message_id}"


def langchain_messages_to_streaming_events(
    messages: list[BaseMessage],
) -> Iterator[BaseEvent]:
    """把 LangChain 消息列表转换为「与正常流式同构」的 AG-UI 增量事件序列。

    转换规则：
      - ``AIMessage``：
          1. 若 ``additional_kwargs.reasoning_content`` 存在，先发 ``reasoning``
             custom event（沿用 ``ReasoningMessage`` 同源字段，但走流式 START/END
             序列）；
          2. 若 ``content`` 非空，发 ``TEXT_MESSAGE_START`` + 单条
             ``TEXT_MESSAGE_CONTENT``（整段 delta） + ``TEXT_MESSAGE_END``；
          3. 若 ``tool_calls`` 非空，对每个 tool_call 发 ``TOOL_CALL_START`` +
             ``TOOL_CALL_ARGS``（整段 args JSON） + ``TOOL_CALL_END``。
      - ``ToolMessage``：发一条 ``TOOL_CALL_RESULT``，``tool_call_id`` 与
        ``message_id`` 保留 DB 原值，``content`` 错误时通过 ``is_error`` 标记。
      - ``HumanMessage`` / ``SystemMessage`` / ``InterruptMessage`` /
        ``ActivityMessage``：不下发（前端历史已持有，且这些类型没有"逐条增量"
        语义；resume 终态场景只补 worker 续流新写的消息）。
    """
    for message in messages:
        if isinstance(message, AIMessage):
            yield from _ai_message_to_events(message)
        elif isinstance(message, ToolMessage):
            yield _tool_message_to_event(message)


def _ai_message_to_events(message: AIMessage) -> Iterator[BaseEvent]:
    """把单条 AIMessage 展开为 reasoning / text / tool_call 事件序列"""
    message_id = str(message.id) if message.id else str(uuid.uuid4())

    # 1) reasoning（如有），与 AGUIAgent 流式路径产出形态保持同源（START/END 配对）
    reasoning_content = (message.additional_kwargs or {}).get("reasoning_content")
    if reasoning_content:
        yield ThinkingTextMessageStartEvent(
            type=EventType.THINKING_TEXT_MESSAGE_START,
        )
        yield ThinkingTextMessageContentEvent(
            type=EventType.THINKING_TEXT_MESSAGE_CONTENT,
            delta=stringify_if_needed(reasoning_content),
        )
        yield ThinkingTextMessageEndEvent(
            type=EventType.THINKING_TEXT_MESSAGE_END,
        )

    # 2) text 内容（非空才发）：保留 DB 中的 message_id，前端按 id 合并不会产生新卡片
    content_text = stringify_if_needed(resolve_message_content(message.content))
    if content_text:
        yield TextMessageStartEvent(
            type=EventType.TEXT_MESSAGE_START,
            message_id=message_id,
            role="assistant",
        )
        yield TextMessageContentEvent(
            type=EventType.TEXT_MESSAGE_CONTENT,
            message_id=message_id,
            delta=content_text,
        )
        yield TextMessageEndEvent(
            type=EventType.TEXT_MESSAGE_END,
            message_id=message_id,
        )

    # 3) tool_calls（如有）：对每个 tool_call 输出完整的 START/ARGS/END 三元组
    for tc in message.tool_calls or []:
        tc_id = str(tc.get("id") or uuid.uuid4())
        yield ExtendToolCallStartEvent(
            type=EventType.TOOL_CALL_START,
            tool_call_id=tc_id,
            tool_call_name=tc.get("name", ""),
            parent_message_id=message_id,
        )
        yield ToolCallArgsEvent(
            type=EventType.TOOL_CALL_ARGS,
            tool_call_id=tc_id,
            delta=json.dumps(tc.get("args", {})),
        )
        yield ToolCallEndEvent(
            type=EventType.TOOL_CALL_END,
            tool_call_id=tc_id,
        )


def _tool_message_to_event(message: ToolMessage) -> BaseEvent:
    """把单条 ToolMessage 展开为一条 TOOL_CALL_RESULT 事件"""
    content = stringify_if_needed(resolve_message_content(message.content))
    is_error = getattr(message, "status", None) == "error"
    return ExtendToolCallResultEvent(
        type=EventType.TOOL_CALL_RESULT,
        tool_call_id=message.tool_call_id,
        message_id=str(message.id) if message.id else str(uuid.uuid4()),
        content=content if not is_error else "",
        role="tool",
        is_error=is_error or None,
        duration=(message.additional_kwargs or {}).get("duration"),
    )


def unwrap_interrupt_source(source: Any) -> Any:
    """从 RUN_FINISHED 事件中解包出 interrupt[0]。"""
    if not isinstance(source, dict) or source.get("type") != "RUN_FINISHED":
        return source

    outcome = source.get("outcome")
    if not isinstance(outcome, dict) or outcome.get("type") != "interrupt":
        return source

    interrupts = outcome.get("interrupts") or []
    if interrupts:
        return interrupts[0]
    return source


def get_interrupt_value(source: Any, *keys: str) -> Any:
    """从 interrupt 对象/dict 中按多个候选 key 查找值。"""
    source = unwrap_interrupt_source(source)
    # LangGraph Interrupt 对象：实际 payload 在 source.value 中，
    # 需要解包后才能按 dict 方式查找 callbackToken、metadata 等字段
    original_source = source
    if not isinstance(source, dict) and hasattr(source, "value"):
        inner = source.value
        if isinstance(inner, dict):
            source = inner

    metadata = {}
    raw_metadata = source.get("metadata") if isinstance(source, dict) else getattr(source, "metadata", None)
    if isinstance(raw_metadata, dict):
        metadata = raw_metadata

    nested_candidates = []
    if isinstance(metadata.get("ticket"), dict):
        nested_candidates.append(metadata["ticket"])
    if isinstance(metadata.get("approval"), dict):
        nested_candidates.append(metadata["approval"])
    if isinstance(metadata.get("target"), dict):
        nested_candidates.append(metadata["target"])
    if isinstance(metadata.get("execution"), dict):
        nested_candidates.append(metadata["execution"])

    for candidate in nested_candidates:
        for key in keys:
            if key in candidate and candidate[key] is not None:
                return candidate[key]

    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]

    for key in keys:
        if isinstance(source, dict):
            if key in source and source[key] is not None:
                return source[key]
        else:
            value = getattr(source, key, None)
            if value is not None:
                return value

    # 兜底：对于 Interrupt 对象（source 已被替换为 value），
    # 仍尝试从原始对象的属性中查找（如 Interrupt.id）
    if original_source is not source:
        for key in keys:
            value = getattr(original_source, key, None)
            if value is not None:
                return value
