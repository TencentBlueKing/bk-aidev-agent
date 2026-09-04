import asyncio
import json
import os
import posixpath
import uuid
import warnings
from functools import partial
from importlib.metadata import version as pkg_version
from logging import getLogger
from typing import Any, Callable, ClassVar, Generator, List, Optional

from ag_ui.core import BaseEvent, CustomEvent, EventType
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables.fallbacks import RunnableWithFallbacks
from langchain_core.stores import ByteStore
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from aidev_agent.api.bk_agent import BkAgentApi
from aidev_agent.config import settings
from aidev_agent.core.ag_ui.aidev_agent import ASK_USER_QUESTION_TOOL_NAME, AidevAGUIAgent
from aidev_agent.core.ag_ui.events import ExtendToolCallResultEvent
from aidev_agent.core.ag_ui.types import (
    AgentInput,
    ExtendMessage,
    ReasoningLangChainMessage,
    SchemaKeys,
    SessionPersistenceEventNames,
)
from aidev_agent.core.ag_ui.utils import (
    contents_to_agui_messages,
    get_schema_keys,
    get_stream_payload_input,
)
from aidev_agent.core.nodes.model import convert_chat_history_to_messages
from aidev_agent.core.tools.a2a_tools.types import AgentBackendType, AgentSpec
from aidev_agent.core.tools.runtime_tools import RuntimeBackendResolver
from aidev_agent.core.tools.runtime_tools.defer_manager import default_runtime_backend_defer_manager
from aidev_agent.enums import AgentType, PromptRole
from aidev_agent.exceptions import AgentDeadlineExceededError, AgentException
from aidev_agent.packages.interrupt_manager import (
    ASK_USER_QUESTION_SKIPPED_CONTENT,
    ApprovalHandler,
    AskUserQuestionHandler,
    InterruptReason,
    InterruptStatus,
    ItsmTicketCreator,
)
from aidev_agent.packages.interrupt_manager.processor import InterruptProcessor
from aidev_agent.packages.interrupt_manager.types import ProcessorContext
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel, ChatModelRunnable
from aidev_agent.packages.langgraph.streaming.streaming_protocol import AgentStreamAdapter
from aidev_agent.packages.resource_manager.registry import resource_manager
from aidev_agent.pydantic_models import (
    AgentOptions,
    ChatPrompt,
    ExecuteKwargs,
    KnowledgeSettings,
    ModelContextSettings,
)
from aidev_agent.services.agent.artifacts import build_artifacts_generated_hook
from aidev_agent.services.agent.registry import AgentBuildContext, ChatBuildExtras
from aidev_agent.services.common_agent import CommonAgentProtocol, CommonQAAgent
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.sandbox_pv_files import (
    IMAGE_DOWNLOAD_URL_EXPIRES_IN,
    SESSION_UPLOAD_IMAGE_EXTENSIONS,
    SESSION_VOLUME_PATH,
    SandboxFileInvalidArgumentError,
    SandboxFileServerError,
    SandboxPvFileService,
)
from aidev_agent.utils.async_utils import async_to_sync_generator
from aidev_agent.utils.loop import run_coro_sync
from aidev_agent.utils.migrations import (
    migration_chat_model_non_thinking_from_non_thinking_llm_v1,
    migration_knowledge_query_options_from_agent_options_v1,
    migration_model_context_options_from_agent_options_v1,
)

try:
    from aidev_agent.packages.opentelemetry.resilience import record_operation_timeout
except ImportError:  # OpenTelemetry is an optional SDK extra.
    record_operation_timeout = None

logger = getLogger(__name__)


def _to_ledger_dict(record: Any) -> dict:
    """把 chat_history 账本记录归一为 dict 形态。

    账本记录以 ChatPrompt 对象为主（build 期 model_validate 承接 + 本轮 patch append）；
    快照转换器（contents_to_agui_messages）按 dict 消费，这里统一把 ChatPrompt 对象
    model_dump 为 dict（role/content 顶层、status/created_at 透传顶层、builtin_property/extra 保留）。
    """
    if isinstance(record, dict):
        return record
    if hasattr(record, "model_dump"):
        return record.model_dump()
    return dict(record)


