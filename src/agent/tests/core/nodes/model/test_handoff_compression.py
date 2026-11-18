# -*- coding: utf-8 -*-
"""完整 Handoff 交接视图回归测试。"""

import concurrent.futures
import contextvars
import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.ag_ui.types import CONTEXT_COMPRESSION_TAG
from aidev_agent.core.nodes.model.basic_middleware import (
    BaseVariablesMiddleware,
    DeepSeekR1VariablesMiddleware,
    SpecialVariablesMiddleware,
)
from aidev_agent.core.nodes.model.context_assembly import ContextAssembly
from aidev_agent.core.nodes.model.handoff import (
    HANDOFF_DONE_TEXT,
    HANDOFF_FAILED_TEXT,
    HandoffCompressionError,
    HandoffCompressionMiddleware,
    _estimate_tokens,
    dump_round,
    load_round,
    parse_handoff_summary,
    render_handoff_summary,
)
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext, PromptSlots
from aidev_agent.packages.opentelemetry.context_obs import CompressionCall
from aidev_agent.pydantic_models import HandoffSettings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import StructuredTool

SUMMARY_JSON = {"task_goal": "完成长任务。", "items": [], "key_message_indexes": []}
SUMMARY_TEXT = json.dumps(SUMMARY_JSON, ensure_ascii=False)
RENDERED = "## 任务目标\n完成长任务。\n\n## 已完成事项\n无\n\n## 进行中事项\n无\n\n## 待办事项\n无\n\n## 关键上下文\n无"
USER_BLOCK = "\n\n## 最近用户输入\n[#1|user|user|-] 完成任务"

TOOL_RESULT_0 = '[#3|t0|tool|-] (返回自: work({"step": 0}))\nresult-0'


@pytest.fixture(autouse=True)
def precise_trigger_count(monkeypatch):
    """用例以模拟的精确计数驱动触发，关闭本地估算粗筛。"""
    monkeypatch.setattr("aidev_agent.core.nodes.model.handoff._ESTIMATE_SKIP_RATIO", 0)


def is_handoff_view(msgs):
    return any(
        isinstance(msg, HumanMessage) and (
            str(msg.content).strip().startswith(("## 任务目标", "已经调用过的工具")) or not str(msg.content).strip()
        )
        for msg in msgs
    )


def interaction(count):
    messages = [SystemMessage(content="固定系统约束", id="system"), HumanMessage(content="完成任务", id="user")]
    for index in range(count):
        messages.extend([
            AIMessage(content="", id=f"a{index}", tool_calls=[{"name": "work", "args": {"step": index}, "id": f"c{index}"}]),
            ToolMessage(content=f"result-{index}", id=f"t{index}", tool_call_id=f"c{index}"),
        ])
    return messages


def view(ctx):
    return "\n".join(str(msg.content) for msg in ctx.chat_prompt_template.invoke(ctx.variables).to_messages())


def make_ctx(messages, *, token_len=1000, structured=False):
    slots = PromptSlots(
        system="SYS {{history_system_prompt}}",
        human="{{query}} {{agent_scratchpad}}" if structured else "{{query}}",
        agent_scratchpad_slot=not structured,
    )
    template = ContextAssembly._assemble_template(slots)
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content=SUMMARY_TEXT)
    llm.get_num_tokens.return_value = 10
    llm.get_num_tokens_from_messages.side_effect = lambda msgs: 500 if is_handoff_view(msgs) else token_len
    ctx = ProcessorContext(state={"messages": list(messages)}, config={}, llm=llm, chat_prompt_template=template)
    BaseVariablesMiddleware()(ctx, lambda: None)
    SpecialVariablesMiddleware(
        use_structured_response=structured, use_general_knowledge_on_miss=False, rejection_message="no",
    )(ctx, lambda: None)
    return ctx


def middleware(timeout=60, **kwargs):
    return HandoffCompressionMiddleware(HandoffSettings(**kwargs), token_limit=1000, token_margin=100, timeout=timeout)


