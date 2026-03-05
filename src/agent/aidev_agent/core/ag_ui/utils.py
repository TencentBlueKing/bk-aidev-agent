import json
import re
import uuid
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any

from ag_ui.core import (
    BinaryInputContent,
    TextInputContent,
)
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from .types import (
    ActivityMessage,
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


def convert_langchain_multimodal_to_agui(
    content: list[dict[str, Any]],
) -> list[TextInputContent | BinaryInputContent]:
    """Convert LangChain's multimodal content to AG-UI format."""
    agui_content = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "text":
                agui_content.append(TextInputContent(type="text", text=item.get("text", "")))
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
            if isinstance(message.content, list):
                content = convert_langchain_multimodal_to_agui(message.content)
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

            agui_messages.append(
                AGUIAssistantMessage(
                    id=str(message.id),
                    role="assistant",
                    content=stringify_if_needed(resolve_message_content(message.content)),
                    tool_calls=tool_calls,
                    name=message.name,
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
        elif isinstance(message, ActivityMessage):
            agui_messages.append(
                AGUIActivityMessage(
                    id=str(message.id),
                    content=message.content,
                    activity_type=message.type,
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
