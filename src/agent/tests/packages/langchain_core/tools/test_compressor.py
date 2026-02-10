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
from typing import Any, TypedDict
from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.api import BKAidevApi
from aidev_agent.config import settings
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.langchain_core.tools.enhance import (
    _build_extended_schema,
    create_enhanced_tool,
)
from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# ============== 测试用的工具和压缩函数 ==============


class SimpleToolInput(BaseModel):
    """简单工具输入 - BaseModel schema"""

    city: str = Field(..., description="城市名称")


def simple_tool_func(city: str) -> str:
    """简单的同步工具函数"""
    return f"Weather in {city}: Sunny, 25°C"


async def simple_tool_func_async(city: str) -> str:
    """简单的异步工具函数"""
    await asyncio.sleep(0.1)  # 模拟异步操作
    return f"Weather in {city}: Sunny, 25°C"


def mock_compressor(original_result, tool_name: str, *, invoke_intent: str = None, **kwargs) -> str:
    """模拟的压缩函数"""
    compressed = f"[Compressed] {original_result[:100]}..."
    if invoke_intent:
        compressed += f" (Intent: {invoke_intent})"
    return compressed


async def mock_compressor_async(original_result, tool_name: str, *, invoke_intent: str = None, **kwargs) -> str:
    """模拟的异步压缩函数"""
    await asyncio.sleep(0.05)
    return mock_compressor(original_result, tool_name, invoke_intent=invoke_intent, **kwargs)


def error_compressor(original_result, tool_name: str, *, invoke_intent: str = None, **kwargs) -> str:
    """会抛出异常的压缩函数"""
    raise ValueError("Compression failed!")


def error_tool_func(city: str) -> str:
    """会抛出异常的工具函数"""
    raise RuntimeError("Tool execution failed!")


# ============== Schema 构建测试 ==============


def test_build_extended_schema_with_basemodel():
    """测试 BaseModel schema 扩展 - 添加 invoke_intent 字段"""
    extended_schema = _build_extended_schema(SimpleToolInput, intent_description="Test intent description")

    # 验证是 BaseModel 类型
    assert issubclass(extended_schema, BaseModel)

    # 验证原有字段存在
    assert "city" in extended_schema.model_fields

    # 验证 invoke_intent 字段存在且为必填
    assert "invoke_intent" in extended_schema.model_fields
    invoke_intent_field = extended_schema.model_fields["invoke_intent"]
    assert invoke_intent_field.is_required()
    assert "Test intent description" in invoke_intent_field.description


def test_build_extended_schema_with_dict():
    """测试 dict schema 扩展 - 模拟 MCP 工具"""
    original_dict_schema = {
        "type": "object",
        "properties": {"location": {"type": "string", "description": "Location name"}},
        "required": ["location"],
    }

    extended_schema = _build_extended_schema(original_dict_schema, intent_description="MCP tool intent")

    # 验证是 dict 类型
    assert isinstance(extended_schema, dict)

    # 验证原有字段存在
    assert "location" in extended_schema["properties"]

    # 验证 invoke_intent 字段存在且为必填
    assert "invoke_intent" in extended_schema["properties"]
    assert "MCP tool intent" in extended_schema["properties"]["invoke_intent"]["description"]
    assert "invoke_intent" in extended_schema["required"]


def test_build_extended_schema_with_none():
    """测试空 schema 扩展"""
    extended_schema = _build_extended_schema(None, intent_description="Empty tool intent")

    # 验证是 dict 类型
    assert isinstance(extended_schema, dict)

    # 验证 invoke_intent 字段存在且为必填
    assert "invoke_intent" in extended_schema["properties"]
    assert "invoke_intent" in extended_schema["required"]


# ============== EnhancedTool 基础功能测试 ==============


