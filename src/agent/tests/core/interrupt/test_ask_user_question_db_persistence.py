# -*- coding: utf-8 -*-
"""验证 ask_user_question 中断时消息序列是否正确入库。

正确序列应为：HumanMessage -> AIMessage(tool_call) -> InterruptRecord -> (续流后) AIMessage(回复)
如果中间的 AIMessage(tool_call) 或 InterruptRecord 缺失，前端显示会丢失中间部分。
"""

import json

import pytest
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import (
    AgentInput,
)
from aidev_agent.core.ag_ui.utils import get_schema_keys
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.enums import PromptRole
from aidev_agent.packages.interrupt_manager import ASK_USER_QUESTION_REASON
from aidev_agent.packages.interrupt_manager.ask_user_question import (
    AskUserQuestionHandler,
    AskUserQuestionOutcomeBuilder,
)
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from aidev_agent.services.event_handlers.base import BaseSessionWriter
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


class _RecordingSessionWriter(BaseSessionWriter):
    """记录所有 create/update 调用的 mock writer。"""

    def __init__(self, tools=None):
        super().__init__(session_code="test", username="test", tools=tools, turn_id="t1")
        self.created: list[dict] = []
        self.updated: list[dict] = []
        self._next_id = 1
        self.streaming_finished_count = 0
        # 模拟 DB 中存储的记录（content_id -> {role, status, content, builtin_property}）
        self._db_records: dict[int, dict] = {}

    def _do_create_content(self, payload, headers):
        self.created.append({"payload": payload})
        content_id = self._next_id
        self._next_id += 1
        # 模拟 DB 存储
        self._db_records[content_id] = {
            "role": payload.get("role"),
            "status": payload.get("status"),
            "content": payload.get("content"),
            "property": payload.get("property", {}),
        }
        return content_id

    def _do_update_content(self, content_id, payload, headers):
        self.updated.append({"content_id": content_id, "payload": payload})
        # 模拟 DB 更新
        if content_id in self._db_records:
            rec = self._db_records[content_id]
            if "content" in payload:
                rec["content"] = payload["content"]
            if "status" in payload:
                rec["status"] = payload["status"]
            if "property" in payload:
                rec["property"] = payload["property"]

    def set_streaming_started(self):
        pass

    def set_streaming_finished(self):
        self.streaming_finished_count += 1


def _noop_dispatch(result: dict) -> None:
    """no-op dispatch：本测试驱动 AidevAGUIAgent.run() 只走 dispatch 路径，不经 chat.py
    装配层派发 skip/answer 事件，故注入空实现（D-16 bound method）。"""


def _simulate_ask_user_answer_persisted(writer, answers):
    """模拟 chat.py resolve_resumes 的 ask_user DB 改写：把 interrupt content 升级为 resolved。

    串行门禁（GATE-01）下 ask_user pending 走 ``query_answered_status`` 只读判已答，
    读记录 ``content.outcome.type`` / ``result.payload.answers``（DB 权威源）。测试仅
    模拟 SSE 层（不经 chat.py execute()），故只升级 content 为终态形态（供门禁判定），
    不改写记录顶层 status。
    """
    interrupt_recs = [rec for rec in writer._db_records.values() if rec.get("role") == PromptRole.INTERRUPT.value]
    assert interrupt_recs, "无 interrupt 记录可升级"
    rec = interrupt_recs[0]
    upgraded = AskUserQuestionOutcomeBuilder.upgrade_content_to_success(
        rec.get("content"), "resolved", resume_answers=answers
    )
    assert upgraded is not None, "interrupt content 升级为 resolved 失败"
    rec["content"] = upgraded
    return rec


