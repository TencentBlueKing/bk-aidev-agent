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

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from aidev_agent.config import settings
from aidev_agent.packages.langchain_core.tools.base import Tool, make_mcp_tools, make_structured_tool
from aidev_agent.packages.resource_manager.agent import AgentResourceManager
from aidev_agent.packages.resource_manager.registry import resource_manager
from aidev_agent.pydantic_models import ExecuteKwargs
from langchain_core.tools import StructuredTool
from langchain_core.tools.base import ToolException

# ================== make_structured_tool Mock 测试 ==================


@pytest.fixture
def sample_weather_tool_data():
    """天气查询工具的示例数据"""
    return {
        "tool_code": "weather-query",
        "tool_name": "天气查询",
        "description": "查询中国国内天气情况",
        "method": "get",
        "url": "https://api.example.com/prod/bkaidev/scene/tool_proxy/tool_proxy/weather-query/call/",
        "property": {
            "body": [
                {
                    "name": "",
                    "type": "string",
                    "default": "",
                    "required": False,
                    "validate": {"rules": [], "enable": False},
                    "description": "",
                }
            ],
            "query": [
                {
                    "name": "id",
                    "type": "string",
                    "default": "88888888",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "固定输入，无需更改",
                },
                {
                    "name": "key",
                    "type": "string",
                    "default": "88888888",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "固定输入，无需更改",
                },
                {
                    "name": "sheng",
                    "type": "string",
                    "default": "",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "省份名",
                },
                {
                    "name": "place",
                    "type": "string",
                    "default": "",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "市区名",
                },
            ],
            "header": [
                {
                    "name": "",
                    "type": "string",
                    "default": "",
                    "required": False,
                    "validate": {"rules": [], "enable": False},
                    "description": "",
                }
            ],
        },
    }


@pytest.fixture
def sample_post_tool_data():
    """POST 请求工具的示例数据"""
    return {
        "tool_code": "create-user",
        "tool_name": "创建用户",
        "description": "创建新用户",
        "method": "post",
        "url": "https://api.example.com/users",
        "property": {
            "body": [
                {
                    "name": "username",
                    "type": "string",
                    "default": "",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "用户名",
                },
                {
                    "name": "email",
                    "type": "string",
                    "default": "",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "邮箱",
                },
                {
                    "name": "age",
                    "type": "integer",
                    "default": 18,
                    "required": False,
                    "validate": {"rules": [], "enable": False},
                    "description": "年龄",
                },
            ],
            "header": [
                {
                    "name": "Content-Type",
                    "type": "string",
                    "default": "application/json",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "内容类型",
                }
            ],
            "query": [],
        },
    }


@pytest.fixture
def sample_path_param_tool_data():
    """包含路径参数的工具示例数据"""
    return {
        "tool_code": "get-user",
        "tool_name": "获取用户信息",
        "description": "根据用户ID获取用户信息",
        "method": "get",
        "url": "https://api.example.com/users/{user_id}",
        "property": {
            "path": [
                {
                    "name": "user_id",
                    "type": "string",
                    "default": "",
                    "required": True,
                    "validate": {"rules": [], "enable": False},
                    "description": "用户ID",
                }
            ],
            "query": [],
            "header": [],
        },
    }