def run(ctx, **kwargs):
    middleware(**kwargs)(ctx, lambda: None)


def parse(text, previous=None, valid=range(4)):
    return parse_handoff_summary(text, previous_items=previous or {}, valid_indexes=set(valid), round_no=2)


@pytest.mark.parametrize("text", [SUMMARY_TEXT, f"```json\n{SUMMARY_TEXT}\n```"])
def test_summary_json_is_parsed(text):
    assert parse(text)["task_goal"] == "完成长任务。"


@pytest.mark.parametrize("patch_", [{"items": 1}, {"items": [{"section": "x", "text": "t"}]}, {"items": [{"section": "todo", "text": " "}]}])
def test_invalid_summary_is_rejected(patch_):
    assert parse("无标题") is None and parse(json.dumps({**SUMMARY_JSON, **patch_})) is None


def test_kept_items_are_copied_verbatim_and_unknown_dropped():
    previous = {"R1-1": {"id": "R1-1", "section": "todo", "text": "原文条目"}}
    raw = [{"section": "completed", "text": "新"}, {"id": "R1-1", "text": "改写"}, {"id": "R1-1"}, {"id": "R1-9"}]
    items = parse(json.dumps({**SUMMARY_JSON, "items": raw}), previous)["items"]
    assert items == [{"id": "R2-1", "section": "completed", "text": "新"}, previous["R1-1"]]


def test_key_messages_bounded_and_user_messages_spliced():
    messages = interaction(2)
    parsed = parse(json.dumps({**SUMMARY_JSON, "key_message_indexes": [1, 3, 3, 9, True]}))
    assert parsed["key_message_indexes"] == [1, 3]
    rendered = render_handoff_summary(parsed, messages, [1])
    assert rendered == RENDERED + "\n\n## 关键原文\n" + TOOL_RESULT_0 + USER_BLOCK


@pytest.mark.parametrize("count", [0, 1, 2])
def test_tail_keeps_complete_interactions(count):
    messages = interaction(4)
    groups = [index for index, msg in enumerate(messages) if not isinstance(msg, (SystemMessage, ToolMessage))]
    start = middleware(keep_last=count)._tail_start(messages, groups, 0, 10**6)
    assert messages[start:] == (messages[-2 * count:] if count else [])
    assert start == len(messages) - 2 * count


@pytest.mark.parametrize("structured", [True, False])
def test_tool_loop_after_handoff_keeps_original_messages(structured):
    messages = interaction(5)
    ctx = make_ctx(messages, structured=structured)
    run(ctx, keep_last=2)
    assert ctx.variables["chat_history"] == []
    assert ctx.variables["query"] == RENDERED + USER_BLOCK
    rendered = ctx.chat_prompt_template.invoke(ctx.variables).to_messages()
    assert isinstance(rendered[0], SystemMessage) and "固定系统约束" in rendered[0].content
    if structured:
        assert "result-3" in ctx.variables["agent_scratchpad"] and "result-2" not in ctx.variables["agent_scratchpad"]
    else:
        assert ctx.variables["agent_scratchpad"] == messages[-4:]
        assert [type(msg) for msg in rendered[1:]] == [HumanMessage, AIMessage, ToolMessage, AIMessage, ToolMessage]
    assert ctx.state["messages"] == messages


def test_multiple_users_are_not_compression_boundaries():
    messages = interaction(3) + [HumanMessage(content="继续任务", id="next")] + interaction(2)[2:]
    ctx = make_ctx(messages)
    run(ctx, keep_last=1)
    assert "## 最近用户输入\n[#1|user|user|-] 完成任务\n[#8|next|user|-] 继续任务" in view(ctx)
    assert "继续任务" in ctx.llm.invoke.call_args.args[0][1].content
    assert ctx.variables["chat_history"] == [] and ctx.variables["agent_scratchpad"] == messages[-2:]


