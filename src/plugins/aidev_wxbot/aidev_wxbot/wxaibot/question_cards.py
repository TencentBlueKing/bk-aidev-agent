"""Native Ask-user cards, signed session binding and strict option decoding."""

import copy
import hashlib
import json
from dataclasses import asdict, dataclass, replace

from aidev_agent.core.ag_ui.ask_user_question import ASK_USER_QUESTION_REASON
from django.core import signing

from .context import _escape_markdown_text

_PREFIX = "question_answer:"
_SALT = "aidev.wxbot.question.v1"
MAX_AGE = 86400


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
    if not questions or len(questions) > 3:
        return None
    for question in questions:
        options = question.get("options")
        if not isinstance(options, list) or not 1 <= len(options) <= (20 if len(questions) == 1 else 9):
            return None
        if not isinstance(question.get("question"), str) or len(question["question"].encode()) > 72:
            return None
        if any(
            not isinstance(option, dict)
            or not isinstance(option.get("label"), str)
            or not option["label"]
            or len(option["label"].encode()) > 32
            for option in options
        ):
            return None
    if len(questions) == 1:
        return "vote_interaction"
    return "multiple_interaction" if not any(q.get("multiSelect") for q in questions) else None


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


def question_prompt(interrupt: dict) -> str:
    """Keep the complete questions and option descriptions available in chat."""
    lines = ["请直接在企微回复答案，也可以使用下方卡片选择（如有）。"]
    for index, question in enumerate((interrupt.get("metadata") or {}).get("questions") or [], 1):
        if not isinstance(question, dict):
            continue
        lines.append(f"\n{index}. {_escape_markdown_text(str(question.get('question') or '请补充信息'))}")
        for option in question.get("options") or []:
            if not isinstance(option, dict):
                continue
            text = str(option.get("label") or "")
            if option.get("description"):
                text += f"：{option['description']}"
            lines.append(f"- {_escape_markdown_text(text)}")
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
                "selected_id": "_",
                "option_list": [{"id": "_", "text": "请选择"}]
                + [{"id": str(j), "text": o["label"]} for j, o in enumerate(q["options"])],
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


def submitted_question_card(interrupt: dict, session_code: str, *, text: str = "答案已接收") -> dict:
    card = build_question_card(interrupt, session_code) or {"main_title": {"title": text}, "card_action": {"type": 0}}
    card["main_title"].pop("desc", None)
    for key in ("checkbox", "select_list", "submit_button"):
        card.pop(key, None)
    card.update(card_type="text_notice", sub_title_text=text)
    return card
