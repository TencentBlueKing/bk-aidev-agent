# -*- coding: utf-8 -*-
"""Chat Agent 工具调用的片段维护与渲染。

企微收到的是全量快照而非增量，因此正文与工具按出现顺序排成片段，
每次状态变化整段重渲染，同一个工具的气泡就能原地从「调用中」刷成「完成」。

长连接（direct_stream）与 HTTP 回调（stream）共用本模块，避免两份渲染实现漂移。
"""

from __future__ import annotations

import json
import re
from logging import getLogger

from ag_ui.core.events import EventType

from .constants import TOOL_LINE_PREFIX, TOOL_STATUS_ICONS, TOOL_TARGET_LIMIT

logger = getLogger(__name__)

_TOOL_EVENTS = (
    EventType.TOOL_CALL_START,
    EventType.TOOL_CALL_ARGS,
    EventType.TOOL_CALL_END,
    EventType.TOOL_CALL_RESULT,
)
_SAFE_TARGET_KEYS = ("skill", "name", "index_set_id", "bk_biz_id")
_SENSITIVE_MARKER = re.compile(
    r"(?i)(?:authorization|cookie|credential|password|passwd|secret|token|api[-_]?key|access[-_]?key|private[-_]?key)"
)
_SENSITIVE_VALUE = re.compile(r"(?i)(?:bearer\s+\S+|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})")
_ERROR_CODE = re.compile(r"(?i)(?:error|错误码|code)\s*[:：=#-]?\s*([A-Za-z0-9_-]*\d[A-Za-z0-9_-]*)")


def is_tool_event(event_type) -> bool:
    return event_type in _TOOL_EVENTS


def _event_value(event: dict, *keys, default=None):
    """兼容 SSE 的 camelCase / snake_case 字段。"""
    for key in keys:
        if key in event and event[key] is not None:
            return event[key]
    return default


def _one_line(value, limit: int) -> str:
    """压成单行并截断。反引号会在企微里意外开启代码块，一并去掉。"""
    text = " ".join(str(value or "").replace("`", "'").split())
    return text if len(text) <= limit else text[:limit] + "…"


def _format_duration(duration) -> str:
    """毫秒数转人读格式，超过 1 秒改用秒，避免出现 6292ms 这种要心算的值。"""
    try:
        ms = int(float(duration))
    except (TypeError, ValueError):
        return ""
    return f"{ms}ms" if ms < 1000 else f"{ms / 1000:.1f}s"


def _format_tool_target(args: str) -> str:
    """仅展示明确允许且不含敏感标记的参数；半截 JSON 和未知字段一律不回显。"""
    try:
        parsed = json.loads(args)
    except (TypeError, ValueError):
        return ""
    if not isinstance(parsed, dict):
        return ""
    normalized = {str(key).lower().replace("-", "_"): value for key, value in parsed.items()}
    for key in _SAFE_TARGET_KEYS:
        if key not in normalized or _SENSITIVE_MARKER.search(key):
            continue
        value = _one_line(normalized[key], TOOL_TARGET_LIMIT)
        if value and not _SENSITIVE_MARKER.search(value) and not _SENSITIVE_VALUE.search(value):
            return value
    return ""


def _safe_tool_error(result: str) -> str:
    """不回显工具原始异常，只保留可安全展示的错误码。"""
    if match := _ERROR_CODE.search(result or ""):
        return f"执行失败（错误码：{match.group(1)}），详细原因请查看服务日志"
    return "执行失败，详细原因请查看服务日志"


def format_tool_markdown(tool: dict) -> str:
    """一行「图标 + 工具名 + 操作对象 + 耗时」，失败时补一行原因。

    工具块靠引用块与正文分开；成功的结果不展示，正文本就会复述一遍。
    """
    status = tool.get("status") or "calling"
    parts = [TOOL_STATUS_ICONS.get(status, "🔄"), f"**{tool.get('name') or 'unknown'}**"]
    target = _format_tool_target(tool.get("args") or "")
    if target:
        parts.append(f"`{target}`")
    duration = _format_duration(tool.get("duration"))
    if duration and status in {"ok", "error"}:
        parts.append(f"· {duration}")

    lines = [" ".join(parts)]
    if status == "error":
        lines.append(tool.get("result") or _safe_tool_error(""))
    return "\n".join(f"{TOOL_LINE_PREFIX}{line}" for line in lines)


