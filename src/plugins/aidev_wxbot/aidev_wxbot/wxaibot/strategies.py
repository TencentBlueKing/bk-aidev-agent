# -*- coding: utf-8 -*-
"""
企微渠道 Agent 处理策略。

使用策略模式将不同 Agent 类型的处理逻辑解耦，本模块只负责：
1. 定义策略协议（AgentStrategy）
2. 实现策略编排（ChatAgentStrategy / FlowAgentStrategy）
3. 策略注册与分发（resolve_strategy）

具体的流消费、事件格式化、认证适配分别委托给：
- stream: SSE 流解析与消费
- formatters: Flow 事件 → 企微可读文本
- auth: RTX 解析与 FlowAgentClient 认证
"""

from __future__ import annotations

import time
import uuid
from logging import getLogger
from typing import TYPE_CHECKING, Protocol

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentBuildType, AgentType, ChannelType
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_bkplugin.services.agent_config import AgentConfigFetcher
from aidev_bkplugin.services.agent_execution import AgentExecutor, build_execute_kwargs
from aidev_bkplugin.services.agent_helpers import AgentHelper
from aidev_bkplugin.services.agent_session import SessionManager

from .auth import WxFlowAgentClient
from .context import LlmChunkMsg
from .direct_stream import AgentStream
from .stream import consume_chat_stream, consume_flow_stream
from .stream_registry import stream_registry

if TYPE_CHECKING:
    from ..utils.rabbitmq import RabbitMQClient

logger = getLogger(__name__)

WECOM_AGENT_EXECUTION_POLICY = (
    "企业微信会话执行规则：\n"
    "1. 用户已给出目标对象、时间范围、数据类型和返回数量时，直接调用工具；"
    "过滤条件等可选参数未提供时使用无过滤默认值，不得重复询问确认。\n"
    "2. 用户要求先说明将开始查询时，先只输出一句简短说明，然后立即调用工具。\n"
    "3. 用户要求返回 N 条记录时，最终回复必须完整展示实际获得的 N 条不同记录，"
    "使用序号 1 到 N 的 Markdown 表格；不得用摘要、样例或省略号代替。\n"
    "4. 工具实际返回少于 N 条时，完整展示已有记录并明确实际条数；不得虚构数据。"
)
WECOM_AGENT_TEMPERATURE = 0.1


# ---------------------------------------------------------------------------
# 策略协议
# ---------------------------------------------------------------------------


class AgentStrategy(Protocol):
    """Agent 处理策略协议。"""

    def execute(
        self,
        *,
        content: str,
        stream_id: str,
        username: str,
        thread_id: str,
        group_id: str,
        rabbitmq_client: RabbitMQClient,
    ) -> None: ...

    def open_stream(
        self,
        *,
        content: str,
        username: str,
        thread_id: str,
        group_id: str,
    ) -> AgentStream: ...


# ---------------------------------------------------------------------------
# Chat Agent 策略
# ---------------------------------------------------------------------------


class ChatAgentStrategy:
    """Chat Agent 策略 —— 调用 LLM 对话，流式推送文本 delta。"""

    def execute(
        self,
        *,
        content: str,
        stream_id: str,
        username: str,
        thread_id: str,
        group_id: str,
        rabbitmq_client: RabbitMQClient,
    ) -> None:
        start_time = time.time()
        agent_stream = self.open_stream(
            content=content,
            username=username,
            thread_id=thread_id,
            group_id=group_id,
        )
        result = agent_stream.generator
        session_code = agent_stream.session_code
        logger.info(f"stream_id:{stream_id} chat agent ok, session_code={session_code}")
        stream_registry.register(stream_id, session_code)
        try:
            if agent_stream.is_stream:
                consume_chat_stream(
                    result,
                    stream_id,
                    start_time,
                    rabbitmq_client,
                    on_run_started=lambda run_id: stream_registry.set_run_id(stream_id, run_id),
                    is_cancelled=lambda: stream_registry.is_cancel_requested(stream_id),
                )
                return

            # 非流式兜底
            final_content = ""
            if isinstance(result, dict):
                choices = result.get("choices") or [{}]
                final_content = (choices[0].get("delta") or {}).get("content", "") or ""
            if not stream_registry.is_cancel_requested(stream_id):
                LlmChunkMsg(
                    content=final_content or "未获取到回答内容",
                    is_finish=True,
                    stream_id=stream_id,
                ).append_to_cache(rabbitmq_client)
        finally:
            stream_registry.unregister(stream_id)

    def open_stream(
        self,
        *,
        content: str,
        username: str,
        thread_id: str,
        group_id: str,
    ) -> AgentStream:
        """创建 Chat Agent 原始 SSE，供 callback 或 WebSocket 各自消费。"""
        execute_kwargs = build_execute_kwargs(
            {"stream": True, "thread_id": thread_id, "executor": username, "group_id": group_id},
            username,
        )
        result, session_code = AgentExecutor.run_chat_completion_with_thread_id(
            thread_id=thread_id,
            input_text=content,
            username=username,
            execute_kwargs=execute_kwargs,
            channel_type=ChannelType.RTX.value,
            save_content=True,
            transient_system_prompt=WECOM_AGENT_EXECUTION_POLICY,
            enable_query_clarification=False,
            temperature=WECOM_AGENT_TEMPERATURE,
        )
        return AgentStream(
            kind="chat",
            generator=result,
            session_code=session_code,
            is_stream=bool(execute_kwargs.stream),
        )


