# -*- coding: utf-8 -*-
"""ask_user 卡片生产路径回归（chat.py execute() 全链路，含 queue 机制）。

覆盖两条 48 后真实回归（生产实证，E2E 直调 agui.run() 无法覆盖）：
1. **all-ready 续流轮已答卡终态可渲染**（处置：replay 事件移除 + 快照承载——
   raw target 形态无顶层 reason/id，replay 会整体替换前端 pending 卡 content，
   ``resultRenderers[null]`` 查无渲染器 → 卡片凭空消失；处理前置改写 +
   MESSAGES_SNAPSHOT 完整携带 resolved 卡片后 replay 冗余，294ff5d55 好基线
   同样不推）。filter_ask_user_question_interrupts 归一化保留为数据面防御。
2. **not-ready 轮卡片推送**（lw4）：双卡串行答第一张后，第二张卡经 SSE 下发
   （MESSAGES_SNAPSHOT → RUN_STARTED → RUN_FINISHED(interrupt)
   协议序列由 ``AidevAGUIAgent`` 快照-结束分支保证，本测试断言卡内容可达消费端）。
"""

import json

from ag_ui.core import EventType
from aidev_agent.core.tools.ask_user_question import ask_user_question
from aidev_agent.enums import PromptRole
from aidev_agent.pydantic_models import ExecuteKwargs
from aidev_agent.services.agent import ChatCompletionAgent
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import MemorySaver


class _FakeToolCallingLLM(BaseChatModel):
    """非流式假模型：按序返回预设响应（含 tool_calls 的 AIMessage）。"""

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


class _MockApi:
    """模拟 BKAidev API client：追踪 DB 读写（id 用 str，对齐生产）。"""

    def __init__(self, client):
        self.client = client
        self._contents: list[dict] = []
        self._next_id = 1

    def create_chat_session_content(self, json, headers):
        content_id = str(self._next_id)
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
        content_id = str(path_params["id"])
        for rec in self._contents:
            if str(rec["id"]) == content_id:
                if "content" in json:
                    rec["content"] = json["content"]
                if "status" in json:
                    rec["status"] = json["status"]
                if "property" in json:
                    rec["property"] = json["property"]
                break
        return {"data": {"id": content_id}}

    def get_chat_session_contents(self, params, headers):
        return {"data": list(self._contents)}

    def update_chat_session(self, path_params, json, headers):
        return {"data": {}}

    def retrieve_chat_session(self, path_params, headers):
        return {"data": {"session_property": {}}}


class _MockBKAidevClient:
    def __init__(self):
        self.api = _MockApi(self)


def _ask_user_tool_call(tool_call_id: str, question: str, header: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "name": "ask_user_question",
                "args": {
                    "questions": [
                        {
                            "header": header,
                            "multiSelect": False,
                            "question": question,
                            "options": [{"label": "瑜伽"}, {"label": "跑步"}],
                        }
                    ]
                },
                "id": tool_call_id,
                "type": "tool_call",
            }
        ],
    )


def _ask_user_tool_calls_two() -> AIMessage:
    """单条 AIMessage 携带两个 ask_user tool_call（同轮双中断，串行一次一卡）。"""
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
                            "question": "您喜欢什么运动？",
                            "options": [{"label": "瑜伽"}, {"label": "跑步"}],
                        }
                    ]
                },
                "id": "call-auq-1",
                "type": "tool_call",
            },
            {
                "name": "ask_user_question",
                "args": {
                    "questions": [
                        {
                            "header": "编辑器",
                            "multiSelect": False,
                            "question": "您常用的编辑器？",
                            "options": [{"label": "VSCode"}, {"label": "Vim"}],
                        }
                    ]
                },
                "id": "call-auq-2",
                "type": "tool_call",
            },
        ],
    )


def _to_history_records(mock_client) -> list[dict]:
    """模拟平台下一轮传入的 session_context_data（DB 记录原样）。"""
    return [
        {"id": rec["id"], "role": rec["role"], "content": rec["content"], "status": rec["status"]}
        for rec in mock_client.api._contents
    ]


def _sse_events(agent: ChatCompletionAgent, execute_kwargs: ExecuteKwargs) -> list[dict]:
    return [json.loads(c[6:]) for c in agent.execute(execute_kwargs) if isinstance(c, str) and c.startswith("data:")]


