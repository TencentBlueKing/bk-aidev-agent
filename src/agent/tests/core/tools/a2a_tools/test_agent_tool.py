# -*- coding: utf-8 -*-
"""A2AAgentTool 单元测试 — 迁移自 test_team_wrapper.py（Phase 28, D-12）。

覆盖：
- _try_extract_member_info: member 模式信息提取
- _try_extract_task_lifecycle: task 模式生命周期提取
- A2AAgentTool.run(): member/task/非匹配场景
- A2AAgentTool.arun(): member/task 异步路径
- types.py KEY_ 常量和 AGENT_TOOL_NAME
- provider.py 集成验证
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest
from aidev_agent.core.tools.a2a_tools.agent_tool import (
    A2AAgentTool,
    _try_extract_member_info,
    _try_extract_task_lifecycle,
)
from aidev_agent.core.tools.a2a_tools.bkai_backend import BkAiBackend
from aidev_agent.core.tools.a2a_tools.provider import AgentBackendResolver, get_agent_tools
from aidev_agent.core.tools.a2a_tools.types import (
    AGENT_TOOL_NAME,
    KEY_AGENT_NAME,
    KEY_EXIT_REASON,
    KEY_MEMBER_NAME,
    KEY_SESSION_CODE,
    KEY_STATUS,
    KEY_TOOL_CALLS,
    AgentBackendType,
    AgentSpec,
)
from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.types import Command

# ── 辅助函数 ──


def _make_tool_args(
    agent_name: str = "member_agent",
    mode: str = "member",
    member_name: str | None = None,
) -> dict[str, Any]:
    """创建工具调用参数字典（替代旧的 _make_tool_call）。"""
    args: dict[str, Any] = {"agent_name": agent_name, "message": "hello", "mode": mode}
    if member_name is not None:
        args["member_name"] = member_name
    return args


def _make_tool_message(content: str, tool_call_id: str = "call_123") -> ToolMessage:
    """创建 ToolMessage。"""
    return ToolMessage(content=content, tool_call_id=tool_call_id)


def _dummy_agent_call(agent_name: str, message: str, mode: str | None = None, **kwargs) -> str:
    """A2AAgentTool 测试用的占位函数。"""
    return json.dumps({"status": "completed", "result": "ok"})


# ============== Test: types.py 常量 ==============


class TestTypesConstants:
    """types.py 中的 JSON 键常量和 AGENT_TOOL_NAME 验证。"""

    def test_key_session_code(self) -> None:
        assert KEY_SESSION_CODE == "session_code"

    def test_key_member_name(self) -> None:
        assert KEY_MEMBER_NAME == "member_name"

    def test_key_agent_name(self) -> None:
        assert KEY_AGENT_NAME == "agent_name"

    def test_key_status(self) -> None:
        assert KEY_STATUS == "status"

    def test_key_exit_reason(self) -> None:
        assert KEY_EXIT_REASON == "exit_reason"

    def test_key_tool_calls(self) -> None:
        assert KEY_TOOL_CALLS == "tool_calls"

    def test_agent_tool_name(self) -> None:
        assert AGENT_TOOL_NAME == "Agent"


# ── _try_extract_member_info 测试 ──


class TestTryExtractMemberInfo:
    """_try_extract_member_info 辅助函数测试。"""

    def test_member_mode_with_session_code(self) -> None:
        """member 模式且返回含 session_code 时提取成功。"""
        tool_args = _make_tool_args(agent_name="helper", mode="member")
        content = json.dumps(
            {
                "status": "completed",
                "result": "ok",
                "session_code": "sess_abc",
                "member_name": "helper",
                "agent_name": "helper",
            }
        )
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result == ("helper", "sess_abc", "helper")

    def test_member_mode_with_custom_member_name(self) -> None:
        """指定 member_name 时，使用 member_name 作为 key。"""
        tool_args = _make_tool_args(agent_name="judge_agent", mode="member", member_name="judge_1")
        content = json.dumps(
            {
                "status": "completed",
                "result": "ok",
                "session_code": "sess_xyz",
                "member_name": "judge_1",
                "agent_name": "judge_agent",
            }
        )
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result == ("judge_1", "sess_xyz", "judge_agent")

    def test_member_name_defaults_to_agent_name(self) -> None:
        """member_name 未指定时默认使用 agent_name。"""
        tool_args = _make_tool_args(agent_name="helper", mode="member")
        content = json.dumps({"status": "completed", "result": "ok", "session_code": "sess_abc"})
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result is not None
        member_name, session_code, agent_name = result
        assert member_name == "helper"
        assert session_code == "sess_abc"
        assert agent_name == "helper"

    def test_task_mode_no_extraction(self) -> None:
        """task 模式不提取。"""
        tool_args = _make_tool_args(mode="task")
        content = json.dumps({"status": "completed", "result": "ok"})
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result is None

    def test_no_tool_name_check_needed(self) -> None:
        """不再检查工具名 — A2AAgentTool 本身就是 Agent 工具子类。"""
        # 旧 API 需要 tool_call.get("name") == "Agent"
        # 新 API 只看 mode 字段
        tool_args = _make_tool_args(mode="member")
        content = json.dumps({"status": "completed", "session_code": "sess_abc"})
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result is not None  # 不因为缺少 name 字段而返回 None

    def test_no_session_code_in_result_no_extraction(self) -> None:
        """返回结果无 session_code 时不提取。"""
        tool_args = _make_tool_args(mode="member")
        content = json.dumps({"status": "completed", "result": "ok"})
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result is None

    def test_failed_result_with_session_code_still_extracts(self) -> None:
        """即使 status=failed，只要包含 session_code 仍提取。"""
        tool_args = _make_tool_args(mode="member")
        content = json.dumps({"status": "failed", "error": "timeout", "session_code": "sess_abc"})
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result is not None

    def test_empty_agent_name_no_extraction(self) -> None:
        """agent_name 为空时不提取。"""
        tool_args = _make_tool_args(agent_name="", mode="member")
        content = json.dumps({"status": "completed", "session_code": "sess_abc"})
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result is None

    def test_mode_none_no_extraction(self) -> None:
        """mode 为 None 时不提取。"""
        tool_args = {"agent_name": "helper", "message": "hello"}  # mode 未传
        content = json.dumps({"status": "completed", "session_code": "sess_abc"})
        msg = _make_tool_message(content)
        result = _try_extract_member_info(tool_args, msg)
        assert result is None

    def test_non_dict_content_returns_none(self) -> None:
        """content 解析为非 dict 时返回 None。"""
        tool_args = _make_tool_args(mode="member")
        msg = _make_tool_message(json.dumps(["not", "a", "dict"]))
        result = _try_extract_member_info(tool_args, msg)
        assert result is None

    def test_invalid_json_returns_none(self) -> None:
        """content 不是合法 JSON 时返回 None。"""
        tool_args = _make_tool_args(mode="member")
        msg = _make_tool_message(content="not json")
        result = _try_extract_member_info(tool_args, msg)
        assert result is None

    def test_empty_content_returns_none(self) -> None:
        """content 为空字符串时返回 None。"""
        tool_args = _make_tool_args(mode="member")
        msg = _make_tool_message(content="")
        result = _try_extract_member_info(tool_args, msg)
        assert result is None


# ── _try_extract_task_lifecycle 测试 ──


class TestTryExtractTaskLifecycle:
    """_try_extract_task_lifecycle 辅助函数测试。"""

    def test_task_mode_with_valid_json(self) -> None:
        """task 模式带有效 JSON 返回 (key, entry)，key = f"{agent_name}:{tool_call_id}"。"""
        tool_args = _make_tool_args(agent_name="task_agent", mode="task")
        content = json.dumps(
            {
                "status": "completed",
                "agent_name": "task_agent",
                "result": "task done",
                "tool_calls": 3,
                "exit_reason": "completed",
            }
        )
        msg = _make_tool_message(content)
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is not None
        key, entry = result
        assert key == "task_agent:call_123"

    def test_entry_contains_required_fields(self) -> None:
        """entry 包含 agent_name, status, tool_call_id。"""
        tool_args = _make_tool_args(agent_name="sub_agent", mode="task")
        content = json.dumps({"status": "completed", "agent_name": "sub_agent", "result": "ok"})
        msg = _make_tool_message(content)
        result = _try_extract_task_lifecycle(tool_args, msg, "call_abc")
        assert result is not None
        _key, entry = result
        assert entry[KEY_AGENT_NAME] == "sub_agent"
        assert entry[KEY_STATUS] == "completed"
        assert entry["tool_call_id"] == "call_abc"

    def test_rich_fields_forwarded_when_present(self) -> None:
        """exit_reason, tool_calls 存在时转发。"""
        tool_args = _make_tool_args(agent_name="rich_agent", mode="task")
        content = json.dumps(
            {"status": "completed", "agent_name": "rich_agent", "exit_reason": "completed", "tool_calls": 5}
        )
        msg = _make_tool_message(content)
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is not None
        _key, entry = result
        assert entry[KEY_EXIT_REASON] == "completed"
        assert entry[KEY_TOOL_CALLS] == 5

    def test_rich_fields_not_inserted_when_absent(self) -> None:
        """exit_reason, tool_calls 不存在时不插入。"""
        tool_args = _make_tool_args(agent_name="minimal_agent", mode="task")
        content = json.dumps({"status": "completed", "agent_name": "minimal_agent"})
        msg = _make_tool_message(content)
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is not None
        _key, entry = result
        assert KEY_EXIT_REASON not in entry
        assert KEY_TOOL_CALLS not in entry

    def test_member_mode_returns_none(self) -> None:
        """member 模式返回 None。"""
        tool_args = _make_tool_args(agent_name="member_agent", mode="member")
        content = json.dumps({"status": "completed", "result": "ok", "session_code": "sess_abc"})
        msg = _make_tool_message(content)
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is None

    def test_invalid_json_returns_none(self) -> None:
        """无效 JSON 返回 None。"""
        tool_args = _make_tool_args(agent_name="bad_json_agent", mode="task")
        msg = _make_tool_message("not valid json {{{")
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is None

    def test_json_not_dict_returns_none(self) -> None:
        """JSON 非 dict 返回 None。"""
        tool_args = _make_tool_args(agent_name="list_agent", mode="task")
        msg = _make_tool_message(json.dumps([1, 2, 3]))
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is None

    def test_empty_agent_name_returns_none(self) -> None:
        """agent_name 为空返回 None。"""
        tool_args = _make_tool_args(agent_name="", mode="task")
        content = json.dumps({"status": "completed", "result": "ok"})
        msg = _make_tool_message(content)
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is None

    def test_failed_status_still_extracts(self) -> None:
        """失败状态仍提取。"""
        tool_args = _make_tool_args(agent_name="failed_agent", mode="task")
        content = json.dumps(
            {
                "status": "failed",
                "agent_name": "failed_agent",
                "error": "timeout",
                "exit_reason": "timeout",
                "tool_calls": 0,
            }
        )
        msg = _make_tool_message(content)
        result = _try_extract_task_lifecycle(tool_args, msg, "call_123")
        assert result is not None
        key, entry = result
        assert key == "failed_agent:call_123"
        assert entry[KEY_STATUS] == "failed"
        assert entry[KEY_EXIT_REASON] == "timeout"

    def test_no_mode_defaults_to_task(self) -> None:
        """mode 未设置时默认为 task 模式。"""
        tool_args = {"agent_name": "worker", "message": "hello"}
        msg = _make_tool_message(json.dumps({"status": "completed"}))
        result = _try_extract_task_lifecycle(tool_args, msg, "call_999")
        assert result is not None
        key, _entry = result
        assert key == "worker:call_999"


# ── A2AAgentTool.run() 测试 ──


class TestA2AAgentToolRun:
    """A2AAgentTool.run() 测试。"""

    @pytest.fixture()
    def agent_tool(self) -> A2AAgentTool:
        """构造测试用 A2AAgentTool 实例。"""
        return A2AAgentTool.from_function(
            func=_dummy_agent_call,
            name="Agent",
            description="test agent tool",
        )

    def test_member_mode_returns_command(self, agent_tool: A2AAgentTool) -> None:
        """member 模式 ToolMessage 被转为 Command。"""

        def member_call(agent_name: str, message: str, mode: str | None = None, **kwargs) -> str:
            return json.dumps(
                {
                    "status": "completed",
                    "result": "ok",
                    "session_code": "sess_abc",
                    "member_name": "helper",
                    "agent_name": "helper",
                }
            )

        tool = A2AAgentTool.from_function(func=member_call, name="Agent", description="test")
        result = tool.run(
            {"agent_name": "helper", "message": "hello", "mode": "member"},
            tool_call_id="call_123",
        )
        assert isinstance(result, Command)
        assert "bk_agent_team" in result.update
        assert result.update["bk_agent_team"]["helper"][KEY_SESSION_CODE] == "sess_abc"
        assert result.update["bk_agent_team"]["helper"][KEY_STATUS] == "active"
        assert result.update["bk_agent_team"]["helper"][KEY_AGENT_NAME] == "helper"
        assert "messages" in result.update
        assert len(result.update["messages"]) == 1
        assert isinstance(result.update["messages"][0], ToolMessage)

    def test_member_mode_custom_member_name(self, agent_tool: A2AAgentTool) -> None:
        """member 模式指定 member_name 时 Command 使用 member_name 作为 key。"""

        def member_call(
            agent_name: str, message: str, mode: str | None = None, member_name: str | None = None, **kwargs
        ) -> str:
            return json.dumps(
                {
                    "status": "completed",
                    "result": "ok",
                    "session_code": "sess_xyz",
                    "member_name": "judge_1",
                    "agent_name": "judge_agent",
                }
            )

        tool = A2AAgentTool.from_function(func=member_call, name="Agent", description="test")
        result = tool.run(
            {"agent_name": "judge_agent", "message": "hello", "mode": "member", "member_name": "judge_1"},
            tool_call_id="call_456",
        )
        assert isinstance(result, Command)
        assert "judge_1" in result.update["bk_agent_team"]
        assert result.update["bk_agent_team"]["judge_1"][KEY_SESSION_CODE] == "sess_xyz"
        assert result.update["bk_agent_team"]["judge_1"][KEY_AGENT_NAME] == "judge_agent"

    def test_task_mode_returns_command(self, agent_tool: A2AAgentTool) -> None:
        """task 模式 ToolMessage 被转为 Command，key = f"{agent_name}:{tool_call_id}"。"""

        def task_call(agent_name: str, message: str, mode: str | None = None, **kwargs) -> str:
            return json.dumps(
                {
                    "status": "completed",
                    "agent_name": "task_agent",
                    "result": "task done",
                    "tool_calls": 3,
                    "exit_reason": "completed",
                }
            )

        tool = A2AAgentTool.from_function(func=task_call, name="Agent", description="test")
        result = tool.run(
            {"agent_name": "task_agent", "message": "hello", "mode": "task"},
            tool_call_id="call_789",
        )
        assert isinstance(result, Command)
        assert "bk_agent_team" in result.update
        key = "task_agent:call_789"
        assert key in result.update["bk_agent_team"]
        entry = result.update["bk_agent_team"][key]
        assert entry[KEY_AGENT_NAME] == "task_agent"
        assert entry[KEY_STATUS] == "completed"
        assert entry["tool_call_id"] == "call_789"
        assert "messages" in result.update

    def test_task_mode_failed_status(self, agent_tool: A2AAgentTool) -> None:
        """task 模式失败状态仍创建 Command。"""

        def failed_call(agent_name: str, message: str, mode: str | None = None, **kwargs) -> str:
            return json.dumps(
                {
                    "status": "failed",
                    "agent_name": "doomed_agent",
                    "error": "timeout",
                    "exit_reason": "timeout",
                    "tool_calls": 0,
                }
            )

        tool = A2AAgentTool.from_function(func=failed_call, name="Agent", description="test")
        result = tool.run(
            {"agent_name": "doomed_agent", "message": "hello", "mode": "task"},
            tool_call_id="call_fail",
        )
        assert isinstance(result, Command)
        key = "doomed_agent:call_fail"
        assert key in result.update["bk_agent_team"]
        entry = result.update["bk_agent_team"][key]
        assert entry[KEY_STATUS] == "failed"

    def test_mode_none_returns_command_for_task(self) -> None:
        """mode 未传时（默认 task），若 agent_name 非空则匹配 task 模式返回 Command。"""

        def simple_call(agent_name: str, message: str, **kwargs) -> str:
            return json.dumps({"status": "completed", "result": "ok"})

        tool = A2AAgentTool.from_function(func=simple_call, name="Agent", description="test")
        result = tool.run(
            {"agent_name": "helper", "message": "hello"},  # mode 未传
            tool_call_id="call_default",
        )
        # mode=None → 不匹配 member；匹配 task（因为 agent_name 非空）
        assert isinstance(result, Command)

    def test_no_agent_name_returns_tool_message(self) -> None:
        """agent_name 为空时返回 ToolMessage 原样。"""

        def empty_call(agent_name: str, message: str, **kwargs) -> str:
            return json.dumps({"status": "completed", "result": "ok"})

        tool = A2AAgentTool.from_function(func=empty_call, name="Agent", description="test")
        result = tool.run(
            {"agent_name": "", "message": "hello", "mode": "task"},
            tool_call_id="call_empty",
        )
        assert isinstance(result, ToolMessage)  # 不匹配，原样返回


# ── A2AAgentTool.arun() 异步测试 ──


class TestA2AAgentToolAsyncRun:
    """A2AAgentTool.arun() 异步测试。"""

    @pytest.mark.asyncio
    async def test_member_mode_returns_command(self) -> None:
        """arun() member 模式返回 Command。"""

        def member_call(agent_name: str, message: str, mode: str | None = None, **kwargs) -> str:
            return json.dumps(
                {
                    "status": "completed",
                    "result": "ok",
                    "session_code": "sess_async",
                    "member_name": "helper",
                    "agent_name": "helper",
                }
            )

        tool = A2AAgentTool.from_function(func=member_call, name="Agent", description="test")
        result = await tool.arun(
            {"agent_name": "helper", "message": "hello", "mode": "member"},
            tool_call_id="call_async_1",
        )
        assert isinstance(result, Command)
        assert "bk_agent_team" in result.update
        assert result.update["bk_agent_team"]["helper"][KEY_SESSION_CODE] == "sess_async"

    @pytest.mark.asyncio
    async def test_task_mode_returns_command(self) -> None:
        """arun() task 模式返回 Command。"""

        def task_call(agent_name: str, message: str, mode: str | None = None, **kwargs) -> str:
            return json.dumps(
                {
                    "status": "completed",
                    "agent_name": "task_agent",
                    "result": "task done",
                    "tool_calls": 3,
                    "exit_reason": "completed",
                }
            )

        tool = A2AAgentTool.from_function(func=task_call, name="Agent", description="test")
        result = await tool.arun(
            {"agent_name": "task_agent", "message": "hello", "mode": "task"},
            tool_call_id="call_async_2",
        )
        assert isinstance(result, Command)
        key = "task_agent:call_async_2"
        assert key in result.update["bk_agent_team"]


# ============== Test: provider.py 集成 ==============


class TestProviderIntegration:
    """provider.py 使用 A2AAgentTool 集成验证。"""

    def test_agent_tool_is_a2a_agent_tool_instance(self) -> None:
        """get_agent_tools() 返回的第一个工具是 A2AAgentTool 实例。"""
        specs = [AgentSpec(name="test", description="test", backend_type=AgentBackendType.BKAI, params={})]
        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend)
        tools = get_agent_tools(specs, resolver)

        agent_tool = next(t for t in tools if t.name == "Agent")
        assert isinstance(agent_tool, A2AAgentTool)

    def test_send_messages_is_structured_tool_instance(self) -> None:
        """get_agent_tools() 返回的第二个工具（sendMessages）是 StructuredTool 实例。"""
        specs = [AgentSpec(name="test", description="test", backend_type=AgentBackendType.BKAI, params={})]
        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend)
        tools = get_agent_tools(specs, resolver)

        send_msg_tool = next(t for t in tools if t.name == "sendMessages")
        assert isinstance(send_msg_tool, StructuredTool)
        assert not isinstance(send_msg_tool, A2AAgentTool)

    def test_provider_no_team_wrapper_reference(self) -> None:
        """provider.py 中无 'team_wrapper' 代码引用。"""
        provider_path = pathlib.Path(__file__).parent.parent.parent.parent.parent / (
            "aidev_agent/core/tools/a2a_tools/provider.py"
        )
        content = provider_path.read_text()
        # 注释中允许 team_wrapper，但不应有 import 或调用
        lines = [line for line in content.splitlines() if not line.strip().startswith("#")]
        code_text = "\n".join(lines)
        assert "import team_wrapper" not in code_text
        assert "team_sync_wrapper" not in code_text
        assert "team_async_wrapper" not in code_text
