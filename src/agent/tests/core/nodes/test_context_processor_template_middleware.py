# -*- coding: utf-8 -*-
"""测试 ContextAssembly 模板拼装管道（PromptSlots + 原子中间件）。"""

from aidev_agent.core.graphs.react import prompts as react_prompts
from aidev_agent.core.nodes.model.context_assembly import ContextAssembly
from aidev_agent.core.nodes.model.prompt_middleware import (
    BeijingTimeMiddleware,
    DecisionSystemMiddleware,
    NoSystemInThinkingMiddleware,
    RoleDefinitionMiddleware,
    StructuredChatFormatMiddleware,
)
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.enums import Decision
from langchain_core.prompts import ChatPromptTemplate


# NOTE: production code does not need pre-built default templates.
# These templates are kept in tests as stable reference values.
def _build_system_prompt_tool_calling(*, decision_type: str) -> str:
    if decision_type == "general":
        return react_prompts.ATOM_GENERAL_TOOL_CALLING_SYSTEM

    if decision_type == "private":
        return (
            react_prompts.ATOM_ROLE_DEFINITION
            + react_prompts.ATOM_PRIVATE_QA_SYSTEM_CORE
            + react_prompts.ATOM_PRIVATE_NOTES
        )

    if decision_type == "clarifying":
        return (
            react_prompts.ATOM_ROLE_DEFINITION
            + react_prompts.ATOM_CLARIFYING_QA_SYSTEM_CORE
            + react_prompts.ATOM_CLARIFYING_INSTRUCTION
            + react_prompts.ATOM_CLARIFYING_NOTES
        )

    raise ValueError(f"Unknown decision_type: {decision_type}")


def _build_human_prompt_tool_calling(*, decision_type: str) -> str:
    if decision_type == "general":
        return react_prompts.ATOM_GENERAL_TOOL_CALLING_HUMAN

    if decision_type in {"private", "clarifying"}:
        return react_prompts.ATOM_PRIVATE_TOOL_CALLING_HUMAN

    raise ValueError(f"Unknown decision_type: {decision_type}")


def _build_chat_prompt_template(*, mode: str, decision_type: str) -> ChatPromptTemplate:
    if mode == "tool_calling":
        return ChatPromptTemplate.from_messages(
            [
                ("system", _build_system_prompt_tool_calling(decision_type=decision_type)),
                ("placeholder", "{chat_history}"),
                ("human", _build_human_prompt_tool_calling(decision_type=decision_type)),
                ("placeholder", "{agent_scratchpad}"),
            ],
            template_format="jinja2",
        )

    if mode == "structured_chat":
        # NOTE: structured_chat: system instructions are embedded in a human message.
        if decision_type == "general":
            system = react_prompts.ATOM_GENERAL_STRUCTURED_SYSTEM
            human = react_prompts.ATOM_GENERAL_STRUCTURED_HUMAN
        else:
            system = react_prompts.ATOM_PRIVATE_STRUCTURED_SYSTEM
            human = react_prompts.ATOM_PRIVATE_STRUCTURED_HUMAN

        return ChatPromptTemplate.from_messages(
            [
                ("human", system),
                ("placeholder", "{chat_history}"),
                ("human", human),
            ],
            template_format="jinja2",
        )

    raise ValueError(f"Unsupported mode: {mode}")


DEFAULT_QA_PROMPT_TEMPLATES = {
    "general_qa_prompt_tool_calling": _build_chat_prompt_template(mode="tool_calling", decision_type="general"),
    "private_qa_prompt_tool_calling": _build_chat_prompt_template(mode="tool_calling", decision_type="private"),
    "clarifying_qa_prompt_tool_calling": _build_chat_prompt_template(mode="tool_calling", decision_type="clarifying"),
    "general_qa_prompt_structured_chat": _build_chat_prompt_template(mode="structured_chat", decision_type="general"),
    "private_qa_prompt_structured_chat": _build_chat_prompt_template(mode="structured_chat", decision_type="private"),
    # NOTE: structured_chat: clarifying uses the same template as private.
    "clarifying_qa_prompt_structured_chat": _build_chat_prompt_template(
        mode="structured_chat", decision_type="clarifying"
    ),
}


def _render_prompt_contents(prompt, variables: dict) -> list[str]:
    """Render a ChatPromptTemplate and return message contents."""

    value = prompt.invoke(variables, config={})
    return [m.content for m in value.to_messages()]


def _build_context_assembly(
    *, use_structured_response: bool, enable_query_clarification: bool = True
) -> ContextAssembly:
    ca = ContextAssembly()
    ca.add_middleware(
        "template",
        StructuredChatFormatMiddleware(use_structured_response=use_structured_response),
    )
    ca.add_middleware("template", RoleDefinitionMiddleware())
    ca.add_middleware(
        "template",
        DecisionSystemMiddleware(enable_query_clarification=enable_query_clarification),
    )
    ca.add_middleware("template", BeijingTimeMiddleware())
    ca.add_middleware("template", NoSystemInThinkingMiddleware())
    return ca


