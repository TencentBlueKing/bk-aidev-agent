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

import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import openai
import pytest
from aidev_agent.config import settings
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from langchain_core.messages import HumanMessage

# 测试模型列表
TEST_MODELS = ["hunyuan-turbo", "qwen3", "deepseek-v3", "deepseek-r1"]

# 支持函数调用的模型列表
TEST_FUNCTION_CALL_MODELS = ["hunyuan-turbo", "qwen3", "deepseek-v3"]

# 支持思考/推理能力的模型列表
TEST_REASONING_MODELS = ["deepseek-r1"]

# 支持视觉能力的模型列表
TEST_VISION_MODELS = ["qwen3-vl-32B"]

# 测试图片路径
TEST_IMAGE_PATH = Path(__file__).parent.parent.parent.parent / "mock_data" / "bkaidev.png"
TEST_BASE_URL = "https://llm-gateway.example.com/v1"


def get_test_image_base64() -> str:
    """读取测试图片并返回 base64 编码"""
    with open(TEST_IMAGE_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def test_chat_model_async_clients_are_isolated_across_worker_threads():
    with ThreadPoolExecutor(max_workers=4) as pool:
        models = list(
            pool.map(
                lambda index: ChatModel.get_setup_instance(model=f"model-{index}", base_url=TEST_BASE_URL),
                range(16),
            )
        )

    try:
        clients = [model.http_async_client for model in models]
        assert len({id(client) for client in clients}) == len(clients)
        assert all(model._owns_http_async_client for model in models)
    finally:
        for client in clients:
            asyncio.run(client.aclose())


def test_chat_model_preserves_caller_owned_async_http_client():
    client = openai.DefaultAsyncHttpxClient()
    model = ChatModel.get_setup_instance(
        model="explicit-client",
        base_url=TEST_BASE_URL,
        http_async_client=client,
    )

    try:
        assert model.http_async_client is client
        assert model._owns_http_async_client is False
    finally:
        asyncio.run(client.aclose())


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
@pytest.mark.parametrize("model_name", TEST_MODELS)
def test_chat_model_simple_invoke(model_name):
    """测试纯模型调用 - 简单的同步调用"""
    # 创建模型实例
    chat_model = ChatModel.get_setup_instance(model=model_name)

    # 简单的消息
    messages = [HumanMessage(content="你好，请用一句话介绍你自己")]

    # 调用模型
    response = chat_model.invoke(messages)

    # 验证响应
    assert response is not None
    assert response.content
    assert len(response.content) > 0
    print(f"\n[{model_name}] 响应: {response.content}")


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
@pytest.mark.parametrize("model_name", TEST_MODELS)
def test_chat_model_streaming(model_name):
    """测试纯模型调用 - 流式响应"""
    # 创建模型实例
    chat_model = ChatModel.get_setup_instance(model=model_name)

    # 简单的消息
    messages = [HumanMessage(content="请简单说一下 Python 的特点")]

    # 流式调用
    chunks = []
    for chunk in chat_model.stream(messages):
        chunks.append(chunk)
        assert chunk is not None

    # 验证响应
    assert len(chunks) > 0
    full_content = "".join([chunk.content for chunk in chunks if chunk.content])
    assert len(full_content) > 0
    print(f"\n[{model_name}] 流式响应完整内容长度: {len(full_content)}")


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
@pytest.mark.parametrize("model_name", TEST_FUNCTION_CALL_MODELS)
def test_chat_model_with_tool_call(model_name):
    """测试工具调用 - bind_tools 和 tool_choice"""
    # 定义一个简单的工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "获取指定城市的天气信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "城市名称，例如：北京、上海",
                        },
                    },
                    "required": ["city"],
                },
            },
        }
    ]

    # 创建模型实例并绑定工具
    chat_model = ChatModel.get_setup_instance(model=model_name)
    chat_model_with_tools = chat_model.bind_tools(tools)

    # 构造会触发工具调用的消息 - 明确要求调用工具
    messages = [HumanMessage(content="调用get_weather去获取深圳天气")]

    # 调用模型
    response = chat_model_with_tools.invoke(messages)

    # 验证响应
    assert response is not None

    # 检查是否有工具调用 - 必须有工具调用
    print(f"\n[{model_name}] 工具调用测试响应类型: {type(response)}")
    print(f"[{model_name}] 响应内容: {response.content if response.content else '(空)'}")

    # 验证必须有 tool_calls
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"[{model_name}] 工具调用: {response.tool_calls}")
        assert len(response.tool_calls) > 0
        # 验证调用的是 get_weather 工具
        assert response.tool_calls[0]["name"] == "get_weather"
    elif hasattr(response, "additional_kwargs") and response.additional_kwargs.get("tool_calls"):
        print(f"[{model_name}] 工具调用 (additional_kwargs): {response.additional_kwargs['tool_calls']}")
        assert len(response.additional_kwargs["tool_calls"]) > 0
    else:
        pytest.fail(f"[{model_name}] 模型未返回工具调用")


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
@pytest.mark.parametrize("model_name", TEST_FUNCTION_CALL_MODELS)
def test_chat_model_with_tool_streaming(model_name):
    """测试工具调用 - 流式响应"""
    # 定义工具
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "执行数学计算",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "数学表达式，例如：2+2",
                        },
                    },
                    "required": ["expression"],
                },
            },
        }
    ]

    # 创建模型实例并绑定工具
    chat_model = ChatModel.get_setup_instance(model=model_name)
    chat_model_with_tools = chat_model.bind_tools(tools)

    # 构造消息
    messages = [HumanMessage(content="计算 15 + 27 等于多少")]

    # 流式调用
    chunks = []
    for chunk in chat_model_with_tools.stream(messages):
        chunks.append(chunk)
        assert chunk is not None

    # 验证响应
    assert len(chunks) > 0
    print(f"\n[{model_name}] 工具流式调用收到 {len(chunks)} 个 chunks")

    # 检查是否有工具调用信息
    for i, chunk in enumerate(chunks):
        if hasattr(chunk, "tool_call_chunks") and chunk.tool_call_chunks:
            print(f"[{model_name}] Chunk {i} 包含工具调用: {chunk.tool_call_chunks}")


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
@pytest.mark.parametrize("model_name", TEST_REASONING_MODELS)
def test_chat_model_reasoning_content(model_name):
    """测试支持推理能力的模型的 reasoning_content 功能"""
    # 创建模型实例
    chat_model = ChatModel.get_setup_instance(model=model_name)

    # 构造需要推理的问题
    messages = [HumanMessage(content="请解释为什么 1+1=2")]

    # 调用模型
    response = chat_model.invoke(messages)

    # 验证响应
    assert response is not None
    print(f"\n[{model_name}] 响应内容: {response.content[:100] if response.content else '(空)'}...")

    # 检查是否有 reasoning_content
    if hasattr(response, "additional_kwargs") and "reasoning_content" in response.additional_kwargs:
        reasoning = response.additional_kwargs["reasoning_content"]
        print(f"[{model_name}] 推理内容: {reasoning[:100] if reasoning else '(空)'}...")
        assert reasoning is not None


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
@pytest.mark.parametrize("model_name", TEST_VISION_MODELS)
def test_chat_model_vision_invoke(model_name):
    """测试视觉模型的图片输入功能 - 同步调用"""
    # 创建模型实例
    chat_model = ChatModel.get_setup_instance(model=model_name)

    # 构建包含图片的多模态消息
    image_base64 = get_test_image_base64()
    multimodal_content = [
        {"type": "text", "text": "请描述这张图片的内容，特别需要包含有什么文字"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
    ]
    messages = [HumanMessage(content=multimodal_content)]

    # 调用模型
    response = chat_model.invoke(messages)

    # 验证响应
    assert response is not None
    assert response.content
    assert len(response.content) > 0
    print(f"\n[{model_name}] 图片描述响应: {response.content[:200]}")
    assert "AIDEV" in response.content


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
@pytest.mark.parametrize("model_name", TEST_VISION_MODELS)
def test_chat_model_vision_streaming(model_name):
    """测试视觉模型的图片输入功能 - 流式响应"""
    # 创建模型实例
    chat_model = ChatModel.get_setup_instance(model=model_name)

    # 构建包含图片的多模态消息
    image_base64 = get_test_image_base64()
    multimodal_content = [
        {"type": "text", "text": "详细描述这张图片中的所有元素"},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
    ]
    messages = [HumanMessage(content=multimodal_content)]

    # 流式调用
    chunks = []
    for chunk in chat_model.stream(messages):
        chunks.append(chunk)
        assert chunk is not None

    # 验证响应
    assert len(chunks) > 0
    full_content = "".join([chunk.content for chunk in chunks if chunk.content])
    assert len(full_content) > 0
    print(f"\n[{model_name}] 图片流式响应完整内容长度: {len(full_content)}")
    print(f"[{model_name}] 图片流式响应内容: {full_content[:200]}")
