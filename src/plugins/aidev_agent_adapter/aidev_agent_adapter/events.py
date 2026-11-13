"""将 ACP 更新转换为关联同一 run 的 AG-UI 生命周期。"""

import json

from ag_ui.core import (
    CustomEvent,
    RunErrorEvent,
    RunFinishedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)

from .journal import Journal


class EventMapper:
    def __init__(self, journal: Journal, run_id: str, thread_id: str):
        self.journal = journal
        self.run_id = run_id
        self.thread_id = thread_id
        self.message_number = 0
        self.active_message: tuple[str | None, str] | None = None
        self.tools: dict[str, dict] = {}
        self.done = False

    def emit(self, event) -> None:
        if not self.done:
            self.journal.append(self.run_id, event)

    def update(self, update) -> None:
        if self.done:
            return
        data = update.model_dump(mode="json", by_alias=True, exclude_none=True)
        kind = data.get("sessionUpdate")
        if kind == "agent_message_chunk" and data["content"].get("type") == "text":
            delta = data["content"]["text"]
            if not delta:
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

    def tool(self, data: dict) -> None:
        source = data["toolCallId"]
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

    def finish_tool(self, state: dict) -> None:
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
