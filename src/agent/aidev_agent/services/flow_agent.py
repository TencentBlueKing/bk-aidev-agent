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

import time
import uuid
from logging import getLogger
from typing import Any, Callable, Generator

from ag_ui.core import BaseEvent, CustomEvent, EventType, RunErrorEvent, RunFinishedEvent, RunStartedEvent
from ag_ui.encoder import EventEncoder
from pydantic import BaseModel, Field

from aidev_agent.api import BKAidevApi
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.config import settings as agent_settings
from aidev_agent.services.messages_handler import GeneratorStreamingHelper, StreamCancelledError
from aidev_agent.services.protocols import FlowAgentClient, FlowAgentPollClient

logger = getLogger(__name__)

# 网络连续失败上限：超过此次数认为服务不可用，停止轮询
MAX_CONSECUTIVE_FAILURES = 10
# Flow Agent 任务终态
FLOW_TASK_FINISHED_STATES = frozenset({"FINISHED"})
FLOW_TASK_FAILED_STATES = frozenset({"FAILED", "REVOKED"})
FLOW_TASK_END_STATES = FLOW_TASK_FINISHED_STATES | FLOW_TASK_FAILED_STATES


class FlowAgentCompletionAgent(BaseModel):
    """Flow Agent —— 通过轮询 bkflow 任务接口实现流式推送

    核心流程：
    1. 调用 start 接口获取 task_id
    2. 以可配置的间隔轮询 task_info 接口
    3. 将状态变化转换为自定义 SSE 事件推送给前端
    """

    # 会话标识
    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_code: str | None = None

    # 启动参数 —— 由前端传入
    flow_start_params: dict = Field(default_factory=dict, description="传给 flow_agent/start/ 接口的请求体")

    # 已有的 task_id —— 如果指定了则跳过 start 直接轮询
    task_id: str | None = Field(default=None, description="已有的 task_id，指定后跳过 start 直接轮询")

    # 资源管理器（用于调用 flow agent start API）
    resource_manager: FlowAgentClient | None = None

    # 轮询配置
    poll_interval: float = Field(
        default_factory=lambda: float(agent_settings.FLOW_AGENT_POLL_INTERVAL),
        description="轮询间隔（秒）",
    )
    poll_timeout: float = Field(
        default_factory=lambda: float(agent_settings.FLOW_AGENT_POLL_TIMEOUT),
        description="轮询超时时间（秒）",
    )

    # 事件处理器（用于回写数据库等）
    event_handler: Callable[[BaseEvent], None] | None = None

    class Config:
        arbitrary_types_allowed = True

    # ---------- 公共入口 ----------

    def execute(self, execute_kwargs=None) -> Generator[str, None, None]:
        """执行 Flow Agent，返回 SSE 编码的字符串生成器

        Args:
            execute_kwargs: 兼容 ChatCompletionAgent 接口，FlowAgent 中不使用
        """
        stream_thread_id = self.session_code or self.thread_id
        helper = GeneratorStreamingHelper(thread_id=stream_thread_id)
        return helper.stream(self._run_flow())

    def stop(self):
        """停止 Flow Agent"""
        stream_thread_id = self.session_code or self.thread_id
        GeneratorStreamingHelper.cancel(stream_thread_id)

    # ---------- 核心流程 ----------

    def _run_flow(self) -> Generator[str, None, None]:
        """核心流程：启动（或使用已有 task_id）→ 轮询 → 产出 SSE 事件"""
        encoder = EventEncoder()
        run_id = str(uuid.uuid4())

        logger.info(
            f"[FLOW_AGENT] _run_flow started: session_code={self.session_code}, "
            f"task_id={self.task_id}, skip_start={bool(self.task_id)}"
        )

        # 0. RUN_STARTED
        run_started_event = RunStartedEvent(type=EventType.RUN_STARTED, run_id=run_id, thread_id=self.thread_id)
        self._dispatch_event(run_started_event)
        yield encoder.encode(run_started_event)

        try:
            # start 接口使用 resource_manager（plugin 层传入的带认证 client）
            start_client = self._get_client()

            # 1. 获取 task_id：优先使用已指定的 task_id，否则调用 start 接口
            task_id = self.task_id
            if not task_id:
                logger.debug(
                    f"[FLOW_AGENT] Calling start_flow_agent: "
                    f"flow_start_params={self.flow_start_params}, client_type={type(start_client).__name__}"
                )

                start_result = start_client.start_flow_agent(data=self.flow_start_params)

                logger.debug(f"[FLOW_AGENT] start_flow_agent response: {start_result}")

                task_id = start_result.get("task_id")
                if not task_id:
                    raise ValueError(f"flow_agent/start response missing task_id: {start_result}")

            logger.info(f"[FLOW_AGENT] task_id={task_id}, skip_start={bool(self.task_id)}")

            # 2. 发送 flow_agent_start 事件
            # 仅在未指定 task_id 时发送 start 事件（指定 task_id 表示直接轮询已有任务）
            if not self.task_id:
                start_event = self._make_custom_event(
                    name=CustomMessageType.FLOW_AGENT_START.value,
                    value={"task_id": str(task_id)},
                )
                self._dispatch_event(start_event)
                yield encoder.encode(start_event)
            else:
                logger.info(f"[FLOW_AGENT] Existing task_id provided, skip flow_agent_start event: task_id={task_id}")

            # 3. 轮询任务状态 —— 直接使用 SDK 的 client 调平台 API Gateway，不经过 plugin 层中转
            poll_client = self._get_poll_client()
            yield from self._poll_task(poll_client, str(task_id), encoder, run_id)

        except StreamCancelledError as e:
            # 任务被取消，通过 generator 机制向外传递异常
            logger.info(f"[FLOW_AGENT] StreamCancelledError caught, re-raising: {e}")
            raise
        except Exception as e:
            logger.exception(f"[FLOW_AGENT] Flow agent error: {e}")
            yield from self._emit_error_and_finish(encoder, run_id, str(e))

    def _poll_task(
        self, client: FlowAgentPollClient, task_id: str, encoder: EventEncoder, run_id: str
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
        logger.info(
            f"[FLOW_AGENT] Polling started: task_id={task_id}, session_code={self.session_code}, "
            f"poll_interval={self.poll_interval}s, poll_timeout={self.poll_timeout}s"
        )
        _poll_count = 0
        while True:
            _poll_count += 1
            # 检查是否被取消
            if GeneratorStreamingHelper.is_cancelled(stream_thread_id):
                logger.info(f"[FLOW_AGENT] Task cancelled: task_id={task_id}, poll_count={_poll_count}")

                # 发送 RUN_FINISHED 事件，明确告知前端任务已结束
                yield from self._emit_finish(encoder, run_id)
                return

            # 检查超时
            elapsed = time.time() - start_time
            if elapsed > self.poll_timeout:
                logger.warning(f"[FLOW_AGENT] Poll timeout ({self.poll_timeout}s) for task_id={task_id}")
                yield from self._emit_error_and_finish(
                    encoder, run_id, f"Flow agent poll timeout ({self.poll_timeout}s)"
                )
                return

            # 获取任务信息
            try:
                task_info = client.get_flow_agent_task_info(task_id)
                consecutive_failures = 0  # 成功后重置计数
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
                # 网络异常时不直接退出，等下一次轮询重试
                self._interruptible_sleep(self.poll_interval, stream_thread_id)
                continue

            # 发送 flow_agent_result 事件（完整数据包）
            result_event = self._make_custom_event(
                name=CustomMessageType.FLOW_AGENT_RESULT.value,
                value=task_info,
            )
            self._dispatch_event(result_event)
            yield encoder.encode(result_event)

            # 检查任务是否结束（兼容 task_state 和 state 两种字段名）
            task_state = task_info.get("task_state", task_info.get("state", ""))

            # 调试日志：前3次和状态变化时打印
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
                # 发送 flow_agent_end 事件（兼容 task_outputs 和 outputs 两种字段名）
                end_value = {
                    "task_id": str(task_id),
                    "task_outputs": task_info.get("task_outputs", task_info.get("outputs", {})),
                }
                if task_state in FLOW_TASK_FAILED_STATES:
                    end_value["error"] = True
                    end_value["state"] = task_state

                end_event = self._make_custom_event(
                    name=CustomMessageType.FLOW_AGENT_END.value,
                    value=end_value,
                )
                self._dispatch_event(end_event)
                yield encoder.encode(end_event)

                # 发送 RUN_FINISHED
                yield from self._emit_finish(encoder, run_id)
                return

            # 等待下次轮询（可中断，快速响应取消信号）
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

    def _get_client(self) -> FlowAgentClient:
        """获取 API 客户端（用于 start 接口等需要特殊认证的场景）"""
        if self.resource_manager is not None:
            return self.resource_manager
        return BKAidevApi.get_client()

    def _get_poll_client(self) -> FlowAgentPollClient:
        """获取轮询专用客户端 —— 直接使用 SDK client 调平台 API Gateway

        轮询 task_info 不需要经过 plugin 层中转，直接走 API Gateway 即可。
        """
        return BKAidevApi.get_client()

    def _emit_error_and_finish(
        self, encoder: EventEncoder, run_id: str, message: str
    ) -> Generator[str, None, None]:
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
        yield from self._emit_finish(encoder, run_id)

    def _emit_finish(self, encoder: EventEncoder, run_id: str) -> Generator[str, None, None]:
        """发送 RUN_FINISHED 事件

        Args:
            encoder: SSE 编码器
            run_id: 当前 run 的唯一标识
        """
        finished_event = RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=self.thread_id, run_id=run_id)
        self._dispatch_event(finished_event)
        yield encoder.encode(finished_event)

    @staticmethod
    def _make_custom_event(name: str, value: Any) -> CustomEvent:
        """构造 AG-UI CUSTOM 事件"""
        return CustomEvent(type=EventType.CUSTOM, name=name, value=value)

    def _dispatch_event(self, event: BaseEvent) -> None:
        """分发事件到外部处理器（如 BaseSessionWriter）"""
        if self.event_handler:
            try:
                self.event_handler(event)
            except Exception as e:
                logger.exception(f"[FLOW_AGENT] Event handler error: {e}")
