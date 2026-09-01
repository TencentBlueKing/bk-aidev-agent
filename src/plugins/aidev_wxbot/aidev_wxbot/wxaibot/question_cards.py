"""Native Ask-user cards, signed session binding and strict option decoding."""

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, replace
from urllib.parse import urlsplit

from aidev_agent.core.ag_ui.ask_user_question import ASK_USER_QUESTION_REASON
from aidev_bkplugin.services.agent_helpers import AgentHelper
from django.core import signing

from .context import _escape_markdown_text, _normalize_url

_PREFIX = "question_answer:"
_SALT = "aidev.wxbot.question.v1"
MAX_AGE = 86400
# Hard limits from https://developer.work.weixin.qq.com/document/path/101032.
# Title/option text lengths there are display recommendations, not rejection rules.
_MAX_VOTE_OPTIONS = 20
_MAX_SELECTORS = 3
_MAX_SELECTOR_OPTIONS = 10


@dataclass(frozen=True)
class QuestionAction:
    session_code: str
    interrupt_id: str
    digest: str
    target: str = ""


def questions_digest(questions: list) -> str:
    return hashlib.sha256(json.dumps(questions, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def question_task_id(action: QuestionAction) -> str:
    digest = hashlib.sha256(f"{action.session_code}\0{action.interrupt_id}".encode()).hexdigest()[:24]
    return f"question_{digest}"


def encode_question_key(action: QuestionAction) -> str:
    return _PREFIX + signing.dumps(asdict(action), salt=_SALT, compress=True)


def decode_question_key(key: str) -> QuestionAction | None:
    if not isinstance(key, str) or not key.startswith(_PREFIX) or len(key) > 2048:
        return None
    try:
        data = signing.loads(key[len(_PREFIX) :], salt=_SALT, max_age=MAX_AGE)
        action = QuestionAction(**data)
    except (signing.BadSignature, ValueError, TypeError):
        return None
    if not all(isinstance(value, str) and len(value) <= 256 for value in asdict(action).values()):
        return None
    return action if action.session_code and action.interrupt_id and action.digest else None


def bind_question_target(card: dict, target: str) -> dict:
    """Bind the signed action to its original recipient before sending."""
    button = card.get("submit_button") or {}
    action = decode_question_key(button.get("key", ""))
    if action is None:
        return card
    result = copy.deepcopy(card)
    result["submit_button"]["key"] = encode_question_key(replace(action, target=target))
    return result


def _native_kind(questions: list) -> str | None:
    """Choose a native card that can express all answers in one submission."""
    if not questions:
        return None
    for question in questions:
        options = question.get("options")
        if not isinstance(options, list) or not options:
            return None
        if not isinstance(question.get("question"), str):
            return None
        if any(
            not isinstance(option, dict) or not isinstance(option.get("label"), str) or not option["label"]
            for option in options
        ):
            return None
    if len(questions) == 1:
        return "vote_interaction" if len(questions[0]["options"]) <= _MAX_VOTE_OPTIONS else None
    # SelectionItem has one selected_id and no multi-select mode. Do not silently
    # turn multiple-choice questions into single-choice selectors.
    if len(questions) <= _MAX_SELECTORS and all(
        not q.get("multiSelect") and len(q["options"]) <= _MAX_SELECTOR_OPTIONS for q in questions
    ):
        return "multiple_interaction"
    return None


def build_pending_question_card(event: dict, session_code: str) -> dict | None:
    interrupt = pending_question(event)
    return build_question_card(interrupt, session_code) if interrupt else None


def pending_question(event: dict) -> dict | None:
    outcome = event.get("outcome") or {}
    if not isinstance(outcome, dict) or outcome.get("type") != "interrupt":
        return None
    interrupts = outcome.get("interrupts") or []
    if not isinstance(interrupts, list):
        return None
    for interrupt in reversed(interrupts):
        if isinstance(interrupt, dict) and interrupt.get("reason") == ASK_USER_QUESTION_REASON:
            metadata = interrupt.get("metadata") or {}
            if not isinstance(metadata, dict) or metadata.get("status", "pending") != "pending":
                return None
            return interrupt
    return None


def _option_prefix(index: int) -> str:
    """Zero-based option index as A…Z, AA…; do not alter protocol labels."""
    prefix = ""
    number = index + 1
    while number:
        number, remainder = divmod(number - 1, 26)
        prefix = chr(ord("A") + remainder) + prefix
    return prefix


def question_prompt(interrupt: dict, *, has_card: bool = False) -> str:
    """Keep the complete questions and option descriptions available in chat."""
    hint = "请直接在企微回复答案。"
    if has_card:
        hint += "也可以使用下方卡片选择。"
    lines = [hint, "选择题可回复题号+选项字母（如：1A；2B；3AC），也可直接描述答案。"]
    for index, question in enumerate((interrupt.get("metadata") or {}).get("questions") or [], 1):
        if not isinstance(question, dict):
            continue
        options = question.get("options") or []
        mode = ("（可多选）" if question.get("multiSelect") else "（单选）") if options else ""
        lines.append(f"\n{index}. {_escape_markdown_text(str(question.get('question') or '请补充信息'))}{mode}")
        for option_index, option in enumerate(options):
            if not isinstance(option, dict):
                continue
            text = str(option.get("label") or "")
            if option.get("description"):
                text += f"：{option['description']}"
            lines.append(f"- {_option_prefix(option_index)}. {_escape_markdown_text(text)}")
    return "\n".join(lines)


def build_question_card(interrupt: dict, session_code: str) -> dict | None:
    questions = (interrupt.get("metadata") or {}).get("questions") or []
    if not isinstance(questions, list) or not all(isinstance(q, dict) for q in questions):
        return None
    kind = _native_kind(questions)
    if not kind or not session_code or not interrupt.get("id"):
        return None
    card = {
        "main_title": {"title": "需要你补充信息", "desc": "请选择后提交，或直接文字回复"},
        "card_action": {"type": 0},
    }
    action = QuestionAction(session_code, interrupt["id"], questions_digest(questions))
    card.update(
        card_type=kind,
        task_id=question_task_id(action),
        submit_button={"text": "提交答案", "key": encode_question_key(action)},
    )
    if kind == "vote_interaction":
        question = questions[0]
        card["main_title"]["title"] = question["question"]
        card["checkbox"] = {
            "question_key": "q0",
            "mode": int(bool(question.get("multiSelect"))),
            "option_list": [{"id": str(i), "text": o["label"]} for i, o in enumerate(question["options"])],
        }
    else:
        card["select_list"] = [
            {
                "question_key": f"q{i}",
                "title": q["question"],
                # Use the native default (first option), without consuming one
                # of the protocol's ten options for an artificial placeholder.
                "option_list": [{"id": str(j), "text": o["label"]} for j, o in enumerate(q["options"])],
            }
            for i, q in enumerate(questions)
        ]
    return card


def decode_answers(questions: list, selected_items: dict) -> list:
    """Use server-side question/option text; never accept labels from callbacks."""
    if not isinstance(selected_items, dict):
        raise ValueError("Invalid selections")
    items = selected_items.get("selected_item")
    if not isinstance(items, list) or len(items) != len(questions):
        raise ValueError("Incomplete answers")
    selected = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Invalid question selection")
        key = item.get("question_key")
        if not isinstance(key, str) or key in selected:
            raise ValueError("Invalid question key")
        option_ids = item.get("option_ids")
        if not isinstance(option_ids, dict):
            raise ValueError("Invalid option IDs")
        selected[key] = option_ids.get("option_id")
    answers = []
    for index, question in enumerate(questions):
        ids = selected.get(f"q{index}")
        options = {str(i): option for i, option in enumerate(question["options"])}
        if (
            not isinstance(ids, list)
            or not ids
            or not all(isinstance(i, str) for i in ids)
            or len(ids) != len(set(ids))
            or any(i not in options for i in ids)
            or (not question.get("multiSelect") and len(ids) != 1)
        ):
            raise ValueError("Invalid option selection")
        answers.append(
            {
                "question": question["question"],
                "multiSelect": bool(question.get("multiSelect")),
                "answer": [{"label": options[i]["label"]} for i in ids],
            }
        )
    return answers


def submitted_question_card(
    interrupt: dict, session_code: str, *, text: str = "答案已接收", answers: list | None = None
) -> dict | None:
    """Replace the controls with a result notice linked only to the original session."""
    card = build_question_card(interrupt, session_code)
    if card is None:
        return None
    session_url = AgentHelper.build_session_detail_url(session_code)
    try:
        parsed = urlsplit(session_url)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    card["main_title"]["desc"] = "点击查看原会话"
    for key in ("checkbox", "select_list", "submit_button"):
        card.pop(key, None)
    lines = [text]
    for index, answer in enumerate(answers or [], 1):
        if len(answers) > 1:
            lines.append(f"\n{index}. {answer['question']}")
        labels = "、".join(option["label"] for option in answer["answer"])
        lines.append(f"你的答案：{labels}")
    card.update(
        card_type="text_notice",
        sub_title_text="\n".join(lines),
        card_action={"type": 1, "url": _normalize_url(session_url)},
    )
    return card