class ChatCompletionAgent(BaseModel):
    """聊天 Agent"""

    agent_type: ClassVar[AgentType] = AgentType.CHAT

    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_model: ChatModelRunnable | None = None
    """聊天模型；种子实例（``ChatCompletionAgent()``）为 ``None``，``build(ctx)``
    装配后由 :meth:`ChatAgentBuilder.build_chat_model` 填充为非空聊天模型 Runnable。
    种子实例不可执行（``execute()`` 假设非空）。"""
    chat_model_non_thinking: BaseChatModel | None = None
    """非思考模型；由 :meth:`ChatAgentBuilder.build_chat_model_non_thinking` 填充。"""
    chat_model_fast: BaseChatModel | None = None
    """快速/轻量模型；由 :meth:`ChatAgentBuilder.build_chat_model_fast` 填充。
    用于 quality_gate 判断 LLM 等辅助任务。"""
    non_thinking_llm: str | None = Field(default=None, deprecated="使用 chat_model_non_thinking 替代")
    chat_history: list[ChatPrompt] | None = None
    file_resources: list[dict] = Field(default_factory=list, exclude=True)
    files: list[dict] = Field(default_factory=list)
    tools: Optional[list[StructuredTool]] = None
    skills: Optional[list] = None
    subagent_specs: Optional[list[Any]] = None  # 实际类型为 list[AgentSpec]，使用 Any 避免 services→tools 依赖方向违规
    executor_info: Optional[dict] = None
    knowledge_bases: Optional[list[dict]] = None
    knowledges: Optional[list[dict]] = None
    knowledge_query_options: Any = None
    model_context_options: ModelContextSettings | None = None
    agent_options: AgentOptions | None = Field(
        default=None,
        deprecated="使用 model_context_options and knowledge_query_options 替代",
    )
    support_vision: bool = False
    file_store: ByteStore | None = None
    role_prompt: str | None = Field(default=None, deprecated="已经被纳入 chat_history 管理")
    max_token_size: int | None = None
    callbacks: list[BaseCallbackHandler] | None = None
    agent_cls: CommonAgentProtocol = Field(default_factory=CommonQAAgent)
    """通用 agent 实例（实现 ``CommonAgentProtocol``）；ChatCompletionAgent 在 ``_get_agent`` 阶段
    通过 ``self.agent_cls.get_agent_executor(...)`` 触发执行器构建。
    字段名保留为 ``agent_cls`` 避免外部破坏，但语义已是「实例」。"""
    messages: list[BaseMessage] = Field(default_factory=list)
    checkpointer: BaseCheckpointSaver | None = None

    event_handler: Callable[[BaseEvent], None] | None = None
    mcp_fetch_failures: list[dict] = Field(default_factory=list, description="MCP 工具拉取失败记录，用于流式事件")
    resource_manager: Any = Field(
        default=None, exclude=True, description="per-request 资源管理器（含正确 app_code / access_token）"
    )
    runtime_backend_resolver: Any = Field(
        default=None,
        exclude=True,
        description="RuntimeBackendResolver 引用，由 ChatAgentBuilder 构造，用于执行结束后关闭沙箱资源",
    )
    interrupt_processor: Any = Field(
        default=None,
        exclude=True,
        description=(
            "InterruptProcessor 统一中断编排器，execute() 入口惰性构造（ItsmTicketCreator "
            "需 execute_kwargs.executor/session_code，build 期拿不到，D-11）。"
        ),
    )
    agent_info: dict | None = Field(default=None, description="原始配置信息，来自 AgentConfig.agent_info")
    max_spawn_depth: int = Field(default=1, description="最大 Agent 嵌套深度，来自 AgentConfig.max_spawn_depth")
    generating_keyword: str | None = Field(
        default=None,
        description="生成中关键词，来自 AgentConfig.generating_keyword；LLM 输入视图据此清理末条 assistant 占位",
    )

    TOOL_EXECUTION_INTERVAL: ClassVar[int] = 10
    UPLOAD_IMAGE_PROMPT_PREFIX: ClassVar[Any] = "我上传了个图片文件,文件名为{file_name}。"
    SKIP_PROMPT_ROLE: ClassVar[list[str]] = ["guide"]

    class Config:
        arbitrary_types_allowed = True

    # ---------- 公共入口 ----------

    def build(self, ctx: AgentBuildContext) -> "ChatCompletionAgent":
        """在 ``self``（``cls()`` 空种子实例）上原地装配 fully-built ``ChatCompletionAgent`` 并返回。

        Chat 专属装配逻辑由 :class:`ChatAgentBuilder` 承接，本方法仅做字段赋值。
        所有装配参数来自 ``ctx``（通用字段）和 ``ctx.chat``（Chat 专属字段），
        不再依赖 factory 反向引用。

        可选字段（``agent_cls`` / ``thread_id`` / ``event_handler``）仅在 ctx 提供
        非空值时覆盖，缺省时保留种子默认值（如 ``thread_id`` 的随机 uuid）。
        """
        chat = ctx.chat or ChatBuildExtras()
        builder = ChatAgentBuilder(ctx)
        builder.handle_agent_switch()
        # 先构建 executor_info，供 build_tools / construct_mcp 使用同一凭证源
        self.executor_info = builder.build_executor_info()
        # 构建 chat_model 和 chat_model_non_thinking
        self.chat_model = builder.build_chat_model()
        self.chat_model_non_thinking = builder.build_chat_model_non_thinking()
        self.chat_model_fast = builder.build_chat_model_fast()
        # 构建需要依赖resource_manager的资源
        self.resource_manager = ctx.resource_manager
        self.skills = builder.build_skills()
        self.tools = builder.build_tools()
        self.mcp_fetch_failures = builder.mcp_fetch_failures
        self.knowledge_bases = builder.build_knowledge_bases()
        self.knowledges = builder.build_knowledge_items()
        self.subagent_specs = builder.build_subagents(ctx.agent_code)
        self.role_prompt = builder.get_role_prompt()
        # chat_history 由 ChatAgentBuilder 无损承接 ctx.session_context_data（A 源适配层输出），
        # 是 agent 唯一历史事实源：LLM 装配（convert 链）与首帧快照均从它派生。
        self.chat_history = builder.build_chat_history(ctx.session_context_data)
        self.file_resources = builder.file_resources
        # 构建Agent参数配置
        if ctx.agent_config and ctx.agent_config.agent_options is not None:
            self.agent_options = ctx.agent_config.agent_options
        self.knowledge_query_options = builder.build_knowledge_query_options()
        self.model_context_options = builder.build_model_context_options()
        self.support_vision = builder.build_support_vision()
        self.checkpointer = builder.build_checkpointer()
        self.callbacks = chat.callbacks
        # 构造 RuntimeBackendResolver（在 ChatAgentBuilder 层管理生命周期）
        self.runtime_backend_resolver = builder.build_runtime_backend_resolver()
        self.agent_info = getattr(ctx.agent_config, "agent_info", None) if ctx.agent_config else None
        self.max_spawn_depth = ctx.agent_config.max_spawn_depth if ctx.agent_config else 1
        self.generating_keyword = ctx.agent_config.generating_keyword if ctx.agent_config else None

        if chat.agent_cls is not None:
            self.agent_cls = chat.agent_cls
        if ctx.session_code is not None:
            self.thread_id = ctx.session_code
        if ctx.event_handler is not None:
            self.event_handler = ctx.event_handler
        return self

    def _prepare_pre_run_history(self, execute_kwargs: ExecuteKwargs) -> None:
        """agent 运行前的对话预处理：resume 收编单入口（装配）+ 本轮记录 patch 进 chat_history 账本。

        在 ``convert_chat_history_to_messages`` 之前调用。build 期 DB 读已先发生，
        这里把本轮 user / tool 记录手工 patch 进 ``self.chat_history``，并把 resume
        命中的末尾 interrupt 记录就地改写为终态（原 id 不变）
        （唯一历史事实源，快照与 convert 链共用），让 ``convert_chat_history_to_messages``
        消费到最新记录，并派发对应 DB 回写事件（由 ``AGUISessionWriter`` 的 handler 落库）。

        - resume + (input 或空 answers)（跳过）：经 ``InterruptProcessor.resolve_resumes``
          → ``AskUserQuestionHandler.on_resume`` 三态分流（skip 补 tool + user 两条、
          派发 skipped + user 事件）。
        - resume + 非空 answers（答题）：经 resolve_resumes → on_resume 改写 interrupt
          记录为终态、派发 resolved 事件。
        - 无 resume + input（普通新对话）：补 user 一条，派发 user 事件。
        - 无 resume + 无 input：无事可做。

        U-05/D-16（48）：``resolve_resumes`` **无返回值**（on_resume 语义）——事件派发
        内聚到 handler（ask_user 经注入 bound method，D-14）。本方法只调
        ``resolve_resumes`` 收编前端 resume 的落库（不消费返回值），删除 action 派发块
        （backfill 派发 / skip 清 resume / interrupt 分支，D-15 skip 统一串行语义不再
        清 resume 当新对话轮）与实例暂存机制（U-08 消亡，回放字段改由 get_resume_input 产出）。
        resolve_resumes 数据源为 chat_history（U-02），不再依赖提前取的 graph tasks。

        input 是独立维度，不绑 resume：跳过判别条件是 ``input 或 answers 为空``，
        因此 ``resume + 无 input + 空 answers`` 也走跳过（仅取消 interrupt，不补 user）。
        """
        if not isinstance(self.event_handler, BaseSessionWriter):
            return
        resume = execute_kwargs.resume
        input_text = execute_kwargs.input
        turn_id = execute_kwargs.turn_id

        # D-13 装配：ask_user resume 的三态分流统一经 InterruptProcessor.resolve_resumes
        # 收编（D-03），事件派发内聚到 on_resume（D-16）。resolve_resumes 无返回值，
        # 不在此消费；审批中断的 resume 由审批路径（DB 权威 read-only 门禁）处理。
        # 时序锚点（F.4 硬约束 #2）：本方法在 convert_history_to_messages 之前。
        if resume:
            processor = self.interrupt_processor or InterruptProcessor(handlers={})
            processor.resolve_resumes(
                resume,
                ProcessorContext(
                    session_code=self.thread_id,
                    thread_id=self.thread_id,
                    chat_history=self.chat_history,
                    turn_id=turn_id,
                    input_text=input_text,
                ),
            )

        # 步骤 7：独立的 user 事件分发（跳过路径 resume 已清空 / 普通新对话 / 审批 resume 都走这里）。
        if input_text:
            # 本轮 user 记录并入 chat_history 账本（唯一事实源）：build 期账本不含本轮 user 消息，
            # 不并入则新对话首帧快照丢失用户刚发的消息；convert 链消费同一账本。
            self.chat_history.append(ChatPrompt(role=PromptRole.USER.value, content=input_text))
            self._dispatch_custom(
                CustomEvent(
                    type=EventType.CUSTOM,
                    name=SessionPersistenceEventNames.UserInputSaved.value,
                    value={"content": input_text, "turn_id": turn_id},
                )
            )

    def _dispatch_ask_user_skip(self, result: dict) -> None:
        """装配层：按 on_resume 的 skip 结果补 tool 记录 + 派发 skipped/finalize 事件。

        skip 的 DB content 改写（interrupt → CANCELLED）已由 on_resume 完成，这里只做
        装配层工作：补 ``ChatPrompt`` TOOL 记录（ChatPrompt 属 services 层类型）+
        派发 ``ExtendToolCallResultEvent`` 与 ``AskUserQuestionFinalized``。upgrade 失败
        （``upgraded_content`` 为 None）时不派发 finalize 事件。
        """
        interrupt = result.get("interrupt")
        tool_call_id = result.get("tool_call_id", "")
        builtin = result.get("builtin_property") or {}
        skipped_answers = result.get("skipped_answers") or []
        upgraded = result.get("upgraded_content")
        turn_id = result.get("turn_id", "")

        self.chat_history.append(
            ChatPrompt(
                role=PromptRole.TOOL.value,
                content=ASK_USER_QUESTION_SKIPPED_CONTENT,
                builtin_property={"tool_call_id": tool_call_id},
            )
        )
        # 本轮 skip tool 记录直接并入 chat_history 账本（唯一事实源，快照与 convert 链共用）。
        self._dispatch_custom(
            ExtendToolCallResultEvent(
                type=EventType.TOOL_CALL_RESULT,
                tool_call_id=tool_call_id,
                tool_call_name=ASK_USER_QUESTION_TOOL_NAME,
                message_id=tool_call_id,
                content=ASK_USER_QUESTION_SKIPPED_CONTENT,
                role="tool",
                duration=None,
                is_error=False,
                additional_metadata={},
                skip_db=False,
            )
        )
        if upgraded is None:
            logger.warning(
                "[AskUserQuestion] skip path upgrade 失败, content_id=%s, 不派发 finalize",
                getattr(interrupt, "id", None),
            )
            return
        # 改写已就地落账（原记录 id 不变），终态内容经 finalize 事件下发前端。
        self._dispatch_custom(
            CustomEvent(
                type=EventType.CUSTOM,
                name=SessionPersistenceEventNames.AskUserQuestionFinalized.value,
                value={
                    "turn_id": turn_id,
                    "status": InterruptStatus.CANCELLED.value,
                    "answers": skipped_answers,
                    "content_id": getattr(interrupt, "id", None),
                    "content": upgraded,
                    "builtin_property": builtin,
                },
            )
        )

    def _dispatch_ask_user_answer(self, result: dict) -> None:
        """装配层：按 on_resume 的 answer 结果派发 finalize 事件（携带终态 content）。

        answer 的 DB content 改写（interrupt → RESOLVED）已由 on_resume 完成，这里只做
        装配层事件派发。upgrade 失败时不派发 finalize 事件（与 skip 路径对称）。
        """
        interrupt = result.get("interrupt")
        answers = result.get("answers") or []
        builtin = result.get("builtin_property") or {}
        upgraded = result.get("upgraded_content")
        turn_id = result.get("turn_id", "")
        if upgraded is None:
            logger.warning(
                "[AskUserQuestion] answer path upgrade 失败, content_id=%s, 不派发 finalize",
                getattr(interrupt, "id", None),
            )
            return
        self._dispatch_custom(
            CustomEvent(
                type=EventType.CUSTOM,
                name=SessionPersistenceEventNames.AskUserQuestionFinalized.value,
                value={
                    "turn_id": turn_id,
                    "answers": answers,
                    "status": InterruptStatus.RESOLVED.value,
                    "content_id": getattr(interrupt, "id", None),
                    "content": upgraded,
                    "builtin_property": builtin,
                },
            )
        )

    def _dispatch_custom(self, event: BaseEvent) -> None:
        """直调 event_handler 派发已构造好的事件（绕开 SSE 编码循环）。

        事件构造由调用方负责，本方法仅做类型守卫与转发。
        """
        if isinstance(self.event_handler, BaseSessionWriter):
            self.event_handler(event)

    def _session_code_for_caller_context(self, execute_kwargs: ExecuteKwargs) -> str:
        return (execute_kwargs.session_code or self.thread_id or "").strip()

    @staticmethod
    def _caller_context_from_session(session: Any) -> dict[str, Any]:
        if not isinstance(session, dict):
            return {}
        prop = session.get("session_property") or {}
        if not isinstance(prop, dict):
            return {}
        data = prop.get("caller_context") or {}
        return data if isinstance(data, dict) else {}

    def _restore_session_caller_context(self, execute_kwargs: ExecuteKwargs, session_code: str) -> None:
        retrieve = getattr(self.resource_manager, "retrieve_chat_session", None)
        if not callable(retrieve):
            return
        try:
            execute_kwargs.apply_caller_context(
                self._caller_context_from_session(retrieve(session_code)),
                overwrite=bool(execute_kwargs.resume),
            )
        except Exception:
            logger.warning("restore session caller_context failed: session_code=%s", session_code, exc_info=True)

    def _persist_session_caller_context(self, execute_kwargs: ExecuteKwargs, session_code: str) -> None:
        update = getattr(self.resource_manager, "update_chat_session_caller_context", None)
        current = execute_kwargs.to_caller_context()
        if not current or not callable(update):
            return
        retrieve = getattr(self.resource_manager, "retrieve_chat_session", None)
        try:
            stored = self._caller_context_from_session(retrieve(session_code) if callable(retrieve) else {})
            merged = {**current, **stored}
            if merged == stored:
                return
            update(session_code, merged)
        except Exception:
            logger.warning("persist session caller_context failed: session_code=%s", session_code, exc_info=True)

    def _sync_session_caller_context(self, execute_kwargs: ExecuteKwargs) -> None:
        """resume 读回 ``caller_context``，非 resume 把当次调用方字段写回会话（已有键不覆盖）。"""
        session_code = self._session_code_for_caller_context(execute_kwargs)
        if session_code:
            self._restore_session_caller_context(execute_kwargs, session_code)
        execute_kwargs.apply_session_caller_defaults(getattr(self.resource_manager, "username", None) or None)
        if session_code:
            self._persist_session_caller_context(execute_kwargs, session_code)

    def execute(self, execute_kwargs: ExecuteKwargs) -> Generator[str, None, None] | str:
        self.migration_v1()
        # D-13：resume dict→list 归一化前移到 execute() 最前（消除 R1/R2 双重兼容逻辑）
        if isinstance(execute_kwargs.resume, dict):
            execute_kwargs.resume = [execute_kwargs.resume]
        # 审批 / ask_user resume 常省略 executor；优先从 session.property.caller_context
        # 回填首次调用身份，再用当前 username 补齐空字段。须在 ItsmTicketCreator 之前。
        self._sync_session_caller_context(execute_kwargs)
        # D-11：processor 惰性构造（execute 入口，非 build 期——ItsmTicketCreator 需
        # execute_kwargs.executor/session_code，build 期拿不到）。
        # D-03（48）：构造参数改为 handlers dict 显式注入（U-01，移除 resource_manager /
        # ticket_creator 构造参数）。审批 handler 自持 resource_manager + ItsmTicketCreator
        # （建单依赖移入 handler，U-01）；ask_user handler 注入 bound method（D-14）。
        if self.interrupt_processor is None:
            approval_handler = ApprovalHandler(
                resource_manager=self.resource_manager,
                ticket_creator=ItsmTicketCreator(
                    self.resource_manager,
                    username=getattr(execute_kwargs, "executor", None) or None,
                    session_code=getattr(execute_kwargs, "session_code", None) or self.thread_id,
                ),
            )
            ask_user_handler = AskUserQuestionHandler(
                dispatch_skip=self._dispatch_ask_user_skip,  # D-14 bound method
                dispatch_answer=self._dispatch_ask_user_answer,
                resource_manager=self.resource_manager,  # Gap 1：ask_user 门禁查 DB 权威 answers 需 RM
            )
            self.interrupt_processor = InterruptProcessor(
                handlers={
                    # 键用 reason 的**值**字符串（str-enum 的 str() 会返回枚举名
                    # 而非值，processor._reason_of 读 pending value 的 reason 字段是
                    # 值字符串 —— 键必须与之 hash 等价，否则聚合门禁 miss handler）。
                    InterruptReason.TOOL_APPROVAL.value: approval_handler,
                    InterruptReason.USER_QUESTION.value: ask_user_handler,
                }
            )
        # U-06（48）：恢复到 294ff5d55 装配顺序——_prepare_pre_run_history 先于 convert；
        # resolve_resumes 只依赖 chat_history（U-02 数据源），不再需要提前取 graph tasks。
        self._prepare_pre_run_history(execute_kwargs)
        if not self.messages:
            self.messages = convert_chat_history_to_messages(
                self._build_llm_history(),
                model_context_options=self.model_context_options,
                support_vision=self.support_vision,
                model_name=self.model_name,
                agent_info=self.agent_info,
                generating_keyword=self.generating_keyword,
                files=self.files,
            )
        messages = self.messages
        chat_models = (
            (self.chat_model.runnable, *self.chat_model.fallbacks)
            if isinstance(self.chat_model, RunnableWithFallbacks)
            else (self.chat_model,)
        )
        for chat_model in chat_models:
            chat_model.callbacks = self.callbacks
        # U-06（48）：_get_agent 移回 _execute 内部，_execute 恢复双参签名（无 agent_e/cfg）。
        return self._execute(messages, execute_kwargs)

    def stop(self):
        helper = GeneratorStreamingHelper(
            thread_id=self.thread_id,
        )
        # 所有 handler 的 request_cancel 都是幂等的，无需先读后写；避免两次远端请求和 TOCTOU 竞态。
        logger.info("[STOP_DEBUG] Requesting cancel for thread_id=%s", self.thread_id)
        helper.message_handler.request_cancel(self.thread_id)
        # 用户主动停止时也释放资源
        self.release_resources()

    def release_resources(self) -> None:
        """释放 agent 持有的资源（沙箱后端等）。

        统一走 ``resolver.close()``，销毁语义由 resolver 按延迟销毁策略分流：
        - 未启用延迟销毁：立即销毁全部；
        - 启用延迟销毁：所有权移交 LifecycleManager（``defer``）
        —— save() 登记记录供后续请求挂载复用，实例由 defer_manager 持有，TTL 到期或进程退出时真实销毁
        此方法是幂等的 — 多次调用不会产生副作用
        """
        if self.runtime_backend_resolver is not None:
            try:
                self.runtime_backend_resolver.close()
            except Exception:
                logger.warning("ChatCompletionAgent.release_resources: 关闭沙箱资源失败", exc_info=True)
            finally:
                self.runtime_backend_resolver = None

    async def _aclose_chat_models(self) -> None:
        """在模型执行 loop 上关闭当前 agent 自己创建的异步 HTTP client。"""
        models: list[Any] = []
        for configured_model in (self.chat_model, self.chat_model_non_thinking, self.chat_model_fast):
            if isinstance(configured_model, RunnableWithFallbacks):
                models.extend((configured_model.runnable, *configured_model.fallbacks))
            else:
                models.append(configured_model)

        clients: dict[int, tuple[Any, list[Any]]] = {}
        for model in models:
            if model is None or not getattr(model, "_owns_http_async_client", False):
                continue
            client = getattr(model, "http_async_client", None)
            if client is not None:
                clients.setdefault(id(client), (client, []))[1].append(model)

        for client, owners in clients.values():
            try:
                await client.aclose()
            except Exception:
                logger.warning("ChatCompletionAgent: 关闭模型异步 HTTP client 失败", exc_info=True)
            else:
                for model in owners:
                    model._owns_http_async_client = False

    @staticmethod
    def _filter_messages_for_llm(messages: list[BaseMessage]) -> list[BaseMessage]:
        """LLM 入口过滤 reasoning，不影响 MESSAGES_SNAPSHOT。"""
        return [each for each in messages if not isinstance(each, ReasoningLangChainMessage)]

    @property
    def model_name(self) -> str:
        return getattr(self.chat_model, "model_name", "")

    # ---------- 内部方法 ----------
    def _update_aidev_agent_header(self, execute_kwargs: ExecuteKwargs) -> None:
        """Build complete X-BKAIDEV-Attributes header (agent.info + session) and inject in-place."""
        agent_info = self.agent_info or {}
        langgraph_thread_id = execute_kwargs.session_code or self.thread_id
        attrs = {
            "agent.info.code": agent_info.get("agent_code") or "",
            "agent.info.name": agent_info.get("agent_name") or "",
            "agent.info.service_catalogue": agent_info.get("service_catalogue") or "",
            "agent.info.sdk_version": pkg_version("aidev_agent"),
            "agent.session.caller_bk_app_code": execute_kwargs.caller_bk_app_code or "",
            "agent.session.caller_bk_biz_env": execute_kwargs.caller_bk_biz_env or "",
            "agent.session.caller_bk_biz_id": str(execute_kwargs.caller_bk_biz_id or ""),
            "agent.session.caller_executor": execute_kwargs.caller_executor or "",
            "agent.session.executor": execute_kwargs.executor or "",
            "agent.session.caller_order_type": execute_kwargs.caller_order_type or "",
            "agent.session.session_code": execute_kwargs.session_code or "",
            "agent.session.langgraph_thread_id": langgraph_thread_id,
        }

        header_value = json.dumps(attrs, ensure_ascii=True)
        # RunnableWithFallbacks 自身无 default_headers，需展开为底层 runnable + fallbacks
        # 后逐个注入，与 _aclose_chat_models 的展开方式保持一致。
        targets: list[Any] = []
        for model in (self.chat_model, self.chat_model_non_thinking, self.chat_model_fast):
            if model is None:
                continue
            if isinstance(model, RunnableWithFallbacks):
                targets.append(model.runnable)
                targets.extend(model.fallbacks)
            else:
                targets.append(model)
        for model in targets:
            if not hasattr(model, "default_headers"):
                continue
            if model.default_headers is None:
                model.default_headers = {}
            model.default_headers["X-BKAIDEV-Attributes"] = header_value

    def _fetch_platform_pv(self) -> list[dict]:
        """从平台拉取已存在的 sandbox PV，返回包含 PV 信息的列表。

        通过 resource_manager.retrieve_chat_session 获取会话的
        session_property.sandbox_pv_id，若存在则构造 platform 来源的 PV 条目；
        失败时返回空列表，不阻塞图执行。
        """
        if self.resource_manager is None or not self.thread_id:
            return []
        try:
            session = self.resource_manager.retrieve_chat_session(self.thread_id)
            session_property = (session or {}).get("session_property") or {}
            sandbox_pv_id = session_property.get("sandbox_pv_id")
        except Exception:
            logger.warning("restore platform PV failed: session_code=%s", self.thread_id, exc_info=True)
            return []
        if not sandbox_pv_id:
            return []
        return [
            {
                "type": "paas-sbx-pv",
                "volume_id": sandbox_pv_id,
                "volume_name": f"agent-pv-{self.thread_id}",
                "mount_path": "session",
                "source": "platform",
            }
        ]

    def _fetch_execute_pv(self) -> list[dict]:
        """从 execute_kwargs 读取 sandbox_pv_id，构造 execute_kwargs 来源的 PV 条目。

        若 execute_kwargs.sandbox_pv_id 存在，直接构造 PV dict 返回；
        失败时返回空列表，不阻塞图执行。

        Returns:
            PV 条目列表，source 为 'execute_kwargs'；若无 sandbox_pv_id 则返回空列表。
        """
        try:
            ek = getattr(self, "_execute_kwargs", None)
            sandbox_pv_id = ek.sandbox_pv_id if ek else None
        except Exception:
            logger.warning("fetch execute PV failed: thread_id=%s", self.thread_id, exc_info=True)
            return []
        if not sandbox_pv_id:
            return []
        return [
            {
                "type": "paas-sbx-pv",
                "volume_id": sandbox_pv_id,
                "volume_name": f"agent-pv-{self.thread_id}",
                "mount_path": "session",
                "source": "execute_kwargs",
            }
        ]

    # ---------- messages 处理流水线（Phase 11.4: 从 agent.py 整合） ----------
    def _sync_checkpoint_messages(self, agent_e: Runnable, cfg: RunnableConfig) -> list[BaseMessage]:
        """同步 checkpoint 中的消息，返回 checkpoint 中非系统消息列表。

        使用 RemoveMessage 清除旧的 checkpoint 消息，避免与平台消息重复/冲突。
        这是保持 thread_id 稳定的前提条件（替代原来的 uuid4 后缀方案）。

        注意：此同步必须在 _execute 中执行（而非 prepare_stream），
        因为非流式路径（ainvoke）不经过 prepare_stream。
        """
        try:
            agent_state = agent_e.get_state(cfg)
            checkpoint_messages = agent_state.values.get("messages", [])
            non_system_checkpoint_msgs = [m for m in checkpoint_messages if not isinstance(m, SystemMessage)]

            if non_system_checkpoint_msgs:
                remove_ops = []
                skipped_none_id_count = 0
                for m in non_system_checkpoint_msgs:
                    if m.id is not None:
                        remove_ops.append(RemoveMessage(id=m.id))
                    else:
                        skipped_none_id_count += 1

                if skipped_none_id_count > 0:
                    logger.warning(
                        "sync_checkpoint: %d checkpoint messages have id=None, "
                        "cannot remove via RemoveMessage, thread_id=%s",
                        skipped_none_id_count,
                        self.thread_id,
                    )

                if remove_ops:
                    agent_e.update_state(
                        cfg,
                        {"messages": remove_ops},
                        as_node="__start__",
                    )

            return non_system_checkpoint_msgs
        except Exception:
            logger.warning(
                "sync_checkpoint: failed to sync checkpoint messages, thread_id=%s",
                self.thread_id,
                exc_info=True,
            )
            return []

    def _merge_state(
        self,
        state: dict[str, Any],
        messages: list[BaseMessage],
    ) -> dict[str, Any]:
        """合并 state：messages + tools + ag-ui 字段 + copilotkit 字段。

        从 agent.py.langgraph_default_merge_state + LangGraphAGUIAgent 覆写整合而来。
        chat.py 总是使用 AidevAGUIAgent（继承 LangGraphAGUIAgent），因此 copilotkit
        字段总是需要构造（与原 LangGraphAGUIAgent 覆写逻辑一致）。

        11.8: 改为接收原始 tools/context 字段（不接收 AgentInput），预处理在 agent_input 构造前完成。
        11.9: 签名收窄为 (state, messages)；tools 从 state.get("tools", []) 获取，
              context 固定为 []（原 tools/context 参数总是传空值）。
        """
        # 直接使用传入的 messages（后端数据库的完整历史）
        merged_messages = messages
        # tools 从 state.get("tools", []) 获取（原 tools 参数总是传 []，等价）
        all_tools = state.get("tools", [])

        # Remove duplicates based on tool name
        seen_names: set[str] = set()
        unique_tools: list = []
        for tool in all_tools:
            tool_name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            if tool_name and tool_name not in seen_names:
                seen_names.add(tool_name)
                unique_tools.append(tool)
            elif not tool_name:
                # Keep tools without names (shouldn't happen, but just in case)
                unique_tools.append(tool)

        merged_state = {
            **state,
            "messages": merged_messages,
            "tools": unique_tools,
            "ag-ui": {"tools": unique_tools, "context": []},  # 11.9: context 固定 []
        }

        # copilotkit 字段（原 LangGraphAGUIAgent.langgraph_default_merge_state 覆写逻辑）
        agui_properties = merged_state.get("ag-ui", {}) or merged_state
        return {
            **merged_state,
            "copilotkit": {
                "actions": agui_properties.get("tools", []),
                "context": agui_properties.get("context", []),
            },
        }

    def _get_checkpoint_before_message(self, agent_e: Runnable, message_id: str, thread_id: str):
        """checkpoint 历史遍历，找 message_id 对应的前一个 checkpoint。

        从 agent.py.get_checkpoint_before_message 迁移，用 agent_e.get_state_history 替代 self.graph.get_state_history。
        """
        if not thread_id:
            raise ValueError("Missing thread_id in config")

        history_list = list(agent_e.get_state_history({"configurable": {"thread_id": thread_id}}))

        history_list.reverse()
        for idx, snapshot in enumerate(history_list):
            messages = snapshot.values.get("messages", [])
            if any(getattr(m, "id", None) == message_id for m in messages):
                if idx == 0:
                    # No snapshot before this
                    # Return synthetic "empty before" version
                    empty_snapshot = snapshot
                    empty_snapshot.values["messages"] = []
                    return empty_snapshot

                snapshot_values_without_messages = snapshot.values.copy()
                del snapshot_values_without_messages["messages"]
                checkpoint = history_list[idx - 1]

                merged_values = {
                    **checkpoint.values,
                    **snapshot_values_without_messages,
                }
                checkpoint = checkpoint._replace(values=merged_values)

                return checkpoint

        raise ValueError("Message ID not found in history")

    def _prepare_stream_input(
        self,
        agent_e: Runnable,
        cfg: RunnableConfig,
        state: dict[str, Any],
        forwarded_props: Any,
        thread_id: str,
        messages: list,
        agent_state,
        schema_keys: SchemaKeys,
    ) -> dict[str, Any]:
        """messages 处理流水线：转换 → 合并 → regenerate 检测 → 时间旅行"""
        state_input = state
        assert state_input is not None, "state must not be None"
        forwarded_props = forwarded_props or {}
        resume_input = forwarded_props.get("command", {}).get("resume", None)
        thread_id = thread_id

        # 1. LLM 入口过滤 reasoning + state 合并（messages 已是 langchain）
        if resume_input:
            state = agent_state.values.copy() if agent_state.values else state_input
            langchain_messages: list[BaseMessage] = []
        else:
            # 不再依赖 checkpoint 中的 messages，直接使用后端数据库传来的完整历史
            state_input["messages"] = []
            langchain_messages = self._filter_messages_for_llm(messages)
            state = self._merge_state(state_input, langchain_messages)

        # 2. regenerate 检测 + checkpoint 时间旅行
        non_system_messages = [msg for msg in langchain_messages if not isinstance(msg, SystemMessage)]
        if not resume_input and len(agent_state.values.get("messages", [])) > len(non_system_messages):
            last_user_message = None
            for i in range(len(langchain_messages) - 1, -1, -1):
                if isinstance(langchain_messages[i], HumanMessage):
                    last_user_message = langchain_messages[i]
                    break

            if last_user_message:
                return self._prepare_regenerate_input(
                    agent_e=agent_e,
                    cfg=cfg,
                    state=state_input,
                    forwarded_props=forwarded_props,
                    thread_id=thread_id,
                    last_user_message=last_user_message,
                    langchain_messages=langchain_messages,
                    schema_keys=schema_keys,
                    agent_state=agent_state,
                )

        # 3. 正常路径：构造 stream_input（从 agent.py prepare_stream 移来，统一用 preprocessed["stream_input"]）
        if resume_input:
            # U-08/D-06（48）：唯一 resume_input 获取点——经 InterruptProcessor.get_resume_input
            # 串行产出 Command（U-03）。不消费实例暂存（U-08 消亡）；stream_input 仅当
            # resume_result.ready 时才非 None（拒绝占位死值，T-48-05 mitigate）。回放三字段 /
            # ready 判定随 resume_input_result 返回，供 _stream 消费。
            resume_result = self.interrupt_processor.get_resume_input(
                tasks=getattr(agent_state, "tasks", None) or [],
                session_code=self.thread_id,
                thread_id=self.thread_id,
                chat_history=self.chat_history,
            )
            self._resume_input_result = resume_result  # _stream 消费回放三字段 + D-09 ready 判定
            stream_input = resume_result.command if resume_result.ready else None
            if stream_input is None and resume_result.ready:
                logger.warning("[ChatCompletionAgent] resume 就绪但未产出 Command，拒绝以占位死值启动")
            # CD-04（48）：skip+input 场景——用户新输入经 Command.update 注入 messages channel
            # （反「当新对话轮」，D-15 统一串行语义），resume 仍从工具处继续。react 图
            # messages channel 用 add_messages reducer 消费 Command.update（已 grep 验证）。
            if resume_result.ready and resume_result.command is not None:
                _exec_kwargs = getattr(self, "_execute_kwargs", None)
                _input_text = getattr(_exec_kwargs, "input", "") if _exec_kwargs is not None else ""
                if _input_text:
                    resume_result.command = Command(
                        resume=resume_result.command.resume,
                        update={"messages": [HumanMessage(content=_input_text)]},
                    )
                    stream_input = resume_result.command
        else:
            payload_input = get_stream_payload_input(
                mode="start",
                state=state,
                schema_keys=schema_keys,
            )
            stream_input = {**forwarded_props, **payload_input} if payload_input else None
            stream_messages = stream_input["messages"] if stream_input else []
            stream_input = {**state, "messages": stream_messages}

        return {
            "state": state,
            "stream_input": stream_input,
            "fork": None,
            "resume_input_result": self._resume_input_result if resume_input else None,
        }

    def _prepare_regenerate_input(
        self,
        agent_e: Runnable,
        cfg: RunnableConfig,
        state: dict[str, Any],
        forwarded_props: Any,
        thread_id: str,
        last_user_message: HumanMessage,
        langchain_messages: list[BaseMessage],
        schema_keys: SchemaKeys,
        agent_state: Any = None,
    ) -> dict[str, Any]:
        """regenerate 路径：checkpoint 时间旅行 + stream input 构造"""
        forwarded_props = forwarded_props or {}
        resume_input = forwarded_props.get("command", {}).get("resume", None)
        # CD-02（48）：与 _prepare_stream_input 同源——resume 分支统一消费
        # _prepare_stream_input 顶部 get_resume_input 存下的 self._resume_input_result，
        # 不再散点直调 processor（U-08 消亡）。

        time_travel_checkpoint = self._get_checkpoint_before_message(agent_e, last_user_message.id, thread_id)
        if time_travel_checkpoint is None:
            # 兜底：找不到 checkpoint 时回退到正常路径（11.6：也构造 stream_input）
            state = self._merge_state(state or {}, langchain_messages)
            if resume_input:
                resume_result = getattr(self, "_resume_input_result", None)
                stream_input: Any = resume_result.command if resume_result is not None and resume_result.ready else None
            else:
                payload_input = get_stream_payload_input(
                    mode="start",
                    state=state,
                    schema_keys=schema_keys,
                )
                stream_input = {**forwarded_props, **payload_input} if payload_input else None
                stream_messages = stream_input["messages"] if stream_input else []
                stream_input = {**state, "messages": stream_messages}
            return {
                "state": state,
                "stream_input": stream_input,
                "fork": None,
            }

        fork = agent_e.update_state(
            time_travel_checkpoint.config,
            time_travel_checkpoint.values,
            as_node=time_travel_checkpoint.next[0] if time_travel_checkpoint.next else "__start__",
        )

        stream_input: Any = self._merge_state(time_travel_checkpoint.values, [last_user_message])
        if forwarded_props.get("command", {}).get("resume"):
            # CD-02（48）：消费 _prepare_stream_input 顶部 get_resume_input 存下的结果
            resume_result = getattr(self, "_resume_input_result", None)
            stream_input = resume_result.command if resume_result is not None and resume_result.ready else None

        return {
            "state": time_travel_checkpoint.values,
            "stream_input": stream_input,
            "fork": fork,
        }

    def _execute(self, messages: list[BaseMessage], execute_kwargs: ExecuteKwargs):
        if not messages:
            raise ValueError("The messages list cannot be empty.")
        self._update_aidev_agent_header(execute_kwargs)
        # U-06（48）：恢复到 294ff5d55——_get_agent 在 _execute 内构建，双参签名（无 agent_e/cfg）。
        agent_e, cfg = self._get_agent(messages, execute_kwargs=execute_kwargs)
        cfg.setdefault("configurable", {})
        cfg["configurable"]["thread_id"] = self.thread_id
        # spawn_depth/spawned_by 由 ExecuteKwargs 默认值（主 Agent）或 _extract_execute_kwargs（子 Agent）提供，
        # 这里不再覆盖；仅主 Agent（无父会话）读 AgentConfig.max_spawn_depth，子 Agent 继承父值
        if execute_kwargs.spawned_by is None:
            execute_kwargs.max_spawn_depth = self.max_spawn_depth
        execute_kwargs.tool_deny = execute_kwargs.tool_deny or []
        execute_kwargs.tool_allow = execute_kwargs.tool_allow or []
        cfg["configurable"]["execute_kwargs"] = execute_kwargs
        self._execute_kwargs = execute_kwargs

        # 清除 checkpoint 中的旧消息，避免与平台消息重复
        # 平台传入的 messages 已包含完整历史，无需拼接
        # resume 时不能清checkpoint，否则 model 节点会拿到空 messages → 拒答。
        if not execute_kwargs.resume:
            self._sync_checkpoint_messages(agent_e, cfg)

        # platform_pv 统一在此构造，下传给 _stream_with_legacy / _stream / _invoke
        state: dict[str, Any] = {}
        platform_pv = self._fetch_execute_pv() or self._fetch_platform_pv()
        if platform_pv:
            state["runtime_paas_sbx_pv"] = platform_pv

        if execute_kwargs.stream:
            if execute_kwargs.legacy_streaming:
                return self._stream_with_legacy(agent_e, cfg, state, messages)
            else:
                return self._stream(agent_e, cfg, state, messages, execute_kwargs)

        else:
            from aidev_agent.services.resume_events import uses_resume_event_stream

            if uses_resume_event_stream(self.resource_manager, execute_kwargs):
                return self._invoke_resume_with_events(agent_e, cfg, state, messages, execute_kwargs)
            return self._invoke(agent_e, cfg, state, messages, execute_kwargs)

    def _invoke_resume_with_events(self, agent_e, cfg, state, messages, execute_kwargs):
        """Keep a non-stream HTTP response while using the AG-UI resume/persistence path.

        _invoke uses ainvoke(input_state), not Command(resume=...). Opted-in
        callbacks must not become new input, nor execute the Agent twice.
        """
        stream_kwargs = execute_kwargs.model_copy(update={"stream": True})
        cfg["configurable"]["execute_kwargs"] = stream_kwargs
        self._execute_kwargs = stream_kwargs
        text, message_id, outcome = [], "", None
        for chunk in self._stream(agent_e, cfg, state, messages, stream_kwargs):
            if not isinstance(chunk, str) or not chunk.startswith("data:"):
                continue
            try:
                event = json.loads(chunk[5:].strip())
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "TEXT_MESSAGE_CONTENT":
                text.append(event.get("delta", ""))
                message_id = event.get("messageId", message_id)
            elif event.get("type") == "RUN_FINISHED" and not event.get("resume_replay"):
                outcome = event.get("outcome")
        result = {
            "choices": [{"delta": {"role": "assistant", "content": "".join(text)}}],
            "id": message_id,
            "model": self.model_name,
            "reference_doc": [],
        }
        if outcome is not None:
            result["outcome"] = outcome
        return result

    def _invoke(
        self,
        agent_e: Runnable,
        cfg: RunnableConfig,
        state: dict[str, Any],
        messages: list[BaseMessage],
        execute_kwargs: ExecuteKwargs,
    ):
        """非流式执行：ainvoke 并构造返回数据。

        state（含 platform_pv）由 _execute 统一构造下传，
        此处仅补充 messages / execute_kwargs 后调用 agent_e.ainvoke。

        D-03：非流式 ``_invoke`` **显式不支持 resume**——消除静默忽略歧义
        （45-D-14 已知边界升级为显式契约）。resume 续流请走流式接口（_stream）。
        """
        # D-03：非流式显式拒绝 resume（消除静默忽略歧义，杜绝非门禁路径绕过）
        if execute_kwargs.resume:
            logger.warning("[ChatCompletionAgent] 非流式 _invoke 不支持 resume，拒绝执行")
            raise AgentException(message="非流式调用不支持 resume 续流，请使用流式接口")
        try:
            input_state: dict[str, Any] = {
                "messages": self._filter_messages_for_llm(messages),
                "execute_kwargs": execute_kwargs,
                **state,
            }

            async def _ainvoke_with_cleanup():
                try:
                    return await agent_e.ainvoke(input_state, cfg)
                finally:
                    await self._aclose_chat_models()

            async def _ainvoke_with_deadline():
                if execute_kwargs.invoke_timeout is None:
                    return await _ainvoke_with_cleanup()
                deadline = asyncio.timeout(execute_kwargs.invoke_timeout)
                try:
                    async with deadline:
                        return await _ainvoke_with_cleanup()
                except TimeoutError:
                    if not deadline.expired():
                        raise
                    raise AgentDeadlineExceededError(
                        f"Agent/session deadline exceeded after {float(execute_kwargs.invoke_timeout):g}s"
                    ) from None

            result = run_coro_sync(_ainvoke_with_deadline)
            result_output = result.get("messages")[-1]
            return_data = {
                "choices": [{"delta": {"role": "assistant", "content": result_output.content}}],
                "model": self.model_name,
                "id": result_output.id,
                "reference_doc": result.get("reference_doc", []),
            }
            return return_data
        except AgentDeadlineExceededError as deadline_error:
            if record_operation_timeout is not None:
                record_operation_timeout(
                    scope="session",
                    outcome="cancelled",
                    error=deadline_error,
                    timeout_seconds=execute_kwargs.invoke_timeout,
                )
            logger.exception("Agent/session deadline exceeded")
            raise AgentException(message=str(deadline_error)) from deadline_error
        except Exception as e:
            logger.exception(f"Error executing agent: {e}")
            raise AgentException(message=f"Error executing agent: {e}")
        finally:
            # 非流式执行结束后释放资源
            self.release_resources()

    def _stream_with_legacy(
        self,
        agent_e: Runnable,
        cfg: RunnableConfig,
        state: dict[str, Any],
        messages: list[BaseMessage],
    ) -> Generator[Any, None, None]:
        _input: dict[str, Any] = {"messages": self._filter_messages_for_llm(messages), **state}
        agent_type = self.model_context_options.llm_code_agent_type if self.model_context_options else None
        adapter = AgentStreamAdapter(agent_type=agent_type)
        return adapter.stream_standard_event(
            agent_e,
            cfg,
            _input,
            async_finalizer=self._aclose_chat_models,
        )

    def _build_snapshot_agui_messages(self) -> list[ExtendMessage]:
        """构建首帧 MESSAGES_SNAPSHOT 的 AG-UI 消息列表。

        数据源为 lossless chat_history 账本（由 build_chat_history 无损承接 session_context_data 而来，
        与前端历史消息接口同源，含 system 展示类记录）；resume 命中的 interrupt 记录已被
        _prepare_pre_run_history 就地改写为终态（原 id 不变），本轮 user/tool 记录也已直接并入账本，
        快照对账本全量转换。

        账本记录统一经 model_dump 归一为 dict 后交由快照转换器消费（role/content 顶层、
        status/created_at 透传顶层、builtin_property/extra 保留）。
        """
        base = [_to_ledger_dict(rec) for rec in (self.chat_history or [])]
        return contents_to_agui_messages(base)

    def _stream(
        self,
        agent_e: Runnable,
        cfg: RunnableConfig,
        state: dict[str, Any],
        messages: list[BaseMessage],
        execute_kwargs: ExecuteKwargs,
    ) -> Generator[Any, None, None]:
        logger.info(
            "[ToolApproval] _stream: resume=%s, thread_id=%s",
            bool(execute_kwargs.resume),
            repr(self.thread_id),
        )

        # 取消信号传递：cancel_checker 在用户点停止时由 Agent 内部轮询，
        # 触发后由 Agent 优雅发送 RunFinishedEvent
        def make_cancel_checker(thread_id: str, run_id: str):
            def cancel_checker() -> bool:
                return GeneratorStreamingHelper.is_cancelled(thread_id, run_id=run_id)

            return cancel_checker

        if isinstance(self.event_handler, BaseSessionWriter):
            self.event_handler.set_tools(self.tools)

        # 续流时，AidevAGUIAgent 装配字段（approve_result / approval_interrupts /
        # ask_user_question_interrupts）由 get_resume_input 结果携带（D-06），在
        # preprocessed 返回后消费注入 Agent 构造（回放三字段必须 Agent 构造前就绪，
        # F.4 硬约束 #1）。消除 _stream 现场二次 resolve（U-07，避免二次 DB 改写）。
        approve_result = None
        approval_interrupts = []
        ask_user_question_interrupts = []

        # 预处理前移到 agent_input 构造之前（消除 model_copy + 消除 agui_entry 依赖）
        # agent_state：resume 与非 resume 均无条件现取——resume 路径
        # _prepare_stream_input 的 state 复制与 get_resume_input 的 tasks 数据源
        # （state.tasks 携带 pending interrupt）都依赖它（294ff5d55 基线同形）。
        # 不得恢复条件守卫：U-07 删除 Phase 47 resume 分支现取块后，若仅在
        # 非 resume 分支赋值，resume 路径 agent_state 未绑定 → UnboundLocalError
        # （ask_user 续流 0000400，回归测试见 test_stream_resume_fetches_agent_state）。
        agent_state = agent_e.get_state(cfg)

        # 2. schema_keys — 直接调 utils.py 函数（不依赖 agui_entry）
        schema_keys = get_schema_keys(agent_e, cfg, ["messages", "tools", "copilotkit"])

        # 3. forwarded_props 构造（在预处理前）
        forwarded_props: dict[str, Any] = {}
        if execute_kwargs.resume:
            forwarded_props = {"command": {"resume": execute_kwargs.resume}}

        # 4. 预处理（在 agent_input 构造前）
        # 11.8: tools/context 不在 _stream 作用域内，原 AgentInput.tools/context 默认为 []（body 不含）
        # tools 通过 AidevAGUIAgent 构造函数传入（graph 挂载），不通过 state 传递
        # 快照 messages 数据源为 lossless ChatPrompt 单账本（含本轮 patch 记录并入）；
        # run_id/stream_input 仍用 langchain messages（LLM 路径不受影响）。
        agui_messages = self._build_snapshot_agui_messages()
        preprocessed = self._prepare_stream_input(
            agent_e,
            cfg,
            state,
            forwarded_props,
            self.thread_id,
            messages,
            agent_state,
            schema_keys,
        )

        # D-06（48）：从 preprocessed.resume_input_result 消费回放三字段注入 Agent 构造
        # （回放字段由 get_resume_input 产出，时序满足 F.4 硬约束 #1）。
        resume_result = preprocessed.get("resume_input_result") if preprocessed else None
        approve_result = getattr(resume_result, "approve_result", None) if resume_result is not None else None
        approval_interrupts = (
            getattr(resume_result, "approval_interrupts", None) or [] if resume_result is not None else []
        )
        ask_user_question_interrupts = (
            getattr(resume_result, "ask_user_question_interrupts", None) or [] if resume_result is not None else []
        )

        # 未就绪（lw4）：不再 hand-roll SSE 早退——并入 Agent 快照-结束路径。
        # resume_result.ready=False → stream_input=None（_prepare_stream_input L801），
        # LangGraphAgent.prepare_stream 检测 stream_input is None 走快照-结束分支
        # （首帧快照后 RUN_STARTED → RUN_FINISHED(下一张卡) 即结束，不拉图，经
        # events_to_dispatch 通道）。与 ready 路径（Agent 正常拉图）互斥，杜绝双
        # RUN_FINISHED（Pitfall 4/A5）。下一张 pending 卡（next_interrupt）经
        # AgentInput.next_interrupt 注入供结束分支构造 RUN_FINISHED outcome；
        # ready 路径不消费该字段。
        next_interrupt = getattr(resume_result, "next_interrupt", None) if resume_result is not None else None

        # 5. body 构造（合并后的 state 直接放进 body["state"]）
        body = {
            "thread_id": self.thread_id,
            "run_id": messages[-1].id or uuid.uuid4().hex,
            "state": preprocessed["state"],
            "messages": agui_messages,
            "stream_input": preprocessed["stream_input"],  # 11.9: stream_input 通过 input 传递
            "next_interrupt": next_interrupt,  # lw4：未就绪下一张 pending 卡（ready 路径为 None）
        }
        if forwarded_props:
            body["forwarded_props"] = forwarded_props

        # 6. agent_input 构造（不需要 model_copy）
        agent_input = AgentInput(**body)

        # 7. config 构造：fork merge 到 cfg
        fork = preprocessed["fork"]
        if fork:
            merged_cfg = {
                **cfg,
                "configurable": {
                    **cfg.get("configurable", {}),
                    **fork.get("configurable", {}),
                },
            }
        else:
            merged_cfg = cfg

        # 8. agui_entry 构造（传 merged_cfg）
        agui_entry = AidevAGUIAgent(
            name="test_agui_agent",
            graph=agent_e,
            event_handler=self.event_handler,
            config=merged_cfg,
            tools={each.name: each for each in self.tools} if self.tools else {},
            cancel_checker=make_cancel_checker(self.thread_id, agent_input.run_id),
            mcp_fetch_failures=getattr(self, "mcp_fetch_failures", []) or [],
            approve_result=approve_result,
            approval_interrupts=approval_interrupts,
            ask_user_question_interrupts=ask_user_question_interrupts,
            run_end_extras_hook=build_artifacts_generated_hook(self.resource_manager, self.executor_info),
            # D-11 装配收编：复用 execute() 入口惰性构造的 processor 注入 AidevAGUIAgent
            # （不再现造；ItsmTicketCreator 由 dispatch_interrupts 内部按 ctx 现构造，
            # RM 在 core/ag_ui 层持有合法，供流结束 processor 的 ApprovalHandler.prepare
            # 建 ITSM 工单，取代 InterruptDispatcher（44 D-02））。
            interrupt_processor=self.interrupt_processor,
        )

        return self._stream_with_queue(
            agui_entry,
            agent_input,
            queue_thread_id=self.thread_id,
            background_only=execute_kwargs.background_only,
            agent_e=agent_e,
            cfg=merged_cfg,
            resume=bool(execute_kwargs.resume),
            attach_only=execute_kwargs.stream_mode == "attach",
            total_timeout=execute_kwargs.invoke_timeout,
        )

    def _stream_with_queue(
        self,
        agui_entry: AidevAGUIAgent,
        agent_input: AgentInput,
        queue_thread_id: str | None = None,
        background_only: bool = False,
        agent_e: Runnable | None = None,
        cfg: RunnableConfig | None = None,
        resume: bool = False,
        attach_only: bool = False,
        total_timeout: int | float | None = None,
    ) -> Generator[Any, None, None]:
        """使用队列处理器缓存流式请求，支持断点续传。

        所有事件都由后台 producer 写入消息处理器。producer 会在 RUN_STARTED
        入队后立即 flush，既保持初始化事件顺序，也确保客户端在首帧前断开时
        producer 仍能继续执行并供后续请求 replay。

        恢复事件的 Trace 上下文在入口同步捕获；队列和 producer 仍延迟到消费时启动。
        """
        from aidev_agent.services.resume_events import resume_events_for

        resume_items = (agent_input.forwarded_props or {}).get("command", {}).get("resume") or []
        observer = (
            resume_events_for(
                self.resource_manager,
                session_code=getattr(self.event_handler, "session_code", "") or "",
                thread_id=agent_input.thread_id,
                turn_id=getattr(self.event_handler, "turn_id", "") or "",
                resume=resume_items if isinstance(resume_items, list) else [resume_items],
            )
            if resume and not attach_only
            else None
        )

        def stream() -> Generator[Any, None, None]:
            # 不把 observer 放进惰性生成器：HTTP 入口 span 可能在首次消费前已经结束。
            helper = GeneratorStreamingHelper(
                thread_id=queue_thread_id or agent_input.thread_id,
                defer_cleanup_on_complete=background_only,
                producer_observer=observer,
            )
            run_id = agent_input.run_id or self.thread_id
            cancel_event = helper.prepare_run(run_id)
            producer = self._build_resume_aware_producer(
                agui_entry,
                agent_input,
                agent_e=agent_e,
                cfg=cfg,
                resume=resume,
                total_timeout=total_timeout,
                producer_observer=observer,
            )
            yield from helper.stream(
                producer,
                # replay 模式下由 producer 在 EOD 写入并 flush 成功后更新会话终态；
                # 消费者中断不会影响最终状态收敛。
                on_complete=partial(self._on_complete, finalize_session=True),
                event_handler=self.event_handler,
                expected_run_id=run_id,
                cancel_event=cancel_event,
                attach_only=attach_only,
            )

        return stream()

    def _build_resume_aware_producer(
        self,
        agui_entry: AidevAGUIAgent,
        agent_input: AgentInput,
        agent_e: Runnable | None,
        cfg: RunnableConfig | None,
        resume: bool,
        total_timeout: int | float | None = None,
        producer_observer=None,
    ) -> Generator[Any, None, None]:
        """构造「resume 感知」的生产者生成器（方案 B 兜底入口）。

        生成器惰性执行：仅当队列处理器决定启动新生产者（即队列已空、错过方案 A 的接管
        窗口）时才会被拉取。届时若这是一次 resume 且对应 graph 已处于终态，则改为从
        checkpoint 重放完整 turn（见 :meth:`_build_terminal_resume_replay`），避免对终态图
        跑空 astream 只拿到空快照；否则回退到正常的 astream 流。

        队列内仍有历史时（方案 A 的接管窗口内），队列处理器走 restore 分支、不会拉取此
        生成器，因此不会触发多余的 ``get_state`` 查询。
        """

        def _gen() -> Generator[Any, None, None]:
            if resume and agent_e is not None and cfg is not None and agent_input.thread_id:
                replay = self._build_terminal_resume_replay(agui_entry, agent_input, agent_e, cfg)
                if replay is not None:
                    if producer_observer is not None:
                        producer_observer.enabled = False
                    logger.info(
                        "[ResumeReplay] graph terminal, replay persisted turn from checkpoint "
                        "(scheme B fallback), thread_id=%s",
                        agent_input.thread_id,
                    )
                    try:
                        yield from replay
                    finally:
                        run_coro_sync(self._aclose_chat_models)
                    return
            yield from async_to_sync_generator(
                agui_entry.run(agent_input),
                async_finalizer=self._aclose_chat_models,
                total_timeout=total_timeout,
            )

        return _gen()

    def _build_terminal_resume_replay(
        self,
        agui_entry: AidevAGUIAgent,
        agent_input: AgentInput,
        agent_e: Runnable,
        cfg: RunnableConfig,
    ) -> Generator[Any, None, None] | None:
        """方案 B：resume 的 graph 已终态时，从 checkpoint 重放完整 turn。

        终态判定与 ``LangGraphAGUIAgent`` 收尾逻辑同源：``state.next`` 为空且首个 task 无
        pending interrupt。命中终态则返回「编码后的事件字符串生成器」（RUN_STARTED →
        STATE_SNAPSHOT + MESSAGES_SNAPSHOT → RUN_FINISHED）；非终态、查询失败或无可重放
        消息时返回 ``None``，由调用方回退正常 astream。

        说明：重放仅用于把已落库内容交付前端，**不**再次触发 event_handler 落库（后台
        drain 阶段的 BaseSessionWriter 已持久化该 turn），故绕过 ``_dispatch_event``。
        """
        thread_id = agent_input.thread_id
        try:
            replay_cfg = dict(cfg)
            replay_cfg["configurable"] = {**cfg.get("configurable", {}), "thread_id": thread_id}
            state = agent_e.get_state(replay_cfg)
        except Exception:
            logger.warning(
                "[ResumeReplay] get_state failed, fallback to astream, thread_id=%s",
                thread_id,
                exc_info=True,
            )
            return None

        tasks = state.tasks if state else None
        interrupts = []
        for task in tasks or []:
            interrupts.extend(getattr(task, "interrupts", None) or [])
        next_nodes = state.next or ()
        is_terminal = len(next_nodes) == 0 and not interrupts
        if not is_terminal:
            logger.info(
                "[ResumeReplay] graph not terminal (next=%s, interrupts=%d), use normal resume astream, thread_id=%s",
                next_nodes,
                len(interrupts),
                thread_id,
            )
            return None

        state_values = state.values if state and state.values else {}
        messages = state_values.get("messages", []) if isinstance(state_values, dict) else []
        non_system = [m for m in messages if not isinstance(m, SystemMessage)]
        if not non_system:
            logger.info(
                "[ResumeReplay] terminal graph has no replayable messages, fallback to astream, thread_id=%s",
                thread_id,
            )
            return None

        return agui_entry.build_terminal_replay_stream(agent_input, non_system)

    def _on_complete(self, *, finalize_session: bool = True):
        if finalize_session and self.event_handler and hasattr(self.event_handler, "set_streaming_finished"):
            self.event_handler.set_streaming_finished()
        # 流式执行结束后释放资源
        self.release_resources()

    def migration_v1(self) -> None:
        """兼容 v1 旧构造参数，统一迁移到当前运行时协议。"""
        if not isinstance(self.model_context_options, ModelContextSettings):
            self.model_context_options = migration_model_context_options_from_agent_options_v1(self.agent_options)
        if not isinstance(self.knowledge_query_options, KnowledgeSettings):
            self.knowledge_query_options = migration_knowledge_query_options_from_agent_options_v1(self.agent_options)
        if not isinstance(self.chat_model_non_thinking, BaseChatModel):
            self.chat_model_non_thinking = migration_chat_model_non_thinking_from_non_thinking_llm_v1(
                self.non_thinking_llm,
            )

    def _get_agent(
        self, messages: list[BaseMessage], *, execute_kwargs: ExecuteKwargs
    ) -> tuple[Runnable, RunnableConfig]:
        """
        由于在流式的时候，Response 立即返回会导致 trace 断掉，所以在_get_agent中添加 execute_kwargs
        execute_kwargs 有携带了 trace 上下文，以便于不要让 trace 断掉
        """
        if self.knowledge_bases:
            self.knowledge_query_options.knowledge_bases = self.knowledge_bases
        if self.knowledges:
            self.knowledge_query_options.knowledge_items = self.knowledges
        logger.info(f"callbacks: {self.callbacks}")
        return self.agent_cls.get_agent_executor(
            llm=self.chat_model,
            non_thinking_llm=self.chat_model_non_thinking or self.chat_model,
            fast_llm=self.chat_model_fast,
            extra_tools=self.tools,
            chat_history=messages[:-1],
            tool_execution_interval=self.TOOL_EXECUTION_INTERVAL,
            support_vision=self.support_vision,
            file_store=self.file_store,
            callbacks=self.callbacks,
            knowledge_query_options=self.knowledge_query_options,
            model_context_options=self.model_context_options,
            skills=self.skills,
            subagent_specs=self.subagent_specs,
            executor_info=self.executor_info,
            execute_kwargs=execute_kwargs,
            checkpointer=self.checkpointer,
            resource_manager=self.resource_manager,
            runtime_backend_resolver=self.runtime_backend_resolver,
        )

    @staticmethod
    def _normalize_file_resource_path(resource: dict) -> str:
        raw_path = resource.get("path") or resource.get("outputId") or resource.get("id")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise SandboxFileInvalidArgumentError("文件资源缺少 path")

        path = raw_path.strip().replace("\\", "/")
        mount_prefix = f"{SESSION_VOLUME_PATH}/"
        if path.startswith(mount_prefix):
            path = path[len(mount_prefix) :]
        elif path.startswith(("/", "$")):
            raise SandboxFileInvalidArgumentError(f"文件资源 path 不属于会话 PV: {raw_path}")
        if any(ord(char) < 32 for char in path):
            raise SandboxFileInvalidArgumentError(f"文件资源 path 含控制字符: {raw_path}")
        if ".." in path.split("/"):
            raise SandboxFileInvalidArgumentError(f"文件资源 path 非法: {raw_path}")

        normalized = posixpath.normpath(path)
        if normalized in {"", "."}:
            raise SandboxFileInvalidArgumentError("文件资源 path 不能为空")
        return normalized

    @staticmethod
    def _is_image_resource(resource: dict, path: str) -> bool:
        mime_type = str(resource.get("mime_type") or resource.get("mime") or resource.get("content_type") or "").lower()
        if mime_type:
            return mime_type.startswith("image/")
        return posixpath.splitext(path)[1].lower() in SESSION_UPLOAD_IMAGE_EXTENSIONS

    @staticmethod
    def _find_binary_by_path(content: list[dict], path: str) -> dict | None:
        """按 PV 相对路径找到对应的展示用 binary。"""
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "binary":
                continue
            if str(item.get("id") or item.get("path") or "") == path:
                return item
        return None

    @staticmethod
    def _build_file_reference_context(paths: list[str]) -> str:
        """构造当前用户精确引用的会话文件路径说明。"""
        return "用户本轮引用了以下会话文件，请优先基于这些精确路径处理：\n" + "\n".join(
            f"- {SESSION_VOLUME_PATH}/{path}" for path in paths
        )

    def _build_llm_history(self) -> list[ChatPrompt]:
        """构造仅供本轮模型调用使用的历史副本。"""
        chat_history = [prompt.model_copy(deep=True) for prompt in self.chat_history or []]
        if not self.file_resources:
            return chat_history

        last_user_prompt = next(
            (prompt for prompt in reversed(chat_history) if prompt.role == PromptRole.USER.value),
            None,
        )
        if last_user_prompt is None:
            return chat_history

        image_paths = []
        referenced_paths = []
        seen_paths = set()
        for resource in self.file_resources:
            path = self._normalize_file_resource_path(resource)
            if path in seen_paths:
                continue
            seen_paths.add(path)
            referenced_paths.append(path)
            if self._is_image_resource(resource, path):
                image_paths.append(path)
        if not referenced_paths:
            return chat_history

        if isinstance(last_user_prompt.content, str):
            content: list[dict] = [{"type": "text", "text": last_user_prompt.content}]
        elif isinstance(last_user_prompt.content, list):
            content = list(last_user_prompt.content)
        else:
            return chat_history

        content.append(
            {
                "type": "text",
                "text": self._build_file_reference_context(referenced_paths),
            }
        )

        if image_paths:
            file_service = SandboxPvFileService(
                resource_manager=self.resource_manager,
                executor_info=self.executor_info or {},
            )
            for path in image_paths:
                url_data = file_service.get_download_url(
                    session_code=self.thread_id,
                    path=path,
                    expires_in=IMAGE_DOWNLOAD_URL_EXPIRES_IN,
                )
                image_url = url_data.get("download_url")
                if not image_url:
                    raise SandboxFileServerError(f"文件 {path} 未返回 download_url")
                existing = self._find_binary_by_path(content, path)
                if existing is not None:
                    existing["url"] = image_url
                else:
                    content.append({"type": "image_url", "image_url": {"url": image_url}})
        last_user_prompt.content = content
        return chat_history


