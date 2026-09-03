import json
import logging
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
    ToolMessage,
)
from pydantic import ValidationError

from .events import ExtendToolCallResultEvent, ExtendToolCallStartEvent
from .types import (
    ExtendActivityMessage as AGUIActivityMessage,
)
from .types import (
    ExtendAssistantMessage as AGUIAssistantMessage,
)
from .types import (
    ExtendDeveloperMessage as AGUIDeveloperMessage,
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
from .types import (
    LangGraphReasoning,
    ReasoningMessage,
    SchemaKeys,
    State,
)
from ...enums import PromptRole

# 仅有 tool_calls、无文本输出的 assistant 消息使用的占位符 content。
# 首帧 MESSAGES_SNAPSHOT（历史还原）与 interrupt 终态回放需将其归一化为 ""，
# 与前端读接口（session_content / session）的展示语义保持一致。
# 定义在 utils（低层模块）供 event_builders 复用，避免 event_builders ↔ utils 循环依赖。
TOOL_CALLING_PLACEHOLDER = "正在调用工具..."

DEFAULT_SCHEMA_KEYS = ["tools"]

logger = logging.getLogger(__name__)

# 平台会话内容 status 域（success/fail/loading + AG-UI 域）→ AG-UI 域映射：
# 平台写入方（services/event_handlers/base.py）落库 success/fail/loading，
# 而 ExtendBaseMessage.status 仅接受 complete/streaming/pending/error/stop。
# 未知值一律收敛为 complete，避免单条记录阻塞整批转换。
_STATUS_MAP = {
    "success": "complete",
    "fail": "error",
    "loading": "streaming",
    # complete / streaming / pending / error / stop 原样透传
}

# 用户图片消息的 Markdown 图片链接提取：`![name](http://host/path/file.ext)`
# 捕获完整的 http(s) 地址（含文件名），与 services/agent/chat.py 的 IMAGE_FILE_PATTERN 保持同源。
IMAGE_FILE_PATTERN = re.compile(r"^!\[.*\]\((http[^)]+/([^/]+?))\)")


def _normalize_status(raw: Any) -> str:
    """把平台会话记录 status 归一化为 AG-UI ExtendBaseMessage.status 允许域。"""
    status = raw if isinstance(raw, str) else ""
    status = _STATUS_MAP.get(status, status)
    return status if status in {"complete", "streaming", "pending", "error", "stop"} else "complete"


def _read_builtin_property(record: dict) -> dict:
    """读取 ChatPrompt 单账本的 builtin_property（适配层回嵌的平铺协议字段）。"""
    bp = record.get("builtin_property")
    return bp if isinstance(bp, dict) else {}


def _read_extra(record: dict) -> Any:  # nosemgrep: aidev-no-bare-any
    """读取 ChatPrompt 单账本的 extra 字段（property.extra，适配层透传）。"""
    extra = record.get("extra")
    if extra is not None:
        return extra
    # 缺 extra 时回退 __pydantic_extra__ 透传的 property 原文
    return (record.get("__pydantic_extra__") or {}).get("property")


def _read_field(record: dict, key: str) -> Any:  # nosemgrep: aidev-no-bare-any
    """按 ChatPrompt 单账本形状读取字段：builtin_property 优先，回退 __pydantic_extra__/顶层。

    迁移函数（migration_chat_session_context_from_chat_session_contents_v1）把平铺顶层字段回嵌 builtin_property，
    缺失时回退 extra="allow" 透传的 __pydantic_extra__；对直构的 A-dict 记录回退顶层，
    保证快照转换对两种形态都容错。
    """
    bp = _read_builtin_property(record)
    value = bp.get(key)
    if value is not None:
        return value
    extra_dict = record.get("__pydantic_extra__")
    if isinstance(extra_dict, dict) and extra_dict.get(key) is not None:
        return extra_dict[key]
    return record.get(key)


def _build_assistant_property(record: dict) -> dict | None:
    """构造 assistant 快照的开放属性字典（与前端 IMessageProperty 契约对齐）。

    artifacts（本轮文件产物）从 builtin_property 显式读取，归入 property["artifacts"]，
    与实时流 artifacts 事件构造的开放属性形态一致；无产物时不写 property，
    避免污染无产物的历史 assistant 消息。
    """
    artifacts = _read_field(record, "artifacts")
    if not artifacts:
        return None
    return {"artifacts": artifacts}


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


def parse_reasoning_content_value(content: Any) -> list[str]:
    """将 reasoning content 归一为 list[str]。

    JSON 字符串解析由平台 session_context / 读库接口完成；此处只做类型归一。
    """
    if isinstance(content, list):
        return [str(each) for each in content]
    if content is None:
        return []
    return [str(content)]


def _map_reference_documents(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将 reference document 数组逐项 ``origin_file_url`` → ``originFileUrl`` 映射（name/url 原样保留）。

    语义镜像前端 ``transferReferenceDocumentApi2ReferenceDocument``（transform/message.ts:108-113）。
    仅映射白名单键，name/url/data 等原键透传不丢；非 list 输入原样返回。
    """
    mapped: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            mapped.append(item)
            continue
        doc = dict(item)
        if "origin_file_url" in doc:
            doc["originFileUrl"] = doc.pop("origin_file_url")
        mapped.append(doc)
    return mapped


def _map_user_multimodal_content(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将 user 多模态 content（dict list）映射为 InputContent 形态，binary 项 ``mime_type`` → ``mimeType``。

    语义镜像前端 ``transferMessageApi2Message`` User 分支（transform/message.ts:352-377）。
    binary 项保 data/filename/id/url；text 项原样保留。
    """
    mapped: list[dict[str, Any]] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "binary":
            binary = dict(item)
            binary["mimeType"] = binary.get("mime_type") or binary.get("mimeType") or "application/octet-stream"
            binary.pop("mime_type", None)
            mapped.append(binary)
        else:
            mapped.append(item)
    return mapped


def _record_to_agui_message(
    record: dict,
    msg_id: str,
    status: str,
    created_at: Any,
) -> AGUIMessage | None:
    """把单条 ChatPrompt 单账本记录（适配层输出形状）转换为 AG-UI ExtendMessage。

    消费形态为 lossless ChatPrompt：role/content 顶层原样，status/created_at/tool_calls/
    tool_call_id/duration/activity_type/artifacts 从 builtin_property（缺失回退 __pydantic_extra__/顶层），
    property 从 extra。ai/pause 归一 assistant（两域统一），user-image 还原为用户多模态。

    由 ``contents_to_agui_messages`` 逐条调用；构造失败（pydantic ValidationError）
    由调用方捕获并跳过，不阻塞整批转换。
    """
    role = record.get("role")

    if role == PromptRole.USER_IMAGE.value:
        # 用户图片消息：提取 Markdown 图片链接为 binary/InputContent 多模态形态
        # （与前端历史接口 binary+url 形态一致，装配侧 _convert_contents 则转 image_url 供 LLM）。
        raw_content = record.get("content")
        match = IMAGE_FILE_PATTERN.search(raw_content) if isinstance(raw_content, str) else None
        content = [{"type": "binary", "mime_type": "image/png", "url": match.group(1)}] if match else raw_content
        return AGUIUserMessage(
            id=msg_id,
            role="user",
            content=content,
            status=status,
            created_at=created_at,
        )
    if role == PromptRole.USER.value:
        raw_content = record.get("content")
        multimodal = parse_multimodal_content(raw_content)
        content = _map_user_multimodal_content(multimodal) if multimodal is not None else raw_content
        return AGUIUserMessage(
            id=msg_id,
            role="user",
            content=content,
            status=status,
            created_at=created_at,
        )
    if role in (PromptRole.ASSISTANT.value, PromptRole.AI.value, PromptRole.PAUSE.value):
        # ai/pause 均归一 assistant（与装配侧 _convert_contents pause→assistant + convert 链 case ASSISTANT|AI 两域统一）
        tool_calls = _extract_agui_tool_calls(_read_field(record, "tool_calls"))
        return AGUIAssistantMessage(
            id=msg_id,
            role="assistant",
            content=record.get("content"),
            tool_calls=tool_calls,
            property=_build_assistant_property(record),
            status=status,
            created_at=created_at,
        )
    if role == PromptRole.TOOL.value:
        content = record.get("content")
        tool_call_id = _read_field(record, "tool_call_id") or msg_id
        return AGUIToolMessage(
            id=msg_id,
            role="tool",
            content=content if status != "error" else "",
            tool_call_id=str(tool_call_id),
            error=content if status == "error" else None,
            duration=_read_field(record, "duration"),
            status=status,
            created_at=created_at,
        )
    if role == PromptRole.ACTIVITY.value:
        activity_type = _read_field(record, "activity_type")
        content = record.get("content")
        if activity_type == "knowledge_rag" and isinstance(content, dict):
            ref_docs = content.get("reference_document")
            content = {
                "content": content.get("content"),
                "referenceDocument": _map_reference_documents(ref_docs) if isinstance(ref_docs, list) else ref_docs,
            }
        elif activity_type == "reference_document" and isinstance(content, list):
            content = _map_reference_documents(content)
        return AGUIActivityMessage(
            id=msg_id,
            role="activity",
            content=content,
            activity_type=activity_type,
            status=status,
            created_at=created_at,
        )
    if role == PromptRole.INTERRUPT.value:
        return AGUIInterruptMessage(
            id=msg_id,
            role="interrupt",
            content=record.get("content"),
            name=record.get("name"),
            status=status,
            created_at=created_at,
        )
    if role == PromptRole.INFO.value:
        return AGUIInfoMessage(
            id=msg_id,
            role="info",
            content=record.get("content"),
            status=status,
            created_at=created_at,
        )
    if role == PromptRole.REASONING.value:
        content = record.get("content")
        if isinstance(content, str):
            try:
                parsed = json.loads(content)
                reasoning_content = parsed if isinstance(parsed, list) else [content]
            except (json.JSONDecodeError, TypeError):
                reasoning_content = [content]
        elif isinstance(content, list):
            reasoning_content = [str(each) for each in content]
        elif content is None:
            reasoning_content = []
        else:
            reasoning_content = [str(content)]
        return ReasoningMessage(
            id=msg_id,
            role="reasoning",
            content=reasoning_content,
            duration=_read_field(record, "duration"),
            status=status,
            created_at=created_at,
        )
    if role == "developer":
        return AGUIDeveloperMessage(
            id=msg_id,
            role="developer",
            content=record.get("content"),
            status=status,
            created_at=created_at,
        )
    if role in (PromptRole.SYSTEM.value, PromptRole.GUIDE.value, PromptRole.HIDDEN.value):
        # system/guide/hidden 均落位 ExtendSystemMessage：content 原样保留（不丢弃），
        # 镜像前端同名 role 的 content 透传语义。AG-UI 协议无 guide/hidden 原生 role，
        # 故统一收敛到 system 消息类型承载 content（禁止清单：不丢 system/guide）。
        # 注意：pause 不在此收敛——pause 已归一 assistant（两域统一），不再作为 system 承载。
        return AGUISystemMessage(
            id=msg_id,
            role="system",
            content=record.get("content"),
            status=status,
            created_at=created_at,
        )
    logger.warning("contents_to_agui_messages: 未识别 role=%r，跳过记录 %r", role, record)
    return None


def _extract_agui_tool_calls(raw_tool_calls: Any) -> list[AGUIToolCall] | None:
    """把 assistant 落库 tool_calls 归一化为 AG-UI ExtendToolCall 列表。

    落库记录（与 ``chat_history_assembly._extract_tool_calls`` 同源）保存 OpenAI 嵌套形态：
    ``{"id","type","function":{name,arguments,mcp_name}}``。先展开嵌套 ``function``
    dict 再读 name/arguments/mcp_name，避免顶层缺失时 name/arguments 被静默丢弃。
    """
    if not isinstance(raw_tool_calls, list) or not raw_tool_calls:
        return None
    tool_calls: list[AGUIToolCall] = []
    for tc in raw_tool_calls:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") if isinstance(tc.get("function"), dict) else {}
        raw_args = tc.get("args") if tc.get("args") is not None else fn.get("arguments")
        arguments = json.dumps(raw_args) if isinstance(raw_args, (dict, list)) else str(raw_args or "{}")
        tool_calls.append(
            AGUIToolCall(
                id=str(tc.get("id") or uuid.uuid4().hex),
                type="function",
                function=AGUIFunctionCall(
                    name=str(tc.get("name") or fn.get("name") or ""),
                    arguments=arguments,
                    description=tc.get("description") or fn.get("description"),
                    mcp_name=tc.get("mcp_name") or tc.get("mcpName") or fn.get("mcp_name") or None,
                ),
            )
        )
    return tool_calls


def contents_to_agui_messages(records: list[dict]) -> list[AGUIMessage]:
    """将 lossless ChatPrompt 单账本记录（快照数据源）转换为 AG-UI ExtendMessage。

    消费形态为适配层输出的 ChatPrompt dict：role/content 顶层原样，status/created_at/
    tool_calls/tool_call_id/duration/activity_type/artifacts 从 builtin_property（缺失回退
    __pydantic_extra__/顶层），property 从 extra。语义镜像前端 ``transferMessageApi2Message``：
    忠实保留多模态/知识库召回/tool 内容，不做 context 链路的破坏性转换（不丢 system/guide、
    不剥离 think、不过滤 tool）。ai/pause 归一 assistant、user-image 还原多模态。
    嵌套 content dict 键手工 camelCase 化（referenceDocument/originFileUrl/mimeType）。
    单条坏记录（缺 role / 非 dict / 构造抛 ValidationError / 未识别 role）跳过并 warning，
    不阻塞整批转换。
    """
    agui_messages: list[AGUIMessage] = []
    for record in records:
        if not isinstance(record, dict):
            logger.warning("contents_to_agui_messages: 跳过非 dict 记录 %r", record)
            continue
        role = record.get("role")
        if not role:
            logger.warning("contents_to_agui_messages: 跳过缺 role 记录 %r", record)
            continue

        created_at = _read_field(record, "created_at")
        # 平台 status 域（success/fail/loading 等）归一化为 AG-UI 允许域，未知值收敛 complete。
        status = _normalize_status(_read_field(record, "status") or "complete")
        msg_id = str(record.get("id") or uuid.uuid4().hex)

        try:
            message = _record_to_agui_message(record, msg_id, status, created_at)
        except ValidationError as e:
            logger.warning("contents_to_agui_messages: 跳过非法记录 id=%s: %s", record.get("id"), e)
            continue
        if message is not None:
            agui_messages.append(message)
    return agui_messages


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


def make_json_safe(value: Any, _seen: set[int] | None = None) -> Any:  # nosemgrep: aidev-no-bare-any
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
    *,
    state_messages: list[BaseMessage] | None = None,
    tools_mapping: dict[str, Any] | None = None,
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

    D-05 方向 a（DB 权威化）：当传入 ``state_messages`` 与 ``tools_mapping`` 时，
    tool_call 重放按 DB 等价谓词过滤审批 pending（无对应 ToolMessage）的项
    （``should_suppress_approval_tool_call`` 同源复算，不真查 DB）。
    """
    for message in messages:
        if isinstance(message, AIMessage):
            yield from _ai_message_to_events(
                message,
                state_messages=state_messages,
                tools_mapping=tools_mapping,
            )
        elif isinstance(message, ToolMessage):
            yield _tool_message_to_event(message)


def _ai_message_to_events(
    message: AIMessage,
    *,
    state_messages: list[BaseMessage] | None = None,
    tools_mapping: dict[str, Any] | None = None,
) -> Iterator[BaseEvent]:
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

    # 3) tool_calls（如有）：对每个 tool_call 输出完整的 START/ARGS/END 三元组。
    #    D-05 方向 a（DB 权威化）：审批 pending 且无对应 ToolMessage 的 tool_call 不重放
    #    （与中断终态快照过滤同用 should_suppress_approval_tool_call，同源复算不真查 DB）。
    #    state_messages 为空（未显式提供）时不启用过滤，保持旧行为。
    if state_messages is not None:
        # 延迟导入打破 utils ↔ event_builders 循环依赖（utils 为低层模块，event_builders 从 utils 导入）。
        from .event_builders import should_suppress_approval_tool_call

        filter_tool_calls = [
            tc
            for tc in message.tool_calls or []
            if not should_suppress_approval_tool_call(tc, state_messages, tools_mapping or {})
        ]
    else:
        filter_tool_calls = message.tool_calls or []

    for tc in filter_tool_calls:
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
        tool_call_name=getattr(message, "name", None),
    )