def test_make_structured_tool_basic(sample_weather_tool_data):
    """测试基本的 make_structured_tool 功能"""
    tool = Tool.model_validate(sample_weather_tool_data)
    structured_tool = make_structured_tool(tool)

    # 验证返回的是 StructuredTool
    assert isinstance(structured_tool, StructuredTool)
    assert structured_tool.name == "weather-query"
    assert structured_tool.description == "查询中国国内天气情况"
    assert structured_tool.metadata == {"tool_id": None, "tool_code": "weather-query", "tool_name": "天气查询"}

    # 验证参数模型
    assert structured_tool.args_schema is not None
    fields = structured_tool.args_schema.model_fields
    assert "query__id" in fields
    assert "query__key" in fields
    assert "query__sheng" in fields
    assert "query__place" in fields


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_get_request_success(mock_session_class, sample_weather_tool_data):
    """测试 GET 请求成功的场景"""
    # Mock 响应
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success", "temperature": "25°C"}
    mock_response.headers.get.return_value = "application/json"
    mock_response.raise_for_status = Mock()

    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # 创建工具
    tool = Tool.model_validate(sample_weather_tool_data)
    structured_tool = make_structured_tool(tool)

    # 执行工具
    result = structured_tool.invoke({"query__sheng": "广东", "query__place": "深圳"})

    # 验证结果
    assert result == {"status": "success", "temperature": "25°C"}
    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    assert call_args[0][0] == "get"
    assert "sheng" in call_args[1]["params"]
    assert call_args[1]["params"]["sheng"] == "广东"
    assert call_args[1]["params"]["place"] == "深圳"


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_post_request_success(mock_session_class, sample_post_tool_data):
    """测试 POST 请求成功的场景"""
    # Mock 响应
    mock_response = Mock()
    mock_response.json.return_value = {"id": 123, "username": "testuser"}
    mock_response.headers.get.return_value = "application/json"
    mock_response.raise_for_status = Mock()

    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # 创建工具
    tool = Tool.model_validate(sample_post_tool_data)
    structured_tool = make_structured_tool(tool)

    # 执行工具
    result = structured_tool.invoke({"body__username": "testuser", "body__email": "test@example.com"})

    # 验证结果
    assert result == {"id": 123, "username": "testuser"}
    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    assert call_args[0][0] == "post"
    assert "json" in call_args[1]
    assert call_args[1]["json"]["username"] == "testuser"
    assert call_args[1]["json"]["email"] == "test@example.com"


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_http_error(mock_session_class, sample_weather_tool_data):
    """测试 HTTP 错误的场景：工具应抛出 ToolException 并携带错误信息"""
    import requests

    mock_response = Mock()
    mock_response.content.decode.return_value = "API error occurred"
    mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)

    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    tool = Tool.model_validate(sample_weather_tool_data)
    structured_tool = make_structured_tool(tool)

    with pytest.raises(ToolException) as exc_info:
        structured_tool.invoke({"query__sheng": "广东", "query__place": "深圳"})
    assert "[HTTPError]" in str(exc_info.value)
    assert "API error occurred" in str(exc_info.value)


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_timeout_error(mock_session_class, sample_weather_tool_data):
    """测试超时错误的场景：工具应抛出 ToolException 并携带错误信息"""
    mock_session = Mock()
    mock_session.request.side_effect = TimeoutError("Request timeout")
    mock_session_class.return_value = mock_session

    tool = Tool.model_validate(sample_weather_tool_data)
    structured_tool = make_structured_tool(tool)

    with pytest.raises(ToolException) as exc_info:
        structured_tool.invoke({"query__sheng": "广东", "query__place": "深圳"})
    assert "Request ERROR" in str(exc_info.value)
    assert "timeout" in str(exc_info.value).lower()


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_path_params(mock_session_class, sample_path_param_tool_data):
    """测试路径参数的处理"""
    # Mock 响应
    mock_response = Mock()
    mock_response.json.return_value = {"id": "123", "name": "John"}
    mock_response.headers.get.return_value = "application/json"
    mock_response.raise_for_status = Mock()

    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # 创建工具
    tool = Tool.model_validate(sample_path_param_tool_data)
    structured_tool = make_structured_tool(tool)

    # 执行工具
    result = structured_tool.invoke({"path__user_id": "123"})

    # 验证结果
    assert result == {"id": "123", "name": "John"}
    mock_session.request.assert_called_once()
    call_args = mock_session.request.call_args
    # 验证 URL 中的路径参数被正确替换
    assert "users/123" in call_args[0][1]


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_max_retry(mock_session_class, sample_weather_tool_data):
    """测试重复请求的限制"""
    # Mock 响应
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success"}
    mock_response.headers.get.return_value = "application/json"
    mock_response.raise_for_status = Mock()

    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # 创建工具
    tool = Tool.model_validate(sample_weather_tool_data)
    structured_tool = make_structured_tool(tool)

    # 相同的请求调用多次
    params = {"query__sheng": "广东", "query__place": "深圳"}
    structured_tool.invoke(params)
    structured_tool.invoke(params)
    result = structured_tool.invoke(params)

    # 第三次应该返回提示信息
    assert "Same request call too much" in result


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_non_json_response(mock_session_class, sample_weather_tool_data):
    """测试非 JSON 响应"""
    # Mock 文本响应
    mock_response = Mock()
    mock_response.text = "Plain text response"
    mock_response.headers.get.return_value = "text/plain"
    mock_response.raise_for_status = Mock()

    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # 创建工具
    tool = Tool.model_validate(sample_weather_tool_data)
    structured_tool = make_structured_tool(tool)

    # 执行工具
    result = structured_tool.invoke({"query__sheng": "广东", "query__place": "深圳"})

    # 验证返回文本
    assert result == "Plain text response"


@patch("aidev_agent.packages.langchain_core.tools.base.requests.Session")
def test_make_structured_tool_with_extra(mock_session_class, sample_weather_tool_data):
    """测试带有 extra 参数的工具"""
    # Mock 响应
    mock_response = Mock()
    mock_response.json.return_value = {"status": "success"}
    mock_response.headers.get.return_value = "application/json"
    mock_response.raise_for_status = Mock()

    mock_session = Mock()
    mock_session.request.return_value = mock_response
    mock_session_class.return_value = mock_session

    # 创建带 extra 的工具
    tool_data = sample_weather_tool_data.copy()
    tool = Tool.model_validate(tool_data)
    tool.extra = {"header": {"Authorization": "Bearer token123"}, "query": {"extra_param": "value"}}

    structured_tool = make_structured_tool(tool)

    # 执行工具
    structured_tool.invoke({"query__sheng": "广东", "query__place": "深圳"})

    # 验证 extra 参数被正确传递
    call_args = mock_session.request.call_args
    assert "Authorization" in call_args[1]["headers"]
    assert call_args[1]["headers"]["Authorization"] == "Bearer token123"
    assert "extra_param" in call_args[1]["params"]
    assert call_args[1]["params"]["extra_param"] == "value"