def test_resume_replay_event_carries_renderable_result():
    """回归（生产实证）：all-ready 续流轮的已答卡终态必须可渲染（经 MESSAGES_SNAPSHOT）。

    处置（2026-09-02 用户裁定）：处理前置（``_prepare_pre_run_history`` 在快照前经
    on_resume 就地改写 interrupt 记录为终态）+ MESSAGES_SNAPSHOT 完整携带 resolved
    卡片（outcome.type=success + result.reason/payload.answers）→ **replay 事件已
    移除**（其数据来自 graph tasks raw value，缺顶层 reason/id，会整体替换前端
    pending 卡 content → ``resultRenderers[null]`` 查无渲染器 → 卡片凭空消失；
    294ff5d55 好基线同样不推该事件）。

    可渲染安全属性迁移到快照：MESSAGES_SNAPSHOT 的 interrupt 记录必须携带
    ``result.reason`` / ``interruptId`` / answers（前端 ``UserQuestionAnsweredCard``
    据此渲染已回答卡）。
    """
    mock_client = _MockBKAidevClient()
    checkpointer = MemorySaver()
    thread_id = "test-auq-replay-result"
    writer1 = AGUISessionWriter(session_code="sess-auq-replay", client=mock_client, username="test", tools=[])
    agent1 = ChatCompletionAgent(
        chat_model=_FakeToolCallingLLM(responses=[_ask_user_tool_call("call-auq-1", "您喜欢什么运动？", "运动偏好")]),
        checkpointer=checkpointer,
        chat_history=[],
        event_handler=writer1,
        tools=[ask_user_question],
    )
    agent1.thread_id = thread_id
    events1 = _sse_events(agent1, ExecuteKwargs(stream=True, input="问我喜欢什么运动"))
    rf1 = [e for e in events1 if e.get("type") == EventType.RUN_FINISHED.value]
    int_rf1 = [e for e in rf1 if e.get("outcome", {}).get("type") == "interrupt"]
    assert int_rf1, "首跑应经 SSE 推送 ask_user 卡片（RUN_FINISHED interrupt）"
    card1_id = int_rf1[-1]["outcome"]["interrupts"][0]["id"]

    # 答卡续流（生产路径：新 agent 实例 + DB 账本 + 同 checkpointer）
    writer2 = AGUISessionWriter(session_code="sess-auq-replay", client=mock_client, username="test", tools=[])
    agent2 = ChatCompletionAgent(
        chat_model=_FakeToolCallingLLM(responses=[AIMessage(content="感谢回答")]),
        checkpointer=checkpointer,
        chat_history=_to_history_records(mock_client),
        event_handler=writer2,
        tools=[ask_user_question],
    )
    agent2.thread_id = thread_id
    events2 = _sse_events(
        agent2,
        ExecuteKwargs(
            stream=True,
            input="",
            resume=[
                {
                    "interruptId": card1_id,
                    "status": "resolved",
                    "payload": {"answers": [{"question": "您喜欢什么运动？", "answer": [{"label": "瑜伽"}]}]},
                }
            ],
        ),
    )

    # replay 事件已移除：续流轮不应出现 resume_replay 事件
    replay_rf = [e for e in events2 if e.get("type") == EventType.RUN_FINISHED.value and e.get("resume_replay")]
    assert not replay_rf, "ask_user 续流不应再推送 replay 事件（快照已承载已答卡终态）"

    # 可渲染安全属性迁移：MESSAGES_SNAPSHOT 的 interrupt 记录必须可渲染
    assert events2, "续流轮应有事件"
    assert events2[0].get("type") == EventType.MESSAGES_SNAPSHOT.value, "首条事件应为 MESSAGES_SNAPSHOT"
    snapshot_interrupts = [m for m in (events2[0].get("messages") or []) if m.get("role") == PromptRole.INTERRUPT.value]
    assert snapshot_interrupts, "快照应含 interrupt 记录（已答卡回显载体）"
    snap_content = snapshot_interrupts[0].get("content") or {}
    assert (snap_content.get("outcome") or {}).get("type") == "success", "快照已答卡应为 success 终态"
    result = snap_content.get("result") or {}
    assert result.get("reason") == "aidev:user_question", (
        f"快照 result.reason 应为 aidev:user_question（实际 {result.get('reason')}）——"
        "为 null 时前端已回答卡不渲染（resultRenderers[null] 查无渲染器），卡片消失"
    )
    assert result.get("interruptId"), "快照 result.interruptId 不应为空（前端关联旧卡）"
    assert result.get("payload", {}).get("answers"), "快照 result 应携带用户答案"
    snap_interrupts_out = (snap_content.get("outcome") or {}).get("interrupts") or []
    assert snap_interrupts_out and snap_interrupts_out[0].get("reason") == "aidev:user_question"

    # Test 3：all-ready（stream_input 非 None / 单卡全答）→ 走正常拉图，不命中快照-结束短路分支。
    # 若误命中快照-结束分支，本轮只会有 [MESSAGES_SNAPSHOT, RUN_STARTED, RUN_FINISHED] 三事件、
    # 绝无图拉起的产物（STEP_STARTED/STEP_FINISHED/TOOL_CALL_RESULT）。此处断言出现这些图拉起的
    # 事件（本轮 resume 消费 ask_user 答案 → 工具结果回填），证明 all-ready 未被快照-结束分支短路。
    graph_events = [
        e
        for e in events2
        if e.get("type")
        in (EventType.STEP_STARTED.value, EventType.STEP_FINISHED.value, EventType.TOOL_CALL_RESULT.value)
    ]
    assert graph_events, (
        "all-ready 轮应拉图产出 STEP/TOOL_CALL_RESULT 事件（未被快照-结束分支短路）"
        f"；实际事件序列: {[e.get('type') for e in events2]}"
    )


