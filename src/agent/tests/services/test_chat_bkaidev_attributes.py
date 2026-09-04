"""Unit tests for X-BKAIDEV-Attributes header construction and injection (Phase 13)."""

import json
import warnings
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent import ChatCompletionAgent
from aidev_agent.services.agent.chat import ChatAgentBuilder
from aidev_agent.services.agent.registry import AgentBuildContext, ChatBuildExtras
from langchain_core.language_models import BaseChatModel
from langchain_core.runnables import Runnable
from langchain_core.runnables.fallbacks import RunnableWithFallbacks


def _make_builder_ctx(agent_info: dict | None = None, non_thinking_llm: str | None = None):
    """Construct minimal ctx for ChatAgentBuilder with configurable agent_info."""
    ctx = MagicMock(spec=AgentBuildContext)
    ctx.session_context_data = []
    ctx.agent_config.agent_info = agent_info
    ctx.agent_config.chat_model = "test-model"
    ctx.agent_config.non_thinking_llm = non_thinking_llm
    ctx.agent_config.temperature = None
    ctx.agent_config.max_tokens = None
    ctx.chat = ChatBuildExtras()
    return ctx


class TestBuildChatModel:
    """Test build_chat_model constructs ChatModel correctly (no header at build time)."""

    @patch("aidev_agent.services.agent.chat.ChatModel.get_setup_instance")
    def test_no_bkaidev_header_at_build_time(self, mock_setup):
        """X-BKAIDEV-Attributes is NOT injected at build time (injected at execute time)."""
        agent_info = {
            "agent_code": "test-code",
            "agent_name": "TestAgent",
            "service_catalogue": "svc/cat",
        }
        ctx = _make_builder_ctx(agent_info=agent_info)
        mock_setup.return_value = MagicMock(spec=BaseChatModel)
        builder = ChatAgentBuilder(ctx)
        builder.build_chat_model()

        mock_setup.assert_called_once()
        call_kwargs = mock_setup.call_args[1]
        # No X-BKAIDEV-Attributes at build time
        if "default_headers" in call_kwargs:
            assert "X-BKAIDEV-Attributes" not in call_kwargs["default_headers"]


class TestBuildChatModelNonThinking:
    """Test build_chat_model_non_thinking returns ChatModel or None."""

    @patch("aidev_agent.services.agent.chat.ChatModel.get_setup_instance")
    def test_returns_chat_model_instance(self, mock_setup):
        """When non_thinking_llm is set, returns ChatModel instance."""
        ctx = _make_builder_ctx(agent_info={}, non_thinking_llm="nt-model-v1")
        mock_setup.return_value = MagicMock(spec=BaseChatModel)
        builder = ChatAgentBuilder(ctx)
        result = builder.build_chat_model_non_thinking()

        assert result is not None
        mock_setup.assert_called_once()
        call_kwargs = mock_setup.call_args[1]
        assert call_kwargs["model"] == "nt-model-v1"

    def test_returns_none_when_no_model(self):
        """When non_thinking_llm is None, returns None."""
        ctx = _make_builder_ctx(agent_info={"agent_code": "x"}, non_thinking_llm=None)
        builder = ChatAgentBuilder(ctx)
        result = builder.build_chat_model_non_thinking()
        assert result is None


@pytest.mark.parametrize(
    ("method_name", "model_name"),
    [
        ("build_chat_model_non_thinking", "nt-model-v1"),
        ("build_chat_model_fast", "fast-model-v1"),
    ],
)
def test_auxiliary_chat_models_forward_default_headers(method_name, model_name):
    headers = {"traceparent": "00-992eea94222b572e883ab78b23e73d64-99e019654b49749a-01"}
    ctx = _make_builder_ctx(agent_info={}, non_thinking_llm=model_name)
    ctx.chat = ChatBuildExtras(default_headers=headers)
    builder = ChatAgentBuilder(ctx)

    with (
        patch("aidev_agent.services.agent.chat.settings.JUDGMENT_LLM_MODEL", model_name),
        patch("aidev_agent.services.agent.chat.settings.LLM_GW_ENDPOINT", "https://llm-gateway.example.com"),
        patch("aidev_agent.services.agent.chat.ChatModel.get_setup_instance") as mock_setup,
    ):
        getattr(builder, method_name)()

    assert mock_setup.call_args.kwargs["default_headers"] == headers