# ================== make_structured_tool 真实测试 ==================


@pytest.mark.skipif(
    not all([settings.LLM_GW_ENDPOINT, settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
def test_make_structured_tool_real_execution():
    """测试真实的工具执行 - 使用 weather-query 工具"""
    # 获取真实的工具配置
    rm = resource_manager()
    tool_code = "weather-query"

    # 使用 ResourceManager 的 construct_tool 方法构造工具
    structured_tool = rm.construct_tool(tool_code)

    # 验证工具创建成功
    assert isinstance(structured_tool, StructuredTool)
    assert structured_tool.name == tool_code
    print(f"\n工具名称: {structured_tool.name}")
    print(f"工具描述: {structured_tool.description}")
    print(f"工具元数据: {structured_tool.metadata}")

    # 执行真实的工具调用
    result = structured_tool.invoke({"query__sheng": "广东", "query__place": "深圳"})

    # 打印结果
    print(f"\n真实执行结果: {result}")

    # 基本验证
    assert result is not None


# ================== make_mcp_tools Mock 测试 ==================


@pytest.fixture
def sample_mcp_config():
    """MCP 配置示例"""
    return {"tencentcloud-doc-mcp": {"url": "http://portal-mcp-server.example.com/mcp", "transport": "streamable_http"}}


@pytest.fixture
def sample_mcp_config_with_auth():
    """带认证的 MCP 配置示例"""
    return {
        "authenticated-mcp": {
            "url": "http://secure-mcp-server.example.com/mcp",
            "transport": "streamable_http",
            "credential_type": "blueapps",
        }
    }


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_basic(mock_mcp_client_class, sample_mcp_config):
    """测试基本的 make_mcp_tools 功能"""
    # Mock 工具列表
    mock_tool = MagicMock(spec=StructuredTool)
    mock_tool.name = "test-mcp-tool"
    mock_tool.description = "Test MCP tool"
    mock_tool.coroutine = AsyncMock()
    mock_tool.metadata = {"mcp_name": "tencentcloud-doc-mcp"}  # 添加 mcp_name 到 metadata

    # Mock MCP 客户端
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_mcp_client_class.return_value = mock_client

    result = make_mcp_tools(sample_mcp_config)

    assert len(result.tools) == 1
    assert result.tools[0].name == "test-mcp-tool"
    assert result.tools[0].metadata["mcp_name"] == "tencentcloud-doc-mcp"
    assert result.tools[0].metadata["mcp_transport"] == "streamable_http"
    assert result.fetch_failures == []
    mock_mcp_client_class.assert_called_once()


@patch("aidev_agent.packages.resource_manager.base.recording_span")
@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_records_list_semantics(mock_mcp_client_class, mock_recording_span, sample_mcp_config):
    from aidev_agent.utils.tracing import CLIENT_SPAN_KIND

    mock_tool = MagicMock(spec=StructuredTool)
    mock_tool.name = "test-mcp-tool"
    mock_tool.coroutine = AsyncMock()
    mock_tool.metadata = {}
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_mcp_client_class.return_value = mock_client
    span = mock_recording_span.return_value.__enter__.return_value

    make_mcp_tools(sample_mcp_config)

    mock_recording_span.assert_called_once_with(
        "mcp.tools.list",
        kind=CLIENT_SPAN_KIND,
        use_global_tracer=True,
        attributes={
            "rpc.system": "mcp",
            "mcp.operation.name": "tools/list",
            "mcp.server.name": "tencentcloud-doc-mcp",
            "mcp.transport": "streamable_http",
            "mcp.retry.count": 0,
        },
    )
    span.set_attribute.assert_called_once_with("mcp.tool.count", 1)


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_with_blueapps_auth(mock_mcp_client_class, sample_mcp_config_with_auth):
    """测试带 blueapps 认证的 MCP 工具"""
    # Mock 工具
    mock_tool = MagicMock(spec=StructuredTool)
    mock_tool.name = "auth-tool"
    mock_tool.coroutine = AsyncMock()
    mock_tool.metadata = {}  # 添加 metadata 属性

    # Mock MCP 客户端
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_mcp_client_class.return_value = mock_client

    result = make_mcp_tools(sample_mcp_config_with_auth)

    # 验证认证信息被添加到配置中
    # MultiServerMCPClient 在异步函数内部被调用，需要检查 mock 的调用参数
    call_args = mock_mcp_client_class.call_args
    assert call_args is not None, "MultiServerMCPClient 应该被调用"
    config_arg = call_args[0][0]  # 第一个位置参数是 server_config
    assert "authenticated-mcp" in config_arg
    assert "headers" in config_arg["authenticated-mcp"]
    assert "X-Bkapi-Authorization" in config_arg["authenticated-mcp"]["headers"]

    # 验证工具被包装
    assert len(result.tools) == 1


@patch(
    "aidev_agent.packages.resource_manager.base.trace_headers",
    return_value={"traceparent": "00-992eea94222b572e883ab78b23e73d64-99e019654b49749a-01"},
)
@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_propagates_trace_context_to_all_remote_servers(mock_mcp_client_class, _mock_trace_headers):
    config = {
        "apigw": {
            "url": "https://example.com/apigw/mcp",
            "transport": "streamable_http",
            "credential_type": "blueapps",
        },
        "external": {"url": "https://example.net/mcp", "transport": "sse", "headers": {"X-Custom": "kept"}},
        "local": {"transport": "stdio", "command": "python", "args": ["server.py"]},
    }
    mock_mcp_client_class.return_value.get_tools = AsyncMock(return_value=[])

    make_mcp_tools(config)

    client_config = mock_mcp_client_class.call_args_list[0].args[0]
    assert client_config["apigw"]["headers"]["traceparent"].split("-")[1] == "992eea94222b572e883ab78b23e73d64"
    assert client_config["external"]["headers"]["traceparent"].split("-")[1] == "992eea94222b572e883ab78b23e73d64"
    assert client_config["external"]["headers"]["X-Custom"] == "kept"
    assert "headers" not in client_config["local"]
    assert callable(mock_mcp_client_class.call_args_list[0].kwargs["tool_interceptors"][0])


@pytest.mark.asyncio
@patch(
    "aidev_agent.packages.resource_manager.base.trace_headers",
    return_value={"traceparent": "00-992eea94222b572e883ab78b23e73d64-99e019654b49749a-01"},
)
async def test_mcp_tool_call_refreshes_trace_context(_mock_trace_headers):
    from aidev_agent.packages.resource_manager.base import _mcp_trace_context_interceptor

    request = MagicMock()
    request.headers = {"X-Custom": "kept"}
    updated_request = request.override.return_value
    handler = AsyncMock(return_value="ok")

    result = await _mcp_trace_context_interceptor(request, handler)

    assert result == "ok"
    request.override.assert_called_once_with(
        headers={
            "X-Custom": "kept",
            "traceparent": "00-992eea94222b572e883ab78b23e73d64-99e019654b49749a-01",
        }
    )
    handler.assert_awaited_once_with(updated_request)


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_error_handling(mock_mcp_client_class, sample_mcp_config, caplog):
    """测试 MCP 工具获取失败时跳过并记录 warning"""
    # Mock 客户端抛出异常
    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(side_effect=Exception("Connection failed"))
    mock_mcp_client_class.return_value = mock_client

    result = make_mcp_tools(sample_mcp_config)

    assert result.tools == []
    assert len(result.fetch_failures) == 1
    assert result.fetch_failures[0].server_name == "tencentcloud-doc-mcp"
    assert "获取MCP工具列表失败" in result.fetch_failures[0].message
    assert "tencentcloud-doc-mcp" in caplog.text
    assert [record.levelname for record in caplog.records if record.levelname == "WARNING"] == ["WARNING"]


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_multiple_servers(mock_mcp_client_class, caplog):
    """测试多个 MCP 服务器中单个失败不会影响其他服务"""
    multi_server_config = {
        "server1": {"url": "http://server1.com/mcp", "transport": "streamable_http"},
        "server2": {"url": "http://server2.com/mcp", "transport": "streamable_http"},
    }

    # Mock 工具
    mock_tool1 = MagicMock(spec=StructuredTool)
    mock_tool1.name = "tool1"
    mock_tool1.coroutine = AsyncMock()
    mock_tool1.metadata = {}  # 添加 metadata 属性

    mock_tool2 = MagicMock(spec=StructuredTool)
    mock_tool2.name = "tool2"
    mock_tool2.coroutine = AsyncMock()
    mock_tool2.metadata = {}  # 添加 metadata 属性

    # Mock 客户端 - server1 返回工具，server2 抛出异常
    mock_client = MagicMock()

    async def mock_get_tools(*, server_name):
        if server_name == "server1":
            return [mock_tool1, mock_tool2]
        raise Exception("Connection failed")

    mock_client.get_tools = AsyncMock(side_effect=mock_get_tools)
    mock_mcp_client_class.return_value = mock_client

    result = make_mcp_tools(multi_server_config)

    assert len(result.tools) == 2
    assert {t.name for t in result.tools} == {"tool1", "tool2"}
    assert len(result.fetch_failures) == 1
    assert result.fetch_failures[0].server_name == "server2"
    assert "server2" in caplog.text
    # 成功拉取 server1 会打 INFO；失败 server2 打 WARNING
    assert [r.levelname for r in caplog.records if r.levelname == "WARNING"] == ["WARNING"]
    assert any(r.levelname == "INFO" and "server1" in r.getMessage() for r in caplog.records)


# ================== wrap_mcp_exception 测试 ==================
@pytest.mark.asyncio
async def test_mcp_exception_wrapper_success():
    """测试 wrap_mcp_exception 正常执行"""
    from aidev_agent.packages.langchain_core.tools.base import wrap_mcp_exception

    async def mock_coro(*args, **kwargs):
        return "success result"

    wrapper = wrap_mcp_exception(mock_coro)
    result = await wrapper()

    assert result == "success result"


@pytest.mark.asyncio
async def test_mcp_exception_wrapper_tool_exception():
    """测试 wrap_mcp_exception 处理 ToolException"""
    from aidev_agent.packages.langchain_core.tools.base import wrap_mcp_exception
    from langchain_core.tools.base import ToolException

    async def mock_coro(*args, **kwargs):
        raise ToolException("Tool error occurred")

    wrapper = wrap_mcp_exception(mock_coro)

    with pytest.raises(ToolException) as exc_info:
        await wrapper()

    assert "[ERROR]" in str(exc_info.value)
    assert "MCP工具调用失败" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_exception_wrapper_connection_error():
    """测试 wrap_mcp_exception 处理连接错误"""
    from aidev_agent.packages.langchain_core.tools.base import wrap_mcp_exception
    from langchain_core.tools.base import ToolException

    async def mock_coro(*args, **kwargs):
        raise ConnectionError("Connection refused")

    wrapper = wrap_mcp_exception(mock_coro)

    with pytest.raises(ToolException) as exc_info:
        await wrapper()

    assert "[ERROR]" in str(exc_info.value)
    assert "连接异常" in str(exc_info.value)


@pytest.mark.asyncio
async def test_mcp_exception_wrapper_timeout_error():
    """测试 wrap_mcp_exception 处理超时错误"""
    from aidev_agent.packages.langchain_core.tools.base import wrap_mcp_exception
    from langchain_core.tools.base import ToolException

    async def mock_coro(*args, **kwargs):
        raise TimeoutError("Request timeout")

    wrapper = wrap_mcp_exception(mock_coro)

    with pytest.raises(ToolException) as exc_info:
        await wrapper()

    assert "[ERROR]" in str(exc_info.value)
    assert "超时异常" in str(exc_info.value)


def test_make_structured_tool_with_inject_config_and_state():
    """测试 make_structured_tool 支持注入 context (config 和 state)"""

    import inspect

    # 创建一个测试工具
    tool = Tool(
        tool_code="test_tool",
        tool_name="测试工具",
        description="用于测试 context 注入的工具",
        method="POST",
        url="https://example.com/api/test",
        property={
            "header": [
                {
                    "name": "X-User-Id",
                    "type": "string",
                    "required": False,
                    "default": "{{ state.user_id }}",
                    "description": "用户ID (从 state 注入)",
                    "validate": {"enable": False, "rules": []},
                },
                {
                    "name": "X-Thread-Id",
                    "type": "string",
                    "required": False,
                    "default": "{{ config.configurable.thread_id }}",
                    "description": "线程ID (从 config 注入)",
                    "validate": {"enable": False, "rules": []},
                },
            ],
            "body": [
                {
                    "name": "message",
                    "type": "string",
                    "required": True,
                    "default": None,
                    "description": "消息内容",
                    "validate": {"enable": False, "rules": []},
                },
                {
                    "name": "tenant",
                    "type": "string",
                    "required": False,
                    "default": "{{ state.tenant }}",
                    "description": "租户 (从 state 注入)",
                    "validate": {"enable": False, "rules": []},
                },
            ],
        },
        extra=None,
    )

    # 构建工具 - 启用 context 注入
    structured_tool = make_structured_tool(
        tool=tool,
        inject_context=True,
    )

    # 验证工具的基本属性
    assert structured_tool.name == "test_tool"
    assert structured_tool.description == "用于测试 context 注入的工具"

    # 验证函数签名包含 state 和 config
    sig = inspect.signature(structured_tool.func)
    assert "state" in sig.parameters, "函数签名应该包含 state 参数"
    assert "config" in sig.parameters, "函数签名应该包含 config 参数"

    # 验证 args_schema 包含正常的业务字段
    schema_fields = structured_tool.args_schema.model_fields
    assert "body__message" in schema_fields
    assert "header__X-User-Id" in schema_fields

    print(f"✓ 工具创建成功，函数签名: {sig}")
    print(f"✓ args_schema 字段: {list(schema_fields.keys())}")


def test_make_structured_tool_inject_context():
    """测试 make_structured_tool 注入 context"""

    import inspect

    tool = Tool(
        tool_code="test_tool_state_only",
        tool_name="Context 注入工具",
        description="测试注入 context",
        method="GET",
        url="https://example.com/api/data",
        property={
            "query": [
                {
                    "name": "user_id",
                    "type": "string",
                    "required": False,
                    "default": "{{ state.user_id }}",
                    "description": "用户ID",
                    "validate": {"enable": False, "rules": []},
                }
            ]
        },
        extra=None,
    )

    structured_tool = make_structured_tool(
        tool=tool,
        inject_context=True,
    )

    sig = inspect.signature(structured_tool.func)
    assert "state" in sig.parameters, "函数签名应该包含 state 参数"
    assert "config" in sig.parameters, "函数签名应该包含 config 参数"

    schema_fields = structured_tool.args_schema.model_fields
    assert "query__user_id" in schema_fields

    print(f"✓ Context 注入成功，函数签名: {sig}")


def test_make_structured_tool_no_injection():
    """测试 make_structured_tool 不注入 (向后兼容)"""

    tool = Tool(
        tool_code="test_tool_no_injection",
        tool_name="无注入工具",
        description="测试不注入",
        method="GET",
        url="https://example.com/api/legacy",
        property={
            "query": [
                {
                    "name": "param1",
                    "type": "string",
                    "required": True,
                    "default": None,
                    "description": "参数1",
                    "validate": {"enable": False, "rules": []},
                }
            ]
        },
        extra=None,
    )

    structured_tool = make_structured_tool(
        tool=tool,
        inject_context=False,
    )

    schema_fields = structured_tool.args_schema.model_fields
    assert "state" not in schema_fields, "不应该包含 state 字段"
    assert "config" not in schema_fields, "不应该包含 config 字段"
    assert "query__param1" in schema_fields

    print(f"✓ 无注入测试成功 (向后兼容)，schema 字段: {list(schema_fields.keys())}")


@pytest.mark.asyncio
async def test_tool_invocation_with_state_and_config():
    """测试工具调用时 state 和 config 的渲染"""

    # Mock HTTP 请求
    with patch("requests.Session.request") as mock_request:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"status": "success"}
        mock_request.return_value = mock_response

        tool = Tool(
            tool_code="test_render_tool",
            tool_name="渲染测试工具",
            description="测试变量渲染",
            method="POST",
            url="https://example.com/api/test",
            property={
                "header": [
                    {
                        "name": "X-User-Id",
                        "type": "string",
                        "required": False,
                        "default": "{{ state.user_id }}",
                        "description": "用户ID",
                        "validate": {"enable": False, "rules": []},
                    },
                    {
                        "name": "X-Thread-Id",
                        "type": "string",
                        "required": False,
                        "default": "{{ config.configurable.thread_id }}",
                        "description": "线程ID",
                        "validate": {"enable": False, "rules": []},
                    },
                ],
                "body": [
                    {
                        "name": "tenant",
                        "type": "string",
                        "required": False,
                        "default": "{{ state.tenant }}",
                        "description": "租户",
                        "validate": {"enable": False, "rules": []},
                    },
                    {
                        "name": "username",
                        "type": "string",
                        "required": False,
                        "default": "{{ bk_username }}",
                        "description": "租户",
                        "validate": {"enable": False, "rules": []},
                    },
                ],
            },
            extra=None,
        )

        structured_tool = make_structured_tool(
            tool=tool,
            inject_context=True,
        )

        # 模拟调用 - 注意:config 通过 RunnableConfig 参数传递,不是通过 input
        from langchain_core.runnables import RunnableConfig

        a = ExecuteKwargs()
        a.executor = "bk_username-X"
        structured_tool.invoke(
            {"state": {"user_id": "user_123", "tenant": "tenant_abc"}},
            config=RunnableConfig(configurable={"thread_id": "thread_456", "execute_kwargs": a}),
        )

        # 验证请求被正确调用
        assert mock_request.called
        call_kwargs = mock_request.call_args.kwargs

        # 验证 headers 和 body 中的模板被正确渲染
        print("✓ 工具调用成功")
        print(f"  - Headers: {call_kwargs.get('headers')}")
        print(f"  - Body: {call_kwargs.get('json')}")

        # 验证渲染结果
        headers = call_kwargs.get("headers", {})
        body = call_kwargs.get("json", {})

        assert headers.get("X-User-Id") == "user_123", "X-User-Id 应该从 state.user_id 渲染"
        assert headers.get("X-Thread-Id") == "thread_456", "X-Thread-Id 应该从 config 渲染"
        assert body.get("tenant") == "tenant_abc", "tenant 应该从 state.tenant 渲染"
        assert body.get("username") == "bk_username-X", "tenant 应该从 config 渲染"


@pytest.mark.asyncio
async def test_tool_with_langgraph_integration():
    """测试与 LangGraph 的集成 (使用 InjectedState)"""

    try:
        import inspect
        from typing import TypedDict

        from langchain_core.messages import AIMessage
        from langgraph.graph import END, START, StateGraph
        from langgraph.prebuilt import ToolNode
    except ImportError:
        pytest.skip("langgraph not installed")

    # Mock HTTP 请求
    with patch("requests.Session.request") as mock_request:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"result": "mocked"}
        mock_request.return_value = mock_response

        tool = Tool(
            tool_code="langgraph_test_tool",
            tool_name="LangGraph 集成工具",
            description="测试 LangGraph 集成",
            method="POST",
            url="https://example.com/api/langgraph",
            property={
                "header": [
                    {
                        "name": "X-User",
                        "type": "string",
                        "required": False,
                        "default": "{{ state.user }}",
                        "description": "用户",
                        "validate": {"enable": False, "rules": []},
                    }
                ],
                "body": [
                    {
                        "name": "session_id",
                        "type": "string",
                        "required": False,
                        "default": "{{ state.session_id }}",
                        "description": "会话ID",
                        "validate": {"enable": False, "rules": []},
                    }
                ],
            },
            extra=None,
        )

        structured_tool = make_structured_tool(
            tool=tool,
            inject_context=True,
        )

        # DEBUG: 检查工具函数签名
        print(f"Tool function: {structured_tool.func}")
        print(f"Function signature: {inspect.signature(structured_tool.func)}")
        print(f"Function annotations: {structured_tool.func.__annotations__}")

        # 构建 LangGraph
        class AgentState(TypedDict):
            messages: list
            user: str
            session_id: str

        workflow = StateGraph(AgentState)
        tool_node = ToolNode([structured_tool])
        workflow.add_node("tools", tool_node)
        workflow.add_edge(START, "tools")
        workflow.add_edge("tools", END)
        graph = workflow.compile()

        # 构造输入
        ai_message = AIMessage(
            content="", tool_calls=[{"name": "langgraph_test_tool", "args": {}, "id": "call_001", "type": "tool_call"}]
        )

        # 执行 Graph
        state = {"messages": [ai_message], "user": "alice", "session_id": "session_789"}

        await graph.ainvoke(state, config={"configurable": {"thread_id": "thread_123"}})

        # 验证工具被调用
        assert mock_request.called
        call_kwargs = mock_request.call_args.kwargs

        headers = call_kwargs.get("headers", {})
        body = call_kwargs.get("json", {})

        print("✓ LangGraph 集成测试成功")
        print(f"  - Headers: {headers}")
        print(f"  - Body: {body}")

        # 验证 state 被正确注入和渲染
        assert headers.get("X-User") == "alice", "X-User 应该从 state.user 渲染"
        assert body.get("session_id") == "session_789", "session_id 应该从 state.session_id 渲染"


# ================== make_mcp_tools 核心逻辑补充测试 ==================


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_selected_tools_filter(mock_mcp_client_class):
    """测试 selected_tools 过滤：只保留配置中指定的工具"""
    config = {
        "server1": {
            "url": "http://server1.com/mcp",
            "transport": "streamable_http",
            "selected_tools": ["tool_a", "tool_c"],
        },
    }

    # Mock 3 个工具，只有 tool_a 和 tool_c 应该被保留
    tools = []
    for name in ["tool_a", "tool_b", "tool_c"]:
        t = MagicMock(spec=StructuredTool)
        t.name = name
        t.coroutine = AsyncMock()
        t.metadata = {}
        tools.append(t)

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=tools)
    mock_mcp_client_class.return_value = mock_client

    result = make_mcp_tools(config)

    assert len(result.tools) == 2
    assert {t.name for t in result.tools} == {"tool_a", "tool_c"}


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_selected_tools_not_passed_to_client(mock_mcp_client_class):
    """测试 selected_tools 和 mcp_type 字段在传给 MultiServerMCPClient 前被清除"""
    config = {
        "server1": {
            "url": "http://server1.com/mcp",
            "transport": "streamable_http",
            "selected_tools": ["tool_a"],
            "mcp_type": "resource",
        },
    }

    mock_tool = MagicMock(spec=StructuredTool)
    mock_tool.name = "tool_a"
    mock_tool.coroutine = AsyncMock()
    mock_tool.metadata = {}

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_mcp_client_class.return_value = mock_client

    make_mcp_tools(config)

    # 验证传给 MultiServerMCPClient 的配置中不包含 selected_tools 和 mcp_type
    call_args = mock_mcp_client_class.call_args[0][0]
    server_cfg = call_args["server1"]
    assert "selected_tools" not in server_cfg
    assert "mcp_type" not in server_cfg


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_retry_on_first_failure(mock_mcp_client_class):
    """测试第一次失败后重试第二次成功"""
    config = {
        "server1": {"url": "http://server1.com/mcp", "transport": "streamable_http"},
    }

    mock_tool = MagicMock(spec=StructuredTool)
    mock_tool.name = "tool1"
    mock_tool.coroutine = AsyncMock()
    mock_tool.metadata = {}

    # 第一个 client 实例 get_tools 抛异常，第二个成功
    mock_client_fail = MagicMock()
    mock_client_fail.get_tools = AsyncMock(side_effect=Exception("transient error"))
    mock_client_ok = MagicMock()
    mock_client_ok.get_tools = AsyncMock(return_value=[mock_tool])
    mock_mcp_client_class.side_effect = [mock_client_fail, mock_client_ok]

    result = make_mcp_tools(config)

    # 重试后应该成功，无失败记录
    assert len(result.tools) == 1
    assert result.tools[0].name == "tool1"
    assert result.fetch_failures == []
    # MultiServerMCPClient 应该被调用了 2 次（重试）
    assert mock_mcp_client_class.call_count == 2


