# -*- coding: utf-8 -*-
"""LocalBackend 单元测试。

覆盖：
1. LocalBackend 类零参构造
2. 满足 AgentBackend Protocol
3. 缺少 agent_cls 时 raise ValueError
4. 缺少 ctx 时 raise ValueError
5. execute() 正常执行 agent_cls() + build(ctx) + child.execute()
6. execute() 注入 session_code 和 session_context_data 到 ctx
7. spawn_depth 深度传播（Phase 33 改造）
8. child.execute() 异常时向上抛出，由上层错误处理器统一处理
9. agent_cls().build(ctx) 异常时向上抛出，由上层错误处理器统一处理
10. _extract_text() 从 choices 中提取文本
11. _extract_text() 兼容 str 返回
12. _extract_text() 无法识别格式返回空字符串
13. _run_subagent 流式执行
14. _run_subagent 心跳发送
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.tools.a2a_tools.local_backend import (
    _ERR_EMPTY_RESOURCE_MANAGER,
    _ERR_EMPTY_SESSION_CODE,
    _ERR_MISSING_AGENT_INSTANCE,
    _ERR_MISSING_CTX,
    LocalBackend,
)
from aidev_agent.core.tools.a2a_tools.types import AgentBackend, AgentBackendType, AgentSpec
from aidev_agent.core.tools.a2a_tools.utils import extract_child_execute_kwargs
from aidev_agent.pydantic_models import ExecuteKwargs


def _make_spec(**overrides: Any) -> AgentSpec:
    """创建测试用 AgentSpec，默认 backend_type=LOCAL。"""
    defaults: dict[str, Any] = {
        "name": "test_local_agent",
        "description": "A test local agent",
        "backend_type": AgentBackendType.LOCAL,
        "params": {},
        "timeout_seconds": 300,
    }
    defaults.update(overrides)
    return AgentSpec(**defaults)


def _make_mock_rm() -> MagicMock:
    """创建 mock resource_manager。"""
    return MagicMock()


@dataclass
class _FakeCtx:
    """模拟 AgentBuildContext（dataclass，支持 dataclasses.replace）。"""

    session_code: str = ""
    session_context_data: list[dict] = field(default_factory=list)
    resource_manager: Any = field(default_factory=_make_mock_rm)
    extra: dict[str, Any] = field(default_factory=dict)


def _make_mock_child(result_text: str = "sub-agent result") -> MagicMock:
    """创建 mock child agent，execute 返回标准格式。"""
    child = MagicMock()
    child.execute.return_value = {
        "choices": [{"delta": {"role": "assistant", "content": result_text}}],
    }
    child.thread_id = "test_thread_id"
    return child


def _make_mock_agent_cls(mock_child: MagicMock | None = None) -> MagicMock:
    """创建 mock agent_cls，调用时返回实例（其 build 返回 mock_child）。"""
    if mock_child is None:
        mock_child = _make_mock_child()

    mock_instance = MagicMock()
    mock_instance.build.return_value = mock_child

    mock_cls = MagicMock(return_value=mock_instance)
    return mock_cls


# ============== Test 1: 零参构造 ==============


class TestLocalBackendConstruction:
    """Test 1: LocalBackend 类零参构造成功。"""

    def test_zero_arg_construction(self) -> None:
        backend = LocalBackend()
        assert backend is not None


# ============== Test 2: 满足 AgentBackend Protocol ==============


class TestLocalBackendProtocol:
    """Test 2: LocalBackend 满足 AgentBackend Protocol (isinstance 检查)。"""

    def test_satisfies_agent_backend_protocol(self) -> None:
        backend = LocalBackend()
        assert isinstance(backend, AgentBackend)


# ============== Test 3: 缺少 agent_cls ==============


class TestLocalBackendMissingAgentCls:
    """Test 3: execute() 缺少 agent_cls 时 raise ValueError。"""

    def test_missing_agent_cls_raises_error(self) -> None:
        backend = LocalBackend()
        spec = _make_spec(params={"ctx": _FakeCtx()})
        with pytest.raises(ValueError, match=_ERR_MISSING_AGENT_INSTANCE):
            backend.execute(spec, "hello", session_code="sess-test")

    def test_none_agent_cls_raises_error(self) -> None:
        backend = LocalBackend()
        spec = _make_spec(params={"agent_cls": None, "ctx": _FakeCtx()})
        with pytest.raises(ValueError, match=_ERR_MISSING_AGENT_INSTANCE):
            backend.execute(spec, "hello", session_code="sess-test")


# ============== Test 4: 缺少 ctx ==============


class TestLocalBackendMissingCtx:
    """Test 4: execute() 缺少 ctx 时 raise ValueError。"""

    def test_missing_ctx_raises_error(self) -> None:
        backend = LocalBackend()
        mock_cls = _make_mock_agent_cls()
        spec = _make_spec(params={"agent_cls": mock_cls})
        with pytest.raises(ValueError, match=_ERR_MISSING_CTX):
            backend.execute(spec, "hello", session_code="sess-test")

    def test_none_ctx_raises_error(self) -> None:
        backend = LocalBackend()
        mock_cls = _make_mock_agent_cls()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": None})
        with pytest.raises(ValueError, match=_ERR_MISSING_CTX):
            backend.execute(spec, "hello", session_code="sess-test")


# ============== Test 5: execute() 正常执行 ==============


class TestLocalBackendNormalExecution:
    """Test 5: execute() 正常调用 agent_cls() + build(ctx) + child.execute()，返回结果。"""

    def test_normal_execution_returns_completed(self) -> None:
        backend = LocalBackend()

        mock_child = _make_mock_child("sub-agent result")
        mock_cls = _make_mock_agent_cls(mock_child)

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        result = backend.execute(spec, "do something", session_code="sess-test")

        assert result.status == "completed"
        assert result.result == "sub-agent result"
        # 验证 agent_cls 被调用创建实例
        mock_cls.assert_called_once()
        # 验证 build 被调用
        mock_cls.return_value.build.assert_called_once()
        mock_child.execute.assert_called_once()

    def test_execute_injects_session_context_data(self) -> None:
        """验证 _prepare_session 加载的 session_context_data 通过 ctx 传入 build。"""
        backend = LocalBackend()

        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)

        # 模拟 resource_manager 返回历史上下文（含当前用户消息）
        mock_rm = MagicMock()
        mock_rm.get_chat_session_context.return_value = [
            {"role": "user", "content": "test message"},
        ]

        ctx = _FakeCtx(resource_manager=mock_rm)
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        backend.execute(spec, "test message", session_code="sess-test")

        # 验证 build 传入的 ctx 包含 session_context_data
        call_args = mock_cls.return_value.build.call_args
        built_ctx = call_args[0][0]
        assert built_ctx.session_context_data == [{"role": "user", "content": "test message"}]

    def test_execute_missing_rm_raises_error(self) -> None:
        """ctx 没有 resource_manager 时 raise ValueError。"""
        backend = LocalBackend()
        mock_cls = _make_mock_agent_cls()
        ctx = _FakeCtx(resource_manager=None)
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        with pytest.raises(ValueError, match=_ERR_EMPTY_RESOURCE_MANAGER):
            backend.execute(spec, "hello", session_code="sess-test")


# ============== Test 6: execute() session_code 注入 ==============


class TestLocalBackendSessionCodeRequired:
    """Test 6: execute() 要求 session_code 非空，并正确注入到 ctx。"""

    def test_empty_session_code_raises_error(self) -> None:
        """空 session_code 触发 ValueError。"""
        backend = LocalBackend()

        mock_cls = _make_mock_agent_cls()

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        with pytest.raises(ValueError, match=_ERR_EMPTY_SESSION_CODE):
            backend.execute(spec, "hello", session_code="")

    def test_execute_member_returns_completed_with_session_code(self) -> None:
        backend = LocalBackend()

        mock_cls = _make_mock_agent_cls()

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        result = backend.execute(spec, "hello", session_code="sess-123")

        assert result.status == "completed"
        assert result.result == "sub-agent result"

    def test_execute_member_injects_session_code_into_ctx(self) -> None:
        """验证 session_code 通过 dataclasses.replace 注入到 ctx。"""
        backend = LocalBackend()

        mock_cls = _make_mock_agent_cls()

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        backend.execute(spec, "hello", session_code="sess-456")

        # build 传入的 ctx 的 session_code 应被替换
        call_args = mock_cls.return_value.build.call_args
        built_ctx = call_args[0][0]
        assert built_ctx.session_code == "sess-456"

    def test_execute_member_missing_agent_cls_raises_error(self) -> None:
        """缺少 agent_cls 时 raise ValueError（validate 在 session_code 之后）。"""
        backend = LocalBackend()
        spec = _make_spec(params={"ctx": _FakeCtx()})
        with pytest.raises(ValueError, match=_ERR_MISSING_AGENT_INSTANCE):
            backend.execute(spec, "hello", session_code="sess-789")


# ============== Test 7: spawn_depth 深度传播 ==============


class TestLocalBackendNestingProtection:
    """Test 7: execute() 通过 _extract_execute_kwargs 传播 spawn_depth。"""

    def test_execute_propagates_spawn_depth(self) -> None:
        """execute() 将 spawn_depth 递增传播到子 Agent 的 execute_kwargs。"""
        backend = LocalBackend()

        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        # 父 Agent spawn_depth=0
        parent_ek = ExecuteKwargs(spawn_depth=0, max_spawn_depth=1, session_code="parent-sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        backend.execute(spec, "hello", session_code="sess-flag", config=config)

        # 验证子 Agent 的 execute_kwargs.spawn_depth = 1
        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.spawn_depth == 1
        assert child_ek.spawned_by == "parent-sess"
        assert child_ek.max_spawn_depth == 1

    def test_execute_depth_increments_at_each_level(self) -> None:
        """多级嵌套时 spawn_depth 逐级递增。"""
        backend = LocalBackend()

        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        # 模拟二级子 Agent（spawn_depth=1），其子应为 depth=2
        parent_ek = ExecuteKwargs(spawn_depth=1, max_spawn_depth=5, session_code="level1-sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        backend.execute(spec, "hello", session_code="sess-abc", config=config)

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.spawn_depth == 2
        assert child_ek.spawned_by == "level1-sess"
        assert child_ek.max_spawn_depth == 5

    def test_execute_inherits_tool_deny_and_allow(self) -> None:
        """tool_deny 和 tool_allow 由 model_copy 自动继承。"""
        backend = LocalBackend()

        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        parent_ek = ExecuteKwargs(
            spawn_depth=0,
            max_spawn_depth=1,
            tool_deny=["web_search"],
            tool_allow=["Agent", "search"],
            session_code="parent-sess",
        )
        config = {"configurable": {"execute_kwargs": parent_ek}}
        backend.execute(spec, "hello", session_code="sess-deny", config=config)

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.tool_deny == ["web_search"]
        assert child_ek.tool_allow == ["Agent", "search"]

    def test_extract_execute_kwargs_increments_spawn_depth_e2e(self) -> None:
        """端到端：父 ExecuteKwargs(spawn_depth=2) → 子 spawn_depth=3（深度递增不被重置）。"""
        parent_ek = ExecuteKwargs(spawn_depth=2, max_spawn_depth=4, session_code="parent_sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        child = extract_child_execute_kwargs(config, state=None, session_code="child_sess", caller_bk_app_code="app")
        assert child.spawn_depth == 3
        assert child.spawned_by == "parent_sess"
        assert child.max_spawn_depth == 4  # 继承父 max_spawn_depth

    def test_extract_execute_kwargs_resets_thread_id(self) -> None:
        """D-04：子 execute_kwargs.thread_id 为 None，不继承父 thread_id。"""
        parent_ek = ExecuteKwargs(spawn_depth=0, max_spawn_depth=2, session_code="p", thread_id="parent-thread-123")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        child = extract_child_execute_kwargs(config, state=None, session_code="child_sess", caller_bk_app_code="")
        assert child.thread_id is None

    def test_extract_execute_kwargs_preserves_identity_fields(self) -> None:
        """D-03：身份字段（executor/caller_*）保持父值继承，不被重置。"""
        parent_ek = ExecuteKwargs(
            spawn_depth=0,
            max_spawn_depth=2,
            session_code="p",
            executor="calling-user",
            caller_bk_app_code="bk-app",
            caller_bk_biz_env="prod",
            caller_bk_biz_id=123,
        )
        config = {"configurable": {"execute_kwargs": parent_ek}}
        child = extract_child_execute_kwargs(config, state=None, session_code="child_sess", caller_bk_app_code="")
        assert child.executor == "calling-user"
        assert child.caller_bk_app_code == "bk-app"
        assert child.caller_bk_biz_env == "prod"
        assert child.caller_bk_biz_id == 123


# ============== Test 8: child.execute() 异常 ==============


class TestLocalBackendExecutionError:
    """Test 8: execute() 执行异常时向上抛出，由上层错误处理器统一处理。"""

    def test_execute_exception_returns_failed(self) -> None:
        backend = LocalBackend()

        mock_child = MagicMock()
        mock_child.execute.side_effect = RuntimeError("child execution failed")
        mock_child.thread_id = "test_thread_id"

        mock_cls = _make_mock_agent_cls(mock_child)

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx}, timeout_seconds=5)
        with pytest.raises(RuntimeError, match="child execution failed"):
            backend.execute(spec, "hello", session_code="sess-err")


# ============== Test 9: agent_cls().build() 异常 ==============


class TestLocalBackendBuildError:
    """Test 9: agent_cls().build(ctx) 异常时向上抛出，由上层错误处理器统一处理。"""

    def test_build_exception_returns_failed(self) -> None:
        backend = LocalBackend()

        mock_instance = MagicMock()
        mock_instance.build.side_effect = ValueError("build config error")

        mock_cls = MagicMock(return_value=mock_instance)

        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})
        with pytest.raises(ValueError, match="build config error"):
            backend.execute(spec, "hello", session_code="sess-build-err")

    def test_build_exception_marks_session_failed(self) -> None:
        """build 失败后必须将 session 置为 FAILED，避免残留 RUNNING。"""
        backend = LocalBackend()

        mock_instance = MagicMock()
        mock_instance.build.side_effect = ValueError("build config error")
        mock_cls = MagicMock(return_value=mock_instance)

        rm = _make_mock_rm()
        ctx = _FakeCtx(resource_manager=rm)
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        with pytest.raises(ValueError, match="build config error"):
            backend.execute(spec, "hello", session_code="sess-build-failed")

        # session 应被置为 FAILED
        failed_calls = [call for call in rm.update_session_status.call_args_list if call.args[1] == "failed"]
        assert failed_calls, f"expected update_session_status(failed), got {rm.update_session_status.call_args_list}"

    def test_prepare_session_exception_marks_session_failed(self) -> None:
        """_prepare_session 内部失败后必须将 session 置为 FAILED。"""
        backend = LocalBackend()

        mock_cls = MagicMock()
        rm = _make_mock_rm()
        # _prepare_session 内部调用 get_or_create_session，让它抛异常
        rm.get_or_create_session.side_effect = RuntimeError("platform api error")

        ctx = _FakeCtx(resource_manager=rm)
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        with pytest.raises(RuntimeError, match="platform api error"):
            backend.execute(spec, "hello", session_code="sess-prepare-failed")

        # 即使 prepare 中途失败，session 也应被兜底置为 FAILED
        failed_calls = [call for call in rm.update_session_status.call_args_list if call.args[1] == "failed"]
        assert failed_calls, f"expected update_session_status(failed), got {rm.update_session_status.call_args_list}"


# ============== Test 10: _extract_text 从 choices 提取文本 ==============


class TestExtractText:
    """Test 10: _extract_text() 从标准 choices 格式中提取文本。"""

    def test_extract_from_choices(self) -> None:
        result = {"choices": [{"delta": {"role": "assistant", "content": "hello world"}}]}
        assert LocalBackend._extract_text(result) == "hello world"

    def test_extract_empty_choices(self) -> None:
        result: dict[str, Any] = {"choices": []}
        assert LocalBackend._extract_text(result) == ""

    def test_extract_missing_delta(self) -> None:
        result = {"choices": [{}]}
        assert LocalBackend._extract_text(result) == ""

    def test_extract_none_content(self) -> None:
        result = {"choices": [{"delta": {"role": "assistant", "content": None}}]}
        assert LocalBackend._extract_text(result) == ""


# ============== Test 11: _extract_text 兼容 str 返回 ==============


class TestExtractTextStrFallback:
    """Test 11: _extract_text() 兼容 str 返回。"""

    def test_str_result(self) -> None:
        assert LocalBackend._extract_text("plain text result") == "plain text result"


# ============== Test 12: _extract_text 无法识别格式 ==============


class TestExtractTextUnknownFormat:
    """Test 12: _extract_text() 无法识别格式返回空字符串。"""

    def test_unknown_format_returns_empty(self) -> None:
        assert LocalBackend._extract_text(12345) == ""

    def test_none_result_returns_empty(self) -> None:
        assert LocalBackend._extract_text(None) == ""

    def test_empty_dict_returns_empty(self) -> None:
        assert LocalBackend._extract_text({}) == ""


# ============== Test 13: _run_subagent 流式执行 ==============


class TestRunSubagent:
    """Test 13: _run_subagent 流式执行子 Agent。"""

    def test_run_subagent_calls_execute_with_stream(self) -> None:
        """验证 _run_subagent 使用 stream 模式调用 subagent.execute。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = []  # 流式返回空事件列表

        result_text, events, _tool_count = backend._run_subagent(  # noqa: SLF001
            mock_subagent, execute_kwargs=ExecuteKwargs(stream=True, invoke_timeout=60)
        )

        # _run_subagent 不再修改 execute_kwargs，直接透传给 subagent.execute
        mock_subagent.execute.assert_called_once()

        assert result_text == ""
        assert events == []

    def test_run_subagent_does_not_modify_execute_kwargs(self) -> None:
        """验证 _run_subagent 不再修改 execute_kwargs（invoke_timeout 由 extract_child_execute_kwargs 注入）。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = []  # 流式返回空事件列表

        ek = ExecuteKwargs(stream=True, invoke_timeout=None)
        backend._run_subagent(  # noqa: SLF001
            mock_subagent, execute_kwargs=ek
        )

        # _run_subagent 不再设置 invoke_timeout，保持 None
        assert ek.invoke_timeout is None
        mock_subagent.execute.assert_called_once_with(ek)


# ============== Test 15: _run_subagent 心跳发送 ==============


class TestLocalBackendHeartbeat:
    """Test 15: _run_subagent 流式循环中发送 subagent.heartbeat 事件（D-04）。"""

    def test_heartbeat_events_sent_with_callback(self) -> None:
        """当 progress_callback 为 mock 时，流式执行中发送 subagent.heartbeat 事件。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"}',
            'data: {"type": "TOOL_CALL_START", "tool_call_id": "t1"}',
            "data: [DONE]",
        ]

        mock_callback = MagicMock()
        with patch("aidev_agent.core.tools.a2a_tools.local_backend.logger"):
            backend._run_subagent(  # noqa: SLF001
                mock_subagent,
                execute_kwargs=ExecuteKwargs(stream=True),
                progress_callback=mock_callback,
            )

        # 验证 progress_callback 被调用，且至少有一次带有 subagent.heartbeat
        heartbeat_calls = [call for call in mock_callback.call_args_list if call[0][0] == "subagent.heartbeat"]
        assert len(heartbeat_calls) > 0, "Expected at least one subagent.heartbeat event"

        # 验证第一个心跳包含正确字段（不再有 elapsed_seconds）
        first_heartbeat = heartbeat_calls[0]
        kwargs = first_heartbeat[1]
        assert "tool_count" in kwargs
        assert "iteration" in kwargs
        assert isinstance(kwargs["tool_count"], int)
        assert isinstance(kwargs["iteration"], int)

    def test_heartbeat_fields_correct(self) -> None:
        """每个心跳包含正确的 tool_count, iteration 值。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "A"}',
            'data: {"type": "TOOL_CALL_START", "tool_call_id": "t1"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "B"}',
            "data: [DONE]",
        ]

        mock_callback = MagicMock()
        with patch("aidev_agent.core.tools.a2a_tools.local_backend.logger"):
            backend._run_subagent(  # noqa: SLF001
                mock_subagent,
                execute_kwargs=ExecuteKwargs(stream=True),
                progress_callback=mock_callback,
            )

        heartbeat_calls = [call for call in mock_callback.call_args_list if call[0][0] == "subagent.heartbeat"]
        # 3 parsed events → 3 heartbeat calls
        assert len(heartbeat_calls) == 3

        # 最后一个心跳的 iteration 应该等于总事件数
        last_kwargs = heartbeat_calls[-1][1]
        assert last_kwargs["iteration"] == 3
        # tool_count 应该是 TOOL_CALL_START 事件总数
        assert last_kwargs["tool_count"] == 1

    def test_no_heartbeat_when_callback_none(self) -> None:
        """当 progress_callback 为 None 时，无心跳（向后兼容）。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"}',
            "data: [DONE]",
        ]

        with patch("aidev_agent.core.tools.a2a_tools.local_backend.logger"):
            result_text, events, _tool_count = backend._run_subagent(  # noqa: SLF001
                mock_subagent, execute_kwargs=ExecuteKwargs(stream=True)
            )

        assert isinstance(result_text, str)
        assert len(events) == 1
        # 没有传入 callback → 无心跳，不报错

    def test_heartbeat_once_per_sse_event(self) -> None:
        """每个解析后的 SSE 事件触发一次心跳。"""
        backend = LocalBackend()

        # 返回 4 个有效 SSE 事件 + 空行和 [DONE]
        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "RUN_STARTED"}',
            "",
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "X"}',
            'data: {"type": "TOOL_CALL_START", "tool_call_id": "t2"}',
            "data: [DONE]",
        ]

        mock_callback = MagicMock()
        with patch("aidev_agent.core.tools.a2a_tools.local_backend.logger"):
            backend._run_subagent(  # noqa: SLF001
                mock_subagent,
                execute_kwargs=ExecuteKwargs(stream=True),
                progress_callback=mock_callback,
            )

        heartbeat_calls = [call for call in mock_callback.call_args_list if call[0][0] == "subagent.heartbeat"]
        # 3 parsed events (empty line skipped), 1 heartbeat per event
        assert len(heartbeat_calls) == 3


