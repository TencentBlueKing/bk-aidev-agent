# -*- coding: utf-8 -*-
"""Phase 11.4 测试辅助：为直接调用 agent.run() 的测试提供 messages 预处理。

重构后 agent.py.prepare_stream 不再做 messages 处理，stream_input 通过
``AgentInput.stream_input`` 字段传入预处理结果。生产路径由 chat.py._stream 完成；
测试中直接创建 AidevAGUIAgent 并调用 run() 时，使用此辅助函数生成预处理结果，
调用方将 ``stream_input`` 放入 ``AgentInput`` body 传给 agent。

此函数为 sync，测试中直接调用。
"""

from typing import Any

from aidev_agent.core.ag_ui.utils import (
    get_stream_payload_input,
)
from aidev_agent.enums import PromptRole
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.types import Command


def _agui_messages_to_langchain(messages: list) -> list[BaseMessage]:
    """测试辅助：将 AGUI 消息（role dict/model 形态）转为 LangChain 消息。

    原 ``agui_messages_to_langchain``（生产零调用死代码）已删除；此处为测试辅助内联的
    安全替代，仅覆盖测试实际用到的 role（user/assistant/system/tool），
    不再复刻引入即炸的 ``tc.function.name`` 顶层 tool_call 暗雷。
    """
    langchain_messages: list[BaseMessage] = []
    for message in messages:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        msg_id = message.get("id") if isinstance(message, dict) else getattr(message, "id", None)
        content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
        if role == PromptRole.USER.value:
            langchain_messages.append(HumanMessage(id=msg_id, content=content))
        elif role == PromptRole.ASSISTANT.value:
            langchain_messages.append(AIMessage(id=msg_id, content=content or ""))
        elif role == PromptRole.SYSTEM.value:
            langchain_messages.append(SystemMessage(id=msg_id, content=content))
        elif role == PromptRole.TOOL.value:
            tool_call_id = (
                message.get("tool_call_id") if isinstance(message, dict) else getattr(message, "tool_call_id", None)
            )
            langchain_messages.append(ToolMessage(id=msg_id, content=content, tool_call_id=tool_call_id))
        # 其他 role（interrupt/info/reasoning）测试辅助用不到，跳过
    return langchain_messages


def _merge_state(
    state: dict[str, Any],
    messages: list[BaseMessage],
) -> dict[str, Any]:
    """合并 state：messages + tools + ag-ui 字段 + copilotkit 字段。

    与 ChatCompletionAgent._merge_state 逻辑一致。
    11.8: 改为接收原始 tools/context 字段（不接收 AgentInput），预处理在 agent_input 构造前完成。
    11.9: 签名收窄为 (state, messages)；tools 从 state.get("tools", []) 获取，
          context 固定为 []（原 tools/context 参数总是传空值）。
    """
    merged_messages = messages
    # 11.9: tools 从 state.get("tools", []) 获取（原 tools 参数总是传 []，等价）
    all_tools = state.get("tools", [])

    seen_names: set[str] = set()
    unique_tools: list = []
    for tool in all_tools:
        tool_name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
        if tool_name and tool_name not in seen_names:
            seen_names.add(tool_name)
            unique_tools.append(tool)
        elif not tool_name:
            unique_tools.append(tool)

    merged_state = {
        **state,
        "messages": merged_messages,
        "tools": unique_tools,
        "ag-ui": {"tools": unique_tools, "context": []},  # 11.9: context 固定 []
    }

    agui_properties = merged_state.get("ag-ui", {}) or merged_state
    return {
        **merged_state,
        "copilotkit": {
            "actions": agui_properties.get("tools", []),
            "context": agui_properties.get("context", []),
        },
    }


def _get_checkpoint_before_message(agent_e: Runnable, message_id: str, thread_id: str):
    """checkpoint 历史遍历，找 message_id 对应的前一个 checkpoint。

    与 ChatCompletionAgent._get_checkpoint_before_message 逻辑一致。
    """
    if not thread_id:
        raise ValueError("Missing thread_id in config")

    history_list = list(agent_e.get_state_history({"configurable": {"thread_id": thread_id}}))

    history_list.reverse()
    for idx, snapshot in enumerate(history_list):
        messages = snapshot.values.get("messages", [])
        if any(getattr(m, "id", None) == message_id for m in messages):
            if idx == 0:
                empty_snapshot = snapshot
                empty_snapshot.values["messages"] = []
                return empty_snapshot

            snapshot_values_without_messages = snapshot.values.copy()
            del snapshot_values_without_messages["messages"]
            checkpoint = history_list[idx - 1]

            merged_values = {
                **checkpoint.values,
                **snapshot_values_without_messages,
            }
            checkpoint = checkpoint._replace(values=merged_values)

            return checkpoint

    raise ValueError("Message ID not found in history")


