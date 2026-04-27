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
from logging import getLogger
from typing import TYPE_CHECKING, Protocol

from aidev_agent.config import settings as agent_settings
from aidev_agent.enums import AgentBuildType, AgentType
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_bkplugin.services.agent import (
    build_execute_kwargs,
    get_agent_config_info,
    get_or_create_session_by_thread_id,
    run_chat_completion_with_thread_id,
    save_session_content,
)
from aidev_bkplugin.utils import bkaidev_api_client

from .auth import WxFlowAgentClient
from .context import LlmChunkMsg
from .stream import consume_chat_stream, consume_flow_stream

if TYPE_CHECKING:
    from ..utils.rabbitmq import RabbitMQClient

logger = getLogger(__name__)


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
        execute_kwargs = build_execute_kwargs(
            {"stream": True, "thread_id": thread_id, "executor": username, "group_id": group_id},
            username,
        )
        result, session_code = run_chat_completion_with_thread_id(
            thread_id=thread_id,
            input_text=content,
            username=username,
            execute_kwargs=execute_kwargs,
            save_content=True,
        )
        logger.info(f"stream_id:{stream_id} chat agent ok, session_code={session_code}")

        if execute_kwargs.stream:
            consume_chat_stream(result, stream_id, start_time, rabbitmq_client)
            return

        # 非流式兜底
        final_content = ""
        if isinstance(result, dict):
            choices = result.get("choices") or [{}]
            final_content = (choices[0].get("delta") or {}).get("content", "") or ""
        LlmChunkMsg(
            content=final_content or "未获取到回答内容",
            is_finish=True,
            stream_id=stream_id,
        ).append_to_cache(rabbitmq_client)


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

        # 1. username 由 ContextGenerator 通过 convert_to_rtx 转换而来
        rtx_username = username
        logger.info(f"[FlowAgentStrategy] 使用 RTX: {rtx_username}")

        # 2. 获取/创建 session
        session_code = get_or_create_session_by_thread_id(rtx_username, thread_id)

        # 3. 保存用户输入
        save_session_content(session_code, "user", content, rtx_username)

        # 4. 构建 agent 依赖（统一走 AgentInstanceFactory）
        # FlowAgent 不需要工厂 SESSION 路径的会话上下文清洗，统一走 DIRECT；
        # session_code 通过工厂 __init__ 透传到 factory.session_code，再由
        # FlowAgentCompletionAgent.build 取用。
        agent_instance = AgentInstanceFactory.build_agent(
            agent_type=AgentType.FLOW,
            build_type=AgentBuildType.DIRECT,
            session_code=session_code,
            session_context_data=[],
            event_handler=AGUISessionWriter(
                session_code=session_code,
                client=bkaidev_api_client,
                username=rtx_username,
            ),
            username=rtx_username,
            # 通过 **extra 透传给 FlowAgentCompletionAgent.build(ctx)；
            # flow_resource_manager 是 flow start 接口专用 client（带特殊认证），与
            # 工厂的 resource_manager（用于会话上下文等通用 API）解耦。
            flow_resource_manager=WxFlowAgentClient(username, rtx_username=rtx_username),
            flow_start_params={"session_code": session_code},
            poll_interval=float(agent_settings.FLOW_AGENT_POLL_INTERVAL),
            poll_timeout=float(agent_settings.FLOW_AGENT_POLL_TIMEOUT),
        )

        # 5. 执行并消费 SSE 流
        generator = agent_instance.execute()
        logger.info(f"stream_id:{stream_id} flow agent started, session_code={session_code}")
        consume_flow_stream(generator, stream_id, start_time, rabbitmq_client, session_code=session_code)


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
        agent_info = get_agent_config_info(username)
        agent_type = agent_info.get("agent_type", "") or _DEFAULT_STRATEGY_TYPE
    except Exception as e:
        logger.warning(f"获取 agent_type 失败，回退到 chat: {e}")
        agent_type = _DEFAULT_STRATEGY_TYPE

    strategy_cls = _STRATEGY_REGISTRY.get(agent_type, _STRATEGY_REGISTRY[_DEFAULT_STRATEGY_TYPE])
    logger.info(f"username={username} resolved agent_type={agent_type}, strategy={strategy_cls.__name__}")
    return strategy_cls()
