# -*- coding: utf-8 -*-
"""模拟前端续流 API 请求，追踪完整事件流和 DB 更新。

前端续流请求格式：
{
  "session_code": "...",
  "execute_kwargs": {
    "stream": true,
    "persist_input": false,
    "resume": {
      "interruptId": "int-question-...",
      "status": "resolved",
      "payload": {"answers": [...]}
    }
  }
}

本测试模拟：
1. 首次请求 → 触发 ask_user_question 中断
2. 前端续流（用前端传的 resume 单 dict 格式）
3. 观察续流后 DB interrupt 记录是否被更新为 resolved
"""

import json

import pytest
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.ask_user_question import ASK_USER_QUESTION_REASON
from aidev_agent.core.ag_ui.types import AgentInput
from aidev_agent.core.ag_ui.utils import get_schema_keys
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.enums import PromptRole
from aidev_agent.services.agent.chat import ChatAgentBuilder, ChatPrompt
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver
from tests.core.ag_ui._prepare_stream_helper import prepare_stream_data_for_agent


class _FakeToolCallingLLM(BaseChatModel):
    model_name: str = "fake-tool-llm"

    def __init__(self, responses, **kw):
        super().__init__(**kw)
        object.__setattr__(self, "_responses", responses)
        object.__setattr__(self, "_call_index", 0)

    def bind_tools(self, tools, **kw):
        return self

    def _generate(self, messages, stop=None, **kw):
        idx = object.__getattribute__(self, "_call_index")
        resp = object.__getattribute__(self, "_responses")
        msg = resp[idx] if idx < len(resp) else AIMessage(content="完成")
        object.__setattr__(self, "_call_index", idx + 1)
        return ChatResult(generations=[ChatGeneration(message=msg)])

    async def _agenerate(self, messages, stop=None, **kw):
        return self._generate(messages, stop=stop, **kw)

    @property
    def _llm_type(self):
        return "fake"


class _MockBKAidevClient:
    """模拟 BKAidev API client，追踪 DB 读写。"""

    def __init__(self):
        self.api = _MockApi(self)


class _MockApi:
    def __init__(self, client):
        self.client = client
        self._contents: list[dict] = []
        self._next_id = 1

    def create_chat_session_content(self, json, headers):
        content_id = self._next_id
        self._next_id += 1
        record = {
            "id": content_id,
            "role": json.get("role"),
            "content": json.get("content"),
            "status": json.get("status"),
            "property": json.get("property", {}),
        }
        self._contents.append(record)
        return {"data": {"id": content_id}}

    def update_chat_session_content(self, path_params, json, headers):
        content_id = path_params["id"]
        for rec in self._contents:
            if rec["id"] == content_id:
                if "content" in json:
                    rec["content"] = json["content"]
                if "status" in json:
                    rec["status"] = json["status"]
                if "property" in json:
                    rec["property"] = json["property"]
                break
        return {"data": {"id": content_id}}

    def get_chat_session_contents(self, params, headers):
        # 模拟生产环境：API 返回的 property 不含 builtin_property
        # （生产环境 get_chat_session_contents 序列化时过滤了 builtin_property）
        stripped = []
        for rec in self._contents:
            rec_copy = dict(rec)
            prop = rec_copy.get("property") or {}
            if isinstance(prop, dict):
                # 只保留非 builtin_property 的字段（模拟生产环境行为）
                stripped_prop = {k: v for k, v in prop.items() if k != "builtin_property"}
                rec_copy["property"] = stripped_prop
            stripped.append(rec_copy)
        return {"data": stripped}

    def update_chat_session(self, path_params, json, headers):
        return {"data": {}}

    def retrieve_chat_session(self, path_params, headers):
        return {"data": {"session_property": {}}}


def _ask_user_question_tool_call() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "ask_user_question",
                "args": {
                    "questions": [
                        {
                            "header": "运动偏好",
                            "multiSelect": False,
                            "question": "您平时最喜欢做什么类型的运动？",
                            "options": [
                                {"label": "瑜伽", "description": "身心平衡的瑜伽练习"},
                                {"label": "跑步", "description": "有氧运动"},
                            ],
                        }
                    ]
                },
                "id": "chatcmpl-tool-test001",
                "type": "tool_call",
            }
        ],
    )


def _build_graph(responses):
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
    return graph, cfg


def _config_with_thread(cfg, thread_id):
    merged = {**(cfg.get("configurable") or {}), "thread_id": thread_id}
    return {**cfg, "configurable": merged}


