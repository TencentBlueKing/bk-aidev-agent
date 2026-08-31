import copy

import pytest
from aidev_wxbot.wxaibot import question_cards as cards


@pytest.mark.parametrize(
    "count,multi,kind",
    [
        (1, False, "vote_interaction"),
        (1, True, "vote_interaction"),
        (2, False, "multiple_interaction"),
        (3, False, "multiple_interaction"),
        (2, True, None),
        (4, False, None),
        (4, True, None),
    ],
)
def test_native_question_types(question_case, count, multi, kind):
    questions = question_case.interrupt["metadata"]["questions"]
    questions[0]["multiSelect"] = multi
    questions[:] = [copy.deepcopy(questions[0]) for _ in range(count)]
    card = cards.build_pending_question_card(question_case.event, "session-1")
    if kind is None:
        assert card is None
        return
    assert card["card_type"] == kind
    assert card["card_action"] == {"type": 0}
    assert "文字回复" in card["main_title"]["desc"]
    if kind == "vote_interaction":
        assert card["checkbox"]["mode"] == int(multi)


@pytest.mark.parametrize("change", ["text", "too_many", "malformed"])
def test_unsupported_questions_use_chat_without_web_card(question_case, change):
    question = question_case.interrupt["metadata"]["questions"][0]
    if change == "text":
        question["options"] = None
    elif change == "too_many":
        question["options"] *= 11
    elif change == "malformed":
        question["options"] = [None]
    card = cards.build_pending_question_card(question_case.event, "session-1")
    assert card is None
    prompt = cards.question_prompt(question_case.interrupt)
    assert question["question"] in prompt
    assert "直接在企微回复" in prompt and "回到原会话" not in prompt


def test_protocol_capacity_and_long_text_are_preserved(protocol_question_case):
    case = protocol_question_case
    original = copy.deepcopy(case.interrupt)
    questions = case.interrupt["metadata"]["questions"]
    card = cards.build_question_card(case.interrupt, "session-1")
    if len(questions) == 1:
        assert card["card_type"] == "vote_interaction"
        assert card["main_title"]["title"] == questions[0]["question"]
        assert card["checkbox"]["mode"] == int(questions[0]["multiSelect"])
        controls = [card["checkbox"]]
    else:
        assert card["card_type"] == "multiple_interaction"
        controls = card["select_list"]
        assert [c["title"] for c in controls] == [q["question"] for q in questions]
    for control, question in zip(controls, questions, strict=True):
        assert control["option_list"] == [{"id": str(i), "text": o["label"]} for i, o in enumerate(question["options"])]
        assert "selected_id" not in control
    answers = cards.decode_answers(questions, case.selected)
    assert [a["answer"] for a in answers] == [[q["options"][-1]] for q in questions]
    assert case.interrupt == original


@pytest.mark.parametrize("multi_flags,option_count", [([False], 21), ([True], 21), ([False, False], 11)])
def test_only_protocol_option_overflow_falls_back(question_case, multi_flags, option_count):
    questions = question_case.interrupt["metadata"]["questions"]
    questions[:] = [copy.deepcopy(questions[0]) for _ in multi_flags]
    for question, multi in zip(questions, multi_flags, strict=True):
        question.update(multiSelect=multi, options=[{"label": str(i)} for i in range(option_count)])
    assert cards.build_question_card(question_case.interrupt, "session-1") is None


@pytest.mark.parametrize("multi_flags", [[False, True], [True, False], [True, True], [False, True, False]])
def test_native_selectors_cannot_express_multiple_choice_questions(question_case, multi_flags):
    questions = question_case.interrupt["metadata"]["questions"]
    questions[:] = [dict(questions[0], multiSelect=multi) for multi in multi_flags]
    assert cards.build_question_card(question_case.interrupt, "session-1") is None
    assert "（可多选）" in cards.question_prompt(question_case.interrupt)


def test_native_card_keeps_option_descriptions_in_chat(question_case):
    question = question_case.interrupt["metadata"]["questions"][0]
    question["options"][0]["description"] = "important context"
    card = cards.build_pending_question_card(question_case.event, "session-1")
    assert card["card_type"] == "vote_interaction"
    assert "important context" in cards.question_prompt(question_case.interrupt)


