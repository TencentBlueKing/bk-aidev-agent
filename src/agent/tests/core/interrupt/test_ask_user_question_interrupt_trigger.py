# -*- coding: utf-8 -*-
"""验证 ask_user_question 工具的 interrupt() 是否在 ReAct 图中正常暂停。

构造 ReActAgentBuilder + mock LLM（返回 ask_user_question tool_call），
验证：
1. 首次调用 graph.ainvoke 后，图在 approval_check 节点暂停（state.next 含 "approval_check"）
2. state.tasks[0].interrupts 非空，且 interrupt.value 含 reason="aidev:user_question"
3. 续流（Command(resume=...)）后图恢复，interrupt() 返回值成为 ToolMessage 内容
"""

from typing import Any, List, Optional, Sequence

import pytest
from aidev_agent.core.ag_ui.ask_user_question import ASK_USER_QUESTION_REASON
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command


class _FakeToolCallingLLM(BaseChatModel):
    """按预设序列返回 AIMessage 的 mock LLM，支持 bind_tools。

    第一次调用返回 ask_user_question tool_call（触发 interrupt），
    第二次调用返回纯文本（续流后 ReAct 循环结束）。
    """

    model_name: str = "fake-tool-llm"
    _responses: list = []
    _call_index: int = 0

    def __init__(self, responses: list[AIMessage] | None = None, **kwargs):
        super().__init__(**kwargs)
        # 用 object.__setattr__ 绕过 pydantic 的私有属性限制
        object.__setattr__(self, "_responses", responses or [])
        object.__setattr__(self, "_call_index", 0)

    def bind_tools(self, tools: Sequence[BaseTool], **kwargs: Any) -> "_FakeToolCallingLLM":
        """bind_tools 返回自身（mock LLM 不真正依赖 tools schema）。"""
        return self

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs: Any):
        # BaseChatModel 兼容路径
        idx = object.__getattribute__(self, "_call_index")
        responses = object.__getattribute__(self, "_responses")
        if idx >= len(responses):
            # 兜底：返回纯文本结束
            msg = AIMessage(content="完成")
        else:
            msg = responses[idx]
        object.__setattr__(self, "_call_index", idx + 1)
        from langchain_core.outputs import ChatGeneration, ChatResult
        return ChatResult(generations=[ChatGeneration(message=msg)])

    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs: Any):
        return self._generate(messages, stop=stop, **kwargs)

    @property
    def _llm_type(self) -> str:
        return "fake-tool-llm"


def _build_ask_user_question_graph(responses: list[AIMessage]):
    """构造启用了 ask_user_question 工具的 ReAct 图。"""
    llm = _FakeToolCallingLLM(responses=responses)
    builder = (
        ReActAgentBuilder()
        .set_llm(llm)
        .set_enable_ask_user_question_tool(True)
        .enable_security_runtime(False)
        .set_debug(False)
    )
    checkpointer = MemorySaver()
    builder.set_checkpointer(checkpointer)
    graph, cfg = builder.build()
    return graph, cfg, checkpointer


def _config_with_thread(cfg: dict, thread_id: str) -> dict:
    """合并 builder cfg 与 thread_id（避免 configurable 互相覆盖）。"""
    merged_configurable = {**(cfg.get("configurable") or {}), "thread_id": thread_id}
    return {**cfg, "configurable": merged_configurable}


def _ask_user_question_tool_call() -> AIMessage:
    """LLM 返回的 ask_user_question tool_call 消息。"""
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "ask_user_question",
                "args": {
                    "questions": [
                        {
                            "header": "部署确认",
                            "multiSelect": False,
                            "question": "请选择部署环境",
                            "options": [
                                {"label": "测试环境", "description": "test"},
                                {"label": "生产环境", "description": "prod"},
                            ],
                        }
                    ]
                },
                "id": "call_auq_001",
                "type": "tool_call",
            }
        ],
    )


