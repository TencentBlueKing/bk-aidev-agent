"""Number knowledge sources once per run so answer markers, the web panel and bots point at the same documents."""

import re
import threading
from collections.abc import Iterable, Mapping
from typing import Any

CITATION_KEY = "citation_index"
CITATION_INSTRUCTION = (
    "引用规则：以下知识带有“引用编号”，编号是回答的证据链。只依据与问题相关的知识作答，"
    "每一句来自知识的事实都必须在句末标注支撑它的编号，如 [1]，多条来源写成 [1][2]；推断或通用知识不标编号，"
    "与问题无关的知识不要引用。知识无法支撑的内容要说明知识库未提及，不要编造编号，"
    "也不要在回答末尾另列参考文档或来源链接，系统会按编号附上文档。"
)
# The platform prefixes every knowledge chunk that has a link with this line.
_SOURCE_LINE = re.compile(r"^来源链接：(?P<url>[^\n]+)", re.MULTILINE)
_MARKER = re.compile(r"\[(\d{1,3})\]")
# Brackets inside fenced code blocks and inline code are indexing, such as items[1], never citations.
_CODE = re.compile(r"```[\s\S]*?(?:```|$)|`[^`\n]*`")


class CitationRegistry:
    """Run-scoped source numbers; tool calls of one batch may run in parallel threads."""

    def __init__(self) -> None:
        self._numbers: dict[str, int] = {}
        self._lock = threading.Lock()

    def number(self, identity: str) -> int:
        with self._lock:
            return self._numbers.setdefault(identity, len(self._numbers) + 1)

    def find(self, identity: str) -> int | None:
        with self._lock:
            return self._numbers.get(identity)


def cite_knowledge(
    knowledge_content: list, reference_doc: list[dict], citations: CitationRegistry
) -> tuple[list, list[dict]]:
    """Number the chunks the model reads and tag the reference documents with the same numbers.

    Chunks without a source line stay unnumbered, so platforms that omit it keep the previous prompt.
    """
    numbered = []
    for item in knowledge_content:
        match = _SOURCE_LINE.search(item) if isinstance(item, str) else None
        number = citations.number(match["url"].strip()) if match else None
        numbered.append(f"引用编号：[{number}]\n{item}" if number else item)
    if numbered != knowledge_content:
        numbered.insert(0, CITATION_INSTRUCTION)

    documents = []
    for each in reference_doc:
        metadata = each["metadata"]
        path, preview = metadata.get("path") or "", metadata.get("preview_path") or ""
        document = {"originFile": preview, "url": path, "name": metadata.get("display_name") or ""}
        number = citations.find(path or preview)
        if number is not None:
            document[CITATION_KEY] = number
        documents.append(document)
    return numbered, documents


def citation_index(item: object) -> int | None:
    if not isinstance(item, Mapping):
        return None
    value = item.get(CITATION_KEY)
    metadata = item.get("metadata")
    if value is None and isinstance(metadata, Mapping):
        value = metadata.get(CITATION_KEY)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def cited_numbers(text: object) -> set[int]:
    """Collect markers such as [1] and [1][2] from an answer."""
    if not isinstance(text, str):
        return set()
    return {int(number) for number in _MARKER.findall(_CODE.sub("", text))}


def select_cited(items: Iterable[Any], text: object) -> list | None:
    """Prefer numbered citations, then unambiguous full titles mentioned outside code."""
    items = list(items)
    cited = cited_numbers(text)
    selected = [item for item in items if citation_index(item) in cited]
    if not selected and isinstance(text, str):
        prose = _CODE.sub("", text)
        titles: dict[str, list] = {}
        for item in items:
            if citation_index(item) is None:
                continue
            metadata = item.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            title = metadata.get("display_name") or item.get("display_name") or item.get("name")
            if not isinstance(title, str) or not title.strip():
                continue
            title = re.sub(r"^\[\d+\]\s*", "", title.strip())
            titles.setdefault(title, []).append(item)
        for title, documents in titles.items():
            if len({citation_index(document) for document in documents}) != 1:
                continue
            quoted = f"《{title}》" in prose
            full_title = len(title) >= 4 and re.search(r"(?<!\w)" + re.escape(title) + r"(?!\w)", prose)
            if quoted or full_title:
                selected.extend(documents)
    return sorted(selected, key=citation_index) if selected else None


def renumber_citations(text: str, numbers: Mapping[int, int]) -> str:
    """Rewrite markers in one pass so a remapped number is never remapped again; code is left untouched."""
    if not numbers:
        return text

    def rewrite(prose: str) -> str:
        return _MARKER.sub(lambda match: f"[{numbers.get(int(match[1]), int(match[1]))}]", prose)

    parts, start = [], 0
    for code in _CODE.finditer(text):
        parts.extend((rewrite(text[start : code.start()]), code[0]))
        start = code.end()
    parts.append(rewrite(text[start:]))
    return "".join(parts)


def uses_citations(state_values: Mapping[str, Any]) -> bool:
    """Whether this run gave the model numbered sources, directly or through a child agent result."""
    contents = [*(state_values.get("knowledge_content") or [])]
    contents.extend(getattr(message, "content", "") for message in state_values.get("messages") or [])
    return any(CITATION_INSTRUCTION in str(content) or f'"{CITATION_KEY}"' in str(content) for content in contents)
