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
from ag_ui.core import EventType
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.ask_user_question import ASK_USER_QUESTION_REASON, ASK_USER_QUESTION_SKIPPED_CONTENT
from aidev_agent.core.ag_ui.types import AgentInput
from aidev_agent.core.ag_ui.utils import get_schema_keys
from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.core.nodes.model.chat_history_assembly import _filter_unmatched_tool_calls
from aidev_agent.enums import PromptRole
from aidev_agent.pydantic_models import ChatPrompt, ExecuteKwargs
from aidev_agent.services.agent.chat import ChatCompletionAgent
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
        # 使 _build_resume_ask_user_question_finished_event 能触发 ACTIVITY_SNAPSHOT 事件推前端。
        ask_user_question_interrupts=_extract_ask_user_question_interrupts(graph, config),
    )
    chunks2 = [chunk async for chunk in agui2.run(agent_input2)]  # noqa: F841

    # 验证续流事件流：不应出现重复的 TOOL_CALL_START/ARGS/END（中断前已发到前端），
    # 只应出现 TOOL_CALL_RESULT（由 OnToolNodeFinish 路径独立产出）。
    tool_call_starts = [c for c in chunks2 if '"type":"TOOL_CALL_START"' in c]
    tool_call_args = [c for c in chunks2 if '"type":"TOOL_CALL_ARGS"' in c]
    tool_call_ends = [c for c in chunks2 if '"type":"TOOL_CALL_END"' in c]
    tool_call_results = [c for c in chunks2 if '"type":"TOOL_CALL_RESULT"' in c]
    assert not tool_call_starts, f"续流不应有 TOOL_CALL_START，实际: {tool_call_starts}"
    assert not tool_call_args, f"续流不应有 TOOL_CALL_ARGS，实际: {tool_call_args}"
    assert not tool_call_ends, f"续流不应有 TOOL_CALL_END，实际: {tool_call_ends}"
    assert len(tool_call_results) == 1, f"续流应有 1 条 TOOL_CALL_RESULT，实际: {len(tool_call_results)}"

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

    # SSE 层不再承担 DB 写入职责，interrupt 终态由 agent 侧 ChatCompletionAgent.execute()
    # 前置派发的会话回写事件（handle_ask_user_question_finalize）负责。
    # 本 e2e 测试仅模拟 SSE 层（不经 execute()），因此 interrupt 记录应仍为 pending（SSE 层不写 DB）。
    assert interrupt_after[0]["status"] == "pending", (
        f"SSE 层不应更新 interrupt 终态，status 应仍为 pending，实际: {interrupt_after[0]['status']}"
    )


def _seed_mock_record(mock_client, role, content, top_fields=None, property_=None) -> int:
    """通过 _MockApi.create_chat_session_content 落库一条记录并返回其 id（复用生产写路径）。

    ``top_fields``：额外顶层字段（如 activity_type / tool_call_id），直接写入落库记录顶层；
    ``property_``：property dict（含 builtin_property）。``_MockApi`` 记录形态为
    ``{id, role, content, status, property}``。
    """
    payload = {"role": role, "content": content, "status": "complete", "property": property_ or {}}
    resp = mock_client.api.create_chat_session_content(payload, {})
    record_id = resp["data"]["id"]
    if top_fields:
        for rec in mock_client.api._contents:
            if rec["id"] == record_id:
                rec.update(top_fields)
                break
    return record_id


def _make_resume_agent(mock_client, session_code, ledger_records):
    """构造直接触达 _stream 快照的 ChatCompletionAgent。

    ``ledger_records`` 为 lossless ChatPrompt 单账本（chat_history，唯一历史事实源），由
    ``_MockApi.get_chat_session_contents``（历史 records）经就地改写（interrupt 记录 content
    升级为终态、原 id 不变）拼接本轮 patch 记录组成。

    返回 ``(agent, contents)``，其中 ``contents`` 为 execute 前（build 期）从 mock 取得的记录集
    （快照 base 数据源），供与快照 messages 做字段级同构对比。
    """
    contents = mock_client.api.get_chat_session_contents({"session_code": session_code}, {})["data"]
    llm = _FakeToolCallingLLM(responses=[AIMessage(content="完成")])
    writer = AGUISessionWriter(session_code=session_code, client=mock_client, username="test", tools=[])
    agent = ChatCompletionAgent(
        chat_model=llm,
        checkpointer=MemorySaver(),
        chat_history=list(ledger_records),
        event_handler=writer,
    )
    return agent, contents