class TestBuildNonThinkingLlmDeprecation:
    """Test build_non_thinking_llm emits DeprecationWarning."""

    def test_emits_deprecation_warning(self):
        """Calling build_non_thinking_llm raises DeprecationWarning."""
        ctx = _make_builder_ctx(agent_info={}, non_thinking_llm="old-model")
        builder = ChatAgentBuilder(ctx)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = builder.build_non_thinking_llm()
            assert len(w) == 1
            assert issubclass(w[0].category, DeprecationWarning)
            assert "build_chat_model_non_thinking" in str(w[0].message)
        assert result == "old-model"


class TestUpdateBkaidevSessionHeader:
    """Test _update_bkaidev_session_header builds complete header (agent.info + session)."""

    def _make_agent_with_model(self, agent_info: dict | None = None):
        """Create ChatCompletionAgent with mocked chat_model."""
        agent = ChatCompletionAgent()
        mock_model = MagicMock()
        mock_model.default_headers = {}
        agent.chat_model = mock_model
        agent.chat_model_non_thinking = None
        agent.agent_info = agent_info
        return agent

    def test_builds_complete_header_with_info_and_session(self):
        """Builds X-BKAIDEV-Attributes with both agent.info and session fields."""
        agent = self._make_agent_with_model(
            agent_info={
                "agent_code": "my-agent",
                "agent_name": "Agent",
                "service_catalogue": "svc/cat",
            }
        )
        kwargs = ExecuteKwargs(
            stream=False,
            caller_bk_app_code="app-001",
            caller_bk_biz_env="public",
            caller_bk_biz_id=6000086,
            caller_executor="user-a",
            executor="user-b",
            caller_order_type="ai-auto",
            session_code="sess-xyz",
        )
        agent._update_aidev_agent_header(kwargs)

        result = json.loads(agent.chat_model.default_headers["X-BKAIDEV-Attributes"])
        # agent.info fields
        assert result["agent.info.code"] == "my-agent"
        assert result["agent.info.name"] == "Agent"
        assert result["agent.info.service_catalogue"] == "svc/cat"
        # session fields
        assert result["agent.session.caller_bk_app_code"] == "app-001"
        assert result["agent.session.caller_bk_biz_env"] == "public"
        assert result["agent.session.caller_bk_biz_id"] == "6000086"  # int -> str
        assert result["agent.session.caller_executor"] == "user-a"
        assert result["agent.session.executor"] == "user-b"
        assert result["agent.session.caller_order_type"] == "ai-auto"
        assert result["agent.session.session_code"] == "sess-xyz"

    def test_none_values_become_empty_string(self):
        """Fields with None value are set to empty string in JSON."""
        agent = self._make_agent_with_model(
            agent_info={
                "agent_code": "my-agent",
                "agent_name": None,
            }
        )
        kwargs = ExecuteKwargs(
            stream=False,
            caller_bk_app_code="app-001",
            caller_bk_biz_env=None,
            caller_bk_biz_id=None,
            caller_executor=None,
            executor=None,
            caller_order_type=None,
            session_code=None,
        )
        agent._update_aidev_agent_header(kwargs)

        result = json.loads(agent.chat_model.default_headers["X-BKAIDEV-Attributes"])
        # Has value
        assert result["agent.info.code"] == "my-agent"
        assert result["agent.session.caller_bk_app_code"] == "app-001"
        # Empty string (not omitted)
        assert result["agent.info.name"] == ""
        assert result["agent.info.service_catalogue"] == ""
        assert result["agent.session.caller_bk_biz_env"] == ""
        assert result["agent.session.caller_bk_biz_id"] == ""

    def test_updates_chat_model_non_thinking_too(self):
        """Both chat_model and chat_model_non_thinking headers are updated."""
        agent = self._make_agent_with_model(agent_info={"agent_code": "x"})
        mock_nt = MagicMock()
        mock_nt.default_headers = {}
        agent.chat_model_non_thinking = mock_nt

        kwargs = ExecuteKwargs(stream=False, session_code="sess-1")
        agent._update_aidev_agent_header(kwargs)

        # Both models updated
        result_main = json.loads(agent.chat_model.default_headers["X-BKAIDEV-Attributes"])
        result_nt = json.loads(agent.chat_model_non_thinking.default_headers["X-BKAIDEV-Attributes"])
        assert result_main["agent.session.session_code"] == "sess-1"
        assert result_nt["agent.session.session_code"] == "sess-1"

    def test_caller_bk_biz_id_int_to_str(self):
        """caller_bk_biz_id (int) is serialized as string in JSON."""
        agent = self._make_agent_with_model(agent_info={})
        kwargs = ExecuteKwargs(stream=False, caller_bk_biz_id=12345)
        agent._update_aidev_agent_header(kwargs)

        result = json.loads(agent.chat_model.default_headers["X-BKAIDEV-Attributes"])
        assert result["agent.session.caller_bk_biz_id"] == "12345"
        assert isinstance(result["agent.session.caller_bk_biz_id"], str)

    def test_all_empty_when_no_data(self):
        """All fields are empty string when agent_info is empty and execute_kwargs has no values."""
        agent = self._make_agent_with_model(agent_info={})
        kwargs = ExecuteKwargs(stream=False)
        agent._update_aidev_agent_header(kwargs)

        result = json.loads(agent.chat_model.default_headers["X-BKAIDEV-Attributes"])
        assert result["agent.info.code"] == ""
        assert result["agent.session.session_code"] == ""

    def test_ensure_ascii_no_raw_chinese_in_header_value(self):
        """Header value uses ASCII-only encoding; Chinese chars are escaped as \\uXXXX
        to comply with W3C baggage header percent-encoding requirements."""
        agent = self._make_agent_with_model(
            agent_info={
                "agent_code": "my-agent",
                "agent_name": "智能助手",
                "service_catalogue": "服务目录/智能服务",
            }
        )
        kwargs = ExecuteKwargs(
            stream=False,
            caller_executor="张三",
            executor="李四",
        )
        agent._update_aidev_agent_header(kwargs)

        header_value = agent.chat_model.default_headers["X-BKAIDEV-Attributes"]
        # The raw JSON string MUST NOT contain unescaped Chinese characters
        assert "智能助手" not in header_value
        assert "服务目录" not in header_value
        assert "智能服务" not in header_value
        assert "张三" not in header_value
        assert "李四" not in header_value
        # It SHOULD contain \\u escapes
        assert "\\u" in header_value

    def test_ensure_ascii_round_trip_chinese_values(self):
        """Unicode-escaped JSON can be parsed back to the original Chinese values."""
        agent = self._make_agent_with_model(
            agent_info={
                "agent_code": "my-agent",
                "agent_name": "智能助手",
                "service_catalogue": "服务目录/智能服务",
            }
        )
        kwargs = ExecuteKwargs(
            stream=False,
            caller_executor="张三",
            executor="李四",
        )
        agent._update_aidev_agent_header(kwargs)

        result = json.loads(agent.chat_model.default_headers["X-BKAIDEV-Attributes"])
        assert result["agent.info.name"] == "智能助手"
        assert result["agent.info.service_catalogue"] == "服务目录/智能服务"
        assert result["agent.session.caller_executor"] == "张三"
        assert result["agent.session.executor"] == "李四"

    def test_ensure_ascii_no_control_chars(self):
        """Header value must not contain any character with code point > 127
        (i.e., no raw non-ASCII bytes)."""
        agent = self._make_agent_with_model(
            agent_info={
                "agent_code": "my-agent",
                "agent_name": "中文名称",
            }
        )
        kwargs = ExecuteKwargs(stream=False)
        agent._update_aidev_agent_header(kwargs)

        header_value = agent.chat_model.default_headers["X-BKAIDEV-Attributes"]
        for ch in header_value:
            assert ord(ch) <= 127, f"Found non-ASCII char U+{ord(ch):04X} in header value"