@pytest.mark.parametrize("tokens, expected", [(899, False), (900, True)])
def test_trigger_boundary(tokens, expected):
    ctx = make_ctx(interaction(2), token_len=tokens)
    run(ctx, keep_last=1)
    assert ("_handoff_state_update" in ctx.metadata) is expected


def test_user_without_earlier_history_can_be_handed_off():
    ctx = make_ctx([HumanMessage(content="任务", id="user")])
    run(ctx, keep_last=0)
    assert ctx.variables["query"] == RENDERED + "\n\n## 最近用户输入\n[#0|user|user|-] 任务"


def test_tail_is_selected_before_summary_and_bounded_by_rendered_chars():
    ctx = make_ctx(interaction(4))
    run(ctx, keep_last=3, tail_char_limit=1)
    assert ctx.variables["query"] == RENDERED + USER_BLOCK
    assert "result-3" in ctx.llm.invoke.call_args.args[0][1].content
    assert ctx.metadata["_handoff_state_update"]["rounds"][0]["searchable_until"] == "t3"


def test_summary_excludes_retained_tail():
    ctx = make_ctx(interaction(4))
    run(ctx, keep_last=2)
    prompt = ctx.llm.invoke.call_args.args[0][1].content
    assert "result-1" in prompt
    assert "result-2" not in prompt and "result-3" not in prompt
    assert "result-2" in view(ctx) and "result-3" in view(ctx)
    assert ctx.metadata["_handoff_state_update"]["rounds"][0]["searchable_until"] == "t1"


def test_checkpoint_view_keeps_new_interactions_as_messages():
    messages = interaction(4)
    first = make_ctx(messages)
    run(first, keep_last=1)
    additions = [AIMessage(content="新增响应", id="new-ai"), HumanMessage(content="新增用户", id="new-user")]
    second = make_ctx(messages + additions, token_len=500)
    second.state["handoff"] = first.metadata["_handoff_state_update"]
    run(second, keep_last=1)
    assert "result-3" in view(second)
    assert "新增响应" in view(second) and "新增用户" in view(second)
    assert "result-2" not in view(second)
    assert [msg.id for msg in second.variables["chat_history"][1:]] == ["a3", "t3", "new-ai"]
    assert second.variables["query"] == "新增用户" and second.variables["agent_scratchpad"] == []
    second.llm.invoke.assert_not_called()


def test_recompression_uses_previous_summary_and_newly_covered_records():
    first = make_ctx(interaction(4))
    run(first, keep_last=1)
    second = make_ctx(interaction(6))
    second.state["handoff"] = first.metadata["_handoff_state_update"]
    counts = iter([1000])
    second.llm.get_num_tokens_from_messages.side_effect = lambda msgs: next(counts, 500)
    run(second, keep_last=1)
    prompt = second.llm.invoke.call_args.args[0][1].content
    assert "## 当前任务目标（进行中，默认继续有效）\n完成长任务。" in prompt and RENDERED not in prompt
    assert "## 用户输入原文\n[#1|user|user|-] 完成任务" in prompt
    assert "result-3" in prompt and "result-4" in prompt
    assert "result-0" not in prompt and "result-5" not in prompt
    assert len(second.metadata["_handoff_state_update"]["rounds"]) == 2


def second_round(prev_json, key_ids=("t0",)):
    first = make_ctx(interaction(4))
    first.llm.invoke.return_value = AIMessage(content=json.dumps(prev_json, ensure_ascii=False))
    run(first, keep_last=1)
    first.metadata["_handoff_state_update"]["rounds"][0]["key_message_ids"] = list(key_ids)
    second = make_ctx(interaction(6))
    second.state["handoff"] = first.metadata["_handoff_state_update"]
    counts = iter([1000])
    second.llm.get_num_tokens_from_messages.side_effect = lambda msgs: next(counts, 500)
    return second


