from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.pydantic_models import (
    AgentExecutorKwargs,
    AgentOptions,
    ChatPrompt,
    ExecuteKwargs,
    IntentRecognition,
    KnowledgebaseSettings,
    SessionContentExtra,
)
from aidev_agent.services.common_agent import CommonQAAgent


def test_chat_prompt():
    chat_prompt = ChatPrompt(role="system", content="aaa", extra=SessionContentExtra(rendered_content="bbbb"))
    assert chat_prompt.content == "bbbb"

    chat_prompt = ChatPrompt(role="system", content="aaa")
    assert chat_prompt.content == "aaa"


def test_legacy_agent_options_allow_extra_fields():
    options = AgentOptions(
        intent_recognition_options=IntentRecognition(agent_type="deepseek_r1"),
        knowledge_query_options=KnowledgebaseSettings(document_fragment_count=3),
    )

    assert options.intent_recognition_options.model_extra["agent_type"] == "deepseek_r1"
    assert options.knowledge_query_options.model_extra["document_fragment_count"] == 3
    assert KnowledgebaseSettings().rejection_message


class TestAgentExecutorKwargs:
    """Tests for AgentExecutorKwargs model."""

    def test_create_minimal_config(self):
        """Test creating config with minimal required fields."""
        mock_llm = MagicMock()
        config = AgentExecutorKwargs(llm=mock_llm)

        assert config.llm == mock_llm
        assert config.knowledge_llm is None
        assert config.extra_tools is None
        assert config.support_vision is False
        assert config.tool_execution_interval == 10

    def test_create_full_config(self):
        """Test creating config with all fields populated."""
        mock_llm = MagicMock()
        mock_knowledge_llm = MagicMock()
        mock_tools = [MagicMock(), MagicMock()]
        mock_callbacks = [MagicMock()]
        mock_file_store = MagicMock()
        mock_checkpointer = MagicMock()
        execute_kwargs = ExecuteKwargs(stream=True)

        config = AgentExecutorKwargs(
            llm=mock_llm,
            knowledge_llm=mock_knowledge_llm,
            non_thinking_llm="gpt-4",
            extra_tools=mock_tools,
            chat_history=[],
            tool_execution_interval=5,
            support_vision=True,
            file_store=mock_file_store,
            callbacks=mock_callbacks,
            execute_kwargs=execute_kwargs,
            checkpointer=mock_checkpointer,
        )

        assert config.llm == mock_llm
        assert config.knowledge_llm == mock_knowledge_llm
        assert config.non_thinking_llm == "gpt-4"
        assert config.extra_tools == mock_tools
        assert config.chat_history == []
        assert config.tool_execution_interval == 5
        assert config.support_vision is True
        assert config.file_store == mock_file_store
        assert config.callbacks == mock_callbacks
        assert config.execute_kwargs == execute_kwargs
        assert config.checkpointer == mock_checkpointer

    def test_model_dump_excludes_none(self):
        """Test that model_dump(exclude_none=True) excludes None values."""
        mock_llm = MagicMock()
        config = AgentExecutorKwargs(
            llm=mock_llm,
            tool_execution_interval=5,
        )

        dumped = config.model_dump(exclude_none=True)

        assert "llm" in dumped
        assert "tool_execution_interval" in dumped
        assert "knowledge_llm" not in dumped
        assert "extra_tools" not in dumped
        assert "file_store" not in dumped

    def test_execute_kwargs_stream_mode_defaults_to_start_and_accepts_attach(self):
        assert ExecuteKwargs().stream_mode == "start"
        assert ExecuteKwargs(stream_mode="attach").stream_mode == "attach"

    def test_execute_kwargs_rejects_unknown_stream_mode(self):
        with pytest.raises(ValueError):
            ExecuteKwargs(stream_mode="resume")

    def test_model_dump_for_builder_kwargs(self):
        """Test that model_dump produces valid kwargs for ReActAgentBuilder."""
        mock_llm = MagicMock()
        mock_tools = [MagicMock()]

        config = AgentExecutorKwargs(
            llm=mock_llm,
            knowledge_llm=mock_llm,
            extra_tools=mock_tools,
            support_vision=True,
        )

        dumped = config.model_dump(exclude_none=True)

        # Verify essential keys are present
        assert "llm" in dumped
        assert "knowledge_llm" in dumped
        assert "extra_tools" in dumped
        assert "support_vision" in dumped

    def test_arbitrary_types_allowed(self):
        """Test that config accepts arbitrary types like BaseChatModel."""
        # This tests that arbitrary_types_allowed=True is working
        mock_llm = MagicMock()
        mock_llm.model_name = "test-model"

        config = AgentExecutorKwargs(llm=mock_llm)

        assert config.llm.model_name == "test-model"

    def test_config_extension(self):
        """Test that config can be extended with custom fields."""

        class CustomConfig(AgentExecutorKwargs):
            """Extended config for custom agent."""

            custom_param: str | None = None
            custom_int: int = 42

        mock_llm = MagicMock()
        config = CustomConfig(
            llm=mock_llm,
            custom_param="custom_value",
            custom_int=100,
        )

        assert config.llm == mock_llm
        assert config.custom_param == "custom_value"
        assert config.custom_int == 100

        # Test model_dump with exclusion
        dumped = config.model_dump(exclude_none=True, exclude={"custom_param"})
        assert "llm" in dumped
        assert "custom_param" not in dumped
        assert "custom_int" in dumped


