# -*- coding: utf-8 -*-
"""Flow Agent 客户端协议

只描述 Flow Agent 调用 plugin 层 client 所需的最小接口，独立于 Agent 注册体系。
Agent 协议与注册中心见 ``aidev_agent.services.agent.registry``。
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class FlowAgentClient(Protocol):
    """Flow Agent 所需的 API 客户端协议

    描述 ``FlowAgentCompletionAgent._get_client()`` 所需的最小接口。
    被作为 pydantic 字段类型使用，需要 ``@runtime_checkable`` 以支持 ``isinstance`` 校验。
    """

    def start_flow_agent(self, data: dict, **kwargs) -> dict:
        """启动 flow agent 任务，返回包含 task_id 的字典"""
        ...


@runtime_checkable
class FlowAgentPollClient(Protocol):
    """Flow Agent 轮询所需的 API 客户端协议

    描述 ``FlowAgentCompletionAgent._poll_task()`` 所需的最小接口。
    被作为 pydantic 字段类型使用，需要 ``@runtime_checkable`` 以支持 ``isinstance`` 校验。
    """

    def get_flow_agent_task_info(self, task_id: str, **kwargs) -> dict:
        """获取 flow agent 任务信息"""
        ...
