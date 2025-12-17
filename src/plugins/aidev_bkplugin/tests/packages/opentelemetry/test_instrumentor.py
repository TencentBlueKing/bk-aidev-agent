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
import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any

from pydantic import BaseModel, Field

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from aidev_agent.core.utils.local import request_local
from aidev_bkplugin.packages.opentelemetry.instrumentor import (
    LiteEnhancedAgentExecutorWrapper,
    LiteEnhancedAgentExecutorStreamEventsWrapper,
    LiteEnhancedAgentExecutorAInvokeWrapper,
)
from aidev_bkplugin.packages.opentelemetry.config import OTelConfig


# Mock ExecuteKwargs with the new definition
class ExecuteKwargs(BaseModel):
    """
    Mock ExecuteKwargs with the new fields from
    /data/workspace/bk-aidev-agent/src/agent/aidev_agent/services/pydantic_models.py
    """
    stream: bool = False
    stream_timeout: int = 30
    passthrough_input: bool = False
    run_agent: bool = False
    # 新增参数
    session_code: str | None = Field(default=None, description="调用时的会话 ID")
    caller_bk_app_code: str | None = Field(default=None, description="调用者BK应用ID")
    caller_bk_biz_env: str | None = Field(default=None, description="调用者BK业务环境")
    caller_bk_biz_id: int | None = Field(default=None, description="调用者BK业务ID")
    caller_executor: str | None = Field(default=None, description="调用人")
    caller_order_type: str | None = Field(default=None, description="调用AI工单类型")
    caller_trace_context: Dict[str, Any] | None = Field(default=None, description="调用链ID")


@pytest.fixture(scope="function", autouse=False)
def tracer_and_config():
    """
    创建 tracer 和配置用于测试

    注意: 此 fixture 为每个测试创建独立的 TracerProvider 实例，
    不设置全局 TracerProvider，以确保测试之间的隔离性。
    """
    # 创建内存导出器
    exporter = InMemorySpanExporter()

    # 创建 TracerProvider
    provider = TracerProvider()
    span_processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(span_processor)

    # 直接从 provider 获取 tracer，不设置全局 TracerProvider
    tracer = provider.get_tracer(__name__)

    # 创建配置
    config = OTelConfig()

    # 清空当前的 spans（以防之前的测试留下数据）
    exporter.clear()

    # Patch ExecuteKwargs in instrumentor module to use our mocked version
    with patch('aidev_bkplugin.packages.opentelemetry.instrumentor.ExecuteKwargs', ExecuteKwargs):
        yield tracer, config, exporter

    # 强制刷新所有 spans
    try:
        span_processor.force_flush()
    except Exception:
        pass

    # 清理
    exporter.clear()


def verify_get_values_result(result):
    """
    公共验证函数：验证 get_values 返回值的结构和内容

    Args:
        result: get_values 方法的返回值
    """
    # 验证返回值包含所有必需的键
    assert "inputs" in result
    assert "execute_kwargs" in result
    assert "agent_info" in result
    assert "parent_trace_context" in result

    # 验证 inputs (user_input) 不能为空
    assert result["inputs"] is not None
    assert result["inputs"] != ""

    # 验证 execute_kwargs 是 ExecuteKwargs 对象
    assert isinstance(result["execute_kwargs"], ExecuteKwargs)
    execute_kwargs = result["execute_kwargs"]

    # 验证 execute_kwargs 包含所有必需的字段
    assert hasattr(execute_kwargs, "session_code")
    assert hasattr(execute_kwargs, "caller_executor")
    assert hasattr(execute_kwargs, "caller_bk_app_code")
    assert hasattr(execute_kwargs, "caller_bk_biz_env")
    assert hasattr(execute_kwargs, "caller_bk_biz_id")
    assert hasattr(execute_kwargs, "caller_order_type")

    # 验证 agent_info 是一个字典
    assert isinstance(result["agent_info"], dict)
    agent_info = result["agent_info"]

    # 验证 agent_info 不能有 otel_info 字段
    assert "otel_info" not in agent_info

    # 验证 agent_info 包含必需的字段
    assert "agent_id" in agent_info
    assert "agent_code" in agent_info
    assert "agent_name" in agent_info
    assert "agent_type" in agent_info
    assert "service_catalogue" in agent_info
    assert "updated_by" in agent_info