def _first_snapshot_messages(agent, input_text: str = "") -> list[dict]:
    """执行流式并返回首帧 MESSAGES_SNAPSHOT 的 messages（换源后快照）。"""
    results = [json.loads(each[6:]) for each in agent.execute(ExecuteKwargs(stream=True, input=input_text))]
    assert results[0].get("type") == EventType.MESSAGES_SNAPSHOT.value, (
        f"首条事件应为 MESSAGES_SNAPSHOT: {results[0].get('type')}"
    )
    return results[0].get("messages") or []


def _pending_interrupt_content() -> dict:
    """构造 pending interrupt 原始 content（未改写形态）。"""
    return {
        "outcome": {
            "type": "interrupt",
            "interrupts": [{"interruptId": "int-question-1", "metadata": {"status": "pending"}}],
        }
    }


def _terminal_interrupt_content(status: str) -> dict:
    """构造改写后的终态 interrupt content（outcome.type=success + metadata.status=终态）。"""
    return {
        "outcome": {
            "type": "success",
            "interrupts": [{"interruptId": "int-question-1", "metadata": {"status": status}}],
        },
        "result": {"payload": {"answers": []}},
    }


def _terminal_snapshot_by_status(snapshot_messages, status: str) -> list[dict]:
    """在快照 messages 中筛出 outcome.type==success 且 metadata.status==status 的 interrupt 终态。"""
    terminal = []
    for m in snapshot_messages:
        if m.get("role") != PromptRole.INTERRUPT.value:
            continue
        content = m.get("content") or {}
        interrupts = (content.get("outcome") or {}).get("interrupts") or []
        if content.get("outcome", {}).get("type") == "success" and any(
            (i.get("metadata") or {}).get("status") == status for i in interrupts
        ):
            terminal.append(m)
    return terminal