class ChatSegments:
    """正文与工具调用按出现顺序排成的片段，可随时渲染成一份全量快照。"""

    def __init__(self, stream_id: str = ""):
        self._stream_id = stream_id
        self._segments: list[dict] = []
        self._tools: dict[str, dict] = {}
        self._pending = ""

    @property
    def pending_size(self) -> int:
        """尚未并入片段的正文长度，供调用方决定何时攒够一次推送。"""
        return len(self._pending)

    def append_text(self, delta: str) -> None:
        self._pending += delta

    def commit_text(self) -> None:
        """把攒着的正文并入片段列表，让后续工具块排在它后面。"""
        if not self._pending:
            return
        if self._segments and self._segments[-1]["kind"] == "text":
            self._segments[-1]["text"] += self._pending
        else:
            self._segments.append({"kind": "text", "text": self._pending})
        self._pending = ""

    def apply_tool_event(self, event_type, event: dict) -> bool:
        """更新工具状态，返回是否需要立刻推送快照。

        ARGS 携带的是流式拼接的半截参数，只攒不推；其余三种状态变化都要让用户看见，
        尤其 START——工具卡住时用户至少知道卡在哪个工具上。
        """
        tool_id = str(_event_value(event, "toolCallId", "tool_call_id", default="") or "")
        name = str(_event_value(event, "toolCallName", "tool_call_name", default="") or "")
        if not tool_id:
            tool_id = name or "unknown"

        if event_type == EventType.TOOL_CALL_ARGS:
            tool = self._ensure_tool(tool_id, name)
            tool["args"] = (tool.get("args") or "") + str(_event_value(event, "delta", default="") or "")
            return False

        self.commit_text()
        tool = self._ensure_tool(tool_id, name)
        if event_type == EventType.TOOL_CALL_START:
            tool["status"] = "calling"
        elif event_type == EventType.TOOL_CALL_END:
            tool["status"] = "running"
        else:
            is_error = bool(_event_value(event, "isError", "is_error", default=False))
            result = str(_event_value(event, "content", default="") or "")
            tool["status"] = "error" if is_error else "ok"
            tool["result"] = _safe_tool_error(result) if is_error else ""
            tool["duration"] = _event_value(event, "duration", default=None)
            logger.info(
                f"stream_id:{self._stream_id} 工具结束 | name={tool['name']} "
                f"status={tool['status']} duration={tool['duration']}"
            )
        return True

    def render(self) -> str:
        blocks = []
        last_kind = ""
        for segment in self._segments:
            if segment["kind"] == "text":
                if segment["text"]:
                    blocks.append(segment["text"])
                    last_kind = "text"
            else:
                blocks.append(format_tool_markdown(segment["tool"]))
                last_kind = "tool"
        if self._pending:
            blocks.append(self._pending)
            last_kind = "text"
        content = "\n\n".join(blocks)
        # 企微会边接收边解析 Markdown。仅有工具引用块的中间快照如果没有空行闭合，
        # 客户端会把它当作尚未完成的引用段，直到下一帧/终态才显示图标。
        return content + "\n\n" if content and last_kind == "tool" else content

    def _ensure_tool(self, tool_id: str, name: str) -> dict:
        if tool_id in self._tools:
            tool = self._tools[tool_id]
            if name:
                tool["name"] = name
            return tool
        tool = {
            "id": tool_id,
            "name": name or "unknown",
            "status": "calling",
            "args": "",
            "result": "",
            "duration": None,
        }
        self._tools[tool_id] = tool
        self._segments.append({"kind": "tool", "tool": tool})
        return tool
