# -*- coding: utf-8 -*-
"""
测试 ReActAgentBuilder 的完整行为：用户配置、build 预处理、返回值、E2E
"""

from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.config import settings
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.graphs.react.skill_middleware import SkillsPromptMiddleware, _extract_paas_params
from aidev_agent.core.nodes.tool import ToolNodeSettings
from aidev_agent.packages.langchain_core.models import ChatModel
from aidev_agent.packages.langgraph.streaming.streaming_protocol import AgentStreamAdapter
from aidev_agent.pydantic_models import AgentExecutorKwargs
from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

# ============================================================================
# 测试工具定义
# ============================================================================


@tool
def calculator(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@tool
def multiplier(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


# ============================================================================
# 自定义 Middleware 用于测试
# ============================================================================


class CustomMiddlewareWithWrap(AgentMiddleware):
    """覆盖了 wrap_tool_call 的中间件"""

    def wrap_tool_call(self, request, execute):
        return execute(request)


class CustomMiddlewareWithAwrap(AgentMiddleware):
    """覆盖了 awrap_tool_call 的中间件"""

    async def awrap_tool_call(self, request, execute):
        return await execute(request)


class CustomMiddlewareWithTools(AgentMiddleware):
    """带有 tools 属性的中间件"""

    def __init__(self, tools: List[BaseTool]):
        self.tools = tools


class CustomMiddlewareNoOverride(AgentMiddleware):
    """没有覆盖任何方法的中间件"""


# ============================================================================
# SKILL.md 辅助写入
# ============================================================================


def _write_skill(root: Path, *, name: str, description: str, body: str, runtime: str | None = None) -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    frontmatter = f"name: {name}\ndescription: {description}\n"
    if runtime is not None:
        frontmatter += f"runtime: {runtime}\n"
    skill_md.write_text(
        "---\n" + frontmatter + "---\n\n" + body + "\n",
        encoding="utf-8",
    )
    return skill_md


# ============================================================================
# 用于 build 测试的通用 patch 上下文
# ============================================================================


# ============================================================================
# A. 用户配置阶段测试
# ============================================================================


class TestReActAgentBuilder:
    """ReActAgentBuilder 全面测试"""

    # ----------------------------------------------------------------
    # A. 用户配置阶段 - setter 方法正确赋值 + 链式调用
    # ----------------------------------------------------------------

    def test_set_llm(self):
        """set_llm 应设置 _llm 并返回 self"""
        builder = ReActAgentBuilder()
        llm = MagicMock()
        result = builder.set_llm(llm)
        assert builder._llm is llm
        assert result is builder

    def test_set_knowledge_llm(self):
        builder = ReActAgentBuilder()
        llm = MagicMock()
        result = builder.set_knowledge_llm(llm)
        assert builder._knowledge_llm is llm
        assert result is builder

    def test_set_non_thinking_llm(self):
        builder = ReActAgentBuilder()
        llm = MagicMock(spec=BaseChatModel)
        result = builder.set_non_thinking_llm(llm)
        assert builder._non_thinking_llm is llm
        assert result is builder

    def test_set_llm_token_limit(self):
        builder = ReActAgentBuilder()
        result = builder.set_llm_token_limit(50000)
        assert builder._llm_token_limit == 50000
        assert result is builder

    def test_set_suffix(self):
        builder = ReActAgentBuilder()
        result = builder.set_suffix("suffix text")
        assert builder._suffix == "suffix text"
        assert result is builder

    def test_set_chat_history(self):
        builder = ReActAgentBuilder()
        history = [HumanMessage(content="hi")]
        result = builder.set_chat_history(history)
        assert builder._chat_history is history
        assert result is builder

    def test_set_knowledge_items(self):
        builder = ReActAgentBuilder()
        items = [{"id": "1"}]
        result = builder.set_knowledge_items(items)
        assert builder._knowledge_items is items
        assert result is builder

    def test_set_knowledge_bases(self):
        builder = ReActAgentBuilder()
        bases = [{"id": "kb1"}]
        result = builder.set_knowledge_bases(bases)
        assert builder._knowledge_bases is bases
        assert result is builder

    def test_set_enable_query_clarification(self):
        builder = ReActAgentBuilder()
        result = builder.set_enable_query_clarification(True)
        assert builder._enable_query_clarification is True
        assert result is builder

    def test_set_enable_skills(self):
        builder = ReActAgentBuilder()
        result = builder.set_enable_skills(True)
        assert builder._enable_skills is True
        assert result is builder

    def test_set_skill_sources_replaces(self):
        builder = ReActAgentBuilder()
        builder._skill_sources = ["old"]
        result = builder.set_skill_sources(["new1", "new2"])
        assert builder._skill_sources == ["new1", "new2"]
        assert result is builder

    def test_add_skill_sources_appends(self):
        builder = ReActAgentBuilder()
        builder.set_skill_sources(["a"])
        result = builder.add_skill_sources(["b", "c"])
        assert builder._skill_sources == ["a", "b", "c"]
        assert result is builder

    def test_set_tools_replaces(self):
        builder = ReActAgentBuilder()
        builder._extra_tools = [calculator]
        result = builder.set_tools([multiplier])
        assert len(builder._extra_tools) == 1
        assert builder._extra_tools[0] is multiplier
        assert result is builder

    def test_set_tools_none_clears(self):
        builder = ReActAgentBuilder()
        builder._extra_tools = [calculator]
        builder.set_tools(None)
        assert builder._extra_tools == []

    def test_add_tools_appends(self):
        builder = ReActAgentBuilder()
        builder.set_tools([calculator])
        result = builder.add_tools([multiplier])
        assert len(builder._extra_tools) == 2
        assert result is builder

    def test_set_tool_node_options(self):
        builder = ReActAgentBuilder()
        opts = ToolNodeSettings()
        result = builder.set_tool_node_options(opts)
        assert builder._tool_node_options is opts
        assert result is builder

    def test_set_enable_runtime_tool(self):
        builder = ReActAgentBuilder()
        result = builder.set_enable_runtime_tool(True)
        assert builder._enable_runtime_tool is True
        assert result is builder

    def test_register_runtime_type(self):
        builder = ReActAgentBuilder()
        fake_cls = type("FakeBackend", (), {})
        result = builder.register_runtime_type("custom", fake_cls)
        assert builder._runtime_types["custom"] is fake_cls
        assert result is builder

    def test_enable_runtime_local_registers_and_removes(self):
        builder = ReActAgentBuilder()
        result = builder.enable_runtime_local(True)
        assert "local" in builder._runtime_types
        assert "local" in builder._runtime_param_with_skill
        assert result is builder
        builder.enable_runtime_local(False)
        assert "local" not in builder._runtime_types

    def test_enable_runtime_agent_run_registers_and_removes(self):
        builder = ReActAgentBuilder()
        result = builder.enable_runtime_agent_run(True)
        assert "agent_run" in builder._runtime_types
        assert "agent_run" in builder._runtime_param_with_skill
        assert result is builder
        builder.enable_runtime_agent_run(False)
        assert "agent_run" not in builder._runtime_types

    def test_enable_runtime_paas_registers_and_removes(self):
        builder = ReActAgentBuilder()
        result = builder.enable_runtime_paas(True)
        assert "paas_sandbox" in builder._runtime_types
        assert "paas_sandbox" in builder._runtime_param_with_skill
        assert result is builder
        builder.enable_runtime_paas(False)
        assert "paas_sandbox" not in builder._runtime_types

    def test_enable_security_runtime_default_true(self):
        """测试默认情况下 _enable_security_runtime 为 True"""
        builder = ReActAgentBuilder()
        assert builder._enable_security_runtime is True

    def test_enable_security_runtime_set_true(self):
        """测试 enable_security_runtime(True) 设置为 True"""
        builder = ReActAgentBuilder()
        # 先设置为 False 再设置回来
        builder._enable_security_runtime = False
        result = builder.enable_security_runtime(True)
        assert builder._enable_security_runtime is True
        assert result is builder

    def test_enable_security_runtime_set_false(self):
        """测试 enable_security_runtime(False) 设置为 False"""
        builder = ReActAgentBuilder()
        result = builder.enable_security_runtime(False)
        assert builder._enable_security_runtime is False
        assert result is builder

    def test_enable_security_runtime_chained_call(self):
        """测试 enable_security_runtime 支持链式调用"""
        llm = MagicMock()
        builder = ReActAgentBuilder().set_llm(llm).enable_security_runtime(False).set_debug(True)
        assert builder._enable_security_runtime is False
        assert builder._debug is True

    def test_set_callbacks(self):
        builder = ReActAgentBuilder()
        cb = [MagicMock()]
        result = builder.set_callbacks(cb)
        assert builder._callbacks is cb
        assert result is builder

    def test_set_file_store(self):
        builder = ReActAgentBuilder()
        store = MagicMock()
        result = builder.set_file_store(store)
        assert builder._file_store is store
        assert result is builder

    def test_set_checkpointer(self):
        builder = ReActAgentBuilder()
        cp = MagicMock()
        result = builder.set_checkpointer(cp)
        assert builder._checkpointer is cp
        assert result is builder

    def test_set_store(self):
        builder = ReActAgentBuilder()
        store = MagicMock()
        result = builder.set_store(store)
        assert builder._store is store
        assert result is builder

    def test_set_langchain_middleware(self):
        builder = ReActAgentBuilder()
        mw = [CustomMiddlewareWithWrap()]
        result = builder.set_langchain_middleware(mw)
        assert builder._langchain_middleware is mw
        assert result is builder

    def test_set_state_schema(self):
        builder = ReActAgentBuilder()
        schema = MagicMock()
        result = builder.set_state_schema(schema)
        assert builder._state_schema is schema
        assert result is builder

    def test_set_interrupt_before(self):
        builder = ReActAgentBuilder()
        result = builder.set_interrupt_before(["model"])
        assert builder._interrupt_before == ["model"]
        assert result is builder

    def test_set_interrupt_after(self):
        builder = ReActAgentBuilder()
        result = builder.set_interrupt_after(["tools"])
        assert builder._interrupt_after == ["tools"]
        assert result is builder

    def test_set_debug(self):
        builder = ReActAgentBuilder()
        result = builder.set_debug(True)
        assert builder._debug is True
        assert result is builder

    def test_set_name(self):
        builder = ReActAgentBuilder()
        result = builder.set_name("my-graph")
        assert builder._name == "my-graph"
        assert result is builder

    def test_set_cache(self):
        builder = ReActAgentBuilder()
        cache = MagicMock()
        result = builder.set_cache(cache)
        assert builder._cache is cache
        assert result is builder

    def test_chained_setters(self):
        """验证多个 setter 可以链式调用"""
        llm = MagicMock()
        builder = ReActAgentBuilder().set_llm(llm).set_support_vision(True).set_debug(True).set_name("chain-test")
        assert builder._llm is llm
        assert builder._support_vision is True
        assert builder._debug is True
        assert builder._name == "chain-test"

    # ----------------------------------------------------------------
    # B. build 预处理阶段测试
    # ----------------------------------------------------------------

    def test_build_raises_without_llm(self):
        """build() 在未设置 llm 时应抛出 ValueError"""
        builder = ReActAgentBuilder()
        with pytest.raises(ValueError, match="缺少 llm"):
            builder.build()

    def test_build_raises_when_knowledge_without_knowledge_llm(self):
        """配置了知识库但未设置 knowledge_llm 时应抛出 ValueError"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"
        builder = ReActAgentBuilder().set_llm(llm).set_knowledge_bases([{"id": "kb1"}])
        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
            pytest.raises(ValueError, match="knowledge_llm"),
        ):
            builder.build()

    def test_build_raises_when_knowledge_query_options_not_knowledgebase_settings(self):
        """knowledge_query_options 不是 KnowledgeSettings 类型时应抛出 ValueError"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"
        builder = ReActAgentBuilder().set_llm(llm)
        builder._knowledge_query_options = {"knowledge_bases": [{"id": "kb1"}]}
        with pytest.raises(ValueError, match="knowledge_query_options 必须为 KnowledgeSettings"):
            builder.build()

    def test_build_extra_tools_passed_to_prepare_agent_tools(self):
        """build() 应将 _extra_tools 传递给 _prepare_agent_tools"""
        llm = MagicMock()
        llm.model_name = "test-model"

        with (
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._prepare_agent_tools",
                return_value=[],
            ) as mock_prepare_tools,
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            ReActAgentBuilder().set_llm(llm).set_tools([calculator, multiplier]).build()
            kwargs = mock_prepare_tools.call_args.kwargs
            assert kwargs["extra_tools"] == [calculator, multiplier]

    def test_build_middleware_tools_collected(self):
        """middleware 中的 tools 属性应被收集到工具列表"""
        builder = ReActAgentBuilder()
        mw = CustomMiddlewareWithTools(tools=[calculator])
        tools = builder._prepare_agent_tools(
            extra_tools=[],
            langchain_middleware=[mw],
        )
        assert calculator in tools

    def test_build_activate_skill_tool_injected(self, tmp_path, monkeypatch):
        """enable_skills=True 时应注入 activate_skill 工具"""
        monkeypatch.chdir(tmp_path)
        skills_root = tmp_path / ".agent" / "skills"
        _write_skill(skills_root, name="s1", description="d", body="b", runtime="local")

        llm = MagicMock()
        llm.model_name = "gpt-4o"

        captured_tools = {}

        def _fake_make_model_node(*, llm, non_thinking_llm, tools, node_options):
            captured_tools["tools"] = tools
            return MagicMock()

        resolver = MagicMock()
        resolver.runtime_param_description.return_value = "runtime target"
        builder = (
            ReActAgentBuilder()
            .set_llm(llm)
            .set_enable_skills(True)
            .set_enable_runtime_tool(True)
            .set_skill_sources([str(skills_root)])
            .enable_runtime_local(True)
        )
        builder._runtime_backend_resolver = resolver

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", new=_fake_make_model_node),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            builder.build()

        tool_names = [t.name for t in captured_tools["tools"]]
        assert "activate_skill" in tool_names

    def test_build_activate_skill_tool_carries_skill_approval_map(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        llm = MagicMock()
        llm.model_name = "gpt-4o"

        provider = MagicMock()
        provider.discover.return_value = [
            {
                "name": "approved-skill",
                "description": "d",
                "path": "api://11/latest",
                "approval": {
                    "enabled": True,
                    "approval_strategy_id": "s1",
                    "skill_id": 11,
                    "skill_name": "approved-skill",
                    "skill_code": "approved-skill",
                },
            }
        ]
        provider.fetch_instructions.return_value = "body"

        captured_tools = {}

        def _fake_make_model_node(*, llm, non_thinking_llm, tools, node_options):
            captured_tools["tools"] = tools
            return MagicMock()

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", new=_fake_make_model_node),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            (ReActAgentBuilder().set_llm(llm).set_enable_skills(True).set_skill_sources([provider]).build())

        activate_tool = next(t for t in captured_tools["tools"] if t.name == "activate_skill")
        approval_map = (activate_tool.metadata or {}).get("skill_approval_map", {})
        assert approval_map["approved-skill"]["target"]["type"] == "skill"
        assert approval_map["approved-skill"]["approval_strategy_id"] == "s1"

    def test_build_runtime_tools_injected(self, tmp_path, monkeypatch):
        """enable_runtime_tool=True 时应注入 7 个运行时客户端工具"""
        monkeypatch.chdir(tmp_path)
        llm = MagicMock()
        llm.model_name = "gpt-4o"

        captured_tools = {}

        def _fake_make_model_node(*, llm, non_thinking_llm, tools, node_options):
            captured_tools["tools"] = tools
            return MagicMock()

        resolver = MagicMock()
        resolver.runtime_param_description.return_value = "runtime target"
        builder = ReActAgentBuilder().set_llm(llm).set_enable_runtime_tool(True).enable_runtime_local(True)
        builder._runtime_backend_resolver = resolver

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", new=_fake_make_model_node),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            builder.build()

        tool_names = [t.name for t in captured_tools["tools"]]
        runtime_expected = {"ls", "read_file", "write_file", "edit_file", "glob", "grep", "execute"}
        assert runtime_expected.issubset(set(tool_names))

    def test_build_skill_sources_creates_registry(self, tmp_path, monkeypatch):
        """enable_skills 时应创建 SkillRegistry 并赋值给 _skill_registry"""
        monkeypatch.chdir(tmp_path)
        skills_root = tmp_path / ".agent" / "skills"
        _write_skill(skills_root, name="s1", description="d", body="b")

        llm = MagicMock()
        llm.model_name = "gpt-4o"

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            builder = ReActAgentBuilder().set_llm(llm).set_enable_skills(True).set_skill_sources([str(skills_root)])
            builder.build()

        assert builder._skill_registry is not None

    def test_build_runtime_backend_resolver_uses_injected_resolver(self):
        """enable_runtime_tool=True 时应使用调用方注入的 RuntimeBackendResolver"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"
        resolver = MagicMock()
        resolver.runtime_param_description.return_value = "runtime target"

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            builder = ReActAgentBuilder().set_llm(llm).set_enable_runtime_tool(True)
            builder._runtime_backend_resolver = resolver
            builder.build()

        assert builder._runtime_backend_resolver is resolver

    def test_build_skill_prompt_middleware_injected(self, tmp_path, monkeypatch):
        """enable_skills 时应向 ModelNodeSettings 注入 SkillsPromptMiddleware"""
        monkeypatch.chdir(tmp_path)
        skills_root = tmp_path / ".agent" / "skills"
        _write_skill(skills_root, name="s1", description="d", body="b")

        llm = MagicMock()
        llm.model_name = "gpt-4o"

        captured_node_options = {}

        def _fake_make_model_node(*, llm, non_thinking_llm, tools, node_options):
            captured_node_options["opts"] = node_options
            return MagicMock()

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", new=_fake_make_model_node),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            (ReActAgentBuilder().set_llm(llm).set_enable_skills(True).set_skill_sources([str(skills_root)]).build())

        middlewares = captured_node_options["opts"].extra_template_middlewares
        assert any(isinstance(m, SkillsPromptMiddleware) for m in middlewares)

    def test_build_knowledge_node_created_when_knowledge_configured(self):
        """配置知识库时应创建 knowledge_node"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"
        knowledge_llm = MagicMock()

        with (
            patch(
                "aidev_agent.core.graphs.react.graph.make_knowledge_node",
                return_value=MagicMock(),
            ) as mock_make_kn,
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            builder = (
                ReActAgentBuilder().set_llm(llm).set_knowledge_llm(knowledge_llm).set_knowledge_bases([{"id": "kb1"}])
            )
            builder.build()
            mock_make_kn.assert_called_once()

    def test_build_model_node_receives_correct_params(self):
        """build() 应将正确的 llm 和 non_thinking_llm 传给 _prepare_agent_model_node"""
        llm = MagicMock()
        llm.model_name = "test-model"

        with (
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._prepare_agent_model_node",
                return_value=MagicMock(),
            ) as mock_model_node,
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            ReActAgentBuilder().set_llm(llm).build()

            kwargs = mock_model_node.call_args.kwargs
            assert kwargs["llm"] is llm

    def test_build_skill_runtime_registers_backend(self, tmp_path, monkeypatch):
        """skill 的 runtime 匹配已注册类型时，应为该 skill 创建并注册独立 backend"""
        monkeypatch.chdir(tmp_path)
        skills_root = tmp_path / ".agent" / "skills"
        _write_skill(skills_root, name="my-skill", description="d", body="b", runtime="sandbox")

        llm = MagicMock()
        llm.model_name = "gpt-4o"

        mock_backend_instance = MagicMock()
        MockBackendCls = MagicMock(return_value=mock_backend_instance)
        MockBackendCls.__name__ = "MockBackend"

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            mock_resolver_instance = MagicMock()
            mock_resolver_instance._backends = {}
            mock_resolver_instance.runtime_param_description.return_value = "runtime target"

            builder = (
                ReActAgentBuilder()
                .set_llm(llm)
                .set_enable_skills(True)
                .set_enable_runtime_tool(True)
                .set_skill_sources([str(skills_root)])
                .register_runtime_type("sandbox", MockBackendCls)
            )
            builder._runtime_backend_resolver = mock_resolver_instance
            builder.build()

        MockBackendCls.assert_called_once()
        builder._runtime_backend_resolver.register_runtime.assert_called_once_with(
            "sandbox_my-skill", mock_backend_instance
        )

    def test_build_skill_unknown_runtime_skipped(self, tmp_path, monkeypatch):
        """skill 声明的 runtime 未注册时应跳过并记录警告"""
        monkeypatch.chdir(tmp_path)
        skills_root = tmp_path / ".agent" / "skills"
        _write_skill(skills_root, name="bad-skill", description="d", body="b", runtime="nonexistent")

        llm = MagicMock()
        llm.model_name = "gpt-4o"

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
            patch("aidev_agent.core.graphs.react.graph.logger") as mock_logger,
        ):
            resolver = MagicMock()
            resolver.runtime_param_description.return_value = "runtime target"
            builder = (
                ReActAgentBuilder()
                .set_llm(llm)
                .set_enable_skills(True)
                .set_enable_runtime_tool(True)
                .set_skill_sources([str(skills_root)])
                .enable_runtime_local(True)
            )
            builder._runtime_backend_resolver = resolver
            builder.build()

        mock_logger.warning.assert_called()
        warning_msg = str(mock_logger.warning.call_args[0])
        assert "nonexistent" in warning_msg
        assert "bad-skill" in warning_msg

    def test_build_no_local_backend_auto_injected(self, tmp_path, monkeypatch):
        """build() 不应自动向 resolver 注册 local backend"""
        monkeypatch.chdir(tmp_path)
        llm = MagicMock()
        llm.model_name = "gpt-4o"

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", return_value=MagicMock()),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            resolver = MagicMock()
            resolver._backends = {}
            resolver.runtime_param_description.return_value = "runtime target"
            builder = ReActAgentBuilder().set_llm(llm).set_enable_runtime_tool(True)
            builder._runtime_backend_resolver = resolver
            builder.build()

        assert builder._runtime_backend_resolver._backends.get("local") is None

    # ----------------------------------------------------------------
    # B (continued). _prepare_agent_tool_node 测试
    # ----------------------------------------------------------------

    @patch("aidev_agent.core.graphs.react.graph.build_tool_node")
    def test_prepare_agent_tool_node_passes_params(self, mock_build_tool_node):
        """_prepare_agent_tool_node 应正确传递参数给 build_tool_node"""
        tools = [calculator, multiplier]
        node_options = ToolNodeSettings(use_timer=False, use_result_limit=True, result_limit_thrd=500)
        mw_wrap = CustomMiddlewareWithWrap()
        mw_awrap = CustomMiddlewareWithAwrap()
        mw_no = CustomMiddlewareNoOverride()

        mock_build_tool_node.return_value = MagicMock()
        builder = ReActAgentBuilder()
        builder._prepare_agent_tool_node(
            tools=tools,
            name="custom_tools",
            tags=["t1"],
            langchain_middleware=[mw_wrap, mw_awrap, mw_no],
            node_options=node_options,
        )

        mock_build_tool_node.assert_called_once()
        kw = mock_build_tool_node.call_args.kwargs
        assert kw["tools"] == tools
        assert kw["name"] == "custom_tools"
        assert kw["node_options"] is node_options
        # mw_no should not appear in wrappers
        assert mw_no not in kw["wrappers"]
        assert mw_no not in kw["async_wrappers"]
        assert mw_wrap.wrap_tool_call in kw["wrappers"]
        assert mw_awrap.awrap_tool_call in kw["async_wrappers"]
        assert mw_awrap.wrap_tool_call not in kw["wrappers"]
        assert mw_wrap.awrap_tool_call not in kw["async_wrappers"]

    def test_prepare_agent_tool_node_returns_none_for_empty_tools(self):
        """tools 为空时 _prepare_agent_tool_node 应返回 None"""
        builder = ReActAgentBuilder()
        result = builder._prepare_agent_tool_node(tools=[], langchain_middleware=[])
        assert result is None

    # ----------------------------------------------------------------
    # B (continued). _should_continue 测试
    # ----------------------------------------------------------------

    def test_should_continue_returns_pv_node_when_tool_calls(self):
        msg = AIMessage(content="", tool_calls=[{"id": "1", "name": "calc", "args": {}}])
        assert ReActAgentBuilder._should_continue({"messages": [msg]}) == "pv_node"

    def test_should_continue_returns_end_when_no_tool_calls(self):
        msg = AIMessage(content="done")
        assert ReActAgentBuilder._should_continue({"messages": [msg]}) == "end"

    def test_should_continue_returns_end_for_empty_messages(self):
        assert ReActAgentBuilder._should_continue({"messages": []}) == "end"

    def test_approval_check_processes_all_tool_calls(self):
        """approval_check 不应只处理第一个需要审批的 tool_call。"""
        original_metadata = dict(getattr(calculator, "metadata", None) or {})
        calculator.metadata = {
            **original_metadata,
            "approval": {"approval_enabled": True},
        }
        try:
            approval_check = ReActAgentBuilder._make_approval_check_node([calculator])
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        id="ai_approval_all",
                        tool_calls=[
                            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
                            {"id": "call_2", "name": "calculator", "args": {"a": 3, "b": 4}, "type": "tool_call"},
                        ],
                    )
                ]
            }

            with patch(
                "aidev_agent.core.graphs.react.graph.request_approval_decision",
                side_effect=[True, False],
            ) as mock_request:
                command = approval_check(state, {"configurable": {"execute_kwargs": MagicMock(resume=None)}})

            assert command.goto == "pv_node"
            updated_messages = command.update["messages"]
            assert len(updated_messages) == 1
            updated_ai_message = updated_messages[0]
            approval_state = updated_ai_message.additional_kwargs["tool_approval"]
            assert approval_state["call_1"]["status"] == "approved"
            assert approval_state["call_2"]["status"] == "rejected"
            assert mock_request.call_count == 2
        finally:
            calculator.metadata = original_metadata

    def test_approval_check_skips_decided_calls_and_continues_pending_one(self):
        """已决策 tool_call 不应重复审批，后续 pending call 应继续处理。"""
        original_metadata = dict(getattr(calculator, "metadata", None) or {})
        calculator.metadata = {
            **original_metadata,
            "approval": {"approval_enabled": True},
        }
        try:
            approval_check = ReActAgentBuilder._make_approval_check_node([calculator])
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        id="ai_approval_resume",
                        tool_calls=[
                            {"id": "call_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"},
                            {"id": "call_2", "name": "calculator", "args": {"a": 3, "b": 4}, "type": "tool_call"},
                        ],
                        additional_kwargs={
                            "tool_approval": {
                                "call_1": {"status": "approved"},
                                "call_2": {"status": "pending", "interrupt": {"id": "int-approval-call_2"}},
                            }
                        },
                    )
                ]
            }

            with patch(
                "aidev_agent.core.graphs.react.graph.request_approval_decision",
                return_value=True,
            ) as mock_request:
                command = approval_check(
                    state, {"configurable": {"execute_kwargs": MagicMock(resume=[{"approved": True}])}}
                )

            assert command.goto == "pv_node"
            updated_ai_message = next(msg for msg in command.update["messages"] if isinstance(msg, AIMessage))
            approval_state = updated_ai_message.additional_kwargs["tool_approval"]
            assert approval_state["call_1"]["status"] == "approved"
            assert approval_state["call_2"]["status"] == "approved"
            assert mock_request.call_count == 1
            target = mock_request.call_args.args[0]
            assert target.target_id == "call_2"
            assert mock_request.call_args.kwargs["interrupt_payload"] == {"id": "int-approval-call_2"}
        finally:
            calculator.metadata = original_metadata

    def test_approval_check_matches_skill_metadata_without_need_approval(self):
        """skill 只要 approval metadata 完整，也应进入统一审批链路。"""
        original_metadata = dict(getattr(calculator, "metadata", None) or {})
        calculator.metadata = {
            **original_metadata,
            "skill_name": "skill-runner",
            "approval": {
                "tool_type": "skill",
                "skill_code": "skill-runner",
                "tool_name": "Skill Runner",
                "target": {
                    "type": "skill",
                    "skill_name": "skill-runner",
                    "display_name": "Skill Runner",
                },
            },
        }
        try:
            approval_check = ReActAgentBuilder._make_approval_check_node([calculator])
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        id="ai_skill_approval",
                        tool_calls=[
                            {"id": "call_skill_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"}
                        ],
                    )
                ]
            }

            with patch(
                "aidev_agent.core.graphs.react.graph.request_approval_decision",
                return_value=True,
            ) as mock_request:
                command = approval_check(state, {"configurable": {"execute_kwargs": MagicMock(resume=None)}})

            assert command.goto == "pv_node"
            updated_ai_message = command.update["messages"][0]
            approval_state = updated_ai_message.additional_kwargs["tool_approval"]
            assert approval_state["call_skill_1"]["status"] == "approved"
            target = mock_request.call_args.args[0]
            assert target.target_type == "skill"
            assert target.target_code == "skill-runner"
            assert target.target_name == "Skill Runner"
        finally:
            calculator.metadata = original_metadata

    def test_approval_check_matches_mcp_metadata_without_need_approval(self):
        """mcp tool 只要 approval metadata 完整，也应进入统一审批链路。"""
        original_metadata = dict(getattr(calculator, "metadata", None) or {})
        calculator.metadata = {
            **original_metadata,
            "tool_code": "query-time",
            "mcp_name": "time-server",
            "approval": {
                "tool_type": "mcp",
                "mcp_code": "time-server",
                "tool_code": "query-time",
                "tool_name": "Query Time",
                "target": {
                    "type": "mcp",
                    "mcp_name": "time-server",
                    "code": "query-time",
                    "display_name": "Query Time",
                },
            },
        }
        try:
            approval_check = ReActAgentBuilder._make_approval_check_node([calculator])
            state = {
                "messages": [
                    AIMessage(
                        content="",
                        id="ai_mcp_approval",
                        tool_calls=[
                            {"id": "call_mcp_1", "name": "calculator", "args": {"a": 1, "b": 2}, "type": "tool_call"}
                        ],
                    )
                ]
            }

            with patch(
                "aidev_agent.core.graphs.react.graph.request_approval_decision",
                return_value=True,
            ) as mock_request:
                command = approval_check(state, {"configurable": {"execute_kwargs": MagicMock(resume=None)}})

            assert command.goto == "pv_node"
            updated_ai_message = command.update["messages"][0]
            approval_state = updated_ai_message.additional_kwargs["tool_approval"]
            assert approval_state["call_mcp_1"]["status"] == "approved"
            target = mock_request.call_args.args[0]
            assert target.target_type == "mcp"
            assert target.target_code == "query-time"
            assert target.target_name == "Query Time"
        finally:
            calculator.metadata = original_metadata

    # ----------------------------------------------------------------
    # B (continued). _prepare_store 测试
    # ----------------------------------------------------------------
    # B (continued). _prepare_store 测试
    # ----------------------------------------------------------------

    def test_prepare_store_returns_inmemory_when_none(self):
        builder = ReActAgentBuilder()
        result = builder._prepare_store(store=None, file_store=None)
        assert isinstance(result, InMemoryStore)

    def test_prepare_store_returns_provided_store(self):
        builder = ReActAgentBuilder()
        store = MagicMock()
        result = builder._prepare_store(store=store, file_store=None)
        assert result is store

    # ----------------------------------------------------------------
    # B (continued). set_bkai_options 测试 (M1)
    # ----------------------------------------------------------------

    def test_set_bkai_options_maps_fields(self):
        """set_bkai_options 应将 AgentExecutorKwargs 字段映射到 builder 内部状态"""
        llm = MagicMock()
        knowledge_llm = MagicMock()
        cb = [MagicMock()]
        opts = AgentExecutorKwargs(
            llm=llm,
            knowledge_llm=knowledge_llm,
            callbacks=cb,
        )
        builder = ReActAgentBuilder()
        result = builder.set_bkai_options(opts)
        assert builder._llm is llm
        assert builder._knowledge_llm is knowledge_llm
        assert builder._callbacks == cb
        assert result is builder

    def test_set_bkai_options_non_thinking_llm_basechatmodel(self):
        """non_thinking_llm 为 BaseChatModel 时应直接赋值"""
        mock_llm = MagicMock(spec=BaseChatModel)
        # Use a real MagicMock without spec for llm to avoid Pydantic serialization issues
        opts = AgentExecutorKwargs(llm=MagicMock(), non_thinking_llm=mock_llm)
        builder = ReActAgentBuilder()
        # Patch model_dump to avoid serialization errors with MagicMock
        with patch.object(opts, "model_dump", return_value={"llm": True, "non_thinking_llm": True}):
            builder.set_bkai_options(opts)
        assert builder._non_thinking_llm is mock_llm

    # ----------------------------------------------------------------
    # B (continued). _prepare_checkpointer 测试 (M2)
    # ----------------------------------------------------------------

    def test_prepare_checkpointer_returns_provided(self):
        """传入 BaseCheckpointSaver 时应直接返回"""
        builder = ReActAgentBuilder()
        cp = MemorySaver()
        result = builder._prepare_checkpointer(checkpointer=cp)
        assert result is cp

    def test_prepare_checkpointer_returns_memory_saver_when_none(self):
        """传入 None 时应返回 MemorySaver"""
        builder = ReActAgentBuilder()
        result = builder._prepare_checkpointer(checkpointer=None)
        assert isinstance(result, MemorySaver)

    # ----------------------------------------------------------------
    # B (continued). _extract_paas_params 测试 (M3)
    # ----------------------------------------------------------------

    def test_extract_paas_params_from_skill_and_config(self, monkeypatch):
        """_extract_paas_params 应从 skill metadata 与 config 中提取参数"""
        monkeypatch.delenv("SANDBOX_BP_ACCESS_TOKEN", raising=False)
        skill = {
            "metadata": {
                "bkai_paas_sandbox": {
                    "image": "snap1",
                    "envs": {"KEY": "VAL"},
                }
            }
        }
        config = {"access_token": "token123", "executor": "admin"}

        result = _extract_paas_params(skill=skill, config=config)
        assert result["app_code"] == settings.APP_CODE
        assert result["bk_username"] == "admin"
        assert result["snapshot"] == "snap1"
        assert result["snapshot_entrypoint"] == []
        assert result["env_vars"] == {"KEY": "VAL", "ACCESS_TOKEN": "token123"}

    def test_extract_paas_params_defaults(self, monkeypatch):
        """skill=None 且 config 为空时应返回带 settings.APP_CODE 的默认值"""
        monkeypatch.delenv("SANDBOX_BP_ACCESS_TOKEN", raising=False)

        result = _extract_paas_params(skill=None, config={})
        assert result["app_code"] == settings.APP_CODE
        assert result["bk_username"] is None
        assert result["snapshot"] == ""
        assert result["snapshot_entrypoint"] == []
        assert result["env_vars"] == {"ACCESS_TOKEN": ""}

    def test_extract_paas_params_access_token_from_env(self, monkeypatch):
        """config 未提供 access_token 时应从环境变量 SANDBOX_BP_ACCESS_TOKEN 读取"""
        monkeypatch.setenv("SANDBOX_BP_ACCESS_TOKEN", "env-token")

        result = _extract_paas_params(skill=None, config={})
        assert result["env_vars"]["ACCESS_TOKEN"] == "env-token"

    # ----------------------------------------------------------------
    # C. build 返回值测试
    # ----------------------------------------------------------------

    def test_build_returns_graph_and_config(self):
        """build() 应返回 (compiled_graph, RunnableConfig) 元组，graph 上有 .agent 属性"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"

        builder = ReActAgentBuilder().set_llm(llm)
        graph, cfg = builder.build()

        # graph 应是 compiled state graph
        assert hasattr(graph, "invoke") or hasattr(graph, "ainvoke")
        # graph.agent 应该是 AgentStreamAdapter
        assert isinstance(graph.agent, AgentStreamAdapter)
        # cfg 应包含 configurable
        assert "configurable" in cfg
        assert "debug" in cfg["configurable"]

    def test_build_with_callbacks_in_config(self):
        """有 callbacks 时 cfg 应包含 callbacks"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"
        cb = [MagicMock()]
        builder = ReActAgentBuilder().set_llm(llm).set_callbacks(cb)
        graph, cfg = builder.build()
        assert "callbacks" in cfg
        assert cfg["callbacks"] == cb

    def test_build_without_tools_graph_no_react_loop(self):
        """无工具时图应为 START -> model -> END（无 tools 节点）"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"
        builder = ReActAgentBuilder().set_llm(llm)
        graph, cfg = builder.build()
        # The compiled graph should not have a 'tools' node
        node_names = set(graph.nodes.keys())
        assert "model" in node_names
        assert "tools" not in node_names

    def test_build_with_tools_graph_has_react_loop(self):
        """有工具时图应包含 tools 节点形成 ReAct 循环"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"
        builder = ReActAgentBuilder().set_llm(llm).set_tools([calculator])
        graph, cfg = builder.build()
        node_names = set(graph.nodes.keys())
        assert "model" in node_names
        assert "tools" in node_names

    def test_build_non_thinking_llm_fallback(self):
        """未设置 non_thinking_llm 时应回退到 _llm"""
        llm = MagicMock()
        llm.model_name = "gpt-4o"

        captured = {}

        def _fake_make_model_node(*, llm, non_thinking_llm, tools, node_options):
            captured["non_thinking_llm"] = non_thinking_llm
            return MagicMock()

        with (
            patch("aidev_agent.core.graphs.react.graph.std_make_model_node", new=_fake_make_model_node),
            patch(
                "aidev_agent.core.graphs.react.graph.ReActAgentBuilder._build_graph",
                return_value=(MagicMock(), {}),
            ),
        ):
            ReActAgentBuilder().set_llm(llm).build()

        assert captured["non_thinking_llm"] is llm

    # ----------------------------------------------------------------
    # D. E2E 测试
    # ----------------------------------------------------------------

    @pytest.mark.skipif(
        not all([settings.APP_CODE, settings.SECRET_KEY]),
        reason="没有配置足够的环境变量,跳过该测试",
    )
    @pytest.mark.slow
    async def test_react_agent_builder_real(self):
        """E2E 测试：使用真实 LLM 调用 ReActAgentBuilder"""
        llm = ChatModel.get_setup_instance()
        builder = ReActAgentBuilder().set_llm(llm).set_tools([calculator])
        graph, cfg = builder.build()

        try:
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="What is 2 + 3?")]},
                config=cfg,
            )
        except Exception as exc:
            if "403" in str(exc) or "PermissionDenied" in type(exc).__name__:
                pytest.skip(f"LLM credential lacks live model permission: {exc}")
            raise
        assert result is not None
        messages = result.get("messages", [])
        assert len(messages) > 0
        # 最后一条应是 AI 回复
        last_msg = messages[-1]
        assert isinstance(last_msg, AIMessage)
        # 验证 tool 被调用过（中间消息应包含 tool_calls）
        tool_call_msgs = [m for m in messages if isinstance(m, AIMessage) and m.tool_calls]
        assert len(tool_call_msgs) > 0, "Expected at least one tool call in the ReAct loop"
