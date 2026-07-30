import json
import re
import uuid
import warnings
from importlib.metadata import version as pkg_version
from logging import getLogger
from typing import Any, Callable, ClassVar, Generator, List, Optional

from ag_ui.core import BaseEvent, EventType, RunFinishedEvent, RunStartedEvent
from ag_ui.encoder import EventEncoder
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.stores import ByteStore
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import BaseModel, Field

from aidev_agent.api.bk_agent import BkAgentApi
from aidev_agent.config import settings
from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import (
    AgentInput,
    InterruptMessage,
    RunFinishedSuccessOutcome,
    serialize_run_finished_outcome,
)
from aidev_agent.core.ag_ui.utils import (
    langchain_messages_to_agui,
    langchain_messages_to_streaming_events,
)
from aidev_agent.core.tools.a2a_tools.types import AgentBackendType, AgentSpec
from aidev_agent.core.tools.runtime_tools import RuntimeBackendResolver
from aidev_agent.enums import AgentType, PromptRole
from aidev_agent.exceptions import AgentException
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.resource_manager.registry import resource_manager
from aidev_agent.pydantic_models import (
    AgentOptions,
    ChatPrompt,
    ExecuteKwargs,
    KnowledgeSettings,
    ModelContextSettings,
)
from aidev_agent.services.agent.approval import ApprovalStateHandler
from aidev_agent.services.agent.registry import AgentBuildContext, ChatBuildExtras
from aidev_agent.services.common_agent import CommonAgentProtocol, CommonQAAgent
from aidev_agent.services.event_handlers.agui_writer import AGUISessionWriter
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.utils.async_utils import async_to_sync_generator
from aidev_agent.utils.loop import run_coro_sync
from aidev_agent.utils.migrations import (
    migration_chat_model_non_thinking_from_non_thinking_llm_v1,
    migration_knowledge_query_options_from_agent_options_v1,
    migration_model_context_options_from_agent_options_v1,
)

logger = getLogger(__name__)


def _extract_tool_calls(builtin_property: dict) -> list[dict]:
    """从 builtin_property 中提取 tool_calls 列表。

    注意：arguments 在数据库中存储为 JSON 字符串，需要解析为字典。
    """
    tool_calls = []
    for tc in builtin_property.get("tool_calls", []):
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