@pytest.mark.asyncio
async def test_ask_user_resume_snapshot_matches_contents():
    """问答中断 answer 续流：首帧快照与 _MockApi contents 记录集同构，含 RESOLVED 终态、本轮 user 消息。

    换源后快照数据源 = lossless chat_history 单账本（与前端历史接口同源），
    字段级（id/role/content）与历史接口记录一致；interrupt 记录被就地改写为 RESOLVED 终态
    （原 id 不变），快照含且仅含这张终态 interrupt 卡片。
    多模态/知识库召回内容在快照与历史接口间一致（硬性断言）。
    """
    mock_client = _MockBKAidevClient()
    # 基础 contents 记录：user + assistant + pending interrupt（builtin_property 含 interrupt_id）
    _seed_mock_record(mock_client, role=PromptRole.USER.value, content="问我喜欢什么运动")
    _seed_mock_record(mock_client, role=PromptRole.ASSISTANT.value, content="您喜欢什么运动？")
    int_id = _seed_mock_record(
        mock_client,
        role=PromptRole.INTERRUPT.value,
        content=_pending_interrupt_content(),
        property_={"builtin_property": {"interrupt_id": "int-question-1"}},
    )
    # 多模态 + 知识库召回记录（落库 content 为 JSON 字符串数组 / reference_document dict）
    _seed_mock_record(
        mock_client,
        role=PromptRole.USER.value,
        content=json.dumps(
            [
                {"type": "text", "text": "图片内容"},
                {"type": "binary", "mime_type": "image/jpeg", "url": "http://x/a.jpg", "id": "img1"},
            ],
            ensure_ascii=False,
        ),
    )
    _seed_mock_record(
        mock_client,
        role=PromptRole.ACTIVITY.value,
        content={
            "content": "知识库召回内容",
            "reference_document": [{"origin_file_url": "http://x/doc.pdf", "name": "doc", "url": "http://x/doc"}],
        },
        top_fields={"activity_type": "knowledge_rag"},
    )

    # 单账本 = contents 历史记录，其中 interrupt 记录（int_id）被就地改写为 RESOLVED 终态
    # （原 id 不变，模拟 _handle_answer_path 的就地升级）；本轮 user 由 _prepare_pre_run_history 经 input 并入账本
    contents = mock_client.api.get_chat_session_contents({"session_code": "resume-snapshot-1"}, {})["data"]
    ledger_records = [
        {**rec, "content": _terminal_interrupt_content("resolved")} if str(rec["id"]) == str(int_id) else rec
        for rec in contents
    ]
    agent, contents = _make_resume_agent(
        mock_client,
        session_code="resume-snapshot-1",
        ledger_records=ledger_records,
    )
    snapshot_messages = _first_snapshot_messages(agent, input_text="我喜欢瑜伽")

    # 字段级同构：contents 记录（含被就地改写的 interrupt 记录）在快照中存在且 id/role 一致
    # （contents 为 build 期从 mock 取得的数据源，即快照 base；后续 execute 写入的本轮记录不在其中）
    for rec in contents:
        match = [m for m in snapshot_messages if m.get("id") == str(rec["id"])]
        assert match, f"快照缺失 contents 记录 id={rec['id']}"
        assert match[0].get("role") == rec["role"], f"记录 id={rec['id']} role 不一致"
    # user/assistant 纯文本记录 content 直接一致（同构核心；多模态 JSON 字符串会被解析为结构化数组，单列断言）
    for rec in contents:
        if rec["role"] not in (PromptRole.USER.value, PromptRole.ASSISTANT.value):
            continue
        if isinstance(rec["content"], list):
            continue
        if isinstance(rec["content"], str):
            try:
                if isinstance(json.loads(rec["content"]), list):
                    continue  # 多模态 JSON 字符串数组，走结构化断言
            except (json.JSONDecodeError, TypeError):
                pass
        match = [m for m in snapshot_messages if m.get("id") == str(rec["id"])]
        assert match, f"快照缺失纯文本记录 id={rec['id']}"
        assert match[0].get("content") == rec["content"], f"记录 id={rec['id']} content 不一致"

    # 改写后无 pending 残留（账本中 interrupt 记录已就地升级为终态，快照不含 pending 卡片）
    stale_pending = [
        m
        for m in snapshot_messages
        if m.get("role") == PromptRole.INTERRUPT.value
        and (m.get("content") or {}).get("outcome", {}).get("type") == "interrupt"
    ]
    assert not stale_pending, f"快照不应包含 pending interrupt 陈旧副本: {stale_pending}"

    # RESOLVED 终态 interrupt 就地改写（原 id 不变），快照含这张终态卡片且无独立终态副本
    assert _terminal_snapshot_by_status(snapshot_messages, "resolved"), "快照应含 RESOLVED 终态 interrupt"
    assert any(m.get("id") == str(int_id) for m in snapshot_messages), "RESOLVED 终态 interrupt 应保留原 id"

    # 本轮 user 消息并入快照（经 _prepare_pre_run_history 并入单账本）
    assert any(
        m.get("role") == PromptRole.USER.value and m.get("content") == "我喜欢瑜伽" for m in snapshot_messages
    ), "快照应含本轮 user 消息"

    # 硬性断言：多模态 binary 项 type=="binary" 且 mimeType 键存在
    binary_found = False
    for m in snapshot_messages:
        if m.get("role") != PromptRole.USER.value or not isinstance(m.get("content"), list):
            continue
        for item in m["content"]:
            if isinstance(item, dict) and item.get("type") == "binary" and item.get("mimeType"):
                binary_found = True
    assert binary_found, "快照应含 type==binary 且 mimeType 键非空的多模态项"

    # 硬性断言：activity 消息 content 含嵌套 referenceDocument 且引用项 originFileUrl 存在
    rag_found = False
    for m in snapshot_messages:
        if m.get("role") != PromptRole.ACTIVITY.value:
            continue
        content = m.get("content") or {}
        ref_docs = content.get("referenceDocument") if isinstance(content, dict) else None
        if isinstance(ref_docs, list) and any(isinstance(d, dict) and d.get("originFileUrl") for d in ref_docs):
            rag_found = True
    assert rag_found, "快照应含 referenceDocument 且引用项 originFileUrl 存在的知识库召回"


