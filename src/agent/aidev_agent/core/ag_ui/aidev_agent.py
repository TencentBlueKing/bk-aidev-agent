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

from aidev_agent.core.nodes.tool.approval_wrapper import TOOL_APPROVAL_REASON
from aidev_agent.exceptions import extract_model_error_message

from .agent import LangGraphAGUIAgent
from .approval import ApprovalOutcomeBuilder, ApproveResultLiteral
from .ask_user_question import AskUserQuestionOutcomeBuilder
from .event_builders import build_tool_result_event, enhance_tool_call, is_tool_approval_required
from .events import ExtendToolCallStartEvent
from .types import (
    AgentInput,
    CustomEventNames,
    CustomMessageType,
    MessagesInProgressRecord,
    MessageSnapshotEventExtend,
    RunFinishedSuccessOutcome,
    SessionPersistenceEventNames,
    State,
    serialize_run_finished_outcome,
)
from .utils import langchain_messages_to_streaming_events

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
    ):
        super().__init__(name=name, graph=graph, description=description, config=config, cancel_checker=cancel_checker)
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
        """运行 Agent 并生成编码后的事件流"""
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
                    if getattr(event, "type", "") == EventType.RUN_FINISHED.value:
                        _outcome = getattr(event, "outcome", None)
                        if isinstance(_outcome, dict) and _outcome.get("type") == "interrupt":
                            for _interrupt in _outcome.get("interrupts", []):
                                if _interrupt.get("reason") != TOOL_APPROVAL_REASON:
                                    continue
                                _metadata = _interrupt.get("metadata")
                                if isinstance(_metadata, dict):
                                    _interrupt["metadata"] = (
                                        {"ticket": _metadata["ticket"]} if "ticket" in _metadata else None
                                    )
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
        支持 approval 和 ask_user_question 两种中断类型，统一构造 RunFinishedEvent。

        注意：ask_user_question 路径的 RunFinishedEvent 走 _dispatch_event（DB writer
        通过 handle_run_finished 消费事件写 DB），approval 路径的 RunFinishedEvent
        保持直发（DB 已在审批回调时落库）。

        ask_user_question 路径额外推送 MESSAGES_SNAPSHOT：前端 handleRunFinishedEvent
        只标记 loading 完成，不更新消息列表中的 interrupt 卡片内容。前端依赖
        MESSAGES_SNAPSHOT 的覆盖式语义来渲染 interrupt 卡片的 resolved 终态
        （outcome.type=success + result.payload.answers）。
        """
        resume_event = self._build_resume_finished_event(input)
        if resume_event is not None:
            try:
                self._dispatch_event(resume_event)
                yield event_encoder.encode(resume_event)
            except Exception:
                logger.exception("[Resume] Failed to emit resume event")

            # ask_user_question 续流：推送 MESSAGES_SNAPSHOT 让前端渲染 interrupt 卡片终态
            if self._ask_user_question_interrupts:
                try:
                    snapshot = self._build_updated_messages_snapshot(input, resume_event)
                    if snapshot is not None:
                        yield event_encoder.encode(snapshot)
                except Exception:
                    logger.exception("[Resume] Failed to emit MESSAGES_SNAPSHOT for ask_user_question")

    def _build_resume_finished_event(self, input: RunAgentInput) -> RunFinishedEvent | None:
        """构造续流首条"终态形态"事件（支持 approval 和 ask_user_question）。

        approval 路径：依赖 ``approve_result`` + ``approval_interrupts``（chat.py 从 DB 查询）。
        ask_user_question 路径：依赖 ``ask_user_question_interrupts``（chat.py 从 graph state 获取）。

        返回 None 表示不需要发首帧回放。
        """
        # approval 续流首帧回放
        if self._should_emit_resume_approval_finished():
            return self._build_resume_approval_finished_event(input)

        # ask_user_question 续流首帧回放
        if self._ask_user_question_interrupts:
            return self._build_resume_ask_user_question_finished_event(input)

        return None

    def _build_updated_messages_snapshot(
        self, input: RunAgentInput, resume_event: RunFinishedEvent
    ) -> MessageSnapshotEventExtend | None:
        """构造续流后的 MESSAGES_SNAPSHOT，将 interrupt 消息更新为终态形态。

        前端 handleRunFinishedEvent 只标记 loading 完成，不更新消息列表中 interrupt 卡片的 content。
        前端依赖 MESSAGES_SNAPSHOT 的覆盖式语义（list.value = messages.map(...)）来触发 Vue 响应式更新，
        渲染 interrupt 卡片的 resolved 终态（outcome.type=success + result.payload.answers）。

        从 input.messages 中找到 role=interrupt 的消息，替换其 content 为 RunFinishedEvent 的终态 content（outcome + result），其余消息不变。

        仅 ask_user_question 路径调用；approval 路径的 DB 已在后台 worker 写好，
        input.messages 中的 interrupt 记录已是 resolved 终态，无需额外处理。
        """
        messages = list(getattr(input, "messages", []) or [])
        if not messages:
            return None

        # 从 RunFinishedEvent 提取终态 outcome / result
        outcome = getattr(resume_event, "outcome", None)
        result = getattr(resume_event, "result", None)
        if outcome is None:
            return None

        # 序列化为 dict（与 MESSAGES_SNAPSHOT 的 API 格式一致）
        if hasattr(outcome, "model_dump"):
            outcome_dict = outcome.model_dump(mode="json", by_alias=True, exclude_none=True)
        else:
            outcome_dict = outcome if isinstance(outcome, dict) else {}
        if hasattr(result, "model_dump"):
            result_dict = result.model_dump(mode="json", by_alias=True, exclude_none=True)
        else:
            result_dict = result if isinstance(result, dict) else {}

        # 构造与 DB 中 upgrade_content_to_success 输出一致的终态 content：
        # {"outcome": {type, interrupts}, "result": {id, interruptId, status, payload, ...}}
        # 注意：result 是单个 dict（不是 list），与 DB 落库格式一致。
        terminal_content = {
            "outcome": outcome_dict,
            "result": result_dict,
        }

        # 替换 interrupt 消息的 content
        updated_messages = []
        found_interrupt = False
        for msg in messages:
            msg_dict = msg if isinstance(msg, dict) else (msg.model_dump() if hasattr(msg, "model_dump") else dict(msg))
            if msg_dict.get("content") == "正在调用工具...":
                msg_dict["content"] = ""
            if not found_interrupt and msg_dict.get("role") == "interrupt":
                msg_dict = dict(msg_dict)
                msg_dict["content"] = terminal_content
                msg_dict["status"] = "complete"
                # 补充 DB 中断消息的顶层字段（前端可能依赖这些字段渲染卡片）
                interrupts = outcome_dict.get("interrupts", [])
                if interrupts:
                    first = interrupts[0]
                    msg_dict["reason"] = first.get("reason", "")
                    msg_dict["interrupt_id"] = first.get("id", "")
                found_interrupt = True
            updated_messages.append(msg_dict)

        if not found_interrupt:
            return None

        return MessageSnapshotEventExtend(
            type=EventType.MESSAGES_SNAPSHOT,
            messages=updated_messages,
        )

    def _resolve_resume_context(self, input: RunAgentInput) -> tuple[str, list]:
        """从 input.resume / forwarded_props 解析 (interruptId, answers)。

        chat.py 把 resume 放在 forwarded_props.command.resume（非 AgentInput.resume），
        前端传的 resume 可能是单 dict 或 list。返回 (interrupt_id, resume_answers)，
        interrupt_id 为空时用 self._ask_user_question_interrupts[0].id 兜底。
        """
        interrupt_id: str = ""
        resume_answers: list = []
        resume_value = None
        if isinstance(input, AgentInput):
            if input.resume:
                resume_value = input.resume
            elif input.forwarded_props:
                resume_value = (input.forwarded_props or {}).get("command", {}).get("resume")
        if resume_value:
            if isinstance(resume_value, dict):
                resume_value = [resume_value]
            if isinstance(resume_value, list) and resume_value:
                first = resume_value[0]
                if isinstance(first, dict):
                    interrupt_id = first.get("interruptId") or ""
                    resume_payload = first.get("payload") or {}
                    if isinstance(resume_payload, dict):
                        resume_answers = resume_payload.get("answers") or []
        if not interrupt_id and self._ask_user_question_interrupts:
            interrupt_id = (self._ask_user_question_interrupts[0] or {}).get("id", "") or ""
        return interrupt_id, resume_answers

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

    def _build_resume_ask_user_question_finished_event(self, input: RunAgentInput) -> RunFinishedEvent:
        """构造 ask_user_question 续流首条 RunFinishedEvent 事件（与 approval 路径对称）。

        通过 RunFinishedEvent（outcome.type=success）关闭弹窗：
        - outcome.interrupts 含完整中断数据（深拷贝 + status 刷写为 resolved）
        - result 含 interruptId / payload.answers / reason / status
        - run_id = interruptId（前端据此关联弹窗）
        """
        interrupt_id, resume_answers = self._resolve_resume_context(input)

        # 调用 AskUserQuestionOutcomeBuilder 构造终态 (outcome, result)——
        # 与 approval 续流路径对称（ApprovalOutcomeBuilder.build_run_finished_payload）。
        outcome_dict, result_dict = AskUserQuestionOutcomeBuilder.build_run_finished_payload(
            self._ask_user_question_interrupts, "resolved", resume_answers=resume_answers
        )
        return RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id=input.thread_id or "",
            run_id=interrupt_id,
            outcome=outcome_dict,
            result=result_dict,
        )

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
        #    （approved / rejected / cancelled），与 AidevAGUIAgent.run 续流首条事件同源。
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
        #    转换器内部会跳过 Human/System/Interrupt/Activity 消息，只下发 AI/Tool 的可重放事件。
        if replayable_messages:
            try:
                event_count = 0
                for ev in langchain_messages_to_streaming_events(replayable_messages):
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
        yield encoder.encode(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=agent_input.thread_id,
                run_id=run_id,
                outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
            )
        )

    async def _handle_single_event(self, event: Any, state: State) -> AsyncGenerator[BaseEvent, None]:
        """覆写：super + 拦截 TOOL_CALL_* yield，审批抑制 + 工具增强在构造侧完成（D-01）。

        MRO: AidevAGUIAgent → LangGraphAGUIAgent（PredictState 注入）→ LangGraphAgent（4 子方法分发）。
        super()._handle_single_event 执行完整链路后，拦截 yield 的 TOOL_CALL_* 事件：
        - ToolCallStartEvent: 审批工具抑制（不 yield + 记录 id），非审批工具 enhance 后 yield ExtendToolCallStartEvent
        - ToolCallArgsEvent: 已抑制 id 的不 yield
        - ToolCallEndEvent: 已抑制 id 的不 yield + discard

        覆盖所有 TOOL_CALL 来源（_handle_*_stream_event 子方法 + _handle_on_chat_model_end_event + ManuallyEmitToolCall），
        不需覆写 3 个子方法。ManuallyEmitToolCall 的 tool_call_id 不在 _suppressed_tool_call_ids（手动发射不审批），透传。
        """
        async for ev in super()._handle_single_event(event, state):
            if isinstance(ev, ToolCallStartEvent):
                if is_tool_approval_required(ev.tool_call_name, self._tool_mapping):
                    logger.info(f"[AidevAGUIAgent] 抑制需要审批的工具流式事件: {ev.tool_call_name} ({ev.tool_call_id})")
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
        """覆写：处理 OnToolNodeFinish/OnToolNodeImmediate/KnowledgeRag CUSTOM 转换（D-04）。

        D-01 后子方法 yield Event（不 dispatch），_dispatch_event 由 _handle_stream_events 消费侧执行。
        原先在 _convert_event CUSTOM 分支中做的 CUSTOM→ToolCallResultEvent/透传转换，
        现在在构造侧（本覆写）完成，yield 转换后的 Event。

        分支顺序与原 _convert_custom_event 保持一致：KNOWLEDGE_RAG_RESULT 优先（D-14 透传），
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
        if self._event_handler:
            try:
                self._event_handler(event)
            except Exception as e:
                logger.exception(f"Event handler failed: {e}")

        return super()._dispatch_event(event)

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