# ============== Test: 多轮交互文本提取 ==============


class TestLocalBackendMultiTurnTextExtraction:
    """LocalBackend 多轮交互文本提取：仅保留最后一轮 TEXT_MESSAGE 文本。"""

    def test_multi_turn_only_returns_final_answer(self) -> None:
        """多轮交互（含 TOOL_CALL）仅返回最后一轮文本，不包含中间思考。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "RUN_STARTED"}',
            'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "让我分析一下..."}',
            'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
            'data: {"type": "TOOL_CALL_START", "toolCallId": "tc_1", "toolCallName": "analyze"}',
            'data: {"type": "TOOL_CALL_END", "toolCallId": "tc_1"}',
            'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_2"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "分析结果如下"}',
            'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_2"}',
            'data: {"type": "RUN_FINISHED"}',
            "data: [DONE]",
        ]

        result_text, events, _tool_count = backend._run_subagent(  # noqa: SLF001
            mock_subagent, execute_kwargs=ExecuteKwargs(stream=True)
        )

        assert result_text == "分析结果如下"
        assert "让我分析一下" not in result_text

    def test_single_turn_unchanged(self) -> None:
        """单轮交互（无 TOOL_CALL）行为与修改前一致。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "直接回答"}',
            'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
            'data: {"type": "RUN_FINISHED"}',
            "data: [DONE]",
        ]

        result_text, events, _tool_count = backend._run_subagent(  # noqa: SLF001
            mock_subagent, execute_kwargs=ExecuteKwargs(stream=True)
        )

        assert result_text == "直接回答"

    def test_tool_call_count_unaffected_by_text_message_start(self) -> None:
        """TEXT_MESSAGE_START 清空 text_parts 不影响 TOOL_CALL_START 统计。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "RUN_STARTED"}',
            'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "思考中..."}',
            'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
            'data: {"type": "TOOL_CALL_START", "toolCallId": "tc_1", "toolCallName": "analyze"}',
            'data: {"type": "TOOL_CALL_END", "toolCallId": "tc_1"}',
            'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_2"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "最终回答"}',
            'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_2"}',
            'data: {"type": "RUN_FINISHED"}',
            "data: [DONE]",
        ]

        result_text, events, tool_count = backend._run_subagent(  # noqa: SLF001
            mock_subagent, execute_kwargs=ExecuteKwargs(stream=True)
        )

        assert tool_count == 1

    def test_multi_turn_final_answer_across_deltas(self) -> None:
        """最终回答跨多个 TEXT_MESSAGE_CONTENT delta 时正确拼接。"""
        backend = LocalBackend()

        mock_subagent = MagicMock()
        mock_subagent.execute.return_value = [
            'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "思考中..."}',
            'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
            'data: {"type": "TOOL_CALL_START", "toolCallId": "tc_1", "toolCallName": "search"}',
            'data: {"type": "TOOL_CALL_END", "toolCallId": "tc_1"}',
            'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_2"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "分析"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "完成"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "结论"}',
            'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_2"}',
            'data: {"type": "RUN_FINISHED"}',
            "data: [DONE]",
        ]

        result_text, events, _tool_count = backend._run_subagent(  # noqa: SLF001
            mock_subagent, execute_kwargs=ExecuteKwargs(stream=True)
        )

        assert result_text == "分析完成结论"


# ============== Test: _extract_execute_kwargs state → sandbox_pv_id (D-15 unit) ==============


def _make_session_pv(volume_id: str, source: str = "runtime") -> dict[str, Any]:
    """构造 session 级 paas-sbx-pv dict。"""
    return {
        "type": "paas-sbx-pv",
        "volume_id": volume_id,
        "volume_name": f"agent-pv-{volume_id}",
        "mount_path": "session",
        "source": source,
    }


class TestExtractExecuteKwargsInjectsSandboxPvIdFromState:
    """D-15: LocalBackend._extract_execute_kwargs 从 state 读 session 级 PV 注入 sandbox_pv_id。"""

    def test_state_session_pv_sets_sandbox_pv_id(self) -> None:
        """state 含 session 级 PV 时，child sandbox_pv_id 设为该 volume_id。"""
        state = {"runtime_paas_sbx_pv": [_make_session_pv("vol-session-1")]}
        child_ek = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": ExecuteKwargs(sandbox_pv_id=None)}}, state=state
        )
        assert child_ek.sandbox_pv_id == "vol-session-1"

    def test_no_session_pv_leaves_none(self) -> None:
        """state 无 session 级 PV 时，child sandbox_pv_id 保持 None。"""
        child_ek = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": ExecuteKwargs(sandbox_pv_id=None)}},
            state={"runtime_paas_sbx_pv": [{"type": "other", "mount_path": "/data", "volume_id": "vol-x"}]},
        )
        assert child_ek.sandbox_pv_id is None

    def test_multiple_pvs_picks_first_session_pv(self) -> None:
        """state 含多条 PV 时，取第一条 session 级 paas-sbx-pv 的 volume_id。"""
        state = {
            "runtime_paas_sbx_pv": [
                {"type": "other", "volume_id": "vol-non-session", "mount_path": "/data"},
                _make_session_pv("vol-session-2"),
                _make_session_pv("vol-session-3"),
            ]
        }
        child_ek = extract_child_execute_kwargs({"configurable": {"execute_kwargs": ExecuteKwargs()}}, state=state)
        assert child_ek.sandbox_pv_id == "vol-session-2"

    def test_none_or_empty_state_no_crash(self) -> None:
        """state=None 或空 dict 时不崩溃，且不设置 sandbox_pv_id。"""
        for state in (None, {}):
            child_ek = extract_child_execute_kwargs({"configurable": {"execute_kwargs": ExecuteKwargs()}}, state=state)
            assert child_ek.sandbox_pv_id is None


class TestExtractExecuteKwargsThreadIdReset:
    """D-04: LocalBackend._extract_execute_kwargs 显式重置 thread_id 避免父子串扰。"""

    def test_thread_id_reset_from_parent(self) -> None:
        """父 execute_kwargs 含 thread_id 时，子对象 thread_id 被重置为 None。"""
        parent_ek = ExecuteKwargs(
            spawn_depth=0, max_spawn_depth=1, session_code="parent-sess", thread_id="parent_thread"
        )
        child_ek = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": parent_ek}}, session_code="sub-sess"
        )
        assert child_ek.thread_id is None

    def test_spawn_depth_and_spawned_by_preserved(self) -> None:
        """thread_id 重置不破坏 spawn_depth+1 / spawned_by 深度传播。"""
        parent_ek = ExecuteKwargs(spawn_depth=1, max_spawn_depth=5, session_code="parent-sess")
        child_ek = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": parent_ek}}, session_code="sub-sess"
        )
        assert child_ek.spawn_depth == 2
        assert child_ek.spawned_by == "parent-sess"
        assert child_ek.max_spawn_depth == 5


# ============== Test: state → sandbox_pv_id 端到端注入 (D-15) ==============


class TestExecuteInjectsSandboxPvIdFromState:
    """D-15: LocalBackend.execute 从 state 读 session 级 PV 注入子 execute_kwargs.sandbox_pv_id。"""

    def test_execute_injects_sandbox_pv_id_from_state(self) -> None:
        """state 含 session 级 PV 时，子 execute_kwargs.sandbox_pv_id 被正确注入。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        parent_ek = ExecuteKwargs(sandbox_pv_id=None, spawn_depth=0, max_spawn_depth=1)
        state = {"runtime_paas_sbx_pv": [_make_session_pv("vol-session-1")]}
        config = {"configurable": {"execute_kwargs": parent_ek}}
        backend.execute(spec, "hello", session_code="sess-pv", config=config, state=state)

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.sandbox_pv_id == "vol-session-1"

    def test_execute_no_pv_in_state_leaves_none(self) -> None:
        """state 无 PV 时，子 execute_kwargs.sandbox_pv_id 保持 None（子 Agent 自行回退）。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        parent_ek = ExecuteKwargs(sandbox_pv_id=None)
        backend.execute(
            spec, "hello", session_code="sess-pv", config={"configurable": {"execute_kwargs": parent_ek}}, state={}
        )

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.sandbox_pv_id is None

    def test_execute_picks_first_session_pv_from_multiple(self) -> None:
        """state 有多条 PV 时，取第一条 session 级 paas-sbx-pv 的 volume_id。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        # 非 session 级 PV 在前，session 级 PV 在后 → 应跳过非 session，选 session 第一条
        state = {
            "runtime_paas_sbx_pv": [
                {"type": "other", "volume_id": "vol-non-session", "mount_path": "/data"},
                _make_session_pv("vol-session-2"),
                _make_session_pv("vol-session-3"),
            ]
        }
        backend.execute(
            spec,
            "hello",
            session_code="sess-pv",
            config={"configurable": {"execute_kwargs": ExecuteKwargs()}},
            state=state,
        )

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek.sandbox_pv_id == "vol-session-2"

    def test_execute_injects_platform_source_pv_too(self) -> None:
        """D-11: state 中 source=platform 的 session 级 PV 同样被注入。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        state = {"runtime_paas_sbx_pv": [_make_session_pv("vol-platform-1", source="platform")]}
        backend.execute(
            spec,
            "hello",
            session_code="sess-pv",
            config={"configurable": {"execute_kwargs": ExecuteKwargs()}},
            state=state,
        )

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek.sandbox_pv_id == "vol-platform-1"


# ============== Test: extract_child_execute_kwargs invoke_timeout 注入 ==============


class TestExtractExecuteKwargsInjectsInvokeTimeout:
    """extract_child_execute_kwargs 的 invoke_timeout 参数注入测试。"""

    def test_invoke_timeout_set_when_provided(self) -> None:
        """传入 invoke_timeout 时写入 child execute_kwargs。"""
        child_ek = extract_child_execute_kwargs(None, session_code="sub-sess", invoke_timeout=120)
        assert child_ek.invoke_timeout == 120

    def test_invoke_timeout_not_set_when_none(self) -> None:
        """invoke_timeout 默认 None 时不修改 child execute_kwargs.invoke_timeout（保持 None）。"""
        child_ek = extract_child_execute_kwargs(None, session_code="sub-sess")
        assert child_ek.invoke_timeout is None

    def test_invoke_timeout_overrides_parent_value(self) -> None:
        """父 execute_kwargs.invoke_timeout 被 invoke_timeout 参数覆盖（LocalBackend 用 spec.timeout_seconds）。"""
        parent_ek = ExecuteKwargs(invoke_timeout=30, session_code="parent-sess")
        child_ek = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": parent_ek}},
            session_code="sub-sess",
            invoke_timeout=300,
        )
        assert child_ek.invoke_timeout == 300

    def test_invoke_timeout_inherits_parent_when_not_provided(self) -> None:
        """不传 invoke_timeout 时，从父 execute_kwargs 继承（model_copy 行为）。"""
        parent_ek = ExecuteKwargs(invoke_timeout=45, session_code="parent-sess")
        child_ek = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": parent_ek}}, session_code="sub-sess"
        )
        assert child_ek.invoke_timeout == 45


class TestExecuteInjectsInvokeTimeoutFromSpec:
    """LocalBackend.execute 把 spec.timeout_seconds 注入子 execute_kwargs.invoke_timeout。"""

    def test_execute_injects_spec_timeout_into_invoke_timeout(self) -> None:
        """spec.timeout_seconds 被注入到子 execute_kwargs.invoke_timeout。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx}, timeout_seconds=180)

        backend.execute(spec, "hello", session_code="sess-timeout")

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.invoke_timeout == 180

    def test_execute_uses_spec_timeout_over_parent_invoke_timeout(self) -> None:
        """父 execute_kwargs.invoke_timeout 被 spec.timeout_seconds 覆盖。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx}, timeout_seconds=90)

        parent_ek = ExecuteKwargs(invoke_timeout=999, session_code="parent-sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        backend.execute(spec, "hello", session_code="sess-timeout", config=config)

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.invoke_timeout == 90


# ============== Test: LocalBackend 从 spec.params 读 caller_bk_app_code ==============


class TestExecuteInjectsCallerBkAppCodeFromSpecParams:
    """LocalBackend.execute 从 spec.params 读 caller_bk_app_code 注入子 execute_kwargs。

    与 BkAiBackend 对齐：caller_bk_app_code 来源是 spec.params，不是 kwargs
    （provider 从不通过 kwargs 传该字段，从 kwargs 读会拿到空串）。
    """

    def test_execute_injects_caller_bk_app_code_from_spec_params(self) -> None:
        """spec.params["caller_bk_app_code"] 被注入到子 execute_kwargs.caller_bk_app_code。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx, "caller_bk_app_code": "bk-app-xyz"})

        backend.execute(spec, "hello", session_code="sess-caller")

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.caller_bk_app_code == "bk-app-xyz"

    def test_execute_no_caller_bk_app_code_in_spec_params_leaves_none(self) -> None:
        """spec.params 无 caller_bk_app_code 时，子 execute_kwargs.caller_bk_app_code 保持 None。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        backend.execute(spec, "hello", session_code="sess-caller")

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        assert child_ek.caller_bk_app_code is None

    def test_execute_ignores_caller_bk_app_code_in_kwargs(self) -> None:
        """kwargs 中的 caller_bk_app_code 被忽略（来源是 spec.params，不是 kwargs）。"""
        backend = LocalBackend()
        mock_child = _make_mock_child("result")
        mock_cls = _make_mock_agent_cls(mock_child)
        ctx = _FakeCtx()
        spec = _make_spec(params={"agent_cls": mock_cls, "ctx": ctx})

        # kwargs 中传 caller_bk_app_code，应被忽略
        backend.execute(spec, "hello", session_code="sess-caller", caller_bk_app_code="from-kwargs")

        call_args = mock_child.execute.call_args
        child_ek = call_args.args[0] if call_args.args else call_args.kwargs.get("execute_kwargs")
        assert child_ek is not None
        # kwargs 中的值不被使用，spec.params 无该字段 → 保持 None
        assert child_ek.caller_bk_app_code is None
