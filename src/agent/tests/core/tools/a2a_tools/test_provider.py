# -*- coding: utf-8 -*-
"""A2A Agent Provider 层单元测试。

覆盖：
- AgentBackendResolver 的注册/解析/链式调用/错误处理
- get_agent_tools 在 member/task 模式下的工具生成
- BkAiBackend 和 LocalBackend 可通过 AgentBackendResolver 注册和解析
- TeamPromptMiddleware 的 sendMessages 引导注入
- AgentResult 后端返回值的序列化
- SubAgentConfig.to_agent_spec() 转换和向后兼容导入
- _check_interrupt / _extract_progress_callback 辅助函数
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from aidev_agent.core.graphs.react.team_middleware import TeamPromptMiddleware
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext, PromptSlots
from aidev_agent.core.tools.a2a_tools.bkai_backend import BkAiBackend
from aidev_agent.core.tools.a2a_tools.local_backend import LocalBackend
from aidev_agent.core.tools.a2a_tools.provider import (
    AgentBackendResolver,
    _check_interrupt,
    _extract_progress_callback,
    get_agent_tools,
)
from aidev_agent.core.tools.a2a_tools.types import (
    AgentBackend,
    AgentBackendType,
    AgentResult,
    AgentSpec,
    SubAgentConfig,
)
from aidev_agent.pydantic_models import ExecuteKwargs


def _make_spec(
    name: str = "test_agent",
    agent_code: str = "test_001",
) -> AgentSpec:
    """创建 AgentSpec 测试辅助。"""
    return AgentSpec(
        name=name,
        description=f"Test agent {name}",
        backend_type=AgentBackendType.BKAI,
        params={"agent_code": agent_code},
    )


def _make_bkai_spec(name: str = "test-bkai", agent_code: str = "test_agent", **extra_params: Any) -> AgentSpec:
    """创建 BKAI 类型的 AgentSpec。"""
    params = {"agent_code": agent_code, **extra_params}
    return AgentSpec(name=name, description="test", backend_type=AgentBackendType.BKAI, params=params)


def _make_local_spec(name: str = "test-local", builder: Any = None, **extra_params: Any) -> AgentSpec:
    """创建 LOCAL 类型的 AgentSpec。"""
    params = {"builder": builder, **extra_params}
    return AgentSpec(name=name, description="test", backend_type=AgentBackendType.LOCAL, params=params)


def _make_resolver() -> AgentBackendResolver:
    """创建注册了 BkAiBackend 的 resolver。"""
    resolver = AgentBackendResolver()
    resolver.register("bkai", BkAiBackend)
    return resolver


# ============== 双后端注册与集成接线测试 ==============


class TestBkAiBackendResolve:
    """AgentBackendResolver 注册 "bkai" 后，resolve(bkai_spec) 返回 BkAiBackend 实例。"""

    def test_resolve_bkai_returns_bkai_backend(self) -> None:
        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend)

        spec = _make_bkai_spec()
        backend = resolver.resolve(spec)

        assert isinstance(backend, BkAiBackend)

    def test_resolve_bkai_returns_fresh_instance(self) -> None:
        """每次 resolve 都应返回新实例。"""
        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend)

        spec = _make_bkai_spec()
        backend1 = resolver.resolve(spec)
        backend2 = resolver.resolve(spec)

        assert backend1 is not backend2


class TestLocalBackendResolve:
    """AgentBackendResolver 注册 "local" 后，resolve(local_spec) 返回 LocalBackend 实例。"""

    def test_resolve_local_returns_local_backend(self) -> None:
        resolver = AgentBackendResolver()
        resolver.register("local", LocalBackend)

        spec = _make_local_spec()
        backend = resolver.resolve(spec)

        assert isinstance(backend, LocalBackend)


class TestDualBackendRouting:
    """两个后端同时注册后，resolve 可正确路由不同 backend_type。"""

    def test_dual_registration_routes_correctly(self) -> None:
        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend).register("local", LocalBackend)

        bkai_spec = _make_bkai_spec()
        local_spec = _make_local_spec()

        bkai_backend = resolver.resolve(bkai_spec)
        local_backend = resolver.resolve(local_spec)

        assert isinstance(bkai_backend, BkAiBackend)
        assert isinstance(local_backend, LocalBackend)

    def test_chain_registration(self) -> None:
        """register() 返回 self 支持链式调用。"""
        resolver = AgentBackendResolver()
        result = resolver.register("bkai", BkAiBackend).register("local", LocalBackend)

        assert result is resolver


class TestGetAgentToolsWithDualBackend:
    """注册双后端后，get_agent_tools 可正常生成工具（非空列表）。"""

    def test_get_agent_tools_returns_non_empty_list(self) -> None:
        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend).register("local", LocalBackend)

        specs = [_make_bkai_spec(), _make_local_spec()]
        tools = get_agent_tools(specs, resolver)

        assert len(tools) == 2
        assert tools[0].name == "Agent"
        assert tools[1].name == "sendMessages"

    def test_get_agent_tools_empty_specs(self) -> None:
        """specs 为空时返回空列表。"""
        resolver = AgentBackendResolver()
        tools = get_agent_tools([], resolver)

        assert tools == []


class TestUnregisteredBackendResolve:
    """未注册的后端类型 resolve 抛出 ValueError。"""

    def test_resolve_unregistered_raises_value_error(self) -> None:
        resolver = AgentBackendResolver()

        spec = _make_bkai_spec()
        with pytest.raises(ValueError, match="Unknown backend type"):
            resolver.resolve(spec)

    def test_resolve_with_available_hint(self) -> None:
        """错误消息包含可用后端列表提示。"""
        resolver = AgentBackendResolver()
        resolver.register("local", LocalBackend)

        spec = _make_bkai_spec()
        with pytest.raises(ValueError, match="Available: local"):
            resolver.resolve(spec)


class TestBackendProtocolSatisfaction:
    """BkAiBackend 和 LocalBackend 实例满足 AgentBackend Protocol（isinstance 检查）。"""

    def test_bkai_backend_satisfies_protocol(self) -> None:
        backend = BkAiBackend()
        assert isinstance(backend, AgentBackend)

    def test_local_backend_satisfies_protocol(self) -> None:
        backend = LocalBackend()
        assert isinstance(backend, AgentBackend)

    def test_resolved_backends_satisfy_protocol(self) -> None:
        """通过 resolver.resolve() 返回的实例也满足 Protocol。"""
        resolver = AgentBackendResolver()
        resolver.register("bkai", BkAiBackend).register("local", LocalBackend)

        bkai_backend = resolver.resolve(_make_bkai_spec())
        local_backend = resolver.resolve(_make_local_spec())

        assert isinstance(bkai_backend, AgentBackend)
        assert isinstance(local_backend, AgentBackend)


# ============== Test: member 模式工具生成 ==============


class TestGetAgentToolsWithMemberMode:
    """get_agent_tools() 工具生成行为。"""

    def test_specs_produce_send_messages_tool(self) -> None:
        """有 spec 时返回 sendMessages 工具（mode 由运行时决定）。"""
        specs = [_make_spec()]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        tool_names = [t.name for t in tools]
        assert "Agent" in tool_names
        assert "sendMessages" in tool_names

    def test_specs_always_produce_send_messages_tool(self) -> None:
        """任何 spec 都返回 sendMessages 工具（mode 不再预配置，由运行时决定）。"""
        specs = [_make_spec()]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        tool_names = [t.name for t in tools]
        assert "sendMessages" in tool_names

    def test_send_messages_missing_session_code_returns_failed(self) -> None:
        """sendMessages 在 session_code 为空时返回 failed。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        send_msg_tool = next(t for t in tools if t.name == "sendMessages")
        # state 中没有 session_code
        state: dict[str, Any] = {
            "bk_agent_team": {"my_member": {"session_code": "", "status": "idle", "agent_name": "member_agent"}}
        }

        # 直接调用底层函数以传递 InjectedState 参数
        result_str = send_msg_tool.func(
            member_name="my_member",
            message="hello",
            config=None,
            state=state,
        )
        result = json.loads(result_str)
        assert result["status"] == "failed"
        assert "尚未初始化" in result["error"]

    def test_send_messages_unknown_agent_returns_failed(self) -> None:
        """sendMessages 对未知的 agent_name 返回 failed。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        send_msg_tool = next(t for t in tools if t.name == "sendMessages")
        state: dict[str, Any] = {
            "bk_agent_team": {
                "unknown_member": {"session_code": "sess_123", "status": "active", "agent_name": "nonexistent_agent"}
            }
        }
        result_str = send_msg_tool.func(
            member_name="unknown_member",
            message="hello",
            config=None,
            state=state,
        )
        result = json.loads(result_str)
        assert result["status"] == "failed"
        assert "未知" in result["error"]

    def test_send_messages_with_session_code_calls_execute(self) -> None:
        """sendMessages 有 session_code 时调用 BkAiBackend.execute。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        send_msg_tool = next(t for t in tools if t.name == "sendMessages")
        state: dict[str, Any] = {
            "bk_agent_team": {
                "my_member": {"session_code": "sess_123", "status": "active", "agent_name": "member_agent"}
            }
        }

        with patch(
            "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
            return_value=AgentResult(status="completed", result="reply"),
        ):
            result_str = send_msg_tool.func(
                member_name="my_member",
                message="hello",
                config=None,
                state=state,
            )
            result = json.loads(result_str)
            assert result["status"] == "completed"

    def test_send_messages_nesting_check_blocks_at_max_depth(self) -> None:
        """D-06：send_messages 达到 max_spawn_depth 时返回嵌套失败结果（不再是旁路）。"""
        specs = [_make_spec(name="agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)
        send_msg_tool = next(t for t in tools if t.name == "sendMessages")

        ek = ExecuteKwargs(spawn_depth=1, max_spawn_depth=1)
        result_str = send_msg_tool.func(
            member_name="member",
            message="hello",
            config={"configurable": {"execute_kwargs": ek}},
            state={"bk_agent_team": {"member": {"session_code": "s1", "agent_name": "agent"}}},
        )
        parsed = json.loads(result_str)
        assert parsed["status"] == "failed"
        assert "嵌套" in parsed["error"]

    def test_send_messages_below_max_depth_not_blocked_by_nesting(self) -> None:
        """D-06：spawn_depth < max_spawn_depth 时 send_messages 正常调用 backend.execute（不抛嵌套）。"""
        specs = [_make_spec(name="agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)
        send_msg_tool = next(t for t in tools if t.name == "sendMessages")

        ek = ExecuteKwargs(spawn_depth=0, max_spawn_depth=1)
        with patch(
            "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
            return_value=AgentResult(status="completed", result="reply"),
        ) as mock_execute:
            result_str = send_msg_tool.func(
                member_name="member",
                message="hello",
                config={"configurable": {"execute_kwargs": ek}},
                state={"bk_agent_team": {"member": {"session_code": "s1", "agent_name": "agent"}}},
            )
        parsed = json.loads(result_str)
        # 嵌套保护未触发：backend.execute 被真实调用，结果无嵌套失败
        mock_execute.assert_called_once()
        assert parsed["status"] != "failed" or "嵌套" not in parsed.get("error", "")

    def test_empty_specs_returns_empty_list(self) -> None:
        """空 specs 返回空列表。"""
        resolver = _make_resolver()
        tools = get_agent_tools([], resolver)
        assert tools == []


# ============== Test: agent_call member 模式 ==============


class TestAgentCallMemberMode:
    """agent_call 在 member 模式下的行为。"""

    def test_member_mode_returns_json_with_session_code(self) -> None:
        """member 模式 agent_call 返回包含 session_code 和 member_name 的 JSON 字符串。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        agent_tool = next(t for t in tools if t.name == "Agent")

        with (
            patch(
                "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend._prepare_session",
                return_value={"status": "completed"},
            ),
            patch(
                "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
                return_value=AgentResult(status="completed", result="reply"),
            ),
        ):
            result = agent_tool.func(
                agent_name="member_agent",
                message="hello",
                mode="member",
                config=None,
                state={"bk_agent_team": {}},
            )

        # member 模式返回纯 JSON 字符串（包含 session_code, member_name, agent_name）
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["status"] == "completed"
        assert "session_code" in parsed
        assert parsed["session_code"]  # session_code 非空
        assert parsed["member_name"] == "member_agent"  # 默认 member_name = agent_name
        assert parsed["agent_name"] == "member_agent"

    def test_member_mode_with_custom_member_name(self) -> None:
        """member 模式指定 member_name 时，使用 member_name 作为 bk_agent_team key。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        agent_tool = next(t for t in tools if t.name == "Agent")

        with (
            patch(
                "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend._prepare_session",
                return_value={"status": "completed"},
            ),
            patch(
                "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
                return_value=AgentResult(status="completed", result="reply"),
            ),
        ):
            result = agent_tool.func(
                agent_name="member_agent",
                message="hello",
                mode="member",
                member_name="judge_1",
                config=None,
                state={"bk_agent_team": {}},
            )

        parsed = json.loads(result)
        assert parsed["member_name"] == "judge_1"
        assert parsed["agent_name"] == "member_agent"

    def test_member_mode_existing_session_reuses(self) -> None:
        """member 模式已有 session_code 时不重新创建。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        agent_tool = next(t for t in tools if t.name == "Agent")

        with (
            patch(
                "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
                return_value=AgentResult(status="completed", result="reply"),
            ) as mock_exec,
        ):
            result = agent_tool.func(
                agent_name="member_agent",
                message="hello",
                mode="member",
                member_name="my_member",
                config=None,
                state={
                    "bk_agent_team": {
                        "my_member": {"session_code": "existing_sess", "status": "active", "agent_name": "member_agent"}
                    }
                },
            )

        # execute 应该使用已有的 session_code
        mock_exec.assert_called_once()
        call_kwargs = mock_exec.call_args
        assert call_kwargs[1].get("session_code") == "existing_sess"
        # 返回值应包含 session_code
        parsed = json.loads(result)
        assert parsed["session_code"] == "existing_sess"
        assert parsed["member_name"] == "my_member"


# ============== Test: agent_call 使用 AgentResult 后端返回值 ==============


class TestAgentCallWithAgentResult:
    """agent_call 在 AgentResult 后端返回值下的行为。"""

    def test_member_mode_wraps_agentresult_with_provider_fields(self) -> None:
        """member 模式：AgentResult.model_dump() + wrapper dict，JSON 中包含 session_code/member_name/agent_name。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        agent_tool = next(t for t in tools if t.name == "Agent")

        with (
            patch(
                "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend._prepare_session",
                return_value={"status": "completed"},
            ),
            patch(
                "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
                return_value=AgentResult(status="completed", result="reply"),
            ),
        ):
            result = agent_tool.func(
                agent_name="member_agent",
                message="hello",
                mode="member",
                config=None,
                state={"bk_agent_team": {}},
            )

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["status"] == "completed"
        assert "session_code" in parsed
        assert parsed["session_code"]
        assert parsed["member_name"] == "member_agent"
        assert parsed["agent_name"] == "member_agent"
        assert parsed["result"] == "reply"

    def test_task_mode_serializes_agentresult_via_model_dump(self) -> None:
        """task 模式：AgentResult 通过 model_dump() 序列化为 JSON。"""
        specs = [_make_spec(name="task_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        agent_tool = next(t for t in tools if t.name == "Agent")

        with patch(
            "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
            return_value=AgentResult(status="completed", result="task result", tool_calls=3),
        ):
            result = agent_tool.func(
                agent_name="task_agent",
                message="do task",
                config=None,
                state={},
            )

        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["status"] == "completed"
        assert parsed["result"] == "task result"
        assert parsed["tool_calls"] == 3

    def test_direct_json_dumps_on_agentresult_raises_typeerror(self) -> None:
        """验证直接对 AgentResult 调用 json.dumps() 抛出 TypeError（不可直接 JSON 序列化）。"""
        agent_result = AgentResult(status="completed", result="test")
        with pytest.raises(TypeError):
            json.dumps(agent_result)

    def test_send_messages_serializes_agentresult_via_model_dump(self) -> None:
        """send_messages：AgentResult 通过 model_dump() 序列化为 JSON。"""
        specs = [_make_spec(name="member_agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)

        send_msg_tool = next(t for t in tools if t.name == "sendMessages")
        state: dict[str, Any] = {
            "bk_agent_team": {
                "my_member": {"session_code": "sess_123", "status": "active", "agent_name": "member_agent"}
            }
        }

        with patch(
            "aidev_agent.core.tools.a2a_tools.bkai_backend.BkAiBackend.execute",
            return_value=AgentResult(status="completed", result="reply"),
        ):
            result_str = send_msg_tool.func(
                member_name="my_member",
                message="hello",
                config=None,
                state=state,
            )

        parsed = json.loads(result_str)
        assert parsed["status"] == "completed"
        assert parsed["result"] == "reply"

    def test_nesting_check_blocks_at_max_depth(self) -> None:
        """spawn_depth >= max_spawn_depth 时抛出 RuntimeError。"""
        specs = [_make_spec(name="agent")]
        resolver = _make_resolver()
        tools = get_agent_tools(specs, resolver)
        agent_tool = next(t for t in tools if t.name == "Agent")

        ek = ExecuteKwargs(spawn_depth=1, max_spawn_depth=1)
        with pytest.raises(RuntimeError, match="嵌套"):
            agent_tool.func(
                agent_name="agent",
                message="hello",
                config={"configurable": {"execute_kwargs": ek}},
                state={},
            )

    def test_nesting_check_allows_below_max_depth(self) -> None:
        """spawn_depth < max_spawn_depth 时正常执行（不抛嵌套异常）。"""
        specs = [_make_spec(name="agent")]
        resolver = _make_resolver()
        resolver.register("local", LocalBackend)
        tools = get_agent_tools(specs, resolver)
        agent_tool = next(t for t in tools if t.name == "Agent")

        from aidev_agent.pydantic_models import ExecuteKwargs

        ek = ExecuteKwargs(spawn_depth=0, max_spawn_depth=1)
        # 不会抛出 RuntimeError（可能因其他原因报错如缺少 client，但不应是嵌套保护）
        try:
            agent_tool.func(
                agent_name="agent",
                message="hello",
                config={"configurable": {"execute_kwargs": ek}},
                state={},
            )
        except RuntimeError as e:
            assert "嵌套" not in str(e)
        except Exception:
            # 非嵌套保护的其他异常（如缺少 client）是预期的，测试通过
            pass


# ============== Test: TeamPromptMiddleware 更新 ==============


class TestTeamPromptMiddlewareUpdate:
    """TeamPromptMiddleware 的 sendMessages 引导注入测试。"""

    def test_specs_include_send_messages_hint(self) -> None:
        """有 specs 时注入 sendMessages 引导文本（mode 由运行时决定）。"""
        specs = [_make_spec()]
        middleware = TeamPromptMiddleware(specs=specs)

        ctx = ProcessorContext(
            state={},
            config={},
            prompt_slots=PromptSlots(system="Original prompt"),
        )
        middleware(ctx, lambda: None)

        assert "sendMessages" in (ctx.prompt_slots.system or "")
        assert "首次调用成员时使用 Agent 工具" in (ctx.prompt_slots.system or "")
        assert "后续与成员对话时使用 sendMessages 工具" in (ctx.prompt_slots.system or "")

    def test_empty_specs_no_injection(self) -> None:
        """空 specs 时不注入任何成员信息。"""
        middleware = TeamPromptMiddleware(specs=[])

        ctx = ProcessorContext(
            state={},
            config={},
            prompt_slots=PromptSlots(system="Original prompt"),
        )
        middleware(ctx, lambda: None)

        assert ctx.prompt_slots.system == "Original prompt"


# ============== SubAgentConfig.to_agent_spec 测试 ==============


class TestSubAgentConfigToAgentSpec:
    """SubAgentConfig.to_agent_spec() 正确转换为 AgentSpec，backend_type 为 BKAI。"""

    def test_subagent_config_to_agent_spec(self) -> None:
        config = SubAgentConfig(
            name="analyzer",
            agent_code="analyzer_001",
            description="Code analysis agent",
            mode="task",
            temperature=0.7,
            max_tokens=4096,
            timeout_seconds=600,
        )
        spec = config.to_agent_spec()

        assert spec.name == "analyzer"
        assert spec.description == "Code analysis agent"
        assert spec.backend_type == "bkai"
        assert spec.params["agent_code"] == "analyzer_001"
        assert spec.params["temperature"] == 0.7
        assert spec.params["max_tokens"] == 4096
        assert spec.timeout_seconds == 600


class TestSubAgentConfigToAgentSpecMinimal:
    """SubAgentConfig 最小参数的 to_agent_spec() 转换。"""

    def test_subagent_config_to_agent_spec_minimal(self) -> None:
        config = SubAgentConfig(
            name="simple",
            agent_code="simple_001",
            description="A simple agent",
        )
        spec = config.to_agent_spec()

        assert spec.name == "simple"
        assert spec.backend_type == "bkai"
        assert spec.params["agent_code"] == "simple_001"
        # temperature 和 max_tokens 未设置，不应出现在 params 中
        assert "temperature" not in spec.params
        assert "max_tokens" not in spec.params
        assert spec.timeout_seconds == 300


# ============== _check_interrupt 测试 ==============


class TestCheckInterruptNoneConfig:
    """_check_interrupt(None) 返回 False。"""

    def test_check_interrupt_none_config(self) -> None:
        assert _check_interrupt(None) is False


class TestCheckInterruptEmptyConfigurable:
    """_check_interrupt(config={"configurable": {}}) 返回 False（键不存在）。"""

    def test_check_interrupt_empty_configurable(self) -> None:
        assert _check_interrupt({"configurable": {}}) is False


class TestCheckInterruptFlagFalse:
    """_check_interrupt(config={"configurable": {"_interrupt_requested": False}}) 返回 False。"""

    def test_check_interrupt_flag_false(self) -> None:
        assert _check_interrupt({"configurable": {"_interrupt_requested": False}}) is False


class TestCheckInterruptFlagTrue:
    """_check_interrupt(config={"configurable": {"_interrupt_requested": True}}) 返回 True。"""

    def test_check_interrupt_flag_true(self) -> None:
        assert _check_interrupt({"configurable": {"_interrupt_requested": True}}) is True


# ============== _extract_progress_callback 测试 ==============


class TestExtractProgressCallbackWithFn:
    """_extract_progress_callback(config={"configurable": {"progress_callback": mock_fn}}) 返回 mock_fn。"""

    def test_extract_progress_callback_with_fn(self) -> None:
        def mock_fn() -> None:
            pass

        result = _extract_progress_callback({"configurable": {"progress_callback": mock_fn}})
        assert result is mock_fn


class TestExtractProgressCallbackEmptyConfigurable:
    """_extract_progress_callback(config={"configurable": {}}) 返回 None。"""

    def test_extract_progress_callback_empty_configurable(self) -> None:
        assert _extract_progress_callback({"configurable": {}}) is None


class TestExtractProgressCallbackNoneConfig:
    """_extract_progress_callback(config=None) 返回 None。"""

    def test_extract_progress_callback_none_config(self) -> None:
        assert _extract_progress_callback(None) is None


# ============== agent_call 中断与 progress_callback 测试 ==============


class SpyBackend:
    """Spy backend that records execute() and new_session() call arguments for verification."""

    def __init__(self) -> None:
        self.execute_calls: list[dict[str, Any]] = []
        self.new_session_calls: list[dict[str, Any]] = []

    def new_session(self, spec: AgentSpec, **kwargs: Any) -> str:
        self.new_session_calls.append({"spec": spec, "kwargs": kwargs})
        return "spy-session-code"

    def execute(
        self,
        spec: AgentSpec,
        message: str,
        *,
        session_code: str = "",
        progress_callback: Any = None,
        config: Any = None,
        **kwargs: Any,
    ) -> AgentResult:
        self.execute_calls.append(
            {
                "spec": spec,
                "message": message,
                "session_code": session_code,
                "progress_callback": progress_callback,
                "config": config,
                "state": kwargs.get("state"),
            }
        )
        return AgentResult(status="completed", result="ok")


def _get_agent_call_from_tool(resolver: AgentBackendResolver):
    """Helper to extract agent_call closure from get_agent_tools first tool."""
    spec = AgentSpec(name="test_agent", description="A test agent", backend_type=AgentBackendType.BKAI)
    tools = get_agent_tools([spec], resolver)
    return tools[0].func


class TestInterruptRequestedTaskMode:
    """agent_call 在 _interrupt_requested=True 时返回 INTERRUPTED 结果，不调用 backend.execute。"""

    def test_interrupt_requested_task_mode(self) -> None:
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        agent_call = _get_agent_call_from_tool(resolver)
        config: dict[str, Any] = {"configurable": {"_interrupt_requested": True}}
        result = json.loads(agent_call(agent_name="test_agent", message="hello", mode="task", config=config))

        assert result["status"] == "interrupted"
        assert result["exit_reason"] == "interrupted"
        assert "error" in result
        assert spy.execute_calls == []


class TestInterruptRequestedMemberMode:
    """agent_call 在 member 模式下 _interrupt_requested=True 时返回 INTERRUPTED，保留 session_code + member_name。"""

    def test_interrupt_requested_member_mode(self) -> None:
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        agent_call = _get_agent_call_from_tool(resolver)
        config: dict[str, Any] = {"configurable": {"_interrupt_requested": True}}
        result = json.loads(agent_call(agent_name="test_agent", message="hello", mode="member", config=config))

        assert result["status"] == "interrupted"
        assert result["exit_reason"] == "interrupted"
        assert "session_code" in result
        assert result["member_name"] == "test_agent"
        assert spy.execute_calls == []


class TestProgressCallbackPassthrough:
    """agent_call 在 config 中有 progress_callback 时将其传递给 backend.execute()。"""

    def test_progress_callback_passthrough(self) -> None:
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        def my_callback(event_type: str, **cb_kwargs: Any) -> None:
            pass

        agent_call = _get_agent_call_from_tool(resolver)
        config: dict[str, Any] = {"configurable": {"progress_callback": my_callback}}
        result = json.loads(agent_call(agent_name="test_agent", message="hello", mode="task", config=config))

        assert result["status"] == "completed"
        assert len(spy.execute_calls) == 1
        # progress_callback 经过 _make_progress_callback 包装，不再直接是 my_callback
        assert spy.execute_calls[0]["progress_callback"] is not None


class TestProgressCallbackNonePassthrough:
    """agent_call 在 config 中无 progress_callback 时传递 None（后端正常工作）。"""

    def test_progress_callback_none_passthrough(self) -> None:
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        agent_call = _get_agent_call_from_tool(resolver)
        config: dict[str, Any] = {"configurable": {}}
        result = json.loads(agent_call(agent_name="test_agent", message="hello", mode="task", config=config))

        assert result["status"] == "completed"
        assert len(spy.execute_calls) == 1
        # progress_callback 经过 _make_progress_callback 包装，即使原始为 None 也非 None
        assert spy.execute_calls[0]["progress_callback"] is not None


class TestNoInterruptNormalExecution:
    """agent_call 在 _interrupt_requested=False 时正常执行 backend.execute()。"""

    def test_no_interrupt_normal_execution(self) -> None:
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        agent_call = _get_agent_call_from_tool(resolver)
        config: dict[str, Any] = {"configurable": {"_interrupt_requested": False}}
        result = json.loads(agent_call(agent_name="test_agent", message="hello", mode="task", config=config))

        assert result["status"] == "completed"
        assert len(spy.execute_calls) == 1


# ============== Test: provider 将 InjectedState state 透传 backend.execute(state=...) (D-09 provider) ==============


class TestProviderForwardsStateToBackend:
    """agent_call / send_messages 将 InjectedState state 透传给 backend.execute(state=...)。"""

    def test_agent_call_forwards_state_in_task_mode(self) -> None:
        """task 模式 agent_call 将 state 透传给 backend.execute(state=...)。"""
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        agent_call = _get_agent_call_from_tool(resolver)
        state: dict[str, Any] = {"runtime_paas_sbx_pv": []}
        agent_call(agent_name="test_agent", message="hello", mode="task", config={"configurable": {}}, state=state)

        assert len(spy.execute_calls) == 1
        assert spy.execute_calls[0]["state"] == state

    def test_send_messages_forwards_state(self) -> None:
        """send_messages 将 state 透传给 backend.execute(state=...)。"""
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        spec = AgentSpec(name="member_agent", description="A test agent", backend_type=AgentBackendType.BKAI)
        tools = get_agent_tools([spec], resolver)
        send_msg_tool = next(t for t in tools if t.name == "sendMessages")
        state: dict[str, Any] = {
            "bk_agent_team": {"my_member": {"session_code": "sess_123", "agent_name": "member_agent"}},
            "runtime_paas_sbx_pv": [],
        }
        send_msg_tool.func(member_name="my_member", message="hello", config=None, state=state)

        assert len(spy.execute_calls) == 1
        assert spy.execute_calls[0]["state"] == state

    def test_agent_call_forwards_empty_state_too(self) -> None:
        """即使 state 为空 dict，也转发给 backend.execute(state=...)（后端自行守护）。"""
        spy = SpyBackend()
        resolver = AgentBackendResolver()
        resolver.register("bkai", lambda: spy)

        agent_call = _get_agent_call_from_tool(resolver)
        agent_call(agent_name="test_agent", message="hello", mode="task", config={"configurable": {}}, state={})

        assert len(spy.execute_calls) == 1
        assert spy.execute_calls[0]["state"] == {}
