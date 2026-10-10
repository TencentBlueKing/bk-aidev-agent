# -*- coding: utf-8 -*-
"""任务工具 LangGraph 状态集成测试。

验证任务工具通过 LangGraph ToolNode 正确更新状态，
构建简单图：START -> test_node -> ToolNode -> END
"""

import json
from typing import Annotated, List, Optional

from aidev_agent.core.tools.task import TeamTaskRecord, TeamTaskStatus, get_task_tools, merge_task_list
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import add_messages
from langgraph.graph.state import StateGraph
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict


class GraphState(TypedDict):
    """测试用最小状态模式。"""

    messages: Annotated[List[BaseMessage], add_messages]
    task_list: Annotated[Optional[List[TeamTaskRecord]], merge_task_list]


def _build_test_graph(tool_calls: list[dict]):
    """构建最小图以调用任务工具并检查状态。

    Args:
        tool_calls: 嵌入到 AIMessage 中的 tool_call 字典列表
    """
    tools = get_task_tools()
    tool_node = ToolNode(tools=tools)

    def test_node(state: GraphState):
        """生成包含 tool_calls 的 AIMessage 以触发 ToolNode。"""
        return {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=tool_calls,
                )
            ]
        }

    graph = StateGraph(state_schema=GraphState)
    graph.add_node("test_node", test_node)
    graph.add_node("tools", tool_node)
    graph.add_edge(START, "test_node")
    graph.add_edge("test_node", "tools")
    graph.add_edge("tools", END)

    return graph.compile(checkpointer=MemorySaver())


def test_task_create_updates_state():
    """测试 TaskCreate 更新图状态中的 task_list。"""
    tool_calls = [
        {
            "name": "TaskCreate",
            "args": {"subject": "Test task", "description": "A test task"},
            "id": "call_1",
            "type": "tool_call",
        }
    ]

    graph = _build_test_graph(tool_calls)
    config = {"configurable": {"thread_id": "test-1"}}

    result = graph.invoke({"messages": [], "task_list": None}, config=config)

    # 检查 task_list 已更新
    assert result.get("task_list") is not None, "task_list 应在状态中被更新"
    assert len(result["task_list"]) == 1, "task_list 应包含一个任务"
    assert result["task_list"][0].subject == "Test task"
    assert result["task_list"][0].status == TeamTaskStatus.PENDING


def test_task_create_then_update_state():
    """测试 TaskCreate 后接 TaskUpdate 均正确更新状态。"""
    # 步骤 1：创建任务
    create_calls = [
        {
            "name": "TaskCreate",
            "args": {"subject": "Task to update", "description": "Will be updated"},
            "id": "call_create",
            "type": "tool_call",
        }
    ]

    create_graph = _build_test_graph(create_calls)
    config = {"configurable": {"thread_id": "test-2a"}}
    create_result = create_graph.invoke({"messages": [], "task_list": None}, config=config)

    assert create_result.get("task_list") is not None
    task_id = create_result["task_list"][0].task_id

    # 步骤 2：更新任务
    update_calls = [
        {
            "name": "TaskUpdate",
            "args": {"task_id": task_id, "status": "in_progress"},
            "id": "call_update",
            "type": "tool_call",
        }
    ]

    update_graph = _build_test_graph(update_calls)
    config2 = {"configurable": {"thread_id": "test-2b"}}
    update_result = update_graph.invoke(
        {"messages": [], "task_list": create_result["task_list"]},
        config=config2,
    )

    assert update_result.get("task_list") is not None
    updated_task = next(t for t in update_result["task_list"] if t.task_id == task_id)
    assert updated_task.status == TeamTaskStatus.IN_PROGRESS


def test_task_list_preserves_state():
    """测试 TaskList 读取状态而不修改 task_list。"""
    # 预填充一个任务
    task = TeamTaskRecord(
        task_id="1",
        subject="Existing task",
        description="Already exists",
        status=TeamTaskStatus.PENDING,
    )

    list_calls = [
        {
            "name": "TaskList",
            "args": {},
            "id": "call_list",
            "type": "tool_call",
        }
    ]

    graph = _build_test_graph(list_calls)
    config = {"configurable": {"thread_id": "test-3"}}
    result = graph.invoke({"messages": [], "task_list": [task]}, config=config)

    # task_list 应保持不变（TaskList 是只读操作）
    assert result.get("task_list") is not None
    assert len(result["task_list"]) == 1
    assert result["task_list"][0].task_id == "1"


