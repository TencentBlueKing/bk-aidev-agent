# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Protocol, runtime_checkable

from typing_extensions import NotRequired, TypedDict


class SkillOptions(TypedDict):
    """Skill metadata parsed from SKILL.md YAML frontmatter.

    Follows Agent Skills spec (https://agentskills.io/specification).
    """

    name: str
    description: str
    path: str
    license: NotRequired[str]
    compatibility: NotRequired[str]
    metadata: NotRequired[dict[str, str]]
    allowed_tools: NotRequired[list[str]]
    instructions: NotRequired[str]
    runtime: NotRequired[str]
    approval: NotRequired[dict]
    callee_agent_code: NotRequired[str]


@runtime_checkable
class SkillProviderBackend(Protocol):
    """Skill provider backend protocol.

    Any object implementing ``discover`` and ``fetch_instructions`` can serve
    as a skill provider backend for :class:`~aidev_agent.core.tools.skill.provider.SkillRegistry`.  Using :pep:`544`
    structural sub-typing (Protocol) instead of ABC so that providers need
    not inherit from a base class – duck-typing is sufficient.
    """

    def discover(self) -> list[SkillOptions]:
        """Return metadata for all skills offered by this provider.

        The returned list should contain :class:`SkillOptions` dicts
        **without** the ``instructions`` field populated (lazy loading).
        """
        ...

    def fetch_instructions(self, skill: SkillOptions) -> str:
        """Fetch the full instruction text for *skill*.

        Returns the SKILL.md body with YAML frontmatter stripped.
        """
        ...