class TestLiteEnhancedAgentExecutorWrapper:
    """测试 LiteEnhancedAgentExecutorWrapper 基类"""

    @patch("aidev_bkplugin.packages.opentelemetry.instrumentor.get_agent_config_info")
    def test_get_values_with_request_local(self, mock_get_agent_config_info, tracer_and_config):
        """测试 get_values 从 request_local 获取 otel_info"""
        tracer, config, _ = tracer_and_config

        # 模拟 get_agent_config_info 返回值
        mock_agent_info = {
            "agent_id": "test-agent-123",
            "agent_code": "test_agent",
            "agent_name": "测试智能体",
            "agent_type": "ai_chat",
            "service_catalogue": "test_service",
            "updated_by": "admin",
            "otel_info": {"should_be_removed": True},  # 这个字段应该被移除
        }
        mock_get_agent_config_info.return_value = mock_agent_info

        # 设置 request_local.otel_info
        request_local.otel_info = {
            "session_code": "session-123",
            "executor": "test-user",
            "caller_bk_app_code": "test-app",
            "caller_bk_biz_env": "domestic_biz",
            "caller_executor": "test-user",
            "caller_bk_biz_id": 100,
            "caller_order_type": "ai_chat",
        }

        # 创建包装器
        wrapper = LiteEnhancedAgentExecutorWrapper(tracer, config)

        # 模拟 agent 对象
        mock_agent = MagicMock()

        # 准备输入
        input_data = {"input": "测试问题"}

        # 调用 get_values
        result = wrapper.get_values(mock_agent, input=input_data)

        # 使用公共验证函数
        verify_get_values_result(result)

        # 验证具体的值
        assert result["inputs"] == "测试问题"
        assert result["execute_kwargs"].session_code == "session-123"
        assert result["execute_kwargs"].caller_executor == "test-user"
        assert result["execute_kwargs"].caller_bk_app_code == "test-app"
        assert result["execute_kwargs"].caller_bk_biz_env == "domestic_biz"
        assert result["execute_kwargs"].caller_bk_biz_id == 100
        assert result["execute_kwargs"].caller_order_type == "ai_chat"

        # 清理
        delattr(request_local, "otel_info")

    @patch("aidev_bkplugin.packages.opentelemetry.instrumentor.get_agent_config_info")
    def test_get_values_with_input_execute_kwargs(self, mock_get_agent_config_info, tracer_and_config):
        """测试 get_values 从 input 中的 execute_kwargs 参数获取"""
        tracer, config, _ = tracer_and_config

        # 模拟 get_agent_config_info 返回值
        mock_agent_info = {
            "agent_id": "test-agent-456",
            "agent_code": "test_agent_2",
            "agent_name": "测试智能体2",
            "agent_type": "ai_chat",
            "service_catalogue": "test_service_2",
            "updated_by": "admin",
            "otel_info": {"should_be_removed": True},  # 这个字段应该被移除
        }
        mock_get_agent_config_info.return_value = mock_agent_info

        # 创建 ExecuteKwargs 对象
        execute_kwargs = ExecuteKwargs(
            session_code="input-session-456",
            caller_bk_app_code="input-app",
            caller_bk_biz_env="domestic_biz",
            caller_bk_biz_id=200,
            caller_executor="input-user",
            caller_order_type="ai_chat",
        )

        # 创建包装器
        wrapper = LiteEnhancedAgentExecutorWrapper(tracer, config)

        # 模拟 agent 对象
        mock_agent = MagicMock()

        # 准备输入 - 通过 input 参数传递 execute_kwargs
        input_data = {"input": "测试问题2", "execute_kwargs": execute_kwargs}

        # 调用 get_values
        result = wrapper.get_values(mock_agent, input=input_data)

        # 使用公共验证函数
        verify_get_values_result(result)

        # 验证具体的值 - 应该使用 input 中的 execute_kwargs
        assert result["inputs"] == "测试问题2"
        assert result["execute_kwargs"].session_code == "input-session-456"
        assert result["execute_kwargs"].caller_executor == "input-user"
        assert result["execute_kwargs"].caller_bk_app_code == "input-app"
        assert result["execute_kwargs"].caller_bk_biz_env == "domestic_biz"
        assert result["execute_kwargs"].caller_bk_biz_id == 200
        assert result["execute_kwargs"].caller_order_type == "ai_chat"

        # 验证 execute_kwargs 已从 input 中移除（根据 pop 操作）
        assert "execute_kwargs" not in input_data


