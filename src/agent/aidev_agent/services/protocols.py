# -*- coding: utf-8 -*-
"""Agent 协议定义

定义所有 Agent 类型的公共协议接口,确保不同 Agent 实现,遵循统一的接口约定。

"""

from typing import Generator, Protocol, runtime_checkable

from aidev_agent.services.pydantic_models import ExecuteKwargs


@runtime_checkable
class CompletionAgentProtocol(Protocol):
    """Agent 公共协议

    所有注册到 AgentInstanceFactory 的 Agent 类型都应当满足该协议：
    - execute(): 执行 Agent,返回字符串生成器（流式）或结果（非流式）
    - stop(): 停止 Agent 执行

    注意：
    - execute_kwargs 参数对于 ChatCompletionAgent 是必需的，
      对于 FlowAgentCompletionAgent 是可选的（默认为 None）。
    - Protocol 不要求签名完全一致，只要求调用兼容性（Liskov 替换）。
    """

    def execute(self, execute_kwargs: ExecuteKwargs | None = None) -> Generator[str, None, None] | str:
        """执行 Agent

        Args:
            execute_kwargs: 执行参数，ChatAgent 必需，FlowAgent 可选

        Returns:
            流式模式返回字符串生成器，非流式模式返回结果字典/字符串
        """
        ...

    def stop(self) -> None:
        """停止 Agent 执行"""
        ...


@runtime_checkable
class FlowAgentClient(Protocol):
    """Flow Agent 所需的 API 客户端协议

    描述 FlowAgentCompletionAgent._get_client() 所需的最小接口。
    """

    def start_flow_agent(self, data: dict, **kwargs) -> dict:
        """启动 flow agent 任务，返回包含 task_id 的字典"""
        ...


@runtime_checkable
class FlowAgentPollClient(Protocol):
    """Flow Agent 轮询所需的 API 客户端协议

    描述 FlowAgentCompletionAgent._poll_task() 所需的最小接口。
    """

    def get_flow_agent_task_info(self, task_id: str, **kwargs) -> dict:
        """获取 flow agent 任务信息"""
        ...
