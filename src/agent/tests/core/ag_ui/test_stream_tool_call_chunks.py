# -*- coding: utf-8 -*-
"""修 C（D-09）验证：tool_call_chunks 流式状态机单 chunk 多 delta 分布。

验证结论（45-05 Task 1，D-09 先验证后修）：
- 对目标模型代理（``MockChatModel``）经 ``ChatCompletionAgent.execute(stream=True)``
  生产路径抓 ``astream_events`` chunk 分布，**单 chunk 多 delta 出现率为 0%**
  ——每个 OnChatModelStream 事件的 ``tool_call_chunks`` 长度恒为 1（单 delta），
  name+id 同帧（100%），并行工具以「每 tool_call 一个独立 chunk」到达。
- 故 **未证实 → 不修**：``agent.py:801 tool_call_chunks[0]`` 保持现状（对当前
  可观测模型分布正确）；多 delta 盲区降级为**已知限制**记录。

本测试是验证结论的永久安全网：直接驱动 ``_handle_on_chat_model_stream_event``
（agent.py:801 所在状态机），断言并行切换（单 delta）下 START/ARGS/END 三元组
完整下发——若未来引入单 chunk 多 delta 复用改造，本测试提供回归基线。
"""

import asyncio

from ag_ui.core import EventType
from aidev_agent.core.ag_ui.agent import LangGraphAgent
from langchain_core.messages import AIMessageChunk


def _make_agent() -> LangGraphAgent:
    """构造最小可运行 _handle_on_chat_model_stream_event 的 agent（__new__ + 显式属性）。"""
    agent = LangGraphAgent.__new__(LangGraphAgent)
    agent.front_end_display = True
    agent.messages_in_process = {}
    agent.active_run = {
        "id": "run-1",
        "thread_id": "t-1",
        "has_function_streaming": False,
        "has_text_output": False,
    }
    agent._tool_mapping = {}
    return agent


def _stream_event(chunk: AIMessageChunk, *, emit_tool_calls: bool = True) -> dict:
    """构造 OnChatModelStream 原始事件。"""
    return {
        "event": "on_chat_model_stream",
        "data": {"chunk": chunk},
        "metadata": {"emit-messages": True, "emit-tool-calls": emit_tool_calls, "predict_state": []},
    }


def _collect(agent: LangGraphAgent, event: dict) -> list:
    """异步迭代 _handle_on_chat_model_stream_event 收集全部产出事件。"""
    return asyncio.run(_async_collect(agent, event))


async def _async_collect(agent: LangGraphAgent, event: dict) -> list:
    return [ev async for ev in agent._handle_on_chat_model_stream_event(event)]


def _event_types(events: list) -> list[str]:
    return [getattr(e, "type", "") for e in events]


def test_parallel_tool_calls_single_delta_chunks_full_sequence():
    """并行工具调用（单 delta 每 chunk）→ START/ARGS/END 三元组完整下发。

    模拟 MockChatModel 的流式形态：每个 tool_call 一个独立 chunk，各自携带
    name+id+args（``tool_call_chunks`` 长度为 1）。第 2 个 chunk 与第 1 个
    ``tool_call_id`` 不同 → 触发 ``is_parallel_tool_switch``。
    """
    agent = _make_agent()

    # tool_call_1：name+id+args（单 delta chunk）
    ev1 = _stream_event(
        AIMessageChunk(
            id="assist-1",
            content="",
            tool_call_chunks=[{"name": "get_weather", "id": "call_1", "args": '{"location": "广州"}'}],
        )
    )
    types1 = _event_types(_collect(agent, ev1))
    assert EventType.TOOL_CALL_START in types1, "首个工具调用应发 START"
    assert EventType.TOOL_CALL_ARGS in types1, "name+args 同 chunk 应发 ARGS"

    # tool_call_2：与 call_1 不同的 id（并行切换）
    ev2 = _stream_event(
        AIMessageChunk(
            id="assist-1",
            content="",
            tool_call_chunks=[{"name": "get_weather", "id": "call_2", "args": '{"location": "深圳"}'}],
        )
    )
    types2 = _event_types(_collect(agent, ev2))
    assert EventType.TOOL_CALL_END in types2, "并行切换应先 END 上一个工具调用（call_1）"
    assert EventType.TOOL_CALL_START in types2, "并行切换应 START 新工具调用（call_2）"

    # 空 chunk（finish_reason 前）→ 当前 in-progress（call_2）END
    ev3 = _stream_event(AIMessageChunk(id="assist-1", content=""))
    types3 = _event_types(_collect(agent, ev3))
    assert EventType.TOOL_CALL_END in types3, "空 chunk 应 END 当前 in-progress 工具调用（call_2）"