def test_second_round_keeps_selected_items_and_key_messages():
    prev = {**SUMMARY_JSON, "items": [{"section": "todo", "text": "旧待办"}, {"section": "completed", "text": "已结束"}]}
    second = second_round(prev)
    second.llm.invoke.return_value = AIMessage(
        content=json.dumps({**SUMMARY_JSON, "items": [{"id": "R1-1"}], "key_message_indexes": [3, 0]})
    )
    run(second, keep_last=1)
    prompt = second.llm.invoke.call_args.args[0][1].content
    assert "[R1-1|todo] 旧待办" in prompt and TOOL_RESULT_0 in prompt
    query = view(second)
    assert "- 旧待办" in query and "已结束" not in query and TOOL_RESULT_0 in query
    assert second.metadata["_handoff_state_update"]["rounds"][-1]["key_message_ids"] == ["t0"]


def test_second_round_without_new_range_reselects_previous_handoff():
    second = second_round(SUMMARY_JSON)
    run(second, keep_last=20)
    assert "## 新增原文\n无" in second.llm.invoke.call_args.args[0][1].content
    assert len(second.metadata["_handoff_state_update"]["rounds"]) == 2


def test_token_fit_moves_whole_group_into_summary():
    messages = interaction(4)
    messages[7].content = "result-2" + "x" * 2000  # 估算约 500 token，超出尾部预算 (900 - 300) × 0.7 = 420
    ctx = make_ctx(messages)
    counts = iter([1000])
    ctx.llm.get_num_tokens_from_messages.side_effect = lambda msgs: next(counts, None) or 300
    run(ctx, keep_last=2)
    assert ctx.llm.get_num_tokens_from_messages.call_count == 3  # 触发判定、固定开销、提交前校验
    assert "result-2" not in view(ctx) and "result-3" in view(ctx)
    assert "result-2" in ctx.llm.invoke.call_args.args[0][1].content
    ctx.llm.invoke.assert_called_once()


@pytest.mark.parametrize("existing", [False, True])
def test_failure_restores_all_slots_and_does_not_commit(existing):
    ctx = make_ctx(interaction(4))
    if existing:
        ctx.state["handoff"] = {"rounds": [{"summary": "old", "searchable_until": "t0"}], "active_round": 0}
    before = dict(ctx.variables)
    state = dict(ctx.state)
    ctx.llm.invoke.side_effect = RuntimeError("failure")
    next_step = MagicMock()
    with (patch("aidev_agent.core.nodes.model.handoff.time.sleep"),
          patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record):
        middleware(keep_last=1)(ctx, next_step)
    # 摘要重试耗尽不中断请求：回到原视图并套用已生效的交接
    assert ctx.state == state and "_handoff_state_update" not in ctx.metadata
    assert view(ctx).startswith("SYS") and ("old" in view(ctx)) is existing
    if not existing:
        assert ctx.variables == before
    record.assert_called_once_with(compression_type="handoff", reason="summary_retry_exhausted")
    next_step.assert_called_once()


def test_unshrinkable_system_does_not_commit():
    ctx = make_ctx(interaction(2))
    ctx.llm.get_num_tokens_from_messages.side_effect = None
    ctx.llm.get_num_tokens_from_messages.return_value = 1100
    before = dict(ctx.variables)
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        run(ctx, keep_last=0)
    assert ctx.variables == before and "_handoff_state_update" not in ctx.metadata
    record.assert_called_once_with(compression_type="handoff", reason="token_budget_exceeded")


def test_retry_and_failure_events():
    ctx = make_ctx(interaction(2))
    ctx.llm.invoke.side_effect = RuntimeError("failure")
    with (patch("aidev_agent.core.nodes.model.handoff.time.sleep"),
          patch("aidev_agent.core.nodes.model.handoff.conditional_dispatch_custom_event") as dispatch):
        run(ctx, max_retries=2)
    assert ctx.llm.invoke.call_count == 3
    dispatch.assert_not_called()