def test_task_get_preserves_state():
    """测试 TaskGet 读取状态而不修改 task_list。"""
    task = TeamTaskRecord(
        task_id="1",
        subject="Existing task",
        description="Already exists",
        status=TeamTaskStatus.PENDING,
    )

    get_calls = [
        {
            "name": "TaskGet",
            "args": {"task_id": "1"},
            "id": "call_get",
            "type": "tool_call",
        }
    ]

    graph = _build_test_graph(get_calls)
    config = {"configurable": {"thread_id": "test-4"}}
    result = graph.invoke({"messages": [], "task_list": [task]}, config=config)

    # task_list 应保持不变
    assert result.get("task_list") is not None
    assert len(result["task_list"]) == 1

    # 检查 ToolMessage 包含任务详情
    tool_messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    content = json.loads(tool_messages[0].content)
    assert content["task_id"] == "1"
    assert content["subject"] == "Existing task"


def test_multiple_task_creates_accumulate():
    """测试多次 TaskCreate 调用会累积任务到状态中。"""
    # 创建第一个任务
    call1 = [
        {
            "name": "TaskCreate",
            "args": {"subject": "First task", "description": "desc 1"},
            "id": "call_1",
            "type": "tool_call",
        }
    ]

    graph1 = _build_test_graph(call1)
    config1 = {"configurable": {"thread_id": "test-5a"}}
    result1 = graph1.invoke({"messages": [], "task_list": None}, config=config1)

    assert len(result1["task_list"]) == 1

    # 使用已有 task_list 创建第二个任务
    call2 = [
        {
            "name": "TaskCreate",
            "args": {"subject": "Second task", "description": "desc 2"},
            "id": "call_2",
            "type": "tool_call",
        }
    ]

    graph2 = _build_test_graph(call2)
    config2 = {"configurable": {"thread_id": "test-5b"}}
    result2 = graph2.invoke({"messages": [], "task_list": result1["task_list"]}, config=config2)

    assert len(result2["task_list"]) == 2
    subjects = {t.subject for t in result2["task_list"]}
    assert subjects == {"First task", "Second task"}


def test_task_update_with_dependencies():
    """测试 TaskUpdate 正确设置依赖关系。"""
    task1 = TeamTaskRecord(task_id="1", subject="Task 1", description="d1", status=TeamTaskStatus.PENDING)
    task2 = TeamTaskRecord(task_id="2", subject="Task 2", description="d2", status=TeamTaskStatus.PENDING)

    update_calls = [
        {
            "name": "TaskUpdate",
            "args": {"task_id": "2", "add_blocked_by": ["1"]},
            "id": "call_dep",
            "type": "tool_call",
        }
    ]

    graph = _build_test_graph(update_calls)
    config = {"configurable": {"thread_id": "test-6"}}
    result = graph.invoke({"messages": [], "task_list": [task1, task2]}, config=config)

    assert result.get("task_list") is not None
    t1 = next(t for t in result["task_list"] if t.task_id == "1")
    t2 = next(t for t in result["task_list"] if t.task_id == "2")
    assert "1" in (t2.blocked_by or [])
    assert "2" in (t1.blocks or [])


def test_parallel_task_creates_merge():
    """同一步的多个 TaskCreate 合并进 task_list。"""
    tool_calls = [
        {"name": "TaskCreate", "args": {"subject": "Task A", "description": "a"}, "id": "call_a", "type": "tool_call"},
        {"name": "TaskCreate", "args": {"subject": "Task B", "description": "b"}, "id": "call_b", "type": "tool_call"},
    ]
    graph = _build_test_graph(tool_calls)
    result = graph.invoke(
        {"messages": [], "task_list": None},
        config={"configurable": {"thread_id": "test-parallel-create"}},
    )
    assert {task.subject for task in result["task_list"]} == {"Task A", "Task B"}
    assert len({task.task_id for task in result["task_list"]}) == 2
