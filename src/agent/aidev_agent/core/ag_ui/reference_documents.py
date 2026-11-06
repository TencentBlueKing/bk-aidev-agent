"""Adapt reference links for the existing UI without changing native retrieval records."""

from typing import Any, NamedTuple
from urllib.parse import SplitResult, urlsplit, urlunsplit

from aidev_agent.core.citations import citation_index, cited_numbers, select_cited

_KNOWLEDGE_PREVIEW_ROUTE = "/agent-develop/knowledgebase"
_LINK_ALIASES = ("originFileUrl", "origin_file_url", "originFile", "origin_file")
_USER_ROLES = ("user", "user-image")
_ANSWER_ROLES = ("assistant", "ai")


class ReferenceLinks(NamedTuple):
    """Links of one retrieved document.

    ``path`` keeps the platform meaning: the original link of web knowledge, otherwise the preview.
    ``external`` is set only for web knowledge; uploaded files and ZIP imports have no original link to open.
    """

    name: str
    path: str
    preview: str
    external: str


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _link(value: object) -> str:
    return _text(value).strip()


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _knowledge_preview_parts(value: str) -> tuple[SplitResult, str] | None:
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    prefix, route, suffix = parts.path.rpartition(_KNOWLEDGE_PREVIEW_ROUTE)
    if not route or (suffix and not suffix.startswith("/")):
        return None
    path = prefix.rstrip("/") + route + suffix
    return parts, path


def _is_knowledge_preview(value: str) -> bool:
    return _knowledge_preview_parts(value) is not None


def _normalize_preview_url(value: str) -> str:
    parsed = _knowledge_preview_parts(value)
    if parsed is None:
        return value
    parts, path = parsed
    if path == parts.path:
        return value
    return urlunsplit(parts._replace(path=path))


def _source_and_preview(item: dict[str, Any], metadata: dict[str, Any]) -> tuple[str, str]:
    source, preview = _link(metadata.get("path")), _link(metadata.get("preview_path"))
    if source or preview:
        return source, preview
    if "originFileUrl" in item or "origin_file_url" in item:
        return _link(item.get("originFileUrl") or item.get("origin_file_url")), _link(item.get("url"))
    if "originFile" in item or "origin_file" in item:
        return _link(item.get("url")), _link(item.get("originFile") or item.get("origin_file"))
    return _link(item.get("url")), ""


def resolve_reference_links(item: object) -> ReferenceLinks | None:
    """Resolve explicit metadata and the known UI aliases into one source/preview pair."""
    if not isinstance(item, dict):
        return None
    metadata = _metadata(item)
    source, preview = _source_and_preview(item, metadata)
    if _is_knowledge_preview(source) and not _is_knowledge_preview(preview):
        source, preview = preview, source
    if not source and not preview:
        return None
    source, preview = _normalize_preview_url(source), _normalize_preview_url(preview)
    # display_name keeps the bare title; the display adapter may prefix name with the citation number.
    name = _text(metadata.get("display_name") or item.get("name")) or source or preview
    is_external = bool(source) and source != preview and not _is_knowledge_preview(source)
    return ReferenceLinks(name=name, path=source, preview=preview, external=source if is_external else "")


def _display_document(item: dict[str, Any]) -> dict[str, Any] | None:
    metadata = _metadata(item)
    has_links = (
        _link(metadata.get("path")) or _link(metadata.get("preview_path")) or any(key in item for key in _LINK_ALIASES)
    )
    links = resolve_reference_links(item) if has_links else None
    if links is None:
        return None
    number = citation_index(item)
    # The existing UI opens url from the title and shows the preview/source icons only when originFile is set.
    # The title carries the citation number so it matches the [n] markers in the answer.
    # Explicit metadata preserves source identity and the bare title for SDK and bot consumers.
    return {
        **item,
        "name": f"[{number}] {links.name}" if number else links.name,
        "url": links.preview or links.path,
        "originFile": links.external if links.preview else "",
        "metadata": {**metadata, "display_name": links.name, "path": links.path, "preview_path": links.preview},
    }


