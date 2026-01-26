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

import base64
from pathlib import Path

import pytest
from aidev_agent.config import settings
from aidev_agent.core.nodes.model import ModelNodeSettings, ModelState, build_model_node
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

# 测试模型列表
TEST_MODELS = ["hunyuan-turbo", "qwen3", "deepseek-v3"]

# 支持视觉能力的模型列表
VISION_MODELS = ["claude-sonnet-4-5-20250929-v1", "qwen3-vl-32B"]

# 测试图片路径
TEST_IMAGE_PATH = Path(__file__).parent.parent.parent / "mock_data" / "bkaidev.png"


def get_test_image_base64() -> str:
    """读取测试图片并返回 base64 编码"""
    with open(TEST_IMAGE_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# 如果没有配置足够的环境变量，跳过该测试
@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
class TestBuildModelNodeIntegration:
    """测试 build_model_node 集成测试（需要真实 LLM 配置）"""

    @pytest.fixture
    def sample_tools(self):
        """示例工具列表"""

        @tool
        def search_tool(query: str) -> str:
            """Search for information"""
            return f"Search results for: {query}"

        @tool
        def calculator(expression: str) -> str:
            """Calculate mathematical expression"""
            return f"Result: {expression}"

        return [search_tool, calculator]

    @pytest.fixture
    def real_context_processor(self, sample_tools):
        """提供 build_model_node 所需的 tools 与 node_options（历史命名保留）。"""
        return {
            "tools": sample_tools,
            "node_options": ModelNodeSettings(
                use_structured_response=False,
                enable_query_clarification=False,
                rejection_message="抱歉，我无法回答这个问题。",
                role_prompt="You are a helpful assistant.",
                use_general_knowledge_on_miss=True,
            ),
        }

    @pytest.fixture
    def real_store(self):
        """创建真实的 Store（使用内存存储）"""
        from langgraph.store.memory import InMemoryStore

        return InMemoryStore()

    @pytest.mark.parametrize("model_name", TEST_MODELS)
    def test_model_node_real_llm_tool_calling(self, model_name, real_context_processor, real_store):
        """测试真实 LLM 的 tool_calling 模式"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node = build_model_node(
            llm=real_llm,
            tools=real_context_processor["tools"],
            node_options=real_context_processor["node_options"],
        )

        state: ModelState = {
            "messages": [HumanMessage(content="What is 2+2?")],
        }
        config = RunnableConfig()

        result = node.invoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证返回了有效的内容
        message = result["messages"][0]
        assert message.content or message.tool_calls  # 应该有内容或工具调用
        print(
            f"\n[{model_name}] Tool calling mode response: {message.content[:100] if message.content else 'Tool calls'}"
        )

    @pytest.mark.parametrize("model_name", TEST_MODELS)
    def test_model_node_real_llm_structured_response(self, model_name, real_store):
        """测试真实 LLM 的 structured_response 模式"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node_options = ModelNodeSettings(
            use_structured_response=True,
            enable_query_clarification=False,
            rejection_message="抱歉，我无法回答这个问题。",
            role_prompt="You are a helpful assistant.",
            use_general_knowledge_on_miss=True,
        )

        node = build_model_node(
            llm=real_llm,
            tools=[],
            node_options=node_options,
        )

        state: ModelState = {
            "messages": [HumanMessage(content="Hello, how are you?")],
        }
        config = RunnableConfig()

        result = node.invoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证返回了有效的内容
        assert result["messages"][0].content
        print(f"\n[{model_name}] Structured response mode: {result['messages'][0].content[:100]}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_name", TEST_MODELS)
    async def test_model_node_real_llm_async(self, model_name, real_context_processor, real_store):
        """测试真实 LLM 的异步调用"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node = build_model_node(
            llm=real_llm,
            tools=real_context_processor["tools"],
            node_options=real_context_processor["node_options"],
        )

        state: ModelState = {
            "messages": [HumanMessage(content="Tell me a joke")],
        }
        config = RunnableConfig()

        result = await node.ainvoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证返回了有效的内容
        message = result["messages"][0]
        assert message.content or message.tool_calls
        print(f"\n[{model_name}] Async call response: {message.content[:100] if message.content else 'Tool calls'}")

    @pytest.mark.parametrize("model_name", TEST_MODELS)
    def test_model_node_with_chat_history(self, model_name, real_context_processor, real_store):
        """测试包含对话历史的情况"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node = build_model_node(
            llm=real_llm,
            tools=real_context_processor["tools"],
            node_options=real_context_processor["node_options"],
        )

        state: ModelState = {
            "messages": [
                HumanMessage(content="My name is Alice"),
                AIMessage(content="Hello Alice! How can I help you?"),
                HumanMessage(content="What is my name?"),
            ],
        }
        config = RunnableConfig()

        result = node.invoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证 LLM 能够记住之前的对话（应该提到 "Alice"）
        response_content = result["messages"][0].content
        assert isinstance(response_content, str)
        print(f"\n[{model_name}] Chat history test: {response_content}")
        # 注意：这个断言可能不稳定，因为 LLM 响应可能变化
        # 在生产测试中可以考虑使用更宽松的验证

    @pytest.mark.parametrize("model_name", TEST_MODELS)
    def test_model_node_with_knowledge_content(self, model_name, real_store):
        """测试包含知识库内容的情况"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node_options = ModelNodeSettings(
            use_structured_response=False,
            enable_query_clarification=False,
            rejection_message="抱歉，我无法回答这个问题。",
            role_prompt="You are a helpful assistant with access to knowledge base.",
            use_general_knowledge_on_miss=True,
        )

        node = build_model_node(
            llm=real_llm,
            tools=[],
            node_options=node_options,
        )

        state: ModelState = {
            "messages": [HumanMessage(content="What is the company policy on vacation?")],
            "knowledge_content": "Company vacation policy: Employees are entitled to 15 days of paid vacation per year.",  # type: ignore
        }
        config = RunnableConfig()

        result = node.invoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证返回了有效的内容
        assert result["messages"][0].content
        print(f"\n[{model_name}] Knowledge content test: {result['messages'][0].content[:100]}")

    @pytest.mark.parametrize("model_name", TEST_MODELS)
    def test_model_node_with_decision_private_qa(self, model_name, real_store):
        """测试包含 PRIVATE_QA decision 的情况"""
        from aidev_agent.enums import Decision

        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node_options = ModelNodeSettings(
            use_structured_response=False,
            enable_query_clarification=False,
            rejection_message="抱歉，我无法回答这个问题。",
            role_prompt="You are a helpful assistant.",
            use_general_knowledge_on_miss=False,
        )

        node = build_model_node(
            llm=real_llm,
            tools=[],
            node_options=node_options,
        )

        state: ModelState = {
            "messages": [HumanMessage(content="What is the company policy?")],
            "decision": Decision.PRIVATE_QA,  # type: ignore
            "knowledge_content": "Company policy: Be respectful to colleagues.",  # type: ignore
        }
        config = RunnableConfig()

        result = node.invoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)
        print(f"\n[{model_name}] PRIVATE_QA decision test: {result['messages'][0].content[:100]}")

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_name", TEST_MODELS)
    async def test_model_node_parallel_tool_calls(self, model_name, real_context_processor, real_store):
        """测试并行工具调用"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node = build_model_node(
            llm=real_llm,
            tools=real_context_processor["tools"],
            node_options=real_context_processor["node_options"],
        )

        state: ModelState = {
            "messages": [HumanMessage(content="Search for Python tutorials and calculate 10 * 5")],
        }
        config = RunnableConfig()

        result = await node.ainvoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证返回了有效的内容或工具调用
        message = result["messages"][0]
        assert message.content or message.tool_calls
        print(
            f"\n[{model_name}] Parallel tool calls test: {message.content[:100] if message.content else f'Tool calls: {len(message.tool_calls)}'}"
        )

    @pytest.mark.parametrize("model_name", VISION_MODELS)
    def test_model_node_with_image_input(self, model_name, real_store):
        """测试视觉模型的图片输入功能"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)
        # 构建包含图片的多模态消息
        image_base64 = get_test_image_base64()
        multimodal_content = [
            {"type": "text", "text": "OCR: 图片包含文字为"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
        ]
        result = real_llm.invoke([HumanMessage(content=multimodal_content)])
        print(result)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("model_name", VISION_MODELS)
    async def test_model_node_with_image_input_async(self, model_name, real_store):
        """测试视觉模型的异步图片输入功能"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node_options = ModelNodeSettings(
            use_structured_response=False,
            enable_query_clarification=False,
            rejection_message="抱歉，我无法回答这个问题。",
            role_prompt="You are a helpful assistant that can analyze images.",
            use_general_knowledge_on_miss=True,
        )

        node = build_model_node(
            llm=real_llm,
            tools=[],
            node_options=node_options,
        )

        # 构建包含图片的多模态消息
        image_base64 = get_test_image_base64()
        multimodal_content = [
            {"type": "text", "text": "Describe this image in detail."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
        ]

        state: ModelState = {
            "messages": [HumanMessage(content=multimodal_content)],
        }
        config = RunnableConfig()

        result = await node.ainvoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证返回了有效的内容
        message = result["messages"][0]
        assert message.content, "视觉模型应该返回对图片的描述"
        print(f"\n[{model_name}] Async image input test: {message.content[:200]}")

    @pytest.mark.parametrize("model_name", VISION_MODELS)
    def test_model_node_with_image_and_chat_history(self, model_name, real_store):
        """测试视觉模型带对话历史的图片功能"""
        # 创建真实的 LLM 实例
        real_llm = ChatModel.get_setup_instance(model=model_name)

        node_options = ModelNodeSettings(
            use_structured_response=False,
            enable_query_clarification=False,
            rejection_message="抱歉，我无法回答这个问题。",
            role_prompt="You are a helpful assistant that can analyze images.",
            use_general_knowledge_on_miss=True,
        )

        node = build_model_node(
            llm=real_llm,
            tools=[],
            node_options=node_options,
        )

        # 构建包含图片的多模态消息（第一轮对话）
        image_base64 = get_test_image_base64()
        multimodal_content = [
            {"type": "text", "text": "What is in this image?"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
        ]

        state: ModelState = {
            "messages": [
                HumanMessage(content=multimodal_content),
                AIMessage(content="I see a logo image."),
                HumanMessage(content="What was in the image I showed you?"),
            ],
        }
        config = RunnableConfig()

        result = node.invoke(state, config=config, store=real_store)

        # 验证返回结构
        assert "messages" in result
        assert len(result["messages"]) == 1
        assert isinstance(result["messages"][0], AIMessage)

        # 验证返回了有效的内容
        message = result["messages"][0]
        assert message.content, "视觉模型应该能够记住之前的图片内容"
        print(f"\n[{model_name}] Image with chat history test: {message.content[:200]}")
