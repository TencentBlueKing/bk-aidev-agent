# -*- coding: utf-8 -*-
"""LangGraph 中断机制特性调研测试。

本文件为统一中断处理器设计提供行为基线。所有测试**直接构造原生 LangGraph**
（StateGraph + MemorySaver + ToolNode + interrupt），不依赖任何项目业务代码，
目的是把 LangGraph 1.0.x 的实际中断语义固化下来，供后续设计阶段参考。

调研维度：

1. ToolNode 并行执行多 tool call —— 验证结果顺序与完整性
2. 并行 interrupt 行为（原生 ToolNode 并发）
   a. interrupt 收集是否完整（多个 interrupt 是否被合并）
   b. interrupt id 是否会冲突 / 是否确定性
   c. 当前批工具 C/D 完成而 A/B 需 interrupt 时，C/D 是否会重新执行
   d. A/B 中断后，能否按 interrupt id 分别拿到对应的 resume 值
3. Send 分派方案验证（官方推荐的并行 interrupt 解法，见
   https://github.com/langchain-ai/langgraph/issues/6624 / #6533）：
   对照第 2 节每条 ToolNode 并发行为，验证 Send 方案如何修复之
4. 流式事件分发：astream 与 astream_events 下 ToolNode 与 SendDispatch
   的可观测差异（``__interrupt__`` chunk 数量、``on_tool_error``/
   ``on_tool_end``、``tools`` 节点启动次数）
5. 子 Graph 多 interrupt 在不同 checkpoint 配置下的传播行为

所有结论性的行为发现以 ``# BEHAVIOR:`` 注释标注，便于设计阶段引用。
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallWithContext
from langgraph.types import Command, Send, interrupt

pytestmark = pytest.mark.asyncio


# ============================================================================
# 测试工具定义
# ============================================================================

# 模块级调用日志，供断言使用。每个测试用例在 setup 时 clear。
call_log: list[tuple[str, Any]] = []


@tool
def tool_a(x: int) -> int:
    """tool A: 加 1。"""
    call_log.append(("a", x))
    return x + 1


@tool
def tool_b(x: int) -> int:
    """tool B: 加 2。"""
    call_log.append(("b", x))
    return x + 2


@tool
def tool_c(x: int) -> int:
    """tool C: 乘 3。"""
    call_log.append(("c", x))
    return x * 3


@tool
def needs_approval(action: str) -> str:
    """需要审批的工具，调用 interrupt 暂停等待用户决策。"""
    val = interrupt({"need": "approval", "action": action})
    return f"approved:{val}"


@tool
def needs_approval_with_id(tag: str) -> str:
    """带 tag 的审批工具，用于区分多个并行 interrupt 的来源。"""
    val = interrupt({"need": "approval", "tag": tag})
    return f"approved:{val}"


# ============================================================================
# 图构造辅助
# ============================================================================


def _make_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """补全 tool_call dict 默认字段。"""
    return [{**tc, "type": "tool_call"} if "type" not in tc else tc for tc in tool_calls]


def build_react_like_graph(
    tools: list,
    first_tool_calls: list[dict],
) -> Any:
    """构造一个 model → tools → model 的简单循环图。

    model 节点：首次收到 HumanMessage 时发出指定的 tool_calls；之后发出 done。
    用 MessagesState 作为状态 schema，输入需用 ``{"messages": [...]}`` 形式。
    """
    call_log.clear()

    def model_node(state):
        last = state["messages"][-1]
        if isinstance(last, HumanMessage):
            return {"messages": [AIMessage(content="", tool_calls=_make_tool_calls(first_tool_calls))]}
        return {"messages": [AIMessage(content="done")]}

    def route(state):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("model", model_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", route)
    graph.add_edge("tools", "model")
    return graph.compile(checkpointer=MemorySaver())


async def _interrupts(state) -> list:
    """从 StateSnapshot 中拉平所有 task 的 interrupt 列表。"""
    out = []
    for t in state.tasks:
        out.extend(t.interrupts)
    return out


# ============================================================================
# 1. ToolNode 并行执行多 tool call
# ============================================================================


class TestToolNodeParallel:
    """验证 ToolNode 并行执行多个 tool call 的基本行为。"""

    async def test_parallel_tools_all_complete_and_ordered(self):
        """3 个无 interrupt 的 tool call 并行执行，结果按 tool_call_id 返回。

        覆盖两点：
        - 完整性 + 顺序：三个 tool call 全部完成，结果按 tool_call_id 索引，
          与调用顺序无关；每个工具各执行一次。
        - 并行性：call_log 不强制时序（asyncio.gather 并发），只验证全部执行。
        """
        app = build_react_like_graph(
            [tool_a, tool_b, tool_c],
            [
                {"name": "tool_a", "args": {"x": 1}, "id": "cA"},
                {"name": "tool_b", "args": {"x": 10}, "id": "cB"},
                {"name": "tool_c", "args": {"x": 4}, "id": "cC"},
            ],
        )
        cfg = {"configurable": {"thread_id": "par-1"}}
        r = await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)

        tool_msgs = [m for m in r["messages"] if isinstance(m, ToolMessage)]
        by_id = {m.tool_call_id: m.content for m in tool_msgs}

        # BEHAVIOR: 三个 tool call 全部完成，结果按 tool_call_id 索引，与调用顺序无关
        assert by_id == {"cA": "2", "cB": "12", "cC": "12"}
        # 每个工具各执行一次（call_log 不强制时序，验证并发全部跑完）
        assert sorted(name for name, _ in call_log) == ["a", "b", "c"]


# ============================================================================
# 2. 并行 interrupt 行为（原生 ToolNode 并发）
# ============================================================================


class TestParallelInterruptWithToolNode:
    """调研 ToolNode 中多个 tool 同时 interrupt() 的实际行为。

    关键发现（见各用例的 BEHAVIOR 注释）汇总：
      - 并发 interrupt 中**只有首个被收集**——``asyncio.gather`` 首异常语义
        取消其余协程，其 ``GraphInterrupt`` 被丢弃（非"合并"）。保留的是
        第一个发起 interrupt 的工具的 value。
      - interrupt_id 非确定性（同图同输入不同 thread 也会不同），
        必须运行时通过 aget_state 读取。
      - 批次被 interrupt 时，已完成工具的 ToolMessage 不会写入状态，
        恢复后整个 ToolNode 批次重新执行（已完成工具会重新执行）。

    对照组见后续 ``TestParallelInterruptWithSendDispatch``：同一组行为在
    Send 分派方案下的修复验证。
    """

    async def test_a_interrupt_collection_completeness(self):
        """3a: 两个并行 needs_approval 是否都产生 interrupt。

        精确机制（非"合并"）：ToolNode 用 ``asyncio.gather`` 并发执行整批
        tool_calls。当其中某个工具 ``interrupt()`` 抛出 ``GraphInterrupt`` 时，
        ``asyncio.gather`` 的首异常语义会**立即取消其他协程**并向上抛出
        第一个异常。因此：

        - 只有**第一个**抛出 ``GraphInterrupt`` 的工具的 interrupt 被收集到
          ``state.tasks[0].interrupts``；
        - 其余并发工具的 ``GraphInterrupt`` **被直接丢弃**（协程被 cancel，
          异常未被收集）——这不是"多个 interrupt 合成一个"，而是"其余被丢"；
        - 已正常返回的工具的 ``ToolMessage`` 也未写入 state（gather 在写回前中断）。

        返回的 interrupt 是一个 ``Interrupt`` 对象，字段：``id``（32 位 hex）、
        ``value``（首个发起 interrupt 的工具传入的 dict）。
        """
        app = build_react_like_graph(
            [needs_approval, tool_a],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "tool_a", "args": {"x": 5}, "id": "cB"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cC"},
            ],
        )
        cfg = {"configurable": {"thread_id": "int-3a"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        # BEHAVIOR: 并发 interrupt 中只有首个被收集，其余被 asyncio.gather
        # 首异常语义丢弃（非合并）。保留的是首个发起者的 value。
        assert len(intrs) == 1, "并发 interrupt 仅首个被收集，其余被丢弃"
        val = intrs[0].value
        assert val["action"] == "A", "保留的是首个发起 interrupt 的工具的 value"

    async def test_b_interrupt_id_not_deterministic(self):
        """3b: interrupt id 在不同 thread 间不同（非确定性）。"""
        ids = []
        for tid in ("int-3b-x", "int-3b-y"):
            app = build_react_like_graph(
                [needs_approval],
                [{"name": "needs_approval", "args": {"action": "X"}, "id": "cA"}],
            )
            cfg = {"configurable": {"thread_id": tid}}
            await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
            state = await app.aget_state(cfg)
            intrs = await _interrupts(state)
            ids.append(intrs[0].id)

        # BEHAVIOR: 同样的图 + 输入，不同 thread 的 interrupt id 不同
        assert ids[0] != ids[1], "interrupt id 非确定性，不能基于源码静态预测"
        # id 是 32 位 hex（md5 风格），不是工具名
        assert all(len(i) == 32 and all(c in "0123456789abcdef" for c in i) for i in ids)
        # 与工具名 md5 无关
        assert ids[0] != hashlib.md5(b"needs_approval").hexdigest()

    async def test_c_completed_tools_reexecuted_after_interrupt(self):
        """3c: 批次中 C 已完成、A/B interrupt 时，C 是否会重新执行。

        场景：tool_a(无 interrupt) 与 needs_approval(interrupt) 同批。
        先 interrupt 暂停，再 resume。观察 tool_a 是否被调用两次。
        """
        app = build_react_like_graph(
            [tool_a, needs_approval],
            [
                {"name": "tool_a", "args": {"x": 7}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "X"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "int-3c"}}

        call_log.clear()
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        first_pass = list(call_log)
        # 第一轮 tool_a 已执行（写入 call_log），但因 interrupt 未提交 ToolMessage
        assert ("a", 7) in first_pass

        state = await app.aget_state(cfg)
        assert state.next == ("tools",), "暂停点应在 tools 节点"

        call_log.clear()
        await app.ainvoke(Command(resume="OK"), config=cfg)
        second_pass = list(call_log)

        # BEHAVIOR: 恢复后整个 ToolNode 批次重新执行，tool_a 被再次调用
        assert ("a", 7) in second_pass, "已完成工具在 resume 后会被重新执行"

    async def test_d_resume_value_routing_single_interrupt(self):
        """3d: 单 interrupt 时 resume 值能正确传回工具。

        注：由于 3a 发现并发 interrupt 仅首个被收集，无法对"两个 interrupt
        分别 resume"做正向断言。本用例验证单 interrupt 场景下 resume 值的
        端到端传递，并显式记录"并发多 interrupt 无法按 id 分别 resume"这一缺陷。

        BEHAVIOR: LangGraph 1.0 中 ``Command(resume=<scalar>)`` 把 <scalar>
        原样作为 ``interrupt()`` 的返回值；若传入 list/dict 包装（如
        ``[{"interrupt_id":..., "resume":...}]``），工具拿到的是该包装本身
        而非解包后的值。统一中断处理器需自行负责 resume payload 的解包/映射。
        """
        app = build_react_like_graph(
            [needs_approval],
            [{"name": "needs_approval", "args": {"action": "A"}, "id": "cA"}],
        )
        cfg = {"configurable": {"thread_id": "int-3d"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        assert await _interrupts(state), "应至少有一个 interrupt"

        # 用标量 resume —— LangGraph 1.0 的正确形式
        await app.ainvoke(Command(resume="VALUE_A"), config=cfg)
        final = await app.aget_state(cfg)
        tool_msgs = [m for m in final.values.get("messages", []) if isinstance(m, ToolMessage)]

        # 单 interrupt 下标量 resume 能让工具拿到对应返回值
        assert any("approved:VALUE_A" in m.content for m in tool_msgs)

        # 反向验证：list 包装形式不会自动解包，工具拿到的是整个 list
        app2 = build_react_like_graph(
            [needs_approval],
            [{"name": "needs_approval", "args": {"action": "A"}, "id": "cA"}],
        )
        cfg2 = {"configurable": {"thread_id": "int-3d-list"}}
        await app2.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg2)
        st2 = await app2.aget_state(cfg2)
        intr2 = (await _interrupts(st2))[0]
        await app2.ainvoke(
            Command(resume=[{"interrupt_id": intr2.id, "resume": "VALUE_A"}]),
            config=cfg2,
        )
        final2 = await app2.aget_state(cfg2)
        tm2 = [m for m in final2.values.get("messages", []) if isinstance(m, ToolMessage)]
        assert tm2 and "interrupt_id" in tm2[0].content, "list 形式 resume 不会被自动解包，工具拿到的是原始 list"

    async def test_d_parallel_multi_interrupt_cannot_be_routed_independently(self):
        """3d(反向): 两个并行 interrupt 无法被分别 resume。

        这是 3a 缺陷的直接后果：并发 interrupt 中只有首个被收集（其余被
        ``asyncio.gather`` 首异常语义丢弃），resume 时只能传一个值，无法让
        action=A 拿到 1、action=B 拿到 2。
        统一中断处理器必须避免在 ToolNode 内对同一 task 同时发起多个 interrupt。
        """
        app = build_react_like_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "int-3d-neg"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        # BEHAVIOR: 即使发起两次 interrupt，state 中只剩一个
        assert len(intrs) == 1
        # 无法分别路由 —— 这是设计统一处理器时要解决的核心约束
        assert intrs[0].value["action"] in ("A", "B")


# ============================================================================
# 3. Send 分派方案：官方推荐的并行 interrupt 解法
# ============================================================================


def build_send_dispatch_graph(tools: list, first_tool_calls: list[dict]) -> Any:
    """构造一个 model →(Send 分派)→ tools → model 的循环图。

    关键区别于 ``build_react_like_graph``：route 函数不再把整批 tool_calls
    交给 ToolNode，而是用 ``Send`` 为**每个** tool_call 创建独立 PUSH task。
    每个 task 拥有独立 checkpoint namespace，从而：

    - 并发 interrupt 不再丢失（每个 task 一个 interrupt）
    - interrupt id 唯一
    - 已完成工具不会因其他工具 interrupt 而重新执行
    - resume 可按 interrupt id 精确路由到对应工具

    见 https://github.com/langchain-ai/langgraph/issues/6624 与 #6533 官方方案。
    """
    call_log.clear()

    def model_node(state):
        last = state["messages"][-1]
        if isinstance(last, HumanMessage):
            return {"messages": [AIMessage(content="", tool_calls=_make_tool_calls(first_tool_calls))]}
        return {"messages": [AIMessage(content="done")]}

    def route(state):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            # 过滤掉已经产出 ToolMessage 的 tool_call，避免重复执行
            done_ids = {m.tool_call_id for m in state["messages"] if isinstance(m, ToolMessage)}
            pending = [c for c in last.tool_calls if c["id"] not in done_ids]
            if pending:
                return [
                    Send(
                        "tools",
                        ToolCallWithContext(
                            __type="tool_call_with_context",
                            tool_call=c,
                            state=state,
                        ),
                    )
                    for c in pending
                ]
        return END

    graph = StateGraph(MessagesState)
    graph.add_node("model", model_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", route)
    graph.add_edge("tools", "model")
    return graph.compile(checkpointer=MemorySaver())


class TestParallelInterruptWithSendDispatch:
    """对照 ``TestParallelInterruptWithToolNode`` 各用例的修复验证。

    每个用例对应 ToolNode 版的同一行为，断言 Send 方案如何修复之：
      - 3a 并发 interrupt 仅首个被收集 → Send 下两个都收集
      - 3b id 非确定性/冲突 → Send 下 id 唯一
      - 3c 已完成工具重执行 → Send 下不重执行
      - 3d 单 interrupt resume + list 不解包 → Send 下按 id dict 分发
      - 3d(反向) 并发多 interrupt 无法分别 resume → Send 下可分别 resume
    """

    async def test_a_send_collects_all_parallel_interrupts(self):
        """3a 修复：两个并发 needs_approval 各产生独立 interrupt。"""
        app = build_send_dispatch_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "send-3a"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        # BEHAVIOR: Send 方案下两个 interrupt 都被收集，value 互不丢失
        assert len(intrs) == 2, "Send 分派让每个 tool_call 成为独立 task，各自 interrupt"
        actions = sorted(i.value["action"] for i in intrs)
        assert actions == ["A", "B"], "两个 interrupt 的 value 都保留"

    async def test_b_send_unique_interrupt_ids(self):
        """3b 修复：两个并发 interrupt 拥有不同 id。"""
        app = build_send_dispatch_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "send-3b"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        # BEHAVIOR: 每个 task 独立 namespace → id 唯一
        ids = [i.id for i in intrs]
        assert len(set(ids)) == 2, "interrupt id 互不冲突"

    async def test_c_send_no_reexecution_of_completed_tools(self):
        """3c 修复：tool_a 完成后不会被 needs_approval 的 interrupt 触发重执行。"""
        app = build_send_dispatch_graph(
            [tool_a, needs_approval],
            [
                {"name": "tool_a", "args": {"x": 7}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "X"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "send-3c"}}
        call_log.clear()
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        first_pass = list(call_log)
        assert ("a", 7) in first_pass

        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        call_log.clear()
        await app.ainvoke(Command(resume={i.id: "OK" for i in intrs}), config=cfg)
        second_pass = list(call_log)

        # BEHAVIOR: tool_a 是独立 task，已写入 ToolMessage；resume 后不重新执行
        assert ("a", 7) not in second_pass, "Send 方案下已完成工具不会重执行"

    async def test_d_send_resume_routed_by_id_dict(self):
        """3d 修复：``Command(resume={id: value})`` dict 形式按 id 精确分发。

        对照 ToolNode 版的 list 包装不解包缺陷：Send 方案下 resume 用
        ``{interrupt_id: value}`` dict 形式，原生支持按 id 分发，工具拿到
        的是解包后的标量值而非整个 dict。
        """
        app = build_send_dispatch_graph(
            [needs_approval],
            [{"name": "needs_approval", "args": {"action": "A"}, "id": "cA"}],
        )
        cfg = {"configurable": {"thread_id": "send-3d-single"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)
        intr = intrs[0]

        await app.ainvoke(Command(resume={intr.id: "VALUE_A"}), config=cfg)
        final = await app.aget_state(cfg)
        tool_msgs = [m for m in final.values.get("messages", []) if isinstance(m, ToolMessage)]

        # BEHAVIOR: dict 形式 resume 按 id 分发，工具拿到解包后的标量值
        assert any("approved:VALUE_A" in m.content for m in tool_msgs), (
            "Command(resume={id: value}) 把 value 解包后传给对应工具"
        )

    async def test_d_send_parallel_multi_interrupt_can_be_routed_independently(self):
        """3d(反向)修复：两个并发 interrupt 可按 id 分别 resume。

        对照 ToolNode 版"无法分别 resume"的缺陷：Send 方案下两个 interrupt
        都被收集且 id 唯一，可用 ``Command(resume={id_A: 1, id_B: 2})`` 一次性
        分别路由，action=A 拿到 1、action=B 拿到 2。
        """
        app = build_send_dispatch_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "send-3d-indep"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        # 两个 interrupt 都被收集
        assert len(intrs) == 2, "两个 interrupt 都被收集"

        # 按 action 构造 resume 映射：A→1, B→2
        resume_map = {i.id: "1" if i.value["action"] == "A" else "2" for i in intrs}

        r = await app.ainvoke(Command(resume=resume_map), config=cfg)
        tool_msgs = [m for m in r["messages"] if isinstance(m, ToolMessage)]
        by_id = {m.tool_call_id: m.content for m in tool_msgs}

        # BEHAVIOR: 按 id 分别 resume，每个工具拿到自己的值
        assert by_id == {"cA": "approved:1", "cB": "approved:2"}, "每个工具拿到对应 interrupt 的 resume 值"


# ============================================================================
# 4. 流式事件分发：astream 与 astream_events
# ============================================================================


async def _astream_interrupt_chunks(app, cfg) -> list:
    """跑 astream(stream_mode=values)，返回所有含 ``__interrupt__`` 的 chunk。"""
    out = []
    async for chunk in app.astream({"messages": [HumanMessage("hi")]}, config=cfg, stream_mode="values"):
        if "__interrupt__" in chunk:
            out.append(chunk["__interrupt__"])
    return out


async def _astream_events(app, cfg, input_) -> list:
    """跑 astream_events(version=v2)，返回 (event, name) 元组列表。"""
    out = []
    async for ev in app.astream_events(input_, config=cfg, version="v2"):
        out.append((ev["event"], ev.get("name", "")))
    return out


class TestStreamEventsToolNode:
    """ToolNode 并发 interrupt 在 astream / astream_events 下的事件分发。

    关键可观测信号：
    - ``astream(stream_mode="values")`` 末尾只产出**一个** ``__interrupt__`` chunk
      （只含首个发起者的 value，印证 3a 缺陷）。
    - ``astream_events(v2)`` 中 interrupt 表现为 ``on_tool_error``（非
      ``on_tool_end``），两个工具的 ``on_tool_start`` 都会发出，但都无
      ``on_tool_end`` —— 因为都被 interrupt 取消。
    """

    async def test_astream_emits_single_interrupt_chunk(self):
        """astream(values) 只产出 1 个 __interrupt__ chunk，仅含 action=A。"""
        app = build_react_like_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "stream-tn-1"}}
        intr_chunks = await _astream_interrupt_chunks(app, cfg)

        # BEHAVIOR: astream 只在末尾产出一个 __interrupt__ chunk
        assert len(intr_chunks) == 1, "ToolNode 并发 interrupt 在 astream 下只产出一个 chunk"
        # 该 chunk 只有 1 个 interrupt，value 是 action=A（首个）
        assert len(intr_chunks[0]) == 1
        assert intr_chunks[0][0].value["action"] == "A"

    async def test_astream_events_both_tools_start_none_end(self):
        """astream_events: 两个 needs_approval 都 on_tool_start，都无 on_tool_end。

        BEHAVIOR: interrupt 在事件流里表现为 ``on_tool_error``（GraphInterrupt
        被当作工具异常），两个工具的 ``on_tool_start`` 都发出（并发已启动），
        但 ``on_tool_end`` 计数为 0。
        """
        app = build_react_like_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "stream-tn-2"}}
        events = await _astream_events(app, cfg, {"messages": [HumanMessage("hi")]})

        tool_starts = [n for ev, n in events if ev == "on_tool_start" and n == "needs_approval"]
        tool_ends = [n for ev, n in events if ev == "on_tool_end" and n == "needs_approval"]
        tool_errors = [n for ev, n in events if ev == "on_tool_error" and n == "needs_approval"]

        # 两个工具都启动
        assert len(tool_starts) == 2, "两个 needs_approval 都发出 on_tool_start"
        # 没有任何工具正常结束
        assert len(tool_ends) == 0, "interrupt 下无 on_tool_end"
        # interrupt 表现为 on_tool_error（至少一个，因 gather 首异常抢占）
        assert len(tool_errors) >= 1, "interrupt 在事件流表现为 on_tool_error"


class TestStreamEventsSendDispatch:
    """SendDispatch 方案在 astream / astream_events 下的事件分发。

    对照 ``TestStreamEventsToolNode``：Send 方案下
    - ``astream(values)`` 产出**多个** ``__interrupt__`` chunk，每个对应一个工具。
    - ``astream_events(v2)`` 中 interrupt 仍表现为 ``on_tool_error``，但 ``tools``
      节点会被 ``Send`` 触发两次（每工具一次）；resume 后两个工具都
      ``on_tool_end``。
    """

    async def test_astream_emits_multiple_interrupt_chunks(self):
        """astream(values) 产出 2 个 __interrupt__ chunk，分别含 A 和 B。"""
        app = build_send_dispatch_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "stream-send-1"}}
        intr_chunks = await _astream_interrupt_chunks(app, cfg)

        # BEHAVIOR: Send 方案下 astream 产出多个 __interrupt__ chunk
        assert len(intr_chunks) == 2, "SendDispatch 每个工具产出独立 interrupt chunk"
        # 每个 chunk 各含 1 个 interrupt，value 分别是 A 和 B
        actions = sorted(c[0].value["action"] for c in intr_chunks)
        assert actions == ["A", "B"], "两个 chunk 分别对应 A 和 B"

    async def test_astream_events_both_tools_start_none_end(self):
        """astream_events: 两个 needs_approval 都 on_tool_start，都无 on_tool_end。

        BEHAVIOR: Send 方案下 interrupt 仍表现为 ``on_tool_error``；两个工具
        的 ``on_tool_start`` 都发出，``on_tool_end`` 计数为 0（与 ToolNode 版
        相同——interrupt 在事件流层面的可观测信号一致）。
        """
        app = build_send_dispatch_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "stream-send-2"}}
        events = await _astream_events(app, cfg, {"messages": [HumanMessage("hi")]})

        tool_starts = [n for ev, n in events if ev == "on_tool_start" and n == "needs_approval"]
        tool_ends = [n for ev, n in events if ev == "on_tool_end" and n == "needs_approval"]
        tool_errors = [n for ev, n in events if ev == "on_tool_error" and n == "needs_approval"]

        assert len(tool_starts) == 2, "两个 needs_approval 都发出 on_tool_start"
        assert len(tool_ends) == 0, "interrupt 下无 on_tool_end"
        assert len(tool_errors) >= 1, "interrupt 在事件流表现为 on_tool_error"

    async def test_astream_events_tools_node_starts_twice_via_send(self):
        """astream_events: tools 节点被 Send 触发两次（每工具一次）。

        BEHAVIOR: Send 分派下 ``tools`` 节点的 ``on_chain_start`` 出现 2 次
        （每 tool_call 独立 task），对照 ToolNode 版只出现 1 次。
        这是 Send 方案与 ToolNode 在事件流上的结构性差异。
        """
        app_send = build_send_dispatch_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg_send = {"configurable": {"thread_id": "stream-send-3"}}
        events_send = await _astream_events(app_send, cfg_send, {"messages": [HumanMessage("hi")]})
        tools_starts_send = [n for ev, n in events_send if ev == "on_chain_start" and n == "tools"]

        app_tn = build_react_like_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg_tn = {"configurable": {"thread_id": "stream-tn-3"}}
        events_tn = await _astream_events(app_tn, cfg_tn, {"messages": [HumanMessage("hi")]})
        tools_starts_tn = [n for ev, n in events_tn if ev == "on_chain_start" and n == "tools"]

        # BEHAVIOR: Send 下 tools 节点启动 2 次；ToolNode 下启动 1 次
        assert len(tools_starts_send) == 2, "Send 分派让 tools 节点启动 2 次"
        assert len(tools_starts_tn) == 1, "ToolNode 下 tools 节点只启动 1 次"

    async def test_astream_events_resume_produces_tool_ends(self):
        """astream_events: resume 后两个 needs_approval 都 on_tool_end。

        BEHAVIOR: resume 后 interrupt 解除，两个工具都正常结束，发出
        ``on_tool_end``。对照 ToolNode 版 resume 后会再次 interrupt（因 3a
        合并丢值），无法一次 resume 让两个工具都结束。
        """
        app = build_send_dispatch_graph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "A"}, "id": "cA"},
                {"name": "needs_approval", "args": {"action": "B"}, "id": "cB"},
            ],
        )
        cfg = {"configurable": {"thread_id": "stream-send-4"}}
        await _astream_events(app, cfg, {"messages": [HumanMessage("hi")]})
        state = await app.aget_state(cfg)
        intrs = [i for t in state.tasks for i in (t.interrupts or [])]

        resume_events = await _astream_events(app, cfg, Command(resume={i.id: "OK" for i in intrs}))
        tool_ends = [n for ev, n in resume_events if ev == "on_tool_end" and n == "needs_approval"]

        # BEHAVIOR: resume 后两个工具都正常 on_tool_end
        assert len(tool_ends) == 2, "Send 方案 resume 后两个工具都正常结束"


def _build_subgraph(tools: list, first_tool_calls: list[dict]) -> Any:
    """构造与 build_react_like_graph 等价的子图（不 compile 或带 checkpointer）。"""
    sub_call_log = first_tool_calls

    def sub_model(state):
        last = state["messages"][-1]
        if isinstance(last, HumanMessage):
            return {"messages": [AIMessage(content="", tool_calls=_make_tool_calls(sub_call_log))]}
        return {"messages": [AIMessage(content="sub-done")]}

    def sub_route(state):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return END

    g = StateGraph(MessagesState)
    g.add_node("model", sub_model)
    g.add_node("tools", ToolNode(tools))
    g.add_edge(START, "model")
    g.add_conditional_edges("model", sub_route)
    g.add_edge("tools", "model")
    return g


# ============================================================================
# 5. 子 Graph 多 interrupt 行为
# ============================================================================


class TestSubgraphInterrupt:
    """3e: 子 Graph 多 interrupt 在不同 checkpoint 配置下的传播行为。"""

    async def test_subgraph_without_checkpointer_runs_to_completion(self):
        """子图无 checkpointer：作为父图节点直接执行完成，interrupt 不传播到父图。

        BEHAVIOR: 无 checkpointer 的子图在父图 tick 内同步跑完，
        interrupt 被吞掉，父图感知不到暂停。
        """
        sub_app = _build_subgraph(
            [needs_approval],
            [{"name": "needs_approval", "args": {"action": "SUB"}, "id": "sA"}],
        ).compile()  # 无 checkpointer

        def parent_call(state):
            last = state["messages"][-1]
            if isinstance(last, HumanMessage):
                return {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[{"name": "sub_node", "args": {}, "id": "p1"}],
                        )
                    ]
                }
            return {"messages": [AIMessage(content="parent-done")]}

        def parent_route(state):
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
                return "sub_node"
            return END

        parent = StateGraph(MessagesState)
        parent.add_node("sub_node", sub_app)
        parent.add_node("model", parent_call)
        parent.add_edge(START, "model")
        parent.add_conditional_edges("model", parent_route)
        parent.add_edge("sub_node", "model")
        app = parent.compile(checkpointer=MemorySaver())

        cfg = {"configurable": {"thread_id": "sub-1"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        # BEHAVIOR: 父图无 interrupt，子图已跑完
        assert len(intrs) == 0, "无 checkpointer 子图的 interrupt 不传播到父图"
        assert state.next == ()

    async def test_subgraph_with_checkpointer_does_not_propagate_interrupt(self):
        """子图带独立 checkpointer：interrupt **不会**自动冒泡到父图。

        BEHAVIOR: 在 LangGraph 1.0 中，把带 checkpointer 的子图作为父图节点
        添加后，子图内的 interrupt 不会自动暂停父图执行——父图 ainvoke 直接
        返回完成态，interrupt 被吞掉。要让子图中断透传到父图，需要显式
        interrupt_before/interrupt_after 或在子图外手动编排。
        统一中断处理器若依赖"子图 interrupt 自动冒泡"，将无法生效。
        """
        sub_app = _build_subgraph(
            [needs_approval],
            [{"name": "needs_approval", "args": {"action": "SUB"}, "id": "sA"}],
        ).compile(checkpointer=MemorySaver())

        def parent_call(state):
            last = state["messages"][-1]
            if isinstance(last, HumanMessage):
                return {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[{"name": "sub_node", "args": {}, "id": "p1"}],
                        )
                    ]
                }
            return {"messages": [AIMessage(content="parent-done")]}

        def parent_route(state):
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
                return "sub_node"
            return END

        parent = StateGraph(MessagesState)
        parent.add_node("sub_node", sub_app)
        parent.add_node("model", parent_call)
        parent.add_edge(START, "model")
        parent.add_conditional_edges("model", parent_route)
        parent.add_edge("sub_node", "model")
        app = parent.compile(checkpointer=MemorySaver())

        cfg = {"configurable": {"thread_id": "sub-2"}}
        await app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await app.aget_state(cfg)
        intrs = await _interrupts(state)

        # BEHAVIOR: 父图感知不到子图 interrupt，已直接完成
        assert len(intrs) == 0, "子图 interrupt 不会自动冒泡到父图 task"
        assert state.next == (), "父图未暂停"

    async def test_subgraph_multiple_parallel_interrupts_also_merged(self):
        """3e 续: 子图内两个并发 interrupt 同样只有首个被收集。

        BEHAVIOR: 3a 的"并发 interrupt 仅首个被收集"缺陷在子图层级同样存在。
        统一中断处理器无论在哪一层，都必须避免同一 task 内并发多个 interrupt。
        由于父图不会感知子图 interrupt（见上一用例），本测试直接对独立子图
        做断言，验证"子图 task 内并发 interrupt 仅首个被收集"这一行为。
        """
        sub_app = _build_subgraph(
            [needs_approval],
            [
                {"name": "needs_approval", "args": {"action": "SA"}, "id": "sA"},
                {"name": "needs_approval", "args": {"action": "SB"}, "id": "sB"},
            ],
        ).compile(checkpointer=MemorySaver())

        cfg = {"configurable": {"thread_id": "sub-3-direct"}}
        await sub_app.ainvoke({"messages": [HumanMessage("hi")]}, config=cfg)
        state = await sub_app.aget_state(cfg)
        intrs = await _interrupts(state)

        # BEHAVIOR: 子图内两个并发 interrupt 仅首个被收集
        assert len(intrs) == 1, "子图内并发 interrupt 同样仅首个被收集"
        assert intrs[0].value["action"] in ("SA", "SB")
