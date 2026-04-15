# -*- coding: utf-8 -*-
"""
Unit tests for ChatModel._create_chat_result method.

These tests reproduce the bug where Kimi-25 model returns tool calls
in reasoning_content field instead of standard tool_calls field.
"""

import pytest

from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice


@pytest.fixture
def chat_model():
    """Create a ChatModel instance for testing.

    No real API call is made - we only test _create_chat_result which
    processes the response object in-memory.
    """
    from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel

    return ChatModel(model_name="test-model", api_key="empty")


@pytest.fixture
def kimi_25_reasoning_content():
    """The abnormal response format from Kimi-25 model.

    The tool call information is embedded in reasoning_content rather than
    being in the standard tool_calls field.
    """
    return (
        " <|tool_calls_section_begin|>"
        " <|tool_call_begin|> functions.read_file:3"
        " <|tool_call_argument_begin|>"
        '{"file_path": "/app/scripts/fetch_logs.py", "offset": 100, "limit": 200,'
        ' "target_runtime": "paas_sandbox_bk-data-fetcher"}'
        " <|tool_call_end|>"
        " <|tool_calls_section_end|>"
    )


@pytest.fixture
def kimi_25_response(kimi_25_reasoning_content):
    """Build a ChatCompletion response object with reasoning_content containing tool calls.

    This mimics what Kimi-25 model returns. The response is an openai.BaseModel
    instance (so isinstance(response, openai.BaseModel) is True), but there is
    no standard tool_calls field -- the tool call data is hidden inside
    reasoning_content.
    """
    message = ChatCompletionMessage(
        role="assistant",
        content=None,
        reasoning_content=kimi_25_reasoning_content,
    )
    choice = Choice(
        index=0,
        message=message,
        finish_reason="stop",
    )
    return ChatCompletion(
        id="chatcmpl-i5DyaZGAbtHQEjWXdmE8Um",
        choices=[choice],
        created=1776171173,
        model="kimi-25",
        object="chat.completion",
        usage={"prompt_tokens": 0, "total_tokens": 0, "completion_tokens": 0},
    )


@pytest.fixture
def normal_tool_call_response():
    """Build a normal ChatCompletion response with standard tool_calls field.

    This is the standard OpenAI-compatible response format.
    """
    message = ChatCompletionMessage(
        role="assistant",
        content=None,
        tool_calls=[
            {
                "id": "call_abc123",
                "type": "function",
                "function": {
                    "name": "read_file",
                    "arguments": '{"file_path": "/app/scripts/fetch_logs.py", "offset": 100, "limit": 200}',
                },
            }
        ],
    )
    choice = Choice(
        index=0,
        message=message,
        finish_reason="tool_calls",
    )
    return ChatCompletion(
        id="chatcmpl-normal",
        choices=[choice],
        created=1776171173,
        model="gpt-4",
        object="chat.completion",
    )


class TestCreateChatResultNormalFormat:
    """Tests for normal OpenAI-compatible response format with tool_calls."""

    def test_returns_chat_result(self, chat_model, normal_tool_call_response):
        """_create_chat_result should return a ChatResult."""
        from langchain_core.outputs import ChatResult

        result = chat_model._create_chat_result(normal_tool_call_response)
        assert isinstance(result, ChatResult)

    def test_result_has_one_generation(self, chat_model, normal_tool_call_response):
        """There should be exactly one generation in the result."""
        result = chat_model._create_chat_result(normal_tool_call_response)
        assert len(result.generations) == 1

    def test_message_is_ai_message(self, chat_model, normal_tool_call_response):
        """The generation message should be an AIMessage."""
        from langchain_core.messages import AIMessage

        result = chat_model._create_chat_result(normal_tool_call_response)
        message = result.generations[0].message
        assert isinstance(message, AIMessage)

    def test_tool_calls_are_parsed(self, chat_model, normal_tool_call_response):
        """Standard tool_calls field should be correctly parsed into message.tool_calls."""
        result = chat_model._create_chat_result(normal_tool_call_response)
        message = result.generations[0].message

        assert len(message.tool_calls) == 1
        tool_call = message.tool_calls[0]
        assert tool_call["name"] == "read_file"
        assert tool_call["args"]["file_path"] == "/app/scripts/fetch_logs.py"

    def test_tool_calls_also_in_additional_kwargs(self, chat_model, normal_tool_call_response):
        """tool_calls should also appear in additional_kwargs for backward compat."""
        result = chat_model._create_chat_result(normal_tool_call_response)
        message = result.generations[0].message

        assert "tool_calls" in message.additional_kwargs
        assert len(message.additional_kwargs["tool_calls"]) == 1