def test_success_events_are_pending_node_updates_not_ledger_mutations():
    ctx = make_ctx(interaction(2))
    with patch("aidev_agent.core.nodes.model.handoff.conditional_dispatch_custom_event") as dispatch:
        run(ctx, keep_last=1)
    assert [call.args[1]["content"] for call in dispatch.call_args_list] == [HANDOFF_DONE_TEXT]
    assert ctx.metadata["_handoff_messages"][0].message_id == dispatch.call_args.args[1]["messageId"]
    assert len(ctx.state["messages"]) == 6


def test_summary_request_does_not_require_token_counting():
    ctx = make_ctx(interaction(1))
    ctx.llm.get_num_tokens_from_messages.side_effect = NotImplementedError
    assert middleware()._invoke_llm(ctx, 300, "history") == SUMMARY_TEXT
    ctx.llm.get_num_tokens_from_messages.assert_not_called()


def test_summary_request_copies_current_context():
    current = contextvars.ContextVar("handoff_test_context", default=None)
    token = current.set("parent")
    ctx = make_ctx(interaction(1))
    ctx.llm.invoke.side_effect = lambda messages, **kwargs: AIMessage(content=current.get())
    try:
        assert middleware()._invoke_llm(ctx, 300, "history") == "parent"
    finally:
        current.reset(token)


def test_summary_timeout_cancels_without_retrying():
    ctx = make_ctx(interaction(2))
    future = MagicMock()
    future.result.side_effect = concurrent.futures.TimeoutError
    with (patch("aidev_agent.core.nodes.model.handoff._compression_executor.submit", return_value=future) as submit,
          patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record):
        run(ctx, timeout=0.01)
    record.assert_called_once_with(compression_type="handoff", reason="summary_timeout")
    future.result.assert_called_once_with(timeout=0.01)
    future.cancel.assert_called_once()
    submit.assert_called_once()

def test_deepseek_processing_does_not_repopulate_handoff_history_slot():
    ctx = make_ctx(interaction(2))
    run(ctx, keep_last=1)
    with patch("aidev_agent.core.nodes.model.basic_middleware.is_deepseek_r1_series_models", return_value=True):
        DeepSeekR1VariablesMiddleware()(ctx, lambda: None)
    assert ctx.variables["chat_history"] == []
    assert ctx.variables["history_system_prompt"] == "固定系统约束"


def test_parallel_tool_results_are_retained_as_one_group():
    messages = interaction(1)
    messages[-2].tool_calls.append({"name": "work", "args": {}, "id": "parallel"})
    messages.append(ToolMessage(content="parallel-result", id="parallel-result", tool_call_id="parallel"))
    ctx = make_ctx(messages)
    run(ctx, keep_last=1)
    assert "result-0" in view(ctx) and "parallel-result" in view(ctx)
    assert ctx.metadata["_handoff_state_update"]["rounds"][0]["searchable_until"] == "user"

@pytest.mark.parametrize("existing", [False, True])
def test_unavailable_trigger_budget_skips_compression_and_continues(existing):
    ctx = make_ctx(interaction(2))
    if existing:
        ctx.state["handoff"] = {"rounds": [{"summary": "old summary", "searchable_until": "t0"}], "active_round": 0}
    original_state = dict(ctx.state)
    ctx.llm.get_num_tokens_from_messages.side_effect = NotImplementedError("unsupported")
    next_step = MagicMock()
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        middleware()(ctx, next_step)
    next_step.assert_called_once()
    ctx.llm.invoke.assert_not_called()
    record.assert_called_once_with(compression_type="handoff", reason="token_count_unavailable")
    assert ctx.state == original_state and "_handoff_state_update" not in ctx.metadata
    assert "_handoff_messages" not in ctx.metadata
    if existing:
        assert ctx.variables["query"].startswith("old summary")

