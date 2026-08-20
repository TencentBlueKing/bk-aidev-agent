# -*- coding: utf-8 -*-
import uuid
from collections.abc import AsyncGenerator, Generator
from logging import getLogger
from typing import Any, Callable

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.graph.state import CompiledStateGraph

from aidev_agent.exceptions import extract_model_error_message
from aidev_agent.packages.interrupt_manager import (
    TOOL_APPROVAL_REASON,
    ApprovalOutcomeBuilder,
    ApproveResultLiteral,
)
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from aidev_agent.utils.event import stamp_round_end_event

from .agent import LangGraphAGUIAgent
from .event_builders import (
    build_tool_result_event,
    enhance_tool_call,
    is_tool_approval_required,
)
from .events import ExtendToolCallStartEvent
from .types import (
    AgentInput,
    CustomEventNames,
    CustomMessageType,
    LangGraphEventTypes,
    MessagesInProgressRecord,
    MessageSnapshotEventExtend,
    RunFinishedSuccessOutcome,
    SessionPersistenceEventNames,
    State,
    serialize_run_finished_outcome,
)
from .utils import langchain_messages_to_streaming_events

ASK_USER_QUESTION_TOOL_NAME = "ask_user_question"


logger = getLogger(__name__)


class AidevAGUIAgent(LangGraphAGUIAgent):
    """实现了对自定义事件处理的 AI 辅助 Agent

    事件处理机制：
    1. event_handler: 通用事件钩子，接收所有 BaseEvent，用于 BaseSessionWriter 等外部处理器
    2. _dispatch_event: DB + SSE 纯分发，event_handler 和 super()._dispatch_event 收到同一个
       事件对象（转换/抑制已在构造侧 _handle_single_event 覆写完成）
    3. cancel_checker: 取消检测回调，返回 True 表示应该取消，Agent 会优雅地发送 RunFinishedEvent

    注意：BaseSessionWriter 处理 CUSTOM（含会话专用名）与 RUN_ERROR 等；RAW 路径已删除（死代码，AG-UI 路径从不构造 RawEvent）
    """

    def __init__(
        self,
        *,
        name: str,
        graph: CompiledStateGraph[Any, None, Any, Any],
        description: str | None = None,
        config: RunnableConfig | None | MessagesInProgressRecord = None,
        tools: dict[str, StructuredTool] | None = None,
        event_handler: Callable[[BaseEvent], None] | None = None,
        cancel_checker: Callable[[], bool] | None = None,
        mcp_fetch_failures: list[dict] | None = None,
        approve_result: ApproveResultLiteral | None = None,
        approval_interrupts: list[dict] | None = None,
        ask_user_question_interrupts: list[dict] | None = None,
        run_end_extras_hook: Callable[..., AsyncGenerator[Any, None]] | None = None,
        interrupt_processor: InterruptProcessor | None = None,
    ):
        super().__init__(
            name=name,
            graph=graph,
            description=description,
            config=config,
            cancel_checker=cancel_checker,
            interrupt_processor=interrupt_processor,
        )
        self._tool_mapping = tools or {}
        self._event_handler = event_handler
        self._suppressed_tool_call_ids: set[str] = set()
        self._mcp_fetch_failures = mcp_fetch_failures or []
        self._approve_result = approve_result
        self._approval_interrupts = approval_interrupts or []
        self._ask_user_question_interrupts = ask_user_question_interrupts or []
        # RUN_FINISHED 前的通用扩展点：由业务层（services/agent/artifacts.py）注入
        # 保持协议层无业务耦合。签名与父类 _emit_run_end_extras 兼容的 async generator。
        self._run_end_extras_hook = run_end_extras_hook

    @staticmethod
    def _format_mcp_fetch_failure_message(failures: list[dict[str, Any]]) -> str:
        """将 MCP 拉取失败列表格式化为一条临时错误消息。"""
        lines = []
        for failure in failures:
            server_name = failure.get("server_name") or "unknown"
            message = failure.get("message") or "MCP tool fetch failed"
            lines.append(f"[{server_name}] {message}")
        return "\n".join(lines)

    async def _emit_run_end_extras(self, state_values: State, thread_id: str) -> AsyncGenerator[Any, None]:
        """RUN_FINISHED 前的通用扩展点：若注入了 hook，转发其产出的事件序列。

        本方法不感知任何业务语义（如 PV / PaaS / artifacts），业务实现由构造时注入的
        ``run_end_extras_hook`` 承载（见 :func:`aidev_agent.services.agent.artifacts.build_artifacts_generated_hook`）。

        hook 通过 ``dispatch_event`` 关键字参数拿到 :meth:`_dispatch_event`，从而让
        CustomEvent 仍走"DB writer + SSE 双分发"通道；事件路由由协议层掌控。
        """
        if self._run_end_extras_hook is None:
            return
        async for ev in self._run_end_extras_hook(
            state_values=state_values,
            thread_id=thread_id,
            active_run=self.active_run,
            dispatch_event=self._dispatch_event,
        ):
            yield ev

    async def run(self, input: RunAgentInput) -> AsyncGenerator[str, None]:
        """运行 Agent 并生成编码后的事件流。

        未就绪 resume（stream_input 为 None + next_interrupt）由父类
        ``prepare_stream`` 经 ``events_to_dispatch`` 通道走快照-结束路径：本方法首帧
        MESSAGES_SNAPSHOT 后，``super().run`` 内部 RUN_STARTED → RUN_FINISHED(下一张
        卡) 即结束，不拉图。ready/普通路径正常进入 ``super().run`` 拉图。
        """
        event_encoder = EventEncoder()
        temp_message_emitted = False
        skip_encode_custom = frozenset({SessionPersistenceEventNames.ChatModelEnd.value})

        # 每次 SSE 连接先下发完整消息快照，让前端重置到 DB 中的会话状态；
        # 后续 RabbitMQ replay 只负责补当前 run 的流式增量。
        yield event_encoder.encode(
            MessageSnapshotEventExtend(
                type=EventType.MESSAGES_SNAPSHOT,
                messages=list(getattr(input, "messages", []) or []),
            )
        )

        # 续流场景：在 SDK 任何事件之前，先回放一条"终态形态"事件
        for chunk in self._emit_resume_replay_events(input, event_encoder):
            yield chunk

        async for event in super().run(input):
            try:
                # 跳过被抑制的空事件（如审批工具的流式 TOOL_CALL 事件被抑制时返回空字符串）
                if not event:
                    continue

                event_type = getattr(event, "type", "")
                # 特殊处理：不输出 message snapshot 事件（已在上方手动 yield 过完整快照）
                if event_type == EventType.MESSAGES_SNAPSHOT:
                    logger.debug(f"message snapshot: {event}")
                elif event_type == EventType.CUSTOM and getattr(event, "name", "") in skip_encode_custom:
                    continue
                elif event_type == EventType.CUSTOM and getattr(event, "name", "") == CustomMessageType.INFO.value:
                    # info（压缩通知等系统信息）仅输出到 SSE，不写入 DB
                    # InfoMessage 已在 _dispatch_compress_activity 中写入 state["messages"]，
                    # 此处直接透传 CustomEvent 供前端实时展示。
                    # SSE 流 value 格式：{"messageId": "xxx", "content": ""}
                    # 入库 InfoMessage 格式：{id: "xxx", role: "info", content: "已压缩上下文（...）"}
                    # 后续如需更新该消息，前端可配合 ACTIVITY_SNAPSHOT(activityType=info) 更新。
                    yield event_encoder.encode(event)
                else:
                    # RUN_FINISHED 事件：approval 中断的 SSE 输出仅保留 metadata.ticket，减少冗余字段。
                    # 非 approval 中断（如 ask_user_question）保留完整 metadata，前端需 questions 数组渲染卡片。
                    # HI-02（D-03/D-04 解耦）：outcome.interrupts 在事件构造/DB 落库侧保留**全量**
                    # （D-04 落库全量，base.py handle_run_finished 以此为落库源）；**SSE 单元素裁剪
                    # 只在此序列化边界发生**（D-03 SSE 逐个下发）——该 outcome dict 在 _dispatch_event
                    # 的 DB 写（_event_handler）之后才被本处就地裁剪，仅影响 SSE 载荷，不影响 DB 落库。
                    if getattr(event, "type", "") == EventType.RUN_FINISHED.value:
                        _outcome = getattr(event, "outcome", None)
                        if isinstance(_outcome, dict):
                            self._trim_run_finished_interrupts_for_sse(_outcome)
                    yield event_encoder.encode(event)

                # MCP 工具拉取失败消息需要紧跟在 RUN_STARTED 后返回
                if not temp_message_emitted and event_type == EventType.RUN_STARTED and self._mcp_fetch_failures:
                    custom_event = CustomEvent(
                        type=EventType.CUSTOM,
                        name=CustomMessageType.TEMP_MESSAGE.value,
                        value={
                            "message": self._format_mcp_fetch_failure_message(self._mcp_fetch_failures),
                            "status": "error",
                        },
                    )
                    self._dispatch_event(custom_event)
                    yield event_encoder.encode(custom_event)
                    temp_message_emitted = True
            except Exception as e:
                logger.exception(f"Failed to encode event: {e}")
                raise e

    def _emit_resume_replay_events(
        self, input: RunAgentInput, event_encoder: EventEncoder
    ) -> Generator[str, None, None]:
        """续流首帧回放：在 SDK 任何事件之前先回放一条"终态形态"事件。

        让前端能立即据此把原中断卡片更新为最终状态（关闭弹窗）。
        当前仅 approval 中断类型；ask_user_question 已移除（见
        :meth:`_build_resume_finished_event` 说明）。

        该 RunFinishedEvent 仅用于更新前端的旧中断卡片，所属 run_id 是 interruptId，
        不是当前恢复请求的 run_id。中断终态已由入口层落库，因此这里只直发 SSE，
        不能走 _dispatch_event 提前结束当前 session。
        """
        resume_event = self._build_resume_finished_event(input)
        if resume_event is not None:
            try:
                yield event_encoder.encode(resume_event)
            except Exception:
                logger.exception("[Resume] Failed to emit resume event")

    def _build_resume_finished_event(self, input: RunAgentInput) -> RunFinishedEvent | None:
        """构造续流首条"终态形态"事件（当前仅 approval）。

        approval 路径：依赖 ``approve_result`` + ``approval_interrupts``（chat.py 从 DB 查询）。

        ask_user_question 续流首帧回放**已移除**（生产回归实证 2026-09-02）：
        处理前置（chat.py ``_prepare_pre_run_history`` 在快照构建前经 on_resume 就地
        改写 interrupt 记录为终态）+ MESSAGES_SNAPSHOT 完整携带 resolved 卡片
        （outcome.type=success + result.reason/payload.answers），replay 事件冗余；
        且其会整体替换前端 pending 卡片的 content——事件数据来自 graph tasks 的
        raw value（缺顶层 reason/id），替换后已回答卡查无渲染器 → 卡片凭空消失。
        294ff5d55（用户验证可用）同样不推送该事件。

        返回 None 表示不需要发首帧回放。
        """
        # approval 续流首帧回放
        if self._should_emit_resume_approval_finished():
            return self._build_resume_approval_finished_event(input)
        return None

    def _should_emit_resume_approval_finished(self) -> bool:
        """是否需要在续流首位发送"终态 RUN_FINISHED"（approval 专用）。

        触发条件（&，全部满足）：

        1. 存在 ``approve_result``（上游 chat 入口仅审批续流时透传）；
        2. ``approval_interrupts`` 非空（DB 解析出原中断）；
        3. ``interrupts[0].reason == TOOL_APPROVAL_REASON``，保险起见限定审批类型，
           避免未来其他 interrupt 类型误触发。

        其他续流（普通续聊、非审批类型恢复）一律不发。
        """
        if not self._approve_result:
            return False
        if not self._approval_interrupts:
            return False
        first = self._approval_interrupts[0] or {}
        return isinstance(first, dict) and first.get("reason") == TOOL_APPROVAL_REASON

    def _build_resume_approval_finished_event(self, input: RunAgentInput) -> RunFinishedEvent:
        """构造续流首条"终态形态" RUN_FINISHED 事件。

        - ``run_id`` 优先取前端续流请求 ``input.resume[0].interruptId``，
          兜底取 ``approval_interrupts[0].id``——确保前端能据此精确定位原中断卡片。
        - ``outcome.type = "success"``，保留 interrupts；同时事件顶层 ``result``
          字段（与 ``outcome`` 平级）承载 interrupts[0] 扁平化数据（metadata 移入
          payload.metadata）。二者由 :meth:`ApprovalOutcomeBuilder.build_run_finished_payload`
          同源构造，与 DB 落库形态一致。

        说明：``ag_ui`` 官方 ``RunFinishedEvent`` 模型原生支持 ``result`` 字段
        （类型为 ``Any | None``），且基于 ConfiguredBaseModel ``extra=allow`` 也允许
        额外的 ``outcome`` 字段透传——直接使用官方事件类型即可输出符合协议的 SSE 载荷。
        """
        interrupt_id: str = ""
        if isinstance(input, AgentInput) and input.resume:
            interrupt_id = input.resume[0].interruptId or ""
        if not interrupt_id and self._approval_interrupts:
            interrupt_id = (self._approval_interrupts[0] or {}).get("id", "") or ""

        outcome_dict, result_dict = ApprovalOutcomeBuilder.build_run_finished_payload(
            self._approval_interrupts, self._approve_result
        )
        return RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id=input.thread_id or "",
            run_id=interrupt_id,
            outcome=outcome_dict,
            result=result_dict,
            resume_replay=True,
        )

    def build_terminal_replay_stream(
        self,
        agent_input: AgentInput,
        replayable_messages: list[BaseMessage] | None = None,
    ) -> Generator[Any, None, None]:
        """把终态 checkpoint 重建成与正常流一致的 AG-UI 编码事件序列。

        续流（resume）场景仍然不下发终态 ``MESSAGES_SNAPSHOT``——前端 SNAPSHOT 是
        覆盖式语义，会把前端已渲染的历史消息全部覆盖。同样不发 ``STATE_SNAPSHOT``——
        其经 ``get_state_snapshot`` 依赖 ``agui_entry.active_run`` 运行期状态，而重放
        路径下 ``agui_entry.run`` 从未执行，该状态未初始化。

        关于"片段语义"：调用方在续流路径下跳过了 checkpoint 同步，故 checkpoint 中的
        ``messages`` 是**完整 turn**
        （``[Human, AI(tool_call), Tool, AI(回复)]``）而非历史上的"仅新增片段"。
        但 ``langchain_messages_to_streaming_events`` 主动过滤
        ``Human/System/Interrupt/Activity``，只下发 ``AI/Tool`` 的可重放事件，
        因此最终前端拿到的仍是"前端缺的那段"（worker 异步跑完 + 30s 队列窗口已过
        的兜底场景下，前端无法通过方案 A 队列接管拿到 worker 写的事件流）：
        前端按 ``message_id`` / ``tool_call_id`` 增量合并，与正常 astream 路径下
        的渲染同构，不会撞覆盖式语义。
        """
        encoder = EventEncoder()
        run_id = agent_input.run_id or uuid.uuid4().hex

        # 1) 审批中断恢复：先回放终态 RUN_FINISHED，让前端把原中断卡片更新为最终状态
        #   （approved / rejected / cancelled），与 AidevAGUIAgent.run 续流首条事件同源。
        try:
            if self._should_emit_resume_approval_finished():
                yield encoder.encode(self._build_resume_approval_finished_event(agent_input))
        except Exception:
            logger.exception("[ResumeReplay] emit resume approval RUN_FINISHED failed")

        # 2) RUN_STARTED
        yield encoder.encode(
            RunStartedEvent(type=EventType.RUN_STARTED, thread_id=agent_input.thread_id, run_id=run_id)
        )

        # 3) 把 checkpoint 「片段」消息逐条转为流式增量事件下发，补齐前端缺失的本轮 worker 续流内容。
        #   转换器内部会跳过 Human/System/Interrupt/Activity 消息，只下发 AI/Tool 的可重放事件。
        if replayable_messages:
            try:
                event_count = 0
                # D-05 方向 a（DB 权威化）：重放 tool_call 按 DB 等价谓词过滤审批 pending
                # （同源复算，不真查 DB）——state_messages 用重放源消息，tools_mapping 用 SSE 侧注入映射。
                for ev in langchain_messages_to_streaming_events(
                    replayable_messages,
                    state_messages=replayable_messages,
                    tools_mapping=self._tool_mapping,
                ):
                    yield encoder.encode(ev)
                    event_count += 1
                logger.info(
                    "[ResumeReplay] streamed %d incremental events from checkpoint fragment, thread_id=%s",
                    event_count,
                    agent_input.thread_id,
                )
            except Exception:
                logger.exception(
                    "[ResumeReplay] failed to stream checkpoint fragment, thread_id=%s",
                    agent_input.thread_id,
                )

        # 4) RUN_FINISHED（续流场景不下发 MESSAGES_SNAPSHOT，前端复用已有消息状态 + 上面补发的增量事件）
        # 这是 checkpoint 重放，不是本轮真实结束，不打墙钟，避免前端把重连时刻当成轮次结束时间。
        finished_event = RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id=agent_input.thread_id,
            run_id=run_id,
            outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
        )
        yield encoder.encode(finished_event)

    async def _handle_single_event(self, event: Any, state: State) -> AsyncGenerator[BaseEvent, None]:
        """覆写：super + 拦截 TOOL_CALL_* yield，审批抑制 + 工具增强在构造侧完成。

        MRO: AidevAGUIAgent → LangGraphAGUIAgent（PredictState 注入）→ LangGraphAgent（4 子方法分发）。
        super()._handle_single_event 执行完整链路后，拦截 yield 的 TOOL_CALL_* 事件：
        - ToolCallStartEvent: 审批工具抑制（不 yield + 记录 id），非审批工具 enhance 后 yield ExtendToolCallStartEvent
        - ToolCallArgsEvent: 已抑制 id 的不 yield
        - ToolCallEndEvent: 已抑制 id 的不 yield + discard

        覆盖所有 TOOL_CALL 来源（_handle_*_stream_event 子方法 + _handle_on_chat_model_end_event + ManuallyEmitToolCall），
        不需覆写 3 个子方法。ManuallyEmitToolCall 的 tool_call_id 不在 _suppressed_tool_call_ids（手动发射不审批），透传。

        审批工具抑制按**原始事件来源**门控：
        - 模型阶段来源（on_chat_model_stream / on_chat_model_end，pre-approval 隐藏语义）：仍抑制，
          与首跑语义一致——审批确认前不向前端暴露工具调用样式。
        - OnToolEnd 补发来源（event.get("event") == LangGraphEventTypes.OnToolEnd，resume 续流审批已决出、
          工具已执行、ToolMessage 已存在）：不抑制，让 TOOL_CALL_START/ARGS/END 与独立路径发出的
          TOOL_CALL_RESULT 完整流向前端，避免 TOOL_CALL_RESULT 孤儿事件（工具卡片样式丢失）。
          该"已执行保留"维度与 event_builders.should_suppress_approval_tool_call 的 DB 等价谓词对齐。

        ask_user_question 工具的 TOOL_CALL_START/ARGS/END 在**首跑与续流均被抑制**（此处按工具名
        直接抑制）。UAT 复盘（2026-08-31）：ask_user 的 tool_call **不在** 45-04 快照谓词
        ``should_suppress_approval_tool_call`` 的过滤范围内（该谓词仅过滤审批 pending）——
        首跑 MESSAGES_SNAPSHOT 已携带 ask_user tool_call 渲染一次，问题卡片经 interrupt
        outcome 下发；若续流放行 OnToolEnd 补发三元组，前端会渲染第二次（单 ask_user
        双样式 UAT 回归）。与审批工具的差异恰在于：审批 pending tool_call 被快照谓词
        过滤（快照渲染 0 次），补发放行后恰好渲染一次。故 ask_user 三元组保持无条件
        抑制；第二个 ask_user 卡片样式由 run-end 出口补发 MESSAGES_SNAPSHOT 修复
        （对齐分支 B ``_build_next_interrupt_events`` 结构）。
        该"流式抑制"是根因 B（同一轮 assistant.tool_calls 存在 4 个互不一致的真相源）的组成部分，
        方向 a（DB 权威化）保持此抑制不动，数量真相源统一由 checkpoint 派生快照/重放按 DB 等价谓词
        过滤（D-05，见 event_builders.should_suppress_approval_tool_call）。
        """
        async for ev in super()._handle_single_event(event, state):
            if isinstance(ev, ToolCallStartEvent):
                # 审批工具抑制按**原始事件来源**门控（quick-omz UAT 回归）：
                # - 模型阶段来源（on_chat_model_stream/end，pre-approval 隐藏语义）仍抑制——
                #   审批确认前不向前端暴露工具调用样式；
                # - OnToolEnd 补发来源（工具已执行、approval 已解决、ToolMessage 已存在）放行——
                #   审批 pending tool_call 已被快照谓词 should_suppress_approval_tool_call 过滤
                #   （快照渲染 0 次），补发三元组与 RESULT 完整下发恰好渲染一次，避免孤儿 RESULT。
                is_ontoolend_source = bool(event and event.get("event") == LangGraphEventTypes.OnToolEnd)
                if is_tool_approval_required(ev.tool_call_name, self._tool_mapping) and not is_ontoolend_source:
                    logger.info(f"[AidevAGUIAgent] 抑制需要审批的工具流式事件: {ev.tool_call_name} ({ev.tool_call_id})")
                    self._suppressed_tool_call_ids.add(ev.tool_call_id)
                    continue  # suppress
                # ask_user 无条件抑制（首跑+续流）：其 tool_call 不在快照谓词过滤范围内，
                # 首跑 MESSAGES_SNAPSHOT 已渲染——补发/流式三元组均冗余（放行会双样式）。
                if ev.tool_call_name == ASK_USER_QUESTION_TOOL_NAME:
                    logger.info(f"[AidevAGUIAgent] 抑制 ask_user_question 工具的 TOOL_CALL_START: {ev.tool_call_id}")
                    self._suppressed_tool_call_ids.add(ev.tool_call_id)
                    continue  # suppress
                enhanced = enhance_tool_call(ev.tool_call_name, self._tool_mapping)
                ev = ExtendToolCallStartEvent(**{**ev.model_dump(), **enhanced})
            elif isinstance(ev, ToolCallArgsEvent):
                if ev.tool_call_id in self._suppressed_tool_call_ids:
                    continue  # suppress
            elif isinstance(ev, ToolCallEndEvent):
                if ev.tool_call_id in self._suppressed_tool_call_ids:
                    self._suppressed_tool_call_ids.discard(ev.tool_call_id)
                    continue  # suppress
            yield ev

    async def _handle_on_custom_event(self, event: Any) -> AsyncGenerator[BaseEvent, None]:
        """覆写：处理 OnToolNodeFinish/OnToolNodeImmediate/KnowledgeRag CUSTOM 转换。

         后子方法 yield Event（不 dispatch），_dispatch_event 由 _handle_stream_events 消费侧执行。
        原先在 _convert_event CUSTOM 分支中做的 CUSTOM→ToolCallResultEvent/透传转换，
        现在在构造侧（本覆写）完成，yield 转换后的 Event。

        分支顺序与原 _convert_custom_event 保持一致：KNOWLEDGE_RAG_RESULT 优先（透传），
        OnToolNodeFinish/OnToolNodeImmediate 随后（→ ToolCallResultEvent），其余委托 super()。
        """
        name = event.get("name", "")
        if name == CustomMessageType.KNOWLEDGE_RAG_RESULT.value:
            # value 为纯 list 供 SSE 渲染（前端只认 list 格式），
            # raw_event 保留完整 dict 供 DB 侧提取 message_id + data
            yield CustomEvent(
                type=EventType.CUSTOM,
                name=name,
                value=event.get("data", {}).get("data", []),
                raw_event=event,
            )
            return
        elif name == CustomEventNames.OnToolNodeFinish.value:
            yield build_tool_result_event(event["data"], is_immediate=False)
            return
        elif name == CustomEventNames.OnToolNodeImmediate.value:
            yield build_tool_result_event(event["data"], is_immediate=True)
            return
        async for ev in super()._handle_on_custom_event(event):
            yield ev

    def _dispatch_event(self, event: BaseEvent) -> str:
        """DB + SSE 纯分发（转换已在构造侧 _handle_single_event 覆写完成）。"""
        if isinstance(event, (RunFinishedEvent, RunErrorEvent)):
            stamp_round_end_event(event)
        if self._event_handler:
            try:
                self._event_handler(event)
            except Exception as e:
                logger.exception(f"Event handler failed: {e}")

        return super()._dispatch_event(event)

    @staticmethod
    def _trim_run_finished_interrupts_for_sse(outcome: dict) -> None:
        """串行语义（用户裁定 2026-08-31）：SSE 边界防御性裁剪 RUN_FINISHED outcome。

        仅对 ``outcome.type == "interrupt"`` 生效：把 ``outcome.interrupts`` 裁剪为
        **单元素**（当前活跃/第一个 pending）。由于源头 ``_resolve_exit`` / 分支 A
        已单元素化（DB 与 SSE 均仅当前活跃），此处裁剪对正常路径为 no-op，仅作
        防御（防其他路径多元素再犯）。顺带完成 approval 中断的 metadata.ticket 精简
        （非 approval 中断保留完整 metadata，前端需 questions 数组渲染卡片）。
        """
        if not isinstance(outcome, dict) or outcome.get("type") != "interrupt":
            return
        _interrupts = outcome.get("interrupts")
        if not isinstance(_interrupts, list):
            return
        if len(_interrupts) > 1:
            outcome["interrupts"] = _interrupts[:1]
        for _interrupt in outcome.get("interrupts", []):
            if _interrupt.get("reason") != TOOL_APPROVAL_REASON:
                continue
            _metadata = _interrupt.get("metadata")
            if isinstance(_metadata, dict):
                _interrupt["metadata"] = {"ticket": _metadata["ticket"]} if "ticket" in _metadata else None

    async def _handle_stream_events(self, input: RunAgentInput, config: RunnableConfig) -> AsyncGenerator[str, None]:
        """处理流事件，添加异常处理"""
        try:
            async for event in super()._handle_stream_events(input, config):
                yield event
        except Exception as e:
            logger.exception(f"Failed to handle stream events: {e}")
            error_chunk = extract_model_error_message(e)
            yield self._dispatch_event(RunErrorEvent(message=error_chunk))
            # 补发 RunFinishedEvent 确保前端和 BaseSessionWriter 收到完整的结束信号
            yield self._dispatch_event(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=input.thread_id,
                    run_id=self.active_run.get("id", "") if self.active_run else "",
                    outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
                )
            )