def reference_documents_for_display(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return items
    return [(_display_document(item) or dict(item)) if isinstance(item, dict) else item for item in items]


def _history_document(item: object) -> object:
    document = _display_document(item) if isinstance(item, dict) else None
    if document is None:
        return item
    document.pop("originFileUrl", None)
    document.pop("origin_file", None)
    document["origin_file_url"] = document["originFile"]
    return document


def history_reference_documents(content: object, activity_type: object) -> object:
    """Rewrite saved reference activity content to the live display contract, returning a copy.

    The history transform keeps only ``name``, ``url`` and ``origin_file_url``: the title opens the same
    preview as the live message, and ``origin_file_url`` / ``originFile`` carry only the external link.
    """
    if activity_type == "reference_document" and isinstance(content, list):
        return [_history_document(item) for item in content]
    documents = content.get("reference_document") if isinstance(content, dict) else None
    if activity_type == "knowledge_rag" and isinstance(documents, list):
        return {**content, "reference_document": [_history_document(item) for item in documents]}
    return content


def reference_activity_documents(content: object, activity_type: object) -> list | None:
    """Documents of a saved reference activity, or None for other activities."""
    if activity_type == "reference_document" and isinstance(content, list):
        return content
    documents = content.get("reference_document") if isinstance(content, dict) else None
    return documents if activity_type == "knowledge_rag" and isinstance(documents, list) else None


def keep_cited_documents(content: object, activity_type: object, cited: set[int]) -> object:
    """Return a copy of a reference activity that keeps only the documents with a cited number."""
    documents = reference_activity_documents(content, activity_type)
    if documents is None:
        return content
    kept = [item for item in documents if citation_index(item) in cited]
    return kept if isinstance(content, list) else {**content, "reference_document": kept}


def _activity_type(payload: dict) -> object:
    builtin_property = payload.get("builtin_property")
    builtin_property = builtin_property if isinstance(builtin_property, dict) else {}
    return builtin_property.get("activity_type") or payload.get("activity_type") or builtin_property.get("type")


def _arrange_turn(turn: list[dict]) -> list[dict]:
    references = []
    for payload in turn:
        activity_type = _activity_type(payload)
        if payload.get("role") == "activity" and reference_activity_documents(payload.get("content"), activity_type):
            payload["content"] = history_reference_documents(payload["content"], activity_type)
            references.append(payload)
    if not references:
        return turn
    answer = "".join(
        payload["content"]
        for payload in turn
        if payload.get("role") in _ANSWER_ROLES and isinstance(payload.get("content"), str)
    )
    documents = [
        item
        for payload in references
        for item in reference_activity_documents(payload["content"], _activity_type(payload))
    ]
    if select_cited(documents, answer) is not None:
        cited = cited_numbers(answer)
        for payload in references:
            payload["content"] = keep_cited_documents(payload["content"], _activity_type(payload), cited)
    answers = [index for index, payload in enumerate(turn) if payload.get("role") in _ANSWER_ROLES]
    if not answers:
        return turn
    # The UI folds everything before the final answer; the references come right after it to stay in view.
    shown = [
        payload for payload in references if reference_activity_documents(payload["content"], _activity_type(payload))
    ]
    ids = {id(payload) for payload in references}
    before = [payload for payload in turn[: answers[-1] + 1] if id(payload) not in ids]
    after = [payload for payload in turn[answers[-1] + 1 :] if id(payload) not in ids]
    return [*before, *shown, *after]


def arrange_reference_history(records: list[dict]) -> list[dict]:
    """Arrange reference activities of saved turns for display, changing the given copies in place.

    Links follow the live display contract. When the answer cites [n], each turn keeps only the cited
    documents and drops a retrieval none of them came from; otherwise every retrieved document stays.
    Answered turns list the references right after the final answer. Saved records are never written.
    """
    arranged: list[dict] = []
    turn: list[dict] = []
    for payload in records:
        if payload.get("role") in _USER_ROLES:
            arranged.extend(_arrange_turn(turn))
            turn = []
        turn.append(payload)
    arranged.extend(_arrange_turn(turn))
    return arranged