class TestCreateChatResultReasoningContentFormat:
    """Tests for abnormal response format where tool calls are in reasoning_content.

    NOTE: The tests marked with @pytest.mark.xfail document the expected behavior
    AFTER the bug is fixed. When the bug is fixed:
    1. Remove the @pytest.mark.xfail decorator from the tests
    2. They should pass immediately
    """

    def test_returns_chat_result(self, chat_model, kimi_25_response):
        """_create_chat_result returns a ChatResult even for abnormal format."""
        from langchain_core.outputs import ChatResult

        result = chat_model._create_chat_result(kimi_25_response)
        assert isinstance(result, ChatResult)

    def test_result_has_one_generation(self, chat_model, kimi_25_response):
        """There should be exactly one generation in the result."""
        result = chat_model._create_chat_result(kimi_25_response)
        assert len(result.generations) == 1

    def test_message_is_ai_message(self, chat_model, kimi_25_response):
        """The generation message should be an AIMessage."""
        from langchain_core.messages import AIMessage

        result = chat_model._create_chat_result(kimi_25_response)
        message = result.generations[0].message
        assert isinstance(message, AIMessage)

    def test_reasoning_content_saved_in_additional_kwargs(self, chat_model, kimi_25_response):
        """reasoning_content is saved to additional_kwargs (documents current behavior)."""
        result = chat_model._create_chat_result(kimi_25_response)
        message = result.generations[0].message

        assert "reasoning_content" in message.additional_kwargs
        assert "<|tool_calls_section_begin|>" in message.additional_kwargs["reasoning_content"]

    @pytest.mark.xfail(reason="BUG: tool_calls not parsed from reasoning_content yet")
    def test_tool_calls_should_be_parsed_from_reasoning_content(self, chat_model, kimi_25_response):
        """EXPECTED BEHAVIOR AFTER FIX: tool_calls should be parsed from reasoning_content.

        When the fix is implemented, remove this xfail marker - the test should pass.
        """
        result = chat_model._create_chat_result(kimi_25_response)
        message = result.generations[0].message
        print(message)

        assert len(message.tool_calls) > 0, (
            "After fix: tool_calls should be parsed from reasoning_content"
        )
        tool_call = message.tool_calls[0]
        assert tool_call["name"] == "read_file"
        assert tool_call["args"]["file_path"] == "/app/scripts/fetch_logs.py"
        assert tool_call["args"]["target_runtime"] == "paas_sandbox_bk-data-fetcher"

    @pytest.mark.xfail(reason="BUG: empty tool_calls breaks ReAct _should_continue routing")
    def test_empty_tool_calls_breaks_react_routing(self, chat_model, kimi_25_response):
        """Demonstrates WHY the bug matters.

        In ReActAgentBuilder._should_continue, the routing logic checks:
            if isinstance(last_message, AIMessage) and last_message.tool_calls:
                return "tools"

        When tool_calls is empty, _should_continue returns "end" instead of "tools",
        causing the agent to stop prematurely.

        After fix, the AIMessage should have tool_calls populated.
        """
        result = chat_model._create_chat_result(kimi_25_response)
        message = result.generations[0].message

        assert len(message.tool_calls) > 0, (
            "tool_calls must be populated for ReAct routing to work correctly"
        )


class TestCreateChatResultResponseTypes:
    """Tests for handling different response types."""

    def test_response_without_reasoning_content(self, chat_model):
        """Response without reasoning_content field works normally."""
        message = ChatCompletionMessage(role="assistant", content="Hello, world!")
        choice = Choice(index=0, message=message, finish_reason="stop")
        response = ChatCompletion(
            id="test-id",
            choices=[choice],
            created=1234567890,
            model="test-model",
            object="chat.completion",
        )

        result = chat_model._create_chat_result(response)
        message_result = result.generations[0].message
        assert message_result.content == "Hello, world!"
        assert "reasoning_content" not in message_result.additional_kwargs

    def test_dict_response_not_processed(self, chat_model):
        """When response is a dict (not openai.BaseModel), only parent logic runs.

        The isinstance(response, openai.BaseModel) check skips reasoning_content
        processing for dict responses.
        """
        response = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello",
                        "reasoning_content": "some reasoning",
                    }
                }
            ]
        }

        result = chat_model._create_chat_result(response)
        message = result.generations[0].message

        assert "reasoning_content" not in message.additional_kwargs

    def test_multiple_tool_calls_in_reasoning_content(self, chat_model):
        """reasoning_content with multiple tool calls is saved to additional_kwargs."""
        reasoning_content = (
            " <|tool_calls_section_begin|>"
            " <|tool_call_begin|> functions.read_file:3"
            " <|tool_call_argument_begin|>"
            '{"file_path": "/app/scripts/fetch_logs.py"}'
            " <|tool_call_end|>"
            " <|tool_call_begin|> functions.write_file:4"
            " <|tool_call_argument_begin|>"
            '{"file_path": "/app/scripts/output.txt", "content": "done"}'
            " <|tool_call_end|>"
            " <|tool_calls_section_end|>"
        )

        message = ChatCompletionMessage(
            role="assistant",
            content=None,
            reasoning_content=reasoning_content,
        )
        choice = Choice(index=0, message=message, finish_reason="stop")
        response = ChatCompletion(
            id="test-multi",
            choices=[choice],
            created=1776171173,
            model="kimi-25",
            object="chat.completion",
        )

        result = chat_model._create_chat_result(response)
        message_result = result.generations[0].message

        # reasoning_content should be saved regardless of tool_calls parsing
        assert "reasoning_content" in message_result.additional_kwargs
        assert "functions.read_file" in message_result.additional_kwargs["reasoning_content"]
        assert "functions.write_file" in message_result.additional_kwargs["reasoning_content"]
