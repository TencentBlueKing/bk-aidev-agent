"""Answer text normalization shared by model processing and memory evidence."""

import re
from bisect import bisect_right
from collections import defaultdict

_TOKEN_RE = re.compile(
    r"(?P<literal_line>^(?:[ ]{0,3}>|[ ]{4}|[ ]*\t)[^\n]*)"
    r"|(?P<escaped>\\[\\`<])|(?P<ticks>`+)|(?P<tildes>~{3,})"
    r"|(?P<thought><(?P<tag>think|thinking|reasoning)>)",
    re.IGNORECASE | re.MULTILINE,
)
_TICKS_RE = re.compile(r"`+")
_CLOSE_RE = re.compile(r"</(?P<tag>think|thinking|reasoning)>", re.IGNORECASE)
_BLANK_RE = re.compile(r"\n[ \t\r]*\n")
_FENCE_RE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})(?P<tail>[^\n]*)(?:\n|\Z)", re.MULTILINE)


def strip_think_blocks(content: str, *, preserve_whitespace: bool = False) -> str:
    """Remove reasoning outside visible Markdown literals using forward scanning.

    Index closing delimiters once. Unmatched code runs and reasoning openers
    must not repeatedly search the remaining answer or retry delimiter suffixes.
    Real reasoning consumes its contents before interpreting any Markdown there.
    """
    ticks = defaultdict(list)
    for match in _TICKS_RE.finditer(content):
        ticks[len(match.group())].append(match.start())
    closes = defaultdict(list)
    for match in _CLOSE_RE.finditer(content):
        closes[match.group("tag").lower()].append((match.start(), match.end()))
    blank_lines = [match.start() for match in _BLANK_RE.finditer(content)]
    line_starts = [0, *(match.end() for match in re.finditer("\n", content))]
    fences = list(_FENCE_RE.finditer(content))
    fence_starts = [match.start("fence") for match in fences]
    pieces = []
    retained_start = skip_until = 0
    for token in _TOKEN_RE.finditer(content):
        start = token.start()
        if start < skip_until or token.lastgroup in {"literal_line", "escaped"}:
            continue
        if token.group("ticks") or token.group("tildes"):
            delimiter = token.group()
            line_start = line_starts[bisect_right(line_starts, start) - 1]
            if len(delimiter) >= 3 and start - line_start <= 3 and not content[line_start:start].strip():
                # Each scanned fence belongs to a block consumed below, so even
                # an unclosed block examines each following fence only once.
                skip_until = len(content)
                for fence_index in range(bisect_right(fence_starts, start), len(fences)):
                    fence = fences[fence_index]
                    closing = fence.group("fence")
                    if (
                        closing[0] == delimiter[0]
                        and len(closing) >= len(delimiter)
                        and not fence.group("tail").strip()
                    ):
                        skip_until = fence.end()
                        break
            elif token.group("ticks"):
                positions = ticks[len(delimiter)]
                next_tick = bisect_right(positions, start)
                next_blank = bisect_right(blank_lines, start)
                paragraph_end = blank_lines[next_blank] if next_blank < len(blank_lines) else len(content)
                if next_tick < len(positions) and positions[next_tick] < paragraph_end:
                    skip_until = positions[next_tick] + len(delimiter)
        else:
            tag = token.group("tag").lower()
            positions = closes[tag]
            next_close = bisect_right(positions, (start, len(content)))
            if next_close < len(positions):
                pieces.append(content[retained_start:start])
                retained_start = skip_until = positions[next_close][1]
    pieces.append(content[retained_start:])
    result = "".join(pieces)
    if preserve_whitespace:
        return result
    # Keep meaningful code indentation recognizable when history is normalized
    # again; otherwise preserve the existing writer's ordinary whitespace trim.
    first_text = len(result) - len(result.lstrip())
    line_start = result.rfind("\n", 0, first_text) + 1
    if len(result[line_start:first_text].expandtabs(4)) >= 4:
        return result[line_start:].rstrip()
    return result.strip()
