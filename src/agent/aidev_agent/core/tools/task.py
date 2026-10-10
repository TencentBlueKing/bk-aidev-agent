# -*- coding: utf-8 -*-
"""使用 LangGraph Command 进行状态更新的任务管理工具。

工具返回 Command 对象来更新 LangGraph 状态中的 task_list 字段。
使用 ToolRuntime 进行状态访问和 tool_call_id 注入。
"""

from __future__ import annotations

import enum
import json
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field


class TeamTaskStatus(str, enum.Enum):
    """任务状态枚举。"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class TeamTaskRecord(BaseModel):
    """独立任务管理的任务记录。"""

    task_id: str = Field(description="稳定的任务 ID")
    subject: str = Field(description="简要任务标题")
    description: Optional[str] = Field(default=None, description="详细任务描述")
    active_form: Optional[str] = Field(default=None, description="在加载动画中显示的进行时形式")
    status: TeamTaskStatus = Field(default=TeamTaskStatus.PENDING)
    owner: Optional[str] = Field(default=None, description="负责此任务的成员")
    blocked_by: Optional[List[str]] = Field(default=None, description="阻塞此任务的任务 ID 列表")
    blocks: Optional[List[str]] = Field(default=None, description="此任务阻塞的任务 ID 列表")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="自定义元数据字典")
    created_at_ms: int = Field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: Optional[int] = Field(default=None)

    def mark_updated(self) -> None:
        self.updated_at_ms = int(time.time() * 1000)


def _coerce_metadata(metadata: Optional[Dict[str, Any] | str]) -> Optional[Dict[str, Any]]:
    """将 metadata 兼容处理为字典，支持模型生成 JSON 字符串的情况。"""
    if metadata is None:
        return None
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
            return parsed if isinstance(parsed, dict) else {"value": metadata}
        except (json.JSONDecodeError, TypeError):
            return {"value": metadata}
    return metadata


def _get_task_list(state: dict | None) -> List[TeamTaskRecord]:
    """从状态中获取任务列表，不存在则返回空列表。"""
    if state is None:
        return []
    return list(state.get("task_list") or [])


def _task_revision(task: TeamTaskRecord) -> int:
    """同一 task_id 冲突时，更新时间优先于创建时间。"""
    return task.updated_at_ms or task.created_at_ms or 0


def _allocate_task_id(tasks: List[TeamTaskRecord], tool_call_id: str) -> str:
    """分配任务 ID。序号按已有任务递增，并带上本次 tool_call_id。

    并行工具读到的是同一步之前的同一份列表，只靠序号会都得到同一个 ID。
    """
    stems = []
    for task in tasks:
        head = task.task_id.split("~", 1)[0]
        if head.isdigit():
            stems.append(int(head))
    base = max(stems, default=0) + 1
    if not tool_call_id:
        return str(base)
    return f"{base}~{tool_call_id}"


def merge_task_list(
    left: Optional[List[TeamTaskRecord]],
    right: Optional[List[TeamTaskRecord]],
) -> List[TeamTaskRecord]:
    """按 task_id 合并两次写入。新 ID 追加；同一 ID 保留修订时间更新的那条。"""
    merged = [] if left is None else list(left)
    index = {task.task_id: position for position, task in enumerate(merged)}
    for task in right or []:
        position = index.get(task.task_id)
        if position is None:
            index[task.task_id] = len(merged)
            merged.append(task)
            continue
        if _task_revision(task) > _task_revision(merged[position]):
            merged[position] = task
    return merged


def _make_update_command(task_list: List[TeamTaskRecord], content: str, tool_call_id: str) -> Command:
    """创建一个 Command 来更新状态中的 task_list 并包含一条 ToolMessage。"""
    return Command(
        update={
            "task_list": task_list,
            "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
        }
    )


def _make_readonly_command(content: str, tool_call_id: str) -> Command:
    """创建一个仅返回 ToolMessage 而不修改状态的 Command。"""
    return Command(
        update={
            "messages": [ToolMessage(content=content, tool_call_id=tool_call_id)],
        }
    )


@tool
def TaskCreate(
    subject: str,
    description: str,
    active_form: Optional[str] = None,
    owner: Optional[str] = None,
    metadata: Optional[Dict[str, Any] | str] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """在任务列表中创建一个新任务。返回新任务的 task_id。

    Args:
        subject: 简要任务标题（祈使形式，如"修复认证漏洞"）
        description: 详细任务描述，包含上下文和验收标准
        active_form: 在加载动画中显示的进行时形式（如"正在修复认证漏洞"）
        owner: 任务负责人（智能体名称）
        metadata: 附加到任务的自定义元数据
    """
    state = runtime.state if runtime else None
    tool_call_id = runtime.tool_call_id if runtime else ""

    metadata = _coerce_metadata(metadata)

    tasks = _get_task_list(state)
    next_id = _allocate_task_id(tasks, tool_call_id)

    task = TeamTaskRecord(
        task_id=next_id,
        subject=subject,
        description=description,
        active_form=active_form,
        owner=owner,
        metadata=metadata,
        status=TeamTaskStatus.PENDING,
        created_at_ms=int(time.time() * 1000),
    )
    tasks.append(task)
    content = f"Task #{next_id} created successfully: {subject}"
    return _make_update_command(task_list=tasks, content=content, tool_call_id=tool_call_id)


@tool
def TaskGet(
    task_id: str,
    runtime: ToolRuntime = None,
) -> Command:
    """根据 task_id 检索单个任务的完整详情，包括描述、依赖关系和元数据。

    Args:
        task_id: 要检索的任务 ID
    """
    state = runtime.state if runtime else None
    tool_call_id = runtime.tool_call_id if runtime else ""

    tasks = _get_task_list(state)
    for task in tasks:
        if task.task_id == task_id:
            # 仅显示未完成的阻塞任务（排除已完成和已删除的）
            open_blocked_by = []
            if task.blocked_by:
                for bid in task.blocked_by:
                    blocker = next((t for t in tasks if t.task_id == bid), None)
                    if blocker and blocker.status not in (TeamTaskStatus.COMPLETED, TeamTaskStatus.DELETED):
                        open_blocked_by.append(bid)

            result = {
                "task_id": task.task_id,
                "subject": task.subject,
                "description": task.description,
                "status": task.status.value,
                "owner": task.owner,
                "active_form": task.active_form,
                "blocked_by": open_blocked_by if open_blocked_by else None,
                "blocks": task.blocks,
                "metadata": task.metadata,
                "created_at_ms": task.created_at_ms,
                "updated_at_ms": task.updated_at_ms,
            }
            return _make_readonly_command(content=json.dumps(result, ensure_ascii=False), tool_call_id=tool_call_id)

    return _make_readonly_command(content=json.dumps({"error": f"Task {task_id} not found"}), tool_call_id=tool_call_id)


@tool
def TaskUpdate(
    task_id: str,
    status: Optional[str] = None,
    subject: Optional[str] = None,
    description: Optional[str] = None,
    active_form: Optional[str] = None,
    owner: Optional[str] = None,
    metadata: Optional[Dict[str, Any] | str] = None,
    add_blocked_by: Optional[List[str]] = None,
    add_blocks: Optional[List[str]] = None,
    runtime: ToolRuntime = None,
) -> Command:
    """更新任务的状态、负责人、依赖关系或其他字段。使用 status='deleted' 可删除任务。

    Args:
        task_id: 要更新的任务 ID
        status: 新状态：'pending'、'in_progress'、'completed' 或 'deleted'
        subject: 新的任务标题
        description: 新的任务描述
        active_form: 在加载动画中显示的进行时形式
        owner: 新的负责人
        metadata: 要合并到任务中的元数据键值对，设为 null 可删除该键
        add_blocked_by: 阻塞此任务的任务 ID 列表
        add_blocks: 此任务阻塞的任务 ID 列表
    """
    state = runtime.state if runtime else None
    tool_call_id = runtime.tool_call_id if runtime else ""

    metadata = _coerce_metadata(metadata)

    tasks = _get_task_list(state)
    task = None
    for t in tasks:
        if t.task_id == task_id:
            task = t
            break

    if task is None:
        return _make_readonly_command(
            content=json.dumps({"error": f"Task {task_id} not found"}), tool_call_id=tool_call_id
        )

    # 更新状态
    if status is not None:
        try:
            task.status = TeamTaskStatus(status)
        except ValueError:
            valid_statuses = ", ".join([s.value for s in TeamTaskStatus])
            return _make_readonly_command(
                content=json.dumps({"error": f"Invalid status: {status}. Must be one of: {valid_statuses}"}),
                tool_call_id=tool_call_id,
            )

    # 更新其他字段
    if subject is not None:
        task.subject = subject
    if description is not None:
        task.description = description
    if active_form is not None:
        task.active_form = active_form
    if owner is not None:
        task.owner = owner

    # 合并元数据
    if metadata is not None:
        if task.metadata is None:
            task.metadata = {}
        for key, value in metadata.items():
            if value is None:
                task.metadata.pop(key, None)
            else:
                task.metadata[key] = value

    # 添加 blocked_by 依赖
    if add_blocked_by:
        if task.blocked_by is None:
            task.blocked_by = []
        for bid in add_blocked_by:
            if bid not in task.blocked_by:
                task.blocked_by.append(bid)
            # 同时更新反向关系
            for other in tasks:
                if other.task_id == bid:
                    if other.blocks is None:
                        other.blocks = []
                    if task_id not in other.blocks:
                        other.blocks.append(task_id)
                        other.mark_updated()

    # 添加 blocks 依赖
    if add_blocks:
        if task.blocks is None:
            task.blocks = []
        for bid in add_blocks:
            if bid not in task.blocks:
                task.blocks.append(bid)
            # 同时更新反向关系
            for other in tasks:
                if other.task_id == bid:
                    if other.blocked_by is None:
                        other.blocked_by = []
                    if task_id not in other.blocked_by:
                        other.blocked_by.append(task_id)
                        other.mark_updated()

    task.mark_updated()
    content = f"Updated task #{task_id} status"
    return _make_update_command(task_list=tasks, content=content, tool_call_id=tool_call_id)


@tool
def TaskList(
    runtime: ToolRuntime = None,
) -> Command:
    """列出任务列表中所有任务的摘要信息（id、subject、status、owner、blockedBy）。"""
    state = runtime.state if runtime else None
    tool_call_id = runtime.tool_call_id if runtime else ""

    tasks = _get_task_list(state)
    result = []
    for task in tasks:
        # 跳过已删除的任务
        if task.status == TeamTaskStatus.DELETED:
            continue

        # 仅显示未完成的阻塞任务（排除已完成和已删除的）
        open_blocked_by = []
        if task.blocked_by:
            for bid in task.blocked_by:
                blocker = next((t for t in tasks if t.task_id == bid), None)
                if blocker and blocker.status not in (TeamTaskStatus.COMPLETED, TeamTaskStatus.DELETED):
                    open_blocked_by.append(bid)

        result.append(
            {
                "id": task.task_id,
                "subject": task.subject,
                "status": task.status.value,
                "owner": task.owner,
                "blockedBy": open_blocked_by if open_blocked_by else None,
            }
        )

    content = json.dumps({"tasks": result}, ensure_ascii=False)
    return _make_readonly_command(content=content, tool_call_id=tool_call_id)


def get_task_tools() -> List[BaseTool]:
    """创建通过 LangGraph 状态运作的任务管理工具。

    工具使用 ToolRuntime 进行状态访问，返回 Command 对象
    来更新 LangGraph 状态中的 task_list 字段。

    Returns:
        工具实例列表：TaskCreate、TaskGet、TaskUpdate、TaskList
    """
    return [TaskCreate, TaskGet, TaskUpdate, TaskList]