def test_submitted_card_removes_controls_and_opens_original_session(native_question_case):
    interrupt = native_question_case.interrupt
    original = copy.deepcopy(interrupt)
    pending = cards.build_question_card(interrupt, "session-1")
    result = cards.submitted_question_card(interrupt, "session-1")
    assert result["card_type"] == "text_notice"
    assert result["task_id"] == pending["task_id"]
    assert result["main_title"]["title"] == pending["main_title"]["title"]
    assert result["sub_title_text"] == "答案已接收"
    assert result["card_action"] == {
        "type": 1,
        "url": "https://agent.example.com/chat-window/?session=session-1",
    }
    assert not {"checkbox", "select_list", "submit_button"} & result.keys()
    assert interrupt == original


@pytest.mark.parametrize("url", ["", "/chat-window/", "javascript:alert(1)", "https://[invalid"])
def test_submitted_card_requires_valid_session_url(question_case, monkeypatch, url):
    monkeypatch.setattr(cards.AgentHelper, "build_session_detail_url", lambda _: url)
    assert cards.submitted_question_card(question_case.interrupt, "session-1") is None


def test_text_questions_have_lettered_options_and_no_card_hint(question_case):
    questions = question_case.interrupt["metadata"]["questions"]
    questions[:] = [copy.deepcopy(questions[0]) for _ in range(4)]
    questions[2]["multiSelect"] = True
    questions[3]["options"] = None
    prompt = cards.question_prompt(question_case.interrupt)
    assert prompt.count("A. 华南") == prompt.count("B. 华东") == 3
    assert "3. 请选择区域（可多选）" in prompt
    assert "4. 请选择区域" in prompt
    assert "1A；2B；3AC" in prompt
    assert "下方卡片" not in prompt


@pytest.mark.parametrize("index,prefix", [(0, "A"), (25, "Z"), (26, "AA"), (27, "AB")])
def test_option_prefix_does_not_run_out_of_letters(index, prefix):
    assert cards._option_prefix(index) == prefix


@pytest.mark.parametrize("status", ["answered", "cancelled", "expired"])
def test_finalized_question_does_not_render_another_card(question_case, status):
    question_case.interrupt["metadata"]["status"] = status
    assert cards.pending_question(question_case.event) is None
    assert cards.build_pending_question_card(question_case.event, "session-1") is None


def test_signed_action_binds_original_target(question_case):
    card = cards.build_pending_question_card(question_case.event, "session-1")
    bound = cards.bind_question_target(card, "group-1")
    action = cards.decode_question_key(bound["submit_button"]["key"])
    assert action.session_code == "session-1" and action.interrupt_id == "question-1"
    assert action.target == "group-1"
    assert cards.decode_question_key(card["submit_button"]["key"]).target == ""
    assert cards.decode_question_key(bound["submit_button"]["key"] + "tampered") is None


@pytest.mark.parametrize("ids", [[], ["_"], ["2"], ["0", "0"], ["0", "1"], [0], None])
def test_reject_invalid_or_multiple_single_choice(question_case, ids):
    question_case.selected["selected_item"][0]["option_ids"]["option_id"] = ids
    with pytest.raises(ValueError):
        cards.decode_answers(question_case.interrupt["metadata"]["questions"], question_case.selected)


def test_multiple_choice_uses_original_labels(question_case):
    questions = question_case.interrupt["metadata"]["questions"]
    questions[0]["multiSelect"] = True
    question_case.selected["selected_item"][0]["option_ids"]["option_id"] = ["1", "0"]
    answers = cards.decode_answers(questions, question_case.selected)
    assert answers == [
        {"question": "请选择区域", "multiSelect": True, "answer": [{"label": "华东"}, {"label": "华南"}]}
    ]


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown", "placeholder"])
def test_multiple_questions_reject_incomplete_or_mismatched_selections(question_case, change):
    questions = question_case.interrupt["metadata"]["questions"]
    questions.append(copy.deepcopy(questions[0]))
    items = question_case.selected["selected_item"]
    if change != "missing":
        items.append({"question_key": "q1", "option_ids": {"option_id": ["1"]}})
        if change == "placeholder":
            items[1]["option_ids"]["option_id"] = ["_"]
        else:
            items[1]["question_key"] = "q0" if change == "duplicate" else "q9"
    with pytest.raises(ValueError):
        cards.decode_answers(questions, question_case.selected)


@pytest.mark.parametrize("reason", ["aidev:ask_user_question", "aidev:tool_approval"])
def test_only_actual_question_reason_is_rendered(question_case, reason):
    question_case.interrupt["reason"] = reason
    assert cards.build_pending_question_card(question_case.event, "session-1") is None
