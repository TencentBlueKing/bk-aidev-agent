# -*- coding: utf-8 -*-
"""Flow Agent 服务

实现 Flow Agent 的流式任务执行：
1. 调用 POST /flow_agent/start/ 启动任务，获取 task_id
2. 轮询 GET /flow_agent/task_info/{task_id}/ 获取任务状态
3. 将轮询结果通过自定义 SSE 事件（CUSTOM）流式推送给前端

SSE 事件格式：
- flow_agent_start: 任务启动成功，携带 task_id
- flow_agent_result: 任务轮询结果，携带完整数据包
- flow_agent_end: 任务执行结束，携带 task_outputs

注意：flow agent 的 bkflow 任务在客户端断开（切换会话、刷新标签页）时不会停止，
任务会继续运行到完成。用户点击「停止」→ revoke bkflow 任务（不可恢复）。
"""

import copy
import time
import uuid
from logging import getLogger
from typing import Any, Callable, ClassVar, Generator

from ag_ui.core import BaseEvent, CustomEvent, EventType, RunErrorEvent, RunStartedEvent
from ag_ui.encoder import EventEncoder
from pydantic import BaseModel, Field, SkipValidation

from aidev_agent.config import settings as agent_settings
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.enums import AgentType
from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol, resource_manager
from aidev_agent.services.agent.registry import AgentBuildContext, FlowBuildExtras
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, StreamCancelledError
from aidev_agent.utils.event import RunId, emit_run_finished_event

logger = getLogger(__name__)

# 网络连续失败上限：超过此次数认为服务不可用，停止轮询
MAX_CONSECUTIVE_FAILURES = 10
# Flow Agent 任务终态
FLOW_TASK_FINISHED_STATE = "FINISHED"
FLOW_TASK_REVOKED_STATE = "REVOKED"
FLOW_TASK_FAILED_STATE = "FAILED"
FLOW_TASK_RUNNING_STATE = "RUNNING"
FLOW_TASK_FINISHED_STATES = frozenset({FLOW_TASK_FINISHED_STATE})
FLOW_TASK_FAILED_STATES = frozenset({FLOW_TASK_FAILED_STATE, FLOW_TASK_REVOKED_STATE})
FLOW_TASK_END_STATES = FLOW_TASK_FINISHED_STATES | FLOW_TASK_FAILED_STATES