@pytest.mark.asyncio
async def test_ask_user_skip_snapshot_includes_tool_and_cancelled():
    """问答中断 skip 续流：首帧快照含 skip tool 记录 + CANCELLED 终态 interrupt（原 id），无 pending 残留。

    skip 路径改写后：interrupt 记录就地升级为 CANCELLED 终态（原 id 不变），
    另补 skip tool 记录（content==SKIPPED、toolCallId 非空），顺序为 [..., interrupt(升级), tool]。
    """
    mock_client = _MockBKAidevClient()
    _seed_mock_record(mock_client, role=PromptRole.USER.value, content="问我问题")
    int_id = _seed_mock_record(
        mock_client,
        role=PromptRole.INTERRUPT.value,
        content=_pending_interrupt_content(),
        property_={"builtin_property": {"interrupt_id": "int-question-1"}},
    )

    # 单账本 = contents 历史记录（interrupt 记录就地改写为 CANCELLED 终态，原 id 不变）
    # + skip tool patch 记录（模拟 _handle_skip_path 的 tool append）
    contents = mock_client.api.get_chat_session_contents({"session_code": "resume-skip-1"}, {})["data"]
    ledger_records = [
        {**rec, "content": _terminal_interrupt_content("cancelled")} if str(rec["id"]) == str(int_id) else rec
        for rec in contents
    ] + [
        {
            "id": "tool-skip-1",
            "role": PromptRole.TOOL.value,
            "content": ASK_USER_QUESTION_SKIPPED_CONTENT,
            "status": "complete",
            "tool_call_id": "call_auq_001",
        },
    ]
    agent, _ = _make_resume_agent(
        mock_client,
        session_code="resume-skip-1",
        ledger_records=ledger_records,
    )
    snapshot_messages = _first_snapshot_messages(agent)

    # skip tool 记录并入：content==SKIPPED、toolCallId 非空
    skip_tools = [
        m
        for m in snapshot_messages
        if m.get("role") == PromptRole.TOOL.value and m.get("content") == ASK_USER_QUESTION_SKIPPED_CONTENT
    ]
    assert skip_tools, "快照应含 skip 路径的 tool 记录"
    assert skip_tools[0].get("toolCallId"), f"skip tool 记录 toolCallId 应为非空: {skip_tools[0].get('toolCallId')}"

    # CANCELLED 终态 interrupt 就地改写（原 id 不变）
    assert _terminal_snapshot_by_status(snapshot_messages, "cancelled"), "快照应含 CANCELLED 终态 interrupt"
    assert any(m.get("id") == str(int_id) for m in snapshot_messages), "CANCELLED 终态 interrupt 应保留原 id"

    # 改写后无 pending 残留
    stale_pending = [
        m
        for m in snapshot_messages
        if m.get("role") == PromptRole.INTERRUPT.value
        and (m.get("content") or {}).get("outcome", {}).get("type") == "interrupt"
    ]
    assert not stale_pending, f"快照不应含 pending interrupt 陈旧副本: {stale_pending}"


@pytest.mark.asyncio
async def test_new_turn_snapshot_includes_current_user_message():
    """新对话首轮：首帧快照含本轮 user 消息，且数据源与 contents 记录集同构。

    ``execute(stream=True, input=...)`` 触发 ``_prepare_pre_run_history`` 将本轮 user 记录并入
    ``chat_history`` 单账本；快照同时含 contents 历史记录与本轮 user 消息。
    """
    mock_client = _MockBKAidevClient()
    _seed_mock_record(mock_client, role=PromptRole.USER.value, content="历史上的问题")
    _seed_mock_record(mock_client, role=PromptRole.ASSISTANT.value, content="历史上的回答")

    contents = mock_client.api.get_chat_session_contents({"session_code": "new-turn-1"}, {})["data"]
    agent, contents = _make_resume_agent(
        mock_client,
        session_code="new-turn-1",
        ledger_records=contents,
    )
    snapshot_messages = _first_snapshot_messages(agent, input_text="第一条用户消息")

    # 本轮 user 消息不丢（经 _prepare_pre_run_history 并入单账本）
    assert any(
        m.get("role") == PromptRole.USER.value and m.get("content") == "第一条用户消息" for m in snapshot_messages
    ), "新对话首帧快照应含本轮 user 消息"

    # 数据源与 contents 记录集同构：contents 历史记录在快照中存在且 id/role/content 一致
    # （contents 为 build 期从 mock 取得的数据源，即快照 base）
    for rec in contents:
        match = [m for m in snapshot_messages if m.get("id") == str(rec["id"])]
        assert match, f"快照缺失 contents 记录 id={rec['id']}"
        assert match[0].get("role") == rec["role"]
        if isinstance(rec["content"], str):
            assert match[0].get("content") == rec["content"], f"记录 id={rec['id']} content 不一致"


def test_filter_unmatched_tool_calls_preserves_ask_user_question():
    """_filter_unmatched_tool_calls 应保留 ask_user_question 的 tool_call（有对应 interrupt 记录）。

    ask_user_question 中断时 AI 有 tool_call 但无 tool 结果（interrupt 中断），
    如果 _filter_unmatched_tool_calls 过滤掉这条 assistant 消息，续流时
    MESSAGES_SNAPSHOT 会丢失 AI(AskUser) 部分。
    """
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

    result = _filter_unmatched_tool_calls(chat_history)

    # assistant 消息应被保留（有对应 interrupt 记录）
    assistant_msgs = [p for p in result if p.role == "assistant"]
    assert len(assistant_msgs) == 1, f"ask_user_question 的 assistant 消息应被保留，实际: {len(assistant_msgs)} 条"
    # tool_call 应保留（在 builtin_property.tool_calls 中）
    tool_calls = assistant_msgs[0].builtin_property.get("tool_calls", [])
    assert len(tool_calls) == 1, f"tool_call 应保留，实际: {len(tool_calls)} 条"
    assert tool_calls[0]["id"] == "call_auq_001"
