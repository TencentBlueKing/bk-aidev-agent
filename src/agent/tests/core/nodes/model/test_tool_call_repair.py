# -*- coding: utf-8 -*-

from aidev_agent.core.nodes.model.tool_call_repair import (
    parse_standalone_plain_text_tool_call_blocks,
)
from aidev_agent.core.nodes.model.utils import (
    extract_text_from_content,
    promote_plain_text_tool_call_message,
    should_promote_message,
)
from langchain_core.messages import AIMessage

# ---------------------------------------------------------------------------
# TestParseBracketFormat
# ---------------------------------------------------------------------------


class TestParseBracketFormat:
    def test_bracket_format_simple(self):
        text = '[read_file]\n{"file_path": "/app/main.py"}'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments == {"file_path": "/app/main.py"}

    def test_bracket_tool_prefix(self):
        text = '[tool:read_file]{"file_path": "/app/main.py"}'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments == {"file_path": "/app/main.py"}

    def test_bracket_with_closing_marker(self):
        text = '[read_file]\n{"file_path": "/app"}\n[/read_file]'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is not None
        assert len(result) == 1
        assert result[0].arguments == {"file_path": "/app"}

    def test_bracket_unknown_tool(self):
        text = '[unknown_tool]\n{"arg": "val"}'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is None

    def test_bracket_mixed_content(self):
        text = 'some text [read_file]\n{"file_path": "/app"}'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is None


# ---------------------------------------------------------------------------
# TestParseHarmonyFormat
# ---------------------------------------------------------------------------


class TestParseHarmonyFormat:
    def test_harmony_simple(self):
        text = 'commentary to=read_file code\n{"file_path": "/app"}'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments == {"file_path": "/app"}

    def test_harmony_with_channel(self):
        text = '<|channel|>analysis to=read_file code<|message|>\n{"file_path": "/app"}'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is not None
        assert result[0].name == "read_file"
        assert result[0].arguments == {"file_path": "/app"}

    def test_harmony_with_call_marker(self):
        text = 'commentary to=read_file code\n{"file_path": "/app"}\n<|call|>'
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is not None
        assert result[0].name == "read_file"
        assert result[0].arguments == {"file_path": "/app"}


# ---------------------------------------------------------------------------
# TestParseXmlFormat
# ---------------------------------------------------------------------------


class TestParseXmlFormat:
    def test_xml_simple(self):
        text = "<function=read_file><parameter=file_path>/app/main.py</parameter></function>"
        result = parse_standalone_plain_text_tool_call_blocks(text, {"read_file"})
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "read_file"
        assert result[0].arguments == {"file_path": "/app/main.py"}

    def test_xml_multiple_params(self):
        text = (
            "<function=write_file>"
            "<parameter=file_path>/app/main.py</parameter>"
            "<parameter=content>hello</parameter>"
            "</function>"
        )
        result = parse_standalone_plain_text_tool_call_blocks(text, {"write_file"})
        assert result is not None
        assert result[0].arguments == {"file_path": "/app/main.py", "content": "hello"}

    def test_xml_no_whitespace_between_params(self):
        """Regression: no infinite loop when parameters have no whitespace between them."""
        text = "<function=f><parameter=a></parameter><parameter=b></parameter></function>"
        result = parse_standalone_plain_text_tool_call_blocks(text, {"f"})
        assert result is not None
        assert result[0].arguments == {"a": "", "b": ""}

    def test_xml_typed_values(self):
        """XML parameters that look like JSON should be parsed as typed values."""
        text = "<function=f><parameter=count>42</parameter><parameter=name>test</parameter></function>"
        result = parse_standalone_plain_text_tool_call_blocks(text, {"f"})
        assert result is not None
        assert result[0].arguments["count"] == 42
        assert result[0].arguments["name"] == "test"


# ---------------------------------------------------------------------------
# TestPromoteMessage
# ---------------------------------------------------------------------------


class TestPromoteMessage:
    def test_should_promote_text_only(self):
        msg = AIMessage(content="hello")
        assert should_promote_message(msg, {"read_file"}) is True

    def test_should_not_promote_with_tool_calls(self):
        msg = AIMessage(content="hello", tool_calls=[{"name": "x", "args": {}, "id": "1"}])
        assert should_promote_message(msg, {"read_file"}) is False

    def test_should_not_promote_empty_tools(self):
        msg = AIMessage(content="hello")
        assert should_promote_message(msg, set()) is False

    def test_promote_success(self):
        text = '[read_file]\n{"file_path": "/app"}'
        msg = AIMessage(content=text)
        result = promote_plain_text_tool_call_message(msg, {"read_file"})
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "read_file"

    def test_promote_failure(self):
        msg = AIMessage(content="some mixed text here")
        result = promote_plain_text_tool_call_message(msg, {"read_file"})
        assert result is msg

    def test_promote_changes_metadata(self):
        text = '[read_file]\n{"file_path": "/app"}'
        msg = AIMessage(content=text)
        result = promote_plain_text_tool_call_message(msg, {"read_file"})
        assert result.response_metadata.get("promoted_from_plain_text") is True

    def test_promote_preserves_list_content(self):
        """WR-04: promotion preserves non-text content blocks."""
        text = '[read_file]\n{"file_path": "/app"}'
        content_list = [{"type": "text", "text": text}, {"type": "image_url", "url": "http://example.com/img"}]
        msg = AIMessage(content=content_list)
        result = promote_plain_text_tool_call_message(msg, {"read_file"})
        assert len(result.tool_calls) == 1
        # Original list content is preserved
        assert isinstance(result.content, list)
        assert len(result.content) == 2


# ---------------------------------------------------------------------------
# TestExtractTextFromContent (WR-05)
# ---------------------------------------------------------------------------


class TestExtractTextFromContent:
    def test_string_content(self):
        assert extract_text_from_content("hello world") == "hello world"

    def test_string_content_stripped(self):
        assert extract_text_from_content("  hello  ") == "hello"

    def test_empty_string_returns_none(self):
        assert extract_text_from_content("") is None

    def test_whitespace_only_returns_none(self):
        assert extract_text_from_content("   \n\t  ") is None

    def test_list_of_dicts_with_text(self):
        content = [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}]
        assert extract_text_from_content(content) == "hello world"

    def test_list_of_dicts_mixed_types(self):
        """Only text blocks are extracted; image_url and other types are skipped."""
        content = [
            {"type": "text", "text": "look at this:"},
            {"type": "image_url", "url": "http://example.com/img"},
            {"type": "text", "text": " nice"},
        ]
        assert extract_text_from_content(content) == "look at this: nice"

    def test_list_of_dicts_no_text_blocks(self):
        content = [{"type": "image_url", "url": "http://example.com/img"}]
        assert extract_text_from_content(content) is None

    def test_list_of_dicts_empty_text(self):
        content = [{"type": "text", "text": ""}, {"type": "text", "text": "   "}]
        assert extract_text_from_content(content) is None

    def test_non_string_non_list_returns_none(self):
        assert extract_text_from_content(42) is None
        assert extract_text_from_content(None) is None