class TestTemplatePipeline:
    def test_unknown_decision_structured_chat_falls_back_to_general_prompt(self):
        ca = _build_context_assembly(use_structured_response=True)

        ctx = ProcessorContext(state={"decision": "UNKNOWN"}, config={}, store=None)
        tpl = ca.get_chat_prompt_template(ctx)

        variables = {
            "query": "hi",
            "role_prompt": "",
            "rejection_response": "no",
            "beijing_now": "2026-01-01",
            "use_general_knowledge_on_miss": True,
            "enable_parallel_tool_calls": True,
            "tool_names": "t1,t2",
            "tools": "t1: ...",
            "chat_history": [],
            "agent_scratchpad": "",
            "context_type": "private",
            "context": "ctx",
            "qa_context": "qa",
        }

        default = DEFAULT_QA_PROMPT_TEMPLATES["general_qa_prompt_structured_chat"]
        assert _render_prompt_contents(tpl, variables) == _render_prompt_contents(default, variables)

    def test_decision_general_qa_structured_chat_matches_default(self):
        ca = _build_context_assembly(use_structured_response=True)

        ctx = ProcessorContext(state={"decision": Decision.GENERAL_QA}, config={}, store=None)
        tpl = ca.get_chat_prompt_template(ctx)

        variables = {
            "query": "hi",
            "role_prompt": "",
            "rejection_response": "no",
            "beijing_now": "2026-01-01",
            "use_general_knowledge_on_miss": True,
            "enable_parallel_tool_calls": True,
            "tool_names": "t1,t2",
            "tools": "t1: ...",
            "chat_history": [],
            "agent_scratchpad": "",
            "context_type": "private",
            "context": "ctx",
            "qa_context": "qa",
        }

        default = DEFAULT_QA_PROMPT_TEMPLATES["general_qa_prompt_structured_chat"]
        assert _render_prompt_contents(tpl, variables) == _render_prompt_contents(default, variables)

    def test_decision_query_clarification_can_fallback_to_private(self):
        ca = _build_context_assembly(use_structured_response=False, enable_query_clarification=False)

        ctx = ProcessorContext(state={"decision": Decision.QUERY_CLARIFICATION}, config={}, store=None)
        tpl = ca.get_chat_prompt_template(ctx)

        variables = {
            "query": "hi",
            "role_prompt": "",
            "rejection_response": "no",
            "beijing_now": "2026-01-01",
            "use_general_knowledge_on_miss": False,
            "chat_history": [],
            "agent_scratchpad": [],
            "context_type": "private",
            "context": "kctx",
            "qa_context": "qactx",
        }

        default = DEFAULT_QA_PROMPT_TEMPLATES["private_qa_prompt_tool_calling"]
        assert _render_prompt_contents(tpl, variables) == _render_prompt_contents(default, variables)

    def test_append_prepend_system_prompt_helpers(self):
        ca = _build_context_assembly(use_structured_response=False)
        ca.prepend_system_prompt("PREFIX\n")
        ca.append_system_prompt("\nSUFFIX")

        ctx = ProcessorContext(state={"decision": Decision.GENERAL_QA}, config={}, store=None)
        tpl = ca.get_chat_prompt_template(ctx)

        variables = {
            "query": "hi",
            "role_prompt": "",
            "rejection_response": "no",
            "beijing_now": "2026-01-01",
            "use_general_knowledge_on_miss": False,
            "chat_history": [],
            "agent_scratchpad": [],
            "context_type": "",
            "context": "",
            "qa_context": "",
        }
        rendered_system = _render_prompt_contents(tpl, variables)[0]
        assert rendered_system.startswith("PREFIX\n")
        assert rendered_system.endswith("\nSUFFIX")


class TestPromptAtomization:
    def test_default_templates_map_contains_expected_keys(self):
        for key in [
            "general_qa_prompt_tool_calling",
            "general_qa_prompt_structured_chat",
            "private_qa_prompt_tool_calling",
            "private_qa_prompt_structured_chat",
            "clarifying_qa_prompt_tool_calling",
            "clarifying_qa_prompt_structured_chat",
        ]:
            assert key in DEFAULT_QA_PROMPT_TEMPLATES

    def test_private_tool_calling_context_type_branches(self):
        base_vars = {
            "query": "hi",
            "role_prompt": "",
            "rejection_response": "no",
            "beijing_now": "2026-01-01",
            "use_general_knowledge_on_miss": False,
            "chat_history": [],
            "agent_scratchpad": [],
            "context": "kctx",
            "qa_context": "qactx",
        }

        prompt = DEFAULT_QA_PROMPT_TEMPLATES["private_qa_prompt_tool_calling"]

        # private
        private_out = "\n".join(_render_prompt_contents(prompt, {**base_vars, "context_type": "private"}))
        assert "来自私域知识库" in private_out

        # qa_response
        qa_out = "\n".join(_render_prompt_contents(prompt, {**base_vars, "context_type": "qa_response"}))
        assert "历史问答记录" in qa_out

        # both
        both_out = "\n".join(_render_prompt_contents(prompt, {**base_vars, "context_type": "both"}))
        assert "知识库" in both_out and "历史问答" in both_out

    def test_clarifying_tool_calling_includes_rewrite_instruction(self):
        variables = {
            "query": "hi",
            "role_prompt": "",
            "rejection_response": "no",
            "beijing_now": "2026-01-01",
            "use_general_knowledge_on_miss": False,
            "chat_history": [],
            "agent_scratchpad": [],
            "context_type": "private",
            "context": "kctx",
            "qa_context": "qactx",
        }
        prompt = DEFAULT_QA_PROMPT_TEMPLATES["clarifying_qa_prompt_tool_calling"]
        rendered = "\n".join(_render_prompt_contents(prompt, variables))
        assert "抱歉，您是不是想问" in rendered
