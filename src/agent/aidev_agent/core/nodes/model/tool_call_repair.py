# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Tool name pattern: alphanumeric, underscore, hyphen
_TOOL_NAME_RE = re.compile(r"[A-Za-z0-9_-]+")
# XML-ish function name pattern
_XML_FUNC_NAME_RE = re.compile(r"[A-Za-z0-9_.:\-]{1,120}")
# XML-ish parameter name pattern
_XML_PARAM_NAME_RE = re.compile(r"[A-Za-z0-9_.:\-]{1,120}")


@dataclass
class ParsedToolCall:
    """Represents a single tool call parsed from plain text."""

    name: str
    arguments: dict


def parse_standalone_plain_text_tool_call_blocks(
    text: str,
    allowed_tool_names: set[str],
) -> list[ParsedToolCall] | None:
    """Parse plain-text tool call blocks, returning a list only if ALL text is consumed.

    Tries three parser formats at each position (bracket, harmony, XML-ish).
    If any portion of the text cannot be parsed as a valid tool call, returns None
    (all-or-nothing semantics). Tool names must match ``allowed_tool_names``
    case-insensitively.

    Args:
        text: The full text to parse.
        allowed_tool_names: Set of valid tool names (case-insensitive matching).

    Returns:
        A list of ParsedToolCall if all text is consumed as valid tool calls,
        or None if any portion fails.
    """
    if not text or not text.strip():
        return None

    # Build a case-insensitive lookup: lowered_name -> canonical_name
    name_lookup: dict[str, str] = {n.lower(): n for n in allowed_tool_names}

    results: list[ParsedToolCall] = []
    cursor = 0
    length = len(text)

    while cursor < length:
        # Skip leading whitespace / newlines between blocks
        while cursor < length and text[cursor] in (" ", "\t", "\n", "\r"):
            cursor += 1
        if cursor >= length:
            break

        # Try each parser in order
        parsed, new_cursor = _try_bracket_format(text, cursor, name_lookup)
        if parsed is not None:
            results.append(parsed)
            cursor = new_cursor
            continue

        parsed, new_cursor = _try_harmony_format(text, cursor, name_lookup)
        if parsed is not None:
            results.append(parsed)
            cursor = new_cursor
            continue

        parsed, new_cursor = _try_xml_format(text, cursor, name_lookup)
        if parsed is not None:
            results.append(parsed)
            cursor = new_cursor
            continue

        # No parser matched — not all text is tool calls
        return None

    if not results:
        return None
    return results


# ---------------------------------------------------------------------------
# Bracket Format Parser
# ---------------------------------------------------------------------------


def _try_bracket_format(
    text: str,
    cursor: int,
    name_lookup: dict[str, str],
) -> tuple[ParsedToolCall | None, int]:
    """Try parsing a bracket-format tool call at *cursor*.

    Patterns::

        [tool:name]{"arg": "val"}
        [name]\\n{"arg": "val"}

    With optional closing markers: ``[END_TOOL_REQUEST]`` or ``[/name]``.
    """
    if cursor >= len(text) or text[cursor] != "[":
        return None, cursor

    # --- Parse header ---
    # Check for [tool:name] variant
    tool_prefix_match = re.match(r"\[tool:", text[cursor:])
    if tool_prefix_match:
        name_start = cursor + len("[tool:")
        m = _TOOL_NAME_RE.match(text, name_start)
        if not m or m.end() >= len(text) or text[m.end()] != "]":
            return None, cursor
        name = m.group()
        pos = m.end() + 1  # skip ']'
        # No line break required after [tool:name]
    else:
        # Plain [name] variant
        m = _TOOL_NAME_RE.match(text, cursor + 1)
        if not m or m.end() >= len(text) or text[m.end()] != "]":
            return None, cursor
        name = m.group()
        pos = m.end() + 1  # skip ']'
        # Require a line break after ]
        if pos < len(text) and text[pos] == "\n":
            pos += 1
        elif pos < len(text) and text[pos] == "\r":
            pos += 1
            if pos < len(text) and text[pos] == "\n":
                pos += 1
        else:
            # No line break after plain [name] — not a bracket format
            return None, cursor

    # Validate name against allowed
    canonical = name_lookup.get(name.lower())
    if canonical is None:
        return None, cursor

    # --- Find JSON object ---
    json_obj, pos = _extract_json_object(text, pos)
    if json_obj is None:
        return None, cursor

    # --- Optional closing markers ---
    saved_pos = pos
    pos = _skip_whitespace(text, pos)

    # Try [END_TOOL_REQUEST]
    if text[pos:].startswith("[END_TOOL_REQUEST]"):
        pos += len("[END_TOOL_REQUEST]")
        pos = _skip_whitespace(text, pos)
    # Try [/name]
    elif text[pos:].startswith(f"[/{name}]"):
        pos += len(f"[/{name}]")
        pos = _skip_whitespace(text, pos)
    else:
        pos = saved_pos

    return ParsedToolCall(name=canonical, arguments=json_obj), pos


# ---------------------------------------------------------------------------
# Harmony Format Parser
# ---------------------------------------------------------------------------