class FlowAgentCompletionAgent(BaseModel):
    """Flow Agent —— 通过轮询 bkflow 任务接口实现流式推送

    核心流程：
    1. 调用 start 接口获取 task_id
    2. 以可配置的间隔轮询 task_info 接口
    3. 将状态变化转换为自定义 SSE 事件推送给前端
    """

    agent_type: ClassVar[AgentType] = AgentType.FLOW

    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    session_code: str | None = None

    flow_start_params: dict = Field(default_factory=dict, description="传给 flow_agent/start/ 接口的请求体")

    task_id: str | None = Field(default=None, description="已有的 task_id，指定后跳过 start 直接轮询")

    resume_from_node: str | None = Field(
        default=None,
        description="节点恢复操作类型（retry/skip），指定后发送 flow_agent_restart 事件",
    )

    resource_manager: SkipValidation[ResourceManagerProtocol | None] = None

    username: str | None = None

    poll_interval: float = Field(
        default_factory=lambda: float(agent_settings.FLOW_AGENT_POLL_INTERVAL),
        description="轮询间隔（秒）",
    )
    poll_timeout: float = Field(
        default_factory=lambda: float(agent_settings.FLOW_AGENT_POLL_TIMEOUT),
        description="轮询超时时间（秒）",
    )

    event_handler: Callable[[BaseEvent], None] | None = None

    # 运行时状态：任务是否已启动根据 flow_agent_start 判断
    # 用于取消时决定发 RUN_FINISHED（已启动）还是 RUN_ERROR（未启动）
    _task_started: bool = False

    class Config:
        arbitrary_types_allowed = True

    # ---------- 公共入口 ----------

    def build(self, ctx: AgentBuildContext) -> "FlowAgentCompletionAgent":
        """在 ``self``（``cls()`` 空种子实例）上原地装配 fully-built ``FlowAgentCompletionAgent`` 并返回。

        FlowAgent 不需要 chat_model / tools / knowledge 等装配，仅依赖：
        - 通用字段：``ctx.session_code`` / ``ctx.username`` / ``ctx.resource_manager``
        - Flow 专属字段：``ctx.flow.{flow_resource_manager, task_id,
          flow_start_params, poll_interval, poll_timeout}``

        ``resource_manager`` 取值优先级：
        1. ``flow.flow_resource_manager``（plugin 层注入的带认证实现）
        2. ``ctx.resource_manager``（工厂装配的通用实现）
        3. 全局 ``resource_manager()`` 工厂注册器的默认实现

        可选字段（``event_handler``）仅在提供时覆盖，缺省时保留种子默认值。
        """
        flow = ctx.flow or FlowBuildExtras()
        self.resource_manager = flow.flow_resource_manager or ctx.resource_manager
        self.session_code = ctx.session_code
        self.task_id = flow.task_id
        self.flow_start_params = flow.flow_start_params or {}
        self.poll_interval = (
            flow.poll_interval if flow.poll_interval is not None else float(agent_settings.FLOW_AGENT_POLL_INTERVAL)
        )
        self.poll_timeout = (
            flow.poll_timeout if flow.poll_timeout is not None else float(agent_settings.FLOW_AGENT_POLL_TIMEOUT)
        )
        self.resume_from_node = flow.resume_from_node
        self.username = ctx.username
        if ctx.event_handler is not None:
            self.event_handler = ctx.event_handler
        return self

    def execute(self, execute_kwargs=None) -> Generator[str, None, None]:
        """执行 Flow Agent，返回 SSE 编码的字符串生成器

        Args:
            execute_kwargs: 兼容 ChatCompletionAgent 接口，FlowAgent 中不使用
        """
        stream_thread_id = self.session_code or self.thread_id
        background_only = bool(getattr(execute_kwargs, "background_only", False))
        helper = GeneratorStreamingHelper(
            thread_id=stream_thread_id,
            defer_cleanup_on_complete=background_only,
        )
        return helper.stream(
            self._run_flow(),
            on_complete=self._on_complete,
            event_handler=self.event_handler,
        )

    def _on_complete(self) -> None:
        """EOD 提交后由 producer 统一收敛 Flow 会话终态。"""
        if self.event_handler and hasattr(self.event_handler, "set_streaming_finished"):
            self.event_handler.set_streaming_finished()

    def stop(self):
        """停止 Flow Agent"""
        stream_thread_id = self.session_code or self.thread_id
        GeneratorStreamingHelper.cancel(stream_thread_id)

    # ---------- 核心流程 ----------

    def _run_flow(self) -> Generator[str, None, None]:
        """核心流程：启动（或使用已有 task_id）→ 轮询 → 产出 SSE 事件"""
        encoder = EventEncoder()
        run_id = str(uuid.uuid4())
        # 每次运行重置任务启动状态
        self._task_started = False

        logger.info(
            "[FLOW_AGENT] _run_flow started: session_code=%s, task_id=%s, skip_start=%s",
            self.session_code,
            self.task_id,
            bool(self.task_id),
        )

        run_started_event = RunStartedEvent(type=EventType.RUN_STARTED, run_id=run_id, thread_id=self.thread_id)
        self._dispatch_event(run_started_event)
        yield encoder.encode(run_started_event)

        try:
            # start 接口使用 resource_manager（plugin 层传入的带认证 client）
            start_client = self._get_client()

            # 在调用 start 接口前检查是否已取消，避免不必要的 API 调用
            stream_thread_id = self.session_code or self.thread_id
            if GeneratorStreamingHelper.is_cancelled(stream_thread_id):
                logger.info("[FLOW_AGENT] Cancelled before start_flow_agent: session_code=%s", self.session_code)
                error_event = RunErrorEvent(type=EventType.RUN_ERROR, message=RunId.CANCELLED_MESSAGE)
                self._dispatch_event(error_event)
                yield encoder.encode(error_event)
                return

            # 优先使用已指定的 task_id，否则调用 start 接口
            task_id = self.task_id
            if not task_id:
                logger.debug(
                    "[FLOW_AGENT] Calling start_flow_agent: flow_start_params=%s, client_type=%s",
                    self.flow_start_params,
                    type(start_client).__name__,
                )

                start_result = start_client.start_flow_agent(data=self.flow_start_params)

                logger.debug("[FLOW_AGENT] start_flow_agent response: %s", start_result)

                task_id = start_result.get("task_id")
                if not task_id:
                    raise ValueError(f"flow_agent/start response missing task_id: {start_result}")

            logger.info("[FLOW_AGENT] task_id=%s, skip_start=%s", task_id, bool(self.task_id))

            # 发送启动/恢复事件：
            # - 未指定 task_id：发送 flow_agent_start（新任务启动）
            # - 指定 task_id 且 resume_from_node：发送 flow_agent_restart（节点重试/跳过后恢复轮询）
            # - 指定 task_id 且无 resume_from_node：跳过启动事件（直接轮询已有任务）
            if not self.task_id:
                start_event = self._make_custom_event(
                    name=CustomMessageType.FLOW_AGENT_START.value,
                    value=[{"task_id": str(task_id)}],
                )
                self._dispatch_event(start_event)
                yield encoder.encode(start_event)
                self._task_started = True
            elif self.resume_from_node:
                resumed_event = self._make_custom_event(
                    name=CustomMessageType.FLOW_AGENT_RESTART.value,
                    value=[{"task_id": str(task_id), "action": self.resume_from_node}],
                )
                self._dispatch_event(resumed_event)
                yield encoder.encode(resumed_event)
                self._task_started = True
                logger.info(
                    "[FLOW_AGENT] Node resumed: task_id=%s, action=%s",
                    task_id,
                    self.resume_from_node,
                )
            else:
                self._task_started = True
                logger.info("[FLOW_AGENT] Existing task_id provided, skip flow_agent_start event: task_id=%s", task_id)

            # 轮询任务状态
            rm = self._get_client()
            yield from self._poll_task(rm, str(task_id), encoder, run_id)

        except StreamCancelledError as e:
            # 任务被取消，通过 generator 机制向外传递异常
            logger.info(
                "[FLOW_AGENT] StreamCancelledError caught, re-raising: %s",
                e,
            )
            raise
        except Exception as e:
            logger.exception("[FLOW_AGENT] Flow agent error: %s", e)
            yield from self._emit_error_and_finish(encoder, run_id, str(e))

    def _poll_task(
        self, client: ResourceManagerProtocol, task_id: str, encoder: EventEncoder, run_id: str
    ) -> Generator[str, None, None]:
        """轮询任务状态并产出 SSE 事件

        轮询逻辑：
        - 每次轮询获取完整的 task_info 数据包
        - 通过 flow_agent_result 事件将完整数据包推送给前端
        - 任务进入终态后发送 flow_agent_end 事件
        """
        start_time = time.time()
        stream_thread_id = self.session_code or self.thread_id
        consecutive_failures = 0
        # 保存最后一次成功轮询的 task_info，用于取消时构造 revoke 事件
        last_task_info: dict | None = None
        logger.info(
            "[FLOW_AGENT] Polling started: task_id=%s, session_code=%s, poll_interval=%ss, poll_timeout=%ss",
            task_id,
            self.session_code,
            self.poll_interval,
            self.poll_timeout,
        )
        _poll_count = 0
        while True:
            _poll_count += 1
            if GeneratorStreamingHelper.is_cancelled(stream_thread_id):
                logger.info("[FLOW_AGENT] Task cancelled: task_id=%s, poll_count=%d", task_id, _poll_count)
                # 根据任务是否已启动决定事件类型：
                # - 已启动（flow_agent_start 已发送）：再轮询一次拿 revoke 状态，发 flow_agent_result + RUN_FINISHED
                # - 未启动（任务还没真正开始）：发 RUN_ERROR，触发暂停补写逻辑
                if self._task_started:
                    yield from self._emit_cancel_result(encoder, task_id, last_task_info)
                    logger.info("[FLOW_AGENT] Task already started, sending RUN_FINISHED: task_id=%s", task_id)
                    yield emit_run_finished_event(
                        thread_id=self.thread_id,
                        run_id=RunId.CANCELLED,
                        event_handler=self._dispatch_event,
                    )
                else:
                    logger.info("[FLOW_AGENT] Task not started yet, sending RUN_ERROR: task_id=%s", task_id)
                    error_event = RunErrorEvent(type=EventType.RUN_ERROR, message=RunId.CANCELLED_MESSAGE)
                    self._dispatch_event(error_event)
                    yield encoder.encode(error_event)
                return

            elapsed = time.time() - start_time
            if elapsed > self.poll_timeout:
                logger.warning(f"[FLOW_AGENT] Poll timeout ({self.poll_timeout}s) for task_id={task_id}")
                yield from self._emit_error_and_finish(
                    encoder, run_id, f"Flow agent poll timeout ({self.poll_timeout}s)"
                )
                return

            try:
                task_info = client.get_flow_agent_task_info(task_id)
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                logger.warning(
                    f"[FLOW_AGENT] Failed to get task info for task_id={task_id} "
                    f"(attempt {consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {e}"
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    logger.error(
                        f"[FLOW_AGENT] {MAX_CONSECUTIVE_FAILURES} consecutive failures getting task info, "
                        f"task_id={task_id}, stopping poll"
                    )
                    yield from self._emit_error_and_finish(
                        encoder,
                        run_id,
                        f"Failed to get task info after {MAX_CONSECUTIVE_FAILURES} consecutive attempts",
                    )
                    return
                self._interruptible_sleep(self.poll_interval, stream_thread_id)
                continue

            # 保存最后一次成功轮询结果，用于取消时构造 revoke 事件
            last_task_info = task_info

            # 双轨派发：
            # - 内部 event_handler（落库）始终使用 ``flow_agent_result``，保证历史回填一致；
            # - SSE 输出在 retry/skip 续流场景使用 ``flow_agent_update``
            result_event = self._make_custom_event(
                name=CustomMessageType.FLOW_AGENT_RESULT.value,
                value=[task_info],
            )
            self._dispatch_event(result_event)
            if self.resume_from_node:
                update_event = self._make_custom_event(
                    name=CustomMessageType.FLOW_AGENT_UPDATE.value,
                    value=[task_info],
                )
                yield encoder.encode(update_event)
            else:
                yield encoder.encode(result_event)

            # 兼容 task_state 和 state 两种字段名
            task_state = task_info.get("task_state", task_info.get("state", ""))

            if _poll_count <= 3 or task_state in FLOW_TASK_END_STATES:
                logger.debug(
                    f"[FLOW_AGENT] Poll #{_poll_count}: task_id={task_id}, "
                    f"task_state={task_state}, elapsed={time.time() - start_time:.1f}s"
                )

            if task_state in FLOW_TASK_END_STATES:
                logger.info(
                    f"[FLOW_AGENT] Task finished: task_id={task_id}, task_state={task_state}, "
                    f"poll_count={_poll_count}, elapsed={time.time() - start_time:.1f}s"
                )
                # 兼容 task_outputs 和 outputs 两种字段名
                end_value = {
                    "task_id": str(task_id),
                    "task_outputs": task_info.get("task_outputs", task_info.get("outputs", {})),
                }
                if task_state in FLOW_TASK_FAILED_STATES:
                    end_value["error"] = True
                    end_value["state"] = task_state

                end_event = self._make_custom_event(
                    name=CustomMessageType.FLOW_AGENT_END.value,
                    value=[end_value],
                )
                self._dispatch_event(end_event)
                yield encoder.encode(end_event)

                yield from self._emit_finish(run_id)
                return

            self._interruptible_sleep(self.poll_interval, stream_thread_id)

    # ---------- 辅助方法 ----------

    @staticmethod
    def _interruptible_sleep(duration: float, thread_id: str) -> None:
        """可中断的 sleep，每 0.1 秒检查一次取消信号

        相比 time.sleep(duration)，此方法能在 0.1 秒内响应取消请求，
        而不是最多等待 duration 秒。

        Args:
            duration: 总等待时间（秒）
            thread_id: 流的线程标识，用于检查取消状态
        """
        check_interval = 0.1
        elapsed = 0.0
        while elapsed < duration:
            time.sleep(min(check_interval, duration - elapsed))
            elapsed += check_interval
            if GeneratorStreamingHelper.is_cancelled(thread_id):
                return

    def _get_client(self) -> ResourceManagerProtocol:
        """获取资源管理器（用于 start 接口等需要特殊认证的场景）

        优先使用外部注入的 resource_manager（plugin 层传入的带认证实现），
        否则从全局 ``resource_manager`` 工厂注册器取默认实现。
        """
        if self.resource_manager is not None:
            return self.resource_manager
        return resource_manager()

    def _emit_error_and_finish(self, encoder: EventEncoder, run_id: str, message: str) -> Generator[str, None, None]:
        """发送 RUN_ERROR + RUN_FINISHED 事件对

        在超时、连续失败、未捕获异常等场景下使用，确保前端收到完整的
        错误信息和结束信号。

        Args:
            encoder: SSE 编码器
            run_id: 当前 run 的唯一标识
            message: 错误消息
        """
        error_event = RunErrorEvent(type=EventType.RUN_ERROR, message=message)
        self._dispatch_event(error_event)
        yield encoder.encode(error_event)
        yield from self._emit_finish(run_id)

    def _emit_finish(self, run_id: str) -> Generator[str, None, None]:
        """发送 RUN_FINISHED 事件

        使用通用的事件发送函数，确保统一的事件格式和编码。

        Args:
            run_id: 当前 run 的唯一标识
        """
        yield emit_run_finished_event(
            thread_id=self.thread_id,
            run_id=run_id,
            event_handler=self._dispatch_event,
        )

    @staticmethod
    def _make_custom_event(name: str, value: Any) -> CustomEvent:
        """构造 AG-UI CUSTOM 事件"""
        return CustomEvent(type=EventType.CUSTOM, name=name, value=value)

    def _emit_cancel_result(
        self, encoder: EventEncoder, task_id: str, last_task_info: dict | None
    ) -> Generator[str, None, None]:
        """发送取消后的 flow_agent_result 事件

        基于最后一次轮询数据手动构造 revoke 状态的事件：
        - task_state 改为 REVOKED
        - nodes 中 RUNNING 状态的节点改为 REVOKED
        - FINISHED 和 PENDING 等其他状态的节点保持不变
        - statistics 中的 state_counts 同步更新

        不通过 API 再轮询，因为用户点停止时 bkflow revoke 是在 cancel 信号之后才执行的，
        此时 API 返回的数据可能仍是 RUNNING 状态。

        Args:
            encoder: SSE 编码器
            task_id: 任务 ID
            last_task_info: 最后一次成功轮询的 task_info，可能为 None
        """
        if last_task_info is None:
            revoke_info = {
                "task_id": task_id,
                "task_state": FLOW_TASK_REVOKED_STATE,
                "nodes": {},
                "statistics": {"total": 0, "state_counts": {}},
            }
        else:
            revoke_info = copy.deepcopy(last_task_info)
            revoke_info["task_state"] = FLOW_TASK_REVOKED_STATE

            # 更新 nodes 中 RUNNING 状态的节点为 REVOKED，并重新统计 state_counts
            nodes = revoke_info.get("nodes", {})
            state_counts: dict[str, int] = {}
            for node_info in nodes.values():
                if isinstance(node_info, dict):
                    node_state = node_info.get("state", "")
                    if node_state == FLOW_TASK_RUNNING_STATE:
                        node_info["state"] = FLOW_TASK_REVOKED_STATE
                        node_state = FLOW_TASK_REVOKED_STATE
                    state_counts[node_state] = state_counts.get(node_state, 0) + 1

            revoke_info["statistics"] = {
                "total": last_task_info.get("statistics", {}).get("total", len(nodes)),
                "state_counts": state_counts,
            }

        revoke_event = self._make_custom_event(
            name=CustomMessageType.FLOW_AGENT_RESULT.value,
            value=[revoke_info],
        )
        self._dispatch_event(revoke_event)
        yield encoder.encode(revoke_event)
        logger.info(
            "[FLOW_AGENT] Emitted cancel result event: task_id=%s, task_state=REVOKED, nodes_count=%d",
            task_id,
            len(revoke_info.get("nodes", {})),
        )

    def _dispatch_event(self, event: BaseEvent) -> None:
        """分发事件到外部处理器（如 BaseSessionWriter）"""
        if self.event_handler:
            try:
                self.event_handler(event)
            except Exception as e:
                logger.exception(f"[FLOW_AGENT] Event handler error: {e}")
