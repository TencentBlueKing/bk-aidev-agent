import logging
from typing import Any, Callable, List, Optional, Type, cast

from ag_ui.core import BaseEvent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from aidev_agent.config import settings
from aidev_agent.enums import AgentBuildType, AgentType
from aidev_agent.packages.resource_manager.registry import resource_manager as resource_manager_factory
from aidev_agent.services.agent.registry import (
    AgentBuildContext,
    ChatBuildExtras,
    FlowBuildExtras,
    agent_registry,
)
from aidev_agent.services.common_agent import CommonQAAgent
from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager

logger = logging.getLogger("aidev-agent")


# 私有 sentinel：仅 ``build_agent`` / 内部代码（如同包测试）持有，限制外部直接 ``__init__``。
# 不在 ``__init__.py`` 门面对外重新导出；模块外不应从此处取用。
_FACTORY_TOKEN = object()


class AgentInstanceFactory:
    """Agent 实例工厂 —— 调度 + 通用预处理 + ctx 装配

    **构造约束**：仅可通过 :meth:`build_agent` 实例化。直接 ``AgentInstanceFactory(...)``
    会触发 :class:`RuntimeError`；同包内单元测试需要直接构造时，应显式传入私有
    ``_FACTORY_TOKEN``（约定的"知情人"凭证）。

    职责：
    1. 拉取 / 清洗 ``session_context_data``（含 ``_check_agent_switch`` 决定 final agent_code、
       ``_clean_last_assistant_message`` 清理 generating 占位）。
    2. 暴露 ``get_agent_config`` 配置存取出口（被 ``ChatAgentBuilder`` 等装配器使用）。
    3. 装配 ``AgentBuildContext`` 并调度 ``agent_class().build(ctx)`` 出实例。

    类型 → 实现类的映射统一由 ``aidev_agent.services.agent.registry.agent_registry`` 管理；
    各 Agent 类型自身实现 ``AgentProtocol``（``build`` 实例方法 / 种子模式 + ``execute / stop``），
    Chat 专属装配方法收敛在 ``services.agent.chat.ChatAgentBuilder``。
    """

    def __init__(
        self,
        agent_code: str,
        agent_type: AgentType = AgentType.CHAT,
        build_type: AgentBuildType = AgentBuildType.SESSION,
        session_code: Optional[str] = None,
        agent_cls: type[CommonQAAgent] | None = None,
        callbacks: List[Any] | None = None,
        auth_headers: dict[str, str] | None = None,
        temperature: float = None,
        max_tokens: int = None,
        switch_agent_by_scene: bool = False,
        config_manager_class: type[AgentConfigManager] | None = None,
        is_temporary: bool = False,
        checkpointer: BaseCheckpointSaver | None = None,
        username: str | None = None,
        version: Optional[str] = None,
        *,
        _token: object = None,
    ):
        """
        初始化Agent工厂实例（受 ``_token`` 闸口保护，外部请走 :meth:`build_agent`）

        资源管理器一律从全局 ``resource_manager`` 工厂注册器取（默认 ``AgentResourceManager``），
        plugin / 测试侧替换实现请用 ``resource_manager.replace_defaults(...)``。

        :param agent_code: Agent代码
        :param agent_type: Agent类型 ("chat", "task", "workflow"等)
        :param build_type: 构建类型 ("session", "direct")
        :param session_code: 会话代码 (build_type="session"时必需)
        :param agent_cls: Agent类
        :param callbacks: 回调函数列表
        :param temperature: 模型温度
        :param max_tokens: 模型最大回复长度
        :param switch_agent_by_scene: 是否根据场景切换智能体
        :param is_temporary: 是否为临时Agent
        :param checkpointer: Checkpoint 存储后端，用于会话状态持久化
        :param username: 用户名
        :param version: 主 agent 的配置版本；为 None 时取最新版（与历史行为一致）。
            命令切换出去的子 agent_code 各有独立版本语义，统一走最新版，不继承本字段。
        :param _token: 私有构造凭证；仅 ``build_agent`` 与同包测试持有。
        """
        if _token is not _FACTORY_TOKEN:
            raise RuntimeError(
                "AgentInstanceFactory 不可直接实例化，请通过 AgentInstanceFactory.build_agent(...) 构造。"
            )
        self.resource_manager = resource_manager_factory()
        self.agent_code = agent_code
        self.agent_type = agent_type
        self.build_type = build_type
        self.session_code = session_code
        self.agent_cls = agent_cls
        self.callbacks = [each for each in callbacks if each] if callbacks else []
        self.auth_headers = auth_headers or None
        self.temperature = temperature or None
        self.max_tokens = max_tokens or None
        self.switch_agent_by_scene = switch_agent_by_scene
        self.config_manager_class = config_manager_class or AgentConfigManager
        self.is_temporary = is_temporary
        self.checkpointer = checkpointer
        self.username = username
        self.version = version

    @classmethod
    def build_agent(
        cls,
        agent_code: str = settings.APP_CODE,
        agent_type: AgentType = AgentType.CHAT,
        build_type: AgentBuildType = AgentBuildType.SESSION,
        session_code: Optional[str] = None,
        session_context_data: Optional[List[dict]] = None,
        agent_cls: Type[CommonQAAgent] | None = CommonQAAgent,
        callbacks: List[Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = settings.MAX_TOKENS,
        switch_agent_by_scene: bool = False,
        config_manager_class: Type[AgentConfigManager] | None = AgentConfigManager,
        is_temporary: bool = False,
        event_handler: Callable[[BaseEvent], None] | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        username: str | None = None,
        version: Optional[str] = None,
        **extra: Any,
    ):
        """
        构建Agent实例

        资源管理器一律从全局 ``resource_manager`` 工厂注册器取；plugin / 测试侧替换实现请用
        ``resource_manager.replace_defaults(...)``，不再通过参数注入。

        :param agent_code: Agent代码
        :param agent_type: Agent类型 ("chat", "task", "workflow"等)
        :param build_type: 构建类型 ("session", "direct")
        :param session_code: 会话代码 (build_type="session"时必需)
        :param session_context_data: 会话上下文数据 (build_type="direct"时使用)
        :param agent_cls: Agent类
        :param callbacks: 回调函数列表
        :param temperature: 模型温度
        :param max_tokens: 模型最大回复长度
        :param switch_agent_by_scene: 是否根据场景切换智能体
        :param config_manager_class: 配置管理类
        :param is_temporary: 是否为临时Agent
        :param event_handler: 事件处理器，接收所有 AG-UI 事件（Callable[[BaseEvent], None]）
        :param checkpointer: Checkpoint 存储后端，用于会话状态持久化
        :param username: 用户名
        :param version: 主 agent 的配置版本；为 None 时取最新版（与历史行为一致）
        :param extra: 透传到 ``AgentBuildContext.extra``，由各 Agent 类的 ``build`` 自取
            （如 FlowAgent 的 ``task_id`` / ``flow_start_params`` / ``poll_interval`` /
            ``poll_timeout`` / ``flow_resource_manager`` 等）
        :return: 构建好的Agent实例
        """
        factory = cls(
            agent_code=agent_code,
            agent_type=agent_type,
            build_type=build_type,
            session_code=session_code,
            agent_cls=agent_cls,
            callbacks=callbacks,
            temperature=temperature,
            max_tokens=max_tokens,
            switch_agent_by_scene=switch_agent_by_scene,
            config_manager_class=config_manager_class,
            is_temporary=is_temporary,
            checkpointer=checkpointer or MemorySaver(),
            username=username,
            version=version,
            _token=_FACTORY_TOKEN,
        )

        factory._validate_params()

        if build_type == AgentBuildType.SESSION:
            base_args = factory._build_from_session()
        elif build_type == AgentBuildType.DIRECT:
            base_args = factory._build_direct(session_context_data or [])
        else:
            raise ValueError(f"Unsupported build_type: {build_type}")

        agent_instance = agent_registry.must_get(factory.agent_type)()
        ctx = factory._make_build_context(base_args, event_handler, extra)
        return agent_instance.build(ctx)

    def get_agent_config(self, agent_code: str) -> AgentConfig:
        """统一的 agent 配置取回出口。

        version 仅作用于主 agent；命令切换出去的子 agent_code 各有独立版本语义，
        本工厂不替它们做版本路由（一律传 None → 最新版）。
        """
        version = self.version if agent_code == self.agent_code else None
        return self.config_manager_class.get_config(agent_code=agent_code, version=version)

    # ============== 内部方法 ==============

    def _validate_params(self):
        """验证初始化参数"""
        if self.build_type == AgentBuildType.SESSION and not self.session_code:
            raise ValueError("session_code is required when build_type is 'session'")

        if self.build_type not in [AgentBuildType.SESSION, AgentBuildType.DIRECT]:
            raise ValueError(f"Unsupported build_type: {self.build_type}")

        if self.agent_type not in agent_registry:
            raise ValueError(
                f"Unsupported agent_type: {self.agent_type}. Supported types: {list(agent_registry.keys())}"
            )

    def _build_from_session(self) -> dict:
        """通过session_code构建基础参数"""
        logger.info(
            f"AgentInstanceFactory: building {self.agent_type} agent for session_code->[{self.session_code}], "
            f"agent_code->[{self.agent_code}]"
        )

        session_code = cast(str, self.session_code)
        session_context_data = self.resource_manager.get_chat_session_context(session_code) or []

        # 去掉 system prompts 在 config_manager 中处理
        session_context_data = [each for each in session_context_data if each.get("role", "") != "system"]

        base_agent_config = self.get_agent_config(self.agent_code)

        logger.info(
            f"AgentInstanceFactory: session->[{self.session_code}] "
            f"get session_context_data count->[{len(session_context_data)}]"
        )

        switch_agent, final_agent_code = self._check_agent_switch(session_context_data, base_agent_config)

        if not switch_agent and self.switch_agent_by_scene:
            switch_agent = True

        self._clean_last_assistant_message(session_context_data, base_agent_config)

        return {
            "agent_code": final_agent_code,
            "session_context_data": session_context_data,
            "switch_agent": switch_agent,
            "config_manager_class": self.config_manager_class,
        }

    def _build_direct(self, session_context_data: List[dict]) -> dict:
        """直接构建基础参数（使用提供的session_context_data）"""
        logger.info(
            f"AgentInstanceFactory: building {self.agent_type} agent directly with agent_code->[{self.agent_code}]"
        )

        return {
            "agent_code": self.agent_code,
            "session_context_data": session_context_data,
            "switch_agent": False,
            "config_manager_class": self.config_manager_class,
        }

    def _check_agent_switch(self, session_context_data: List[dict], base_agent_config: AgentConfig) -> tuple[bool, str]:
        """检查是否需要切换智能体"""
        switch_agent = False
        final_agent_code = self.agent_code

        try:
            last_user_message = (
                next(
                    (msg for msg in reversed(session_context_data) if msg["role"] == "user"),
                    None,
                )
                or {}
            )

            first_user_message = (
                next(
                    (msg for msg in session_context_data if msg["role"] == "user"),
                    None,
                )
                or {}
            )

            last_command = last_user_message.get("extra", {}).get("command")
            first_command = first_user_message.get("extra", {}).get("command")

            if last_command:
                # 若最后一条会话记录存在 Command，且该 Command 映射到了新的 Agent，
                # 那么在本轮对话中使用新的 Agent 的配置
                command_agent_code = base_agent_config.command_agent_mapping.get(last_command, self.agent_code)
            elif self.is_temporary and first_command:
                # 若该会话是临时会话，且第一条用户记录内容中存在 Command，使用该 Command 映射的 Agent 配置
                command_agent_code = base_agent_config.command_agent_mapping.get(first_command, self.agent_code)
            else:
                command_agent_code = self.agent_code

            switch_agent = command_agent_code != self.agent_code
            final_agent_code = command_agent_code

        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"AgentInstanceFactory: get last user message error->[{e}]")

        return switch_agent, final_agent_code

    def _clean_last_assistant_message(self, session_context_data: List[dict], base_agent_config):
        """清理最后一条 assistant 消息（如果包含生成中关键词）"""
        if not session_context_data:
            return

        if session_context_data[-1]["role"] != "assistant":
            return

        logger.info(
            f"AgentInstanceFactory: session->[{self.session_code}] last message is assistant, checking if should remove"
        )

        content = session_context_data[-1]["content"]

        if base_agent_config.generating_keyword not in content:
            return

        logger.info("AgentInstanceFactory: removing last assistant message with generating keyword")
        session_context_data.pop()

    def _make_build_context(
        self,
        base_args: dict,
        event_handler: Callable[[BaseEvent], None] | None,
        extra: dict[str, Any],
    ) -> AgentBuildContext:
        """根据基础参数装配 ``AgentBuildContext``

        - 主智能体配置 ``agent_config`` 在此处一次性 ``get_agent_config(final_agent_code)``
          后装入，避免下游 ``ChatAgentBuilder`` 的每个装配方法都触发 API。
        - 按 ``agent_type`` 把工厂上的专属字段打包到 ``ctx.chat`` / ``ctx.flow`` 子对象；
          flow 专属字段从 ``extra`` 中拆出（plugin 层仍通过 ``**extra`` 传入，无感）。
        """
        final_agent_code = base_args["agent_code"]

        chat_extras: ChatBuildExtras | None = None
        flow_extras: FlowBuildExtras | None = None
        agent_config: AgentConfig | None = None
        remaining_extra = dict(extra or {})

        if self.agent_type == AgentType.CHAT:
            # CHAT 路径必读主配置（下游 ChatAgentBuilder 大量依赖）
            agent_config = self.get_agent_config(final_agent_code)
            chat_extras = ChatBuildExtras(
                agent_cls=self.agent_cls,
                callbacks=list(self.callbacks),
                auth_headers=self.auth_headers,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                checkpointer=self.checkpointer,
            )
        elif self.agent_type == AgentType.FLOW:
            # FLOW 路径不依赖 agent 配置（与原行为保持一致），跳过预读
            flow_extras = FlowBuildExtras(
                flow_resource_manager=remaining_extra.pop("flow_resource_manager", None),
                poll_client=remaining_extra.pop("poll_client", None),
                task_id=remaining_extra.pop("task_id", None),
                flow_start_params=remaining_extra.pop("flow_start_params", None) or {},
                poll_interval=remaining_extra.pop("poll_interval", None),
                poll_timeout=remaining_extra.pop("poll_timeout", None),
            )

        return AgentBuildContext(
            agent_code=final_agent_code,
            agent_type=self.agent_type,
            agent_config=agent_config,
            config_manager_class=base_args.get("config_manager_class") or self.config_manager_class,
            resource_manager=self.resource_manager,
            session_code=self.session_code,
            username=self.username,
            session_context_data=base_args.get("session_context_data") or [],
            switch_agent=base_args.get("switch_agent", False),
            event_handler=event_handler,
            chat=chat_extras,
            flow=flow_extras,
            extra=remaining_extra,
        )