def prepare_stream_data_for_agent(
    agent_e: Runnable,
    cfg: RunnableConfig,
    state: dict[str, Any],
    forwarded_props: Any,
    thread_id: str,
    messages: list,
    agent_state,
    schema_keys,
) -> dict[str, Any]:
    """为直接调用 agent.run() 的测试生成 stream_input。

    与 ChatCompletionAgent._prepare_stream_input 逻辑一致，但作为 sync 独立函数
    供测试使用（测试不经过 chat.py._stream）。调用方需将返回的 ``stream_input`` 放入
    ``AgentInput`` body 传给 agent。

    11.6：正常路径和兜底路径都构造 stream_input（与 chat.py 一致），接收 schema_keys 参数。
    11.7：返回值收窄（去掉 is_regenerate / langchain_messages），调用方需覆盖 agent_input.state 后再 run。
    11.8: 改为接收原始字段（不接收 AgentInput），预处理在 agent_input 构造前完成。
    11.9: 签名移除 tools/context（总是传空值），_merge_state 调用同步收窄。
    """
    state_input = state or {}
    forwarded_props = forwarded_props or {}
    resume_input = forwarded_props.get("command", {}).get("resume", None)
    thread_id = thread_id

    # 1. ag-ui → langchain 转换 + state 合并
    if resume_input:
        state = agent_state.values.copy() if agent_state.values else state_input
        langchain_messages: list[BaseMessage] = []
    else:
        state_input["messages"] = []
        langchain_messages = _agui_messages_to_langchain(messages)
        state = _merge_state(state_input, langchain_messages)

    # 2. regenerate 检测 + checkpoint 时间旅行
    non_system_messages = [msg for msg in langchain_messages if not isinstance(msg, SystemMessage)]
    if not resume_input and len(agent_state.values.get("messages", [])) > len(non_system_messages):
        last_user_message = None
        for i in range(len(langchain_messages) - 1, -1, -1):
            if isinstance(langchain_messages[i], HumanMessage):
                last_user_message = langchain_messages[i]
                break

        if last_user_message:
            time_travel_checkpoint = _get_checkpoint_before_message(agent_e, last_user_message.id, thread_id)

            if time_travel_checkpoint is not None:
                fork = agent_e.update_state(
                    time_travel_checkpoint.config,
                    time_travel_checkpoint.values,
                    as_node=time_travel_checkpoint.next[0] if time_travel_checkpoint.next else "__start__",
                )

                stream_input: Any = _merge_state(time_travel_checkpoint.values, [last_user_message])
                if resume := forwarded_props.get("command", {}).get("resume"):
                    # 47-02：Command 由 pre_run（chat.py _prepare_pre_run_history）唯一构造；
                    # 测试辅助直接构造现成 Command 供 prepare_stream 统一启动消费。
                    stream_input = Command(resume=resume)

                return {
                    "state": time_travel_checkpoint.values,
                    "stream_input": stream_input,
                    "fork": fork,
                }

    # 3. 正常路径：构造 stream_input（11.6：与 chat.py _prepare_stream_input 一致）
    if resume_input:
        # 47-02：分支 B 已删除，prepare_stream 只消费现成 Command（input.stream_input 即
        # Command → 统一启动）。测试辅助直接构造现成 Command（镜像 pre_run 产出）。
        stream_input: Any = Command(resume=resume_input)
    else:
        payload_input = get_stream_payload_input(
            mode="start",
            state=state,
            schema_keys=schema_keys,
        )
        stream_input = {**forwarded_props, **payload_input} if payload_input else None
        if not isinstance(stream_input, Command):
            stream_messages = stream_input["messages"] if stream_input else []
            stream_input = {**state, "messages": stream_messages}

    return {
        "state": state,
        "stream_input": stream_input,
        "fork": None,
    }
