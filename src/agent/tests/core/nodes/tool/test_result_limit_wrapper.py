# -*- coding: utf-8 -*-
"""Tests for the tool-result limit wrapper (aidev_agent.core.nodes.tool.result_limit_wrapper)."""

from __future__ import annotations

from types import SimpleNamespace

from aidev_agent.core.nodes.tool.result_limit_wrapper import (
    TOOL_RESULT_TOO_LONG_MESSAGE,
    build_result_limit_sync_wrapper,
)
from langchain_core.messages import ToolMessage


def _make_request(name: str) -> SimpleNamespace:
    return SimpleNamespace(tool_call={"name": name, "id": "id-1"}, tool=None, state={})


class TestResultLimitWrapper:
    def test_short_result_unchanged(self):
        wrapper = build_result_limit_sync_wrapper(100)
        msg = ToolMessage(content="short", tool_call_id="id-1", name="t")
        result = wrapper(_make_request("t"), lambda _req: msg)
        assert result.content == "short"

    def test_long_string_replaced_with_reject_message(self):
        wrapper = build_result_limit_sync_wrapper(100)
        content = "HEAD-" + "M" * 1000 + "-TAIL"
        msg = ToolMessage(content=content, tool_call_id="id-1", name="t")
        result = wrapper(_make_request("t"), lambda _req: msg)
        assert result.content == TOOL_RESULT_TOO_LONG_MESSAGE
        assert result.status == "error"

    def test_custom_reject_message(self):
        wrapper = build_result_limit_sync_wrapper(10, reject_message="too long")
        msg = ToolMessage(content="x" * 100, tool_call_id="id-1", name="t")
        result = wrapper(_make_request("t"), lambda _req: msg)
        assert result.content == "too long"
        assert result.status == "error"

    def test_structured_content_over_limit_rejected(self):
        wrapper = build_result_limit_sync_wrapper(10)
        msg = ToolMessage(content=[{"type": "text", "text": "x" * 100}], tool_call_id="id-1", name="t")
        result = wrapper(_make_request("t"), lambda _req: msg)
        assert result.content == TOOL_RESULT_TOO_LONG_MESSAGE
        assert result.status == "error"