class TestLiteEnhancedAgentExecutorStreamEventsWrapper:
    """测试 LiteEnhancedAgentExecutorStreamEventsWrapper 流式包装器"""

    @patch("aidev_bkplugin.packages.opentelemetry.instrumentor.get_agent_config_info")
    def test_stream_events_wrapper(self, mock_get_agent_config_info, tracer_and_config):
        """测试流式包装器的使用 - 模拟 ChatCompletionViewSet.create 的用法"""
        tracer, config, exporter = tracer_and_config

        # 模拟 get_agent_config_info 返回值
        mock_agent_info = {
            "agent_id": "test-agent-123",
            "agent_code": "test_agent",
            "agent_name": "测试智能体",
            "agent_type": "qa",
            "service_catalogue": "test_service",
            "updated_by": "admin",
            "otel_info": {},
        }
        mock_get_agent_config_info.return_value = mock_agent_info

        # 创建 ExecuteKwargs 对象 - 模拟 ChatCompletionViewSet 的实际用法
        execute_kwargs = ExecuteKwargs(
            session_code="stream-session-456",
            caller_bk_app_code="stream-app",
            caller_bk_biz_env="domestic_biz",
            caller_bk_biz_id=200,
            caller_executor="stream-user",
            caller_order_type="ai_chat",
        )

        # 创建包装器
        wrapper = LiteEnhancedAgentExecutorStreamEventsWrapper(tracer, config)

        # 模拟被包装的函数（生成器）
        def mock_stream_events(*args, **kwargs):
            yield {"event": "start"}
            yield {"event": "data", "content": "测试"}
            yield {"event": "end"}

        # 模拟 agent 和 instance
        mock_agent = MagicMock()
        mock_instance = MagicMock()
        mock_instance.agent = mock_agent

        # 准备输入 - 通过 input 传递 execute_kwargs（而不是 request_local）
        input_data = {"input": "流式测试", "execute_kwargs": execute_kwargs}
        config_data = {"callbacks": []}

        # 调用包装器
        generator = wrapper(
            wrapped=mock_stream_events,
            instance=mock_instance,
            args=(input_data,),
            kwargs={"config": config_data},
        )

        # 消费生成器
        events = list(generator)

        # 验证生成器输出
        assert len(events) == 3
        assert events[0]["event"] == "start"
        assert events[1]["event"] == "data"
        assert events[2]["event"] == "end"

        # 验证创建了 span
        spans = exporter.get_finished_spans()
        assert len(spans) > 0

        # 找到 agent.execution span
        agent_span = None
        for span in spans:
            if span.name == "agent.execution":
                agent_span = span
                break

        assert agent_span is not None

        # 验证 span 名称
        assert agent_span.name == "agent.execution"

        # 验证 agent.session.* 属性
        assert agent_span.attributes["agent.session.session_code"] == "stream-session-456"
        assert agent_span.attributes["agent.session.caller_executor"] == "stream-user"
        assert agent_span.attributes["agent.session.caller_bk_app_code"] == "stream-app"
        assert agent_span.attributes["agent.session.caller_bk_biz_env"] == "domestic_biz"
        assert agent_span.attributes["agent.session.caller_bk_biz_id"] == 200
        assert agent_span.attributes["agent.session.caller_order_type"] == "ai_chat"

        # 验证 agent.info.* 属性
        assert agent_span.attributes["agent.info.code"] == "test_agent"


class TestLiteEnhancedAgentExecutorAInvokeWrapper:
    """测试 LiteEnhancedAgentExecutorAInvokeWrapper 异步包装器"""

    @pytest.mark.asyncio
    @patch("aidev_bkplugin.packages.opentelemetry.instrumentor.get_agent_config_info")
    async def test_ainvoke_wrapper(self, mock_get_agent_config_info, tracer_and_config):
        """测试异步包装器的使用"""
        tracer, config, exporter = tracer_and_config

        # 模拟 get_agent_config_info 返回值
        mock_agent_info = {
            "agent_id": "test-agent-789",
            "agent_code": "async_agent",
            "agent_name": "异步智能体",
            "agent_type": "qa",
            "service_catalogue": "async_service",
            "updated_by": "async_admin",
            "otel_info": {},
        }
        mock_get_agent_config_info.return_value = mock_agent_info

        # 设置 request_local.otel_info
        request_local.otel_info = {
            "session_code": "async-session-789",
            "executor": "async-user",
            "caller_bk_app_code": "async-app",
            "caller_bk_biz_env": "domestic_biz",
            "caller_executor": "async-user",
            "caller_bk_biz_id": 300,
            "caller_order_type": "ai_chat",
        }

        # 创建包装器
        wrapper = LiteEnhancedAgentExecutorAInvokeWrapper(tracer, config)

        # 模拟被包装的异步函数
        async def mock_ainvoke(*args, **kwargs):
            return {"output": "异步测试结果"}

        # 模拟 agent 和 instance
        mock_agent = MagicMock()
        mock_instance = MagicMock()
        mock_instance.agent = mock_agent

        # 准备输入
        input_data = {"input": "异步测试问题"}
        config_data = {"callbacks": []}

        # 调用包装器
        result = await wrapper(
            wrapped=mock_ainvoke,
            instance=mock_instance,
            args=(input_data,),
            kwargs={"config": config_data},
        )

        # 验证结果
        assert result == {"output": "异步测试结果"}

        # 验证创建了 span
        spans = exporter.get_finished_spans()
        assert len(spans) > 0

        # 找到 agent.execution span
        agent_span = None
        for span in spans:
            if span.name == "agent.execution":
                agent_span = span
                break

        assert agent_span is not None

        # 验证 span 名称
        assert agent_span.name == "agent.execution"

        # 验证 agent.session.* 属性
        assert agent_span.attributes["agent.session.session_code"] == "async-session-789"
        assert agent_span.attributes["agent.session.caller_executor"] == "async-user"
        assert agent_span.attributes["agent.session.caller_bk_app_code"] == "async-app"
        assert agent_span.attributes["agent.session.caller_bk_biz_env"] == "domestic_biz"
        assert agent_span.attributes["agent.session.caller_bk_biz_id"] == 300
        assert agent_span.attributes["agent.session.caller_order_type"] == "ai_chat"

        # 验证 agent.info.* 属性
        assert agent_span.attributes["agent.info.code"] == "async_agent"

        # 清理
        delattr(request_local, "otel_info")
