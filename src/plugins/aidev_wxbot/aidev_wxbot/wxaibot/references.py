"""Normalize retrieval events for both WeCom streaming transports."""

from typing import Any

from aidev_agent.core.citations import CITATION_KEY, citation_index


def collect_reference_documents(event: dict[str, Any], documents: list[dict]) -> None:
    payload = event.get("documents")
    if event.get("name") == "knowledge_rag_result" and isinstance(event.get("value"), list):
        payload = event.get("value")
    if not isinstance(payload, list):
        return
    seen = {document.get("path") or document.get("preview_path") for document in documents}
    for document in payload:
        if not isinstance(document, dict):
            continue
        metadata = document.get("metadata")
        source = metadata if isinstance(metadata, dict) else document
        name = source.get("display_name") or source.get("name")
        path = source.get("path") or source.get("url")
        preview_path = source.get("preview_path") or source.get("originFile")
        if not isinstance(path, str) or not path.strip():
            path = preview_path if isinstance(preview_path, str) else ""
        path = path.strip()
        if not path or path in seen:
            continue
        seen.add(path)
        normalized = dict(metadata) if isinstance(metadata, dict) else {}
        normalized.update(display_name=name if isinstance(name, str) and name else path, path=path)
        if isinstance(preview_path, str) and preview_path:
            normalized["preview_path"] = preview_path
        number = citation_index(document)
        if number is not None:
            normalized[CITATION_KEY] = number
        documents.append(normalized)