def _extract_ask_user_question_interrupts(graph, config) -> list[dict]:
    """从 graph state 提取 ask_user_question interrupts（复刻 chat.py._query_ask_user_question_interrupts）。

    续流时 graph checkpoint 保留了中断记录，测试需像生产一样提取并传给 AidevAGUIAgent，
    使 _build_resume_ask_user_question_finished_event 能触发 ACTIVITY_SNAPSHOT 事件，
    经 _dispatch_event 派发给 writer 的 handle_activity_snapshot。
    """
    try:
        agent_state = graph.get_state(config)
        tasks = agent_state.tasks if agent_state.tasks else []
        interrupts: list[dict] = []
        for task in tasks:
            for intr in task.interrupts or []:
                value = intr.value
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except Exception:
                        continue
                if isinstance(value, dict) and value.get("reason") == ASK_USER_QUESTION_REASON:
                    interrupts.append(value)
        return interrupts
    except Exception:
        return []


@pytest.mark.asyncio
async def test_resume_with_frontend_dict_format_updates_interrupt():
    """模拟前端续流（resume 为单 dict 格式），验证 DB interrupt 记录更新为 resolved。

    前端传的 resume 格式：
    {"interruptId": "...", "status": "resolved", "payload": {"answers": [...]}}
    """
    responses = [
        _ask_user_question_tool_call(),
        AIMessage(content="感谢您的回答！您喜欢瑜伽。"),
    ]
    graph, cfg = _build_graph(responses)
    config = _config_with_thread(cfg, "test-frontend-resume-1")

    # 用真实的 AGUISessionWriter + mock client
    mock_client = _MockBKAidevClient()
    writer1 = AGUISessionWriter(
        session_code="test-frontend-resume-1",
        client=mock_client,
        username="test",
        tools=[],
    )

    # 第一次请求 — 触发中断
    agent_input1 = AgentInput(
        thread_id="test-frontend-resume-1",
        run_id="run-1",
        state={},
        messages=[{"role": "user", "content": "问我喜欢什么运动", "id": "user-msg-1"}],
    )

    # Phase 11.8: 预处理前移（消除 model_copy + 消除 agui_entry 依赖）
    agent_state1 = await graph.aget_state(config)
    schema_keys1 = get_schema_keys(graph, config, ["messages", "tools", "copilotkit"])
    preprocessed1 = prepare_stream_data_for_agent(
        graph,
        config,
        state=agent_input1.state or {},
        forwarded_props=agent_input1.forwarded_props or {},
        thread_id=agent_input1.thread_id,
        messages=agent_input1.messages,
        agent_state=agent_state1,
        schema_keys=schema_keys1,
    )
    body1 = {
        "thread_id": agent_input1.thread_id,
        "run_id": agent_input1.run_id,
        "state": preprocessed1["state"],
        "messages": agent_input1.messages,
        "stream_input": preprocessed1["stream_input"],  # 11.9: stream_input 通过 input 传递
    }
    if agent_input1.forwarded_props:
        body1["forwarded_props"] = agent_input1.forwarded_props
    agent_input1 = AgentInput(**body1)
    fork1 = preprocessed1["fork"]
    if fork1:
        merged_cfg1 = {
            **config,
            "configurable": {
                **config.get("configurable", {}),
                **fork1.get("configurable", {}),
            },
        }
    else:
        merged_cfg1 = config
    agui1 = AidevAGUIAgent(
        name="test-agent",
        graph=graph,
        event_handler=writer1,
        config=merged_cfg1,
        tools={},
    )
    chunks1 = [chunk async for chunk in agui1.run(agent_input1)]  # noqa: F841

    # 检查 DB 中 interrupt 记录
    db_after_interrupt = list(mock_client.api._contents)
    print(f"\n=== After interrupt — DB records: {len(db_after_interrupt)} ===")
    for rec in db_after_interrupt:
        print(f"  id={rec['id']}, role={rec['role']}, status={rec['status']}")

    interrupt_recs = [r for r in db_after_interrupt if r["role"] == PromptRole.INTERRUPT.value]
    assert interrupt_recs, "首次中断后 DB 应有 interrupt 记录"
    interrupt_id = interrupt_recs[0]["id"]  # noqa: F841
    assert interrupt_recs[0]["status"] == "pending", f"interrupt 应为 pending，实际: {interrupt_recs[0]['status']}"

    # 第二次请求 — 前端续流（新 writer 实例，模拟新 API 请求）
    writer2 = AGUISessionWriter(
        session_code="test-frontend-resume-1",
        client=mock_client,  # 复用同一 client（同 DB）
        username="test",
        tools=[],
    )

    # 前端传的 resume 是单 dict 格式
    frontend_resume = {
        "interruptId": interrupt_recs[0]["property"]["builtin_property"]["interrupt_id"],
        "status": "resolved",
        "payload": {
            "answers": [
                {
                    "question": "您平时最喜欢做什么类型的运动？",
                    "answer": [{"label": "瑜伽", "description": "身心平衡的瑜伽练习"}],
                }
            ]
        },
    }

    agent_input2 = AgentInput(
        thread_id="test-frontend-resume-1",
        run_id="run-2",
        state={},
        messages=[],
        forwarded_props={"command": {"resume": frontend_resume}},
    )
    agent_state2 = await graph.aget_state(config)
    schema_keys2 = get_schema_keys(graph, config, ["messages", "tools", "copilotkit"])
    preprocessed2 = prepare_stream_data_for_agent(
        graph,
        config,
        state=agent_input2.state or {},
        forwarded_props=agent_input2.forwarded_props or {},
        thread_id=agent_input2.thread_id,
        messages=agent_input2.messages,
        agent_state=agent_state2,
        schema_keys=schema_keys2,
    )
    body2 = {
        "thread_id": agent_input2.thread_id,
        "run_id": agent_input2.run_id,
        "state": preprocessed2["state"],
        "messages": agent_input2.messages,
        "stream_input": preprocessed2["stream_input"],  # 11.9: stream_input 通过 input 传递
    }
    if agent_input2.forwarded_props:
        body2["forwarded_props"] = agent_input2.forwarded_props
    agent_input2 = AgentInput(**body2)
    fork2 = preprocessed2["fork"]
    if fork2:
        merged_cfg2 = {
            **config,
            "configurable": {
                **config.get("configurable", {}),
                **fork2.get("configurable", {}),
            },
        }
    else:
        merged_cfg2 = config
    agui2 = AidevAGUIAgent(
        name="test-agent",
        graph=graph,
        event_handler=writer2,
        config=merged_cfg2,
        tools={},
        # 与 chat.py 主流程对称：从 graph state 查 ask_user_question interrupts，
        # 使 _build_resume_ask_user_question_finished_event 能触发 ACTIVITY_SNAPSHOT 事件，
        # 经 _dispatch_event 派发给 writer 的 handle_activity_snapshot
        ask_user_question_interrupts=_extract_ask_user_question_interrupts(graph, config),
    )
    chunks2 = [chunk async for chunk in agui2.run(agent_input2)]  # noqa: F841

    # 检查 DB 中 interrupt 记录是否被更新
    db_after_resume = list(mock_client.api._contents)
    print(f"\n=== After resume — DB records: {len(db_after_resume)} ===")
    for rec in db_after_resume:
        status = rec["status"]
        content_preview = str(rec.get("content", ""))[:80]
        print(f"  id={rec['id']}, role={rec['role']}, status={status}, content={content_preview}")

    # 关键断言：interrupt 记录应被更新为 resolved/complete
    interrupt_after = [r for r in db_after_resume if r["role"] == PromptRole.INTERRUPT.value]
    assert interrupt_after, "续流后 interrupt 记录应仍存在"
    print("\n=== Interrupt record after resume ===")
    print(f"  status: {interrupt_after[0]['status']}")
    content = interrupt_after[0]["content"]
    if isinstance(content, dict):
        print(f"  outcome.type: {content.get('outcome', {}).get('type')}")
    elif isinstance(content, str):
        print(f"  content (str): {content[:100]}")

    assert interrupt_after[0]["status"] != "pending", (
        f"interrupt 记录仍为 pending（未更新为 resolved），status={interrupt_after[0]['status']}"
    )


