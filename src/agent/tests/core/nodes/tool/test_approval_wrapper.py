# -*- coding: utf-8 -*-
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.nodes.tool.approval_wrapper import (
    TOOL_APPROVAL_STATE_KEY,
    itsm_approval_async_wrapper,
    itsm_approval_sync_wrapper,
)
from aidev_agent.core.nodes.tool.node import build_tool_node
from aidev_agent.core.tools.ask_user_question import _ask_user_question, ask_user_question
from aidev_agent.packages.interrupt_manager import ASK_USER_QUESTION_REASON
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallWithContext
from langgraph.types import Command, Send


def _build_send_graph(tools, wrappers, first_tool_calls):
    """构造 model →(Send 分派)→ tools → model 的循环图，工具 wrapper 用 ITSM 审批 wrapper。"""

    def model_node(state):
        last = state["messages"][-1]
        if isinstance(last, HumanMessage):
            return {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[{**tc, "type": "tool_call"} if "type" not in tc else tc for tc in first_tool_calls],
                    )
                ]
            }
        return {"messages": [AIMessage(content="done")]}

    def route(state):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            done_ids = {m.tool_call_id for m in state["messages"] if isinstance(m, ToolMessage)}
            pending = [c for c in last.tool_calls if c["id"] not in done_ids]
            if pending:
                return [
                    Send(
                        "tools",
                        ToolCallWithContext(__type="tool_call_with_context", tool_call=c, state=state),
                    )
                    for c in pending
                ]
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("model", model_node)
    graph.add_node("tools", ToolNode(tools, wrap_tool_call=wrappers[0], awrap_tool_call=wrappers[1]))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", route)
    graph.add_edge("tools", "model")
    return graph.compile(checkpointer=MemorySaver())


def _flatten_interrupts(state) -> list:
    """从 StateSnapshot 拉平所有 task 的 interrupt 列表。"""
    out = []
    for t in state.tasks:
        out.extend(t.interrupts)
    return out


def _make_request(tool_call: dict, state: dict | None = None, tool=None):
    request = MagicMock()
    request.tool_call = tool_call
    request.state = state if state is not None else {}
    request.tool = tool
    request.runtime = MagicMock()
    request.runtime.config = {}
    return request


