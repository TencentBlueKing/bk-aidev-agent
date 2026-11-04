"""Adapt reference links for the existing UI without changing native retrieval records."""

from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _normalize_preview_url(value: str) -> str:
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    prefix, route, suffix = parts.path.rpartition("/agent-develop/knowledgebase")
    if not route or (suffix and not suffix.startswith("/")):
        return value
    path = prefix.rstrip("/") + route + suffix
    if path == parts.path:
        return value
    return urlunsplit(parts._replace(path=path))


def _reference_document_for_display(item: dict[str, Any]) -> dict[str, Any]:
    document = dict(item)
    metadata = item.get("metadata")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    source = _text(metadata.get("path"))
    preview = _text(metadata.get("preview_path"))
    if not source and not preview:
        if "originFileUrl" in item or "origin_file_url" in item:
            source = _text(item.get("originFileUrl") or item.get("origin_file_url"))
            preview = _text(item.get("url"))
        elif "originFile" in item or "origin_file" in item:
            source = _text(item.get("url"))
            preview = _text(item.get("originFile") or item.get("origin_file"))
        else:
            return document
    if not source and not preview:
        return document
    normalized_preview = _normalize_preview_url(preview)
    if source == preview:
        source = normalized_preview
    name = _text(item.get("name") or metadata.get("display_name")) or source or normalized_preview
    metadata.update(display_name=name, path=source, preview_path=normalized_preview)
    # The existing UI reads url for preview and originFile for the source.
    # Explicit metadata preserves source identity for SDK and bot consumers.
    document.update(
        name=name,
        url=normalized_preview or source,
        originFile=source or normalized_preview,
        metadata=metadata,
    )
    return document


def reference_documents_for_display(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return items
    return [_reference_document_for_display(item) if isinstance(item, dict) else item for item in items]