def _extract_ask_user_question_interrupts(graph, config) -> list[dict]:
    """从 graph state 提取 ask_user_question interrupts（复刻 chat.py._query_ask_user_question_interrupts）。

    续流时 graph checkpoint 保留了中断记录，测试需像生产一样提取并传给 AidevAGUIAgent，
    否则 _build_resume_ask_user_question_finished_event 不会触发，writer 拿不到 resume_answers。
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


def _ask_user_question_tool_call() -> AIMessage:
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


def _build_graph_and_writer(responses):
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
    writer = _RecordingSessionWriter(tools=[])
    return graph, cfg, writer


def _config_with_thread(cfg, thread_id):
    merged = {**(cfg.get("configurable") or {}), "thread_id": thread_id}
    return {**cfg, "configurable": merged}


@pytest.mark.asyncio
async def test_interrupt_writes_assistant_and_interrupt_records():
    """首次中断时应写入：assistant(tool_call) + interrupt 记录。

    如果缺少其中任一条，前端显示会丢失中间部分。
    """
    graph, cfg, writer = _build_graph_and_writer([_ask_user_question_tool_call()])
    config = _config_with_thread(cfg, "test-db-write-1")

    # 用 AidevAGUIAgent 跑完整 SSE 流，让 writer 接收事件

    agent_input = AgentInput(
        thread_id="test-db-write-1",
        run_id="run-1",
        state={},
        messages=[{"role": "user", "content": "问我要哪个环境", "id": "user-msg-1"}],
    )

    # Phase 11.8: 预处理前移到 agent_input 构造之前（消除 model_copy + 消除 agui_entry 依赖）
    agent_state = await graph.aget_state(config)
    schema_keys = get_schema_keys(graph, config, ["messages", "tools", "copilotkit"])
    preprocessed = prepare_stream_data_for_agent(
        graph,
        config,
        state=agent_input.state or {},
        forwarded_props=agent_input.forwarded_props or {},
        thread_id=agent_input.thread_id,
        messages=agent_input.messages,
        agent_state=agent_state,
        schema_keys=schema_keys,
    )
    # 11.8: 合并后的 state 直接放进 body（不再 model_copy）
    body = {
        "thread_id": agent_input.thread_id,
        "run_id": agent_input.run_id,
        "state": preprocessed["state"],
        "messages": agent_input.messages,
        "stream_input": preprocessed["stream_input"],  # 11.9: stream_input 通过 input 传递
    }
    if agent_input.forwarded_props:
        body["forwarded_props"] = agent_input.forwarded_props
    agent_input = AgentInput(**body)
    # fork merge 到 config
    fork = preprocessed["fork"]
    if fork:
        merged_cfg = {
            **config,
            "configurable": {
                **config.get("configurable", {}),
                **fork.get("configurable", {}),
            },
        }
    else:
        merged_cfg = config
    agui = AidevAGUIAgent(
        name="test-agent",
        graph=graph,
        event_handler=writer,
        config=merged_cfg,
        tools={},
    )

    chunks = [chunk async for chunk in agui.run(agent_input)]  # noqa: F841

    # 分析 writer 记录的 create 调用
    roles_created = [c["payload"].get("role") for c in writer.created]
    print(f"Created roles: {roles_created}")
    for c in writer.created:
        print(f"  role={c['payload'].get('role')}, status={c['payload'].get('status')}")

    # 关键断言：应写入 assistant 和 interrupt 记录
    assert PromptRole.ASSISTANT.value in roles_created, (
        f"缺少 assistant 记录（AI 调用 AskUser 的 AIMessage 未入库），roles={roles_created}"
    )
    assert PromptRole.INTERRUPT.value in roles_created, (
        f"缺少 interrupt 记录（AskUser 中断未入库），roles={roles_created}"
    )


@pytest.mark.asyncio
async def test_resume_preserves_prior_messages_and_writes_final_reply():
    """续流后应保留首次的 assistant+interrupt 记录，并写入最终回复。

    正确序列：assistant(tool_call) + interrupt + assistant(回复)。
    如果续流后序列变成只有 assistant(回复)，说明中间记录被覆盖或丢失。
    """
    responses = [
        _ask_user_question_tool_call(),  # 首次：触发 interrupt
        AIMessage(content="已收到你的选择，开始部署到生产环境"),  # 续流：最终回复
    ]
    graph, cfg, writer = _build_graph_and_writer(responses)
    config = _config_with_thread(cfg, "test-db-write-2")

    # Phase 11.8: 预处理前移（消除 model_copy + 消除 agui_entry 依赖）
    # 第一次调用 — 触发中断
    agent_input1 = AgentInput(
        thread_id="test-db-write-2",
        run_id="run-1",
        state={},
        messages=[{"role": "user", "content": "问我要哪个环境", "id": "user-msg-1"}],
    )
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
        event_handler=writer,
        config=merged_cfg1,
        tools={},
    )
    chunks1 = [chunk async for chunk in agui1.run(agent_input1)]  # noqa: F841

    roles_after_interrupt = [c["payload"].get("role") for c in writer.created]
    print(f"After interrupt — Created roles: {roles_after_interrupt}")

    # 串行门禁（GATE-01）下 ask_user pending 走 query_answered_status 只读判已答，
    # DB 必须先含该已答记录（模拟生产 chat.py resolve_resumes 的 DB 改写前置）。
    # 测试绕过 chat.py 直调 AidevAGUIAgent.run()，故在此模拟持久化。
    _simulate_ask_user_answer_persisted(
        writer,
        [
            {
                "question": "请选择部署环境",
                "answer": [{"label": "生产环境", "description": "prod"}],
            }
        ],
    )

    # 第二次调用 — 续流（复用 writer，模拟同 session）
    agent_input2 = AgentInput(
        thread_id="test-db-write-2",
        run_id="run-2",
        state={},
        messages=[],
        forwarded_props={
            "command": {
                "resume": [
                    {
                        "interruptId": "int-question-call_auq_001-",
                        "status": "resolved",
                        "payload": {
                            "answers": [
                                {"question": "请选择部署环境", "answer": [{"label": "生产环境", "description": "prod"}]}
                            ]
                        },
                    }
                ]
            }
        },
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
        event_handler=writer,
        config=merged_cfg2,
        tools={},
        # 串行门禁（GATE-01）：ask_user pending 走 query_resume_status 只读门禁判已答。
        # D-03（48）：processor 构造参数改为 handlers dict 注入（移除 resource_manager=）。
        # 本测试驱动 AidevAGUIAgent.run() 只走 dispatch_interrupts（建单/enrich 路径，
        # 不经 chat.py get_resume_input 门禁），ask_user handler 无需 resource_manager 读 DB。
        interrupt_processor=InterruptProcessor(
            handlers={
                str(ASK_USER_QUESTION_REASON.value): AskUserQuestionHandler(
                    dispatch_skip=_noop_dispatch,
                    dispatch_answer=_noop_dispatch,
                )
            }
        ),
        # 与 chat.py 主流程对称：从 graph state 查 ask_user_question interrupts，
        # 使 _build_resume_ask_user_question_finished_event 能触发 ACTIVITY_SNAPSHOT 事件，
        # 经 _dispatch_event 派发给 writer 的 handle_activity_snapshot
        ask_user_question_interrupts=_extract_ask_user_question_interrupts(graph, config),
    )
    chunks2 = [chunk async for chunk in agui2.run(agent_input2)]  # noqa: F841

    roles_after_resume = [c["payload"].get("role") for c in writer.created]
    print(f"After resume — Created roles: {roles_after_resume}")
    for c in writer.created:
        role = c["payload"].get("role")
        status = c["payload"].get("status")
        content_preview = str(c["payload"].get("content", ""))[:80]
        print(f"  role={role}, status={status}, content={content_preview}")

    # 首次的 assistant 和 interrupt 记录应仍然存在
    assert roles_after_resume.count(PromptRole.ASSISTANT.value) >= 1, "首次的 assistant(tool_call) 记录丢失"
    assert PromptRole.INTERRUPT.value in roles_after_resume, "interrupt 记录丢失"

    # 续流后应新增最终回复的 assistant 记录
    assert roles_after_resume.count(PromptRole.ASSISTANT.value) >= 2, (
        f"续流后未写入最终回复的 assistant 记录，roles={roles_after_resume}"
    )

    # SSE 层不再 UPDATE interrupt 记录（DB 终态由入口层 chat.py:138 负责）
    interrupt_updates = [
        u
        for u in writer.updated
        if isinstance(u.get("payload", {}).get("content"), dict)
        and u["payload"]["content"].get("outcome", {}).get("type") == "success"
    ]
    assert not interrupt_updates, f" 后 SSE 层不应再 UPDATE interrupt 记录为 resolved，updates={len(writer.updated)}"
    assert writer.streaming_finished_count == 0, "旧 interrupt 的回放事件不应结束当前恢复 run"
