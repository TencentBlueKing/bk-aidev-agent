"""Adapt reference links for the existing UI without changing native retrieval records."""

from typing import Any, NamedTuple
from urllib.parse import SplitResult, urlsplit, urlunsplit

_KNOWLEDGE_PREVIEW_ROUTE = "/agent-develop/knowledgebase"
_LINK_ALIASES = ("originFileUrl", "origin_file_url", "originFile", "origin_file")


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
    name = _text(item.get("name") or metadata.get("display_name")) or source or preview
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
    # The existing UI opens url from the title and shows the preview/source icons only when originFile is set.
    # Explicit metadata preserves source identity for SDK and bot consumers.
    return {
        **item,
        "name": links.name,
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
