"""将 ACP 更新转换为关联同一 run 的 AG-UI 生命周期，并统一负责中断收口事件生成。"""

import json
from typing import Any

from ag_ui.core import (
    CustomEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)


def build_abort_events(
    persisted_events: list[dict[str, Any]],
    *,
    thread_id: str,
    run_id: str,
    code: str,
    message: str,
) -> list[Any]:
    """根据已落盘事件重建未闭合的文本/工具生命周期，并以 RUN_ERROR 原子收口。"""
    messages: set[str] = set()
    tools: dict[str, dict[str, Any]] = {}
    started = False
    for event in persisted_events:
        kind = event.get("type")
        if kind == "RUN_STARTED":
            started = True
        elif kind == "TEXT_MESSAGE_START":
            messages.add(event["messageId"])
        elif kind == "TEXT_MESSAGE_END":
            messages.discard(event["messageId"])
        elif kind == "TOOL_CALL_START":
            tools[event["toolCallId"]] = {"args": False, "end": False}
        elif kind in {"TOOL_CALL_ARGS", "TOOL_CALL_END"} and event.get("toolCallId") in tools:
            tools[event["toolCallId"]]["args" if kind == "TOOL_CALL_ARGS" else "end"] = True
        elif kind == "CUSTOM" and event.get("name") == "acp.tool_status":
            value = event.get("value") or {}
            tid = value.get("toolCallId")
            update = value.get("update") or {}
            if tid in tools:
                if "rawInput" in update:
                    tools[tid]["input"] = update["rawInput"]
                if "rawOutput" in update:
                    tools[tid]["output"] = update["rawOutput"]
                elif "content" in update:
                    tools[tid]["output"] = update["content"]
        elif kind == "TOOL_CALL_RESULT":
            tools.pop(event.get("toolCallId"), None)

    closing: list[Any] = []
    if not started:
        closing.append(RunStartedEvent(thread_id=thread_id, run_id=run_id))
    for message_id in sorted(messages):
        closing.append(TextMessageEndEvent(message_id=message_id))
    for tool_id, state in tools.items():
        if not state["args"]:
            closing.append(ToolCallArgsEvent(tool_call_id=tool_id, delta=json.dumps(state.get("input", {}))))
        if not state["end"]:
            closing.append(ToolCallEndEvent(tool_call_id=tool_id))
        result_payload: dict[str, Any] = {"status": "unknown"}
        if "output" in state:
            result_payload["output"] = state["output"]
        closing.append(
            ToolCallResultEvent(
                tool_call_id=tool_id,
                message_id=f"{tool_id}:result",
                role="tool",
                content=json.dumps(result_payload),
            )
        )
    closing.append(RunErrorEvent(message=message, code=code))
    return closing


class EventMapper:
    def __init__(self, journal, run_id: str, thread_id: str):
        self.journal = journal
        self.run_id = run_id
        self.thread_id = thread_id
        self.message_number = 0
        self.active_message: tuple[str | None, str] | None = None
        self.tools: dict[str, dict[str, Any]] = {}
        self.done = False

    def emit(self, event) -> None:
        if not self.done:
            self.journal.append(self.run_id, event)

    def update(self, update) -> None:
        if self.done:
            return
        data = update.model_dump(mode="json", by_alias=True, exclude_none=True)
        kind = data.get("sessionUpdate")
        content = data.get("content")
        if kind == "agent_message_chunk" and isinstance(content, dict) and content.get("type") == "text":
            delta = content.get("text")
            if not isinstance(delta, str) or not delta:
                return
            source_id = data.get("messageId")
            if self.active_message is None or self.active_message[0] != source_id:
                self.close_message()
                self.message_number += 1
                self.active_message = (source_id, f"{self.run_id}:message:{self.message_number}")
                self.emit(TextMessageStartEvent(message_id=self.active_message[1]))
            self.emit(TextMessageContentEvent(message_id=self.active_message[1], delta=delta))
        elif kind in {"tool_call", "tool_call_update"}:
            self.tool(data)
        else:
            # 保留计划、思考和非文本内容，不能丢弃或伪装成 assistant 文本。
            self.emit(CustomEvent(name="acp.session_update", value=data))

    def close_message(self) -> None:
        if self.active_message is not None:
            self.emit(TextMessageEndEvent(message_id=self.active_message[1]))
            self.active_message = None

    def tool(self, data: dict[str, Any]) -> None:
        source = data.get("toolCallId")
        if not isinstance(source, str) or not source:
            raise ValueError("missing toolCallId in ACP tool update")
        if source in self.tools and self.tools[source]["done"]:
            return
        self.close_message()
        if source not in self.tools:
            tool_id = f"{self.run_id}:tool:{len(self.tools) + 1}"
            self.tools[source] = {"id": tool_id, "done": False}
            self.emit(ToolCallStartEvent(tool_call_id=tool_id, tool_call_name=data.get("title") or "tool"))
        state = self.tools[source]
        state.update({key: data[key] for key in ("rawInput", "rawOutput", "content", "status") if key in data})
        self.emit(CustomEvent(name="acp.tool_status", value={"toolCallId": state["id"], "update": data}))
        if state.get("status") in {"completed", "failed"}:
            self.finish_tool(state)

    def finish_tool(self, state: dict[str, Any]) -> None:
        # rawInput 是快照，不能把每次更新当作 JSON delta 追加。
        self.emit(ToolCallArgsEvent(tool_call_id=state["id"], delta=json.dumps(state.get("rawInput", {}))))
        self.emit(ToolCallEndEvent(tool_call_id=state["id"]))
        content = {"status": state.get("status", "unknown"), "output": state.get("rawOutput", state.get("content", []))}
        self.emit(
            ToolCallResultEvent(
                tool_call_id=state["id"], message_id=f"{state['id']}:result", content=json.dumps(content), role="tool"
            )
        )
        state["done"] = True

    def finish(self, stop_reason: str | None = None, *, error: str | None = None) -> None:
        if self.done:
            return
        self.close_message()
        for state in self.tools.values():
            if not state["done"]:
                state["status"] = "unknown"
                self.finish_tool(state)
        event = (
            RunErrorEvent(message="ACP execution interrupted; outcome unknown", code=error)
            if error
            else RunFinishedEvent(thread_id=self.thread_id, run_id=self.run_id, result={"stopReason": stop_reason})
        )
        self.journal.append(self.run_id, event, terminal=True)
        self.done = True