def _make_runnable_with_default_headers():
    """构造一个带 default_headers 的 Runnable mock（spec=Runnable 既能通过
    RunnableWithFallbacks 的 pydantic 校验，又能手动赋 default_headers）。"""
    m = MagicMock(spec=Runnable)
    m.default_headers = {}
    return m


class TestUpdateBkaidevSessionHeaderFallback:
    """Regression: chat_model 为 RunnableWithFallbacks 时 header 注入。

    回归源：23199f9b 把 build_chat_model 的返回值在配置 fallback_model 时
    改为 RunnableWithFallbacks，而 _update_aidev_agent_header 只判断
    hasattr(model, 'default_headers')，RunnableWithFallbacks 无此属性导致
    主模型被整体跳过。此处用真实 RunnableWithFallbacks 覆盖该路径。
    """

    @staticmethod
    def _wrap(primary, fallbacks):
        return RunnableWithFallbacks(runnable=primary, fallbacks=fallbacks)

    def _make_agent(self, chat_model, agent_info=None, non_thinking=None, fast=None):
        agent = ChatCompletionAgent()
        agent.chat_model = chat_model
        agent.chat_model_non_thinking = non_thinking
        agent.chat_model_fast = fast
        agent.agent_info = agent_info
        return agent

    def test_chat_model_runnable_with_fallbacks_injects_primary_and_fallback(self):
        """主模型为 RunnableWithFallbacks 时，runnable 与每个 fallback 均被注入。"""
        primary = _make_runnable_with_default_headers()
        fallback = _make_runnable_with_default_headers()
        wrapped = self._wrap(primary, [fallback])
        agent = self._make_agent(wrapped, agent_info={"agent_code": "x"})

        agent._update_aidev_agent_header(ExecuteKwargs(stream=False, session_code="sess-1"))

        for model in (primary, fallback):
            assert "X-BKAIDEV-Attributes" in model.default_headers
            result = json.loads(model.default_headers["X-BKAIDEV-Attributes"])
            assert result["agent.info.code"] == "x"
            assert result["agent.session.session_code"] == "sess-1"

    def test_fallback_submodel_also_injected_regression(self):
        """Regression: 修复前 fallback 子模型被漏注入。

        RunnableWithFallbacks 实例的 default_headers 通过 Runnable 基类
        属性透传指向 runnable（primary），原实现只注入 primary，
        fallback 列表中的子模型不会被注入——主模型切到 fallback 时
        网关拿不到 X-BKAIDEV-Attributes。此处断言 fallback 也被注入。
        """
        primary = _make_runnable_with_default_headers()
        fallback = _make_runnable_with_default_headers()
        wrapped = self._wrap(primary, [fallback])
        agent = self._make_agent(wrapped, agent_info={"agent_code": "reg"})

        agent._update_aidev_agent_header(ExecuteKwargs(stream=False, session_code="reg-1"))

        # 修复前：primary 被注入，fallback 漏注入
        assert "X-BKAIDEV-Attributes" in fallback.default_headers
        result = json.loads(fallback.default_headers["X-BKAIDEV-Attributes"])
        assert result["agent.info.code"] == "reg"
        assert result["agent.session.session_code"] == "reg-1"

    def test_multiple_fallbacks_all_injected(self):
        """多个 fallback 全部注入，且内容一致。"""
        primary = _make_runnable_with_default_headers()
        fb1 = _make_runnable_with_default_headers()
        fb2 = _make_runnable_with_default_headers()
        wrapped = self._wrap(primary, [fb1, fb2])
        agent = self._make_agent(wrapped, agent_info={"agent_code": "multi"})

        agent._update_aidev_agent_header(ExecuteKwargs(stream=False, caller_executor="u1", session_code="s-multi"))

        expected = json.loads(primary.default_headers["X-BKAIDEV-Attributes"])
        for model in (fb1, fb2):
            assert json.loads(model.default_headers["X-BKAIDEV-Attributes"]) == expected
        assert expected["agent.info.code"] == "multi"
        assert expected["agent.session.caller_executor"] == "u1"

    def test_mixed_fallback_and_plain_models(self):
        """chat_model 是 RunnableWithFallbacks、辅助模型是普通模型时全部注入。"""
        primary = _make_runnable_with_default_headers()
        fallback = _make_runnable_with_default_headers()
        wrapped = self._wrap(primary, [fallback])
        non_thinking = _make_runnable_with_default_headers()
        fast = _make_runnable_with_default_headers()
        agent = self._make_agent(wrapped, agent_info={"agent_code": "mix"}, non_thinking=non_thinking, fast=fast)

        agent._update_aidev_agent_header(ExecuteKwargs(stream=False, session_code="s-mix"))

        for model in (primary, fallback, non_thinking, fast):
            result = json.loads(model.default_headers["X-BKAIDEV-Attributes"])
            assert result["agent.info.code"] == "mix"
            assert result["agent.session.session_code"] == "s-mix"

    def test_fallback_wrapper_header_value_identical_across_models(self):
        """同一轮 execute 注入到所有模型的 header 字符串完全一致（同一份快照）。"""
        primary = _make_runnable_with_default_headers()
        fallback = _make_runnable_with_default_headers()
        wrapped = self._wrap(primary, [fallback])
        agent = self._make_agent(wrapped, agent_info={"agent_code": "snap"})

        agent._update_aidev_agent_header(ExecuteKwargs(stream=False, caller_bk_app_code="app-x", session_code="snap-1"))

        assert primary.default_headers["X-BKAIDEV-Attributes"] == fallback.default_headers["X-BKAIDEV-Attributes"]


