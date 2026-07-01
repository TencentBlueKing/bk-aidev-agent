# -*- coding: utf-8 -*-
"""TDD tests for aidev_agent.core.nodes.model.utils (CR #1 extraction).

These tests verify that the 7 helper functions + 2 regex constants were
correctly migrated to utils.py and remain behaviorally identical.
"""

from aidev_agent.core.nodes.model.utils import (
    detect_thinking_exhaustion,
    has_content_after_think_block,
    has_inline_thinking,
    has_prior_tool_results,
    is_truncated,
    promote_plain_text_tool_call_message,
    strip_think_blocks,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


class TestUtilsImports:
    """Verify all 7 functions are importable from utils."""

    def test_strip_think_blocks_importable(self):
        assert callable(strip_think_blocks)

    def test_has_inline_thinking_importable(self):
        assert callable(has_inline_thinking)

    def test_has_content_after_think_block_importable(self):
        assert callable(has_content_after_think_block)

    def test_detect_thinking_exhaustion_importable(self):
        assert callable(detect_thinking_exhaustion)

    def test_is_truncated_importable(self):
        assert callable(is_truncated)

    def test_has_prior_tool_results_importable(self):
        assert callable(has_prior_tool_results)

    def test_promote_plain_text_tool_call_message_importable(self):
        assert callable(promote_plain_text_tool_call_message)


class TestUtilsBehavior:
    """Verify migrated functions behave identically."""

    def test_strip_think_blocks_removes_block(self):
        assert strip_think_blocks("<think>x</think>") == ""

    def test_has_content_after_think_block_true(self):
        assert has_content_after_think_block("<think>x</think>visible") is True

    def test_has_content_after_think_block_false(self):
        assert has_content_after_think_block("<think>x</think>") is False

    def test_detect_thinking_exhaustion_true(self):
        assert detect_thinking_exhaustion("<think>lots</think>") is True

    def test_detect_thinking_exhaustion_false(self):
        assert detect_thinking_exhaustion("<think>lots</think>answer") is False

    def test_is_truncated_length(self):
        msg = AIMessage(content="x", response_metadata={"finish_reason": "length"})
        assert is_truncated(msg) is True

    def test_is_truncated_stop(self):
        msg = AIMessage(content="x", response_metadata={"finish_reason": "stop"})
        assert is_truncated(msg) is False

    def test_has_prior_tool_results_true(self):
        msgs = [HumanMessage(content="q"), ToolMessage(content="r", tool_call_id="1"), AIMessage(content="a")]
        assert has_prior_tool_results(msgs) is True

    def test_has_prior_tool_results_false(self):
        msgs = [HumanMessage(content="q"), AIMessage(content="a")]
        assert has_prior_tool_results(msgs) is False

    def test_promote_plain_text_tool_call_message(self):
        msg = AIMessage(content='[read_file]\n{"file_path": "/app"}')
        result = promote_plain_text_tool_call_message(msg, {"read_file"})
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "read_file"