class TestCommonQAAgentGetAgentExecutor:
    """Tests for CommonQAAgent.get_agent_executor() (kwargs-only + model_validate)."""

    @patch("aidev_agent.services.common_agent.agent.ReActAgentBuilder")
    def test_get_agent_executor_validates_kwargs_and_calls_builder(self, mock_builder_class):
        mock_llm = MagicMock()

        mock_builder = MagicMock()
        mock_builder.set_bkai_options.return_value = mock_builder
        mock_builder.enable_security_runtime.return_value = mock_builder
        mock_builder.build.return_value = (MagicMock(), MagicMock())
        mock_builder_class.return_value = mock_builder

        agent, cfg = CommonQAAgent.get_agent_executor(
            llm=mock_llm,
            knowledge_llm=mock_llm,
            support_vision=True,
        )

        mock_builder_class.assert_called_once_with()
        mock_builder.set_bkai_options.assert_called_once()
        called_options = mock_builder.set_bkai_options.call_args.args[0]
        assert isinstance(called_options, AgentExecutorKwargs)
        assert called_options.llm == mock_llm
        assert called_options.knowledge_llm == mock_llm
        assert called_options.support_vision is True

    @patch("aidev_agent.services.common_agent.agent.ReActAgentBuilder")
    def test_get_agent_executor_preserves_extra_fields(self, mock_builder_class):
        mock_llm = MagicMock()

        mock_builder = MagicMock()
        mock_builder.set_bkai_options.return_value = mock_builder
        mock_builder.enable_security_runtime.return_value = mock_builder
        mock_builder.build.return_value = (MagicMock(), MagicMock())
        mock_builder_class.return_value = mock_builder

        CommonQAAgent.get_agent_executor(
            llm=mock_llm,
            knowledge_llm=mock_llm,
            custom_param="custom_value",
        )

        called_options = mock_builder.set_bkai_options.call_args.args[0]
        dumped = called_options.model_dump(exclude_none=True)
        assert dumped["custom_param"] == "custom_value"


def test_execute_kwargs_input_default_empty():
    assert ExecuteKwargs().input == ""


def test_execute_kwargs_input_assignment_and_serialization():
    kwargs = ExecuteKwargs(input="hi")
    assert kwargs.input == "hi"
    assert kwargs.model_dump()["input"] == "hi"