def test_not_ready_round_pushes_next_card_via_sse():
    """回归：双卡串行——答第一张后续流轮（not ready）应经 SSE 推送第二张卡。

    lw4：未就绪 resume 并入父类 prepare_stream 快照-结束通道（events_to_dispatch，原 chat 层
    `_build_not_ready_sse` 已删除）。断言事件序列恰为 MESSAGES_SNAPSHOT → RUN_STARTED → RUN_FINISHED(第二张卡)，
    图不拉起（无 TEXT/TOOL 事件），已答第一张卡在首帧快照中为终态。
    """
    mock_client = _MockBKAidevClient()
    checkpointer = MemorySaver()
    thread_id = "test-auq-2card-sse"
    writer1 = AGUISessionWriter(session_code="sess-auq-2card", client=mock_client, username="test", tools=[])
    agent1 = ChatCompletionAgent(
        chat_model=_FakeToolCallingLLM(responses=[_ask_user_tool_calls_two()]),
        checkpointer=checkpointer,
        chat_history=[],
        event_handler=writer1,
        tools=[ask_user_question],
    )
    agent1.thread_id = thread_id
    events1 = _sse_events(agent1, ExecuteKwargs(stream=True, input="问我两个问题"))
    int_rf1 = [
        e
        for e in events1
        if e.get("type") == EventType.RUN_FINISHED.value and e.get("outcome", {}).get("type") == "interrupt"
    ]
    assert int_rf1, "首跑应推送第一张卡（一次一卡）"
    card1_id = int_rf1[-1]["outcome"]["interrupts"][0]["id"]

    # 答第一张 → 第二张未就绪 → 快照-结束路径应推送第二张卡
    writer2 = AGUISessionWriter(session_code="sess-auq-2card", client=mock_client, username="test", tools=[])
    agent2 = ChatCompletionAgent(
        chat_model=_FakeToolCallingLLM(responses=[AIMessage(content="两问均已作答")]),
        checkpointer=checkpointer,
        chat_history=_to_history_records(mock_client),
        event_handler=writer2,
        tools=[ask_user_question],
    )
    agent2.thread_id = thread_id
    events2 = _sse_events(
        agent2,
        ExecuteKwargs(
            stream=True,
            input="",
            resume=[
                {
                    "interruptId": card1_id,
                    "status": "resolved",
                    "payload": {"answers": [{"question": "您喜欢什么运动？", "answer": [{"label": "瑜伽"}]}]},
                }
            ],
        ),
    )

    # Test 1：事件序列恰为 MESSAGES_SNAPSHOT → RUN_STARTED → RUN_FINISHED，图不拉起。
    seq_types = [e.get("type") for e in events2]
    assert seq_types[0] == EventType.MESSAGES_SNAPSHOT.value, f"未就绪轮首条应为快照: {seq_types}"
    assert EventType.RUN_STARTED.value in seq_types, "未就绪轮应发 RUN_STARTED（前端 RUN_FINISHED 关联前提）"
    assert seq_types.count(EventType.RUN_STARTED.value) == 1, f"未就绪轮不应重复 RUN_STARTED: {seq_types}"
    assert seq_types[-1] == EventType.RUN_FINISHED.value, f"未就绪轮末条应为 RUN_FINISHED: {seq_types}"
    # 除快照/RUN_STARTED/RUN_FINISHED 外无其他事件（图不拉起，消除「每答一张卡拉一次图」乒乓）
    assert not [e for e in events2 if e.get("type") == EventType.TEXT_MESSAGE_START.value], (
        "未就绪轮图不应被拉起（无 TEXT_MESSAGE_START）"
    )
    assert not [e for e in events2 if e.get("type") == EventType.TOOL_CALL_START.value], (
        "未就绪轮图不应被拉起（无 TOOL_CALL_START）"
    )

    int_rf2 = [
        e
        for e in events2
        if e.get("type") == EventType.RUN_FINISHED.value and e.get("outcome", {}).get("type") == "interrupt"
    ]
    assert int_rf2, "未就绪续流轮应推送第二张卡（RUN_FINISHED interrupt）"
    card2 = int_rf2[-1]["outcome"]["interrupts"][0]
    assert "编辑器" in json.dumps(card2, ensure_ascii=False), "第二张卡应为编辑器问题"
    assert card2.get("reason") == "aidev:user_question"

    # Test 2：未就绪轮首帧快照中，本批已答卡（card1）应为终态（outcome.type success）。
    snapshot_interrupts = [m for m in (events2[0].get("messages") or []) if m.get("role") == PromptRole.INTERRUPT.value]
    assert snapshot_interrupts, "未就绪轮首帧快照应含 interrupt 记录"
    snap_content = snapshot_interrupts[0].get("content") or {}
    assert (snap_content.get("outcome") or {}).get("type") == "success", (
        f"快照已答卡应为 success 终态（实际 {snap_content.get('outcome')}）"
    )
