# -*- coding: utf-8 -*-
"""BkAiBackend 远程后端单元测试。

覆盖 BkAiBackend 的：
- 零参构造和 Protocol 满足性
- 缺失 client/agent_code/session_code 时的 ValueError
- execute 正常调用路径（通过 SSE 流式请求）
- 异常捕获返回 failed 字典
- 流式调用验证
- _prepare_session 方法
- caller_bk_app_code 传递
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.api.bk_agent import Client as BkAgentApiClient
from aidev_agent.core.tools.a2a_tools.bkai_backend import BkAiBackend
from aidev_agent.core.tools.a2a_tools.types import AgentBackend, AgentBackendType, AgentSpec
from aidev_agent.core.tools.a2a_tools.utils import extract_child_execute_kwargs
from aidev_agent.pydantic_models import ExecuteKwargs


def _make_mock_client() -> MagicMock:
    """创建 mock Client 实例（spec=BkAgentApiClient 以通过 isinstance 校验）。"""
    mock = MagicMock(spec=BkAgentApiClient)
    # 设置 chat_completion Operation 的 path 属性
    mock.private_chat_completion.path = "/bk_plugin/private/agent/chat_completion/"
    mock.openapi_chat_completion.path = "/bk_plugin/openapi/agent/chat_completion/"
    return mock


def _setup_stream_response(
    mock_client: MagicMock,
    lines: list[str],
) -> MagicMock:
    """配置 mock Client 的 chat_op.request 返回模拟 SSE 响应。

    Args:
        mock_client: mock Client 实例
        lines: SSE 行列表

    Returns:
        mock 响应对象
    """
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_lines.return_value = lines
    mock_client.private_chat_completion.request.return_value = mock_resp
    mock_client.openapi_chat_completion.request.return_value = mock_resp
    return mock_resp


def _make_bkai_spec(
    name: str = "test_agent",
    client: Any = None,
    **extra_params: Any,
) -> AgentSpec:
    """创建 BKAI 类型的 AgentSpec 测试辅助。"""
    params: dict[str, Any] = {}
    if client is not None:
        params["client"] = client
    params.update(extra_params)
    return AgentSpec(name=name, description="Test BKAI agent", backend_type=AgentBackendType.BKAI, params=params)


# ============== Test 1: 零参构造 ==============


class TestBkAiBackendInstantiate:
    """Test 1: BkAiBackend 类存在且零参构造成功。"""

    def test_bkai_backend_instantiate(self) -> None:
        backend = BkAiBackend()
        assert backend is not None


# ============== Test 2: AgentBackend Protocol ==============


class TestBkAiBackendSatisfiesProtocol:
    """Test 2: BkAiBackend 满足 AgentBackend Protocol (isinstance 检查)。"""

    def test_bkai_backend_satisfies_protocol(self) -> None:
        backend = BkAiBackend()
        assert isinstance(backend, AgentBackend)


# ============== Test 3: 缺失 client ==============


class TestBkAiBackendMissingClient:
    """Test 3: execute() 缺少 client 时抛出 ValueError。"""

    def test_missing_client_raises_value_error(self) -> None:
        backend = BkAiBackend()
        spec_no_client = AgentSpec(
            name="test_agent",
            description="Test",
            backend_type=AgentBackendType.BKAI,
            params={},
        )

        with pytest.raises(ValueError, match="Missing 'client' in spec.params"):
            backend.execute(spec_no_client, "hello", session_code="sess_test")

    def test_missing_session_code_raises_value_error(self) -> None:
        """execute() 缺少 session_code 时抛出 ValueError。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        spec = _make_bkai_spec(client=mock_client)

        with pytest.raises(ValueError, match="session_code must not be empty for BkAiBackend"):
            backend.execute(spec, "hello")


# ============== Test 4: 无效 client 类型 ==============


