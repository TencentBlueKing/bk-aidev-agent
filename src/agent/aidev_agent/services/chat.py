import json
import re
import uuid
from logging import getLogger
from typing import Any, Callable, ClassVar, Generator, Optional

from ag_ui.core import BaseEvent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.stores import ByteStore
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

from aidev_agent.core.ag_ui.aidev_agent import AidevAGUIAgent
from aidev_agent.core.ag_ui.types import AgentInput
from aidev_agent.core.ag_ui.utils import langchain_messages_to_agui
from aidev_agent.enums import PromptRole
from aidev_agent.exceptions import AgentException
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.services.common_agent import CommonQAAgent
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from aidev_agent.services.messages_handler import GeneratorStreamingHelper
from aidev_agent.services.pydantic_models import AgentOptions, ChatPrompt, ExecuteKwargs
from aidev_agent.utils.async_utils import async_to_sync_generator
from aidev_agent.utils.loop import get_event_loop

logger = getLogger(__name__)


class ChatCompletionAgent(BaseModel):
    """聊天Agent"""

    thread_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    chat_model: BaseChatModel
    non_thinking_llm: str | None = None
    chat_history: list[ChatPrompt] | None = None
    files: list[dict] = Field(default_factory=list)
    tools: Optional[list[StructuredTool]] = None
    knowledge_bases: Optional[list[dict]] = None
    knowledges: Optional[list[dict]] = None
    support_vision: bool = False  # 是否支持图片
    file_store: ByteStore | None = None
    role_prompt: str | None = None
    agent_prompt: str | None = None
    max_token_size: int | None = None
    callbacks: list[BaseCallbackHandler] | None = None
    agent_cls: type[CommonQAAgent] = CommonQAAgent
    agent_options: AgentOptions = Field(default_factory=AgentOptions)
    messages: list[BaseMessage] = Field(default_factory=list)
    checkpointer: BaseCheckpointSaver | None = None

    # using in streaming
    event_handler: Callable[[BaseEvent], None] | None = None
    mcp_fetch_failures: list[dict] = Field(default_factory=list, description="MCP 工具拉取失败记录，用于流式事件")

    IMAGE_FILE_PATTERN: ClassVar[re.Pattern] = re.compile(r"^\!\[.*\]\((http[^)]+/([^/]+?)\))")
    TOOL_EXECUTION_INTERVAL: ClassVar[int] = 10
    UPLOAD_IMAGE_PROMPT_PREFIX: ClassVar[Any] = "我上传了个图片文件,文件名为{file_name}。"
    SKIP_PROMPT_ROLE: ClassVar[list[str]] = ["guide", "reasoning"]

    class Config:
        arbitrary_types_allowed = True

    def convert_history_to_messages(self) -> list[BaseMessage]:
        if not self.chat_history:
            raise ValueError("The chat history cannot be empty.")
        return self._chat_history_to_langchain_messages(self._convert_contents(self.chat_history))

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
                case PromptRole.ASSISTANT.value | PromptRole.AI.value:
                    tool_calls = self._extract_tool_calls(bp)
                    messages.append(AIMessage(id=each.id, content=each.content, tool_calls=tool_calls))
                case PromptRole.SYSTEM.value:
                    messages.append(SystemMessage(id=each.id, content=each.content))
                case PromptRole.TOOL.value:
                    content = each.content if isinstance(each.content, str) else str(each.content)
                    messages.append(ToolMessage(id=each.id, content=content, tool_call_id=bp.get("tool_call_id", "")))
        return messages

    def _extract_tool_calls(self, builtin_property: dict) -> list[dict]:
        """从 builtin_property 中提取 tool_calls 列表

        注意：arguments 在数据库中存储为 JSON 字符串，需要解析为字典
        """
        tool_calls = []
        for tc in builtin_property.get("tool_calls", []):
            # arguments 是 JSON 字符串，需要解析为字典
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

    def _convert_contents(self, contents: list[ChatPrompt]) -> list[ChatPrompt]:
        """将无需送到大模型处理的content去掉"""
        new_contents = []
        hunyuan_system_content: list[str] = []
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
                    # 仅在支持图片的模型中生效
                    raise AgentException(message="当前模型不支持图片识别,请切换其他模型")
                each.role = PromptRole.USER.value
                match = self.IMAGE_FILE_PATTERN.search(each.content)
                if match:
                    file_path = match.group(2)
                    each.content = self.UPLOAD_IMAGE_PROMPT_PREFIX.format(file_name=file_path)
                    # 对于图片则不计算大小,但是不能给个1,随便给一个大于0的值
                    self.files.append({"file_name": file_path, "file_size": 100})
                else:
                    # 匹配不中,抛出异常
                    raise AgentException(message="图片md格式非法")
            if each.role == PromptRole.USER.value and hunyuan_system_content:
                new_content = "\n".join((hunyuan_system_content.pop(), each.content))
                each.content = new_content

            # 对于deepseek-r1 系列的需要把system去掉
            if each.role == PromptRole.SYSTEM.value and "deepseek-r1" in self.model_name:
                each.role = PromptRole.USER.value

            # 对于hunyuan需要兼容多`system`的case
            if each.role == PromptRole.SYSTEM.value and "hunyuan" in self.model_name:
                hunyuan_system_content.append(each.content)
            else:
                new_contents.append(each)

        return new_contents

    @property
    def model_name(self) -> str:
        return getattr(self.chat_model, "model_name", "")

    def execute(self, execute_kwargs: ExecuteKwargs) -> Generator[str, None, None] | str:
        # 执行agent操作
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

    def _execute(self, messages: list[BaseMessage], execute_kwargs: ExecuteKwargs):
        if not messages:
            raise ValueError("The messages list cannot be empty.")
        agent_e, cfg = self._get_agent(messages, execute_kwargs=execute_kwargs)
        cfg.setdefault("configurable", {})
        cfg["configurable"]["thread_id"] = execute_kwargs.session_code or self.thread_id
        cfg["configurable"]["execute_kwargs"] = execute_kwargs
        messages = [msg for msg in messages]
        if execute_kwargs.stream:
            if execute_kwargs.legacy_streaming:
                return self._stream_with_legacy(agent_e, cfg, messages)
            else:
                return self._stream(agent_e, cfg, messages, execute_kwargs)

        else:
            loop = get_event_loop()
            result = loop.run_until_complete(
                agent_e.ainvoke({"messages": messages, "execute_kwargs": execute_kwargs}, cfg)
            )
            result_output = result.get("messages")[-1]
            return_data = {
                "choices": [{"delta": {"role": "assistant", "content": result_output.content}}],
                "model": self.model_name,
                "id": result_output.id,
                "reference_doc": result.get("reference_doc", []),
            }
            return return_data

    def _stream_with_legacy(
        self, agent_e: Runnable, cfg: RunnableConfig, messages: list[BaseMessage]
    ) -> Generator[Any, None, None]:
        _input = {"messages": messages}
        return agent_e.agent.stream_standard_event(agent_e, cfg, _input)

    def _stream(
        self, agent_e: Runnable, cfg: RunnableConfig, messages: list[BaseMessage], execute_kwargs: ExecuteKwargs
    ) -> Generator[Any, None, None]:
        # 使用 session_code 作为 stream_thread_id，以支持断点续传（RabbitMQ 队列标识）
        # 当用户刷新页面重新进入同一会话时，可以从 RabbitMQ 队列恢复之前的流
        stream_thread_id = execute_kwargs.session_code or self.thread_id
        # 每次请求使用新的 graph_thread_id，避免 LangGraph checkpoint 累积历史消息
        # 因为平台端每次都从 DB 读取完整历史传入，不需要依赖 checkpoint 中的消息
        graph_thread_id = f"{stream_thread_id}_{uuid.uuid4().hex[:8]}"
        body = {
            "thread_id": graph_thread_id,
            "run_id": messages[-1].id or uuid.uuid4().hex,
            "state": {},
            "messages": langchain_messages_to_agui(messages),
        }
        agent_input = AgentInput(**body)

        # 创建取消检测回调，让 Agent 内部能够感知取消信号
        # 当用户点击停止按钮时，cancel_checker 会返回 True，Agent 会优雅地发送 RunFinishedEvent
        def make_cancel_checker(thread_id: str):
            def cancel_checker() -> bool:
                return GeneratorStreamingHelper.is_cancelled(thread_id)

            return cancel_checker

        if isinstance(self.event_handler, BaseSessionWriter):
            self.event_handler.set_tools(self.tools)
        agui_entry = AidevAGUIAgent(
            name="test_agui_agent",
            graph=agent_e,
            event_handler=self.event_handler,
            config=cfg,
            tools={each.name: each for each in self.tools} if self.tools else {},
            cancel_checker=make_cancel_checker(stream_thread_id),
            mcp_fetch_failures=getattr(self, "mcp_fetch_failures", []) or [],
        )

        return self._stream_with_queue(agui_entry, agent_input, queue_thread_id=stream_thread_id)

    def _stream_with_queue(
        self, agui_entry: AidevAGUIAgent, agent_input: AgentInput, queue_thread_id: str | None = None
    ) -> Generator[Any, None, None]:
        """使用队列处理器缓存流式请求，支持断点续传

        断点续传逻辑：
        1. 如果流正在运行或已完成，且有未消费的缓存消息，则从 client_index 位置续传
        2. 否则开始新的流式请求

        客户端在消费时应该在每次成功接收后更新 client_index，
        以便在连接中断后能够从正确的位置继续。

        Args:
            agui_entry: AGUI Agent 入口
            agent_input: Agent 输入参数
            queue_thread_id: 队列标识ID（用于断点续传），默认使用 agent_input.thread_id

        Yields:
            流式响应数据
        """
        helper = GeneratorStreamingHelper(
            thread_id=queue_thread_id or agent_input.thread_id,
        )
        return helper.stream(async_to_sync_generator(agui_entry.run(agent_input)), on_complete=self._on_complete)

    def _on_complete(self):
        if self.event_handler and hasattr(self.event_handler, "set_streaming_finished"):
            self.event_handler.set_streaming_finished()

    def _get_agent(
        self, messages: list[BaseMessage], *, execute_kwargs: ExecuteKwargs
    ) -> tuple[Runnable, RunnableConfig]:
        """
        由于在流式的时候，Response 立即返回会导致 trace 断掉，所以在_get_agent中添加 execute_kwargs
        execute_kwargs 有携带了 trace 上下文，以便于不要让 trace 断掉
        """
        if self.knowledge_bases:
            self.agent_options.knowledge_query_options.knowledge_bases = self.knowledge_bases
        if self.knowledges:
            self.agent_options.knowledge_query_options.knowledge_items = self.knowledges
        logger.info(f"callbacks: {self.callbacks}")
        return self.agent_cls.get_agent_executor(
            llm=self.chat_model,
            knowledge_llm=self.chat_model
            if self.non_thinking_llm is None
            else ChatModel.get_setup_instance(model=self.non_thinking_llm),
            extra_tools=self.tools,
            chat_history=messages[:-1],
            tool_execution_interval=self.TOOL_EXECUTION_INTERVAL,
            support_vision=self.support_vision,
            file_store=self.file_store,
            role_prompt=self.role_prompt,
            agent_prompt=self.agent_prompt,
            callbacks=self.callbacks,
            agent_options=self.agent_options,
            execute_kwargs=execute_kwargs,
            checkpointer=self.checkpointer if self.checkpointer else MemorySaver(),
        )