class TestExecuteFillsSessionCallerDefaults:
    """execute() 从 session.property.caller_context 回填，再用 username 补齐空的 executor。"""

    def _execute_and_capture(self, execute_kwargs, *, username="user", resource_manager=None):
        from langchain_core.messages import HumanMessage

        agent = ChatCompletionAgent()
        agent.resource_manager = resource_manager or MagicMock(username=username)
        if resource_manager is None:
            agent.resource_manager.retrieve_chat_session.return_value = {"session_property": {}}
        agent.chat_model = MagicMock()
        agent.chat_model_non_thinking = None
        agent.interrupt_processor = MagicMock()
        agent.messages = [HumanMessage(content="hi")]
        captured = {}

        def _execute(messages, kwargs):
            captured["kwargs"] = kwargs
            return "ok"

        agent._execute = _execute
        agent.execute(execute_kwargs)
        return captured["kwargs"], agent.resource_manager

    def test_approval_resume_fills_from_resource_manager_username(self):
        kwargs, _ = self._execute_and_capture(
            ExecuteKwargs(stream=True, resume=[{"interruptId": "approval-1"}]),
        )
        assert kwargs.caller_bk_app_code is None
        assert kwargs.caller_bk_biz_env is None
        assert kwargs.caller_order_type is None
        assert kwargs.executor == "user"
        assert kwargs.caller_executor == "user"

    def test_ask_user_resume_fills_from_resource_manager_username(self):
        kwargs, _ = self._execute_and_capture(
            ExecuteKwargs(
                stream=True,
                resume=[
                    {
                        "interruptId": "ask-1",
                        "status": "resolved",
                        "payload": {"answers": [{"question": "q", "answer": "a"}]},
                    }
                ],
            ),
        )
        assert kwargs.caller_bk_app_code is None
        assert kwargs.executor == "user"
        assert kwargs.caller_executor == "user"

    def test_first_call_persists_caller_context(self):
        kwargs, rm = self._execute_and_capture(
            ExecuteKwargs(
                stream=True,
                session_code="sess-1",
                caller_bk_app_code="app-001",
                caller_bk_biz_env="public",
                executor="user-a",
            ),
        )
        assert kwargs.caller_bk_app_code == "app-001"
        rm.update_chat_session_caller_context.assert_called_once_with(
            "sess-1",
            {
                "caller_bk_app_code": "app-001",
                "caller_bk_biz_env": "public",
                "caller_executor": "user-a",
                "executor": "user-a",
            },
        )

    def test_resume_restores_caller_context_over_worker_username(self):
        rm = MagicMock(username="approver")
        stored = {
            "caller_bk_app_code": "app-001",
            "caller_bk_biz_env": "public",
            "caller_executor": "user-a",
            "caller_order_type": "ai-auto",
            "executor": "user-a",
        }
        rm.retrieve_chat_session.return_value = {"session_property": {"caller_context": stored}}
        kwargs, _ = self._execute_and_capture(
            ExecuteKwargs(stream=True, session_code="sess-1", resume=[{"interruptId": "approval-1"}]),
            resource_manager=rm,
        )
        assert kwargs.caller_bk_app_code == "app-001"
        assert kwargs.caller_bk_biz_env == "public"
        assert kwargs.caller_order_type == "ai-auto"
        assert kwargs.executor == "user-a"
        assert kwargs.caller_executor == "user-a"