def test_compressed_tool_creation():
    """测试 EnhancedTool 创建"""
    # 创建原始工具
    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather information", args_schema=SimpleToolInput
    )

    # 创建压缩工具
    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=False
    )

    # 验证基本属性
    assert compressed_tool.name == "weather_tool"
    assert compressed_tool.description == "Get weather information"
    assert compressed_tool.show_intent is False
    assert compressed_tool.fallback_on_error is True


def test_compressed_tool_with_intent_schema_basemodel():
    """测试启用 show_intent 后 BaseModel schema 正确修改"""
    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=True
    )

    # 验证 args_schema 包含 invoke_intent
    assert compressed_tool.args_schema is not None
    assert "invoke_intent" in compressed_tool.args_schema.model_fields
    assert "city" in compressed_tool.args_schema.model_fields


def test_compressed_tool_with_intent_schema_dict():
    """测试启用 show_intent 后 dict schema 正确修改"""
    # 创建使用 dict schema 的工具
    dict_schema = {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Search query"}},
        "required": ["query"],
    }

    original_tool = StructuredTool(
        name="search_tool",
        description="Search tool",
        func=lambda query: f"Results for {query}",
        args_schema=dict_schema,
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=True
    )

    # 验证 args_schema 包含 invoke_intent
    schema = compressed_tool.args_schema
    assert "invoke_intent" in schema["properties"]
    assert "invoke_intent" in schema["required"]


# ============== 同步调用测试 ==============


def test_compressed_tool_sync_invoke_without_intent():
    """测试同步调用 - 不启用 intent"""
    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=False
    )

    # 调用工具
    result = compressed_tool.invoke({"city": "Beijing"})

    # 验证结果被压缩
    assert "[Compressed]" in result
    assert "Weather in Beijing" in result


def test_compressed_tool_sync_invoke_with_intent():
    """测试同步调用 - 启用 intent"""
    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=True
    )

    # 调用工具时提供 invoke_intent
    result = compressed_tool.invoke({"city": "Shanghai", "invoke_intent": "Check weather for trip planning"})

    # 验证结果包含 intent 信息
    assert "[Compressed]" in result
    assert "Intent: Check weather for trip planning" in result


def test_compressed_tool_sync_invoke_missing_intent_raises_error():
    """测试同步调用 - 启用 intent 但未提供时应抛出异常"""
    from pydantic import ValidationError

    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=True
    )

    # 未提供 invoke_intent 应抛出 ValidationError（Pydantic 验证错误）
    with pytest.raises(ValidationError, match="invoke_intent"):
        compressed_tool.invoke({"city": "Beijing"})


# ============== 异步调用测试 ==============


@pytest.mark.asyncio
async def test_compressed_tool_async_invoke_without_intent():
    """测试异步调用 - 不启用 intent"""
    original_tool = StructuredTool.from_function(
        coroutine=simple_tool_func_async, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=False
    )

    # 异步调用工具
    result = await compressed_tool.ainvoke({"city": "Beijing"})

    # 验证结果被压缩
    assert "[Compressed]" in result
    assert "Weather in Beijing" in result


@pytest.mark.asyncio
async def test_compressed_tool_async_invoke_with_async_compressor():
    """测试异步调用 - 使用异步压缩函数"""
    original_tool = StructuredTool.from_function(
        coroutine=simple_tool_func_async, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool,
        compressor_func=mock_compressor_async,  # 异步压缩函数
        show_intent=False,
    )

    # 异步调用工具
    result = await compressed_tool.ainvoke({"city": "Shenzhen"})

    # 验证结果被压缩
    assert "[Compressed]" in result
    assert "Weather in Shenzhen" in result


@pytest.mark.asyncio
async def test_compressed_tool_async_invoke_with_intent():
    """测试异步调用 - 启用 intent"""
    original_tool = StructuredTool.from_function(
        coroutine=simple_tool_func_async, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor_async, show_intent=True
    )

    # 异步调用工具时提供 invoke_intent
    result = await compressed_tool.ainvoke({"city": "Guangzhou", "invoke_intent": "Weather check for outdoor event"})

    # 验证结果包含 intent 信息
    assert "[Compressed]" in result
    assert "Intent: Weather check for outdoor event" in result