@patch("aidev_agent.packages.resource_manager.base.MultiServerMCPClient")
def test_make_mcp_tools_does_not_mutate_original_config(mock_mcp_client_class):
    """测试不会修改原始传入的 server_config"""
    config = {
        "server1": {
            "url": "http://server1.com/mcp",
            "transport": "streamable_http",
            "selected_tools": ["tool_a"],
            "mcp_type": "resource",
            "credential_type": "blueapps",
        },
    }
    import copy

    original_config = copy.deepcopy(config)

    mock_tool = MagicMock(spec=StructuredTool)
    mock_tool.name = "tool_a"
    mock_tool.coroutine = AsyncMock()
    mock_tool.metadata = {}

    mock_client = MagicMock()
    mock_client.get_tools = AsyncMock(return_value=[mock_tool])
    mock_mcp_client_class.return_value = mock_client

    make_mcp_tools(config)

    # 原始配置不应被修改
    assert config == original_config


# ================== construct_tool 的 X-Bkapi-Authorization 头部拼装 ==================


def _rm_with_mocked_client(tool_data: dict, credential_type: str = "blueapps") -> AgentResourceManager:
    """构造一个 client 已被 mock 的 AgentResourceManager，避免真实网络调用。"""
    rm = AgentResourceManager(app_code="dummy_app", app_secret="dummy_credential")
    data = {**tool_data, "credential_type": credential_type}
    mock_client = MagicMock()
    mock_client.api.retrieve_tool = MagicMock(return_value={"data": data})
    mock_client.api.appspace_retrieve_tool = MagicMock(return_value={"data": data})
    rm.get_client = MagicMock(return_value=mock_client)  # type: ignore[method-assign]
    # 默认令 resolve_access_token 返回空串，避免依赖 bkoauth；具体用例可再单独 patch
    rm.resolve_access_token = MagicMock(return_value="")  # type: ignore[method-assign]
    return rm