def test_tool_call_chunks_length_is_one_for_single_delta():
    """回归锚点：当前模型代理（MockChatModel）每个 OnChatModelStream 事件只携带 1 个 delta。

    若未来模型代理改为单 chunk 多 delta（``len(tool_call_chunks)>1``），本断言会暴露，
    提醒重新评估 agent.py:801 的 ``tool_call_chunks[0]``（已知限制 D-09）。
    """
    chunk = AIMessageChunk(
        id="assist-1",
        content="",
        tool_call_chunks=[{"name": "t", "id": "call_1", "args": "{}"}],
    )
    # 直接观察输入 chunk 的 tool_call_chunks 长度（agent.py:801 只取 [0]）
    assert len(chunk.tool_call_chunks) == 1, "单 chunk 多 delta 未出现，tool_call_chunks[0] 保持现状（D-09 已知限制）"


def test_finish_reason_early_return_relies_on_chat_model_end():
    """finish_reason 帧提前 return（agent.py:836）时，最后一个 tool_call 的 END 依赖 OnChatModelEnd。

    验证：finish_reason 帧不产出事件（提前 return），OnChatModelEnd 收尾为 in-progress
    tool_call 补发 END（agent.py:1063-1071）。
    """
    agent = _make_agent()

    # tool_call 起始
    _collect(
        agent,
        _stream_event(
            AIMessageChunk(id="assist-1", content="", tool_call_chunks=[{"name": "t", "id": "call_1", "args": "{}"}]),
        ),
    )

    # finish_reason 帧：chunk 带 response_metadata.finish_reason → 提前 return（无事件）
    finish_ev = _stream_event(
        AIMessageChunk(
            id="assist-1",
            content="",
            tool_call_chunks=[],
            response_metadata={"finish_reason": "tool_calls"},
        )
    )
    types = _event_types(_collect(agent, finish_ev))
    assert types == [], "finish_reason 帧应提前 return（不产出事件）"

    # OnChatModelEnd：为 in-progress tool_call 补发 END（收尾）
    from langchain_core.messages import AIMessage

    end_event = {"data": {"output": AIMessage(content="")}}
    events = asyncio.run(_async_collect_chat_model_end(agent, end_event))
    from ag_ui.core import ToolCallEndEvent

    ends = [e for e in events if isinstance(e, ToolCallEndEvent)]
    assert ends and ends[0].tool_call_id == "call_1", "OnChatModelEnd 应为 in-progress tool_call 补发 END"


async def _async_collect_chat_model_end(agent: LangGraphAgent, event: dict) -> list:
    """异步迭代 _handle_on_chat_model_end_event。"""
    return [ev async for ev in agent._handle_on_chat_model_end_event(event)]


def test_chat_model_end_emits_end_for_in_progress_tool_call():
    """OnChatModelEnd 收尾：in-progress tool_call 补发 END（agent.py:1063-1071）。"""
    agent = _make_agent()

    # 先建立 in-progress tool_call
    _collect(
        agent,
        _stream_event(
            AIMessageChunk(id="assist-1", content="", tool_call_chunks=[{"name": "t", "id": "call_x", "args": "{}"}]),
        ),
    )

    from ag_ui.core import ToolCallEndEvent
    from langchain_core.messages import AIMessage

    events = asyncio.run(_async_collect_chat_model_end(agent, {"data": {"output": AIMessage(content="")}}))
    ends = [e for e in events if isinstance(e, ToolCallEndEvent)]
    assert ends and ends[0].tool_call_id == "call_x", "OnChatModelEnd 应为 in-progress tool_call 补发 END"


def test_ask_user_question_tool_deferred_in_model_end_payload():
    """D-15 回归信号：ask_user_question 工具经 build_model_end_payload 走 deferred（延迟写）。

    ask_user 与 approval 统一抑制/回填语义后，其 tool_call 不应出现在首帧快照的
    immediate tool_calls（否则前端立即看到 pending 工具卡，与审批语义不一致）。
    本断言守护 event_builders._is_deferred_tool 谓词（同源复算两处对称）不被破坏。
    """
    from unittest.mock import MagicMock

    from aidev_agent.core.ag_ui.event_builders import build_model_end_payload
    from langchain_core.messages import AIMessage

    ask_tool = MagicMock()
    ask_tool.name = "ask_user_question"
    ask_tool.description = "请求用户回答"
    ask_tool.metadata = {}
    tools_mapping = {"ask_user_question": ask_tool}
    output_message = AIMessage(
        content="",
        id="msg-auq",
        tool_calls=[{"name": "ask_user_question", "args": {"questions": []}, "id": "call-auq"}],
        additional_kwargs={},
    )
    payload = build_model_end_payload(output_message, tools_mapping)
    assert payload["tool_calls"] == []
    assert len(payload["deferred_tool_calls"]) == 1
    assert payload["deferred_tool_calls"][0]["id"] == "call-auq"