# ============== 错误处理测试 ==============


def test_original_tool_error_propagates():
    """测试原始工具报错时异常正确传播"""
    original_tool = StructuredTool.from_function(
        func=error_tool_func, name="error_tool", description="Tool that raises error", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=False
    )

    # 原始工具抛出的异常应该被传播
    with pytest.raises(RuntimeError, match="Tool execution failed!"):
        compressed_tool.invoke({"city": "Beijing"})


def test_compressor_error_with_fallback_disabled():
    """测试压缩函数报错 - fallback_on_error=False 时抛出异常"""
    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool,
        compressor_func=error_compressor,  # 会抛出异常的压缩函数
        show_intent=False,
        fallback_on_error=False,  # 禁用降级
    )

    # 压缩函数的异常应该被抛出
    with pytest.raises(ValueError, match="Compression failed!"):
        compressed_tool.invoke({"city": "Beijing"})


def test_compressor_error_with_fallback_enabled():
    """测试压缩函数报错 - fallback_on_error=True 时返回原始结果"""
    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool,
        compressor_func=error_compressor,  # 会抛出异常的压缩函数
        show_intent=False,
        fallback_on_error=True,  # 启用降级
    )

    # 应该返回原始结果
    result = compressed_tool.invoke({"city": "Beijing"})

    # 验证返回的是原始结果（未压缩）
    assert result == "Weather in Beijing: Sunny, 25°C"
    assert "[Compressed]" not in result


def test_compressor_success_returns_compressed_result():
    """测试正常情况 - 返回压缩后的结果"""
    original_tool = StructuredTool.from_function(
        func=simple_tool_func, name="weather_tool", description="Get weather", args_schema=SimpleToolInput
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=False
    )

    result = compressed_tool.invoke({"city": "Beijing"})

    # 验证返回压缩后的结果
    assert "[Compressed]" in result


# ============== 与 ChatModel 集成测试 ==============


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_compressed_tool_with_chatmodel_without_intent():
    """测试 EnhancedTool 与 ChatModel 集成 - 不启用 intent (真实请求)"""
    # 获取 weather-query 工具
    client = BKAidevApi.get_client()
    weather_tool = client.construct_tool("weather-query")

    # 创建压缩工具（不启用 intent）
    compressed_tool = create_enhanced_tool(
        original_tool=weather_tool, compressor_func=mock_compressor, show_intent=False, fallback_on_error=True
    )

    # 创建 ChatModel
    chat_model = ChatModel.get_setup_instance(model="qwen3")
    chat_model_with_tool = chat_model.bind_tools([compressed_tool])

    # 调用模型
    messages = [HumanMessage(content="调用weather-query查询深圳市的天气")]
    response = chat_model_with_tool.invoke(messages)

    # 验证响应
    assert response is not None
    print(f"\n[Test] Response content: {response.content}")

    # 检查是否有工具调用
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"[Test] Tool calls: {response.tool_calls}")
        tool_call = response.tool_calls[0]

        # 验证工具调用不包含 invoke_intent 参数
        assert "invoke_intent" not in tool_call.get("args", {})


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_compressed_tool_with_chatmodel_with_intent():
    """测试 EnhancedTool 与 ChatModel 集成 - 启用 intent (真实请求)"""
    # 获取 weather-query 工具
    client = BKAidevApi.get_client()
    weather_tool = client.construct_tool("weather-query")

    # 创建压缩工具（启用 intent）
    compressed_tool = create_enhanced_tool(
        original_tool=weather_tool, compressor_func=mock_compressor, show_intent=True, fallback_on_error=True
    )

    # 创建 ChatModel
    chat_model = ChatModel.get_setup_instance(model="qwen3")
    chat_model_with_tool = chat_model.bind_tools([compressed_tool])

    # 调用模型
    messages = [HumanMessage(content="调用weather-query查询深圳市的天气")]
    response = chat_model_with_tool.invoke(messages)

    # 验证响应
    assert response is not None
    print(f"\n[Test] Response content: {response.content}")

    # 检查是否有工具调用
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"[Test] Tool calls: {response.tool_calls}")
        tool_call = response.tool_calls[0]

        # 验证工具调用包含 invoke_intent 参数
        assert "invoke_intent" in tool_call.get("args", {}), "启用 show_intent 后，模型应该输出 invoke_intent 参数"

        print(f"[Test] invoke_intent: {tool_call['args']['invoke_intent']}")


