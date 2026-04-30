# -*- coding: utf-8 -*-
"""业务级资源管理器。

对外契约（``ResourceManagerProtocol``）描述业务侧依赖的资源接口；
默认实现（``AgentResourceManager``）持有底层 ``Client`` 做 HTTP 调用，承载
``construct_tool`` / ``knowledge_query`` / flow agent 方法族 /
资源取回的 ``version`` 装参 / ``data`` 抽取等业务装配。

调用约定：
- 业务侧依赖 ``ResourceManagerProtocol`` 类型注解；通过鸭子类型实现替换 / Mock 即可，无需继承。
- 取实例：``resource_manager()``——返回当前注册器默认实现的实例（默认 ``AgentResourceManager()``）。
- 替换实现：``resource_manager.replace_defaults(MyResourceManager)``（plugin / 测试 fixture 用）。
"""

from .agent import AgentResourceManager
from .base import BaseResourceManager
from .registry import ResourceManagerProtocol, resource_manager

# wiring：把默认实现注册到工厂；放在 __init__.py 而非 registry.py，
# 让 registry.py 保持纯契约 / 不反向依赖 agent.py。
resource_manager.replace_defaults(AgentResourceManager)


__all__ = [
    "AgentResourceManager",
    "BaseResourceManager",
    "ResourceManagerProtocol",
    "resource_manager",
]
