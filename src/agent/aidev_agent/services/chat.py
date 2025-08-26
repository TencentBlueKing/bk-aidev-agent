import json
import re
from collections import deque
from logging import getLogger
from time import time
from typing import Any, ClassVar, Generator, Optional

from langchain.memory.token_buffer import ConversationTokenBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.stores import ByteStore
from langchain_core.tools import StructuredTool
from langchain_openai.chat_models.base import _convert_message_to_dict
from pydantic import BaseModel, Field

from aidev_agent.core.agent.multimodal import EnhancedAgentExecutor
from aidev_agent.core.extend.agent.qa import CommonQAAgent
from aidev_agent.core.utils.loop import get_event_loop
from aidev_agent.enums import PromptRole, StreamEventType
from aidev_agent.exceptions import AgentException
from aidev_agent.services.pydantic_models import AgentOptions, ChatPrompt, ExecuteKwargs

logger = getLogger(__name__)


class ChatCompletionAgent(BaseModel):
    """聊天Agent"""

    chat_model: BaseChatModel
    chat_history: list[ChatPrompt]
    files: list[dict] = Field(default_factory=list)
    tools: Optional[list[StructuredTool]] = None
    knowledge_bases: Optional[list[dict]] = None
    knowledges: Optional[list[dict]] = None
    support_vision: bool = False  # 是否支持图片
    file_store: ByteStore | None = None
    role_prompt: str | None = None
    max_token_size: int | None = None
    callbacks: list[BaseCallbackHandler] | None = None
    agent_cls: type[CommonQAAgent] = CommonQAAgent
    agent_options: AgentOptions = Field(default_factory=AgentOptions)

    # using in streaming
    first_chunk: bool = True
    has_think: bool = False
    last_event_type: StreamEventType = StreamEventType.NO
    elapsed: list = [0.0, 0.0]

    IMAGE_FILE_PATTERN: ClassVar[re.Pattern] = re.compile(r"^\!\[.*\]\((http[^)]+/([^/]+?)\))")
    HEARTBEATS_INTERVAL: ClassVar[int] = 3
    TOOL_EXECUTION_INTERVAL: ClassVar[int] = 10
    UPLOAD_IMAGE_PROMPT_PREFIX: ClassVar[Any] = "我上传了个图片文件,文件名为{file_name}。"
    SKIP_PROMPT_ROLE: ClassVar[list[str]] = ["guide"]
    MAX_Q_LENGTH: ClassVar[int] = 5  # streaming Q lenghth

    class Config:
        arbitrary_types_allowed = True

    def convert_history_to_messages(self) -> list[BaseMessage]:
        return self._chat_history_to_langchain_messages(self._convert_contents(self.chat_history))

    def _chat_history_to_langchain_messages(self, chat_history: list[ChatPrompt]) -> list[BaseMessage]:
        messages: list[BaseMessage] = []
        for each in chat_history:
            match each.role:
                case PromptRole.USER.value:
                    messages.append(HumanMessage(content=each.content))
                case PromptRole.ASSISTANT.value:
                    messages.append(AIMessage(content=each.content))
                case PromptRole.AI.value:
                    messages.append(AIMessage(content=each.content))
                case PromptRole.SYSTEM.value:
                    messages.append(SystemMessage(content=each.content))
        return messages

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
            if each.role == PromptRole.SYSTEM.value and "hunyuan" in self.model_name and self.is_run_by_agent():
                hunyuan_system_content.append(each.content)
            else:
                new_contents.append(each)

        return new_contents

    @property
    def model_name(self) -> str:
        return getattr(self.chat_model, "model_name", "")

    def is_run_by_agent(self) -> bool:
        return any(
            [
                self.tools,
                self.files,
                self.knowledge_bases,
                self.knowledges,
                self.agent_options.knowledge_query_options.qa_response_knowledge_bases,
                self.agent_options.intent_recognition_options.intent_recognition_knowledge,
            ]
        )

    def execute(self, execute_kwargs: ExecuteKwargs) -> dict | Generator[str, None, None] | str:
        # 执行agent操作
        messages = self.convert_history_to_messages()
        if execute_kwargs.run_agent or self.is_run_by_agent():
            return self._execute_by_agent(messages, stream=execute_kwargs.stream)
        if self.callbacks:
            self.chat_model.callbacks = self.callbacks
        if execute_kwargs.stream:
            return self._stream(messages)
        return self._invoke(messages)

    def _execute_by_agent(self, messages: list[BaseMessage], stream: bool = False):
        agent_e, cfg = self._get_agent(messages)
        if stream:
            return agent_e.agent.stream_standard_event(
                agent_e, cfg, {"input": messages[-1].content}, timeout=self.HEARTBEATS_INTERVAL
            )
        else:
            loop = get_event_loop()
            result = loop.run_until_complete(agent_e.ainvoke({"input": messages[-1].content}, cfg))
            return result.get("output", "")

    def _stream(self, messages: list[BaseMessage]) -> Generator[str, None, None]:
        # 流式处理
        q = deque(maxlen=self.MAX_Q_LENGTH)
        try:
            for each in self.chat_model.stream(input=messages):
                if self.first_chunk and not each.content and not each.additional_kwargs.get("reasoning_content"):
                    continue
                event_type = (
                    StreamEventType.THINK if each.additional_kwargs.get("reasoning_content") else StreamEventType.TEXT
                )
                if self.last_event_type == StreamEventType.NO and event_type == StreamEventType.THINK:
                    self.elapsed[0] = time()
                if self.last_event_type == StreamEventType.THINK and event_type == StreamEventType.TEXT:
                    self.elapsed[1] = time()
                self.last_event_type = event_type
                self.first_chunk = False
                ret = {
                    "event": event_type.value,
                    "content": each.content
                    if event_type == StreamEventType.TEXT
                    else each.additional_kwargs.get("reasoning_content", ""),
                }
                if not self.has_think and ret["event"] == StreamEventType.THINK.value and ret["content"].strip():
                    self.has_think = True
                q.append(ret)
                if len(q) == self.MAX_Q_LENGTH:
                    # 如果没有think内容则不输出think
                    ret = self._pop_q_get_ret(q)
                    if ret:
                        yield f"data: {json.dumps(ret)}\n\n"
            while q:
                ret = self._pop_q_get_ret(q)
                if ret:
                    yield f"data: {json.dumps(ret)}\n\n"
        except Exception as exception:
            ret = {
                "event": StreamEventType.ERROR.value,
                "code": exception.code if hasattr(exception, "code") else 400,
                "message": exception.response_data() if hasattr(exception, "response_data") else str(exception),
            }
            logger.exception(exception)
            yield f"data: {json.dumps(ret)}\n\n"
        yield "data: [DONE]\n\n"

    def _pop_q_get_ret(self, q):
        ret = q.popleft()
        if not self.has_think and ret["event"] == StreamEventType.THINK.value:
            return None
        if self.has_think and self.elapsed[1] != 0 and q[0]["event"] == StreamEventType.TEXT.value:
            ret["elapsed_time"] = (self.elapsed[1] - self.elapsed[0]) * 1000
            self.elapsed = [0.0, 0.0]
        return ret

    def _invoke(self, messages: list[BaseMessage]) -> dict:
        # 非流式
        result = self.chat_model.invoke(input=messages)
        message_dict = _convert_message_to_dict(result)
        return {
            "choices": [{"delta": message_dict}],
            "model": self.model_name,
            "id": result.id,
        }

    def _get_agent(self, messages: list[BaseMessage]) -> tuple[EnhancedAgentExecutor, RunnableConfig]:
        if self.knowledge_bases:
            self.agent_options.knowledge_query_options.knowledge_bases = self.knowledge_bases
        if self.knowledges:
            self.agent_options.knowledge_query_options.knowledge_items = self.knowledges
        return self.agent_cls.get_agent_executor(
            llm=self.chat_model,
            knowledge_llm=self.chat_model,
            extra_tools=self.tools,
            chat_history=messages[:-1],
            tool_execution_interval=self.TOOL_EXECUTION_INTERVAL,
            support_vision=self.support_vision,
            file_store=self.file_store,
            role_prompt=self.role_prompt,
            callbacks=self.callbacks,
            agent_options=self.agent_options,
        )

    def get_memory_window(
        self,
        memory=None,
        max_token_limit=4096,
    ) -> int:
        """返回window内可以保留的有效条目数"""
        history = ChatMessageHistory()
        history.add_messages(self.chat_history)
        memory = memory or ConversationTokenBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            input_key="input",
            output_key="output",
            chat_memory=history,
            llm=self.chat_model,
            max_token_limit=max_token_limit,
        )
        return len(memory.buffer) - len(self.chat_history)