class ChatAgentBuilder:
    """``ChatCompletionAgent`` 装配器

    把原 ``AgentInstanceFactory`` 中所有 Chat 专属装配方法收敛在这里：

    - 模型 / 工具 / 知识 / 技能装配
    - 聊天历史构建（lossless 单账本承接，LLM 侧过滤归 convert 链）
    - executor_info / checkpointer 取值
    - model_context_options / knowledge_query_options 取值
    - handle_agent_switch（替换 system 消息）
    - specific_resources 提取（``_handle_last_human_message``）

    持有 :class:`AgentBuildContext` 引用：
    - 主智能体配置直接读 ``self.ctx.agent_config``（已在 ctx 装配阶段一次性预读）。
    - 通用字段读 ``self.ctx.{resource_manager, username, agent_code, session_context_data, switch_agent}``。
    - Chat 专属字段读 ``self.ctx.chat.{temperature, max_tokens, auth_headers, checkpointer, ...}``。
    """

    def __init__(self, ctx: AgentBuildContext):
        self.ctx = ctx
        self._specific_resources: list[dict] = []
        self._file_resources: list[dict] = []
        self._mcp_fetch_failures: list[dict] = []
        self._executor_info: dict | None = None
        self._runtime_backend_resolver: Any | None = None
        # 装配前先从最后一条 user 消息提取 specific_resources，供 build_tools / build_knowledge_bases 过滤
        self._handle_last_human_message(ctx.session_context_data)

    @property
    def mcp_fetch_failures(self) -> list[dict]:
        """MCP 工具拉取失败记录，由 ``build_tools`` 写入"""
        return self._mcp_fetch_failures

    @property
    def file_resources(self) -> list[dict]:
        """返回当前用户消息中声明的文件资源。"""
        return list(self._file_resources)

    def build_runtime_backend_resolver(self) -> RuntimeBackendResolver:
        """构造 RuntimeBackendResolver（每会话一个，scoping 归 RuntimeBackendDeferManager，决策 1）。

        功能开关 ``BKAI_RUNTIME_SANDBOX_DEFERRED_DESTROY_ENABLED``：
            开启时使用``defer_manager`` 模块的进程级默认单例 ``default_runtime_backend_defer_manager``（延迟销毁 + 会话级复用，start 幂等多请求安全）；
            关闭时构造纯路由 resolver（release 立即销毁）
        agent_code/session_code 经构造参数注入
        任一为空时 resolver 内部强制 create-only —— 无 scoping 的复用会命中其他会话/智能体的沙箱，实质导致越权。
        """
        defer_manager = None
        if settings.BKAI_RUNTIME_SANDBOX_DEFERRED_DESTROY_ENABLED and self.ctx.agent_code and self.ctx.session_code:
            defer_manager = default_runtime_backend_defer_manager
        resolver = RuntimeBackendResolver(
            default_runtime="local",
            defer_manager=defer_manager,
            agent_code=self.ctx.agent_code,
            session_code=self.ctx.session_code,
        )
        self._runtime_backend_resolver = resolver
        return resolver

    # ---------- 公共：装配方法（被 ChatCompletionAgent.build 调用） ----------

    def build_chat_model(self) -> ChatModelRunnable:
        """构建聊天模型"""
        config = self.ctx.agent_config
        chat = self.ctx.chat or ChatBuildExtras()

        if not config.chat_model:
            raise ValueError("请配置智能体默认模型并重新发布")

        kwargs: dict[str, Any] = {
            "model": config.chat_model,
            "fallback_model": config.fallback_model,
            "base_url": settings.LLM_GW_ENDPOINT,
        }

        temperature = chat.temperature if chat.temperature is not None else config.temperature
        if temperature is not None:
            kwargs["temperature"] = temperature

        max_tokens = chat.max_tokens if chat.max_tokens is not None else config.max_tokens
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if chat.auth_headers:
            kwargs["auth_headers"] = chat.auth_headers

        if chat.default_headers:
            kwargs["default_headers"] = chat.default_headers

        if self.ctx.session_code:
            kwargs["session_code"] = self.ctx.session_code

        retry_strategy = chat.retry_strategy or settings.LLM_RETRY_STRATEGY
        kwargs["retry_strategy"] = retry_strategy
        if retry_strategy == "sdk":
            kwargs["max_retries"] = 0

        return ChatModel.get_setup_instance(**kwargs)

    def build_chat_model_non_thinking(self) -> BaseChatModel | None:
        """构建非思考模型 (返回 ChatModel 实例)"""
        model_name = self.ctx.agent_config.non_thinking_llm
        if not model_name:
            return None
        kwargs: dict[str, Any] = {
            "model": model_name,
            "base_url": settings.LLM_GW_ENDPOINT,
        }
        chat = self.ctx.chat or ChatBuildExtras()
        if chat.auth_headers:
            kwargs["auth_headers"] = chat.auth_headers
        if chat.default_headers:
            kwargs["default_headers"] = chat.default_headers

        retry_strategy = chat.retry_strategy or settings.LLM_RETRY_STRATEGY
        kwargs["retry_strategy"] = retry_strategy
        if retry_strategy == "sdk":
            kwargs["max_retries"] = 0

        return ChatModel.get_setup_instance(**kwargs)

    def build_chat_model_fast(self) -> BaseChatModel | None:
        """构建快速/轻量模型（用于 quality_gate 判断 LLM 等辅助任务）。

        当前从 ``agent_config.fast_llm`` 读取模型名（与
        ``build_chat_model_non_thinking`` 读 ``agent_config.non_thinking_llm`` 对称），
        ``agent_config.fast_llm`` 由 resource_manager 填充，未配置时回退到
        ``non_thinking_llm`` / ``llm_code``。
        """
        model_name = self.ctx.agent_config.fast_llm
        base_url = settings.LLM_GW_ENDPOINT
        if not model_name or not base_url:
            return None
        kwargs: dict[str, Any] = {
            "model": model_name,
            "base_url": base_url,
        }
        chat = self.ctx.chat or ChatBuildExtras()
        if chat.auth_headers:
            kwargs["auth_headers"] = chat.auth_headers
        if chat.default_headers:
            kwargs["default_headers"] = chat.default_headers

        retry_strategy = chat.retry_strategy or settings.LLM_RETRY_STRATEGY
        kwargs["retry_strategy"] = retry_strategy
        if retry_strategy == "sdk":
            kwargs["max_retries"] = 0

        return ChatModel.get_setup_instance(**kwargs)

    def build_chat_history(self, session_context_data: List[dict]) -> List[ChatPrompt]:
        """构建聊天历史：无损承接 session_context_data（A 源适配层输出）为唯一历史账本。

        不做任何过滤或改写：system 展示类、思考内容、空 content、半成品记录全部原样保留，
        供快照忠实转换；LLM 侧过滤由 convert 链（_build_llm_history_view / status 过滤 /
        轮数截断）在副本上承担。
        """
        return [ChatPrompt.model_validate(each) for each in (session_context_data or [])]

    def build_non_thinking_llm(self) -> str | None:
        """构建非思考模型

        .. deprecated::
            Use :meth:`build_chat_model_non_thinking` instead.
        """
        warnings.warn(
            "build_non_thinking_llm is deprecated, use build_chat_model_non_thinking instead",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.ctx.agent_config.non_thinking_llm

    def build_knowledge_bases(self) -> List[dict]:
        """构建知识库"""
        config = self.ctx.agent_config
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
            f"ChatAgentBuilder: config knowledgebase_ids->[{config.knowledgebase_ids}], "
            f"specific_resources->[{specific_resources}]"
        )
        return [self.ctx.resource_manager.retrieve_knowledgebase(_id) for _id in knowledgebase_ids]

    def build_knowledge_items(self) -> List[dict]:
        """构建知识条目"""
        config = self.ctx.agent_config
        return [self.ctx.resource_manager.retrieve_knowledge(_id) for _id in config.knowledge_ids]

    def build_tools(self) -> List[Any]:
        """构建工具"""
        config = self.ctx.agent_config
        specific_mcps = [each.get("code") for each in self._specific_resources if each.get("type") == "mcp"]
        if specific_mcps:
            mcp_server_config = {each: config.mcp_server_config.get(each) for each in specific_mcps}
        else:
            mcp_server_config = config.mcp_server_config
        mcp_result = self.ctx.resource_manager.construct_mcp(
            mcp_config=mcp_server_config,
            username=self.ctx.username,
            executor_info=self._executor_info,
        )
        self._mcp_fetch_failures = [f.model_dump() for f in mcp_result.fetch_failures]
        logger.info(f"ChatAgentBuilder: mcp_server_config->[{mcp_server_config}]")
        specific_tools = [each.get("code") for each in self._specific_resources if each.get("type") == "tool"]
        if specific_tools:
            tool_codes = [each for each in config.tool_codes if each in specific_tools]
        else:
            tool_codes = config.tool_codes
        logger.info(f"ChatAgentBuilder: tool_codes->[{tool_codes}]")
        tools = [
            self.ctx.resource_manager.construct_tool(
                tool_code,
                username=self.ctx.username,
                executor_info=self._executor_info,
            )
            for tool_code in tool_codes
        ] + mcp_result.tools
        self._apply_tool_approval_settings(tools)
        return tools

    def _apply_tool_approval_settings(self, tools: list[Any]) -> None:
        approval_items = self._normalize_tool_approval_bindings()
        logger.info("[ToolApproval] ========== _apply_tool_approval_settings 被调用 ==========")
        logger.info("[ToolApproval] 归一化审批配置: %s", approval_items)
        logger.info("[ToolApproval] 工具对象 id 列表: %s", [(getattr(t, "name", ""), id(t)) for t in tools])

        if not approval_items:
            logger.info("[ToolApproval] 没有需要审批的工具")
            return

        for tool in tools:
            metadata = getattr(tool, "metadata", None) or {}
            tool_name = getattr(tool, "name", "")
            logger.info("[ToolApproval] 检查工具: %s, metadata: %s", tool_name, metadata)
            matched = self._match_approval_item(metadata, tool_name, approval_items)
            if not matched:
                logger.info("[ToolApproval] 工具 %s 未匹配到审批配置", tool_name)
                continue
            logger.info("[ToolApproval] 工具 %s 匹配到审批配置: %s", tool_name, matched)
            target_type = matched.get("tool_type") or "tool"
            metadata["approval"] = {
                **matched,
                "tool_code": metadata.get("tool_code") or tool_name,
                "tool_name": metadata.get("tool_name") or tool_name,
                "tool_type": target_type,
                "target": {
                    "type": target_type,
                    "id": metadata.get("tool_id"),
                    "name": tool_name,
                    "display_name": metadata.get("tool_name") or tool_name,
                    "code": metadata.get("tool_code") or tool_name,
                    "mcp_name": metadata.get("mcp_name"),
                    "skill_name": metadata.get("skill_name"),
                },
            }
            tool.metadata = metadata
            logger.info("[ToolApproval] 工具 %s 已设置 approval metadata: %s", tool_name, metadata["approval"])

    def _normalize_tool_approval_bindings(self) -> list[dict[str, Any]]:
        config = self.ctx.agent_config
        approval_settings = getattr(config, "approval_settings", None) or {}

        strategy_index = self._build_approval_strategy_index(approval_settings)

        # 从 config.resources 构建 id→code 映射，用于将 binding 中的整数 id 解析为字符串 code
        resource_id_map = self._build_resource_id_map(getattr(config, "resources", None) or [])

        bindings: list[dict[str, Any]] = []

        # 从 approval_settings.bindings 读取绑定关系
        # 字段命名与平台保持一致：approval_strategy_id / approval_enabled
        # 审批人列表不直接出现在 binding 中，需要通过 approval_strategy_id 反查 strategies 拿 approvers
        for binding_data in approval_settings.get("bindings", []) or []:
            if not isinstance(binding_data, dict):
                continue
            approval_enabled = binding_data.get("approval_enabled") is True
            strategy_id = str(binding_data.get("approval_strategy_id") or "").strip()
            if not approval_enabled or not strategy_id:
                continue
            strategy = strategy_index.get(strategy_id)
            if strategy is None:
                logger.warning(
                    "[ToolApproval] 绑定引用了不存在的策略: approval_strategy_id=%s, binding=%s",
                    strategy_id,
                    binding_data,
                )
                continue
            resource_type = binding_data.get("resource_type", "")
            tool_type = {"tool": "tool", "mcp_tool": "mcp"}.get(resource_type, resource_type)
            binding = {
                "resource_type": resource_type,
                "tool_type": tool_type,
                "approval_enabled": True,
                "approval_strategy_id": strategy_id,
                "approval_name": strategy.get("approval_name", ""),
                "approvers": strategy.get("approvers") or [],
                "strategy": strategy,
            }
            if resource_type == "tool":
                tool_id = binding_data.get("tool_id")
                binding["id"] = tool_id
                # 优先从 resources 映射解析 tool_code，回退到 binding_data 中的字段
                tool_code = resource_id_map.get(("tool", tool_id)) if tool_id else None
                binding["tool_code"] = tool_code or binding_data.get("tool_code") or tool_id
                binding["tool_name"] = tool_code or binding_data.get("tool_name") or tool_id
            elif resource_type == "mcp_tool":
                mcp_id = binding_data.get("mcp_id")
                binding["mcp_id"] = mcp_id
                # 优先使用平台 runtime binding 下发的 mcp_name/mcp_code，resources 映射仅作兜底
                mcp_code = binding_data.get("mcp_code") or (resource_id_map.get(("mcp", mcp_id)) if mcp_id else None)
                binding["mcp_code"] = mcp_code
                binding["mcp_name"] = binding_data.get("mcp_name") or mcp_code
                binding["tool_code"] = binding_data.get("mcp_tool_name", "")
                binding["tool_name"] = binding_data.get("mcp_tool_name", "")
            bindings.append(binding)

        return bindings

    @staticmethod
    def _build_approval_strategy_index(approval_settings: dict[str, Any]) -> dict[str, dict[str, Any]]:
        strategies = approval_settings.get("strategies", []) if isinstance(approval_settings, dict) else []
        strategy_index: dict[str, dict[str, Any]] = {}
        for strategy in strategies or []:
            strategy_id = strategy.get("strategy_id")
            if strategy_id:
                strategy_index[str(strategy_id)] = strategy
        return strategy_index

    @staticmethod
    def _build_resource_id_map(resources: list[dict]) -> dict[tuple[str, int], str]:
        """从 resources 列表构建 (type, id) → code 映射，用于将 binding 中的整数 id 解析为字符串 code。"""
        id_map: dict[tuple[str, int], str] = {}
        for r in resources:
            if not isinstance(r, dict):
                continue
            r_type = r.get("type")
            r_id = r.get("id")
            r_code = r.get("code")
            if r_type and r_id is not None and r_code:
                id_map[(r_type, r_id)] = r_code
        return id_map

    @staticmethod
    def _match_approval_item(metadata: dict, tool_name: str, approval_items: list[dict]) -> dict | None:
        tool_code = metadata.get("tool_code") or tool_name
        tool_id = metadata.get("tool_id")
        mcp_name = metadata.get("mcp_name")
        for item in approval_items:
            resource_type = item.get("resource_type") or item.get("tool_type")
            if resource_type == "tool":
                if item.get("id") and item.get("id") == tool_id:
                    return item
                if item.get("tool_code") and item.get("tool_code") == tool_code:
                    return item
                if item.get("tool_name") and item.get("tool_name") in {tool_name, tool_code}:
                    return item
            elif resource_type in {"mcp_tool", "mcp"}:
                if item.get("mcp_name") and item.get("mcp_name") != mcp_name:
                    continue
                if item.get("tool_name") and item.get("tool_name") in {tool_name, tool_code}:
                    return item
                if item.get("tool_code") and item.get("tool_code") == tool_code:
                    return item
                if item.get("mcp_code") and item.get("mcp_code") == mcp_name:
                    expected_tool_code = item.get("code") or item.get("tool_code")
                    if not expected_tool_code or expected_tool_code == tool_code:
                        return item
            if item.get("code") and item.get("code") == tool_code:
                return item
            if item.get("tool_code") and item.get("tool_code") == tool_code:
                return item
        return None

    def build_skills(self) -> list | None:
        """构建关联技能"""
        return self.ctx.agent_config.related_skills

    def build_subagents(self, agent_code: str) -> list[Any]:
        """构建子 Agent 规格，基于 ping 检查动态选择 BKAI/LOCAL 后端。

        - 始终构造 Client 并通过 ping 判断远端可达性；
          api_url 有值时传入 endpoint，否则由 get_client 自动构建
        - BKAI 路径：仅构造 `AgentSpec(params={"agent_code", "client"})` 远端服务可用，走 API 网关直调，无需构造 agent_cls/ctx
        - LOCAL 路径：通过 `resource_manager.get_agent_config(agent_code=child_agent_code, version=None)` 获取子 Agent 配置
          每条子 Agent 产出 ``AgentSpec(params={"agent_cls", "ctx"})``，
          让 LocalBackend 在运行时 ``agent_cls()`` 创建实例再 ``.build(ctx)``
        - 子 Agent 保留自身 ``related_agents``，支持 ``max_spawn_depth > 1``；
          嵌套深度由 ``ExecuteKwargs.spawn_depth`` 和 ``_check_nesting`` 控制

        Args:
            agent_code: 父 Agent 的 agent_code（仅用于日志输出，与子 Agent 无关）

        Returns:
            ``list[AgentSpec]``，每条对应一个子 Agent；related_agents 为空时返回空列表
        """
        parent_config = self.ctx.agent_config
        related_agents = parent_config.related_agents if parent_config else []
        logger.info(
            "build_subagents: parent_agent_code=%s, related_agents count=%d",
            agent_code,
            len(related_agents),
        )

        # 关键设计：所有 Agent（父 + 所有子）共享同一 checkpointer 实例（Phase 16-fix）
        # 理由：
        # - member 模式依赖 LangGraph checkpointer + thread_id 续接多轮对话
        # - 若子 Agent 每次新建 MemorySaver，每次 chat_completion 构建的 child 只能看到
        #  自己这一个 MemorySaver 的历史；而真正的期望是「同一 thread_id 跨父子/成员的
        #  state 在同一 checkpointer 存取」
        # - 父 ctx.chat.checkpointer 在 factory.py:170 处一定非空（fallback 到 MemorySaver），
        #  此处直接复用；仅在极端情况下（ctx.chat 为 None 或 checkpointer 缺失）
        #  fallback，新建实例也仅对当前这一批 subagents 生效
        parent_chat = self.ctx.chat
        shared_checkpointer = parent_chat.checkpointer
        specs: list[Any] = []
        for agent in related_agents:
            child_agent_code = agent.get("agent_code", "")
            if not child_agent_code:
                continue

            # ★ 始终构造 Client 并通过 ping 判断远端可达性
            # api_url 有值时传入 endpoint，否则由 get_client 自动构建
            # validate_endpoint=True：若平台提供的 url 不含环境，则由 get_client 自动补全
            access_token = (self._executor_info or {}).get("access_token", "")
            api_url: Any = agent.get("api_url", "")

            bkai_client = BkAgentApi.get_client(
                agent_code=child_agent_code,
                access_token=access_token,
                endpoint=api_url,
                validate_endpoint=True,
            )
            try:
                bkai_client.ping()
                is_remote = True
                logger.info("build_subagents: ping %s → available, is_remote", child_agent_code)
            except Exception:
                is_remote = False
                logger.info("build_subagents: ping %s → unavailable, fallback to LOCAL", child_agent_code)

            if is_remote:
                # BKAI 路径：只需 client（远端服务可用，走 API 网关直调）
                specs.append(
                    AgentSpec(
                        name=child_agent_code,
                        description=agent.get("description") or agent.get("agent_name", ""),
                        backend_type=AgentBackendType.BKAI,
                        params={
                            "client": bkai_client,  # 注入已构造好的 Client 实例
                            "resource_manager": self.ctx.resource_manager,
                            "caller_bk_app_code": self.ctx.agent_code,
                        },
                    )
                )
            else:
                # LOCAL 路径：构造 agent_cls + ctx（由 LocalBackend 运行时实例化并 build）
                # 1. 取子 Agent 配置（version=None → 最新版；子 agent_code 不继承父 version 语义）
                child_config = self.ctx.resource_manager.get_agent_config(agent_code=child_agent_code, version=None)

                # 2. 保留子 config 的 related_agents，支持 max_spawn_depth > 1
                #    （Phase 33 起不再递归清空；LocalBackend 运行时会按 max_spawn_depth 控制是否继续 spawn）
                # child_config 直接使用，不修改 related_agents

                # 3. 构造子 ChatBuildExtras：与父共享 agent_cls/auth_headers/checkpointer；
                #   仅 callbacks 隔离避免事件双发
                child_chat = ChatBuildExtras(
                    agent_cls=parent_chat.agent_cls if parent_chat is not None else None,
                    callbacks=[],  # 子 Agent 不继承父 callbacks，避免事件双发
                    auth_headers=parent_chat.auth_headers if parent_chat is not None else None,
                    temperature=None,  # 由子 agent_config.temperature 决定（build_chat_model 读取）
                    max_tokens=None,  # 同上
                    retry_strategy=parent_chat.retry_strategy if parent_chat is not None else None,
                    checkpointer=shared_checkpointer,  # 共享父 checkpointer，使 member 模式可跨调用续接
                )

                # 4. 构造子 AgentBuildContext
                child_ctx = AgentBuildContext(
                    agent_code=child_agent_code,
                    agent_type=AgentType.CHAT,
                    agent_config=child_config,
                    resource_manager=self.ctx.resource_manager,  # 复用父 rm
                    session_code=None,  # 子 Agent 不继承父 session_code；member 模式由 LocalBackend 运行时注入
                    username=self.ctx.username,  # 复用父 username（日志/审计）
                    session_context_data=[],  # 子 Agent 不继承父会话历史
                    switch_agent=False,  # 子 Agent 不走切换逻辑
                    event_handler=AGUISessionWriter(
                        session_code="",
                        client=resource_manager().get_client(),
                        username=self.ctx.username,
                        turn_id="",
                    ),  # 子 Agent 使用独立 AGUISessionWriter，session_code 由 LocalBackend 运行时注入
                    chat=child_chat,
                    flow=None,
                    extra={},
                )

                # 4. 构造子 Agent 规格（agent_cls + ctx，由 LocalBackend 运行时实例化并 build）
                specs.append(
                    AgentSpec(
                        name=child_agent_code,
                        description=agent.get("description") or agent.get("agent_name", ""),
                        backend_type=AgentBackendType.LOCAL,
                        params={
                            "agent_cls": ChatCompletionAgent,
                            "ctx": child_ctx,
                            "caller_bk_app_code": self.ctx.agent_code,
                        },
                    )
                )
            logger.info("build_subagents: ping %s → available, is_remote %s", child_agent_code, str(specs))
        return specs

    def build_knowledge_query_options(self) -> KnowledgeSettings:
        """从 AgentConfig 构建 KnowledgeSettings；新协议为空时兼容旧 agent_options。
        经过评估，现在模型通过 Agentic RAG 进行知识查询能力已经可以媲美两步 RAG
        以下是现在的开启方式：
        对于 enable_knowledge_node:
        1. 有环境变量 ENABLE_KNOWLEDGE_NODE 的时候， 以环境变量为准，仅当 ENABLE_KNOWLEDGE_NODE=true(小写)的时候为 True
        2. 如果有 self._specific_resources 有 knowledgebase, 开启两步 RAG (这表明用户有意图需要使用两步 RAG)
        3. 其他情况为默认值(当前为 False)

        对于 ENABLE_AGENTIC_RAG_TOOL:
        1. 有环境变量 ENABLE_AGENTIC_RAG_TOOL 的时候， 以环境变量为准，仅当 ENABLE_AGENTIC_RAG_TOOL=true(小写)的时候为 True
        2. 其他情况为默认值(当前为 True)
        """
        data = self.ctx.agent_config.knowledge_query_options_data
        if data:
            options = KnowledgeSettings.model_validate(data)
        else:
            options = migration_knowledge_query_options_from_agent_options_v1(self.ctx.agent_config.agent_options)

        ekn_env = os.getenv("ENABLE_KNOWLEDGE_NODE")
        if ekn_env:
            options.enable_knowledge_node = ekn_env.lower() == "true"
        elif any(r.get("type") == "knowledgebase" for r in self._specific_resources):
            options.enable_knowledge_node = True

        eart_env = os.getenv("ENABLE_AGENTIC_RAG_TOOL")
        if eart_env:
            options.enable_agentic_rag_tool = eart_env.lower() == "true"

        return options

    def build_model_context_options(self) -> ModelContextSettings | None:
        """从 AgentConfig 构建 ModelContextSettings；新协议为空时兼容旧 agent_options。"""
        data = self.ctx.agent_config.model_context_options_data
        if data:
            return ModelContextSettings.model_validate(data)
        return migration_model_context_options_from_agent_options_v1(self.ctx.agent_config.agent_options)

    def build_support_vision(self) -> bool:
        """从 prompt_setting.support_upload.vision 构建 support_vision"""
        support_upload = self.ctx.agent_config.model_context_options_data.get("support_upload") or {}
        return bool(support_upload.get("vision", False))

    def build_executor_info(self) -> dict:
        """构建执行用户信息，包含 access_token / app_code / app_secret 用于沙箱认证和 MCP 调用"""
        info = {"executor": self.ctx.username}
        access_token = self.ctx.resource_manager.resolve_access_token(self.ctx.username)
        if access_token:
            info["access_token"] = access_token
        # 将 resource_manager 的 app_code/app_secret 传入 executor_info，
        # 用于 PaaS Sandbox API 的应用态认证（平台测试页进程是平台凭证）
        if self.ctx.resource_manager.app_code:
            info["app_code"] = self.ctx.resource_manager.app_code
        if self.ctx.resource_manager.app_secret:
            info["app_secret"] = self.ctx.resource_manager.app_secret
        logger.info(
            f"[credential] build_executor_info: username={self.ctx.username}, "
            f"access_token={'***' if access_token else 'empty'}, "
            f"app_code={info.get('app_code', 'empty')}, "
            f"has_app_secret={bool(info.get('app_secret'))}, "
            f"rm_type={type(self.ctx.resource_manager).__name__}"
        )
        self._executor_info = info
        return info

    def build_checkpointer(self) -> BaseCheckpointSaver:
        """获取 Checkpointer，必须注入，否则抛出异常"""
        chat = self.ctx.chat or ChatBuildExtras()
        if chat.checkpointer is not None:
            return chat.checkpointer
        raise ValueError("Checkpointer is required but not provided. Please inject a valid checkpointer.")

    def get_role_prompt(self) -> str | None:
        """获取角色提示词"""
        config = self.ctx.agent_config
        return config.role_prompts[0]["content"] if config.role_prompts else None

    def handle_agent_switch(self) -> None:
        """处理智能体切换：system 差异由注入挂点天然承担，不再改写账本。

        切换后 ctx.agent_config 已指向新 agent（factory 经 get_agent_config(final_agent_code)
        装配），self.agent_info 随之指向新 agent，inject_role_system 注入自动使用新 agent 预设。
        账本 system 记录原样保留，不再视图级改写污染快照。
        """
        if not self.ctx.switch_agent:
            return

        logger.info(f"ChatAgentBuilder: switching agent to->[{self.ctx.agent_code}]")

    # ---------- 内部方法 ----------

    def _handle_last_human_message(self, session_context_data: List[dict]):
        """处理最后一条 human 消息，判断有 resources"""
        if not session_context_data:
            return

        for item in reversed(session_context_data):
            logger.info(
                f"ChatAgentBuilder: handling last human message with resources in session_context_data->[{item}]"
            )
            if item.get("role") == PromptRole.USER.value:
                # item.get("extra") 有可能为 None, 和 item.get("extra", {}) 不等价
                extra = item.get("extra") or {}
                resources = extra.get("resources") or []
                self._file_resources = [resource for resource in resources if resource.get("type") == "file"]
                self._specific_resources = [resource for resource in resources if resource.get("type") != "file"]
                break
