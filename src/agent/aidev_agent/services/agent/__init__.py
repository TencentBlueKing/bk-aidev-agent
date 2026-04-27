# -*- coding: utf-8 -*-
"""Agent 子包门面

外部统一从 ``aidev_agent.services.agent`` 导入：
- ``AgentInstanceFactory``：构建 Agent 实例的工厂入口
- ``AgentBuildContext`` / ``ChatBuildExtras`` / ``FlowBuildExtras`` / ``AgentProtocol``
  / ``agent_registry``：构建上下文、子对象、协议、注册中心
- ``ChatCompletionAgent`` / ``FlowAgentCompletionAgent``：默认 Agent 实现

新增 Agent 类型：实现 ``AgentProtocol`` 后，在本文件追加
``agent_registry.register(MyAgent.agent_type, MyAgent)``。
"""

from aidev_agent.services.agent.chat import ChatCompletionAgent
from aidev_agent.services.agent.factory import AgentInstanceFactory
from aidev_agent.services.agent.flow import FlowAgentCompletionAgent
from aidev_agent.services.agent.registry import (
    AgentBuildContext,
    AgentProtocol,
    ChatBuildExtras,
    FlowBuildExtras,
    agent_registry,
)

agent_registry.register(ChatCompletionAgent.agent_type, ChatCompletionAgent)
agent_registry.register(FlowAgentCompletionAgent.agent_type, FlowAgentCompletionAgent)

__all__ = [
    "AgentBuildContext",
    "AgentInstanceFactory",
    "AgentProtocol",
    "ChatBuildExtras",
    "ChatCompletionAgent",
    "FlowAgentCompletionAgent",
    "FlowBuildExtras",
    "agent_registry",
]
