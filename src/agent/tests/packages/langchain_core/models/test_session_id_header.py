# -*- coding: utf-8 -*-
"""单测：透传 ``session_code`` 到 LLM gateway 的 ``X-Session-ID`` header

仅覆盖 spec `.local/docs/202605/llm_chat_session_id_header.md` 中 model 节点的
注入入口与 chat 装配层透传，不依赖外部 LLM gateway。
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from aidev_agent.enums import AgentType
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel, Embeddings
from aidev_agent.pydantic_models import AgentConfig, AgentOptions
from aidev_agent.services.agent import AgentBuildContext, ChatBuildExtras
from aidev_agent.services.agent.chat import ChatAgentBuilder
from aidev_agent.services.common_agent import CommonQAAgent
from langchain_core.runnables.fallbacks import RunnableWithFallbacks
from langgraph.checkpoint.memory import MemorySaver

# ============================== ApiGwMixin.get_setup_instance ==============================


class TestApiGwMixinSessionIdHeader:
    """`ApiGwMixin.get_setup_instance` 对 ``session_code`` kwarg 的处理"""

    def test_session_code_injected_into_default_headers(self):
        instance = ChatModel.get_setup_instance(model="mock-model", session_code="abc")
        assert instance.default_headers["X-Session-ID"] == "abc"

    def test_no_session_code_kwarg_no_header(self):
        instance = ChatModel.get_setup_instance(model="mock-model")
        assert "X-Session-ID" not in instance.default_headers

    def test_empty_session_code_no_header(self):
        instance = ChatModel.get_setup_instance(model="mock-model", session_code="")
        assert "X-Session-ID" not in instance.default_headers

    def test_none_session_code_no_header(self):
        instance = ChatModel.get_setup_instance(model="mock-model", session_code=None)
        assert "X-Session-ID" not in instance.default_headers

    def test_caller_default_headers_take_precedence(self):
        """调用方在 ``default_headers`` 中显式提供 ``X-Session-ID`` 时不被覆盖"""
        instance = ChatModel.get_setup_instance(
            model="mock-model",
            session_code="from-mixin",
            default_headers={"X-Session-ID": "from-caller"},
        )
        assert instance.default_headers["X-Session-ID"] == "from-caller"

    def test_session_code_coexists_with_auth_headers(self):
        auth_headers = {"bk_app_code": "code-x", "bk_app_secret": "secret-x"}
        instance = ChatModel.get_setup_instance(
            model="mock-model",
            session_code="abc",
            auth_headers=auth_headers,
        )
        assert instance.default_headers["X-Session-ID"] == "abc"
        assert json.loads(instance.default_headers["X-Bkapi-Authorization"]) == auth_headers

    def test_embeddings_subclass_also_supports_session_code(self):
        """``Embeddings`` 共享 ``ApiGwMixin``，应同样支持注入"""
        instance = Embeddings.get_setup_instance(model="text-embedding-test", session_code="abc")
        assert instance.default_headers["X-Session-ID"] == "abc"

    def test_session_code_not_leaked_to_chat_model_kwargs(self):
        """``session_code`` 仅作 header 注入，不应泄漏到底层 ChatOpenAI 字段"""
        instance = ChatModel.get_setup_instance(model="mock-model", session_code="abc")
        # ChatOpenAI / pydantic 不应有 ``session_code`` 字段
        assert not hasattr(instance, "session_code")

    def test_fallback_model_has_explicit_observability_role(self):
        instance = ChatModel.get_setup_instance(model="primary-model", fallback_model="fallback-model")

        assert isinstance(instance, RunnableWithFallbacks)
        assert instance.runnable._model_role == "primary"
        assert instance.fallbacks[0]._model_role == "fallback"


# ============================== ChatAgentBuilder.build_chat_model ==============================


def _make_agent_config(agent_code: str = "agent-x") -> AgentConfig:
    return AgentConfig(
        agent_code=agent_code,
        agent_name=agent_code,
        chat_model="mock-llm",
        non_thinking_llm="mock-llm",
        fast_llm="mock-llm",
        agent_options=AgentOptions(),
    )


def _make_chat_ctx(session_code: str | None) -> AgentBuildContext:
    return AgentBuildContext(
        agent_code="agent-x",
        agent_type=AgentType.CHAT,
        agent_config=_make_agent_config(),
        resource_manager=MagicMock(name="rm"),
        session_code=session_code,
        username="alice",
        session_context_data=[],
        switch_agent=False,
        event_handler=None,
        chat=ChatBuildExtras(
            agent_cls=CommonQAAgent(),
            callbacks=[],
            checkpointer=MemorySaver(),
        ),
    )


class TestChatAgentBuilderTransparentSessionCode:
    """``ChatAgentBuilder.build_chat_model`` 应将 ``ctx.session_code`` 透传给
    ``ChatModel.get_setup_instance`` 的 ``session_code`` kwarg。
    """

    def test_session_code_forwarded_to_get_setup_instance(self):
        ctx = _make_chat_ctx(session_code="conv-12345")
        builder = ChatAgentBuilder(ctx)

        with patch.object(ChatModel, "get_setup_instance", return_value=MagicMock()) as mocked:
            builder.build_chat_model()

        kwargs = mocked.call_args.kwargs
        assert kwargs["session_code"] == "conv-12345"
        assert kwargs["model"] == "mock-llm"

    def test_no_session_code_in_ctx_no_kwarg_passed(self):
        ctx = _make_chat_ctx(session_code=None)
        builder = ChatAgentBuilder(ctx)

        with patch.object(ChatModel, "get_setup_instance", return_value=MagicMock()) as mocked:
            builder.build_chat_model()

        kwargs = mocked.call_args.kwargs
        assert "session_code" not in kwargs

    def test_fallback_model_forwarded_to_get_setup_instance(self):
        ctx = _make_chat_ctx(session_code="conv-fallback")
        ctx.agent_config.fallback_model = "backup-llm"
        builder = ChatAgentBuilder(ctx)

        with patch.object(ChatModel, "get_setup_instance", return_value=MagicMock()) as mocked:
            builder.build_chat_model()

        assert mocked.call_args.kwargs["fallback_model"] == "backup-llm"

    def test_empty_session_code_in_ctx_no_kwarg_passed(self):
        ctx = _make_chat_ctx(session_code="")
        builder = ChatAgentBuilder(ctx)

        with patch.object(ChatModel, "get_setup_instance", return_value=MagicMock()) as mocked:
            builder.build_chat_model()

        kwargs = mocked.call_args.kwargs
        assert "session_code" not in kwargs

    def test_end_to_end_default_headers_contains_session_id(self):
        """build_chat_model 不打 patch，直接断言最终 ChatModel 实例的 default_headers"""
        ctx = _make_chat_ctx(session_code="conv-e2e")
        builder = ChatAgentBuilder(ctx)

        chat_model = builder.build_chat_model()

        assert chat_model.default_headers["X-Session-ID"] == "conv-e2e"