def _try_harmony_format(
    text: str,
    cursor: int,
    name_lookup: dict[str, str],
) -> tuple[ParsedToolCall | None, int]:
    """Try parsing a harmony-format tool call at *cursor*.

    Pattern::

        [<|channel|>]commentary|analysis|final to=tool_name code [<|message|>]
        {"arg": "val"}

    With optional ``<|call|>`` closing marker.
    """
    pos = cursor

    # Optional opening '[' bracket
    if pos < len(text) and text[pos] == "[":
        pos += 1

    # Optional <|channel|> prefix
    if text[pos:].startswith("<|channel|>"):
        pos += len("<|channel|>")
        # Skip optional closing ']' after channel marker
        if pos < len(text) and text[pos] == "]":
            pos += 1

    # Channel keyword: commentary, analysis, or final
    for kw in ("commentary", "analysis", "final"):
        if text[pos:].startswith(kw):
            pos += len(kw)
            break
    else:
        return None, cursor

    # Skip whitespace
    pos = _skip_whitespace(text, pos)

    # to=tool_name
    if not text[pos:].startswith("to="):
        return None, cursor
    pos += len("to=")

    m = _TOOL_NAME_RE.match(text, pos)
    if not m:
        return None, cursor
    name = m.group()
    pos = m.end()

    # Validate name
    canonical = name_lookup.get(name.lower())
    if canonical is None:
        return None, cursor

    # Skip whitespace
    pos = _skip_whitespace(text, pos)

    # "code" keyword
    if not text[pos:].startswith("code"):
        return None, cursor
    pos += len("code")

    # Skip whitespace
    pos = _skip_whitespace(text, pos)

    # Optional [<|message|>] or <|message|> marker
    if text[pos:].startswith("[<|message|>]"):
        pos += len("[<|message|>]")
    elif text[pos:].startswith("<|message|>"):
        pos += len("<|message|>")

    # Skip whitespace/newlines
    pos = _skip_whitespace(text, pos)

    # --- Find JSON object ---
    json_obj, pos = _extract_json_object(text, pos)
    if json_obj is None:
        return None, cursor

    # --- Optional <|call|> closing ---
    saved_pos = pos
    pos = _skip_whitespace(text, pos)
    if text[pos:].startswith("<|call|>"):
        pos += len("<|call|>")
    else:
        pos = saved_pos

    return ParsedToolCall(name=canonical, arguments=json_obj), pos


# ---------------------------------------------------------------------------
# XML-ish Format Parser
# ---------------------------------------------------------------------------


def _try_xml_format(
    text: str,
    cursor: int,
    name_lookup: dict[str, str],
) -> tuple[ParsedToolCall | None, int]:
    """Try parsing an XML-ish format tool call at *cursor*.

    Pattern::

        <function=tool_name>
          <parameter=key>value</parameter>
        </function>
    """
    pos = cursor

    # Opening: <function=name>
    if not text[pos:].startswith("<function="):
        return None, cursor
    pos += len("<function=")

    m = _XML_FUNC_NAME_RE.match(text, pos)
    if not m or pos + len(m.group()) >= len(text) or text[pos + len(m.group())] != ">":
        return None, cursor
    name = m.group()
    pos += len(m.group()) + 1  # skip '>'

    # Validate name
    canonical = name_lookup.get(name.lower())
    if canonical is None:
        return None, cursor

    # Parse parameters
    args: dict = {}
    while pos < len(text):
        # Skip whitespace
        pos = _skip_whitespace(text, pos)

        # Check for closing </function>
        if text[pos:].startswith("</function>"):
            pos += len("</function>")
            return ParsedToolCall(name=canonical, arguments=args), pos

        # Check for <parameter=key>
        if not text[pos:].startswith("<parameter="):
            # Unknown content — fail
            return None, cursor
        pos += len("<parameter=")

        pm = _XML_PARAM_NAME_RE.match(text, pos)
        if not pm or pos + len(pm.group()) >= len(text) or text[pos + len(pm.group())] != ">":
            return None, cursor
        param_name = pm.group()
        pos += len(pm.group()) + 1  # skip '>'

        # Read raw value until </parameter> (case-insensitive close)
        close_tag = "</parameter>"
        close_idx = text.lower().find(close_tag.lower(), pos)
        if close_idx == -1:
            return None, cursor

        value = text[pos:close_idx]
        # Strip leading/trailing line breaks from parameter values
        value = value.strip("\n\r")
        # Try to parse as JSON for type consistency with bracket/harmony formats
        try:
            parsed_value = json.loads(value)
            if isinstance(parsed_value, (dict, list, int, float, bool)):
                args[param_name] = parsed_value
            else:
                args[param_name] = value
        except (json.JSONDecodeError, ValueError):
            args[param_name] = value
        pos = close_idx + len(close_tag)

    # Reached end without </function>
    return None, cursor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skip_whitespace(text: str, pos: int) -> int:
    """Advance *pos* past whitespace characters."""
    while pos < len(text) and text[pos] in (" ", "\t", "\n", "\r"):
        pos += 1
    return pos


def _extract_json_object(text: str, pos: int) -> tuple[dict | None, int]:
    """Extract a JSON object ``{...}`` starting at *pos* using balanced brace counting.

    Returns (parsed_dict, new_pos) or (None, pos) on failure.
    """
    # Skip whitespace before JSON
    while pos < len(text) and text[pos] in (" ", "\t", "\n", "\r"):
        pos += 1

    if pos >= len(text) or text[pos] != "{":
        return None, pos

    start = pos
    depth = 0
    in_string = False
    escape_next = False

    while pos < len(text):
        ch = text[pos]
        if escape_next:
            escape_next = False
            pos += 1
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            pos += 1
            continue
        if ch == '"':
            in_string = not in_string
            pos += 1
            continue
        if in_string:
            pos += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                pos += 1
                json_str = text[start:pos]
                try:
                    obj = json.loads(json_str)
                    if isinstance(obj, dict):
                        return obj, pos
                except json.JSONDecodeError:
                    pass
                return None, start
        pos += 1

    return None, start
