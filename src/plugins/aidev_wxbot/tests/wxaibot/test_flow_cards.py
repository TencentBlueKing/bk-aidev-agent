"""Flow 失败节点重试/跳过卡片：选取、签名绑定与结果卡。"""

import copy
import hashlib

import pytest
from aidev_wxbot.wxaibot.flow_cards import (
    FlowNodeAction,
    bind_flow_target,
    build_flow_action_card,
    build_flow_action_result_card,
    decode_flow_event_key,
    encode_flow_event_key,
    flow_card_task_id,
    pick_first_actionable_failed_node,
)


def _nodes(**items):
    return items


def test_pick_first_failed_actionable_node_skips_earlier_success():
    nodes = _nodes(
        n1={"id": "n1", "name": "成功节点", "state": "FINISHED", "retryable": True, "skippable": True},
        n2={"id": "n2", "name": "失败节点", "state": "FAILED", "retryable": True, "skippable": False},
        n3={"id": "n3", "name": "后一个失败", "state": "FAILED", "retryable": True, "skippable": True},
    )
    picked = pick_first_actionable_failed_node(nodes)
    assert picked is not None
    assert picked[0] == "n2"
    assert picked[2] is True
    assert picked[3] is False


def test_pick_skips_failed_node_without_actions_when_flags_present():
    nodes = _nodes(
        n1={"id": "n1", "name": "不可操作", "state": "FAILED", "retryable": False, "skippable": False},
        n2={"id": "n2", "name": "可跳过", "state": "FAILED", "retryable": False, "skippable": True},
    )
    picked = pick_first_actionable_failed_node(nodes)
    assert picked is not None
    assert picked[0] == "n2"
    assert picked[3] is True


def test_missing_flags_on_failed_node_are_treated_as_both_actions():
    picked = pick_first_actionable_failed_node({"n1": {"id": "n1", "name": "HTTP", "state": "FAILED"}})
    assert picked == ("n1", {"id": "n1", "name": "HTTP", "state": "FAILED"}, True, True)


def test_revoked_or_running_nodes_are_not_actionable():
    assert pick_first_actionable_failed_node({"n1": {"id": "n1", "state": "REVOKED"}}) is None
    assert pick_first_actionable_failed_node({"n1": {"id": "n1", "state": "RUNNING"}}) is None


@pytest.mark.parametrize("session_url", ["https://agent.example.com/session-1", "", "javascript:alert(1)"])
def test_build_card_only_includes_allowed_buttons(monkeypatch, session_url):
    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.flow_cards.AgentHelper.build_session_detail_url",
        lambda _session: session_url,
    )
    card = build_flow_action_card(
        session_code="session-1",
        task_id="42",
        nodes={"n1": {"id": "n1", "name": "查询日志", "state": "FAILED", "retryable": True, "skippable": True}},
    )
    assert card is not None
    assert card["card_type"] == "button_interaction"
    assert [button["text"] for button in card["button_list"]] == ["重试", "跳过"]
    retry = decode_flow_event_key(card["button_list"][0]["key"])
    skip = decode_flow_event_key(card["button_list"][1]["key"])
    assert retry.operation == "retry"
    assert skip.operation == "skip"
    assert retry.node_id == skip.node_id == "n1"
    assert card["task_id"] == flow_card_task_id(retry)
    if session_url.startswith("https://"):
        assert card["card_action"] == {"type": 1, "url": session_url}
    else:
        assert card["card_action"] == {"type": 0}


def test_build_card_returns_none_when_no_actionable_node():
    assert (
        build_flow_action_card(
            session_code="session-1",
            task_id="42",
            nodes={"n1": {"id": "n1", "state": "FINISHED"}},
        )
        is None
    )


def test_sent_card_binds_signed_target_without_changing_original(monkeypatch):
    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.flow_cards.AgentHelper.build_session_detail_url",
        lambda _session: "https://agent.example.com/session-1",
    )
    original = build_flow_action_card(
        session_code="session-1",
        task_id="42",
        nodes={"n1": {"id": "n1", "name": "查询日志", "state": "FAILED"}},
    )
    snapshot = copy.deepcopy(original)
    bound = bind_flow_target(original, "group-original")
    action = decode_flow_event_key(bound["button_list"][0]["key"])
    assert action.target == "group-original"
    assert original == snapshot
    assert decode_flow_event_key(original["button_list"][0]["key"]).target == ""


def test_signed_key_cannot_change_target():
    action = FlowNodeAction("session-1", "42", "n1", "retry", "查询日志", "alice-wx")
    key = encode_flow_event_key(action)
    head, signature = key.rsplit(":", 1)
    assert decode_flow_event_key(f"{head}:{'x' if signature[0] != 'x' else 'y'}{signature[1:]}") is None


@pytest.mark.parametrize(
    ("ok", "operation", "label"), [(True, "retry", "已重试"), (True, "skip", "已跳过"), (False, "retry", "操作失败")]
)
def test_result_card_replaces_buttons(ok, operation, label, monkeypatch):
    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.flow_cards.AgentHelper.build_session_detail_url",
        lambda _session: "https://agent.example.com/session-1",
    )
    action = FlowNodeAction("session-1", "42", "n1", operation, "查询日志")
    card = build_flow_action_result_card(action, flow_card_task_id(action), ok=ok)
    assert card["card_type"] == "text_notice"
    assert "button_list" not in card
    assert card["jump_list"] == [{"type": 0, "title": label}]


def test_result_card_rejects_mismatched_task_id():
    action = FlowNodeAction("session-1", "42", "n1", "retry")
    assert build_flow_action_result_card(action, "other-task", ok=True) is None


def test_wecom_task_id_binds_session_task_node_and_card():
    action = FlowNodeAction("session-1", "42", "n1", "retry", card_id="c1")
    assert flow_card_task_id(action) == "flow_" + hashlib.sha256(b"session-1\x0042\x00n1\x00c1").hexdigest()[:24]


def test_each_issued_card_gets_unique_wecom_task_id(monkeypatch):
    monkeypatch.setattr(
        "aidev_wxbot.wxaibot.flow_cards.AgentHelper.build_session_detail_url",
        lambda _session: "https://agent.example.com/session-1",
    )
    nodes = {"n1": {"id": "n1", "name": "HTTP请求", "state": "FAILED", "retryable": True, "skippable": True}}
    first = build_flow_action_card(session_code="session-1", task_id="42", nodes=nodes)
    second = build_flow_action_card(session_code="session-1", task_id="42", nodes=nodes)
    assert first["task_id"] != second["task_id"]
    first_id = decode_flow_event_key(first["button_list"][0]["key"]).card_id
    second_id = decode_flow_event_key(second["button_list"][0]["key"]).card_id
    assert first_id and second_id and first_id != second_id
