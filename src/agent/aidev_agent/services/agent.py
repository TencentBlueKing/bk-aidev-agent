import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Type, cast

from ag_ui.core import BaseEvent
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from aidev_agent.api import BKAidevApi
from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.config import settings
from aidev_agent.enums import AgentBuildType, AgentType, PromptRole
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.langchain_core.tools import make_mcp_tools
from aidev_agent.services.chat import ChatCompletionAgent
from aidev_agent.services.common_agent import CommonQAAgent
from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager
from aidev_agent.services.pydantic_models import AgentOptions, ChatPrompt

logger = logging.getLogger("aidev-agent")


class AgentInstanceFactory:
    """
    Agent实例工厂 - 支持构建多种类型的Agent
    """

    # Agent类型映射表
    _agent_classes: Dict[AgentType, Type] = {}
    # Agent构建器注册表
    _agent_builders: Dict[AgentType, Callable] = {}

    def __init__(
        self,
        agent_code: str,
        agent_type: AgentType = AgentType.CHAT,
        build_type: AgentBuildType = AgentBuildType.SESSION,
        session_code: Optional[str] = None,
        agent_cls: type[CommonQAAgent] | None = None,
        callbacks: List[Any] | None = None,
        resource_manager: AbstractBKAidevResourceManager | None = None,
        auth_headers: Dict[str, str] | None = None,
        temperature: float = None,
        max_tokens: int = None,
        switch_agent_by_scene: bool = False,
        config_manager_class: type[AgentConfigManager] | None = None,
        is_temporary: bool = False,
        checkpointer: BaseCheckpointSaver | None = None,
        username: str | None = None,
    ):
        """
        初始化Agent工厂实例
        :param agent_code: Agent代码
        :param agent_type: Agent类型 ("chat", "task", "workflow"等)
        :param build_type: 构建类型 ("session", "direct")
        :param session_code: 会话代码 (build_type="session"时必需)
        :param agent_cls: Agent类
        :param callbacks: 回调函数列表
        :param resource_manager:  bkaidev 资源管理
        :param temperature: 模型温度
        :param max_tokens: 模型最大回复长度
        :param switch_agent_by_scene: 是否根据场景切换智能体
        :param is_temporary: 是否为临时Agent
        :param checkpointer: Checkpoint 存储后端，用于会话状态持久化
        :param username: 用户名
        """
        self.resource_manager = resource_manager or BKAidevApi.get_client()
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
        self._specific_resources: list[dict] = []

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
        resource_manager: AbstractBKAidevResourceManager | None = None,
        temperature: float | None = None,
        max_tokens: int | None = settings.MAX_TOKENS,
        switch_agent_by_scene: bool = False,
        config_manager_class: Type[AgentConfigManager] | None = AgentConfigManager,
        is_temporary: bool = False,
        event_handler: Callable[[BaseEvent], None] | None = None,
        checkpointer: BaseCheckpointSaver | None = None,
        username: str | None = None,
    ):
        """
        构建Agent实例
        :param agent_code: Agent代码
        :param agent_type: Agent类型 ("chat", "task", "workflow"等)
        :param build_type: 构建类型 ("session", "direct")
        :param session_code: 会话代码 (build_type="session"时必需)
        :param session_context_data: 会话上下文数据 (build_type="direct"时使用)
        :param agent_cls: Agent类
        :param callbacks: 回调函数列表
        :param resource_manager: 资源管理类
        :param temperature: 模型温度
        :param max_tokens: 模型最大回复长度
        :param switch_agent_by_scene: 是否根据场景切换智能体
        :param config_manager_class: 配置管理类
        :param is_temporary: 是否为临时Agent
        :param event_handler: 事件处理器，接收所有 AG-UI 事件（Callable[[BaseEvent], None]）
        :param checkpointer: Checkpoint 存储后端，用于会话状态持久化
        :param username: 用户名
        :return: 构建好的Agent实例
        """
        # 创建工厂实例
        factory = cls(
            agent_code=agent_code,
            agent_type=agent_type,
            build_type=build_type,
            session_code=session_code,
            agent_cls=agent_cls,
            callbacks=callbacks,
            resource_manager=resource_manager,
            temperature=temperature,
            max_tokens=max_tokens,
            switch_agent_by_scene=switch_agent_by_scene,
            config_manager_class=config_manager_class,
            is_temporary=is_temporary,
            checkpointer=checkpointer or MemorySaver(),
            username=username,
        )

        # 验证参数
        factory._validate_params()

        # 构建基础参数
        if build_type == AgentBuildType.SESSION:
            base_args = factory._build_from_session()
        elif build_type == AgentBuildType.DIRECT:
            base_args = factory._build_direct(session_context_data or [])
        else:
            raise ValueError(f"Unsupported build_type: {build_type}")

        # 根据agent_type构建特定参数
        agent_args = factory._build_agent_args(base_args)

        # 设置事件处理器
        if event_handler is not None:
            agent_args["event_handler"] = event_handler

        # 创建Agent实例
        return factory._create_agent_instance(agent_args)

    def _validate_params(self):
        """验证初始化参数"""
        if self.build_type == AgentBuildType.SESSION and not self.session_code:
            raise ValueError("session_code is required when build_type is 'session'")

        if self.build_type not in [AgentBuildType.SESSION, AgentBuildType.DIRECT]:
            raise ValueError(f"Unsupported build_type: {self.build_type}")

        if self.agent_type not in self._agent_builders:
            raise ValueError(
                f"Unsupported agent_type: {self.agent_type}. Supported types: {list(self._agent_builders.keys())}"
            )

    def _build_agent_args(self, base_args: dict) -> dict:
        """
        构建Agent特定参数
        取决于Agent类别
        """
        builder = self._agent_builders[self.agent_type]
        agent_specific_args = builder(self, **base_args)

        # 合并通用参数
        final_args = {
            "agent_cls": self.agent_cls,
            "callbacks": self.callbacks,
            "run_by_agent": True,
            **agent_specific_args,
        }

        return final_args

    def _create_agent_instance(self, agent_args: dict):
        """创建Agent实例"""
        agent_class = self._agent_classes[self.agent_type]
        return agent_class(**agent_args)

    def _build_from_session(self) -> dict:
        """通过session_code构建基础参数"""
        logger.info(
            f"AgentInstanceFactory: building {self.agent_type} agent for session_code->[{self.session_code}], "
            f"agent_code->[{self.agent_code}]"
        )

        # 获取会话上下文数据
        session_code = cast(str, self.session_code)
        session_context_data = self.resource_manager.get_chat_session_context(session_code) or []

        # 去掉 system prompts 在config_manager中处理
        session_context_data = [each for each in session_context_data if each.get("role", "") != "system"]

        base_agent_config = self.config_manager_class.get_config(
            agent_code=self.agent_code, resource_manager=self.resource_manager
        )

        logger.info(
            f"AgentInstanceFactory: session->[{self.session_code}] "
            f"get session_context_data count->[{len(session_context_data)}]"
        )

        # 检查是否需要切换智能体
        switch_agent, final_agent_code = self._check_agent_switch(session_context_data, base_agent_config)

        if not switch_agent and self.switch_agent_by_scene:
            switch_agent = True

        # 处理最后一条assistant消息
        self._clean_last_assistant_message(session_context_data, base_agent_config)

        # 处理最后一条human消息,判断有无resources
        self._handle_last_human_message(session_context_data)

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

    def _handle_last_human_message(self, session_context_data: List[dict]):
        """处理最后一条human消息,判断有resources"""
        if not session_context_data:
            return

        for item in reversed(session_context_data):
            logger.info(
                f"AgentInstanceFactory: handling last human message with resources in session_context_data->[{item}]"
            )
            if item.get("role") == PromptRole.USER.value:
                if item.get("extra", {}).get("resources"):
                    self._specific_resources = item.get("extra", {}).get("resources")
                break

    # ============== 通用构建方法 ==============

    def build_chat_model(self, agent_code: str):
        """构建聊天模型"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)

        if not config.chat_model:
            raise ValueError("请配置智能体默认模型并重新发布")

        # Prepare kwargs for ChatModel.get_setup_instance
        kwargs = {
            "model": config.chat_model,
            "base_url": settings.LLM_GW_ENDPOINT,
        }

        # 优先使用工厂传入的参数，否则使用配置中的参数
        temperature = self.temperature if self.temperature is not None else config.temperature
        if temperature is not None:
            kwargs["temperature"] = temperature

        max_tokens = self.max_tokens if self.max_tokens is not None else config.max_tokens
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        # Only add auth_headers if it has a value
        if self.auth_headers:
            kwargs["auth_headers"] = self.auth_headers

        return ChatModel.get_setup_instance(**kwargs)

    def build_chat_history(
        self, session_context_data: List[dict], agent_code: Optional[str] = None
    ) -> List[ChatPrompt]:
        """构建聊天历史"""

        # 添加系统历史
        config = self.config_manager_class.get_config(
            agent_code=agent_code or self.agent_code,
            resource_manager=self.resource_manager,
        )
        role_history = (
            [
                ChatPrompt(role=each["role"].replace("hidden-", ""), content=each["content"])
                for each in config.role_prompts
                if each.get("role") in ["user", "assistant", "hidden-user", "hidden-assistant", "hidden-system"]
            ]
            if config.role_prompts
            else []
        )

        chat_history = [
            ChatPrompt.model_validate(each)
            for each in (session_context_data or [])
            if each.get("content") and each["role"] != "system"
        ]
        for each in chat_history:
            if each.role != "assistant":
                continue
            each.content = _remove_think(each.content)

        # 过滤没有匹配工具结果的 assistant 消息
        chat_history = self._filter_unmatched_tool_calls(chat_history)

        self._modify_last_system_message(chat_history, agent_code or self.agent_code)
        chat_history = role_history + chat_history
        return chat_history

    def build_non_thinking_llm(self, agent_code: str) -> str | None:
        """构建非思考模型"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return config.non_thinking_llm

    def build_knowledge_bases(self, agent_code: str) -> List[dict]:
        """构建知识库"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        specific_resources = [
            each.get("id") for each in self._specific_resources if each.get("type") == "knowledgebase"
        ]
        if specific_resources:
            knowledgebase_ids = [
                each for each in config.knowledgebase_ids if specific_resources and each in specific_resources
            ]
        else:
            knowledgebase_ids = config.knowledgebase_ids
        logger.info(
            f"AgentInstanceFactory: config knowledgebase_ids->[{config.knowledgebase_ids}], specific_resources->[{specific_resources}]"
        )
        return [self.resource_manager.retrieve_knowledgebase(_id) for _id in knowledgebase_ids]

    def build_knowledge_items(self, agent_code: str) -> List[dict]:
        """构建知识条目"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return [self.resource_manager.retrieve_knowledge(_id) for _id in config.knowledge_ids]

    def build_tools(self, agent_code: str) -> List[Any]:
        """构建工具"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        specific_mcps = [each.get("code") for each in self._specific_resources if each.get("type") == "mcp"]
        if specific_mcps:
            mcp_server_config = {each: config.mcp_server_config.get(each) for each in specific_mcps}
        else:
            mcp_server_config = config.mcp_server_config
        mcp_result = make_mcp_tools(mcp_server_config, config.agent_options, username=self.username)
        self._mcp_fetch_failures = [f.model_dump() for f in mcp_result.fetch_failures]
        logger.info(f"AgentInstanceFactory: mcp_server_config->[{mcp_server_config}]")
        specific_tools = [each.get("code") for each in self._specific_resources if each.get("type") == "tool"]
        if specific_tools:
            tool_codes = [each for each in config.tool_codes if each in specific_tools]
        else:
            tool_codes = config.tool_codes
        logger.info(f"AgentInstanceFactory: tool_codes->[{tool_codes}]")
        return [self.resource_manager.construct_tool(tool_code) for tool_code in tool_codes] + mcp_result.tools

    def get_role_prompt(self, agent_code: str) -> str | None:
        """获取角色提示词"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return config.role_prompts[0]["content"] if config.role_prompts else None

    def build_agent_options(self, agent_code: str) -> AgentOptions:
        """构建Agent选项"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return config.agent_options

    def build_agent_prompt(self, agent_code: str) -> str | None:
        """构建Agent提示词"""
        config = self.config_manager_class.get_config(agent_code=agent_code, resource_manager=self.resource_manager)
        return config.agent_prompt

    def build_checkpointer(self) -> BaseCheckpointSaver:
        """获取 Checkpointer，必须注入，否则抛出异常"""
        if self.checkpointer is not None:
            return self.checkpointer
        raise ValueError("Checkpointer is required but not provided. Please inject a valid checkpointer.")

    def handle_agent_switch(self, session_context_data: List[dict], agent_code: str, switch_agent: bool):
        """处理智能体切换"""
        if not switch_agent:
            return

        logger.info(f"AgentInstanceFactory: switching agent to->[{agent_code}]")
        # 找到最后一条role为system的记录并修改
        for item in reversed(session_context_data):
            if item["role"] == "system":
                item["content"] = self.get_role_prompt(agent_code)
                break

    def _check_agent_switch(self, session_context_data: List[dict], base_agent_config: AgentConfig) -> tuple[bool, str]:
        """检查是否需要切换智能体"""
        switch_agent = False
        final_agent_code = self.agent_code

        try:
            # 获取最后一条用户消息
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

            if (
                last_command
            ):  # 若最后一条会话记录存在Command，且该Command映射到了新的Agent,那么在本轮对话中使用新的Agent的配置
                command_agent_code = base_agent_config.command_agent_mapping.get(last_command, self.agent_code)
            elif (
                self.is_temporary and first_command
            ):  # 若该会话是临时会话,且第一条用户记录内容中存在Command,使用该Command映射的Agent配置
                command_agent_code = base_agent_config.command_agent_mapping.get(first_command, self.agent_code)
            else:
                command_agent_code = self.agent_code

            switch_agent = command_agent_code != self.agent_code
            final_agent_code = command_agent_code  # 切换Agent

        except Exception as e:  # pylint: disable=broad-except
            logger.warning(f"AgentInstanceFactory: get last user message error->[{e}]")

        return switch_agent, final_agent_code

    def _clean_last_assistant_message(self, session_context_data: List[dict], base_agent_config):
        """清理最后一条assistant消息（如果包含生成中关键词）"""
        # 卫语句：如果没有消息数据，直接返回
        if not session_context_data:
            return

        # 卫语句：如果最后一条消息不是assistant，直接返回
        if session_context_data[-1]["role"] != "assistant":
            return

        logger.info(
            f"AgentInstanceFactory: session->[{self.session_code}] last message is assistant, checking if should remove"
        )

        content = session_context_data[-1]["content"]

        # 卫语句：如果content中没有生成中关键词，直接返回
        if base_agent_config.generating_keyword not in content:
            return

        logger.info("AgentInstanceFactory: removing last assistant message with generating keyword")
        session_context_data.pop()

    def _filter_unmatched_tool_calls(self, chat_history: List[ChatPrompt]) -> List[ChatPrompt]:
        """过滤没有匹配工具结果的 assistant 消息

        当 assistant 消息包含 tool_calls 但没有对应的 tool 结果消息时，
        该 assistant 消息会导致模型调用失败（模型期望每个 tool_use 都有对应的 tool_result）。

        Args:
            chat_history: 聊天历史列表

        Returns:
            过滤后的聊天历史列表，移除了不完整的工具调用链
        """
        if not chat_history:
            return chat_history

        # 收集所有 tool 消息的 tool_call_id
        tool_result_ids: set[str] = set()
        for prompt in chat_history:
            if prompt.role == "tool":
                tool_call_id = prompt.builtin_property.get("tool_call_id", "")
                if tool_call_id:
                    tool_result_ids.add(tool_call_id)

        # 过滤 assistant 消息中未匹配的 tool_calls
        # 如果所有 tool_calls 都没有结果，则过滤整个 assistant 消息
        # 如果部分 tool_calls 有结果，则只移除没有结果的 tool_calls
        filtered_history: List[ChatPrompt] = []
        for prompt in chat_history:
            if prompt.role != "assistant":
                filtered_history.append(prompt)
                continue

            # 提取 assistant 消息中的 tool_calls
            tool_calls = self._extract_tool_calls_from_prompt(prompt)

            if not tool_calls:
                # 没有 tool_calls 的 assistant 消息，直接保留
                filtered_history.append(prompt)
                continue

            # 分离匹配和未匹配的 tool_calls
            matched_calls = [tc for tc in tool_calls if tc.get("id", "") in tool_result_ids]
            unmatched_calls = [tc for tc in tool_calls if tc.get("id", "") not in tool_result_ids]

            if not matched_calls:
                # 所有工具调用都没有结果，移除整个消息
                logger.info(
                    f"AgentInstanceFactory: filtering assistant message with no matched tool_calls, "
                    f"message_id=[{prompt.id}], tool_calls_count=[{len(tool_calls)}]"
                )
                continue

            if unmatched_calls:
                # 部分工具调用有结果，保留消息但移除未匹配的 tool_calls
                logger.info(
                    f"AgentInstanceFactory: removing unmatched tool_calls from assistant message, "
                    f"message_id=[{prompt.id}], total_calls=[{len(tool_calls)}], "
                    f"matched=[{len(matched_calls)}], unmatched=[{len(unmatched_calls)}]"
                )
                # 更新 builtin_property 中的 tool_calls，只保留匹配的
                self._update_tool_calls_in_prompt(prompt, matched_calls)

            # 保留该 assistant 消息
            filtered_history.append(prompt)

        return filtered_history

    def _extract_tool_calls_from_prompt(self, prompt: ChatPrompt) -> List[dict]:
        """从 ChatPrompt 中提取 tool_calls 列表

        Args:
            prompt: ChatPrompt 对象

        Returns:
            tool_calls 列表，每个元素包含 id, name, args 字段
        """
        builtin_property = prompt.builtin_property or {}
        tool_calls_raw = builtin_property.get("tool_calls", [])

        if not tool_calls_raw:
            return []

        tool_calls = []
        for tc in tool_calls_raw:
            # arguments 在数据库中存储为 JSON 字符串，需要解析为字典
            args_str = tc.get("function", {}).get("arguments", "{}")
            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}

            tool_calls.append(
                {
                    "id": tc.get("id", ""),
                    "name": tc.get("function", {}).get("name", ""),
                    "args": args,
                    "type": "tool_call",
                }
            )

        return tool_calls

    def _update_tool_calls_in_prompt(self, prompt: ChatPrompt, matched_tool_calls: List[dict]) -> None:
        """更新 ChatPrompt 中的 tool_calls，只保留匹配的调用

        Args:
            prompt: ChatPrompt 对象
            matched_tool_calls: 匹配的 tool_calls 列表（来自 _extract_tool_calls_from_prompt 的格式）
        """
        builtin_property = prompt.builtin_property or {}
        tool_calls_raw = builtin_property.get("tool_calls", [])

        # 获取匹配的 tool_call id 集合
        matched_ids = {tc.get("id", "") for tc in matched_tool_calls}

        # 从原始 tool_calls 中过滤出匹配的项
        filtered_tool_calls = [tc for tc in tool_calls_raw if tc.get("id", "") in matched_ids]

        # 更新 builtin_property
        if builtin_property:
            builtin_property["tool_calls"] = filtered_tool_calls
        else:
            prompt.builtin_property = {"tool_calls": filtered_tool_calls}

    def _modify_last_system_message(self, chat_history: List[ChatPrompt], agent_code: Optional[str]) -> None:
        if not agent_code:
            return

        role_prompt = self.get_role_prompt(agent_code)
        if not role_prompt:
            return

        for prompt in reversed(chat_history):
            if prompt.role == "system":
                prompt.content = role_prompt
                break

    @classmethod
    def register_agent_type(
        cls,
        agent_type: AgentType,
        agent_class: Type,
        builder_func: Callable,
        override=False,
    ):
        """注册新的Agent类型"""
        if not override and agent_type in cls._agent_classes:
            raise ValueError(f"Agent type '{agent_type}' already exists")
        cls._agent_classes[agent_type] = agent_class
        cls._agent_builders[agent_type] = builder_func
        logger.info(f"AgentInstanceFactory: registered agent type->[{agent_type}] with class->[{agent_class.__name__}]")

    # ============== Agent构建器函数 ==============

    @staticmethod
    def build_chat_agent_args(
        factory: "AgentInstanceFactory",
        agent_code: str,
        session_context_data: List[dict],
        switch_agent: bool,
        config_manager_class: type[AgentConfigManager] | None = None,
    ):
        """构建ChatCompletionAgent参数"""
        logger.info(f"Building ChatCompletionAgent args with agent_code->[{agent_code}]")

        if switch_agent:
            factory.config_manager_class = config_manager_class

        # 处理智能体切换
        factory.handle_agent_switch(session_context_data, agent_code, switch_agent)

        tools = factory.build_tools(agent_code)
        mcp_fetch_failures = getattr(factory, "_mcp_fetch_failures", [])
        chat_agent_args = {
            "chat_model": factory.build_chat_model(agent_code),
            "non_thinking_llm": factory.build_non_thinking_llm(agent_code),
            "tools": tools,
            "mcp_fetch_failures": mcp_fetch_failures,
            "knowledge_bases": factory.build_knowledge_bases(agent_code),
            "knowledge_items": factory.build_knowledge_items(agent_code),
            "chat_history": factory.build_chat_history(session_context_data, agent_code),
            "agent_options": factory.build_agent_options(agent_code),
            "agent_prompt": factory.build_agent_prompt(agent_code),
            "checkpointer": factory.build_checkpointer(),
            "role_prompt": factory.get_role_prompt(agent_code),
        }
        if factory.session_code is not None:
            chat_agent_args["thread_id"] = factory.session_code
        return chat_agent_args

    @staticmethod
    def build_task_agent_args(
        factory,
        agent_code,
        session_context_data,
        switch_agent,
        config_manager_class: type[AgentConfigManager] | None = None,
    ):
        """构建TaskAgent参数（示例）"""
        # 处理智能体切换
        factory.handle_agent_switch(session_context_data, agent_code, switch_agent)
        if switch_agent:
            factory.config_manager_class = config_manager_class

        # TaskAgent可能需要不同的参数组合
        return {
            "task_config": factory.get_role_prompt(agent_code),
            "tools": factory.build_tools(agent_code),
            "chat_history": factory.build_chat_history(session_context_data, agent_code),
            # 可能不需要knowledge_bases等
        }


# 注册默认的Agent类型
AgentInstanceFactory.register_agent_type(
    agent_type=AgentType.CHAT,
    agent_class=ChatCompletionAgent,
    builder_func=AgentInstanceFactory.build_chat_agent_args,
)


def _remove_think(content: str) -> str:
    """移除HTML中的思考部分内容
    Args:
        content: 包含思考内容的HTML字符串
    Returns:
        清理后的内容字符串
    """
    # 第一步：移除思考头部（使用DOTALL模式匹配多行内容）
    _content = re.sub(
        r'<section class="think-head click-close">[\s\S]*?</section>',
        "",
        content,
        flags=re.DOTALL,
    )

    _content = re.sub(
        r'<section class="think-head click-close closed">[\s\S]*?</section>',
        "",
        _content,
        flags=re.DOTALL,
    )

    # 第二步：移除思考主体部分
    _content = re.sub(r'<section class="think-body">[\s\S]*?</section>', "", _content, flags=re.DOTALL)

    # 第三步：如果内容为空则尝试提取思考主体内容
    if not _content.strip():
        # 使用search而非match来查找任意位置的匹配
        think_body_match = re.search(r'<section class="think-body">([\s\S]*?)</section>', content, re.DOTALL)
        if think_body_match:
            # 使用group(1)获取第一个捕获组的内容
            _content = think_body_match.group(1).strip()

    return _content.strip()
