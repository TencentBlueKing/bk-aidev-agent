# -*- coding: utf-8 -*-
"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - AIDev (BlueKing - AIDev) available.
Copyright (C) 2025 THL A29 Limited,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated, Callable, List, Optional, Sequence, Tuple, get_type_hints

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
)
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import ByteStore
from langchain_core.tools import BaseTool
from langgraph.cache.base import BaseCache
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END, START
from langgraph.graph import add_messages
from langgraph.graph.state import StateGraph
from langgraph.prebuilt.tool_node import ToolCallWithContext
from langgraph.store.memory import InMemoryStore
from langgraph.types import Send
from typing_extensions import Literal, TypedDict, TypeVar

from aidev_agent.config import settings
from aidev_agent.core.graphs.react.skill_middleware import (
    SkillsPromptMiddleware,
    _extract_e2b_params,
    _extract_local_params,
    _extract_paas_params,
)
from aidev_agent.core.graphs.react.team_middleware import TeamInfo, TeamPromptMiddleware, ToolFilterMiddleware
from aidev_agent.core.nodes.knowledge import make_knowledge_node
from aidev_agent.core.nodes.model import ModelNodeSettings
from aidev_agent.core.nodes.model import build_model_node as std_make_model_node
from aidev_agent.core.nodes.pv import add_pv_info, make_pv_node
from aidev_agent.core.nodes.tool import ToolNodeSettings, build_tool_node
from aidev_agent.core.tools.a2a_tools import AgentBackendResolver, get_agent_tools
from aidev_agent.core.tools.a2a_tools import BkAiBackend as BkAiA2ABackend
from aidev_agent.core.tools.a2a_tools import LocalBackend as LocalA2ABackend
from aidev_agent.core.tools.ask_user_question import ask_user_question as _ask_user_question_tool
from aidev_agent.core.tools.knowledge import make_knowledge_retrieval_tool
from aidev_agent.core.tools.runtime_tools import get_client_tools_with_runtime
from aidev_agent.core.tools.runtime_tools.e2b_backend import E2BSandboxBackend
from aidev_agent.core.tools.runtime_tools.local_backend import FilesystemBackend
from aidev_agent.core.tools.runtime_tools.paas_backend import PaasSandboxBackend
from aidev_agent.core.tools.skill.bkai_backend import BkAiBackend
from aidev_agent.core.tools.skill.local_backend import LocalBackend as LocalSkillBackend
from aidev_agent.core.tools.skill.provider import SkillRegistry
from aidev_agent.core.tools.skill.types import SkillOptions, SkillProviderBackend
from aidev_agent.core.tools.task import TeamTaskRecord, get_task_tools
from aidev_agent.enums import Decision
from aidev_agent.packages.langchain_core.models.utils import is_model_without_function_calling
from aidev_agent.packages.langgraph.streaming.streaming_protocol import AgentStreamAdapter
from aidev_agent.pydantic_models import AgentExecutorKwargs, KnowledgeSettings, ModelContextSettings

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable
    from langgraph.store.base import BaseStore

    from aidev_agent.core.tools.a2a_tools.types import AgentSpec

ResponseT = TypeVar("ResponseT")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Runtime 参数提取函数（模块级，供 enable_runtime_* 注册到 _runtime_param_with_skill）
# ---------------------------------------------------------------------------


def _resolve_task_state_schema(schemas: List[type]) -> type:
    """通过合并多个 TypedDict schemas 来解析状态 schema。

    Args:
        schemas: 要合并的 TypedDict schemas 列表

    Returns:
        包含所有输入 schemas 字段的新 TypedDict 类
    """
    all_annotations = {}
    for schema in schemas:
        hints = get_type_hints(schema, include_extras=True)
        all_annotations.update(hints)

    return TypedDict("FinalState", all_annotations)  # type: ignore[misc]


class DefaultState(TypedDict):
    # 消息历史（包含人类消息、AI消息和工具执行结果）
    messages: Annotated[List[BaseMessage], add_messages]
    # 知识库相关数据
    decision: Decision
    knowledge_resources_highly_relevant: list
    knowledge_resources_moderately_relevant: list
    knowledge_resources_lowly_relevant: list
    reference_doc: list
    knowledge_content: list
    knowledge_qa_content: list
    with_qa_response: list
    runtime_paas_sbx_pv: Annotated[list[dict], add_pv_info]


class KnowledgeInputState(TypedDict):
    input: str
    query: str


