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

from typing import Literal

from aidev_agent.enums import Decision

from .pydantic_models import NextFunction, ProcessorContext

PromptMode = Literal["tool_calling", "structured_chat"]


def _get_prompt_atoms():
    """Delayed import to avoid `nodes/` depending on `graphs/` at import time."""

    from aidev_agent.core.graphs.react import prompts as p

    return p


class StructuredChatFormatMiddleware:
    """Set prompt mode and placeholder conventions.

    - tool_calling: use system+human messages and agent_scratchpad placeholder
    - structured_chat: use human messages (system instructions in human) and
      embed agent_scratchpad inside the final human content.
    """

    def __init__(self, *, use_structured_response: bool):
        self.use_structured_response = use_structured_response

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        mode: PromptMode = "structured_chat" if self.use_structured_response else "tool_calling"
        ctx.metadata["prompt_mode"] = mode

        if mode == "structured_chat":
            # NOTE: for structured_chat, agent_scratchpad must be inside human.
            ctx.prompt_slots.agent_scratchpad_slot = False

        next()


class RoleDefinitionMiddleware:
    """Set base role definition for tool_calling system prompt."""

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        mode = ctx.metadata.get("prompt_mode", "tool_calling")
        if mode == "tool_calling":
            p = _get_prompt_atoms()
            ctx.prompt_slots.system = p.ATOM_ROLE_DEFINITION

        next()


class DecisionSystemMiddleware:
    """Append decision-specific system/human prompt atoms into PromptSlots."""

    _ATOM_GENERAL_TOOL_CALLING_SYSTEM_CORE = (
        "负责回答用户最新提问。"
        "{% if use_general_knowledge_on_miss %}"
        "{% if has_tools %}请优先判断是否有相关工具可调用，仅当工具与问题无关时，才使用通识知识回答。{% endif -%}"
        "{% if not has_tools %}请用通识知识回答。{% endif -%}"
        "{% endif -%}"
        "{% if not use_general_knowledge_on_miss %}如果无法使用提供的工具回答，请使用拒答文案'{{rejection_response}}'拒绝回答。{% endif -%}"
    )

    def __init__(self, *, enable_query_clarification: bool):
        self.enable_query_clarification = enable_query_clarification

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        p = _get_prompt_atoms()

        decision = ctx.state.get("decision", Decision.GENERAL_QA)
        if decision == Decision.GENERAL_QA:
            decision_type: Literal["general", "private", "clarifying"] = "general"
        elif decision == Decision.PRIVATE_QA:
            decision_type = "private"
        elif decision == Decision.QUERY_CLARIFICATION:
            decision_type = "clarifying" if self.enable_query_clarification else "private"
        else:
            decision_type = "general"

        mode: PromptMode = ctx.metadata.get("prompt_mode", "tool_calling")

        if mode == "structured_chat":
            # Structured chat prompts are already full, including beijing/no_system.
            if decision_type == "general":
                ctx.prompt_slots.system = p.ATOM_GENERAL_STRUCTURED_SYSTEM
                ctx.prompt_slots.human = p.ATOM_GENERAL_STRUCTURED_HUMAN
            else:
                ctx.prompt_slots.system = p.ATOM_PRIVATE_STRUCTURED_SYSTEM
                ctx.prompt_slots.human = p.ATOM_PRIVATE_STRUCTURED_HUMAN

            ctx.metadata["slots_has_beijing"] = True
            ctx.metadata["slots_has_no_system_in_thinking"] = True
            ctx.metadata["slots_has_image_rendering"] = True
            next()
            return

        # tool_calling
        if decision_type == "general":
            ctx.prompt_slots.system += self._ATOM_GENERAL_TOOL_CALLING_SYSTEM_CORE
            ctx.prompt_slots.human = p.ATOM_GENERAL_TOOL_CALLING_HUMAN
        elif decision_type == "private":
            ctx.prompt_slots.system += p.ATOM_PRIVATE_QA_SYSTEM_CORE + p.ATOM_PRIVATE_NOTES
            ctx.prompt_slots.human = p.ATOM_PRIVATE_TOOL_CALLING_HUMAN
            ctx.metadata["slots_has_beijing"] = True
            ctx.metadata["slots_has_no_system_in_thinking"] = True
            ctx.metadata["slots_has_image_rendering"] = True
        else:  # clarifying
            ctx.prompt_slots.system += (
                p.ATOM_CLARIFYING_QA_SYSTEM_CORE + p.ATOM_CLARIFYING_INSTRUCTION + p.ATOM_CLARIFYING_NOTES
            )
            ctx.prompt_slots.human = p.ATOM_PRIVATE_TOOL_CALLING_HUMAN
            ctx.metadata["slots_has_beijing"] = True
            ctx.metadata["slots_has_no_system_in_thinking"] = True
            ctx.metadata["slots_has_image_rendering"] = True

        next()


class HistorySystemPromptMiddleware:
    """将历史 system 提示词注入到模板 system 槽位末尾。"""

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        if ctx.metadata.get("slots_has_history_system_prompt"):
            next()
            return

        p = _get_prompt_atoms()
        ctx.prompt_slots.system += p.ATOM_HISTORY_SYSTEM_PROMPT_TEMPLATE
        ctx.metadata["slots_has_history_system_prompt"] = True
        next()


class BeijingTimeMiddleware:
    """Append Beijing time atom to system prompt when needed."""

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        mode: PromptMode = ctx.metadata.get("prompt_mode", "tool_calling")
        if mode == "tool_calling" and not ctx.metadata.get("slots_has_beijing"):
            p = _get_prompt_atoms()
            ctx.prompt_slots.system += "\n\n" + p.ATOM_BEIJING_NOW
            ctx.metadata["slots_has_beijing"] = True

        next()


class NoSystemInThinkingMiddleware:
    """Append no-system-in-thinking atom to system prompt when needed."""

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        mode: PromptMode = ctx.metadata.get("prompt_mode", "tool_calling")
        if mode == "tool_calling" and not ctx.metadata.get("slots_has_no_system_in_thinking"):
            p = _get_prompt_atoms()
            ctx.prompt_slots.system += "\n\n" + p.ATOM_NO_SYSTEM_IN_THINKING
            ctx.metadata["slots_has_no_system_in_thinking"] = True

        next()


class ImageRenderingMiddleware:
    """Append image rendering atom to system prompt when needed."""

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        mode: PromptMode = ctx.metadata.get("prompt_mode", "tool_calling")
        if mode == "tool_calling" and not ctx.metadata.get("slots_has_image_rendering"):
            p = _get_prompt_atoms()
            ctx.prompt_slots.system += "\n\n" + p.ATOM_IMAGE_RENDERING
            ctx.metadata["slots_has_image_rendering"] = True

        next()