def test_filter_unmatched_tool_calls_preserves_ask_user_question():
    """_filter_unmatched_tool_calls 应保留 ask_user_question 的 tool_call（有对应 interrupt 记录）。

    ask_user_question 中断时 AI 有 tool_call 但无 tool 结果（interrupt 中断），
    如果 _filter_unmatched_tool_calls 过滤掉这条 assistant 消息，续流时
    MESSAGES_SNAPSHOT 会丢失 AI(AskUser) 部分。
    """
    builder = ChatAgentBuilder.__new__(ChatAgentBuilder)
    # 构造 chat_history：user -> assistant(tool_call=ask_user_question) -> interrupt
    chat_history = [
        ChatPrompt(role="user", content="问我问题"),
        ChatPrompt(
            role="assistant",
            content="",
            id="ai-1",
            builtin_property={
                "tool_calls": [
                    {
                        "id": "call_auq_001",
                        "type": "function",
                        "function": {
                            "name": "ask_user_question",
                            "arguments": '{"questions": [...]}',
                        },
                    }
                ]
            },
        ),
        ChatPrompt(
            role="interrupt",
            content={"outcome": {"type": "interrupt", "interrupts": []}},
            builtin_property={"tool_call_id": "call_auq_001"},
        ),
    ]

    result = builder._filter_unmatched_tool_calls(chat_history)

    # assistant 消息应被保留（有对应 interrupt 记录）
    assistant_msgs = [p for p in result if p.role == "assistant"]
    assert len(assistant_msgs) == 1, f"ask_user_question 的 assistant 消息应被保留，实际: {len(assistant_msgs)} 条"
    # tool_call 应保留（在 builtin_property.tool_calls 中）
    tool_calls = assistant_msgs[0].builtin_property.get("tool_calls", [])
    assert len(tool_calls) == 1, f"tool_call 应保留，实际: {len(tool_calls)} 条"
    assert tool_calls[0]["id"] == "call_auq_001"