def _send_dispatch_route(state: dict):
    """Send 分派 route：把每个 pending tool_call 派发为独立 Send task。

    过滤已产出 ToolMessage 的 tool_call（避免 resume 后重复执行），
    每个 pending tool_call 返回一个 Send("tools", ToolCallWithContext(...))。
    无 pending 时返回 END。
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        done_ids = {m.tool_call_id for m in state["messages"] if isinstance(m, ToolMessage)}
        pending = [c for c in last.tool_calls if c["id"] not in done_ids]
        if pending:
            return [
                Send(
                    "tools",
                    ToolCallWithContext(
                        __type="tool_call_with_context",
                        tool_call=c,
                        state=state,
                    ),
                )
                for c in pending
            ]
    return END


class ReActAgentBuilder:
    """LangGraph V1 QA Agent 构建器。

    支持工具调用的完整 ReAct 循环：
    - model 节点：调用 LLM 进行推理
    - tool 节点：执行工具调用
    - 条件路由：model → tool / END，tool → model
    """

    def __init__(self) -> None:
        # 模型设置
        self._llm: BaseChatModel | None = None
        self._knowledge_llm: BaseChatModel | None = None
        self._non_thinking_llm: BaseChatModel | None = None
        self._fast_llm: BaseChatModel | None = None
        self._support_vision: bool = False
        self._llm_token_limit: int = 28000
        # 对话设置
        self._suffix: str | None = None
        self._chat_history: list[BaseMessage] | None = None
        # 多智能体设置
        self._enable_a2a_tool: bool = False
        self._a2a_specs: list[AgentSpec] = []
        self._a2a_backend_types: dict[str, type] = {}  # 后端类型名称 -> 后端类
        self._a2a_resolver: AgentBackendResolver | None = None
        self._enable_team: bool = False
        self._team_config = None  # TeamConfig | None
        self._enable_task: bool = False
        # 知识库设置
        self._knowledge_items: list[dict] | None = None
        self._knowledge_bases: list[dict] | None = None
        # SKILL设置
        self._enable_skills: bool = False
        self._skill_sources: list[str | SkillProviderBackend] = []
        self._skill_registry = None
        self._runtime_param_with_skill: dict[
            str, Callable[[SkillOptions, dict], dict]
        ] = {}  # runtime_name -> param extractor (skill, config) -> dict
        # 工具设置
        self._extra_tools: list[BaseTool] = []
        self._enable_runtime_tool: bool = False
        self._runtime_backend_resolver = None
        self._enable_security_runtime: bool = True  # 默认启用安全校验
        self._enable_ask_user_question_tool: bool = True
        # Graph 运行时参数设置
        self._model_context_options: ModelContextSettings | None = None
        self._knowledge_query_options: KnowledgeSettings | None = None
        self._enable_agentic_rag_tool: bool = True
        self._executor_info: dict | None = None
        self._callbacks: list | None = None
        self._file_store: ByteStore | None = None
        self._state_schema: type[AgentState[ResponseT]] | None = None
        self._checkpointer: BaseCheckpointSaver | None = None
        self._store: "BaseStore | None" = None
        self._interrupt_before: list[str] | None = None
        self._interrupt_after: list[str] | None = None
        self._debug: bool = False
        self._name: str | None = None
        self._cache: BaseCache | None = None
        self._enable_query_clarification: Optional[bool] = None
        self._langchain_middleware: Sequence[AgentMiddleware] = ()
        self._tool_node_options: ToolNodeSettings | None = None
        self._resource_manager = None

    # ====================================================================================================
    # 模型设置
    # ====================================================================================================
    def set_llm(self, llm: BaseChatModel) -> "ReActAgentBuilder":
        self._llm = llm
        return self

    def set_knowledge_llm(self, knowledge_llm: BaseChatModel | None) -> "ReActAgentBuilder":
        self._knowledge_llm = knowledge_llm
        return self

    def set_non_thinking_llm(self, non_thinking_llm: BaseChatModel | None) -> "ReActAgentBuilder":
        self._non_thinking_llm = non_thinking_llm
        return self

    def set_support_vision(self, support_vision: bool) -> "ReActAgentBuilder":
        self._support_vision = support_vision
        return self

    def set_llm_token_limit(self, llm_token_limit: int) -> "ReActAgentBuilder":
        self._llm_token_limit = llm_token_limit
        return self

    # ====================================================================================================
    # 对话设置
    # ====================================================================================================
    def set_suffix(self, suffix: str | None) -> "ReActAgentBuilder":
        self._suffix = suffix
        return self

    def set_chat_history(self, chat_history: list[BaseMessage] | None) -> "ReActAgentBuilder":
        self._chat_history = chat_history
        return self

    # ====================================================================================================
    # 多智能体设置
    # ====================================================================================================
    def enable_a2a_tool(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用 A2A 工具用于多智能体交互。

        启用后，将根据注册的 AgentSpec 注入 A2A Agent 工具。

        Args:
            enable: True 启用（默认），False 禁用。

        Returns:
            self（支持链式调用）。
        """
        self._enable_a2a_tool = bool(enable)
        return self

    def enable_team(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用 Team 模式插件。

        注意：对于新的 AgentSpec+AgentBackend 范式，请使用 add_subagent_specs() 替代。
        此方法保留用于向后兼容，仅设置内部标志。

        Args:
            enable: True 启用（默认），False 禁用。

        Returns:
            self（支持链式调用）。
        """
        self._enable_team = bool(enable)
        # Team 模式隐式启用任务管理
        if enable:
            self._enable_task = True
        return self

    def set_team_config(self, config) -> "ReActAgentBuilder":
        """设置 Team 配置。

        Args:
            config: TeamConfig 实例（或 None 清除配置）

        Returns:
            self（支持链式调用）。
        """
        self._team_config = config
        return self

    def enable_task(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用任务管理工具。

        启用后，将注入任务工具（TaskCreate、TaskGet、TaskUpdate、TaskList）
        并将 TaskState 字段合并到状态 schema 中。

        Args:
            enable: True 启用（默认），False 禁用。

        Returns:
            self（支持链式调用）。
        """
        self._enable_task = bool(enable)
        return self

    def enable_a2a_backend_local(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用 A2A 本地后端类型（local）。

        - enable=True：注册 a2a 后端类型 ``local`` -> ``LocalA2ABackend``
        - enable=False：移除 a2a 后端类型 ``local``

        Args:
            enable: True 启用（默认），False 禁用。

        Returns:
            self（支持链式调用）。
        """
        if enable:
            self._a2a_backend_types["local"] = LocalA2ABackend
            return self

        self._a2a_backend_types.pop("local", None)
        return self

    def enable_a2a_backend_bkai(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用 A2A 蓝鲸智能体后端类型（bkai）。

        - enable=True：注册 a2a 后端类型 ``bkai`` -> ``BkAiA2ABackend``
        - enable=False：移除 a2a 后端类型 ``bkai``

        Args:
            enable: True 启用（默认），False 禁用。

        Returns:
            self（支持链式调用）。
        """
        if enable:
            self._a2a_backend_types["bkai"] = BkAiA2ABackend
            return self

        self._a2a_backend_types.pop("bkai", None)
        return self

    def add_subagent_specs(self, specs: list[AgentSpec]) -> "ReActAgentBuilder":
        """添加子 Agent 规格。

        使用 AgentSpec+AgentBackend 新范式替代旧的 enable_team() 路径。
        仅负责将 specs 添加到内部列表，后端注册和工具注入由 _prepare_a2a 在 build() 时统一处理。

        Args:
            specs: AgentSpec 列表，定义可调用的子 Agent

        Returns:
            self（支持链式调用）

        Example:
            builder.enable_a2a_backend_bkai().add_subagent_specs([
                AgentSpec(name="helper", description="...", backend_type=AgentBackendType.BKAI, params={"agent_code": "xxx"}),
                AgentSpec(name="local_worker", description="...", backend_type=AgentBackendType.LOCAL, params={"prompt_overrides": {...}}),
            ])
        """
        if not specs:
            return self

        self._a2a_specs.extend(specs)
        return self

    # ====================================================================================================
    # 知识库设置
    # ====================================================================================================
    def set_knowledge_items(self, knowledge_items: list[dict] | None) -> "ReActAgentBuilder":
        self._knowledge_items = knowledge_items
        return self

    def set_knowledge_bases(self, knowledge_bases: list[dict] | None) -> "ReActAgentBuilder":
        self._knowledge_bases = knowledge_bases
        return self

    def set_enable_query_clarification(self, enable_query_clarification: bool | None) -> "ReActAgentBuilder":
        self._enable_query_clarification = enable_query_clarification
        return self

    # ====================================================================================================
    # SKILL设置
    # ====================================================================================================
    def set_enable_skills(self, enable_skills: bool) -> "ReActAgentBuilder":
        self._enable_skills = bool(enable_skills)
        return self

    def set_skill_sources(self, skill_sources: list[str | SkillProviderBackend]) -> "ReActAgentBuilder":
        self._skill_sources = list(skill_sources)
        return self

    def add_skill_sources(self, sources: list[str | SkillProviderBackend]) -> "ReActAgentBuilder":
        self._skill_sources.extend(sources)
        return self

    # ====================================================================================================
    # 工具设置
    # ====================================================================================================
    def set_tools(self, tools: Sequence[BaseTool] | None) -> "ReActAgentBuilder":
        self._extra_tools = list(tools or [])
        return self

    def add_tools(self, tools: Sequence[BaseTool]) -> "ReActAgentBuilder":
        self._extra_tools.extend(list(tools or []))
        return self

    def set_tool_node_options(self, tool_node_options: ToolNodeSettings | None) -> "ReActAgentBuilder":
        self._tool_node_options = tool_node_options
        return self

    def set_enable_runtime_tool(self, enable_runtime_tool: bool) -> "ReActAgentBuilder":
        self._enable_runtime_tool = bool(enable_runtime_tool)
        return self

    def set_enable_ask_user_question_tool(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用 ask_user_question 工具。

        默认开启。业务侧可通过 ``builder.set_enable_ask_user_question_tool(False)``
        关闭。工具注册到 tool_node，LLM 调用时内部通过 ``interrupt()`` 暂停图执行，
        等待用户回答。
        """
        self._enable_ask_user_question_tool = bool(enable)
        return self

    def register_runtime_type(self, name: str, cls: type | None) -> "ReActAgentBuilder":
        """注册 runtime 类型名到 backend 类的映射（委托 RuntimeBackendResolver）。

        skill 的 ``runtime`` frontmatter 字段引用此处注册的类型名。类型注册表（``_backend_cls``）唯一归属 RuntimeBackendResolver
        本方法仅委托其``register_runtime_cls`` 维护，使 resolver 成为运行时类型注册+实例注册+沙箱生命周期的唯一事实源

        Args:
            name: runtime 类型名（如 ``"sandbox"``）。
            cls: 对应的 backend 类（如 ``E2BSandboxBackend``）；None 表示注销该类型名（pop 静默）

        Returns:
            self（支持链式调用）。

        Raises:
            RuntimeError: 未注入 runtime_backend_resolver（先经
                set_bkai_options/set_runtime_backend_resolver 注入）。
        """
        self._require_runtime_backend_resolver()
        self._runtime_backend_resolver.register_runtime_cls(name, cls)
        return self

    def enable_runtime_local(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用本地运行时类型（local）。

        - enable=True：注册 runtime type `local` -> `FilesystemBackend`，并注册参数提取函数
        - enable=False：移除 runtime type `local`

        Raises:
            RuntimeError: 未注入 runtime_backend_resolver（经 ``register_runtime_type``转发校验，要求 resolver 已存在）。
        """
        if enable:
            self._runtime_param_with_skill["local"] = _extract_local_params
            return self.register_runtime_type("local", FilesystemBackend)

        return self.register_runtime_type("local", None)

    def enable_runtime_agent_run(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用 agent_run 沙箱运行时类型（sandbox）。

        - enable=True：注册 runtime type `sandbox` -> `E2BSandboxBackend`，并注册参数提取函数
        - enable=False：移除 runtime type `sandbox`

        Raises:
            RuntimeError: 未注入 runtime_backend_resolver（经 ``register_runtime_type``转发校验，要求 resolver 已存在）。
        """
        if enable:
            self._runtime_param_with_skill["agent_run"] = _extract_e2b_params
            return self.register_runtime_type("agent_run", E2BSandboxBackend)

        return self.register_runtime_type("agent_run", None)

    def enable_runtime_paas(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用蓝鲸 PaaS 沙箱运行时类型（paas_sandbox）。

        - enable=True：注册 runtime type `paas_sandbox` -> `PaasSandboxBackend`，并注册参数提取函数
        - enable=False：移除 runtime type `paas_sandbox`

        Raises:
            RuntimeError: 未注入 runtime_backend_resolver（经 ``register_runtime_type``转发校验，要求 resolver 已存在）。
        """
        if enable:
            self._runtime_param_with_skill["paas_sandbox"] = _extract_paas_params
            return self.register_runtime_type("paas_sandbox", PaasSandboxBackend)

        return self.register_runtime_type("paas_sandbox", None)

    def set_runtime_backend_resolver(self, resolver) -> "ReActAgentBuilder":
        """注入 RuntimeBackendResolver（公开 setter，链式调用风格）。

        供测试与装配层注入 resolver，避免直捅私有属性。
        运行时类型注册（``register_runtime_type``/``enable_runtime_*``）要求 resolver 已存在
        须先调用本方法（或经 ``set_bkai_options`` 注入）再启用运行时类型。

        Args:
            resolver: RuntimeBackendResolver 实例。

        Returns:
            self（支持链式调用）。
        """
        self._runtime_backend_resolver = resolver
        return self

    def _require_runtime_backend_resolver(self) -> None:
        """校验已注入 runtime_backend_resolver，缺失则抛异常。

        enable_runtime_* 在 ``build()`` 前的配置期即须把 runtime 类型注册到 resolver
        因此要求 resolver 已经存在，否则抛 ``RuntimeError``
        提示先经``set_bkai_options``/``set_runtime_backend_resolver`` 注入
        """
        if self._runtime_backend_resolver is None:
            raise RuntimeError(
                "ReActAgentBuilder 启用了 runtime 注册，但未提供 runtime_backend_resolver，"
                "请先经 set_bkai_options/set_runtime_backend_resolver 注入"
            )

    def enable_security_runtime(self, enable: bool = True) -> "ReActAgentBuilder":
        """启用/禁用运行时命令安全校验。

        控制是否对 execute 工具执行的命令进行白名单校验。

        Args:
            enable: True 启用安全校验（默认），False 禁用安全校验。

        Returns:
            self（支持链式调用）。

        注意：
            - 安全校验默认启用，通过白名单机制限制可执行的命令
            - 禁用安全校验会允许执行任意命令，仅用于测试或特殊场景
        """
        self._enable_security_runtime = enable
        return self

    # ====================================================================================================
    # Graph 运行时参数设置
    # ====================================================================================================
    def set_callbacks(self, callbacks: list | None) -> "ReActAgentBuilder":
        self._callbacks = callbacks
        return self

    def set_file_store(self, file_store: ByteStore | None) -> "ReActAgentBuilder":
        self._file_store = file_store
        return self

    def set_checkpointer(self, checkpointer: BaseCheckpointSaver | None) -> "ReActAgentBuilder":
        self._checkpointer = checkpointer
        return self

    def set_store(self, store: "BaseStore | None") -> "ReActAgentBuilder":
        self._store = store
        return self

    def set_langchain_middleware(self, middleware: Sequence[AgentMiddleware]) -> "ReActAgentBuilder":
        self._langchain_middleware = middleware or ()
        return self

    def set_bkai_options(self, options: AgentExecutorKwargs) -> "ReActAgentBuilder":
        """将 BkAi 平台通用配置（AgentExecutorKwargs）映射到 builder 内部状态。"""
        if options.resource_manager is not None:
            self._resource_manager = options.resource_manager
        if options.llm is not None:
            self._llm = options.llm
        if options.non_thinking_llm is not None:
            self._non_thinking_llm = options.non_thinking_llm
        if options.fast_llm is not None:
            self._fast_llm = options.fast_llm
        if options.knowledge_llm is not None:
            self._knowledge_llm = options.knowledge_llm
        if options.extra_tools is not None:
            self._extra_tools = list(options.extra_tools)
        if options.chat_history is not None:
            self._chat_history = list(options.chat_history)
        if options.support_vision is not None:
            self._support_vision = bool(options.support_vision)
        if options.file_store is not None:
            self._file_store = options.file_store
        if options.callbacks is not None:
            self._callbacks = list(options.callbacks)
        if options.checkpointer is not None:
            self._checkpointer = options.checkpointer
        if options.executor_info is not None:
            self._executor_info = options.executor_info
        if options.knowledge_query_options is not None:
            self._knowledge_query_options = options.knowledge_query_options
            self._enable_agentic_rag_tool = options.knowledge_query_options.enable_agentic_rag_tool
        if options.model_context_options is not None:
            self._model_context_options = options.model_context_options

        # RuntimeBackendResolver（由调用方构造并注入）——必须先于 skills 块内
        # enable_runtime_paas/local（新方案下这些调用要求 resolver 已存在）
        if options.runtime_backend_resolver is not None:
            self._runtime_backend_resolver = options.runtime_backend_resolver

        # Skills（从配置链路传入的关联技能配置 list）
        # options.skills 允许混合两种元素：
        #   1. 满足 SkillProviderBackend 协议的后端实例（如 LocalSkillBackend）——直接作为 source 注册
        #   2. 平台下发的技能配置 dict ——聚合后交给 BkAiBackend 解析
        if options.skills is not None and options.skills:
            self.set_enable_skills(True)
            skill_backends: list[str | SkillProviderBackend] = [
                s for s in options.skills if isinstance(s, SkillProviderBackend)
            ]
            related_skills = [s for s in options.skills if not isinstance(s, SkillProviderBackend)]

            if skill_backends:
                self.add_skill_sources(skill_backends)
            # 仅在确有平台技能配置时构造 BkAiBackend，避免注册空后端
            if related_skills:
                # 优先使用 per-request resource_manager（含调试Agent自己的app_code / access_token），
                self.add_skill_sources(
                    [
                        BkAiBackend(
                            client=self._resource_manager,
                            related_skills=related_skills,
                        )
                    ]
                )

            self.set_enable_runtime_tool(True)
            self.enable_runtime_paas(True)
            # 存在本地技能后端时才启用 local runtime（LocalSkillBackend 的技能默认 runtime="local"）
            if any(isinstance(s, LocalSkillBackend) for s in skill_backends):
                self.enable_runtime_local(True)

        # Subagents（子 Agent 规格，注册后端 + 注入 A2A 工具）
        if options.subagent_specs is not None and options.subagent_specs:
            self.enable_a2a_tool(settings.BKAI_TOOL_A2A_ENABLED)
            self.enable_team(settings.BKAI_TOOL_TEAM_ENABLED)
            self.enable_task(settings.BKAI_TOOL_TASK_ENABLED)
            self.enable_a2a_backend_local(True).enable_a2a_backend_bkai(True)
            self.add_subagent_specs(options.subagent_specs)
            # A2A 子 Agent PV 共享需要 PaaS 沙箱 runtime 支持；
            # 仅在 A2A 工具实际启用时才开启，避免配置关闭时多余启用
            if settings.BKAI_TOOL_A2A_ENABLED:
                self.set_enable_runtime_tool(True)
                self.enable_runtime_paas(True)

        return self

    def set_state_schema(self, state_schema: type[AgentState[ResponseT]] | None) -> "ReActAgentBuilder":
        self._state_schema = state_schema
        return self

    def set_interrupt_before(self, interrupt_before: list[str] | None) -> "ReActAgentBuilder":
        self._interrupt_before = interrupt_before
        return self

    def set_interrupt_after(self, interrupt_after: list[str] | None) -> "ReActAgentBuilder":
        self._interrupt_after = interrupt_after
        return self

    def set_debug(self, debug: bool) -> "ReActAgentBuilder":
        self._debug = debug
        return self

    def set_name(self, name: str | None) -> "ReActAgentBuilder":
        self._name = name
        return self

    def set_cache(self, cache: BaseCache | None) -> "ReActAgentBuilder":
        self._cache = cache
        return self

    # ====================================================================================================
    # 预处理，将配置信息标准化处理
    # ====================================================================================================
    def _compute_use_structured_response(self) -> bool:
        """判断是否使用结构化输出模式。"""
        llm_code_agent_type = self._model_context_options.llm_code_agent_type if self._model_context_options else None
        if llm_code_agent_type:
            return bool("deepseek" in llm_code_agent_type)
        return bool(is_model_without_function_calling(self._llm) and self._extra_tools)

    def _prepare_agent_options(self):
        # knowledge_settings
        knowledge_settings = self._knowledge_query_options
        if knowledge_settings is not None and not isinstance(knowledge_settings, KnowledgeSettings):
            raise ValueError(
                "ReActAgentBuilder 构建失败：knowledge_query_options 必须为 KnowledgeSettings 类型，"
                f"实际类型为 {type(knowledge_settings).__name__}"
            )
        # 将 knowledge_bases / knowledge_items / enable_query_clarification 赋值到 knowledge_settings
        if self._knowledge_bases or self._knowledge_items or self._enable_query_clarification is not None:
            if knowledge_settings is None:
                knowledge_settings = KnowledgeSettings()
            if self._knowledge_bases:
                knowledge_settings.knowledge_bases = self._knowledge_bases
            if self._knowledge_items:
                knowledge_settings.knowledge_items = self._knowledge_items
            if self._enable_query_clarification is not None:
                knowledge_settings.enable_query_clarification = self._enable_query_clarification
        self._knowledge_query_options = knowledge_settings

        # 若配置了知识库/知识项，则需要 knowledge_llm
        # build() 入口已对 self._knowledge_llm 做回退（knowledge_llm or non_thinking_llm or llm），
        # 此处校验回退后的值是否仍为空（即三者都未配置）
        has_knowledge = bool(self._knowledge_query_options and self._knowledge_query_options.knowledge_bases) or bool(
            self._knowledge_query_options and self._knowledge_query_options.knowledge_items
        )
        if has_knowledge and self._knowledge_llm is None:
            raise ValueError("ReActAgentBuilder 构建失败：检测到知识库配置，但 knowledge_llm 为空")

        # runtime_tool 合法性校验
        if self._enable_runtime_tool and self._runtime_backend_resolver is None:
            raise ValueError(
                "ReActAgentBuilder 构建失败：启用了 runtime_tool 但未提供 runtime_backend_resolver，"
                "请通过 AgentExecutorKwargs.runtime_backend_resolver 传入"
            )

        # A2A 依赖 PaaS 沙箱：子 Agent PV 创建需要 paas_client，仅启用 A2A 而未启用
        # paas_sandbox runtime 时，paas_client 为 None，调用 Agent/sendMessages 会触发崩溃
        if self._enable_a2a_tool and not (
            self._enable_runtime_tool
            and self._runtime_backend_resolver is not None
            and self._runtime_backend_resolver.have_runtime_cls("paas_sandbox")
        ):
            raise ValueError(
                "ReActAgentBuilder 构建失败：启用了 A2A 工具但未启用 PaaS 沙箱 runtime，"
                "请同时调用 set_enable_runtime_tool(True) 和 enable_runtime_paas(True)"
            )

    def _prepare_agent_knowledge_node(
        self, *, knowledge_llm, knowledge_query_options: KnowledgeSettings | None, chat_history
    ):
        if knowledge_query_options is None:
            return None
        # 判断使用哪种 RAG 模式：未启用 enable_knowledge_node 时不构造独立节点
        if not knowledge_query_options.enable_knowledge_node:
            return None
        has_knowledge = knowledge_query_options.knowledge_bases or knowledge_query_options.knowledge_items
        if has_knowledge:
            logger.info("[ReActAgentBuilder] 两步RAG 模式已启用，使用独立的knowledge节点")
            return make_knowledge_node(
                llm=knowledge_llm,
                knowledge_query_options=knowledge_query_options,
                chat_history=chat_history,
            )
        return None

    def _prepare_agent_model_node(
        self,
        *,
        llm: BaseChatModel,
        non_thinking_llm: BaseChatModel,
        judge_llm: BaseChatModel | None,
        tools: List[BaseTool],
    ):
        """创建模型节点。

        构建 ModelNodeSettings 并创建 model_node，用于 LLM 推理。
        ModelNodeSettings 的参数从 self._model_context_options / self._knowledge_query_options 中提取。

        Args:
            llm: 语言模型
            non_thinking_llm: 非深度思考模型
            judge_llm: 判断用 LLM（quality_gate 任务完成度判断）；None 时 fail-open
            tools: 工具列表

        Returns:
            model_node: 模型节点
        """
        # 判断 use_structured_response
        node_options_kwargs = {"use_structured_response": self._compute_use_structured_response()}

        # 从 model_context_options 提取参数
        model_context_options = self._model_context_options
        if model_context_options is not None:
            if model_context_options.llm_token_limit is not None:
                node_options_kwargs["token_limit"] = model_context_options.llm_token_limit
            if model_context_options.token_limit_margin is not None:
                node_options_kwargs["token_margin"] = model_context_options.token_limit_margin
            if model_context_options.tool_output_compress_thrd is not None:
                node_options_kwargs["tool_output_compress_thrd"] = model_context_options.tool_output_compress_thrd
            if model_context_options.enable_judge_response is not None:
                node_options_kwargs["enable_judge_response"] = model_context_options.enable_judge_response

        # 从 knowledge_query_options 提取参数
        knowledge_query_options = self._knowledge_query_options
        if knowledge_query_options is not None:
            if knowledge_query_options.rejection_message is not None:
                node_options_kwargs["rejection_message"] = knowledge_query_options.rejection_message
            node_options_kwargs["use_general_knowledge_on_miss"] = (
                knowledge_query_options.is_response_when_no_knowledgebase_match
            )
            node_options_kwargs["enable_query_clarification"] = knowledge_query_options.enable_query_clarification

        node_options = ModelNodeSettings(**node_options_kwargs)

        if self._enable_skills and self._skill_registry is not None:
            node_options.extra_template_middlewares.append(
                SkillsPromptMiddleware(
                    registry=self._skill_registry,
                    enable_runtime_tool=self._enable_runtime_tool,
                )
            )

        # Team middleware registration (A2A Agent paradigm)
        if self._a2a_specs and self._a2a_resolver is not None:
            node_options.extra_template_middlewares.append(TeamPromptMiddleware(specs=self._a2a_specs))
            node_options.extra_tool_middlewares.append(ToolFilterMiddleware())

        # 创建模型节点
        model_node = std_make_model_node(
            llm=llm,
            non_thinking_llm=non_thinking_llm,
            judge_llm=judge_llm,
            tools=tools,
            node_options=node_options,
        )

        return model_node

    def _prepare_agent_tools(
        self,
        *,
        extra_tools: List[BaseTool] = None,
        ignore_errors: bool = False,
        langchain_middleware: Sequence[AgentMiddleware],
    ) -> List[BaseTool]:
        tools: List[BaseTool] = []
        # 加载所有传入的工具
        if extra_tools:
            tools.extend(extra_tools or [])
        # 加载由中间间导入的工具
        middleware_tools = [t for m in langchain_middleware for t in getattr(m, "tools", [])]
        tools.extend(middleware_tools)

        # ask_user_question 工具注入
        if self._enable_ask_user_question_tool:
            tools.append(_ask_user_question_tool)

        # 加载 SKILL 工具
        if self._enable_skills and self._skill_registry is not None:
            tools.append(self._skill_registry.get_activate_skill_tool())

        # 加载 Runtime 工具 (ls/read_file/write_file/edit_file/glob/grep/execute)
        if self._enable_runtime_tool and self._runtime_backend_resolver is not None:
            tools.extend(
                get_client_tools_with_runtime(
                    self._runtime_backend_resolver,
                    enable_security=self._enable_security_runtime,
                )
            )

        # 加载 Task 工具
        if self._enable_task:
            tools.extend(get_task_tools())

        # 加载 A2A Agent 工具
        if self._a2a_specs and self._a2a_resolver is not None:
            a2a_tools = get_agent_tools(self._a2a_specs, self._a2a_resolver)
            tools.extend(a2a_tools)

        if self._enable_agentic_rag_tool:
            # Agentic RAG模式：将知识检索作为工具
            knowledge_tool = make_knowledge_retrieval_tool(
                llm=self._knowledge_llm,
                knowledge_query_options=self._knowledge_query_options,
            )
            if knowledge_tool:
                tools.append(knowledge_tool)
                logger.info("[ReActAgentBuilder] Agentic RAG 模式已启用，知识检索工具已添加到工具列表")

        # 为所有工具添加忽略错误表示
        if ignore_errors:
            # NOTE: 在 StructuredChatAgent 中修改 tools 中的参数
            # 使得如果 LLM 调用工具时如果出现以下类型的错误，可以重新尝试，继续进行而不阻碍过程
            for i in range(len(tools)):
                tools[i].handle_validation_error = True
                tools[i].handle_tool_error = True
        return tools

    def _prepare_skills(self) -> None:
        """准备 skills 系统。

        - 初始化 SkillRegistry
        - 将 activate_skill 工具与 prompt middleware 所需的 registry 写入 self._skill_registry
        - 为每个 skill 根据其 runtime 创建并注册 backend 到 self._runtime_backend_resolver。

        所有 runtime（含 local）统一经 ``resolver.get_or_create_backend`` 获取/复用。
        模型可见路由名（runtime_name）为 ``{skill_runtime}_{skill_name}``（与 skill 提示/工具 target_runtime 一致）
        runtime_id 由 resolver 内部 ``compose_runtime_id`` 幂等推导（``{agent_code}:{session_code}:{runtime}_{skill}``）
        """
        registry = SkillRegistry(self._skill_sources or [])
        self._skill_registry = registry
        resolver = self._runtime_backend_resolver

        for skill in registry.list_skills():
            skill_name = skill["name"]
            skill_runtime = skill.get("runtime")
            logger.debug(f"ReActBuilderSkill {skill_runtime} {sorted(resolver._backend_cls) if resolver else None}")
            # 预检：runtime 类型须已注册到 resolver。resolver 为 None（未启用
            # runtime_tool 的 skills 场景）时视作无任何类型注册，跳过所有带
            # runtime 的 skill（与旧实现空 _runtime_types 的跳过语义一致）。
            if skill_runtime is None or resolver is None or not resolver.have_runtime_cls(skill_runtime):
                logger.warning(f"Skill '{skill_name}' 声明 runtime='{skill_runtime}' 但未注册对应类型，跳过该 skill")
                continue
            # 实例化独立 backend 所需构造参数
            extractor = self._runtime_param_with_skill.get(skill_runtime)
            params = extractor(skill, self._executor_info or {}) if extractor is not None else {}
            if skill_runtime == "paas_sandbox" and self._resource_manager is not None:
                client = self._resource_manager.get_paas_sbx_client(self._executor_info or {})
                params["client"] = client
            logger.info(
                f"[credential] skill_runtime={skill_runtime}, skill_name={skill_name}, "
                f"executor_info_keys={list((self._executor_info or {}).keys())}, "
                f"has_app_code={bool((self._executor_info or {}).get('app_code'))}, "
                f"has_access_token={bool((self._executor_info or {}).get('access_token'))}, "
                f"runtime_cls_name={skill_runtime}"
            )
            # 所有 runtime（含 local）统一走 get_or_create_backend：
            # runtime_name = {runtime}_{skill}（模型可见路由名，注册 _backends 供 target_runtime 解析）；
            # runtime_id 由 resolver 内部 compose_runtime_id 幂等推导（{agent_code}:{session_code}:{runtime}_{skill}），
            # resolver 内部按 runtime_cls_name 从 _backend_cls 查类构造实例。
            runtime_name = f"{skill_runtime}_{skill_name}"
            resolver.get_or_create_backend(
                runtime_name=runtime_name,
                runtime_cls_name=skill_runtime,  # resolver 内部按名查 _backend_cls
                construct_params=params,
            )

    def _prepare_a2a(self) -> None:
        """准备 A2A 多智能体系统。

        - 根据 self._a2a_backend_types 创建 AgentBackendResolver 并注册所有后端类型
        - 将 resolver 写入 self._a2a_resolver，供后续工具注入和 prompt middleware 使用
        """
        if not self._a2a_backend_types:
            return

        resolver = AgentBackendResolver()
        for backend_type_name, backend_cls in self._a2a_backend_types.items():
            resolver.register(backend_type_name, backend_cls)
        self._a2a_resolver = resolver

    def _prepare_agent_pv_node(self):
        """构造 PV Node，用于惰性创建/获取持久卷。

        仅在启用 paas_sandbox runtime 时注入真实的 BkPaaSSandboxApi client；
        否则仍返回 pv_node callable（无 PV 支持），保持图结构一致。

        Returns:
            pv_node callable
        """
        paas_client = None
        paas_app_code = ""
        if (
            self._enable_runtime_tool
            and self._runtime_backend_resolver is not None
            and self._runtime_backend_resolver.have_runtime_cls("paas_sandbox")
        ):
            executor_info = self._executor_info or {}
            paas_app_code = executor_info.get("app_code", "")
            if paas_app_code and self._resource_manager is not None:
                paas_client = self._resource_manager.get_paas_sbx_client(executor_info)
        return make_pv_node(
            client=paas_client,
            app_code=paas_app_code,
            resource_manager=self._resource_manager,
            enable_pv_by_subagent=bool(self._enable_a2a_tool),
        )

    def _prepare_agent_interrupt_node(self, *, tools: List[BaseTool]):
        """构造中断检查节点 (approval_check)。【已废弃】

        图拓扑已改为 Send 分派 + build_tool_node 内的 ITSM 审批 wrapper
        （nodes/tool/approval_wrapper.py），本方法不再被调用，保留占位
        以兼容子类重写扩展点。子类如仍需自定义中断策略，应改为在
        build_tool_node 的 wrapper 链注入自定义 strategy。

        Args:
            tools: 图绑定的工具列表（保留签名兼容子类重写）。

        Returns:
            None：本方法不再构造中断节点。
        """
        return None

    def _prepare_agent_tool_node(
        self,
        tools: List[BaseTool],
        *,
        name: str = "tools",
        tags: List[str] | None = None,
        langchain_middleware: Sequence[AgentMiddleware],
        node_options: ToolNodeSettings = None,
    ):
        middleware_w_wrap_tool_call = [
            m.wrap_tool_call
            for m in langchain_middleware
            if m.__class__.wrap_tool_call is not AgentMiddleware.wrap_tool_call
        ]
        middleware_w_awrap_tool_call = [
            m.awrap_tool_call
            for m in langchain_middleware
            if m.__class__.awrap_tool_call is not AgentMiddleware.awrap_tool_call
        ]
        if tools:
            return build_tool_node(
                tools=tools,
                name=name,
                tags=tags,
                wrappers=middleware_w_wrap_tool_call,
                async_wrappers=middleware_w_awrap_tool_call,
                node_options=node_options,
            )
        return None

    def _prepare_checkpointer(self, *, checkpointer: BaseCheckpointSaver | None = None):
        if isinstance(checkpointer, BaseCheckpointSaver):
            return checkpointer
        return MemorySaver()

    def _prepare_store(
        self,
        *,
        store: "BaseStore | None",
        file_store: Optional[ByteStore],
    ) -> "BaseStore":
        """使用 LangGraph Store 模拟 request_local.current_user_store。

        - 默认使用 InMemoryStore
        - 预先写入 file_store / image / knowledge_bases / knowledge_items / reference_doc
        """
        if store is None:
            store = InMemoryStore()
        return store

    def _prepare_state_schema(self, _TaskState: type | None = None) -> type:
        """根据 builder 内部状态构造 state_schema。

        逻辑：
        1. 收集需要合并的 schema 类列表
        2. 如果有 _TaskState 需求（enable_task / a2a_specs / enable_team），合并 TeamInfo + _TaskState
        3. 如果用户提供了 _state_schema，追加到列表末尾（而非替换）
        4. 调用 _resolve_task_state_schema 合并

        Args:
            _TaskState: 仅在 build() 中有条件定义的 _TaskState TypedDict

        Returns:
            合并后的 state_schema 类型
        """
        schemas: list[type] = [DefaultState]

        if _TaskState is not None and (self._enable_task or self._a2a_specs or self._enable_team):
            if self._a2a_specs or self._enable_team:
                schemas.append(TeamInfo)
            schemas.append(_TaskState)

        if self._state_schema is not None:
            schemas.append(self._state_schema)

        if len(schemas) == 1:
            return schemas[0]
        return _resolve_task_state_schema(schemas)

    @staticmethod
    def _should_continue(state: dict) -> Literal["pv_node", "end"]:
        """条件路由函数：决定 model 节点后的下一步。

        检查模型输出是否包含 tool_calls：
        - 如果有 tool_calls，路由到 pv_node 节点（准备 Send 分派）
        - 否则路由到 end 结束对话

        Args:
            state: 当前状态字典

        Returns:
            "pv_node" 或 "end"
        """
        messages = state.get("messages", [])
        if not messages:
            return "end"

        last_message = messages[-1]

        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "pv_node"

        return "end"

    def _build_graph(
        self,
        *,
        state_schema,
        callbacks: List,
        debug: bool,
        checkpointer,
        store,
        interrupt_before,
        interrupt_after,
        name,
        cache,
        knowledge_node,
        model_node,
        tool_node,
        pv_node=None,
        tools: "List[BaseTool] | None" = None,
    ) -> Tuple["Runnable", RunnableConfig]:
        """构建 LangGraph 图。

        图结构：
        - 无知识库配置: START → model → tools/END
        - 有知识库配置: START → knowledge → model → tools/END
        - 如果有工具: model → (条件) → pv_node / END, pv_node →(Send 分派)→ tools → model

        Args:
            state_schema: 状态模式
            callbacks: 回调列表
            debug: 是否开启调试模式
            checkpointer: 检查点
            store: 存储
            interrupt_before: 中断前节点列表
            interrupt_after: 中断后节点列表
            name: 图名称
            cache: 缓存
            knowledge_node: 知识库节点
            model_node: 模型节点
            tool_node: 工具节点
            pv_node: PV 节点 callable，由 _prepare_agent_pv_node 构造
            tools: 绑定的工具列表

        Returns:
            (CompiledGraph, RunnableConfig) 元组
        """
        graph = StateGraph(state_schema=state_schema)

        # 如果配置了知识库,添加 knowledge 节点
        if knowledge_node:
            graph.add_node("knowledge", knowledge_node)

        # 添加模型节点
        graph.add_node("model", model_node)

        # 根据是否有知识库节点,连接不同的边
        if knowledge_node:
            # 有知识库: START → knowledge → model
            graph.add_edge(START, "knowledge")
            graph.add_edge("knowledge", "model")
        else:
            # 无知识库: START → model
            graph.add_edge(START, "model")

        # 如果有工具，添加工具节点和条件路由
        if tool_node:
            graph.add_node("pv_node", pv_node)
            graph.add_node("tools", tool_node)
            # model → (should_continue) → pv_node / end
            graph.add_conditional_edges(
                "model",
                self._should_continue,
                {
                    "pv_node": "pv_node",
                    "end": END,
                },
            )
            # pv_node →(Send 分派)→ tools → model (形成 ReAct 循环)
            graph.add_conditional_edges("pv_node", _send_dispatch_route)
            graph.add_edge("tools", "model")
        else:
            # 无工具时直接结束
            graph.add_edge("model", END)

        compile_graph = graph.compile(
            checkpointer=checkpointer,
            cache=cache,
            store=store,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
            debug=debug,
            name=name,
        )

        cfg = RunnableConfig()
        cfg["configurable"] = {
            "debug": debug,
        }
        cfg["recursion_limit"] = 1000
        if callbacks:
            cfg["callbacks"] = callbacks
        compile_graph = compile_graph.with_config({"callbacks": callbacks})
        logger.info(f"react graph callbacks: {callbacks}")
        return compile_graph, cfg

    def build(self) -> Tuple["Runnable", RunnableConfig]:
        """构建并返回 compiled graph 与 runnable config。"""
        if self._llm is None:
            raise ValueError("ReActAgentBuilder 构建失败：缺少 llm，请先调用 set_llm(...) 或 set_bkai_options(...)")
        callbacks = list(self._callbacks or [])
        non_thinking_llm = self._non_thinking_llm or self._llm
        # judge_llm 回退到 non_thinking_llm / 主 llm，未配置 non_thinking_llm 时使用主 llm
        judge_llm = self._fast_llm or self._non_thinking_llm or self._llm
        # knowledge_llm 回退链：显式配置 -> non_thinking_llm -> llm
        # 模型配置集中在 build 入口，便于排查问题
        self._knowledge_llm = self._knowledge_llm or self._non_thinking_llm or self._llm

        self._prepare_agent_options()

        # Skills / runtime tools setup (must run before preparing tools)
        if self._enable_skills:
            self._prepare_skills()

        # A2A 后端注册（必须在工具注入之前执行）
        if self._enable_a2a_tool:
            self._prepare_a2a()

        # 统一处理 tools
        tool_ignore_errors = self._compute_use_structured_response()
        tools: List[BaseTool] = self._prepare_agent_tools(
            extra_tools=self._extra_tools,
            ignore_errors=tool_ignore_errors,
            langchain_middleware=self._langchain_middleware,
        )

        # 两步RAG模式：根据 enable_knowledge_node 决定是否创建独立的 knowledge_node
        knowledge_node = self._prepare_agent_knowledge_node(
            knowledge_llm=self._knowledge_llm,
            knowledge_query_options=self._knowledge_query_options,
            chat_history=self._chat_history,
        )

        # 统一处理 model_node
        model_node = self._prepare_agent_model_node(
            llm=self._llm,
            non_thinking_llm=non_thinking_llm,
            judge_llm=judge_llm,
            tools=tools,
        )

        # 构造 PV Node
        pv_node = self._prepare_agent_pv_node()

        # 统一处理 tool_node
        tool_node = self._prepare_agent_tool_node(
            tools,
            langchain_middleware=self._langchain_middleware,
            node_options=self._tool_node_options,
        )

        # 初始化 Store
        store = self._prepare_store(store=self._store, file_store=self._file_store)

        # 定义 _TaskState（如需）——仅在 task/team/a2a 分支中使用
        if self._enable_task or self._a2a_specs or self._enable_team:
            _TaskState = TypedDict("_TaskState", {"task_list": Optional[List[TeamTaskRecord]]})

        # 定制 ReAct chat prompt template
        state_schema = self._prepare_state_schema(
            _TaskState if self._enable_task or self._a2a_specs or self._enable_team else None
        )

        # 构建图
        compile_graph, cfg = self._build_graph(
            state_schema=state_schema,
            callbacks=callbacks,
            debug=self._debug,
            checkpointer=self._checkpointer,
            store=store,
            interrupt_before=self._interrupt_before,
            interrupt_after=self._interrupt_after,
            name=self._name,
            cache=self._cache,
            knowledge_node=knowledge_node,
            model_node=model_node,
            tool_node=tool_node,
            pv_node=pv_node,
            tools=tools if tools else None,
        )

        # 添加适配器
        llm_code_agent_type = self._model_context_options.llm_code_agent_type if self._model_context_options else None
        compile_graph.agent = AgentStreamAdapter(agent_type=llm_code_agent_type)
        return compile_graph, cfg
