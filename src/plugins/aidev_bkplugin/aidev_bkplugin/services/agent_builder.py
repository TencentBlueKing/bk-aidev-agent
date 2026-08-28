# -*- coding: utf-8 -*-
"""``ChatCompletionAgent`` 构建器。

``AgentBuilder`` 收敛 3 种构建路径（by_session_code / by_thread_id /
by_thread_id_with_chat_history），统一通过私方法 ``_build_session_agent_for_thread`` 装配
SESSION 路径，``event_handler`` / ``checkpointer`` 集中注入。
"""

from __future__ import annotations

from logging import getLogger

from aidev_agent.enums import AgentBuildType, PromptRole, SessionsStatus
from aidev_agent.packages.resource_manager.agent import AgentResourceManager
from aidev_agent.packages.resource_manager.registry import ResourceManagerProtocol
from aidev_agent.pydantic_models import AgentConfig, ChatPrompt
from aidev_agent.services.agent import AgentInstanceFactory, ChatCompletionAgent
from aidev_agent.services.common_agent import common_agent_factory
from aidev_agent.services.event_handlers import AGUISessionWriter
from django.conf import settings

from .agent_helpers import AgentHelper
from .agent_session import SessionManager

logger = getLogger(__name__)


class LLMOverrideResourceManager(AgentResourceManager):
    """带 model 热切换覆盖的 resource manager。

    在 ``get_agent_config`` 装配 ``AgentConfig`` 后，用传入的 ``model`` 覆盖 ``chat_model``，
    实现已发布智能体在聊天时动态切换模型，无需重新发布智能体。
    ``model`` 为空时不覆盖，行为与 ``AgentResourceManager`` 完全一致。
    """

    def __init__(self, username: str = "", model: str = "", *, app_code: str = "", app_secret: str = ""):
        # username/model 保持在前两位以兼容位置参数调用；凭证为 keyword-only，
        # 避免 LLMOverrideResourceManager("alice", "gpt") 被静默解读成应用凭证。
        super().__init__(app_code=app_code, app_secret=app_secret, username=username)
        self.model = model or ""

    def get_agent_config(self, agent_code: str, version: str | None = None, **kwargs) -> AgentConfig:
        config = super().get_agent_config(agent_code, version=version, **kwargs)
        if self.model:
            config.chat_model = self.model
        return config


class AgentBuilder:
    """构建 ``ChatCompletionAgent`` 的 OO 入口。

    - ``by_session_code``：直接以已有 ``session_code`` 走 SESSION 路径。
    - ``by_thread_id`` / ``by_thread_id_with_chat_history``：先 ensure session，再走 SESSION 路径。
    """

    def __init__(
        self,
        username: str = "",
        agent_code: str | None = None,
        session_manager: SessionManager | None = None,
        resource_manager: ResourceManagerProtocol | None = None,
        turn_id: str = "",
        model: str = "",
        temperature: float | None = None,
        retry_strategy: str | None = None,
    ):
        self.username = username
        self.resource_manager = resource_manager
        rm_agent_code = resource_manager.get_agent_code() if resource_manager else ""
        self.agent_code = agent_code or rm_agent_code or settings.APP_CODE
        self.session_manager = session_manager or SessionManager(
            username=username, agent_code=self.agent_code, resource_manager=self.resource_manager
        )
        self.turn_id = turn_id
        # 模型热更新：非空时覆盖 agent 配置的 chat_model
        self.model = model or ""
        self.temperature = temperature
        self.retry_strategy = retry_strategy

    def by_session_code(
        self,
        session_code: str,
        *,
        version: str | None = None,
        channel_type: str | None = None,
    ) -> ChatCompletionAgent:
        return self._build_session_agent_for_thread(session_code, version=version, channel_type=channel_type)

    def by_thread_id(
        self,
        thread_id: str,
        input_text: str,
        *,
        save_content: bool = True,
        version: str | None = None,
        channel_type: str | None = None,
    ) -> tuple[ChatCompletionAgent, str]:
        session_code = self.session_manager.get_or_create_by_thread_id(thread_id)
        if save_content and input_text:
            saved = self.session_manager.save_content(
                session_code=session_code,
                role=PromptRole.USER.value,
                content=input_text,
                turn_id=self.turn_id,
            )
            self.turn_id = (
                (saved.get("property") or {}).get("turn_id") if isinstance(saved, dict) else ""
            ) or self.turn_id
        return self._build_session_agent_for_thread(
            session_code,
            version=version,
            channel_type=channel_type,
        ), session_code

    def by_thread_id_with_chat_history(
        self,
        thread_id: str,
        chat_history: list[ChatPrompt],
        *,
        version: str | None = None,
        channel_type: str | None = None,
    ) -> tuple[ChatCompletionAgent, str]:
        session_code = self.session_manager.get_or_create_by_thread_id(thread_id)
        if chat_history and chat_history[-1].role == PromptRole.USER.value:
            # 最后一条 user 视为本轮新输入；历史消息不带 turn_id
            self.session_manager.save_chat_history(session_code, chat_history[:-1])
            last = chat_history[-1]
            saved = self.session_manager.save_content(
                session_code=session_code,
                role=last.role,
                content=last.content,
                turn_id=self.turn_id,
            )
            self.turn_id = (
                (saved.get("property") or {}).get("turn_id") if isinstance(saved, dict) else ""
            ) or self.turn_id
        else:
            self.session_manager.save_chat_history(session_code, chat_history)
        try:
            agent = self._build_session_agent_for_thread(
                session_code,
                version=version,
                channel_type=channel_type,
            )
        except Exception:
            # Agent 构建失败，尝试标记 session 为 FAILED
            try:
                self.session_manager.update_session_status(session_code, SessionsStatus.FAILED.value)
            except Exception:
                logger.exception(
                    "Failed to mark session as FAILED after agent build error: session_code=%s", session_code
                )
            raise
        return agent, session_code

    def _build_session_agent_for_thread(
        self,
        session_code: str,
        *,
        version: str | None = None,
        channel_type: str | None = None,
    ) -> ChatCompletionAgent:
        """SESSION 路径 agent 装配；client 取自注入的 ``resource_manager``，未注入时回落应用态。"""
        agent_cls = common_agent_factory.get()
        # 兜底须先于 event_handler 构造：否则 writer 拿应用态 client、agent 拿用户态 rm，同一次装配两套身份
        if not self.resource_manager and self.username:
            self.resource_manager = LLMOverrideResourceManager(username=self.username, model=self.model)
        elif self.model and isinstance(self.resource_manager, LLMOverrideResourceManager):
            # 注入的 rm 保留用户态认证，仅补上 model 覆盖能力
            self.resource_manager.model = self.model
        event_handler = AGUISessionWriter(
            session_code=session_code,
            client=AgentHelper.get_client(resource_manager=self.resource_manager),
            username=self.username,
            turn_id=self.turn_id,
        )
        return AgentInstanceFactory.build_agent(
            agent_code=self.agent_code,
            build_type=AgentBuildType.SESSION,
            session_code=session_code,
            agent_cls=agent_cls,
            checkpointer=AgentHelper.get_checkpointer(),
            event_handler=event_handler,
            resource_manager=self.resource_manager,
            username=self.username,
            version=version,
            channel_type=channel_type,
            temperature=self.temperature,
            retry_strategy=self.retry_strategy,
        )
