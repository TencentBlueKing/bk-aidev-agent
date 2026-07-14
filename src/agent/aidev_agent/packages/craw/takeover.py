# -*- coding: utf-8 -*-
"""``enable_chat_takeover()``：env 门控地让 craw 接管 ``AgentType.CHAT``。

机制与既有插件的 registry 覆盖先例一致：在 ``agent_registry`` 层整体
替换（craw 内核自身就是完整 agent——会话循环 / 工具编排都在 craw 侧，
不能再被 LangGraph ReAct 套一层）。

门控（``BKAI_CRAW_BACKEND``，未设 = 零影响保持原生 ReAct）：
- ``openclaw`` / ``hermes`` / 其他已注册内核名 → ``CrawCompletionAgent``
  接管 CHAT，连接参数由对应后端的 env 回落链装配；
- 未注册的值 → 记 warning，保持原生（接管失败不拖垮宿主启动）。

宿主接入：在插件 / 应用启动路径（如 Django ``AppConfig.ready`` 或
``extend/agent.py`` 末尾）调用一次::

    from aidev_agent.packages.craw import enable_chat_takeover
    enable_chat_takeover()
"""

from __future__ import annotations

import os
from logging import getLogger

from aidev_agent.packages.craw.registry import BACKEND_ENV, craw_backend_registry

logger = getLogger(__name__)


def enable_chat_takeover() -> bool:
    """按 env ``BKAI_CRAW_BACKEND`` 接管 ``AgentType.CHAT``。

    :return: 是否完成接管。env 未设 / 内核未注册 / 接管异常均返回 ``False``
        并保持原生 ``ChatCompletionAgent``（可逆、失败降级）。
    """
    name = (os.getenv(BACKEND_ENV) or "").strip().lower()
    if not name:
        return False
    if name not in craw_backend_registry:
        logger.warning("[CRAW] 未注册的 %s=%r（已注册: %s），保持原生 CHAT agent", BACKEND_ENV, name, list(craw_backend_registry.keys()))
        return False
    try:
        from aidev_agent.enums import AgentType
        from aidev_agent.packages.craw.agent import CrawCompletionAgent
        from aidev_agent.packages.craw.registry import get_backend
        from aidev_agent.services.agent.registry import agent_registry

        backend = get_backend(name)  # 提前装配一次，暴露连接参数问题
        agent_registry.remove(AgentType.CHAT)
        agent_registry.register(AgentType.CHAT, CrawCompletionAgent, priority=100)
        logger.warning(
            "[CRAW] CrawCompletionAgent 已接管 AgentType.CHAT（backend=%s, api_url=%s, model=%s）",
            backend.name,
            backend.api_url,
            backend.model,
        )
        return True
    except Exception as exc:  # 接管失败不应拖垮宿主启动，降级回原生
        logger.exception("[CRAW] 接管 CHAT 失败，保持原生 ChatCompletionAgent: %s", exc)
        return False
