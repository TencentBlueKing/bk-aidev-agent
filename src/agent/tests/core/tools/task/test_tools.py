# -*- coding: utf-8 -*-
"""任务工具单元测试。

直接通过传入 ToolRuntime mock 对象测试工具函数。
LangGraph 状态集成测试见 test_integration.py。
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from aidev_agent.core.tools.task import TeamTaskRecord, TeamTaskStatus, get_task_tools, merge_task_list
from langgraph.types import Command


@dataclass
class MockToolRuntime:
    """单元测试用 ToolRuntime mock。"""

    state: Dict[str, Any]
    tool_call_id: str = "test_call_id"
    config: Any = None
    context: Any = None
    store: Any = None
    stream_writer: Any = None


def make_runtime(task_list=None):
    """创建包含给定 task_list 状态的 mock runtime。"""
    return MockToolRuntime(state={"task_list": task_list or []})


def _extract_task_list(result: Command) -> List[TeamTaskRecord]:
    """从 Command update 中提取 task_list。"""
    assert isinstance(result, Command), f"期望 Command，实际为 {type(result)}"
    update = result.update
    assert isinstance(update, dict), f"期望 dict update，实际为 {type(update)}"
    return update.get("task_list", [])


def _extract_content(result: Command) -> str:
    """从 Command update 中提取 ToolMessage 内容。"""
    assert isinstance(result, Command)
    messages = result.update.get("messages", [])
    assert len(messages) > 0, "Command 应包含至少一条 ToolMessage"
    return messages[0].content


def test_task_create_creates_and_returns_task_id():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")

    runtime = make_runtime()
    result = create_tool.func(subject="Fix bug", description="Fix the authentication bug", runtime=runtime)

    task_list = _extract_task_list(result)
    assert len(task_list) == 1
    assert task_list[0].subject == "Fix bug"
    assert task_list[0].status == TeamTaskStatus.PENDING

    content = _extract_content(result)
    assert "created" in content.lower()
    assert "Fix bug" in content


def test_task_create_with_active_form_and_owner():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")

    runtime = make_runtime()
    result = create_tool.func(
        subject="Run tests",
        description="Run the test suite",
        active_form="Running tests",
        owner="alice",
        runtime=runtime,
    )

    task_list = _extract_task_list(result)
    assert task_list[0].active_form == "Running tests"
    assert task_list[0].owner == "alice"


def test_task_create_increments_id():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")

    runtime = make_runtime()
    r1 = create_tool.func(subject="Task 1", description="desc 1", runtime=runtime)
    task_list_1 = _extract_task_list(r1)

    runtime2 = make_runtime(task_list=task_list_1)
    r2 = create_tool.func(subject="Task 2", description="desc 2", runtime=runtime2)
    task_list_2 = _extract_task_list(r2)

    assert task_list_1[0].task_id.split("~", 1)[0] == "1"
    assert task_list_2[1].task_id.split("~", 1)[0] == "2"
    assert task_list_1[0].task_id != task_list_2[1].task_id


def test_task_get_returns_full_details():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    get_tool = next(t for t in tools if t.name == "TaskGet")

    runtime = make_runtime()
    r = create_tool.func(
        subject="My task",
        description="Detailed description",
        active_form="Working on task",
        owner="bob",
        metadata={"priority": "high"},
        runtime=runtime,
    )
    task_list = _extract_task_list(r)

    runtime2 = make_runtime(task_list=task_list)
    result = get_tool.func(task_id=task_list[0].task_id, runtime=runtime2)

    content = json.loads(_extract_content(result))
    assert content["task_id"] == task_list[0].task_id
    assert content["subject"] == "My task"
    assert content["description"] == "Detailed description"
    assert content["status"] == "pending"
    assert content["owner"] == "bob"
    assert content["metadata"] == {"priority": "high"}


def test_task_get_nonexistent_returns_error():
    tools = get_task_tools()
    get_tool = next(t for t in tools if t.name == "TaskGet")

    runtime = make_runtime()
    result = get_tool.func(task_id="999", runtime=runtime)

    content = json.loads(_extract_content(result))
    assert "error" in content
    assert "not found" in content["error"]


def test_task_update_changes_status():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    update_tool = next(t for t in tools if t.name == "TaskUpdate")

    runtime = make_runtime()
    r = create_tool.func(subject="My task", description="do something", runtime=runtime)
    task_list = _extract_task_list(r)
    task_id = task_list[0].task_id

    runtime2 = make_runtime(task_list=task_list)
    update_result = update_tool.func(task_id=task_id, status="in_progress", owner="alice", runtime=runtime2)

    updated_list = _extract_task_list(update_result)
    task = next(t for t in updated_list if t.task_id == task_id)
    assert task.status == TeamTaskStatus.IN_PROGRESS
    assert task.owner == "alice"
    assert task.updated_at_ms is not None


def test_task_update_deleted_status():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    update_tool = next(t for t in tools if t.name == "TaskUpdate")
    list_tool = next(t for t in tools if t.name == "TaskList")

    runtime = make_runtime()
    r = create_tool.func(subject="To delete", description="will be deleted", runtime=runtime)
    task_list = _extract_task_list(r)
    task_id = task_list[0].task_id

    runtime2 = make_runtime(task_list=task_list)
    update_result = update_tool.func(task_id=task_id, status="deleted", runtime=runtime2)
    updated_list = _extract_task_list(update_result)

    # 已删除的任务不应出现在 TaskList 中
    runtime3 = make_runtime(task_list=updated_list)
    list_result = list_tool.func(runtime=runtime3)
    content = json.loads(_extract_content(list_result))
    assert len(content["tasks"]) == 0


def test_task_update_invalid_status_returns_error():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    update_tool = next(t for t in tools if t.name == "TaskUpdate")

    runtime = make_runtime()
    r = create_tool.func(subject="My task", description="do something", runtime=runtime)
    task_list = _extract_task_list(r)
    task_id = task_list[0].task_id

    runtime2 = make_runtime(task_list=task_list)
    result = update_tool.func(task_id=task_id, status="invalid_status", runtime=runtime2)

    content = json.loads(_extract_content(result))
    assert "error" in content
    assert "Invalid status" in content["error"]


def test_task_update_nonexistent_returns_error():
    tools = get_task_tools()
    update_tool = next(t for t in tools if t.name == "TaskUpdate")

    runtime = make_runtime()
    result = update_tool.func(task_id="nonexistent", status="completed", runtime=runtime)

    content = json.loads(_extract_content(result))
    assert "error" in content
    assert "not found" in content["error"]


def test_task_update_metadata_merge():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    update_tool = next(t for t in tools if t.name == "TaskUpdate")

    runtime = make_runtime()
    r = create_tool.func(
        subject="Task with metadata",
        description="desc",
        metadata={"key1": "value1", "key2": "value2"},
        runtime=runtime,
    )
    task_list = _extract_task_list(r)
    task_id = task_list[0].task_id

    runtime2 = make_runtime(task_list=task_list)
    update_result = update_tool.func(
        task_id=task_id,
        metadata={"key2": None, "key3": "value3"},
        runtime=runtime2,
    )

    updated_list = _extract_task_list(update_result)
    task = next(t for t in updated_list if t.task_id == task_id)
    assert task.metadata == {"key1": "value1", "key3": "value3"}


def test_task_update_dependencies():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    update_tool = next(t for t in tools if t.name == "TaskUpdate")

    runtime = make_runtime()
    r1 = create_tool.func(subject="Task 1", description="first", runtime=runtime)
    task_list = _extract_task_list(r1)
    task_id_1 = task_list[0].task_id
    runtime2 = make_runtime(task_list=task_list)
    r2 = create_tool.func(subject="Task 2", description="second", runtime=runtime2)
    task_list = _extract_task_list(r2)
    task_id_2 = next(task.task_id for task in task_list if task.task_id != task_id_1)

    # Task 2 被 Task 1 阻塞
    runtime3 = make_runtime(task_list=task_list)
    update_result = update_tool.func(task_id=task_id_2, add_blocked_by=[task_id_1], runtime=runtime3)
    updated_list = _extract_task_list(update_result)

    task1 = next(t for t in updated_list if t.task_id == task_id_1)
    task2 = next(t for t in updated_list if t.task_id == task_id_2)

    assert task_id_1 in task2.blocked_by
    assert task_id_2 in task1.blocks


def test_task_list_returns_all_tasks():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    list_tool = next(t for t in tools if t.name == "TaskList")

    runtime = make_runtime()
    r1 = create_tool.func(subject="Task 1", description="desc 1", runtime=runtime)
    task_list = _extract_task_list(r1)
    runtime2 = make_runtime(task_list=task_list)
    r2 = create_tool.func(subject="Task 2", description="desc 2", runtime=runtime2)
    task_list = _extract_task_list(r2)

    runtime3 = make_runtime(task_list=task_list)
    result = list_tool.func(runtime=runtime3)

    content = json.loads(_extract_content(result))
    tasks = content["tasks"]
    assert len(tasks) == 2
    subjects = {t["subject"] for t in tasks}
    assert subjects == {"Task 1", "Task 2"}


def test_task_list_shows_open_blockers_only():
    tools = get_task_tools()
    create_tool = next(t for t in tools if t.name == "TaskCreate")
    update_tool = next(t for t in tools if t.name == "TaskUpdate")
    list_tool = next(t for t in tools if t.name == "TaskList")

    runtime = make_runtime()
    r1 = create_tool.func(subject="Blocker", description="blocks task 2", runtime=runtime)
    task_list = _extract_task_list(r1)
    blocker_id = task_list[0].task_id
    runtime2 = make_runtime(task_list=task_list)
    r2 = create_tool.func(subject="Blocked", description="blocked by task 1", runtime=runtime2)
    task_list = _extract_task_list(r2)
    blocked_id = next(task.task_id for task in task_list if task.task_id != blocker_id)

    # 设置依赖
    runtime3 = make_runtime(task_list=task_list)
    ur = update_tool.func(task_id=blocked_id, add_blocked_by=[blocker_id], runtime=runtime3)
    task_list = _extract_task_list(ur)

    # 完成阻塞任务前
    runtime4 = make_runtime(task_list=task_list)
    list_result = list_tool.func(runtime=runtime4)
    content = json.loads(_extract_content(list_result))
    task2_info = next(t for t in content["tasks"] if t["id"] == blocked_id)
    assert task2_info["blockedBy"] == [blocker_id]

    # 完成阻塞任务
    runtime5 = make_runtime(task_list=task_list)
    ur2 = update_tool.func(task_id=blocker_id, status="completed", runtime=runtime5)
    task_list = _extract_task_list(ur2)

    # 完成阻塞任务后
    runtime6 = make_runtime(task_list=task_list)
    list_result2 = list_tool.func(runtime=runtime6)
    content2 = json.loads(_extract_content(list_result2))
    task2_info2 = next(t for t in content2["tasks"] if t["id"] == blocked_id)
    assert task2_info2["blockedBy"] is None


def test_get_task_tools_returns_four_tools():
    tools = get_task_tools()
    assert len(tools) == 4
    tool_names = {t.name for t in tools}
    assert tool_names == {"TaskCreate", "TaskGet", "TaskUpdate", "TaskList"}


def test_parallel_creates_get_distinct_ids_and_merge():
    tools = get_task_tools()
    create_tool = next(tool for tool in tools if tool.name == "TaskCreate")
    shared = make_runtime().state
    first = create_tool.func(subject="A", description="a", runtime=MockToolRuntime(state=shared, tool_call_id="call_a"))
    second = create_tool.func(
        subject="B", description="b", runtime=MockToolRuntime(state=shared, tool_call_id="call_b")
    )
    merged = merge_task_list(_extract_task_list(first), _extract_task_list(second))
    assert {task.subject for task in merged} == {"A", "B"}
    assert len({task.task_id for task in merged}) == 2


def test_merge_task_list_keeps_newer_parallel_updates():
    task_a = TeamTaskRecord(task_id="1", subject="A", description="a", created_at_ms=1000)
    task_b = TeamTaskRecord(task_id="2", subject="B", description="b", created_at_ms=1000)
    updated_a = task_a.model_copy(update={"status": TeamTaskStatus.COMPLETED, "updated_at_ms": 2000})
    updated_b = task_b.model_copy(update={"owner": "alice", "updated_at_ms": 2000})
    merged = merge_task_list([task_a, task_b], [updated_a, task_b])
    merged = merge_task_list(merged, [task_a, updated_b])
    assert next(task for task in merged if task.task_id == "1").status == TeamTaskStatus.COMPLETED
    assert next(task for task in merged if task.task_id == "2").owner == "alice"