@pytest.mark.parametrize("token_results", [[1000, None], [1000, 300, None]])
@pytest.mark.parametrize("existing", [False, True])
def test_unavailable_compressed_count_restores_view_and_continues(token_results, existing):
    ctx = make_ctx(interaction(3))
    compressor = middleware(keep_last=2)
    if existing:
        ctx.state["handoff"] = {"rounds": [{"summary": "old", "searchable_until": "t0"}], "active_round": 0}
        compressor._apply_view(ctx, ctx.state["messages"], ctx.state["handoff"])
    before = dict(ctx.variables)
    state = dict(ctx.state)
    ctx.llm.get_num_tokens_from_messages.side_effect = token_results
    next_step = MagicMock()
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        compressor(ctx, next_step)
    next_step.assert_called_once()
    assert ctx.variables == before and ctx.state == state
    assert "_handoff_state_update" not in ctx.metadata and "_handoff_messages" not in ctx.metadata
    record.assert_called_once_with(compression_type="handoff", reason="compressed_token_count_unavailable")


@pytest.mark.parametrize("count", [None, NotImplementedError("unsupported")])
def test_unavailable_summary_count_skips_ratio_check_and_records_metric(count):
    ctx = make_ctx(interaction(2))
    ctx.llm.get_num_tokens.side_effect = count if isinstance(count, Exception) else None
    ctx.llm.get_num_tokens.return_value = None
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        run(ctx, keep_last=1)
    assert "_handoff_state_update" in ctx.metadata
    ctx.llm.invoke.assert_called_once()
    record.assert_called_once_with(compression_type="handoff", reason="summary_token_count_unavailable")


@pytest.mark.parametrize("shrunk_count", [None, 500])
def test_second_summary_count_never_raises(shrunk_count):
    ctx = make_ctx(interaction(2))
    ctx.llm.get_num_tokens.side_effect = [500, shrunk_count]
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        run(ctx, keep_last=1)
    assert "_handoff_state_update" in ctx.metadata and ctx.llm.invoke.call_count == 2
    reason = "summary_token_count_unavailable" if shrunk_count is None else "summary_target_exceeded"
    record.assert_called_once_with(compression_type="handoff", reason=reason)


@pytest.mark.parametrize("shrink_result", [RuntimeError("boom"), "无法解析"])
def test_shrink_failure_keeps_first_summary(shrink_result):
    ctx = make_ctx(interaction(2))
    ctx.llm.get_num_tokens.side_effect = [500]
    first = ctx.llm.invoke.return_value
    ctx.llm.invoke.side_effect = [first, shrink_result if isinstance(shrink_result, Exception) else MagicMock(content=shrink_result)]
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        run(ctx, keep_last=1)
    assert ctx.metadata["_handoff_state_update"]["rounds"][-1]["summary"] == RENDERED + USER_BLOCK
    record.assert_called_once_with(compression_type="handoff", reason="summary_shrink_failed")


@pytest.mark.parametrize("shrink", [False, True])
def test_all_summary_calls_have_internal_compression_tag(shrink):
    ctx = make_ctx(interaction(2))
    if shrink:
        ctx.llm.get_num_tokens.side_effect = [500, 10]
    run(ctx, keep_last=1)
    assert ctx.llm.invoke.call_count == (2 if shrink else 1)
    assert all(call.kwargs["config"] == {"tags": [CONTEXT_COMPRESSION_TAG]} for call in ctx.llm.invoke.call_args_list)