class TestBkAiBackendInvalidClientType:
    """Test 4: execute() 中 client 非 BkAgentApiClient 实例时抛出 ValueError。"""

    def test_invalid_client_dict_raises_value_error(self) -> None:
        """client 为 dict（非 BkAgentApiClient）时抛出 ValueError。"""
        backend = BkAiBackend()
        spec = _make_bkai_spec(client={"not": "a real client"})

        with pytest.raises(ValueError, match="Invalid 'client' in spec.params"):
            backend.execute(spec, "hello", session_code="sess_test")

    def test_invalid_client_str_raises_value_error(self) -> None:
        """client 为 str（非 BkAgentApiClient）时抛出 ValueError。"""
        backend = BkAiBackend()
        spec = _make_bkai_spec(client="not_a_client")

        with pytest.raises(ValueError, match="Invalid 'client' in spec.params"):
            backend.execute(spec, "hello", session_code="sess_test")

    def test_invalid_client_object_raises_value_error(self) -> None:
        """client 为任意对象（非 BkAgentApiClient）时抛出 ValueError。"""
        backend = BkAiBackend()

        class DummyClient:
            pass

        spec = _make_bkai_spec(client=DummyClient())

        with pytest.raises(ValueError, match="Invalid 'client' in spec.params"):
            backend.execute(spec, "hello", session_code="sess_test")

    def test_invalid_client_error_includes_agent_name(self) -> None:
        """错误消息包含 agent 名和实际类型名。"""
        backend = BkAiBackend()
        spec = _make_bkai_spec(name="my_agent", client=123)

        with pytest.raises(ValueError, match="my_agent") as exc_info:
            backend.execute(spec, "hello", session_code="sess_test")

        assert "BkAgentApiClient" in str(exc_info.value)
        assert "int" in str(exc_info.value)

    def test_invalid_client_error_includes_type_name(self) -> None:
        """错误消息包含实际 client 的类型名。"""
        backend = BkAiBackend()

        class CustomType:
            pass

        spec = _make_bkai_spec(client=CustomType())

        with pytest.raises(ValueError, match="CustomType"):
            backend.execute(spec, "hello", session_code="sess_test")


# ============== Test 5: execute 通过流式请求正常调用 ==============


class TestBkAiBackendExecuteSuccess:
    """Test 5: execute() 通过 SSE 流式请求正常调用并返回 completed。"""

    def test_execute_success_returns_completed(self) -> None:
        """execute() 流式请求返回 completed，result_text 来自 TEXT_MESSAGE_CONTENT 事件。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "子 Agent 返回的文本"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        result = backend.execute(spec, "请分析这段代码", session_code="sess_test")

        assert result.status == "completed"
        assert result.result == "子 Agent 返回的文本"

    def test_execute_calls_chat_op_request_with_payload(self) -> None:
        """execute() 通过 chat_op.request 发送流式请求，payload 包含 input 和 session_code。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "result"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        backend.execute(spec, "hello", session_code="sess_test")

        # 验证 chat_op.request 被调用
        mock_client.private_chat_completion.request.assert_called_once()
        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        assert payload.get("input") == "hello"
        assert payload.get("session_code") == "sess_test"

    def test_execute_payload_stream_true_and_persist_input(self) -> None:
        """execute() 请求体中 execute_kwargs.stream 为 True 且 persist_input 为 True。"""

        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        backend.execute(spec, "hello", session_code="sess_test")

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        assert payload.get("execute_kwargs", {}).get("stream") is True
        assert payload.get("execute_kwargs", {}).get("persist_input") is True
        assert payload.get("input") == "hello"
        assert payload.get("session_code") == "sess_test"

    def test_execute_counts_tool_calls(self) -> None:
        """execute() 统计 TOOL_CALL_START 事件数为 tool_calls。"""

        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TOOL_CALL_START", "tool_call_id": "t1"}',
                'data: {"type": "TOOL_CALL_START", "tool_call_id": "t2"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "done"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        result = backend.execute(spec, "hello", session_code="sess_test")

        assert result.status == "completed"
        assert result.tool_calls == 2

    def test_execute_concatenates_multiple_text_deltas(self) -> None:
        """execute() 拼接多个 TEXT_MESSAGE_CONTENT 事件的 delta。"""

        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello "}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "World"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        result = backend.execute(spec, "hello", session_code="sess_test")

        assert result.result == "Hello World"


# ============== Test 6: 异常捕获 ==============


