# -*- coding: utf-8 -*-
import pytest
from aidev_agent.core.nodes.model.handoff_ledger import format_message
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

LEDGER = [
    HumanMessage(content="查 pod", id="u0"),
    AIMessage(
        content="",
        id="a1",
        tool_calls=[
            {"id": "c1", "name": "ListPo", "args": {"namespace": "dev"}},
            {"id": "c2", "name": "ListPo", "args": {"namespace": "test"}},
        ],
    ),
    ToolMessage(content="test-pods", tool_call_id="c2", id="t2"),
    ToolMessage(content="orphan", tool_call_id="missing", id="t3"),
]


@pytest.mark.parametrize(
    "index, expected",
    [
        (2, '[#2|t2|tool|-] (返回自: ListPo({"namespace": "test"}))\ntest-pods'),
        (3, "[#3|t3|tool|-] orphan"),
    ],
)
def test_format_message(index, expected):
    assert format_message(LEDGER, index) == expected