# ============== Mock 测试 - 模拟模型响应 ==============


def test_compressed_tool_with_chatmodel_mock_without_intent():
    """测试 EnhancedTool 与 ChatModel 集成 - Mock 版本 (不启用 intent)"""
    # 创建一个简单的工具用于测试
    original_tool = StructuredTool.from_function(
        func=simple_tool_func,
        name="weather_query",
        description="Query weather information",
        args_schema=SimpleToolInput,
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=False
    )

    # Mock 模型响应 - 包含工具调用
    mock_response = MagicMock()
    mock_response.content = ""
    mock_response.tool_calls = [{"name": "weather_query", "args": {"city": "Shenzhen"}, "id": "call_123"}]

    with patch.object(ChatModel, "invoke", return_value=mock_response):
        chat_model = ChatModel.get_setup_instance(model="qwen3")
        chat_model_with_tool = chat_model.bind_tools([compressed_tool])

        messages = [HumanMessage(content="Query weather in Shenzhen")]
        response = chat_model_with_tool.invoke(messages)

        # 验证响应
        assert response.tool_calls
        assert response.tool_calls[0]["name"] == "weather_query"
        assert "invoke_intent" not in response.tool_calls[0]["args"]


def test_compressed_tool_with_chatmodel_mock_with_intent():
    """测试 EnhancedTool 与 ChatModel 集成 - Mock 版本 (启用 intent)"""
    # 创建一个简单的工具用于测试
    original_tool = StructuredTool.from_function(
        func=simple_tool_func,
        name="weather_query",
        description="Query weather information",
        args_schema=SimpleToolInput,
    )

    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=True
    )

    # Mock 模型响应 - 包含工具调用和 invoke_intent
    mock_response = MagicMock()
    mock_response.content = ""
    mock_response.tool_calls = [
        {
            "name": "weather_query",
            "args": {"city": "Shenzhen", "invoke_intent": "Check weather for travel planning"},
            "id": "call_456",
        }
    ]

    with patch.object(ChatModel, "invoke", return_value=mock_response):
        chat_model = ChatModel.get_setup_instance(model="qwen3")
        chat_model_with_tool = chat_model.bind_tools([compressed_tool])

        messages = [HumanMessage(content="Query weather in Shenzhen")]
        response = chat_model_with_tool.invoke(messages)

        # 验证响应
        assert response.tool_calls
        assert response.tool_calls[0]["name"] == "weather_query"
        assert "invoke_intent" in response.tool_calls[0]["args"]
        assert response.tool_calls[0]["args"]["invoke_intent"] == "Check weather for travel planning"