class TestItsmApprovalWrapper:
    @pytest.mark.parametrize(
        "decision, should_execute",
        [
            ({"toolCallId": "call_1", "status": "approved"}, True),
            ({"toolCallId": "call_1", "status": "rejected"}, False),
        ],
    )
    def test_approval_decision(self, decision, should_execute):
        """审批通过放行 execute，审批拒绝短路返回拒绝 ToolMessage。"""
        tool = MagicMock()
        tool.name = "calculator"
        tool.metadata = {"approval": {"approval_enabled": True}}
        request = _make_request(
            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
            state={"messages": [AIMessage(content="")]},
            tool=tool,
        )
        wrapper = itsm_approval_sync_wrapper
        executed = []

        def execute(req):
            executed.append(req)
            return ToolMessage(content="ok", tool_call_id="call_1")

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
            return_value=decision,
        ):
            result = wrapper(request, execute)
        if should_execute:
            assert len(executed) == 1
            assert result.content == "ok"
        else:
            assert len(executed) == 0
            assert result.status == "error"
            assert "审批未通过" in result.content

    def test_approval_mismatched_tool_call_id_rejects(self):
        """resume 返回的 toolCallId 与当前 tool_call 不一致时视为拒绝。"""
        tool = MagicMock()
        tool.name = "calculator"
        tool.metadata = {"approval": {"approval_enabled": True}}
        request = _make_request(
            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
            state={"messages": [AIMessage(content="")]},
            tool=tool,
        )
        wrapper = itsm_approval_sync_wrapper
        executed = []

        def execute(req):
            executed.append(req)
            return ToolMessage(content="ok", tool_call_id="call_1")

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
            return_value={"toolCallId": "call_999", "status": "approved"},
        ):
            result = wrapper(request, execute)
        assert len(executed) == 0
        assert result.status == "error"

    # ------------------------------------------------------------------ #
    # D-05：重复审批短路 + 直抛 ApprovalTarget（alias 协议名 + reason）
    # ------------------------------------------------------------------ #

    def test_approval_no_terminal_state_calls_interrupt_with_alias_value(self):
        """① state 无终态 → 调 interrupt(value)，value 为 alias 协议名 + reason，approved → execute。"""
        tool = MagicMock()
        tool.name = "calculator"
        tool.metadata = {"approval": {"approval_enabled": True}}
        request = _make_request(
            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
            state={"messages": [AIMessage(content="")]},
            tool=tool,
        )
        wrapper = itsm_approval_sync_wrapper
        executed = []

        def execute(req):
            executed.append(req)
            return ToolMessage(content="ok", tool_call_id="call_1")

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
            return_value={"toolCallId": "call_1", "status": "approved"},
        ) as mock_interrupt:
            result = wrapper(request, execute)

        # 无终态 → 调 interrupt 一次
        mock_interrupt.assert_called_once()
        value = mock_interrupt.call_args.args[0]
        # value 为 alias 协议名 + reason（不含 payload/metadata）
        assert value["toolCallId"] == "call_1"
        assert value["toolName"] == "calculator"
        assert value["toolArgs"] == {"a": 1, "b": 2}
        assert value["reason"] == "aidev:tool_approval"
        assert "metadata" not in value
        assert "callbackToken" not in value
        # approved decision → execute
        assert len(executed) == 1
        assert result.content == "ok"

    def test_approval_approved_terminal_state_skips_interrupt(self):
        """② state approved 终态 → 不调 interrupt，直接 execute。"""
        tool = MagicMock()
        tool.name = "calculator"
        tool.metadata = {"approval": {"approval_enabled": True}}
        request = _make_request(
            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
            state={
                "messages": [
                    AIMessage(
                        content="",
                        additional_kwargs={TOOL_APPROVAL_STATE_KEY: {"call_1": {"status": "approved"}}},
                    )
                ]
            },
            tool=tool,
        )
        wrapper = itsm_approval_sync_wrapper
        executed = []

        def execute(req):
            executed.append(req)
            return ToolMessage(content="ok", tool_call_id="call_1")

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
        ) as mock_interrupt:
            result = wrapper(request, execute)

        mock_interrupt.assert_not_called()
        assert len(executed) == 1
        assert result.content == "ok"

    def test_approval_rejected_terminal_state_short_circuits(self):
        """③ state rejected 终态 → 不调 interrupt，返回拒绝 ToolMessage。"""
        tool = MagicMock()
        tool.name = "calculator"
        tool.metadata = {"approval": {"approval_enabled": True}}
        request = _make_request(
            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
            state={
                "messages": [
                    AIMessage(
                        content="",
                        additional_kwargs={TOOL_APPROVAL_STATE_KEY: {"call_1": {"status": "rejected"}}},
                    )
                ]
            },
            tool=tool,
        )
        wrapper = itsm_approval_sync_wrapper
        executed = []

        def execute(req):
            executed.append(req)
            return ToolMessage(content="ok", tool_call_id="call_1")

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
        ) as mock_interrupt:
            result = wrapper(request, execute)

        mock_interrupt.assert_not_called()
        assert len(executed) == 0
        assert result.status == "error"
        assert "审批未通过" in result.content