@pytest.mark.parametrize("final_tokens, applied, after", [(500, True, 500), (2000, False, 1000)])
def test_compress_is_observed_once_with_result(final_tokens, applied, after):
    ctx = make_ctx(interaction(4))
    counts = iter([1000, 300])
    ctx.llm.get_num_tokens_from_messages.side_effect = lambda msgs: next(counts, final_tokens)
    calls = []

    errors = []

    @contextmanager
    def observe(**kwargs):
        calls.append(CompressionCall(**kwargs))
        try:
            yield calls[-1]
        except Exception as exc:  # 未交接的异常应穿过 span（真实 span 据此标记 ERROR）
            errors.append(exc)
            raise

    with patch("aidev_agent.core.nodes.model.handoff.observe_compression_call", side_effect=observe):
        run(ctx, keep_last=1)
    (call,) = calls
    attrs = call.build_attributes()
    assert attrs["context.compression.module"] == "handoff" and attrs["context.compression.applied"] is applied
    assert (attrs["context.compression.before_tokens"], attrs["context.compression.after_tokens"]) == (1000, after)
    assert attrs.get("error.type") == (None if applied else "token_budget_exceeded")
    assert [getattr(exc, "reason", None) for exc in errors] == ([] if applied else ["token_budget_exceeded"])
    assert "context.compression.input_chars" not in attrs and "gen_ai.usage.input_tokens" not in attrs

def test_source_indexes_render_read_hint():
    messages = [HumanMessage(content="u", id="u0"), AIMessage(content="长回复", id="a1")]
    item = {"section": "key_context", "text": "结论", "source_indexes": [1, 5]}
    parsed = parse_handoff_summary(
        json.dumps({**SUMMARY_JSON, "items": [item]}), previous_items={}, valid_indexes=set(), round_no=1, source_limit=2
    )
    assert parsed["items"][0]["source_indexes"] == [1]
    assert '- 结论（原文 #1(id="a1")，可用 handoff_read_history 查看全文）' in render_handoff_summary(parsed, messages, [])


def test_round_ids_convert_only_at_load_and_dump():
    messages = [HumanMessage(content="u", id="u0"), AIMessage(content="r", id="a1"), HumanMessage(content="n", id="u2")]
    item = {"id": "R1-1", "section": "todo", "text": "t", "source_indexes": [1]}
    parsed = {"task_goal": "g", "items": [item], "key_message_indexes": [0]}
    stored = dump_round(messages, parsed, "s", 2, 100)
    assert stored["items"][0]["source_ids"] == ["a1"] and stored["key_message_ids"] == ["u0"]
    assert (stored["searchable_until"], stored["context_end_id"]) == ("a1", "u2")
    loaded = load_round([HumanMessage(content="x", id="x"), *messages], stored)
    assert loaded.items["R1-1"]["source_indexes"] == [2] and loaded.key_indexes == [1]
    assert (loaded.covered_end, loaded.context_end) == (3, 3)


def test_users_leaving_window_are_offered_to_summary_model():
    messages = [SystemMessage(content="固定系统约束", id="system")]
    for index in range(5):
        messages.extend([
            HumanMessage(content=f"约束{index}", id=f"u{index}"),
            AIMessage(content="", id=f"a{index}", tool_calls=[{"name": "work", "args": {}, "id": f"c{index}"}]),
            ToolMessage(content=f"result-{index}", id=f"t{index}", tool_call_id=f"c{index}"),
        ])
    ctx = make_ctx(messages)
    ctx.llm.invoke.return_value = AIMessage(content=json.dumps({**SUMMARY_JSON, "key_message_indexes": [1]}))
    previous = {"summary": "old", "searchable_until": "t2", "context_end_id": "t2"}
    ctx.state["handoff"] = {"rounds": [previous], "active_round": 0}
    run(ctx, keep_last=1)
    dropped = ctx.llm.invoke.call_args.args[0][1].content.split("## 移出原文保留的用户输入")[1].split("## 新增原文")[0]
    assert "约束0" in dropped and "约束1" in dropped and "约束2" not in dropped
    rounds = ctx.metadata["_handoff_state_update"]["rounds"]
    assert "## 关键原文\n[#1|u0|user|-] 约束0" in rounds[-1]["summary"]


