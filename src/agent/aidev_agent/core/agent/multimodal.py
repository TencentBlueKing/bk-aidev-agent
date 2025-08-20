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

import os
from abc import ABC, abstractmethod
from copy import deepcopy
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    ClassVar,
    Dict,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    cast,
)

from jinja2.sandbox import SandboxedEnvironment as Environment
from langchain.agents import (
    AgentExecutor,
)
from langchain.agents.agent import RunnableAgent, RunnableMultiActionAgent
from langchain.agents.structured_chat.base import StructuredChatAgent
from langchain.agents.structured_chat.prompt import FORMAT_INSTRUCTIONS
from langchain.memory.chat_memory import BaseChatMemory
from langchain.memory.token_buffer import ConversationTokenBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import BaseCallbackHandler, Callbacks
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.prompts.chat import (
    BaseMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain_core.runnables import AddableDict, Runnable, RunnableConfig
from langchain_core.runnables.schema import StreamEvent
from langchain_core.stores import ByteStore
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from typing_extensions import Literal, Self

from aidev_agent.core.extend.intent.prompts import general_qa_prompt_structured_chat
from aidev_agent.core.utils.async_utils import async_generator_with_timeout, async_to_sync_generator
from aidev_agent.core.utils.local import request_local
from aidev_agent.packages.langchain.tools.builtin import add_image_to_chat_context
from aidev_agent.services.pydantic_models import AgentOptions

from .agents import create_enhanced_structured_chat_agent, create_enhanced_tool_calling_agent
from .patches import apply_patches
from .prompts import (
    MULTI_MODAL_PREFIX,
    MULTI_MODAL_PREFIX_J2_TPL,
    STRUCTURED_CHAT_MULTI_MODAL_PREFIX_ADDON,
    SUFFIX,
)

apply_patches()


class J2PromptMixin:
    @classmethod
    def get_prefix(cls, prefix: str, **kwargs) -> str:
        return Environment().from_string(prefix).render(**kwargs)


class LiteEnhancedAgentExecutor(AgentExecutor):
    def stream_events(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        *,
        version: Literal["v1", "v2"],
        include_names: Optional[Sequence[str]] = None,
        include_types: Optional[Sequence[str]] = None,
        include_tags: Optional[Sequence[str]] = None,
        exclude_names: Optional[Sequence[str]] = None,
        exclude_types: Optional[Sequence[str]] = None,
        exclude_tags: Optional[Sequence[str]] = None,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> Iterator[StreamEvent]:
        aiter = self.astream_events(
            input,
            config,
            version=version,
            include_names=include_names,
            include_types=include_types,
            include_tags=include_tags,
            exclude_names=exclude_names,
            exclude_types=exclude_types,
            exclude_tags=exclude_tags,
            **kwargs,
        )
        _aiter = async_generator_with_timeout(aiter, timeout=timeout)
        g = async_to_sync_generator(_aiter)
        yield from g


class EnhancedAgentExecutor(LiteEnhancedAgentExecutor):
    agent: "CommonAgentMixIn"

    def invoke(self, input: Dict[str, str], *args, **kwargs) -> Dict[str, Any]:
        """执行"""
        self._setup_execute_context(input)
        ret = super().invoke(input, *args, **kwargs)
        reference_doc = request_local.current_user_store["reference_doc"]
        if reference_doc:
            ret["reference_doc"] = reference_doc
        return ret

    async def ainvoke(self, input: Dict[str, str], *args, **kwargs) -> Dict[str, Any]:
        """执行"""
        self._setup_execute_context(input)
        ret = await super().ainvoke(input, *args, **kwargs)
        reference_doc = request_local.current_user_store["reference_doc"]
        if reference_doc:
            ret["reference_doc"] = reference_doc
        return ret

    def stream(
        self,
        input: Union[Dict[str, Any], Any],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any,
    ) -> Iterator[AddableDict]:
        self._setup_execute_context(input)
        return super().stream(input, config, **kwargs)

    async def astream_events(
        self,
        input: Any,
        config: Optional[RunnableConfig] = None,
        *,
        version: Literal["v1", "v2"],
        include_names: Optional[Sequence[str]] = None,
        include_types: Optional[Sequence[str]] = None,
        include_tags: Optional[Sequence[str]] = None,
        exclude_names: Optional[Sequence[str]] = None,
        exclude_types: Optional[Sequence[str]] = None,
        exclude_tags: Optional[Sequence[str]] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[Any, Any]:
        self._setup_execute_context(input)
        async for each in super().astream_events(
            input,
            config,
            version=version,
            include_names=include_names,
            include_types=include_types,
            include_tags=include_tags,
            exclude_names=exclude_names,
            exclude_types=exclude_types,
            exclude_tags=exclude_tags,
            **kwargs,
        ):
            yield each

    def _setup_execute_context(self, input: Dict[str, Any]) -> None:
        """设置执行上下文"""
        request_local.current_user_store = {
            "file_store": self.agent.file_store,
            "image": {},
            "knowledge_bases": self.agent.agent_options.knowledge_query_options.knowledge_bases,
            "knowledge_items": self.agent.agent_options.knowledge_query_options.knowledge_items,
            "reference_doc": {},
        }
        files_list = input.get("files_lst", [])
        input["files_list"] = files_list


class CommonAgentMixIn(BaseModel, ABC):
    default_setup_entry: str = "get_agent_executor"
    knowledge_llm: BaseChatModel = Field(default=None)
    callbacks: Optional[List[BaseCallbackHandler]]
    prefix: Optional[str] = None
    knowledge_items: List[Dict] = Field(default_factory=list)
    knowledge_bases: List[Dict] = Field(default_factory=list)
    file_store: Optional[ByteStore] = None
    support_vision: bool = False  # 是否支持图片输入
    llm_token_limit: Optional[int] = None  # LLM支持的最大token数
    chat_prompt_template: Optional[ChatPromptTemplate] = None
    create_agent_func: Callable = None  # 创建 agent 的具体方法
    agent_options: AgentOptions = Field(default_factory=AgentOptions, description="Agent运行使用的配置")

    agent_classes: ClassVar[Dict] = None
    builtin_tools: ClassVar[List[BaseTool]] = []
    MULTI_MODAL_PREFIX: ClassVar[str] = MULTI_MODAL_PREFIX

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_agent_executor(
        cls,
        llm: BaseChatModel,
        knowledge_llm: BaseChatModel,
        extra_tools: Optional[List[BaseTool]] = None,
        prefix: Optional[str] = None,
        role_prompt: Optional[str] = None,
        suffix: Optional[str] = None,
        format_instructions: Optional[str] = None,
        memory: Optional[BaseChatMemory] = None,
        chat_history: Optional[List[BaseMessage]] = None,
        callbacks: Optional[List] = None,
        knowledge_items: Optional[List[Dict]] = None,
        knowledge_bases: Optional[List[Dict]] = None,
        file_store: Optional[ByteStore] = None,
        support_vision: bool = False,
        llm_token_limit=28000,
        agent_options: Optional[AgentOptions] = None,
        **kwargs,
    ) -> Tuple[AgentExecutor, RunnableConfig]:
        """获得multimodal agent执行实例"""
        callbacks = callbacks or []
        tools: List[BaseTool] = deepcopy(cls.builtin_tools)
        query_knowledgebase = False
        if any((knowledge_items, knowledge_bases)):
            query_knowledgebase = True
        tools.extend(extra_tools or [])
        if support_vision:
            tools.append(add_image_to_chat_context)
        agent = cls.create_agent(
            llm=llm,
            tools=tools,
            prefix=prefix,
            role_prompt=role_prompt,
            suffix=suffix,
            format_instructions=format_instructions,
            query_knowledgebase=query_knowledgebase,
            agent_options=agent_options,
        )
        agent.file_store = file_store
        agent.knowledge_llm = knowledge_llm
        agent.llm_token_limit = llm_token_limit or int(os.getenv("LLM_TOKEN_LIMIT", 28000))
        if agent_options:
            agent.agent_options = agent_options
        if kwargs.get("intent_recognition_kwargs"):
            agent.agent_options.intent_recognition_options.tool_output_compress_thrd = kwargs.get(
                "intent_recognition_kwargs", {}
            ).get("tool_output_compress_thrd", 5000)
        if knowledge_bases:
            agent.agent_options.knowledge_query_options.knowledge_bases = knowledge_bases
        if knowledge_items:
            agent.agent_options.knowledge_query_options.knowledge_items = knowledge_items
        history = ChatMessageHistory()
        if chat_history:
            history.add_messages(chat_history)
        memory = memory or ConversationTokenBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            input_key="input",
            output_key="output",
            chat_memory=history,
            llm=llm,
        )
        e = cls.create_executor(agent=agent, tools=tools, memory=memory, kwargs=kwargs)
        cfg = RunnableConfig()
        cfg["callbacks"] = callbacks
        return e, cfg

    @classmethod
    @abstractmethod
    def create_agent(
        cls,
        llm: BaseChatModel,
        tools: List[BaseTool],
        prefix: Optional[str] = None,
        role_prompt: Optional[str] = None,
        suffix: Optional[str] = None,
        format_instructions: Optional[str] = None,
        **kwargs,
    ) -> Self:
        pass

    @classmethod
    def create_executor(
        cls,
        agent: Self,
        tools: List[BaseTool],
        memory: BaseChatMemory,
        kwargs: Dict[Any, Any],
    ) -> EnhancedAgentExecutor:
        e = EnhancedAgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            return_intermediate_steps=True,
            handle_parsing_errors=True,
            memory=memory,
            **kwargs.get("executor_kwargs", {}),
        )
        return e

    def add_image_to_messages(self, messages: List[BaseMessagePromptTemplate]) -> None:
        for name, image in request_local.current_user_store["image"].items():
            image_template = HumanMessagePromptTemplate.from_template(
                [
                    {"text": f"This is image {name}"},
                    {"image_url": {"url": f"data:image/jpeg;base64,{image}"}},
                ]
            )
            messages.insert(-1, image_template)

    def _setup_runnable(self, **kwargs):
        if request_local.current_user_store["image"] and self.chat_prompt_template:
            self.add_image_to_messages(self.chat_prompt_template.messages)
            agent_runnable = self.create_agent_func(self.llm, self.tools, self.chat_prompt_template)
            self.runnable = agent_runnable
        else:
            if not kwargs.get("runnable_has_been_modified"):
                self.runnable = self.raw_runnable  # type: ignore # noqa

    def plan(self, intermediate_steps, callbacks, **kwargs):
        self._setup_runnable(**kwargs)
        return super().plan(intermediate_steps, callbacks, **kwargs)

    async def aplan(self, intermediate_steps, callbacks, **kwargs):
        self._setup_runnable(**kwargs)
        return await super().aplan(intermediate_steps, callbacks, **kwargs)


class StructuredCommonAgent(CommonAgentMixIn, StructuredChatAgent):
    raw_prompt: ChatPromptTemplate = Field(default=None)

    def plan(
        self,
        intermediate_steps: List[Tuple[AgentAction, str]],
        callbacks: Callbacks = None,
        **kwargs: Any,
    ) -> Union[AgentAction, AgentFinish]:
        """添加多模态支持"""
        full_inputs = self.get_full_inputs(intermediate_steps, **kwargs)
        if not getattr(self, "raw_prompt", None):
            self.raw_prompt = deepcopy(self.llm_chain.prompt)  # type: ignore
        current_user_store_image = request_local.current_user_store.get("image")
        if current_user_store_image:
            self.llm_chain.prompt = deepcopy(self.raw_prompt)
            self.add_image_to_messages(self.llm_chain.prompt.messages)  # type: ignore
        else:
            self.llm_chain.prompt = self.raw_prompt
        full_output = self.llm_chain.predict(callbacks=callbacks, **full_inputs)
        return self.output_parser.parse(full_output)

    @classmethod
    def create_agent(
        cls,
        llm: BaseChatModel,
        tools: List[BaseTool],
        prefix: Optional[str] = None,
        role_prompt: Optional[str] = None,
        suffix: Optional[str] = None,
        format_instructions: Optional[str] = None,
        **kwargs,
    ) -> Self:
        agent = cls.from_llm_and_tools(
            llm,
            tools,
            prefix=(
                prefix or cls.MULTI_MODAL_PREFIX + f"\n{role_prompt or ''}\n" + STRUCTURED_CHAT_MULTI_MODAL_PREFIX_ADDON
            ),
            suffix=suffix or SUFFIX,
            memory_prompts=[MessagesPlaceholder("chat_history")],  # type: ignore
            format_instructions=FORMAT_INSTRUCTIONS,
        )
        agent = cast(Self, agent)
        return agent


class ToolCallCommonAgentMixIn(J2PromptMixin, CommonAgentMixIn):
    multi_modal_runnable: Optional[Runnable[dict, Union[AgentAction, AgentFinish]]] = None
    raw_runnable: Optional[Runnable[dict, Union[AgentAction, AgentFinish]]] = None
    role_prompt: Optional[str] = None
    llm: BaseChatModel = Field(default=None)
    tools: List[BaseTool] = Field(default_factory=list)
    MULTI_MODAL_PREFIX: ClassVar[str] = MULTI_MODAL_PREFIX_J2_TPL
    DEFAULT_CHAT_PROMPT_TPL: ClassVar[str] = MULTI_MODAL_PREFIX_J2_TPL
    chat_prompt_template: ChatPromptTemplate = Field(default=None)
    create_agent_func: Callable = create_enhanced_tool_calling_agent

    @classmethod
    def get_agent_executor(cls, *args, **kwargs: Dict[Any, Any]) -> Tuple[AgentExecutor, RunnableConfig]:
        prefix = cls.get_prefix(kwargs.pop("prefix", cls.MULTI_MODAL_PREFIX), **kwargs)
        kwargs["prefix"] = prefix
        agent, cfg = super().get_agent_executor(*args, **kwargs)
        return agent, cfg

    @classmethod
    def create_agent(
        cls,
        llm: BaseChatModel,
        tools: List[BaseTool],
        prefix: Optional[str] = None,
        role_prompt: Optional[str] = None,
        **kwargs,
    ) -> Self:
        messages = [
            (
                "system",
                (prefix or cls.MULTI_MODAL_PREFIX) + f"\n{role_prompt or ''}\n",
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
        if kwargs.get("query_knowledgebase"):
            messages.insert(
                -2,
                (
                    "human",
                    "根据后续用户提的问题，获取knowledge_item_ids与knowledgebase_ids, 先使用工具查询下知识库。"
                    "如果发现knowledge_items或knowledgebase都和主题无关，那就随机挑选一个存在的。",
                ),
            )
            messages.insert(
                -2, ("ai", "好的，接下来我会先查询下知识库，并确保传入了knowledge_item_ids或knowledgebase_ids。")
            )
        chat_prompt_template = ChatPromptTemplate.from_messages(messages)
        # TODO:
        # 1. 将以上 chat_prompt_template 构建替换成 chat_prompt_template = deepcopy(general_qa_prompt_tool_calling)
        # 2. 适配更新测试样例 test_ws_consumer 逻辑防止出现：
        # KeyError: "Input to ChatPromptTemplate is missing variables {'role_prompt', 'query'}.
        # Expected: ['query', 'role_prompt']
        # Received: ['input', 'files_list', 'knowledge_items', 'knowledge_bases', 'chat_history',
        # 'intermediate_steps', 'agent_scratchpad']
        # Note: if you intended {role_prompt} to be part of the string and not a variable,
        # please escape it with double curly braces like: '{{role_prompt}}'."
        agent_runnable = create_enhanced_tool_calling_agent(llm, tools, chat_prompt_template)
        agent = cls(runnable=agent_runnable, callbacks=[])  # type: ignore
        agent.raw_runnable = agent_runnable
        agent.llm = llm
        agent.tools = tools
        agent.prefix = prefix
        agent.role_prompt = role_prompt
        agent.chat_prompt_template = chat_prompt_template
        agent = cast(Self, agent)
        return agent


class StructuredChatCommonAgentMixIn(ToolCallCommonAgentMixIn):
    create_agent_func: Callable = create_enhanced_structured_chat_agent

    @classmethod
    def create_agent(
        cls,
        llm: BaseChatModel,
        tools: List[BaseTool],
        prefix: Optional[str] = None,
        role_prompt: Optional[str] = None,
        suffix: Optional[str] = None,
        format_instructions: Optional[str] = None,
        agent_options: Optional[AgentOptions] = None,
        **kwargs,
    ) -> Self:
        chat_prompt_template = deepcopy(general_qa_prompt_structured_chat)
        agent_runnable = create_enhanced_structured_chat_agent(llm, tools, chat_prompt_template, agent_options)
        agent = cls(runnable=agent_runnable, callbacks=[])  # type: ignore
        agent.raw_runnable = agent_runnable
        agent.llm = llm
        # NOTE: 在 StructuredChatAgent 中修改 tools 中的参数
        # 使得如果 LLM 调用工具时如果出现以下类型的错误，可以重新尝试，继续进行而不阻碍过程
        for i in range(len(tools)):
            tools[i].handle_validation_error = True
            tools[i].handle_tool_error = True
        agent.tools = tools
        agent.prefix = prefix
        agent.role_prompt = role_prompt
        agent.chat_prompt_template = chat_prompt_template
        agent = cast(Self, agent)
        return agent


class ToolCallCommonAgent(ToolCallCommonAgentMixIn, RunnableAgent):
    stream_runnable: bool = True


class MultiToolCallCommonAgent(ToolCallCommonAgentMixIn, RunnableMultiActionAgent):
    stream_runnable: bool = True


class StructuredChatCommonAgent(StructuredChatCommonAgentMixIn, RunnableAgent):
    stream_runnable: bool = True