class TestUserQuestionToolDirectInterrupt:
    """D-12：ask_user 工具本体直调 interrupt() 的行为测试。

    UserQuestionStrategy 已删除，提问中断逻辑下沉到 ask_user_question 工具函数：
    构造 AskUserQuestionTarget → interrupt(target.model_dump()) → 答案经
    parse_resume_answers 直接作为工具返回值（interrupt() 前零副作用，Pitfall 3）。
    """

    def test_user_question_tool_direct_interrupt_builds_target_and_returns_answer(self):
        """工具函数直接调 interrupt(target.model_dump())，答案经 parse_resume_answers 返回。"""
        # 工具函数在 ToolNode 内由 ToolRuntime 注入，直接调用函数本身（非 wrapper）。
        # 用 patch 拦截 ask_user_question 模块内的 interrupt 以断言 target 形态与返回值。
        runtime = MagicMock()
        runtime.tool_call_id = "q1"
        with patch(
            "aidev_agent.core.tools.ask_user_question.interrupt",
            return_value={"answers": [{"answer": "A"}]},
        ) as mock_interrupt:
            result = _ask_user_question(
                [{"question": "选哪个?"}],
                runtime=runtime,
            )

        # 工具直调 interrupt(target.model_dump())：5 键 target 形态
        mock_interrupt.assert_called_once()
        value = mock_interrupt.call_args.args[0]
        assert value["questions"] == [{"question": "选哪个?", "header": None, "multiSelect": False, "options": None}]
        assert value["interrupt_reason"] == ASK_USER_QUESTION_REASON
        assert value["message"] == "请求用户回答以下问题"
        assert value["toolCallId"] == "q1"
        assert "expiresAt" in value, "target 形态应含 expiresAt 字段"
        from datetime import datetime

        assert datetime.fromisoformat(value["expiresAt"]).tzinfo is not None
        # target 形态无 reason / id / metadata
        assert "reason" not in value, "target 形态不应含 reason 键"
        assert "id" not in value, "target 形态不应含随机 id"
        assert "metadata" not in value, "target 形态不应含 metadata"
        # 答案经 parse_resume_answers 直接作为工具返回值（不再写入 state key）
        assert result == [{"answer": "A"}]

    def test_user_question_invalid_questions_returns_error_tool_message(self):
        """ToolNode 统一异常处理 — build_tool_node 装配 interrupt 策略 + ask_user_question 工具，
        非法 questions → 工具内 AskUserQuestionTarget 构造直抛 ValidationError →
        default_tool_call_handler 兜底为 error ToolMessage，不抛异常、不产生 GraphInterrupt。"""
        # build_tool_node 默认装配 ItsmApprovalStrategy（ask_user 无审批配置不触发）
        # + handle_tool_errors=default_tool_call_handler（统一异常处理）。
        tool_node = build_tool_node([ask_user_question])
        # 非法 questions（str 而非 list）→ 工具内 AskUserQuestionTarget 校验失败直抛 ValidationError
        tool_call = {
            "name": "ask_user_question",
            "args": {"questions": "not-a-list"},
            "id": "q_bad",
            "type": "tool_call",
        }
        # 经图 invoke（ToolNode 需在图中运行以注入 tool_runtime），不抛异常、不产生中断，
        # 返回 error ToolMessage（default_tool_call_handler 去异常类型）。
        graph = StateGraph(MessagesState)
        graph.add_node("tools", tool_node)
        graph.add_edge(START, "tools")
        graph.add_edge("tools", END)
        compiled = graph.compile()
        result = compiled.invoke({"messages": [AIMessage(content="", tool_calls=[tool_call])]})
        tool_msgs = [m for m in result.get("messages", []) if isinstance(m, ToolMessage)]
        assert tool_msgs, "非法 questions 应返回 error ToolMessage"
        assert tool_msgs[0].status == "error"
        # 去异常类型：内容为字段校验错误信息（含 questions 字段），非完整 traceback/异常类型
        assert "questions" in tool_msgs[0].content


class TestItsmApprovalWrapperAsync:
    @pytest.mark.asyncio
    async def test_async_wrapper_rejects_without_execute(self):
        """异步 wrapper 审批拒绝时短路返回，不执行工具。"""
        tool = MagicMock()
        tool.name = "calculator"
        tool.metadata = {"approval": {"approval_enabled": True}}
        request = _make_request(
            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
            state={"messages": [AIMessage(content="")]},
            tool=tool,
        )
        wrapper = itsm_approval_async_wrapper
        executed = []

        async def execute(req):
            executed.append(req)
            return ToolMessage(content="ok", tool_call_id="call_1")

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
            return_value={"toolCallId": "call_1", "status": "rejected"},
        ):
            result = await wrapper(request, execute)
        assert len(executed) == 0
        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_async_wrapper_approves_and_executes(self):
        """异步 wrapper 审批通过时执行工具。"""
        tool = MagicMock()
        tool.name = "calculator"
        tool.metadata = {"approval": {"approval_enabled": True}}
        request = _make_request(
            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
            state={"messages": [AIMessage(content="")]},
            tool=tool,
        )
        wrapper = itsm_approval_async_wrapper
        executed = []

        async def execute(req):
            executed.append(req)
            return ToolMessage(content="ok", tool_call_id="call_1")

        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
            return_value={"toolCallId": "call_1", "status": "approved"},
        ):
            result = await wrapper(request, execute)
        assert len(executed) == 1
        assert result.content == "ok"


# ============================================================================
# 集成测试：Send 分派图 + approval_wrapper 端到端（场景 1 审批 / 2 提问 / 5 并行审批）
# ============================================================================