def _extract_auth_header(tool) -> str | None:
    """从 StructuredTool 里取出 X-Bkapi-Authorization 头（未注入时返回 None）。

    ``make_structured_tool`` 在 ``inject_context=True``（默认）时会把 ``ApiWrapper``
    包在闭包 ``tool_func`` 里；关闭时 ``func`` 直接就是 ``ApiWrapper`` 实例。
    这里兼容两种情况，先直接取 ``_extra``，取不到再从闭包里翻出来。
    """
    func = tool.func
    api_wrapper = func if hasattr(func, "_extra") else None
    if api_wrapper is None and getattr(func, "__closure__", None):
        for cell in func.__closure__:
            if hasattr(cell.cell_contents, "_extra"):
                api_wrapper = cell.cell_contents
                break
    if api_wrapper is None:
        return None
    header = api_wrapper._extra.header or {}
    return header.get("X-Bkapi-Authorization")


def test_construct_tool_skips_header_when_credential_type_is_null(sample_weather_tool_data):
    """credential_type=null 的工具不注入 X-Bkapi-Authorization。"""
    rm = _rm_with_mocked_client(sample_weather_tool_data, credential_type="null")

    tool = rm.construct_tool("weather-query")

    assert _extract_auth_header(tool) is None


@pytest.mark.parametrize(
    "self_username, kwargs, expected_auth",
    [
        # 无 username / self.username / executor_info → 纯应用凭据，不含 bk_username
        pytest.param(
            "",
            {},
            {"bk_app_code": "dummy_app", "bk_app_secret": "dummy_credential"},
            id="without_user_context",
        ),
        # 仅显式 username → 应用凭据 + bk_username
        pytest.param(
            "",
            {"username": "alice"},
            {"bk_app_code": "dummy_app", "bk_app_secret": "dummy_credential", "bk_username": "alice"},
            id="with_username",
        ),
        # 仅 self.username（未显式传参）→ 回退到 self.username 拼装 bk_username
        pytest.param(
            "bob",
            {},
            {"bk_app_code": "dummy_app", "bk_app_secret": "dummy_credential", "bk_username": "bob"},
            id="fallback_to_self_username",
        ),
        # 显式 username 覆盖 self.username → 使用显式值
        pytest.param(
            "bob",
            {"username": "alice"},
            {"bk_app_code": "dummy_app", "bk_app_secret": "dummy_credential", "bk_username": "alice"},
            id="explicit_username_overrides_self_username",
        ),
        # executor_info 提供 access_token → 仅 access_token，忽略其他字段
        pytest.param(
            "",
            {"username": "alice", "executor_info": {"access_token": "dummy_exec_value"}},
            {"access_token": "dummy_exec_value"},
            id="with_access_token",
        ),
    ],
)
def test_construct_tool_injects_expected_authorization_header(
    sample_weather_tool_data, self_username, kwargs, expected_auth
):
    """按输入拼装 X-Bkapi-Authorization：应用凭据 / 用户凭据 / access_token 优先。

    覆盖场景：
    - 纯应用态（无任何 username 来源）不含 bk_username 字段；
    - 仅显式 username / 仅 self.username 回退 / 显式 username 覆盖 self.username；
    - executor_info.access_token 优先，其他字段被忽略。
    """
    rm = _rm_with_mocked_client(sample_weather_tool_data)
    rm.username = self_username

    tool = rm.construct_tool("weather-query", **kwargs)

    auth_header = _extract_auth_header(tool)
    assert auth_header is not None
    assert json.loads(auth_header) == expected_auth