@pytest.mark.asyncio
async def test_ask_user_question_triggers_interrupt():
    """首次 ainvoke 后图应在 tools 节点暂停，interrupt 携带 aidev:user_question reason。"""
    graph, cfg, _ = _build_ask_user_question_graph([_ask_user_question_tool_call()])
    config = _config_with_thread(cfg, "test-auq-interrupt-1")

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content="请帮我部署，但先问我要哪个环境")]},
        config,
    )

    state = await graph.aget_state(config)
    # 图应暂停在 approval_check 节点（next 含 "approval_check" 或处于 interrupt 态）
    assert state.next, f"图未暂停，state.next 为空: {state.next}"
    assert "approval_check" in state.next, f"图未在 approval_check 节点暂停，next={state.next}"

    # 提取 interrupts
    tasks = state.tasks or []
    interrupts = []
    for task in tasks:
        for intr in (task.interrupts or []):
            interrupts.append(intr)
    assert interrupts, "state.tasks 中无 interrupt 记录，interrupt() 未触发"

    # 验证 interrupt payload 的 reason
    first_intr = interrupts[0]
    value = first_intr.value
    if isinstance(value, str):
        import json
        value = json.loads(value)
    assert isinstance(value, dict), f"interrupt.value 非 dict: {type(value)}"
    assert value.get("reason") == ASK_USER_QUESTION_REASON, (
        f"interrupt reason 应为 {ASK_USER_QUESTION_REASON}，实际: {value.get('reason')}"
    )
    assert "questions" in value.get("metadata", {}), "interrupt metadata 缺少 questions 数组"


@pytest.mark.asyncio
async def test_ask_user_question_resume_returns_answer():
    """续流后 interrupt() 返回 resume 值，图恢复并结束 ReAct 循环。"""
    graph, cfg, _ = _build_ask_user_question_graph(
        [_ask_user_question_tool_call(), AIMessage(content="已收到你的选择，开始部署到生产环境")]
    )
    config = _config_with_thread(cfg, "test-auq-resume-1")

    # 第一次调用 — 触发 interrupt
    await graph.ainvoke(
        {"messages": [HumanMessage(content="请帮我部署，但先问我要哪个环境")]},
        config,
    )
    state = await graph.aget_state(config)
    assert state.next, "首次调用后图应暂停"

    # 续流 — 提交用户回答
    resume_value = {
        "answers": [
            {
                "question": "请选择部署环境",
                "answer": [{"label": "生产环境", "description": "prod"}],
            }
        ]
    }
    result = await graph.ainvoke(Command(resume=resume_value), config)

    # 续流后图应结束
    state2 = await graph.aget_state(config)
    assert not state2.next, f"续流后图应已结束，但 next={state2.next}"

    # 验证 ToolMessage 内容为 resume 值（interrupt 返回值成为 ToolMessage）
    messages = state2.values.get("messages", [])
    tool_msgs = [m for m in messages if m.type == "tool"]
    assert tool_msgs, "续流后应产生 ToolMessage"
    # interrupt() 返回值为 resume_value，应作为 ToolMessage content
    last_tool_msg = tool_msgs[-1]
    assert "answers" in last_tool_msg.content or "生产环境" in str(last_tool_msg.content), (
        f"ToolMessage content 未包含 resume 值: {last_tool_msg.content}"
    )


@pytest.mark.asyncio
async def test_ask_user_question_interrupt_payload_structure():
    """验证 interrupt payload 完整结构（reason + metadata.questions + expiresAt）。"""
    graph, cfg, _ = _build_ask_user_question_graph([_ask_user_question_tool_call()])
    config = _config_with_thread(cfg, "test-auq-payload-1")

    await graph.ainvoke(
        {"messages": [HumanMessage(content="问我要哪个环境")]},
        config,
    )

    state = await graph.aget_state(config)
    tasks = state.tasks or []
    interrupts = []
    for task in tasks:
        for intr in (task.interrupts or []):
            interrupts.append(intr)
    assert interrupts, "无 interrupt 记录"

    value = interrupts[0].value
    if isinstance(value, str):
        import json
        value = json.loads(value)

    assert value["reason"] == ASK_USER_QUESTION_REASON
    # toolCallId 来自 ToolRuntime，测试环境中可能为空字符串
    assert "toolCallId" in value, "payload 缺少 toolCallId 字段"
    assert "expiresAt" in value, "payload 缺少顶层 expiresAt 字段"
    metadata = value["metadata"]
    assert metadata["type"] == "ask_user_question"
    assert metadata["status"] == "pending"
    questions = metadata["questions"]
    assert len(questions) == 1
    assert questions[0]["question"] == "请选择部署环境"
    assert questions[0]["multiSelect"] is False
    assert len(questions[0]["options"]) == 2