class TestIntegrationApprovalReject:
    """场景 1：审批拒绝短路 —— 工具不执行，返回拒绝 ToolMessage。"""

    @pytest.mark.asyncio
    async def test_rejected_tool_short_circuits(self):
        executed = []

        @tool
        def my_tool(x: int) -> int:
            """Add one to x."""
            executed.append(x)
            return x + 1

        my_tool.metadata = {"approval": {"approval_enabled": True}}
        sync_wrapper = itsm_approval_sync_wrapper
        app = _build_send_graph(
            [my_tool],
            [sync_wrapper, None],
            [{"name": "my_tool", "args": {"x": 1}, "id": "cA"}],
        )
        cfg = {"configurable": {"thread_id": "itg-reject"}}
        with patch(
            "aidev_agent.core.nodes.tool.approval_wrapper.interrupt",
            return_value={"toolCallId": "cA", "status": "rejected"},
        ):
            await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        assert executed == [], "审批拒绝时工具不应执行"
        state = await app.aget_state(cfg)
        tool_msgs = [m for m in state.values.get("messages", []) if isinstance(m, ToolMessage)]
        assert tool_msgs and tool_msgs[0].status == "error"


class TestIntegrationParallelApproval:
    """场景 5：并行审批走策略真实 interrupt 路径，各产生独立 interrupt 且可按 id resume。"""

    @pytest.mark.asyncio
    async def test_two_parallel_interrupts_resume_by_id(self):
        @tool
        def needs_approval(action: str) -> str:
            """Return approved result for action."""
            return f"approved:{action}"

        needs_approval.metadata = {"approval": {"approval_enabled": True}}
        sync_wrapper = itsm_approval_sync_wrapper
        app = _build_send_graph(
            [needs_approval],
            [sync_wrapper, None],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "itg-par"}}
        # 新策略直抛 ApprovalTarget（无建单副作用），保留 interrupt() 真实路径（真正抛 GraphInterrupt）。
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = _flatten_interrupts(state)
        assert len(intrs) == 2, "Send 分派下两个策略审批各产生独立 interrupt"
        assert all(i.value.get("reason") == "aidev:tool_approval" for i in intrs)
        # 按 interrupt id resume，value 的 toolCallId 与各 task 的 tool_call 一致
        resume_map = {i.id: {"toolCallId": i.value["toolCallId"], "status": "approved"} for i in intrs}
        await app.ainvoke(Command(resume=resume_map), config=cfg)
        final = await app.aget_state(cfg)
        tool_msgs = [m for m in final.values.get("messages", []) if isinstance(m, ToolMessage)]
        by_id = {m.tool_call_id: m.content for m in tool_msgs}
        assert by_id == {"cA": "approved:A", "cB": "approved:B"}


class TestIntegrationUserQuestion:
    """场景 2：D-12 提问直调 —— ask_user 工具本体 interrupt() 后续流产生答案工具 ToolMessage。"""

    @pytest.mark.asyncio
    async def test_user_question_direct_interrupt_produces_answer_toolmessage(self):
        # D-12：中断由工具本体直调，wrapper 仅剩 ItsmApprovalStrategy（ask_user 无审批不触发）。
        # 用真实策略 wrapper 链装配，验证工具内部 interrupt() 在 Send 分派拓扑下正常工作。
        sync_wrapper = itsm_approval_sync_wrapper
        app = _build_send_graph(
            [ask_user_question],
            [sync_wrapper, None],
            [{"name": "ask_user_question", "args": {"questions": [{"question": "选哪个?"}]}, "id": "q1"}],
        )
        cfg = {"configurable": {"thread_id": "itg-q"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = _flatten_interrupts(state)
        assert (
            intrs and (intrs[0].value.get("reason") or intrs[0].value.get("interrupt_reason")) == "aidev:user_question"
        )
        await app.ainvoke(
            Command(resume={i.id: {"answers": [{"answer": "A"}]} for i in intrs}),
            config=cfg,
        )
        final = await app.aget_state(cfg)
        tool_msgs = [m for m in final.values.get("messages", []) if isinstance(m, ToolMessage)]
        assert tool_msgs, "提问续流后应产生工具 ToolMessage"
        # D-12：答案经 parse_resume_answers 作为工具返回值进入 ToolMessage content
        assert any("A" in str(m.content) for m in tool_msgs), (
            f"ToolMessage content 应包含用户答案，实际: {[m.content for m in tool_msgs]}"
        )