class TestBkAiBackendExecuteException:
    """Test 6: execute() SSE 流式请求异常时直接向上抛出（由 ToolNode 统一处理）。"""

    def test_stream_error_event_raises(self) -> None:
        """SSE 事件包含 type="error" 时，execute() 抛 RuntimeError。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "error", "error": "Remote agent error"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        with pytest.raises(RuntimeError, match="Remote agent error"):
            backend.execute(spec, "hello", session_code="sess_test")

    def test_http_exception_raises(self) -> None:
        """HTTP 连接异常时，execute() 抛 ConnectionError。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        mock_client.private_chat_completion.request.side_effect = ConnectionError("网络连接失败")

        spec = _make_bkai_spec(client=mock_client)

        with pytest.raises(ConnectionError, match="网络连接失败"):
            backend.execute(spec, "hello", session_code="sess_test")

    def test_exception_propagates_to_caller(self) -> None:
        """内部异常直接向上抛出，由 ToolNode 的 default_tool_call_handler 统一处理。"""

        backend = BkAiBackend()
        mock_client = _make_mock_client()
        mock_client.private_chat_completion.request.side_effect = Exception("unexpected")

        spec = _make_bkai_spec(client=mock_client)

        with pytest.raises(Exception, match="unexpected"):
            backend.execute(spec, "hello", session_code="sess_test")


# ============== Test: execute 委托关系 ==============


class TestBkAiBackendExecute:
    """execute() 方法测试：统一处理 task 和 member 模式。"""

    def test_execute_success(self) -> None:
        """execute() 正常返回 completed。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "chat result"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        result = backend.execute(spec, "hello", session_code="sess_test")

        assert result.status == "completed"
        assert result.result == "chat result"

    def test_execute_uses_stream_via_chat_op_request(self) -> None:
        """execute() 通过 chat_op.request 发送流式请求。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "direct result"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        result = backend.execute(spec, "hello", session_code="sess_test")

        assert result.status == "completed"
        assert result.result == "direct result"
        # 验证通过 chat_op.request 发送请求
        mock_client.private_chat_completion.request.assert_called_once()


# ============== Test: _prepare_session 方法 ==============


class TestBkAiBackendPrepareSession:
    """_prepare_session() 方法单元测试。"""

    def test_prepare_session_calls_client_create_and_save(self) -> None:
        """_prepare_session() 调用 client.create_session + client.save_session_content。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()

        backend._prepare_session(mock_client, "sess_abc", "test-session", "hello")  # noqa: SLF001

        mock_client.create_session.assert_called_once_with(
            data={"is_temporary": False, "session_code": "sess_abc", "session_name": "test-session"},
            headers={"X-BKAIDEV-USER": ""},
        )
        mock_client.save_session_content.assert_called_once_with(
            data={"session_code": "sess_abc", "role": "user", "content": "hello"}
        )

    def test_prepare_session_create_exception_logged(self) -> None:
        """_prepare_session() create_session 异常时记录日志但不抛出。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        mock_client.create_session.side_effect = Exception("HTTP 503")

        # 不应抛出异常
        backend._prepare_session(mock_client, "sess_abc", "test-session", "hello")  # noqa: SLF001

        mock_client.save_session_content.assert_called_once()

    def test_prepare_session_save_exception_logged(self) -> None:
        """_prepare_session() save_session_content 异常时记录日志但不抛出。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        mock_client.save_session_content.side_effect = Exception("HTTP 500")

        # 不应抛出异常
        backend._prepare_session(mock_client, "sess_abc", "test-session", "hello")  # noqa: SLF001

        mock_client.create_session.assert_called_once()

    def test_prepare_session_default_executor(self) -> None:
        """_prepare_session() 不传 executor 时仍然正常调用 client API。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()

        backend._prepare_session(mock_client, "sess_abc", "test-session", "hello")  # noqa: SLF001

        mock_client.create_session.assert_called_once_with(
            data={"is_temporary": False, "session_code": "sess_abc", "session_name": "test-session"},
            headers={"X-BKAIDEV-USER": ""},
        )
        mock_client.save_session_content.assert_called_once_with(
            data={"session_code": "sess_abc", "role": "user", "content": "hello"}
        )


# ============== Test: execute member 模式增强 ==============


