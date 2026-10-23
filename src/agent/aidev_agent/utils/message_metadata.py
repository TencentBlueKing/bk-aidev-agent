"""Completion metadata shared by current responses and persisted history."""

from datetime import datetime, timezone

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage

from aidev_agent.utils.message_text import strip_think_blocks


def message_timestamp(value):
    """把宿主提供的时间戳（ISO 字符串或 `datetime`）归一化为带时区的 ISO 字符串。

    无时区信息时按 UTC 处理；格式非法或类型不支持时返回 `None`，避免可选元数据异常打断对话。
    """
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def assistant_source_timestamp(message, *, generate: bool = False) -> str | None:
    """解析并固化 assistant 消息的原始完成时间，确保事件副本与状态副本使用同一时间。

    依次取 `response_metadata` 中的 `source_timestamp`、`created_at`、`timestamp`；都缺失且
    `generate=True` 时以当前 UTC 时间补齐。结果会写回 `response_metadata["source_timestamp"]`
    （副作用），返回 ISO 字符串，无法得到时返回 `None`。
    """
    metadata = message.response_metadata
    stamp = next(
        (
            value
            for key in ("source_timestamp", "created_at", "timestamp")
            if (value := message_timestamp(metadata.get(key)))
        ),
        None,
    )
    if stamp is None and generate:
        stamp = datetime.now(timezone.utc).isoformat()
    if stamp is not None:
        metadata["source_timestamp"] = stamp
    return stamp


def assistant_source_text(message) -> str:
    """返回 assistant 消息用作记忆证据的正文，供本轮证据与无台账回放共用同一口径。

    优先使用结算时写入的 `response_metadata["source_text"]`，否则取 `content`；
    统一剔除推理块并保留原有空白。
    """
    text = message.response_metadata.get("source_text")
    if not isinstance(text, str):
        text = message.content
    return strip_think_blocks(text, preserve_whitespace=True)


def memory_source_metadata(metadata: dict) -> dict:
    """提取输出转换后仍需保留的记忆来源元数据。

    只携带完成时间与待结算标记；原始 `finish_reason` 改存为 `memory_source_finish_reason`，
    供记忆判断截断，而不影响质量门对转换后消息的截断恢复判定。
    """
    carried = {
        key: metadata[key]
        for key in ("source_timestamp", "memory_source_pending", "memory_source_complete")
        if key in metadata
    }
    if "finish_reason" in metadata:
        carried["memory_source_finish_reason"] = metadata["finish_reason"]
    return carried


def memory_finish_reason(metadata: dict):
    """返回记忆判断完整性使用的结束原因，优先取转换前保留的原始值。"""
    return metadata.get("memory_source_finish_reason", metadata.get("finish_reason"))


def is_complete_finish_reason(value) -> bool:
    """判断模型 `finish_reason` 是否代表完整的最终回答。

    截断（`length`/`max_tokens`）、内容过滤、未完成、取消/停止、错误以及工具调用类结束原因
    视为不完整；缺失或为空视为完整。比较时忽略大小写。
    """
    return str(value or "").lower() not in {
        "length",
        "max_tokens",
        "content_filter",
        "incomplete",
        "cancelled",
        "stopped",
        "error",
        "tool_calls",
        "function_call",
    }


class AssistantCompletionTimestamp(BaseCallbackHandler):
    """Stamp the assembled provider output before stream tracers copy or publish it."""

    run_inline = True

    def __init__(self, *, pending_transform: bool = False):
        """初始化回调。

        `pending_transform=True` 表示模型输出之后还有转换或质量门禁步骤，此时会把消息标记为
        待结算，交由 `finalize_memory_source` 在调用方接受输出后再确定是否可作为记忆来源。
        """
        self.pending_transform = pending_transform

    def on_llm_end(self, response, **kwargs):
        """模型调用结束时为每个 `AIMessage` 生成结果补齐 `source_timestamp`。

        开启 `pending_transform` 时同时写入 `memory_source_pending=True`、
        `memory_source_complete=False`，在结算前一律视为不可用的记忆来源。
        """
        for generations in response.generations:
            for generation in generations:
                message = getattr(generation, "message", None)
                if isinstance(message, AIMessage):
                    assistant_source_timestamp(message, generate=True)
                    if self.pending_transform:
                        message.response_metadata.update(memory_source_pending=True, memory_source_complete=False)


def finalize_memory_source(message, *, accepted: bool = True) -> dict | None:
    """在调用方接受转换后的输出后，结算该消息能否作为记忆来源。

    仅处理带 `memory_source_pending` 标记的 `AIMessage`（会弹出该标记），否则返回 `None`。
    `accepted` 为真、无（无效）工具调用、剔除推理块后正文非空且 `finish_reason` 完整时判为完整，
    并写回 `memory_source_complete`；完整时还写入 `source_text` 并补齐 `source_timestamp`。
    返回 `MemorySourceFinalized` 事件所需的 payload。
    """
    if not isinstance(message, AIMessage) or not message.response_metadata.pop("memory_source_pending", False):
        return None
    text = strip_think_blocks(message.content, preserve_whitespace=True) if isinstance(message.content, str) else ""
    complete = bool(
        accepted
        and not message.tool_calls
        and not message.invalid_tool_calls
        and text.strip()
        and is_complete_finish_reason(memory_finish_reason(message.response_metadata))
    )
    message.response_metadata["memory_source_complete"] = complete
    result = {"message_id": message.id, "memory_source_complete": complete}
    if complete:
        message.response_metadata["source_text"] = text
        result["source_text"] = message.response_metadata["source_text"]
        result["source_timestamp"] = assistant_source_timestamp(message, generate=True)
    return result
