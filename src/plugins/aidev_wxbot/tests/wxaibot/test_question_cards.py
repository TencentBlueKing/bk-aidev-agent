import copy

import pytest
from aidev_wxbot.wxaibot import question_cards as cards


@pytest.mark.parametrize(
    "count,multi,kind",
    [
        (1, False, "vote_interaction"),
        (1, True, "vote_interaction"),
        (2, False, "multiple_interaction"),
        (2, True, None),
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


@pytest.mark.parametrize("change", ["text", "too_many", "malformed", "long"])
def test_unsupported_questions_use_chat_without_web_card(question_case, change):
    question = question_case.interrupt["metadata"]["questions"][0]
    if change == "text":
        question["options"] = None
    elif change == "too_many":
        question["options"] *= 11
    elif change == "malformed":
        question["options"] = [None]
    else:
        question["question"] = "长" * 100
    card = cards.build_pending_question_card(question_case.event, "session-1")
    assert card is None
    prompt = cards.question_prompt(question_case.interrupt)
    assert question["question"] in prompt
    assert "直接在企微回复" in prompt and "回到原会话" not in prompt


def test_native_card_keeps_option_descriptions_in_chat(question_case):
    question = question_case.interrupt["metadata"]["questions"][0]
    question["options"][0]["description"] = "important context"
    card = cards.build_pending_question_card(question_case.event, "session-1")
    assert card["card_type"] == "vote_interaction"
    assert "important context" in cards.question_prompt(question_case.interrupt)


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


@pytest.mark.parametrize("reason", ["aidev:ask_user_question", "aidev:tool_approval"])
def test_only_actual_question_reason_is_rendered(question_case, reason):
    question_case.interrupt["reason"] = reason
    assert cards.build_pending_question_card(question_case.event, "session-1") is None