# ---------------------------------------------------------------------------
# Flow Agent 策略
# ---------------------------------------------------------------------------


class FlowAgentStrategy:
    """Flow Agent 策略 —— 启动 bkflow 任务，轮询状态并推送结构化进度。

    编排流程：
    1. 确定用户 RTX
    2. 获取/创建 session
    3. 保存用户输入
    4. 构建 FlowAgentCompletionAgent
    5. 消费 SSE 事件流
    """

    def execute(
        self,
        *,
        content: str,
        stream_id: str,
        username: str,
        thread_id: str,
        group_id: str,
        rabbitmq_client: RabbitMQClient,
    ) -> None:
        start_time = time.time()
        agent_stream = self.open_stream(
            content=content,
            username=username,
            thread_id=thread_id,
            group_id=group_id,
        )
        session_code = agent_stream.session_code
        stream_registry.register(stream_id, session_code)
        try:
            logger.info(f"stream_id:{stream_id} flow agent started, session_code={session_code}")
            consume_flow_stream(
                agent_stream.generator,
                stream_id,
                start_time,
                rabbitmq_client,
                session_code=session_code,
                on_run_started=lambda run_id: stream_registry.set_run_id(stream_id, run_id),
                is_cancelled=lambda: stream_registry.is_cancel_requested(stream_id),
            )
        finally:
            stream_registry.unregister(stream_id)

    def open_stream(
        self,
        *,
        content: str,
        username: str,
        thread_id: str,
        group_id: str,
    ) -> AgentStream:
        """创建 Flow Agent 原始 SSE，供 callback 或 WebSocket 各自消费。"""
        rtx_username = username
        logger.info(f"[FlowAgentStrategy] 使用 RTX: {rtx_username}")
        turn_id = uuid.uuid4().hex
        session_manager = SessionManager(username=rtx_username)
        session_code = session_manager.get_or_create_by_thread_id(thread_id)
        session_manager.save_content(session_code=session_code, role="user", content=content, turn_id=turn_id)

        agent_instance = AgentInstanceFactory.build_agent(
            agent_type=AgentType.FLOW,
            build_type=AgentBuildType.DIRECT,
            session_code=session_code,
            session_context_data=[],
            event_handler=AGUISessionWriter(
                session_code=session_code,
                client=AgentHelper.get_client(),
                username=rtx_username,
                turn_id=turn_id,
            ),
            username=rtx_username,
            flow_resource_manager=WxFlowAgentClient(username, rtx_username=rtx_username),
            flow_start_params={"session_code": session_code, "channel_type": ChannelType.RTX.value},
            poll_interval=float(agent_settings.FLOW_AGENT_POLL_INTERVAL),
            poll_timeout=float(agent_settings.FLOW_AGENT_POLL_TIMEOUT),
        )
        return AgentStream(
            kind="flow",
            generator=agent_instance.execute(),
            session_code=session_code,
        )


# ---------------------------------------------------------------------------
# 策略注册表 & 工厂函数
# ---------------------------------------------------------------------------

_STRATEGY_REGISTRY: dict[str, type] = {
    "chat": ChatAgentStrategy,
    "flow": FlowAgentStrategy,
}

_DEFAULT_STRATEGY_TYPE = "chat"


def resolve_strategy(username: str) -> AgentStrategy:
    """根据平台配置的 agent_type 解析出对应的处理策略。"""
    try:
        agent_info = AgentConfigFetcher.get_info(username=username)
        agent_type = agent_info.get("agent_type", "") or _DEFAULT_STRATEGY_TYPE
    except Exception as e:
        logger.warning(f"获取 agent_type 失败，回退到 chat: {e}")
        agent_type = _DEFAULT_STRATEGY_TYPE

    strategy_cls = _STRATEGY_REGISTRY.get(agent_type, _STRATEGY_REGISTRY[_DEFAULT_STRATEGY_TYPE])
    logger.info(f"username={username} resolved agent_type={agent_type}, strategy={strategy_cls.__name__}")
    return strategy_cls()
