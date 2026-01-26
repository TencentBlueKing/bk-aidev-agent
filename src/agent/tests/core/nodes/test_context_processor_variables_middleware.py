# -*- coding: utf-8 -*-
"""测试 ContextAssembly 变量处理中间件。"""

import pytest
from aidev_agent.core.nodes.model.basic_middleware import (
    BaseVariablesMiddleware,
    DeepSeekR1VariablesMiddleware,
    SpecialVariablesMiddleware,
)
from aidev_agent.core.nodes.model.context_assembly import MiddlewarePipeline
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.core.nodes.model.token_compression import (
    ChatHistoryCompressionMiddleware,
    CompressionState,
    KnowledgeCompressionMiddleware,
)
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate


class FakeLLM:
    def __init__(self, model_name: str):
        self.model_name = model_name

    def get_num_tokens_from_messages(self, messages):
        # 用消息数量模拟 token 数，方便测试压缩逻辑
        return len(messages)

    def invoke(self, messages, config=None):
        # 用固定输出模拟压缩结果
        return AIMessage(content="Z")


class FakeTokenLLM(FakeLLM):
    def get_num_tokens_from_messages(self, messages):
        # 用字符长度近似 token 数，方便验证 context 压缩
        total = 0
        for m in messages:
            content = getattr(m, "content", "")
            if content is None:
                continue
            if not isinstance(content, str):
                content = str(content)
            total += len(content)
        return total


class FakeKnowledgeCompressor:
    """模拟知识库压缩函数。"""

    def __init__(self):
        self.calls = 0

    def __call__(self, provided_chat_history, query, context):
        self.calls += 1
        # 返回短字符串，确保压缩后 token 数降低
        return f"c{self.calls}"


