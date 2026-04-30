# -*- coding: utf-8 -*-
"""``ResourceManagerProtocol``：业务侧资源接口契约。

``resource_manager``：全局 :class:`SimpleFactory` 实例工厂。
- 业务侧通过 ``resource_manager()`` 取当前默认实现的实例（无 key）；
- Plugin / 测试侧用 ``resource_manager.replace_defaults(MyImpl)`` 在进程层级整体替换，
  或 ``resource_manager.register(key, callback)`` 按 key 注册多种实现；
- 默认绑定（``AgentResourceManager``）在包 ``__init__.py`` 完成 wiring，
  避免 ``registry.py`` 反向依赖 ``agent.py``。
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from langchain_core.tools import StructuredTool

from aidev_agent.utils.factory import SimpleFactory


@runtime_checkable
class ResourceManagerProtocol(Protocol):
    """业务侧资源管理协议。

    所有方法定义业务契约（含返回结构语义），由 ``AgentResourceManager`` 提供默认实现。
    Plugin / 测试侧若要替换或 Mock，按本协议鸭子类型实现即可（不必继承）。
    """

    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict:
        """按 ID 取回知识库详情（业务返回结构 = 后端 ``data`` 字段）"""
        ...

    def retrieve_knowledge(self, id: int, **kwargs) -> dict:
        """按 ID 取回知识条目详情（业务返回结构 = 后端 ``data`` 字段）"""
        ...

    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]:
        """取回会话上下文消息列表（业务返回结构 = 后端 ``data`` 字段）"""
        ...

    def retrieve_agent_config(self, agent_code: str, version: Optional[str] = None, **kwargs) -> dict:
        """取回 agent 配置原始字典。

        :param version: 可选的 agent 配置版本；为空时由后端返回最新版本。
        """
        ...

    def retrieve_skill(self, skill_id: str, version: str, **kwargs) -> dict:
        """按 skill_id + version 取回技能详情。"""
        ...

    def construct_tool(self, tool_code: str, **kwargs) -> StructuredTool:
        """按 ``tool_code`` 装配 LangChain ``StructuredTool``（含凭证拼装）。"""
        ...

    def knowledge_query(self, data: dict[str, Any]) -> dict:
        """提交知识库查询并返回业务结果（``data`` 字段）。"""
        ...

    def start_flow_agent(self, data: dict, **kwargs) -> dict:
        """启动 flow agent 任务，返回包含 task_id 的字典。"""
        ...

    def get_flow_agent_task_info(self, task_id: str, **kwargs) -> dict:
        """获取 flow agent 任务信息。"""
        ...

    def retry_flow_agent_node(self, session_code: str, node_id: str, **kwargs) -> dict:
        """重试 flow agent 任务节点。"""
        ...

    def skip_flow_agent_node(self, session_code: str, node_id: str, **kwargs) -> dict:
        """跳过 flow agent 任务节点。"""
        ...

    def stop_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        """停止 flow agent 任务。"""
        ...

    def pause_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        """暂停 flow agent 任务。"""
        ...

    def resume_flow_agent_task(self, session_code: str, **kwargs) -> dict:
        """恢复 flow agent 任务。"""
        ...

    def get_flow_agent_task_node_info(self, task_id: str, node_id: str, **kwargs) -> dict:
        """获取 flow agent 任务节点信息。"""
        ...


resource_manager: SimpleFactory[str, ResourceManagerProtocol] = SimpleFactory("resource_manager")