@pytest.mark.parametrize("base, compressed", [(300, True), (900, False)])
def test_budget_uses_available_context_not_trigger_size(base, compressed):
    ctx = make_ctx(interaction(4))
    counts = iter([4000])
    ctx.llm.get_num_tokens_from_messages.side_effect = lambda msgs: next(counts, None) or (
        base if not any("result-3" in str(msg.content) for msg in msgs) else base + 100
    )
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        run(ctx, keep_last=1)
    assert ("_handoff_state_update" in ctx.metadata) is compressed
    if compressed:
        assert "约 180 token" in ctx.llm.invoke.call_args.args[0][0].content
    else:
        record.assert_called_once_with(compression_type="handoff", reason="token_budget_exceeded")


@pytest.mark.parametrize("text, expected", [("", 0), ("abcd", 1), ("abcde", 2), ("中文", 2), ("中文ab", 3)])
def test_estimate_tokens(text, expected):
    assert _estimate_tokens(text) == expected


def test_compression_does_not_mutate_state():
    ctx = make_ctx(interaction(4))
    original = dict(ctx.state)
    run(ctx, keep_last=1)
    assert ctx.state == original and "_handoff_state_update" in ctx.metadata
    assert ctx.metadata["_handoff_applied"] is True


def test_unexpected_error_fails_request_and_restores_view():
    ctx = make_ctx(interaction(4))
    ctx.state["handoff"] = {"rounds": [{"summary": "old", "searchable_until": "missing"}]}
    before = dict(ctx.variables)
    next_step = MagicMock()
    with (patch("aidev_agent.core.nodes.model.handoff.conditional_dispatch_custom_event") as dispatch,
          pytest.raises(HandoffCompressionError) as raised):
        middleware(keep_last=1)(ctx, next_step)
    assert raised.value.reason == "handoff_failed" and ctx.variables == before
    assert [call.args[1]["content"] for call in dispatch.call_args_list] == [HANDOFF_FAILED_TEXT]
    next_step.assert_not_called()


def test_estimate_prefilter_skips_precise_count(monkeypatch):
    monkeypatch.setattr("aidev_agent.core.nodes.model.handoff._ESTIMATE_SKIP_RATIO", 0.7)
    ctx = make_ctx(interaction(2))
    run(ctx, keep_last=1)
    ctx.llm.get_num_tokens_from_messages.assert_not_called()
    assert "_handoff_state_update" not in ctx.metadata


def test_tool_definitions_count_towards_context_tokens():
    tool = StructuredTool.from_function(func=lambda query: query, name="demo_tool", description="说明" * 50)
    compressor = HandoffCompressionMiddleware(
        HandoffSettings(), token_limit=1000, token_margin=100, tools=[tool]
    )
    assert compressor.tool_tokens >= 100
    ctx = make_ctx(interaction(1), token_len=10)
    assert compressor._count_tokens(ctx) == 10 + compressor.tool_tokens


@pytest.mark.parametrize("payload", [{}, {"error": "x"}, {"task_goal": "g", "items": []}])
def test_missing_required_fields_are_rejected(payload):
    assert parse(json.dumps(payload)) is None


def test_missing_required_fields_retry_without_commit():
    ctx = make_ctx(interaction(4))
    ctx.llm.invoke.return_value = AIMessage(content=json.dumps({"error": "上下文过长"}))
    with patch("aidev_agent.core.nodes.model.handoff.record_compression_skipped") as record:
        run(ctx, keep_last=1, max_retries=1)
    assert ctx.llm.invoke.call_count == 2 and "_handoff_state_update" not in ctx.metadata
    record.assert_called_once_with(compression_type="handoff", reason="summary_retry_exhausted")


@pytest.mark.parametrize("limit, truncated", [(10, True), (30000, False)])
def test_key_message_char_limit_is_configurable(limit, truncated):
    messages = [AIMessage(content="x" * 20, id="a0")]
    parsed = {**SUMMARY_JSON, "key_message_indexes": [0]}
    rendered = render_handoff_summary(parsed, messages, [], limit)
    assert ("offset=10) 续读" in rendered) is truncated
    assert HandoffSettings().key_message_char_limit == 30000