@pytest.mark.skipif(
    False,
    reason="测试已修复",
)
class TestVariablesMiddleware:
    def test_tool_calling_agent_scratchpad_is_messages(self):
        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )

        prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
        messages = [
            HumanMessage(content="hi"),
            AIMessage(
                content="",
                tool_calls=[{"name": "t", "args": {"a": 1}, "id": "call_1", "type": "tool_call"}],
            ),
            ToolMessage(content="ok", tool_call_id="call_1", name="t"),
        ]

        ctx = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
        )
        pipeline.execute(ctx)

        assert ctx.variables["query"] == "hi"
        assert ctx.variables["chat_history"] == []
        assert isinstance(ctx.variables["agent_scratchpad"], list)
        assert len(ctx.variables["agent_scratchpad"]) == 2

    def test_structured_agent_scratchpad_is_string(self):
        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=True,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )

        prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
        messages = [
            HumanMessage(content="hi"),
            AIMessage(
                content="",
                tool_calls=[{"name": "t", "args": {"a": 1}, "id": "call_1", "type": "tool_call"}],
            ),
            ToolMessage(content="ok", tool_call_id="call_1", name="t"),
        ]

        ctx = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
        )
        pipeline.execute(ctx)

        scratchpad = ctx.variables["agent_scratchpad"]
        assert isinstance(scratchpad, str)
        assert '"action": "t"' in scratchpad
        assert "观察结果：ok" in scratchpad

    def test_deepseek_r1_converts_system_message_in_chat_history(self):
        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )
        pipeline.use(DeepSeekR1VariablesMiddleware())

        prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
        messages = [
            SystemMessage(content="sys"),
            HumanMessage(content="hi"),
        ]

        ctx = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeLLM(model_name="deepseek-r1"),
        )
        pipeline.execute(ctx)

        assert len(ctx.variables["chat_history"]) == 1
        assert isinstance(ctx.variables["chat_history"][0], HumanMessage)
        assert ctx.variables["chat_history"][0].content == "sys"

    def test_chat_history_compression_can_drop_chat_history(self):
        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )
        pipeline.use(ChatHistoryCompressionMiddleware(token_limit=2, token_margin=0))

        prompt = ChatPromptTemplate.from_messages([("placeholder", "{chat_history}"), ("human", "{input}")])
        messages = [
            HumanMessage(content="m0"),
            HumanMessage(content="m1"),
            HumanMessage(content="m2"),
        ]

        ctx = ProcessorContext(
            state={"messages": messages, "input": "x"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeLLM(model_name="any"),
            metadata={"_compression_state": CompressionState(), "enable_custom_event": False},
        )
        pipeline.execute(ctx)

        # 原本 chat_history 有 2 条（m0,m1），压缩后应减少到 1 条
        assert [m.content for m in ctx.variables["chat_history"]] == ["m1"]

    def test_knowledge_compression_first_time(self):
        compressor = FakeKnowledgeCompressor()
        compression_state = CompressionState()

        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )
        pipeline.use(
            KnowledgeCompressionMiddleware(
                knowledge_compressor_func=compressor,
                token_limit=5,
                token_margin=0,
            )
        )

        prompt = ChatPromptTemplate.from_messages([("human", "{context}")])
        ctx = ProcessorContext(
            state={"messages": [HumanMessage(content="hi")], "knowledge_content": "abcdefghijk"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeTokenLLM(model_name="any"),
            metadata={
                "_compression_state": compression_state,
                "provided_chat_history": [],
                "enable_custom_event": False,
            },
        )
        pipeline.execute(ctx)

        assert ctx.variables["context"] == "c1"
        assert compressor.calls == 1
        assert compression_state.knowledge_compressed is True
        assert compression_state.knowledge_cache == "c1"

    def test_knowledge_compression_cache_hit(self):
        compressor = FakeKnowledgeCompressor()
        compression_state = CompressionState()

        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )
        pipeline.use(
            KnowledgeCompressionMiddleware(
                knowledge_compressor_func=compressor,
                token_limit=5,
                token_margin=0,
            )
        )

        prompt = ChatPromptTemplate.from_messages([("human", "{context}")])

        ctx1 = ProcessorContext(
            state={"messages": [HumanMessage(content="hi")], "knowledge_content": "abcdefghijk"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeTokenLLM(model_name="any"),
            metadata={
                "_compression_state": compression_state,
                "provided_chat_history": [],
                "enable_custom_event": False,
            },
        )
        pipeline.execute(ctx1)

        ctx2 = ProcessorContext(
            state={"messages": [HumanMessage(content="hi")], "knowledge_content": "abcdefghijk"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeTokenLLM(model_name="any"),
            metadata={
                "_compression_state": compression_state,
                "provided_chat_history": [],
                "enable_custom_event": False,
            },
        )
        pipeline.execute(ctx2)

        assert ctx2.variables["context"] == "c1"
        assert compressor.calls == 1

    def test_knowledge_compression_recompress_on_change(self):
        compressor = FakeKnowledgeCompressor()
        compression_state = CompressionState()

        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )
        pipeline.use(
            KnowledgeCompressionMiddleware(
                knowledge_compressor_func=compressor,
                token_limit=5,
                token_margin=0,
            )
        )

        prompt = ChatPromptTemplate.from_messages([("human", "{context}")])

        ctx1 = ProcessorContext(
            state={"messages": [HumanMessage(content="hi")], "knowledge_content": "abcdefghijk"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeTokenLLM(model_name="any"),
            metadata={
                "_compression_state": compression_state,
                "provided_chat_history": [],
                "enable_custom_event": False,
            },
        )
        pipeline.execute(ctx1)

        ctx2 = ProcessorContext(
            state={"messages": [HumanMessage(content="hi")], "knowledge_content": "NEW_CONTENT_XXXX"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeTokenLLM(model_name="any"),
            metadata={
                "_compression_state": compression_state,
                "provided_chat_history": [],
                "enable_custom_event": False,
            },
        )
        pipeline.execute(ctx2)

        assert ctx1.variables["context"] == "c1"
        assert ctx2.variables["context"] == "c2"
        assert compressor.calls == 2

    def test_chat_history_compression_skips_when_not_overflow(self):
        compression_state = CompressionState()

        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )
        pipeline.use(ChatHistoryCompressionMiddleware(token_limit=3, token_margin=0))

        prompt = ChatPromptTemplate.from_messages([("placeholder", "{chat_history}"), ("human", "{input}")])
        messages = [
            HumanMessage(content="m0"),
            HumanMessage(content="m1"),
            HumanMessage(content="m2"),
        ]

        ctx = ProcessorContext(
            state={"messages": messages, "input": "x"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeLLM(model_name="any"),
            metadata={"_compression_state": compression_state, "enable_custom_event": False},
        )
        pipeline.execute(ctx)

        assert [m.content for m in ctx.variables["chat_history"]] == ["m0", "m1"]
        assert compression_state.chat_history_removed == 0

    def test_chat_history_compression_multi_round_is_incremental(self):
        compression_state = CompressionState()

        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())
        pipeline.use(
            SpecialVariablesMiddleware(
                use_structured_response=False,
                use_general_knowledge_on_miss=False,
                rejection_message="rej",
                role_prompt="role",
            )
        )
        pipeline.use(ChatHistoryCompressionMiddleware(token_limit=2, token_margin=0))

        prompt = ChatPromptTemplate.from_messages([("placeholder", "{chat_history}"), ("human", "{input}")])

        messages = [
            HumanMessage(content="m0"),
            HumanMessage(content="m1"),
            HumanMessage(content="m2"),
        ]

        ctx1 = ProcessorContext(
            state={"messages": messages, "input": "x"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeLLM(model_name="any"),
            metadata={"_compression_state": compression_state, "enable_custom_event": False},
        )
        pipeline.execute(ctx1)

        assert [m.content for m in ctx1.variables["chat_history"]] == ["m1"]
        assert compression_state.chat_history_removed == 1
        assert len(messages) == 3

        # ReAct 循环：新增消息
        messages.append(HumanMessage(content="m3"))

        ctx2 = ProcessorContext(
            state={"messages": messages, "input": "x"},
            config={},
            chat_prompt_template=prompt,
            llm=FakeLLM(model_name="any"),
            metadata={"_compression_state": compression_state, "enable_custom_event": False},
        )
        pipeline.execute(ctx2)

        assert [m.content for m in ctx2.variables["chat_history"]] == ["m2"]
        assert compression_state.chat_history_removed == 2
        assert len(messages) == 4

    def test_cache_first_call_populates_cache(self):
        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())

        prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
        messages = [
            HumanMessage(content="hi"),
            AIMessage(content=""),
            ToolMessage(content="ok", tool_call_id="call_1", name="t"),
        ]
        split_cache = {}

        ctx = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
            assembly_cache=split_cache,
        )
        pipeline.execute(ctx)

        assert split_cache["last_human_idx"] == 0
        assert ctx.metadata["chat_history"][0] is messages[0]
        assert len(ctx.metadata["tool_messages"]) == 2

    def test_cache_invalidates_on_new_human_message(self):
        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())

        prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
        messages = [
            HumanMessage(content="hi"),
            AIMessage(content=""),
            ToolMessage(content="ok", tool_call_id="call_1", name="t"),
        ]
        split_cache = {}

        ctx1 = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
            assembly_cache=split_cache,
        )
        pipeline.execute(ctx1)

        first_chat_history = ctx1.metadata["chat_history"]

        messages.append(HumanMessage(content="new"))

        ctx2 = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
            assembly_cache=split_cache,
        )
        pipeline.execute(ctx2)

        assert split_cache["last_human_idx"] == len(messages) - 1
        assert ctx2.metadata["chat_history"] is not first_chat_history
        assert ctx2.metadata["chat_history"][-1].content == "new"
        assert ctx2.metadata["tool_messages"] == []

    def test_cache_tool_messages_incremental_correctness(self):
        pipeline = MiddlewarePipeline()
        pipeline.use(BaseVariablesMiddleware())

        prompt = ChatPromptTemplate.from_messages([("human", "{input}")])
        messages = [
            HumanMessage(content="hi"),
            AIMessage(content=""),
            ToolMessage(content="ok", tool_call_id="call_1", name="t"),
        ]
        split_cache = {}

        ctx1 = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
            assembly_cache=split_cache,
        )
        pipeline.execute(ctx1)

        messages.append(AIMessage(content=""))
        messages.append(ToolMessage(content="ok2", tool_call_id="call_2", name="t"))

        ctx2 = ProcessorContext(
            state={"messages": messages, "input": "ignored"},
            config={},
            chat_prompt_template=prompt,
            assembly_cache=split_cache,
        )
        pipeline.execute(ctx2)

        tool_messages = ctx2.metadata["tool_messages"]
        assert len(tool_messages) == 4
        assert tool_messages[-1].content == "ok2"