class ChatCompletionAgent(BaseModel):
    """聊天 Agent"""

    agent_type: ClassVar[AgentType] = AgentType.CHAT

    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_model: BaseChatModel | None = None
    """聊天模型；种子实例（``ChatCompletionAgent()``）为 ``None``，``build(ctx)``
    装配后由 :meth:`ChatAgentBuilder.build_chat_model` 填充为非空 ``BaseChatModel``。
    种子实例不可执行（``execute()`` 假设非空）。"""
    chat_model_non_thinking: BaseChatModel | None = None
    """非思考模型；由 :meth:`ChatAgentBuilder.build_chat_model_non_thinking` 填充。"""
    non_thinking_llm: str | None = Field(default=None, deprecated="使用 chat_model_non_thinking 替代")
    chat_history: list[ChatPrompt] | None = None
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
    agent_info: dict | None = Field(default=None, description="原始配置信息，来自 AgentConfig.agent_info")

    IMAGE_FILE_PATTERN: ClassVar[re.Pattern] = re.compile(r"^!\[.*\]\((http[^)]+/([^/]+?))\)")
    TOOL_EXECUTION_INTERVAL: ClassVar[int] = 10
    UPLOAD_IMAGE_PROMPT_PREFIX: ClassVar[Any] = "我上传了个图片文件,文件名为{file_name}。"
    SKIP_PROMPT_ROLE: ClassVar[list[str]] = ["guide", "reasoning"]

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

        self.chat_model = builder.build_chat_model()
        self.chat_model_non_thinking = builder.build_chat_model_non_thinking()
        self.skills = builder.build_skills()
        # 先构建 executor_info，供 build_tools / construct_mcp 使用同一凭证源
        self.executor_info = builder.build_executor_info()
        self.resource_manager = ctx.resource_manager
        self.tools = builder.build_tools()
        self.mcp_fetch_failures = builder.mcp_fetch_failures
        self.knowledge_bases = builder.build_knowledge_bases()
        self.knowledges = builder.build_knowledge_items()
        self.knowledge_query_options = builder.build_knowledge_query_options()
        self.model_context_options = builder.build_model_context_options()
        if ctx.agent_config and ctx.agent_config.agent_options is not None:
            self.agent_options = ctx.agent_config.agent_options
        self.support_vision = builder.build_support_vision()
        self.chat_history = builder.build_chat_history(ctx.session_context_data)
        self.checkpointer = builder.build_checkpointer()
        self.subagent_specs = builder.build_subagents(ctx.agent_code)
        self.role_prompt = builder.get_role_prompt()
        self.callbacks = chat.callbacks
        # 构造 RuntimeBackendResolver（在 ChatAgentBuilder 层管理生命周期）
        self.runtime_backend_resolver = builder.build_runtime_backend_resolver()
        self.agent_info = getattr(ctx.agent_config, "agent_info", None) if ctx.agent_config else None

        if chat.agent_cls is not None:
            self.agent_cls = chat.agent_cls
        if ctx.session_code is not None:
            self.thread_id = ctx.session_code
        if ctx.event_handler is not None:
            self.event_handler = ctx.event_handler
        return self

    def execute(self, execute_kwargs: ExecuteKwargs) -> Generator[str, None, None] | str:
        self.migration_v1()
        if not self.messages:
            self.messages = self.convert_history_to_messages()
        messages = self.messages
        self.chat_model.callbacks = self.callbacks
        return self._execute(messages, execute_kwargs)

    def stop(self):
        helper = GeneratorStreamingHelper(
            thread_id=self.thread_id,
        )
        if not helper.message_handler.is_cancel_requested(self.thread_id):
            logger.info(f"[STOP_DEBUG] Calling message_handler.request_cancel() for thread_id={self.thread_id}")
            helper.message_handler.request_cancel(self.thread_id)
        else:
            logger.info(f"[STOP_DEBUG] Cancel already requested for thread_id={self.thread_id}")
        # 用户主动停止时也释放资源
        self.release_resources()

    def release_resources(self) -> None:
        """释放 agent 持有的资源（沙箱后端等）。

        调用 RuntimeBackendResolver.close() 关闭所有已解析的沙箱后端。
        此方法是幂等的 — 多次调用不会产生副作用。
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
        clients: dict[int, tuple[Any, list[BaseChatModel]]] = {}
        for model in (self.chat_model, self.chat_model_non_thinking):
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

    def _query_approval_status(self, session_code: str) -> dict | None:
        """查询 gongfeng 后端判断是否需要续流，并从 interrupt 记录获取审批结果及 interrupts。

        Returns:
            ``{"approve_result": ApproveResult, "interrupts": list, "id": int|None}``
            或 None（尚未回调），其中 ``approve_result`` ∈ {approved, rejected, cancelled}。
        """
        return ApprovalStateHandler().query_approval_info(session_code)

    def convert_history_to_messages(self) -> list[BaseMessage]:
        if not self.chat_history:
            return []
        return self._chat_history_to_langchain_messages(self._convert_contents(self.chat_history))

    @property
    def model_name(self) -> str:
        return getattr(self.chat_model, "model_name", "")

    # ---------- 内部方法 ----------

    def _sync_checkpoint_messages(self, agent_e: Runnable, cfg: RunnableConfig) -> list[BaseMessage]:
        """同步 checkpoint 中的消息，返回 checkpoint 中非系统消息列表。

        使用 RemoveMessage 清除旧的 checkpoint 消息，避免与平台消息重复/冲突。
        这是保持 thread_id 稳定的前提条件（替代原来的 uuid4 后缀方案）。

        注意：此同步必须在 _execute 中执行（而非 prepare_stream），
        因为非流式路径（ainvoke）不经过 prepare_stream。
        """
        try:
            agent_state = run_coro_sync(agent_e.aget_state(cfg))
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
                    run_coro_sync(
                        agent_e.aupdate_state(
                            cfg,
                            {"messages": remove_ops},
                            as_node="__start__",
                        )
                    )

            return non_system_checkpoint_msgs
        except Exception:
            logger.warning(
                "sync_checkpoint: failed to sync checkpoint messages, thread_id=%s",
                self.thread_id,
                exc_info=True,
            )
            return []

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
        for model in (self.chat_model, self.chat_model_non_thinking):
            if model is None or not hasattr(model, "default_headers"):
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

    def _execute(self, messages: list[BaseMessage], execute_kwargs: ExecuteKwargs):
        if not messages:
            raise ValueError("The messages list cannot be empty.")
        self._update_aidev_agent_header(execute_kwargs)
        agent_e, cfg = self._get_agent(messages, execute_kwargs=execute_kwargs)
        cfg.setdefault("configurable", {})
        cfg["configurable"]["thread_id"] = self.thread_id
        cfg["configurable"]["execute_kwargs"] = execute_kwargs

        # 清除 checkpoint 中的旧消息，避免与平台消息重复
        # 平台传入的 messages 已包含完整历史，无需拼接
        # resume 时不能清checkpoint，否则 model 节点会拿到空 messages → 拒答。
        if not execute_kwargs.resume:
            self._sync_checkpoint_messages(agent_e, cfg)

        if execute_kwargs.stream:
            if execute_kwargs.legacy_streaming:
                return self._stream_with_legacy(agent_e, cfg, messages)
            else:
                return self._stream(agent_e, cfg, messages, execute_kwargs)

        else:
            try:
                platform_pv = self._fetch_platform_pv()
                input_state: dict[str, Any] = {"messages": messages, "execute_kwargs": execute_kwargs}
                if platform_pv:
                    input_state["runtime_paas_sbx_pv"] = platform_pv

                async def _ainvoke_with_cleanup():
                    try:
                        return await agent_e.ainvoke(input_state, cfg)
                    finally:
                        await self._aclose_chat_models()

                result = run_coro_sync(_ainvoke_with_cleanup(), timeout=execute_kwargs.invoke_timeout)
                result_output = result.get("messages")[-1]
                return_data = {
                    "choices": [{"delta": {"role": "assistant", "content": result_output.content}}],
                    "model": self.model_name,
                    "id": result_output.id,
                    "reference_doc": result.get("reference_doc", []),
                }
                return return_data
            except Exception as e:
                logger.exception(f"Error executing agent: {e}")
                raise AgentException(message=f"Error executing agent: {e}")
            finally:
                # 非流式执行结束后释放资源
                self.release_resources()

    def _stream_with_legacy(
        self, agent_e: Runnable, cfg: RunnableConfig, messages: list[BaseMessage]
    ) -> Generator[Any, None, None]:
        platform_pv = self._fetch_platform_pv()
        _input: dict[str, Any] = {"messages": messages}
        if platform_pv:
            _input["runtime_paas_sbx_pv"] = platform_pv
        return agent_e.agent.stream_standard_event(
            agent_e,
            cfg,
            _input,
            async_finalizer=self._aclose_chat_models,
        )

    def _stream(
        self, agent_e: Runnable, cfg: RunnableConfig, messages: list[BaseMessage], execute_kwargs: ExecuteKwargs
    ) -> Generator[Any, None, None]:
        # 兼容前端：``execute_kwargs.resume`` 历史协议为 ``list[ResumeItem]``，部分前端会直接
        # 传单条 dict（如 ``{"interruptId": "...", "status": "resolved"}``），此处统一归一化为
        # 列表，确保后续 ``hydrate_resume_payload`` / LangGraph 续流逻辑接收到一致形态。
        if isinstance(execute_kwargs.resume, dict):
            execute_kwargs.resume = [execute_kwargs.resume]

        logger.info(
            "[ToolApproval] _stream: resume=%s, thread_id=%s",
            bool(execute_kwargs.resume),
            repr(self.thread_id),
        )

        # 拉取平台已存在的 sandbox PV 注入 state（runtime_paas_sbx_pv）
        platform_pv = self._fetch_platform_pv()
        state: dict[str, Any] = {}
        if platform_pv:
            state["runtime_paas_sbx_pv"] = platform_pv
        body = {
            "thread_id": self.thread_id,
            "run_id": messages[-1].id or uuid.uuid4().hex,
            "state": state,
            "messages": langchain_messages_to_agui(messages),
        }
        if execute_kwargs.resume:
            body["forwarded_props"] = {"command": {"resume": execute_kwargs.resume}}
        agent_input = AgentInput(**body)

        # 取消信号传递：cancel_checker 在用户点停止时由 Agent 内部轮询，
        # 触发后由 Agent 优雅发送 RunFinishedEvent
        def make_cancel_checker(thread_id: str):
            def cancel_checker() -> bool:
                return GeneratorStreamingHelper.is_cancelled(thread_id)

            return cancel_checker

        if isinstance(self.event_handler, BaseSessionWriter):
            self.event_handler.set_tools(self.tools)

        # 续流时，查询审批结果供 AidevAGUIAgent 发送 custom 事件及填充 resume payload
        approve_result = None
        approval_interrupts = []
        if execute_kwargs.resume:
            approval_info = self._query_approval_status(self.thread_id)
            if approval_info is not None:
                approve_result = approval_info["approve_result"]
                approval_interrupts = approval_info.get("interrupts") or []
            ApprovalStateHandler.hydrate_resume_payload(execute_kwargs.resume, approve_result)

        agui_entry = AidevAGUIAgent(
            name="test_agui_agent",
            graph=agent_e,
            event_handler=self.event_handler,
            config=cfg,
            tools={each.name: each for each in self.tools} if self.tools else {},
            cancel_checker=make_cancel_checker(self.thread_id),
            mcp_fetch_failures=getattr(self, "mcp_fetch_failures", []) or [],
            approve_result=approve_result,
            approval_interrupts=approval_interrupts,
        )

        return self._stream_with_queue(
            agui_entry,
            agent_input,
            queue_thread_id=self.thread_id,
            background_only=execute_kwargs.background_only,
            agent_e=agent_e,
            cfg=cfg,
            resume=bool(execute_kwargs.resume),
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
    ) -> Generator[Any, None, None]:
        """使用队列处理器缓存流式请求，支持断点续传。

        两阶段输出：
        1. 同步直传头部帧到RUN_STARTED，
           绕过 RabbitMQ buffer 避免 gevent 环境下的顺序竞态。
        2. 后续运行时事件交给队列管理，支持断点续传。
        """
        helper = GeneratorStreamingHelper(
            thread_id=queue_thread_id or agent_input.thread_id,
            defer_cleanup_on_complete=background_only,
        )
        producer = self._build_resume_aware_producer(agui_entry, agent_input, agent_e=agent_e, cfg=cfg, resume=resume)

        # ---- 阶段 1：同步拉取头部帧并直接 yield ----
        head_frames = []
        remaining_producer = self._extract_head_frames(producer, head_frames)
        for frame in head_frames:
            yield frame

        # ---- 阶段 2：剩余帧交给队列管理（支持断点续传）----
        yield from helper.stream(remaining_producer, on_complete=self._on_complete)

    @staticmethod
    def _extract_head_frames(
        producer: Generator[Any, None, None],
        head_frames: list,
    ) -> Generator[Any, None, None]:
        """从 producer 中同步提取头部帧（到 RUN_STARTED 为止），返回剩余帧 generator。

        事件流结构：MESSAGES_SNAPSHOT → [RUN_FINISHED] → RUN_STARTED → STEP_* ...
        RUN_STARTED 是 Agent 图执行的起点，之前的帧为初始化/回放事件。
        """
        RUN_STARTED_MARKER = '"type":"RUN_STARTED"'

        def _remaining() -> Generator[Any, None, None]:
            yield from producer

        for frame in producer:
            head_frames.append(frame)
            if isinstance(frame, str) and RUN_STARTED_MARKER in frame:
                break

        return _remaining()

    def _build_resume_aware_producer(
        self,
        agui_entry: AidevAGUIAgent,
        agent_input: AgentInput,
        agent_e: Runnable | None,
        cfg: RunnableConfig | None,
        resume: bool,
    ) -> Generator[Any, None, None]:
        """构造「resume 感知」的生产者生成器（方案 B 兜底入口）。

        生成器惰性执行：仅当队列处理器决定启动新生产者（即队列已空、错过方案 A 的接管
        窗口）时才会被拉取。届时若这是一次 resume 且对应 graph 已处于终态，则改为从
        checkpoint 重放完整 turn（见 :meth:`_build_terminal_resume_replay`），避免对终态图
        跑空 astream 只拿到空快照；否则回退到正常的 astream 流。

        队列内仍有历史时（方案 A 的接管窗口内），队列处理器走 restore 分支、不会拉取此
        生成器，因此不会触发多余的 ``aget_state`` 查询。
        """

        def _gen() -> Generator[Any, None, None]:
            if resume and agent_e is not None and cfg is not None and agent_input.thread_id:
                replay = self._build_terminal_resume_replay(agui_entry, agent_input, agent_e, cfg)
                if replay is not None:
                    logger.info(
                        "[ResumeReplay] graph terminal, replay persisted turn from checkpoint "
                        "(scheme B fallback), thread_id=%s",
                        agent_input.thread_id,
                    )
                    try:
                        yield from replay
                    finally:
                        run_coro_sync(self._aclose_chat_models())
                    return
            yield from async_to_sync_generator(
                agui_entry.run(agent_input),
                async_finalizer=self._aclose_chat_models,
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
            state = run_coro_sync(agent_e.aget_state(replay_cfg))
        except Exception:
            logger.warning(
                "[ResumeReplay] aget_state failed, fallback to astream, thread_id=%s",
                thread_id,
                exc_info=True,
            )
            return None

        tasks = state.tasks if state and len(state.tasks) > 0 else None
        interrupts = tasks[0].interrupts if tasks else []
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

        return self._terminal_replay_event_stream(agui_entry, agent_input, non_system)

    def _terminal_replay_event_stream(
        self,
        agui_entry: AidevAGUIAgent,
        agent_input: AgentInput,
        replayable_messages: list[BaseMessage] | None = None,
    ) -> Generator[Any, None, None]:
        """把终态 checkpoint 重建成与正常流一致的 AG-UI 编码事件序列。

        续流（resume）场景仍然不下发终态 ``MESSAGES_SNAPSHOT``——前端 SNAPSHOT 是
        覆盖式语义，会把前端已渲染的历史消息全部覆盖。同样不发 ``STATE_SNAPSHOT``——
        其经 ``get_state_snapshot`` 依赖 ``agui_entry.active_run`` 运行期状态，而重放
        路径下 ``agui_entry.run`` 从未执行，该状态未初始化。

        关于"片段语义"：resume 路径下 ``_sync_checkpoint_messages`` 被显式跳过
        （见 ``_execute``），故 checkpoint 中的 ``messages`` 是**完整 turn**
        （``[Human, AI(tool_call), Tool, AI(回复)]``）而非历史上的"仅新增片段"。
        但 ``langchain_messages_to_streaming_events`` 主动过滤
        ``Human/System/Interrupt/Activity``，只下发 ``AI/Tool`` 的可重放事件，
        因此最终前端拿到的仍是"前端缺的那段"（worker 异步跑完 + 30s 队列窗口已过
        的兜底场景下，前端无法通过方案 A 队列接管拿到 worker 写的事件流）：
        前端按 ``message_id`` / ``tool_call_id`` 增量合并，与正常 astream 路径下
        的渲染同构，不会撞覆盖式语义。
        """
        encoder = EventEncoder()
        run_id = agent_input.run_id or uuid.uuid4().hex

        # 1) 审批中断恢复：先回放终态 RUN_FINISHED，让前端把原中断卡片更新为最终状态
        #    （approved / rejected / cancelled），与 AidevAGUIAgent.run 续流首条事件同源。
        try:
            if agui_entry._should_emit_resume_approval_finished():
                yield encoder.encode(agui_entry._build_resume_approval_finished_event(agent_input))
        except Exception:
            logger.exception("[ResumeReplay] emit resume approval RUN_FINISHED failed")

        # 2) RUN_STARTED
        yield encoder.encode(
            RunStartedEvent(type=EventType.RUN_STARTED, thread_id=agent_input.thread_id or "", run_id=run_id)
        )

        # 3) 把 checkpoint 「片段」消息逐条转为流式增量事件下发，补齐前端缺失的本轮 worker 续流内容。
        #    转换器内部会跳过 Human/System/Interrupt/Activity 消息，只下发 AI/Tool 的可重放事件。
        if replayable_messages:
            try:
                event_count = 0
                for ev in langchain_messages_to_streaming_events(replayable_messages):
                    yield encoder.encode(ev)
                    event_count += 1
                logger.info(
                    "[ResumeReplay] streamed %d incremental events from checkpoint fragment, thread_id=%s",
                    event_count,
                    agent_input.thread_id,
                )
            except Exception:
                logger.exception(
                    "[ResumeReplay] failed to stream checkpoint fragment, thread_id=%s",
                    agent_input.thread_id,
                )

        # 4) RUN_FINISHED（续流场景不下发 MESSAGES_SNAPSHOT，前端复用已有消息状态 + 上面补发的增量事件）
        yield encoder.encode(
            RunFinishedEvent(
                type=EventType.RUN_FINISHED,
                thread_id=agent_input.thread_id or "",
                run_id=run_id,
                outcome=serialize_run_finished_outcome(RunFinishedSuccessOutcome()),
            )
        )

    def _on_complete(self):
        if self.event_handler and hasattr(self.event_handler, "set_streaming_finished"):
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

    def _chat_history_to_langchain_messages(self, chat_history: list[ChatPrompt]) -> list[BaseMessage]:
        """
        将 ChatPrompt 列表转换为 LangChain 消息列表
        支持从 builtin_property 中提取 tool_calls 和 tool_call_id 等协议字段，
        以支持多轮工具调用场景的历史消息透传。
        """
        messages: list[BaseMessage] = []
        for each in chat_history:
            bp = each.builtin_property or {}
            match each.role:
                case PromptRole.USER.value:
                    if isinstance(each.content, list):
                        new_content = []
                        for each_content in each.content:
                            if each_content.get("url"):
                                new_content.append({"type": "image_url", "image_url": {"url": each_content.get("url")}})
                            else:
                                new_content.append(each_content)
                        each.content = new_content
                        messages.append(HumanMessage(id=each.id, content=each.content))
                    else:
                        messages.append(HumanMessage(id=each.id, content=str(each.content)))
                case PromptRole.ASSISTANT.value | PromptRole.AI.value:
                    tool_calls = _extract_tool_calls(bp)
                    messages.append(AIMessage(id=each.id, content=each.content, tool_calls=tool_calls))
                case PromptRole.SYSTEM.value:
                    messages.append(SystemMessage(id=each.id, content=each.content))
                case PromptRole.TOOL.value:
                    content = each.content if isinstance(each.content, str) else str(each.content)
                    messages.append(ToolMessage(id=each.id, content=content, tool_call_id=bp.get("tool_call_id", "")))
                case PromptRole.INTERRUPT.value:
                    # 中断/审批卡片：content 落库为 JSON 字符串（形如
                    # ``{"outcome": {"type": "interrupt"/"success", "interrupts": [...]}}``），
                    # 历史回放时可能已被解析为 dict。统一还原为 dict 后封装成
                    # InterruptMessage（继承 ActivityMessage），既进入 state["messages"]
                    # 供 MESSAGES_SNAPSHOT 重建与前端展示，又会被 basic_middleware 的
                    # isinstance(ActivityMessage) 过滤剔除，绝不进入 LLM 输入。
                    interrupt_content = each.content
                    if isinstance(interrupt_content, str):
                        try:
                            interrupt_content = json.loads(interrupt_content)
                        except (json.JSONDecodeError, TypeError):
                            interrupt_content = {}
                    if not isinstance(interrupt_content, (dict, list)):
                        interrupt_content = {}
                    messages.append(InterruptMessage(id=each.id, content=interrupt_content))
        return messages

    def _convert_contents(self, contents: list[ChatPrompt]) -> list[ChatPrompt]:
        """将无需送到大模型处理的 content 去掉"""
        new_contents = []
        for each in contents:
            each.role = each.role.replace("hidden-", "")
            if each.role in self.SKIP_PROMPT_ROLE:
                continue
            if each.role == PromptRole.HIDDEN.value:
                each.role = PromptRole.USER.value
            if each.role == PromptRole.PAUSE.value:
                each.role = PromptRole.ASSISTANT.value
            if each.role == PromptRole.USER_IMAGE.value:
                if not self.support_vision:
                    raise AgentException(message="当前模型不支持图片识别,请切换其他模型")
                each.role = PromptRole.USER.value
                match = self.IMAGE_FILE_PATTERN.search(each.content)
                if match:
                    file_path, _ = match.group(1), match.group(2)
                    each.content = [{"type": "image_url", "image_url": {"url": file_path}}]
                    # 图片不计算实际大小，但不能为 0 —— 给一个大于 0 的占位值
                    self.files.append({"file_name": file_path, "file_size": 100})
                else:
                    raise AgentException(message="图片md格式非法")
            # deepseek-r1 系列不支持 system role，需要降级为 user
            if each.role == PromptRole.SYSTEM.value and "deepseek-r1" in self.model_name:
                each.role = PromptRole.USER.value
            new_contents.append(each)

        return new_contents


class ChatAgentBuilder:
    """``ChatCompletionAgent`` 装配器

    把原 ``AgentInstanceFactory`` 中所有 Chat 专属装配方法收敛在这里：

    - 模型 / 工具 / 知识 / 技能装配
    - 聊天历史构建（含 tool_calls 过滤、think 移除、role_history 拼接、modify_last_system_message）
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
        self._mcp_fetch_failures: list[dict] = []
        self._executor_info: dict | None = None
        self._runtime_backend_resolver: Any | None = None
        # 装配前先从最后一条 user 消息提取 specific_resources，供 build_tools / build_knowledge_bases 过滤
        self._handle_last_human_message(ctx.session_context_data)

    @property
    def mcp_fetch_failures(self) -> list[dict]:
        """MCP 工具拉取失败记录，由 ``build_tools`` 写入"""
        return self._mcp_fetch_failures

    def build_runtime_backend_resolver(self) -> RuntimeBackendResolver:
        """构造 RuntimeBackendResolver。

        resolver 将通过 AgentExecutorKwargs 传入 ReActAgentBuilder。
        """
        self._runtime_backend_resolver = RuntimeBackendResolver(default_runtime="local")
        return self._runtime_backend_resolver

    # ---------- 公共：装配方法（被 ChatCompletionAgent.build 调用） ----------

    def build_chat_model(self) -> BaseChatModel:
        """构建聊天模型"""
        config = self.ctx.agent_config
        chat = self.ctx.chat or ChatBuildExtras()

        if not config.chat_model:
            raise ValueError("请配置智能体默认模型并重新发布")

        kwargs: dict[str, Any] = {
            "model": config.chat_model,
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
        return ChatModel.get_setup_instance(**kwargs)

    def build_chat_history(self, session_context_data: List[dict]) -> List[ChatPrompt]:
        """构建聊天历史"""
        config = self.ctx.agent_config
        role_prompt_roles = {
            PromptRole.USER.value,
            PromptRole.ASSISTANT.value,
            PromptRole.SYSTEM.value,
            PromptRole.PAUSE.value,
            "hidden-user",
            "hidden-assistant",
            "hidden-system",
        }
        role_history = [
            ChatPrompt(role=each["role"].replace("hidden-", ""), content=each["content"])
            for each in (config.role_prompts or [])
            if each.get("content") and each.get("role") in role_prompt_roles
        ]

        chat_history = [
            ChatPrompt.model_validate(each)
            for each in (session_context_data or [])
            if each.get("content") and each["role"] != "system"
        ]
        for each in chat_history:
            if each.role != "assistant":
                continue
            each.content = self._remove_think(each.content)

        chat_history = self._filter_unmatched_tool_calls(chat_history)

        self._modify_last_system_message(chat_history)
        chat_history = role_history + chat_history
        return chat_history

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
        tools = [self.ctx.resource_manager.construct_tool(tool_code) for tool_code in tool_codes] + mcp_result.tools
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
        - **硬约束**：子 ``agent_config.related_agents`` 被清空，实现递归断开 ——
          即使配置里有嵌套 subagents 也不会生成第二层 AgentSpec

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
        #   自己这一个 MemorySaver 的历史；而真正的期望是「同一 thread_id 跨父子/成员的
        #   state 在同一 checkpointer 存取」
        # - 父 ctx.chat.checkpointer 在 factory.py:170 处一定非空（fallback 到 MemorySaver），
        #   此处直接复用；仅在极端情况下（ctx.chat 为 None 或 checkpointer 缺失）
        #   fallback，新建实例也仅对当前这一批 subagents 生效
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

                # 2. 递归断开：清空子 config 的 related_agents（D-06）
                child_config = child_config.model_copy(update={"related_agents": []})

                # 3. 构造子 ChatBuildExtras：与父共享 agent_cls/auth_headers/checkpointer；
                #    仅 callbacks 隔离避免事件双发
                child_chat = ChatBuildExtras(
                    agent_cls=parent_chat.agent_cls if parent_chat is not None else None,
                    callbacks=[],  # 子 Agent 不继承父 callbacks，避免事件双发
                    auth_headers=parent_chat.auth_headers if parent_chat is not None else None,
                    temperature=None,  # 由子 agent_config.temperature 决定（build_chat_model 读取）
                    max_tokens=None,  # 同上
                    checkpointer=shared_checkpointer,  # 共享父 checkpointer，使 member 模式可跨调用续接
                )

                # 4. 构造子 AgentBuildContext（D-05）
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

                # 5. 构造子 Agent 规格（agent_cls + ctx，由 LocalBackend 运行时实例化并 build）
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

    def build_knowledge_query_options(self):
        """从 AgentConfig 构建 KnowledgeSettings；新协议为空时兼容旧 agent_options。"""
        data = self.ctx.agent_config.knowledge_query_options_data
        if data:
            return KnowledgeSettings.model_validate(data)
        return migration_knowledge_query_options_from_agent_options_v1(self.ctx.agent_config.agent_options)

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
        """处理智能体切换：替换最后一条 system 消息为新 role_prompt"""
        if not self.ctx.switch_agent:
            return

        logger.info(f"ChatAgentBuilder: switching agent to->[{self.ctx.agent_code}]")
        for item in reversed(self.ctx.session_context_data):
            if item["role"] == "system":
                item["content"] = self.get_role_prompt()
                break

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
                if extra.get("resources"):
                    self._specific_resources = extra.get("resources")
                break

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

        tool_result_ids: set[str] = set()
        for prompt in chat_history:
            if prompt.role == "tool":
                tool_call_id = prompt.builtin_property.get("tool_call_id", "")
                if tool_call_id:
                    tool_result_ids.add(tool_call_id)

        # 过滤 assistant 消息中未匹配的 tool_calls：
        # 全部无结果 → 整条丢弃；部分有结果 → 仅保留匹配的 tool_calls。
        filtered_history: List[ChatPrompt] = []
        for prompt in chat_history:
            if prompt.role != "assistant":
                filtered_history.append(prompt)
                continue

            tool_calls = self._extract_tool_calls_from_prompt(prompt)

            if not tool_calls:
                filtered_history.append(prompt)
                continue

            matched_calls = [tc for tc in tool_calls if tc.get("id", "") in tool_result_ids]
            unmatched_calls = [tc for tc in tool_calls if tc.get("id", "") not in tool_result_ids]

            if not matched_calls:
                logger.info(
                    f"ChatAgentBuilder: filtering assistant message with no matched tool_calls, "
                    f"message_id=[{prompt.id}], tool_calls_count=[{len(tool_calls)}]"
                )
                continue

            if unmatched_calls:
                logger.info(
                    f"ChatAgentBuilder: removing unmatched tool_calls from assistant message, "
                    f"message_id=[{prompt.id}], total_calls=[{len(tool_calls)}], "
                    f"matched=[{len(matched_calls)}], unmatched=[{len(unmatched_calls)}]"
                )
                self._update_tool_calls_in_prompt(prompt, matched_calls)

            filtered_history.append(prompt)

        return filtered_history

    def _extract_tool_calls_from_prompt(self, prompt: ChatPrompt) -> List[dict]:
        """从 ChatPrompt 中提取 tool_calls 列表

        Args:
            prompt: ChatPrompt 对象

        Returns:
            tool_calls 列表，每个元素包含 id, name, args 字段
        """
        return _extract_tool_calls(prompt.builtin_property or {})

    def _update_tool_calls_in_prompt(self, prompt: ChatPrompt, matched_tool_calls: List[dict]) -> None:
        """更新 ChatPrompt 中的 tool_calls，只保留匹配的调用

        Args:
            prompt: ChatPrompt 对象
            matched_tool_calls: 匹配的 tool_calls 列表（来自 _extract_tool_calls_from_prompt 的格式）
        """
        builtin_property = prompt.builtin_property or {}
        tool_calls_raw = builtin_property.get("tool_calls", [])

        matched_ids = {tc.get("id", "") for tc in matched_tool_calls}

        filtered_tool_calls = [tc for tc in tool_calls_raw if tc.get("id", "") in matched_ids]

        if builtin_property:
            builtin_property["tool_calls"] = filtered_tool_calls
        else:
            prompt.builtin_property = {"tool_calls": filtered_tool_calls}

    def _modify_last_system_message(self, chat_history: List[ChatPrompt]) -> None:
        if not self.ctx.agent_code:
            return

        role_prompt = self.get_role_prompt()
        if not role_prompt:
            return

        for prompt in reversed(chat_history):
            if prompt.role == "system":
                prompt.content = role_prompt
                break

    @staticmethod
    def _remove_think(content: str) -> str:
        """移除 HTML 中的思考部分内容

        Args:
            content: 包含思考内容的 HTML 字符串

        Returns:
            清理后的内容字符串
        """
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

        _content = re.sub(r'<section class="think-body">[\s\S]*?</section>', "", _content, flags=re.DOTALL)

        if not _content.strip():
            think_body_match = re.search(r'<section class="think-body">([\s\S]*?)</section>', content, re.DOTALL)
            if think_body_match:
                _content = think_body_match.group(1).strip()

        return _content.strip()
