# -*- coding: utf-8 -*-
"""Handoff 历史检索/读取工具单元测试。"""

import json

import pytest
from aidev_agent.core.tools.handoff_history import (
    make_handoff_read_history_tool,
    make_handoff_search_history_tool,
    read_history,
    search_history,
)
from langchain_core.messages import AIMessage, HumanMessage


def make_state(*, until_id="a1", messages=None):
    messages = messages or [
        HumanMessage(
            content="部署方案确认了吗", id="h0", additional_kwargs={"created_at": "2026-01-01T00:00:00+00:00"}
        ),
        AIMessage(content="已确认灰度部署", id="a1", additional_kwargs={"created_at": "2026-01-02T00:00:00+00:00"}),
        HumanMessage(content="当前问题", id="h2"),
        AIMessage(content="当前回答", id="a2"),
    ]
    return {
        "messages": messages,
        "handoff": {
            "rounds": [{"summary": "摘要", "searchable_until": until_id}],
            "active_round": 0,
        },
    }


class TestSearch:
    def test_hits_only_replaced_interval(self):
        result = json.loads(search_history("部署", state=make_state()))
        assert [item["id"] for item in result["results"]] == ["h0", "a1"]
        assert result["results"][0]["role"] == "user"

    def test_ignores_current_view_messages(self):
        assert "没有找到" in search_history("当前问题", state=make_state())

    def test_no_handoff_returns_empty_notice(self):
        assert "没有可检索" in search_history("部署", state={"messages": []})

    def test_limit_caps_results(self):
        result = json.loads(search_history("部署", limit=1, state=make_state()))
        assert len(result["results"]) == 1

    def test_time_range_filters_when_timestamps_exist(self):
        result = json.loads(
            search_history("部署", start_time="2026-01-02T00:00:00+00:00", state=make_state()),
        )
        assert [item["id"] for item in result["results"]] == ["a1"]

    def test_missing_timestamp_degrades_to_keyword(self):
        messages = [
            HumanMessage(content="部署方案", id="h0"),
            HumanMessage(content="当前问题", id="h2"),
        ]
        state = make_state(until_id="h0", messages=messages)
        result = json.loads(search_history("部署", start_time="2026-01-01T00:00:00+00:00", state=state))
        assert [item["id"] for item in result["results"]] == ["h0"]


class TestRead:
    def test_returns_full_text_of_range(self):
        output = read_history("h0", "a1", state=make_state())
        assert "部署方案确认了吗" in output
        assert "已确认灰度部署" in output

    def test_clamps_to_accessible_upper_bound(self):
        output = read_history("h0", "a2", state=make_state())
        assert "已确认灰度部署" in output
        assert "当前回答" not in output
        assert "已裁剪到可访问范围" in output

    def test_range_outside_compressed_history_is_rejected(self):
        output = read_history("h2", "a2", state=make_state())
        assert "不在已压缩历史内" in output and "当前回答" not in output

    def test_unknown_id_returns_notice(self):
        assert "未找到消息 id" in read_history("missing", state=make_state())

    @pytest.mark.parametrize("until_id, expected", [("", "没有可读取"), ("not-in-ledger", "压缩偏移已失效")])
    def test_boundary_without_valid_id(self, until_id, expected):
        assert expected in read_history("h0", "a1", state=make_state(until_id=until_id))

    def test_output_is_truncated(self, monkeypatch):
        import aidev_agent.core.tools.runtime_tools.utils as runtime_utils

        monkeypatch.setattr(runtime_utils, "MAX_OUTPUT_LENGTH", 10)
        output = read_history("h0", "a1", state=make_state())
        assert "输出已截断" in output


class TestToolFactory:
    def test_tool_names_and_no_runtime_dependency(self):
        tools = [make_handoff_search_history_tool(), make_handoff_read_history_tool()]
        assert [tool.name for tool in tools] == ["handoff_search_history", "handoff_read_history"]
        assert "runtime" not in tools[0].description
        assert tools[1].args_schema is not None


@pytest.mark.parametrize("keyword", ["run_job", "job_key"])
def test_search_and_read_include_tool_call_details(keyword):
    messages = [
        AIMessage(content="", id="call", tool_calls=[{"name": "run_job", "args": {"job_key": "value"}, "id": "c"}]),
        HumanMessage(content="now", id="now"),
    ]
    state = make_state(until_id="call", messages=messages)
    result = json.loads(search_history(keyword, state=state))
    assert result["results"][0]["id"] == "call"
    output = read_history("call", state=state)
    assert "run_job" in output and "job_key" in output


@pytest.mark.parametrize("timestamp", ["2026-01-02T00:00:00", "2026-01-02T08:00:00+08:00"])
def test_search_normalizes_timestamp_timezone(timestamp):
    state = make_state()
    state["messages"][1].additional_kwargs["created_at"] = timestamp
    result = json.loads(search_history("部署", start_time="2026-01-02T00:00:00Z", state=state))
    assert [item["id"] for item in result["results"]] == ["a1"]


@pytest.mark.parametrize("start_time", ["2026-01-02T00:00:00", "2026-01-02T08:00:00+08:00"])
def test_search_normalizes_query_timezone(start_time):
    result = json.loads(search_history("部署", start_time=start_time, state=make_state()))
    assert [item["id"] for item in result["results"]] == ["a1"]


@pytest.mark.parametrize("times", [{"start_time": "invalid"}, {"end_time": "invalid"}])
def test_search_rejects_invalid_time(times):
    assert "ISO 8601" in search_history("部署", state=make_state(), **times)


def long_state(text):
    messages = [AIMessage(content=text, id="a0"), HumanMessage(content="当前问题", id="h1")]
    return make_state(until_id="a0", messages=messages)


class TestPagedRead:
    def test_reads_single_message_page_by_page(self):
        state = long_state("a" * 10 + "b" * 10)
        first = read_history("a0", offset=0, max_chars=10, state=state)
        second = read_history("a0", offset=10, max_chars=10, state=state)
        assert "a" * 10 in first and "b" not in first.split("]", 1)[1].split("[")[0]
        assert "下一页 offset=10" in first
        assert "b" * 10 in second and "已读到末尾" in second

    @pytest.mark.parametrize(
        "kwargs, expected",
        [
            ({"offset": 99}, "offset 超出消息长度"),
            ({"offset": -1}, "offset 不能为负数"),
            ({"offset": 1, "end_id": "a0"}, "字符 1-"),
        ],
    )
    def test_invalid_or_same_id_offsets(self, kwargs, expected):
        assert expected in read_history("a0", state=long_state("x" * 20), **kwargs)

    def test_offset_rejected_for_range(self):
        assert "仅支持单条" in read_history("h0", "a1", offset=1, state=make_state())


def test_search_snippet_centers_on_late_match():
    state = long_state("x" * 1000 + "关键结论" + "y" * 1000)
    result = json.loads(search_history("关键结论", state=state))["results"][0]
    assert result["match_offset"] == 1000 and result["length"] == 2004
    assert "关键结论" in result["snippet"] and result["snippet"].startswith("…")