class TestBkAiBackendExecuteMemberMode:
    """execute() member 模式增强测试（session_code 非空，should_prepare_session=True）。"""

    def test_execute_with_should_prepare_session_calls_prepare(self) -> None:
        """should_prepare_session=True 时调用 _prepare_session 准备远端 session。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "result"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client, should_prepare_session=True)

        with patch.object(backend, "_prepare_session") as mock_prepare:
            backend.execute(spec, "hello user", session_code="sess_123")

        mock_prepare.assert_called_once()

    def test_execute_without_should_prepare_session_skips_prepare(self) -> None:
        """should_prepare_session=False（默认）时不调用 _prepare_session。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)

        with patch.object(backend, "_prepare_session") as mock_prepare:
            result = backend.execute(spec, "hello", session_code="sess_456")

        assert result.status == "completed"
        mock_prepare.assert_not_called()

    def test_execute_result_contains_text(self) -> None:
        """execute() 返回结果中包含流式文本。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "assistant reply"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client, should_prepare_session=True)

        with patch.object(backend, "_prepare_session"):
            result = backend.execute(spec, "hello", session_code="sess_123")

        assert result.status == "completed"
        assert result.result == "assistant reply"


# ============== Test: _extract_execute_kwargs ==============


class TestBkAiBackendExtractExecuteKwargs:
    """_extract_execute_kwargs() 辅助方法测试。"""

    def test_extract_execute_kwargs_with_execute_kwargs_object(self) -> None:
        """_extract_execute_kwargs() 从 config 中的 ExecuteKwargs Pydantic 对象构造子对象。"""

        ek = ExecuteKwargs(executor="user1", session_code="sess_abc", caller_bk_app_code="app_123")
        config = {"configurable": {"execute_kwargs": ek}}

        result = extract_child_execute_kwargs(
            config, session_code="sub_sess", stream=True, caller_bk_app_code="caller_app"
        )

        assert result.stream is True
        assert result.persist_input is True
        assert result.session_code == "sub_sess"
        # caller_bk_app_code 通过参数传入，覆盖原始 ExecuteKwargs 中的值
        assert result.caller_bk_app_code == "caller_app"
        # executor 从原始 ExecuteKwargs 继承
        assert result.executor == "user1"

    def test_extract_execute_kwargs_spawn_depth_increments(self) -> None:
        """_extract_execute_kwargs() 递增 spawn_depth 并记录 spawned_by（CR #1 Bkai 路径修复）。"""

        ek = ExecuteKwargs(executor="user1", session_code="parent_sess", spawn_depth=2)
        config = {"configurable": {"execute_kwargs": ek}}

        result = extract_child_execute_kwargs(config, session_code="sub_sess")

        assert result.spawn_depth == 3
        assert result.spawned_by == "parent_sess"

    def test_extract_execute_kwargs_thread_id_reset(self) -> None:
        """_extract_execute_kwargs() 显式重置 thread_id，避免父子会话串扰（D-04）。"""

        ek = ExecuteKwargs(executor="user1", session_code="parent_sess", thread_id="parent_thread")
        config = {"configurable": {"execute_kwargs": ek}}

        result = extract_child_execute_kwargs(config, session_code="sub_sess")

        assert result.thread_id is None

    def test_extract_execute_kwargs_no_config(self) -> None:
        """_extract_execute_kwargs() 无 config 时只设置覆盖字段。"""

        result = extract_child_execute_kwargs(None, session_code="sub_sess")

        assert result.stream is True
        assert result.persist_input is True
        assert result.session_code == "sub_sess"

    def test_extract_execute_kwargs_non_execute_kwargs_object_ignored(self) -> None:
        """_extract_execute_kwargs() config 中的 execute_kwargs 非 ExecuteKwargs 实例时忽略。"""

        # 非 ExecuteKwargs 对象（如 dict）不会被使用
        config = {"configurable": {"execute_kwargs": {"executor": "user1"}}}

        result = extract_child_execute_kwargs(config, session_code="sub_sess")

        # 只包含覆盖字段，原始 execute_kwargs 被忽略
        assert result.stream is True
        assert result.persist_input is True
        assert result.session_code == "sub_sess"
        assert result.executor is None

    def test_extract_execute_kwargs_caller_bk_app_code(self) -> None:
        """_extract_execute_kwargs() 将 caller_bk_app_code 参数写入 execute_kwargs。"""

        result = extract_child_execute_kwargs(None, session_code="sub_sess", caller_bk_app_code="my_app_code")

        assert result.caller_bk_app_code == "my_app_code"

    def test_extract_execute_kwargs_no_caller_bk_app_code(self) -> None:
        """_extract_execute_kwargs() 无 caller_bk_app_code 时不设置该字段。"""

        result = extract_child_execute_kwargs(None, session_code="sub_sess")

        assert result.caller_bk_app_code is None

    def test_extract_execute_kwargs_increments_spawn_depth_e2e(self) -> None:
        """D-08：Bkai 子 ExecuteKwargs spawn_depth+1、spawned_by 正确（修复 CR #1 Bkai 路径缺失）。"""
        parent_ek = ExecuteKwargs(spawn_depth=1, max_spawn_depth=3, session_code="parent_sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        child = extract_child_execute_kwargs(config, state=None, session_code="child_sess", caller_bk_app_code="app")
        assert isinstance(child, ExecuteKwargs)
        assert child.spawn_depth == 2
        assert child.spawned_by == "parent_sess"
        assert child.max_spawn_depth == 3

    def test_extract_execute_kwargs_resets_thread_id_e2e(self) -> None:
        """D-04：Bkai 子 execute_kwargs.thread_id 为 None，不继承父。"""
        parent_ek = ExecuteKwargs(spawn_depth=0, max_spawn_depth=2, session_code="p", thread_id="parent-thread-1")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        child = extract_child_execute_kwargs(config, state=None, session_code="child_sess", caller_bk_app_code="")
        assert isinstance(child, ExecuteKwargs)
        assert child.thread_id is None


# ============== Test: Client 从 spec.params 注入 ==============


class TestBkAiBackendClientInjection:
    """BkAiBackend 从 spec.params["client"] 获取 Client，不负责构造。"""

    def test_execute_uses_injected_client(self) -> None:
        """execute() 使用注入的 Client。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)
        result = backend.execute(spec, "hello", session_code="sess_test")

        assert result.status == "completed"
        mock_client.private_chat_completion.request.assert_called_once()


# ============== Test 17: BkAiBackend 心跳发送 ==============


class TestBkAiBackendHeartbeat:
    """Test 17: 流式方法中发送 subagent.heartbeat 事件（D-04）。"""

    def test_heartbeat_events_sent_with_callback(self) -> None:
        """当提供 progress_callback 时，_run_subagent 发送心跳。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()

        # 模拟 HTTP 响应的 iter_lines
        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"}',
            'data: {"type": "TOOL_CALL_START", "tool_call_id": "t1"}',
            "data: [DONE]",
        ]
        mock_client.private_chat_completion.request.return_value = mock_resp

        spec = _make_bkai_spec(client=mock_client)
        mock_callback = MagicMock()

        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.logger"):
            _, events, _tool_count = backend._run_subagent(  # noqa: SLF001
                mock_client,
                spec,
                "hello",
                execute_kwargs=ExecuteKwargs(),
                progress_callback=mock_callback,
            )

        assert len(events) == 2  # DONE is not yielded

        heartbeat_calls = [call for call in mock_callback.call_args_list if call[0][0] == "subagent.heartbeat"]
        assert len(heartbeat_calls) == 2

        first_kwargs = heartbeat_calls[0][1]
        assert "elapsed_seconds" in first_kwargs
        assert "tool_count" in first_kwargs
        assert "iteration" in first_kwargs

    def test_no_heartbeat_when_callback_none(self) -> None:
        """当 progress_callback 为 None 时，无心跳事件。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()

        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Hello"}',
            "data: [DONE]",
        ]
        mock_client.private_chat_completion.request.return_value = mock_resp

        spec = _make_bkai_spec(client=mock_client)

        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.logger"):
            _, events, _tool_count = backend._run_subagent(  # noqa: SLF001
                mock_client,
                spec,
                "hello",
                execute_kwargs=ExecuteKwargs(),
            )

        assert len(events) == 1
        # 无 callback → 无心跳，不报错

    def test_heartbeat_once_per_sse_event(self) -> None:
        """每个解析的 SSE 事件触发一次心跳。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()

        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            'data: {"type": "RUN_STARTED"}',
            "",
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "X"}',
            'data: {"type": "TOOL_CALL_START", "tool_call_id": "t2"}',
            "data: [DONE]",
        ]
        mock_client.private_chat_completion.request.return_value = mock_resp

        spec = _make_bkai_spec(client=mock_client)
        mock_callback = MagicMock()

        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.logger"):
            backend._run_subagent(  # noqa: SLF001
                mock_client,
                spec,
                "hello",
                execute_kwargs=ExecuteKwargs(),
                progress_callback=mock_callback,
            )

        heartbeat_calls = [call for call in mock_callback.call_args_list if call[0][0] == "subagent.heartbeat"]
        # 3 parsed events (empty line skipped) → 3 heartbeats
        assert len(heartbeat_calls) == 3

    def test_heartbeat_includes_tool_count(self) -> None:
        """心跳中的 tool_count 正确反映 TOOL_CALL_START 事件数。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()

        mock_resp = MagicMock()
        mock_resp.iter_lines.return_value = [
            'data: {"type": "TOOL_CALL_START", "tool_call_id": "t_a"}',
            'data: {"type": "TOOL_CALL_START", "tool_call_id": "t_b"}',
            'data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "Done"}',
            "data: [DONE]",
        ]
        mock_client.private_chat_completion.request.return_value = mock_resp

        spec = _make_bkai_spec(client=mock_client)
        mock_callback = MagicMock()

        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.logger"):
            backend._run_subagent(  # noqa: SLF001
                mock_client,
                spec,
                "hello",
                execute_kwargs=ExecuteKwargs(),
                progress_callback=mock_callback,
            )

        heartbeat_calls = [call for call in mock_callback.call_args_list if call[0][0] == "subagent.heartbeat"]
        # 最后一条心跳的 tool_count 应为 2
        last_kwargs = heartbeat_calls[-1][1]
        assert last_kwargs["tool_count"] == 2
        assert last_kwargs["iteration"] == 3


# ============== Test: 多轮交互文本提取 ==============


class TestBkAiBackendMultiTurnTextExtraction:
    """BkAiBackend 多轮交互文本提取：仅保留最后一轮 TEXT_MESSAGE 文本。"""

    def test_multi_turn_only_returns_final_answer(self) -> None:
        """多轮交互（含 TOOL_CALL）仅返回最后一轮文本，不包含中间思考。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "RUN_STARTED"}',
                'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "让我查一下天气信息..."}',
                'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
                'data: {"type": "TOOL_CALL_START", "toolCallId": "tc_1", "toolCallName": "get_weather"}',
                'data: {"type": "TOOL_CALL_ARGS", "toolCallId": "tc_1", "delta": "{\\"location\\": \\"广州\\"}"}',
                'data: {"type": "TOOL_CALL_END", "toolCallId": "tc_1"}',
                'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_2"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "广州今天多云，温度25度。"}',
                'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_2"}',
                'data: {"type": "RUN_FINISHED"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)
        result = backend.execute(spec, "广州天气", session_code="sess_test")

        assert "广州今天多云" in result.result
        assert "让我查一下" not in result.result

    def test_single_turn_unchanged(self) -> None:
        """单轮交互（无 TOOL_CALL）行为与修改前一致。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "直接回答"}',
                'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
                'data: {"type": "RUN_FINISHED"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)
        result = backend.execute(spec, "hello", session_code="sess_test")

        assert result.result == "直接回答"

    def test_tool_call_count_unaffected_by_text_message_start(self) -> None:
        """TEXT_MESSAGE_START 清空 text_parts 不影响 TOOL_CALL_START 统计。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "RUN_STARTED"}',
                'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "思考中..."}',
                'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
                'data: {"type": "TOOL_CALL_START", "toolCallId": "tc_1", "toolCallName": "search"}',
                'data: {"type": "TOOL_CALL_END", "toolCallId": "tc_1"}',
                'data: {"type": "TOOL_CALL_START", "toolCallId": "tc_2", "toolCallName": "lookup"}',
                'data: {"type": "TOOL_CALL_END", "toolCallId": "tc_2"}',
                'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_2"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "最终回答"}',
                'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_2"}',
                'data: {"type": "RUN_FINISHED"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)
        result = backend.execute(spec, "hello", session_code="sess_test")

        assert result.tool_calls == 2

    def test_multi_turn_final_answer_across_deltas(self) -> None:
        """最终回答跨多个 TEXT_MESSAGE_CONTENT delta 时正确拼接。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(
            mock_client,
            [
                'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_1"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_1", "delta": "思考中..."}',
                'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_1"}',
                'data: {"type": "TOOL_CALL_START", "toolCallId": "tc_1", "toolCallName": "search"}',
                'data: {"type": "TOOL_CALL_END", "toolCallId": "tc_1"}',
                'data: {"type": "TEXT_MESSAGE_START", "messageId": "msg_2"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "广州"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "今天"}',
                'data: {"type": "TEXT_MESSAGE_CONTENT", "messageId": "msg_2", "delta": "多云"}',
                'data: {"type": "TEXT_MESSAGE_END", "messageId": "msg_2"}',
                'data: {"type": "RUN_FINISHED"}',
                "data: [DONE]",
            ],
        )

        spec = _make_bkai_spec(client=mock_client)
        result = backend.execute(spec, "广州天气", session_code="sess_test")

        assert result.result == "广州今天多云"


# ============== Test: _get_verify_ssl 环境判断 ==============


class TestGetVerifySsl:
    """BkAiBackend._get_verify_ssl() 根据 settings.BKPAAS_ENVIRONMENT 判断（D-01/D-02）。"""

    def test_dev_environment_returns_false(self) -> None:
        """dev 环境返回 False。"""
        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.settings") as mock_settings:
            mock_settings.BKPAAS_ENVIRONMENT = "dev"
            assert BkAiBackend._get_verify_ssl() is False

    def test_development_environment_returns_false(self) -> None:
        """development 环境返回 False。"""
        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.settings") as mock_settings:
            mock_settings.BKPAAS_ENVIRONMENT = "development"
            assert BkAiBackend._get_verify_ssl() is False

    def test_prod_environment_returns_true(self) -> None:
        """生产环境返回 True。"""
        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.settings") as mock_settings:
            mock_settings.BKPAAS_ENVIRONMENT = "prod"
            assert BkAiBackend._get_verify_ssl() is True

    def test_stag_environment_returns_true(self) -> None:
        """stag 环境返回 True。"""
        with patch("aidev_agent.core.tools.a2a_tools.bkai_backend.settings") as mock_settings:
            mock_settings.BKPAAS_ENVIRONMENT = "stag"
            assert BkAiBackend._get_verify_ssl() is True


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
    """D-15: BkAiBackend._extract_execute_kwargs 从 state 读 session 级 PV 注入 sandbox_pv_id。"""

    def test_state_session_pv_sets_sandbox_pv_id(self) -> None:
        """state 含 session 级 PV 时，child dict sandbox_pv_id 设为该 volume_id。"""
        state = {"runtime_paas_sbx_pv": [_make_session_pv("vol-session-1")]}
        child_ek = extract_child_execute_kwargs(
            {"configurable": {"execute_kwargs": ExecuteKwargs(sandbox_pv_id=None)}}, state=state
        )
        assert child_ek.sandbox_pv_id == "vol-session-1"

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

    def test_none_state_no_sandbox_pv_id(self) -> None:
        """state=None 时不崩溃，且 sandbox_pv_id 不在结果中（或为 None）。"""
        child_ek = extract_child_execute_kwargs({"configurable": {"execute_kwargs": ExecuteKwargs()}}, state=None)
        assert child_ek.sandbox_pv_id is None


# ============== Test: state → sandbox_pv_id 端到端注入 (D-15) ==============


class TestExecuteInjectsSandboxPvIdFromState:
    """D-15: BkAiBackend.execute 从 state 读 session 级 PV 注入 payload["execute_kwargs"]["sandbox_pv_id"]。"""

    @pytest.mark.xfail(
        reason="bkai_backend.execute 暂时关闭 sandbox_pv_id 注入（line 107 置 None），等 PaaS 沙箱支持后开启",
        strict=True,
    )
    def test_execute_injects_sandbox_pv_id_from_state(self) -> None:
        """state 含 session 级 PV 时，payload execute_kwargs.sandbox_pv_id 被正确注入。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)

        state = {"runtime_paas_sbx_pv": [_make_session_pv("vol-bkai-1")]}
        backend.execute(spec, "hello", session_code="sess_test", state=state)

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        assert payload.get("execute_kwargs", {}).get("sandbox_pv_id") == "vol-bkai-1"

    def test_execute_no_pv_in_state_no_sandbox_pv_id(self) -> None:
        """state 无 PV 时，payload execute_kwargs 不含 sandbox_pv_id（或为 None，子 Agent 回退）。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)

        backend.execute(spec, "hello", session_code="sess_test", state={})

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        assert payload.get("execute_kwargs", {}).get("sandbox_pv_id") is None

    @pytest.mark.xfail(
        reason="bkai_backend.execute 暂时关闭 sandbox_pv_id 注入（line 107 置 None），等 PaaS 沙箱支持后开启",
        strict=True,
    )
    def test_execute_picks_first_session_pv_from_multiple(self) -> None:
        """state 有多条 PV 时，取第一条 session 级 paas-sbx-pv 的 volume_id。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)

        state = {
            "runtime_paas_sbx_pv": [
                {"type": "other", "volume_id": "vol-non-session", "mount_path": "/data"},
                _make_session_pv("vol-bkai-2"),
                _make_session_pv("vol-bkai-3"),
            ]
        }
        backend.execute(spec, "hello", session_code="sess_test", state=state)

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        assert payload.get("execute_kwargs", {}).get("sandbox_pv_id") == "vol-bkai-2"

    @pytest.mark.xfail(
        reason="bkai_backend.execute 暂时关闭 sandbox_pv_id 注入（line 107 置 None），等 PaaS 沙箱支持后开启",
        strict=True,
    )
    def test_execute_injects_platform_source_pv_too(self) -> None:
        """D-11: state 中 source=platform 的 session 级 PV 同样被注入。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)

        state = {"runtime_paas_sbx_pv": [_make_session_pv("vol-bkai-platform", source="platform")]}
        backend.execute(spec, "hello", session_code="sess_test", state=state)

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        assert payload.get("execute_kwargs", {}).get("sandbox_pv_id") == "vol-bkai-platform"


# ============== Test: BkAiBackend 不注入 invoke_timeout（超时由 HTTP 层控制）==============


class TestBkAiBackendDoesNotInjectInvokeTimeout:
    """BkAiBackend 不向 extract_child_execute_kwargs 传 invoke_timeout，超时由 HTTP 层 spec.timeout_seconds 控制。"""

    def test_bkai_does_not_set_invoke_timeout_when_parent_none(self) -> None:
        """父 execute_kwargs 无 invoke_timeout 时，BkAi 路径保持 None（不读 spec.timeout_seconds）。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)
        spec.timeout_seconds = 120

        backend.execute(spec, "hello", session_code="sess_test")

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        # BkAi 不传 invoke_timeout，子 execute_kwargs.invoke_timeout 保持 None
        assert payload.get("execute_kwargs", {}).get("invoke_timeout") is None
        # HTTP 层超时由 spec.timeout_seconds 控制（requests timeout 参数）
        assert request_call_kwargs.kwargs.get("timeout") == 120

    def test_bkai_inherits_parent_invoke_timeout(self) -> None:
        """父 execute_kwargs.invoke_timeout 通过 model_copy 继承（BkAi 不覆盖）。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)
        spec.timeout_seconds = 60

        parent_ek = ExecuteKwargs(invoke_timeout=45, session_code="parent-sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        backend.execute(spec, "hello", session_code="sess_test", config=config)

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        # 继承自父，不被 spec.timeout_seconds 覆盖
        assert payload.get("execute_kwargs", {}).get("invoke_timeout") == 45


# ============== Test: BkAiBackend.execute config 显式参数 ==============


class TestBkAiBackendExecuteAcceptsConfigExplicitly:
    """BkAiBackend.execute 接受 config 作为显式关键字参数（与 LocalBackend 签名对齐）。"""

    def test_execute_accepts_config_as_explicit_kwarg(self) -> None:
        """config 作为显式关键字参数传入，从中提取 execute_kwargs。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)

        parent_ek = ExecuteKwargs(executor="user1", session_code="parent-sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        backend.execute(spec, "hello", session_code="sess_test", config=config)

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        # config 中的 execute_kwargs 被正确提取并继承到子 payload
        assert payload.get("execute_kwargs", {}).get("executor") == "user1"

    def test_execute_config_none_uses_default_execute_kwargs(self) -> None:
        """config=None 时使用默认 ExecuteKwargs（不抛错）。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)

        # 不传 config（默认 None），应正常执行
        result = backend.execute(spec, "hello", session_code="sess_test")
        assert result.status == "completed"

    def test_execute_config_passed_positionally_via_kwargs_still_works(self) -> None:
        """通过 **kwargs 传 config=config 仍然工作（向后兼容 provider 调用方式）。"""
        backend = BkAiBackend()
        mock_client = _make_mock_client()
        _setup_stream_response(mock_client, ['data: {"type": "TEXT_MESSAGE_CONTENT", "delta": "ok"}', "data: [DONE]"])
        spec = _make_bkai_spec(client=mock_client)

        parent_ek = ExecuteKwargs(executor="user2", session_code="parent-sess")
        config = {"configurable": {"execute_kwargs": parent_ek}}
        # 模拟 provider 的调用方式：config 通过关键字传入
        backend.execute(spec, "hello", session_code="sess_test", config=config, state={})

        request_call_kwargs = mock_client.private_chat_completion.request.call_args
        payload = request_call_kwargs.kwargs.get("json", {})
        assert payload.get("execute_kwargs", {}).get("executor") == "user2"