# ============== InjectedState 注解测试 ==============
def test_compressed_tool_with_injected_state():
    """测试 EnhancedTool 与 InjectedState 注解 - 使用 ToolNode 和 LangGraph"""
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import InjectedState, ToolNode
    from typing_extensions import Annotated

    # 定义完整的工具函数，包含所有类型的参数
    def weather_tool_full(
        city: str,
        state: Annotated[dict, InjectedState],
        user: Annotated[str, InjectedState("user")],
        config: RunnableConfig,
    ) -> str:
        """Complete weather tool with all parameter types"""
        session_id = state.get("session_id", "unknown")
        request_count = state.get("request_count", 0)

        return (
            f"Weather in {city}\n"
            f"User: {user}\n"
            f"Session: {session_id}\n"
            f"Request: #{request_count}\n"
            f"Config: {config['configurable']['thread_id']}"
        )

    # 创建原始工具
    original_tool = StructuredTool.from_function(
        func=weather_tool_full, name="weather_tool", description="Get weather with full state context"
    )

    # 创建两个压缩工具：一个有 intent，一个没有
    compressed_tool_no_intent = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=False
    )

    compressed_tool_with_intent = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=True
    )

    # 验证 schema 结构
    # 无 intent 版本
    schema_no_intent = compressed_tool_no_intent.args_schema.model_fields
    assert "city" in schema_no_intent
    assert "state" in schema_no_intent
    assert "user" in schema_no_intent
    # 注意：config (RunnableConfig) 不会出现在 schema 中，它由 LangChain 自动注入
    assert "invoke_intent" not in schema_no_intent

    # 有 intent 版本
    schema_with_intent = compressed_tool_with_intent.args_schema.model_fields
    assert "city" in schema_with_intent
    assert "state" in schema_with_intent
    assert "user" in schema_with_intent
    assert "invoke_intent" in schema_with_intent

    # 验证 InjectedState 标记
    assert any(isinstance(m, type) and issubclass(m, InjectedState) for m in schema_no_intent["state"].metadata)
    assert any(isinstance(m, InjectedState) for m in schema_no_intent["user"].metadata)

    # 构建 LangGraph: START -> ToolNode -> END
    class AgentState(TypedDict):
        """Agent state"""

        messages: list
        user: str
        session_id: str
        request_count: int

    # 测试场景 1: 无 intent 工具
    workflow_no_intent = StateGraph(AgentState)
    tool_node_no_intent = ToolNode([compressed_tool_no_intent])
    workflow_no_intent.add_node("tools", tool_node_no_intent)
    workflow_no_intent.add_edge(START, "tools")
    workflow_no_intent.add_edge("tools", END)
    graph_no_intent = workflow_no_intent.compile()

    # 构造输入：AIMessage 带 tool_calls
    ai_message_no_intent = AIMessage(
        content="",
        tool_calls=[{"name": "weather_tool", "args": {"city": "Beijing"}, "id": "call_001", "type": "tool_call"}],
    )

    # 执行 Graph（state 会自动注入）
    state: Any = {"messages": [ai_message_no_intent], "user": "alice", "session_id": "session_123", "request_count": 5}
    result_no_intent = graph_no_intent.invoke(state, config={"configurable": {"thread_id": "thread_id_1234"}})

    # 验证结果
    tool_messages_no_intent = [m for m in result_no_intent["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages_no_intent) == 1
    tool_result = tool_messages_no_intent[0].content

    # 验证压缩结果包含注入的信息
    assert "[Compressed]" in tool_result
    assert "Beijing" in tool_result
    assert "alice" in tool_result
    assert "session_123" in tool_result
    assert "thread_id_1234" in tool_result

    # 测试场景 2: 有 intent 工具
    workflow_with_intent = StateGraph(AgentState)
    tool_node_with_intent = ToolNode([compressed_tool_with_intent])
    workflow_with_intent.add_node("tools", tool_node_with_intent)
    workflow_with_intent.add_edge(START, "tools")
    workflow_with_intent.add_edge("tools", END)
    graph_with_intent = workflow_with_intent.compile()

    # 构造输入：AIMessage 带 tool_calls（包含 invoke_intent）
    ai_message_with_intent = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "weather_tool",
                "args": {"city": "Shanghai", "invoke_intent": "Check weather for travel planning"},
                "id": "call_002",
                "type": "tool_call",
            }
        ],
    )

    # 执行 Graph
    state = {"messages": [ai_message_with_intent], "user": "bob", "session_id": "session_456", "request_count": 10}
    result_with_intent = graph_with_intent.invoke(state, config={"configurable": {"thread_id": "thread_id_5678"}})

    # 验证结果
    tool_messages_with_intent = [m for m in result_with_intent["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages_with_intent) == 1
    tool_result_intent = tool_messages_with_intent[0].content

    # 验证压缩结果包含 intent 和注入的信息
    assert "[Compressed]" in tool_result_intent
    assert "Shanghai" in tool_result_intent
    assert "bob" in tool_result_intent
    assert "session_456" in tool_result_intent
    assert "thread_id_5678" in tool_result_intent
    assert "Intent: Check weather for travel planning" in tool_result_intent


@pytest.mark.asyncio
async def test_compressed_tool_with_injected_state_async():
    """测试 EnhancedTool 异步调用 + InjectedState - 使用 ToolNode 和 LangGraph"""
    from langchain_core.messages import AIMessage, ToolMessage
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph
    from langgraph.prebuilt import InjectedState, ToolNode
    from typing_extensions import Annotated

    # 定义异步工具函数
    async def async_weather_tool_full(
        city: str,
        state: Annotated[dict, InjectedState],
        user: Annotated[str, InjectedState("user")],
        config: RunnableConfig,
    ) -> str:
        """Async weather tool with all parameter types"""
        await asyncio.sleep(0.1)  # 模拟异步操作

        session_id = state.get("session_id", "unknown")
        request_count = state.get("request_count", 0)

        return (
            f"Async Weather in {city}\n"
            f"User: {user}\n"
            f"Session: {session_id}\n"
            f"Request: #{request_count}\n"
            f"Config: {config['configurable']['thread_id']}"
        )

    # 创建原始工具
    original_tool = StructuredTool.from_function(
        coroutine=async_weather_tool_full,
        name="async_weather_tool",
        description="Get weather async with full state context",
    )

    # 创建两个压缩工具：一个有 intent，一个没有
    compressed_tool_no_intent = create_enhanced_tool(
        original_tool=original_tool,
        compressor_func=mock_compressor_async,  # 使用异步压缩函数
        show_intent=False,
    )

    compressed_tool_with_intent = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor_async, show_intent=True
    )

    # 验证 schema 结构
    schema_no_intent = compressed_tool_no_intent.args_schema.model_fields
    assert "city" in schema_no_intent
    assert "invoke_intent" not in schema_no_intent

    schema_with_intent = compressed_tool_with_intent.args_schema.model_fields
    assert "city" in schema_with_intent
    assert "invoke_intent" in schema_with_intent

    # 构建 LangGraph: START -> ToolNode -> END
    class AgentState(dict):
        """Agent state"""

        messages: list
        user: str
        session_id: str
        request_count: int

    # 测试场景 1: 异步工具（无 intent）
    workflow_no_intent = StateGraph(AgentState)
    tool_node_no_intent = ToolNode([compressed_tool_no_intent])
    workflow_no_intent.add_node("tools", tool_node_no_intent)
    workflow_no_intent.add_edge(START, "tools")
    workflow_no_intent.add_edge("tools", END)
    graph_no_intent = workflow_no_intent.compile()

    ai_message_no_intent = AIMessage(
        content="",
        tool_calls=[
            {"name": "async_weather_tool", "args": {"city": "Guangzhou"}, "id": "call_003", "type": "tool_call"}
        ],
    )

    # 异步执行 Graph
    state: Any = {
        "messages": [ai_message_no_intent],
        "user": "charlie",
        "session_id": "session_789",
        "request_count": 15,
    }
    result_no_intent = await graph_no_intent.ainvoke(state, config={"configurable": {"thread_id": "thread_id_1234"}})

    # 验证结果
    tool_messages = [m for m in result_no_intent["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1
    tool_result = tool_messages[0].content

    # 验证压缩结果
    assert "[Compressed]" in tool_result
    assert "Guangzhou" in tool_result
    assert "charlie" in tool_result
    assert "session_789" in tool_result
    assert "thread_id_1234" in tool_result

    # 测试场景 2: 异步工具（有 intent）
    workflow_with_intent = StateGraph(AgentState)
    tool_node_with_intent = ToolNode([compressed_tool_with_intent])
    workflow_with_intent.add_node("tools", tool_node_with_intent)
    workflow_with_intent.add_edge(START, "tools")
    workflow_with_intent.add_edge("tools", END)
    graph_with_intent = workflow_with_intent.compile()

    ai_message_with_intent = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "async_weather_tool",
                "args": {"city": "Shenzhen", "invoke_intent": "Async weather monitoring"},
                "id": "call_004",
                "type": "tool_call",
            }
        ],
    )

    # 异步执行 Graph
    state: Any = {
        "messages": [ai_message_with_intent],
        "user": "david",
        "session_id": "session_101",
        "request_count": 20,
    }
    result_with_intent = await graph_with_intent.ainvoke(
        state, config={"configurable": {"thread_id": "thread_id_5678"}}
    )

    # 验证结果
    tool_messages_intent = [m for m in result_with_intent["messages"] if isinstance(m, ToolMessage)]
    assert len(tool_messages_intent) == 1
    tool_result_intent = tool_messages_intent[0].content

    # 验证压缩结果
    assert "[Compressed]" in tool_result_intent
    assert "Shenzhen" in tool_result_intent
    assert "david" in tool_result_intent
    assert "session_101" in tool_result_intent
    assert "thread_id_5678" in tool_result_intent
    assert "Intent: Async weather monitoring" in tool_result_intent


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_compressed_tool_injected_state_schema_structure():
    """测试 InjectedState 参数在 EnhancedTool 中的 schema 结构保持正确"""
    from langgraph.prebuilt import InjectedState
    from pydantic import BaseModel, Field
    from typing_extensions import Annotated

    # 定义带 schema 的工具
    class WeatherInput(BaseModel):
        city: str = Field(description="City name")
        units: str = Field(default="celsius", description="Temperature units")

    def tool_with_schema_and_state(
        city: str, units: str = "celsius", state: Annotated[dict, InjectedState] = None
    ) -> str:
        """Tool with both schema and injected state"""
        user = state.get("user", "guest") if state else "guest"
        return f"Weather in {city} ({units}) for {user}: 25°"

    # 创建工具
    original_tool = StructuredTool.from_function(
        func=tool_with_schema_and_state,
        name="weather_schema",
        description="Weather query with schema",
        args_schema=WeatherInput,
    )

    # 创建压缩工具（启用 intent）
    compressed_tool = create_enhanced_tool(
        original_tool=original_tool, compressor_func=mock_compressor, show_intent=True
    )
    # 创建 ChatModel
    chat_model = ChatModel.get_setup_instance(model="qwen3")
    chat_model_with_tool = chat_model.bind_tools([compressed_tool])

    # 调用模型
    messages = [HumanMessage(content="调用weather-query查询深圳市的天气")]
    response = chat_model_with_tool.invoke(messages)
    print(response)

    # 验证 args_schema 结构
    schema_fields = compressed_tool.args_schema.model_fields

    # 原有字段应该存在
    assert "city" in schema_fields
    assert "units" in schema_fields

    # invoke_intent 应该被添加
    assert "invoke_intent" in schema_fields
    # 验证字段描述保留
    assert "City name" in schema_fields["city"].description

    # 调用测试（使用原始 schema 的字段）
    result = compressed_tool.invoke(
        {
            "city": "Tokyo",
            "units": "fahrenheit",
            "invoke_intent": "International weather check",
        }
    )

    assert "[Compressed]" in result
    assert "Intent: International weather check" in result
