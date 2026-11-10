"""Visible XML examples remain complete evidence after reasoning removal."""

import asyncio
import json
import time
from unittest.mock import MagicMock

import pytest
from aidev_agent.core.tools.memory import PersonalMemoryRuntime
from aidev_agent.services.agent.memory import completed_history
from aidev_agent.utils.message_text import strip_think_blocks
from langchain_core.messages import AIMessage

from .test_memory_native_source import capture, persisted_events, source_manager


@pytest.mark.parametrize(
    "literal",
    [
        "```xml\n<think>example</think>\n```",
        "~~~xml\n<thinking>example</thinking>\n~~~",
        "````xml\n```\n<reasoning>example</reasoning>\n```\n````",
        "```xml\n<think>example</think>\n````",
        "`````xml\n<think>example</think>\n```\n`````",
        "```xml\n<think>unfinished literal\n```",
        "```xml\n<think>example</think>",
        "```xml\r\n<think>example</think>\r\n```\r\n",
        "Use `<think>example</think>` as literal XML.",
        "Use ``<think>`example`</think>`` as literal XML.",
        "`<think>multiline\nexample</think>`",
        "> <think>quoted example</think>",
        "    <think>indented example</think>",
        "\t<think>tab-indented example</think>",
        r"\<think>escaped example</think>",
        "&lt;think&gt;escaped example&lt;/think&gt;",
    ],
)
def test_reasoning_removal_preserves_markdown_literals(literal):
    expected = literal.rstrip() if literal.startswith(("    ", "\t")) else literal.strip()
    normalized = strip_think_blocks(literal)
    assert normalized == expected
    assert strip_think_blocks("<think>Discarded draft</think>\n" + literal) == expected
    assert strip_think_blocks(normalized) == normalized


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Before <think>hidden</think> after", "Before  after"),
        ("<THINK>hidden</think>Final", "Final"),
        ("<thinking>hidden</thinking><reasoning>hidden</reasoning>Final", "Final"),
        ("<think>Draft with an unfinished ``` fence</think>Final", "Final"),
        (
            "```xml\n<think>unclosed example\n```\n<think>hidden</think>Final",
            "```xml\n<think>unclosed example\n```\nFinal",
        ),
        ("`<think>example</think>`<think>hidden</think>Final", "`<think>example</think>`Final"),
        ("An unmatched ` marker <think>hidden</think>Final", "An unmatched ` marker Final"),
        ("`unclosed\n\n<think>hidden</think>Final", "`unclosed\n\nFinal"),
        ("A ~~~ marker <think>hidden</think>Final", "A ~~~ marker Final"),
        ("<think>unclosed", "<think>unclosed"),
        ("<think>unclosed <thinking>hidden</thinking>Final", "<think>unclosed Final"),
        (r"Use `\` as literal XML: <think>hidden</think>Final", r"Use `\` as literal XML: Final"),
    ],
)
def test_real_reasoning_is_removed_without_literal_delimiter_leaks(text, expected):
    assert strip_think_blocks(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Example: " + "`" * 32000 + "x",
        " ".join("`" * length for length in range(1, 300)),
        "<think>" * 4000 + "unfinished",
        "```xml\n<think>literal</think>\n```\n" * 1000,
    ],
    ids=["long-run", "distinct-unmatched-runs", "unclosed-reasoning", "many-fenced-blocks"],
)
def test_large_unmatched_delimiters_and_many_blocks_preserve_text(text):
    assert strip_think_blocks(text) == text.strip()


@pytest.mark.asyncio
async def test_long_unmatched_code_does_not_starve_sibling_chat_task():
    text = "Example: " + "`" * 32000 + "x"
    gaps = []
    finished = asyncio.Event()

    async def sibling():
        previous = time.monotonic()
        while not finished.is_set():
            await asyncio.sleep(0.001)
            now = time.monotonic()
            gaps.append(now - previous)
            previous = now

    ticker = asyncio.create_task(sibling())
    await asyncio.sleep(0.01)
    try:
        _, answer = await capture(text, False, False)
        assert answer.content == text
    finally:
        finished.set()
        await ticker
    # Generous regression guard against seconds of synchronous backtracking,
    # not a latency budget for the model or production chat service.
    assert gaps and max(gaps) < 0.5


@pytest.mark.parametrize("promote", [False, True])
@pytest.mark.parametrize("hidden", [False, True])
@pytest.mark.parametrize(
    "literal",
    [
        "```xml\n<think>example</think>\n```",
        "Use `<reasoning>example</reasoning>`.",
        "Note:\n    <think>example</think>",
    ],
)
def test_visible_literal_survives_current_writer_history_and_reference_audit(promote, hidden, literal):
    text = ("<think>Discarded private draft</think>\n" if hidden else "") + literal
    events, answer = asyncio.run(capture(text, False, promote))
    rows, manager = persisted_events(events), source_manager()
    runtime = PersonalMemoryRuntime(
        lambda _: {
            "username": "alice",
            "agent_code": "agent",
            "session_id": "s",
            "session_date": "2026-10-22",
            "messages": [],
        },
        manager=manager,
        schemas=manager.memory_schemas.return_value,
    )
    runtime.complete({"messages": [answer]}, {})
    current = manager.complete_memory_round.call_args.args[0]["context"]["messages"]
    restored = completed_history(
        [{**row, "builtin_property": row["property"]["builtin_property"]} for row in rows], "s"
    )
    expected = ("\n" if hidden else "") + literal
    assert restored == current and current[0]["text"] == expected
    assert rows[0]["content"] == answer.content.strip()
    audit = MagicMock()
    audit.invoke.return_value = AIMessage(content='{"memory_ids":[]}')
    runtime.reference_model = audit
    assert runtime.referenced_ids(answer, [{"memory_id": "m", "text": "example"}]) == []
    audited = json.loads(audit.invoke.call_args.args[0][-1].content)
    assert audited["answer"] == expected
