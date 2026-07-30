import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from ag_ui.core import EventType, RunErrorEvent, RunFinishedEvent
from aidev_agent.config import settings
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.enums import PromptRole
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.langchain_core.models.mock import MockChatModel, MockResponse
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.packages.resource_manager.base import BaseResourceManager
from aidev_agent.pydantic_models import (
    AgentConfig,
    ChatPrompt,
    ExecuteKwargs,
    KnowledgeSettings,
    ModelContextSettings,
)
from aidev_agent.services.agent import ChatCompletionAgent
from aidev_agent.services.event_handlers.base import BaseSessionWriter
from aidev_agent.services.messages_handler.streaming_helper import GeneratorStreamingHelper
from aidev_agent.utils.event import RunId
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import ToolException, tool
from langgraph.checkpoint.memory import MemorySaver


class _ConcreteWriter(BaseSessionWriter):
    """可实例化的测试用 Writer，记录回写内容以便断言"""

    def __init__(self, session_code: str = "test_session", **kwargs):
        super().__init__(session_code=session_code, **kwargs)
        self._created_contents: list[dict] = []

    @property
    def is_cancelled(self) -> bool:
        """返回是否已被取消（只读）"""
        return self._is_cancelled

    @property
    def created_contents(self) -> tuple[dict, ...]:
        """返回已创建内容的只读副本"""
        return tuple(self._created_contents)

    def _do_create_content(self, payload: dict, headers: dict) -> int | None:
        self._created_contents.append(payload)
        return len(self._created_contents)

    def _do_update_content(self, content_id: int, payload: dict, headers: dict) -> None:
        pass


def assert_content_type_equal(results: list[dict], event_type: EventType, content: str):
    contents = []
    for each in results:
        if each["type"] == event_type:
            contents.append(each["delta"])
    assert "".join(contents) == content


def assert_custom_event_exists(results: list[dict], custom_message_type: CustomMessageType) -> dict:
    """断言指定的自定义消息类型存在于 results 中并返回该事件

    Args:
        results: 事件结果列表
        custom_message_type: 自定义消息类型枚举

    Returns:
        找到的第一个匹配事件

    Raises:
        AssertionError: 如果未找到匹配的事件
    """
    matched_events = [
        e for e in results if e.get("type") == EventType.CUSTOM and e.get("name") == custom_message_type.value
    ]
    assert len(matched_events) > 0, f"应该有 {custom_message_type.value} 事件"
    return matched_events[0]


@tool
def get_weather(location: str) -> str:
    """获取指定地点的天气预报"""
    return f"天气预报：{location}, 多云，25度，湿度60%。"


@tool
def get_weather_error(location: str) -> str:
    """获取指定地点的天气预报"""
    raise ToolException("天气预报获取失败")


@tool
def slow_task(seconds: float = 1.0) -> str:
    """模拟耗时任务，用于主动停止测试"""
    time.sleep(seconds)
    return "任务执行完毕"


class TestCommonAgentChatStreaming:
    """测试聊天代理的流式响应功能"""

    def test_basic_chat(self):
        """case 1: 基础聊天测试"""
        llm = MockChatModel(
            responses=["你好\n我可以帮你什么?"],
            reasoning_contents=["用户希望我帮他复述一下上下文"],
            stream_chunk_size=2,
        )
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(
                    id="1",
                    role="system",
                    content="You are a professional translator, please help translate the user input to English.",
                ),
                ChatPrompt(id="2", role="user", content="안녕하세요"),
                ChatPrompt(id="3", role="assistant", content="Hello, how can I help you?"),
                ChatPrompt(id="4", role="user", content="复述一下上下文的内容"),
            ],
        )
        results = []
        for each in agent.execute(ExecuteKwargs(stream=True)):
            _each = json.loads(each[6:])
            results.append(_each)
        assert_content_type_equal(results, EventType.THINKING_TEXT_MESSAGE_CONTENT, "用户希望我帮他复述一下上下文")
        assert_content_type_equal(results, EventType.TEXT_MESSAGE_CONTENT, "你好\n我可以帮你什么?")

    def test_tool_calling(self):
        """case 2: 工具调用

        测试使用MockResponse按顺序返回不同类型的响应：
        1. 第一次返回工具调用
        2. 第二次返回工具结果的总结（不再有工具调用，agent自动结束）
        """
        llm = MockChatModel(
            mock_responses=[
                # 第一个响应：返回工具调用
                MockResponse(
                    content="",
                    tool_calls=[{"name": "get_weather", "args": {"location": "广州"}, "id": "call_1"}],
                ),
                # 第二个响应：返回工具结果的总结（不再有工具调用，agent会自动结束）
                MockResponse(content="根据天气预报，广州今天多云，温度25度，湿度60%。"),
            ],
            stream_chunk_size=2,
            loop=False,  # 不循环使用响应，避免无限循环
        )
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(id="1", role="user", content="今天广州天气怎么样？"),
            ],
            tools=[get_weather],
        )

        results = []
        for each in agent.execute(ExecuteKwargs(stream=True)):
            _each = json.loads(each[6:])
            results.append(_each)

        # 验证1：工具调用开始事件
        tool_call_start_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_START]
        assert len(tool_call_start_events) == 1, "应该有工具调用开始事件"

        # 验证2：工具名称正确
        tool_names = [e.get("toolCallName") for e in tool_call_start_events]
        assert "get_weather" in tool_names, f"应该调用了get_weather工具，实际: {tool_names}"

        # 验证3：工具调用结束事件
        tool_call_end_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_END]
        assert len(tool_call_end_events) == 1, "应该有工具调用结束事件"

        # 验证4：工具执行结果事件
        tool_result_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_RESULT]
        assert len(tool_result_events) == 1, "应该有工具执行结果事件"

        # 验证5：工具结果内容包含天气信息
        tool_results = [e.get("content", "") for e in tool_result_events]
        tool_result_text = "".join(tool_results)
        assert "天气预报" in tool_result_text and "广州" in tool_result_text, (
            f"工具结果应该包含天气信息，实际: {tool_result_text[:100]}"
        )

    def test_parallel_tool_calls(self):
        """case 2b: 并行工具调用

        测试当 LLM 返回多个并行工具调用时，agent 正确处理：
        1. 两个工具同时被调用
        2. 两个工具的结果都被收集
        3. 最终汇总两个工具的结果
        """
        llm = MockChatModel(
            mock_responses=[
                # 第一个响应：返回两个并行工具调用（不同 index 表示并行）
                MockResponse(
                    content="",
                    tool_calls=[
                        {"name": "get_weather", "args": {"location": "广州"}, "id": "call_1", "index": 0},
                        {"name": "get_weather", "args": {"location": "深圳"}, "id": "call_2", "index": 1},
                    ],
                ),
                # 第二个响应：返回工具结果的总结
                MockResponse(content="根据查询结果，广州今天多云25度，深圳晴朗28度。"),
            ],
            stream_chunk_size=2,
            loop=False,
        )
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(id="1", role="user", content="今天广州和深圳的天气怎么样？"),
            ],
            tools=[get_weather],
        )

        results = []
        for each in agent.execute(ExecuteKwargs(stream=True)):
            _each = json.loads(each[6:])
            results.append(_each)

        # 验证1：有两个工具调用开始事件
        tool_call_start_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_START]
        assert len(tool_call_start_events) == 2, f"应该有两个工具调用开始事件，实际: {len(tool_call_start_events)}"

        # 验证2：两个工具都被调用
        tool_names = [e.get("toolCallName") for e in tool_call_start_events]
        assert tool_names.count("get_weather") == 2, f"应该调用了两次 get_weather 工具，实际: {tool_names}"

        # 验证3：验证两个工具调用的参数
        tool_call_args_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_ARGS]
        assert len(tool_call_args_events) == 2, f"应该有两个工具调用参数事件，实际: {len(tool_call_args_events)}"

        # 验证参数内容
        args_list = [json.loads(e.get("delta", "{}")) for e in tool_call_args_events]
        locations = [args.get("location", "") for args in args_list]
        assert "广州" in locations, f"应该包含广州，实际: {locations}"
        assert "深圳" in locations, f"应该包含深圳，实际: {locations}"

        # 验证4：有两个工具调用结束事件
        tool_call_end_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_END]
        assert len(tool_call_end_events) == 2, f"应该有两个工具调用结束事件，实际: {len(tool_call_end_events)}"

        # 验证5：有两个工具执行结果事件
        tool_result_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_RESULT]
        assert len(tool_result_events) == 2, f"应该有两个工具执行结果事件，实际: {len(tool_result_events)}"

        # 验证6：工具结果内容包含两个城市的天气信息
        tool_results = [e.get("content", "") for e in tool_result_events]
        tool_result_text = "".join(tool_results)
        assert "广州" in tool_result_text, f"工具结果应该包含广州，实际: {tool_result_text}"
        assert "深圳" in tool_result_text, f"工具结果应该包含深圳，实际: {tool_result_text}"

        # 验证7：最终文本响应包含汇总结果
        assert_content_type_equal(
            results, EventType.TEXT_MESSAGE_CONTENT, "根据查询结果，广州今天多云25度，深圳晴朗28度。"
        )

    def test_tool_call_after_reasoning_emits_model_stream_events(self):
        llm = MockChatModel(
            mock_responses=[
                MockResponse(
                    content="\n\n",
                    reasoning_content="我需要先思考，再调用天气工具。",
                    tool_calls=[{"name": "get_weather", "args": {"location": "广州"}, "id": "call_1"}],
                ),
                MockResponse(content="广州今天多云，温度25度。"),
            ],
            stream_chunk_size=2,
            loop=False,
        )
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(id="1", role="user", content="今天广州天气怎么样？")],
            tools=[get_weather],
        )
        results = [json.loads(each[6:]) for each in agent.execute(ExecuteKwargs(stream=True))]
        tool_start = next(e for e in results if e.get("type") == EventType.TOOL_CALL_START)
        tool_args = next(e for e in results if e.get("type") == EventType.TOOL_CALL_ARGS)
        tool_result_index = next(i for i, e in enumerate(results) if e.get("type") == EventType.TOOL_CALL_RESULT)
        tool_args_index = next(i for i, e in enumerate(results) if e.get("type") == EventType.TOOL_CALL_ARGS)
        assert tool_start["rawEvent"]["event"] == "on_chat_model_stream"
        assert tool_args["rawEvent"]["event"] == "on_chat_model_stream"
        assert json.loads(tool_args["delta"]) == {"location": "广州"}
        assert tool_args_index < tool_result_index

    def test_mcp_tool_calling(self):
        """case 3: MCP工具调用

        测试使用MockResponse模拟MCP工具调用流程：
        1. 第一次返回MCP工具调用
        2. 第二次返回MCP工具结果的总结

        使用mock避免依赖外部MCP服务器配置
        """
        from langchain_core.tools import StructuredTool

        # 创建一个mock的MCP工具（模拟从MCP服务器获取的工具）
        async def mock_mcp_get_time(timezone: str = "UTC") -> str:
            """获取指定时区的当前时间"""
            return f"当前{timezone}时区的时间是: 2024-01-28 12:00:00"

        mock_mcp_tool = StructuredTool.from_function(
            coroutine=mock_mcp_get_time,
            name="get_current_time",
            description="获取指定时区的当前时间",
        )
        # 添加metadata标记这是MCP工具
        mock_mcp_tool.metadata = {"mcp_name": "time-server"}

        # 创建MockChatModel，模拟工具调用流程
        llm = MockChatModel(
            mock_responses=[
                # 第一个响应：返回MCP工具调用
                MockResponse(
                    content="",
                    tool_calls=[
                        {"name": "get_current_time", "args": {"timezone": "Asia/Shanghai"}, "id": "call_mcp_1"}
                    ],
                ),
                # 第二个响应：返回工具结果的总结（不再有工具调用，agent会自动结束）
                MockResponse(content="根据查询结果，Asia/Shanghai时区的当前时间是2024-01-28 12:00:00。"),
            ],
            stream_chunk_size=2,
            loop=False,  # 不循环使用响应，避免无限循环
        )

        # 创建Agent，直接传入mock的MCP工具
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(id="1", role="user", content="现在上海是几点？"),
            ],
            tools=[mock_mcp_tool],  # 直接传入mock的MCP工具
        )

        results = []
        for each in agent.execute(ExecuteKwargs(stream=True)):
            _each = json.loads(each[6:])
            results.append(_each)

        # 验证1：工具调用开始事件
        tool_call_start_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_START]
        assert len(tool_call_start_events) > 0, "应该有工具调用开始事件"
        assert tool_call_start_events[0]["mcpName"] == "time-server"

        # 验证2：MCP工具名称正确
        tool_names = [e.get("toolCallName") for e in tool_call_start_events]
        assert "get_current_time" in tool_names, f"应该调用了get_current_time工具，实际: {tool_names}"

        # 验证3：工具调用结束事件
        tool_call_end_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_END]
        assert len(tool_call_end_events) > 0, "应该有工具调用结束事件"

        # 验证4：工具执行结果事件
        tool_result_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_RESULT]
        assert len(tool_result_events) > 0, "应该有工具执行结果事件"

        # 验证5：工具结果内容包含时间信息
        tool_results = [e.get("content", "") for e in tool_result_events]
        tool_result_text = "".join(tool_results)
        assert "Asia/Shanghai" in tool_result_text and "时间" in tool_result_text, (
            f"工具结果应该包含时间信息，实际: {tool_result_text[:100]}"
        )

    @pytest.mark.skip(reason="待修复：从 checkpoint 恢复的用例暂时跳过")
    def test_resume_from_checkpoint(self):
        """case 4: 从checkpoint恢复

        测试使用MockResponse模拟MCP工具调用流程：
        1. 第一次返回MCP工具调用
        2. 第二次从checkpoint恢复并继续响应

        """
        llm = MockChatModel(
            responses=["你好\n我可以帮你什么?"],
            reasoning_contents=["用户希望我帮他复述一下上下文"],
            stream_chunk_size=2,
        )
        thread_id = "onlyfortest"
        agent = ChatCompletionAgent(
            thread_id=thread_id,
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(
                    id="1",
                    role="system",
                    content="You are a professional translator, please help translate the user input to English.",
                ),
                ChatPrompt(id="2", role="user", content="안녕하세요"),
                ChatPrompt(id="3", role="assistant", content="Hello, how can I help you?"),
                ChatPrompt(id="4", role="user", content="复述一下上下文的内容"),
            ],
        )
        results = []
        for idx, each in enumerate(agent.execute(ExecuteKwargs(stream=True))):
            _each = json.loads(each[6:])
            results.append(_each)
            if idx == 10:
                break

        agent2 = ChatCompletionAgent(
            thread_id=thread_id,
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(
                    id="1",
                    role="system",
                    content="You are a professional translator, please help translate the user input to English.",
                ),
                ChatPrompt(id="2", role="user", content="안녕하세요"),
                ChatPrompt(id="3", role="assistant", content="Hello, how can I help you?"),
                ChatPrompt(id="4", role="user", content="复述一下上下文的内容"),
            ],
        )
        for idx, each in enumerate(agent2.execute(ExecuteKwargs(stream=True))):
            _each = json.loads(each[6:])
            results.append(_each)

        assert_content_type_equal(results, EventType.THINKING_TEXT_MESSAGE_CONTENT, "用户希望我帮他复述一下上下文")
        assert_content_type_equal(results, EventType.TEXT_MESSAGE_CONTENT, "你好\n我可以帮你什么?")

    def test_model_error_case(self):
        """case 5: 模型错误处理

        测试当使用无权限的模型时，错误信息能够被正确捕获并返回给消费者。
        使用MockChatModel模拟模型调用异常。
        错误响应格式: data: {"event": "error", "code": "UNKNOWN", "message": "模型调用异常: ..."}
        """

        llm = MockChatModel(
            responses=[""],  # 空响应
            sleep_time=0,
        )

        # Mock _astream方法使其抛出异常（agent使用的是异步流式调用）
        with patch.object(llm, "_astream", side_effect=Exception("Authentication failed for model gptoss-999b")):
            agent = ChatCompletionAgent(
                chat_model=llm,
                checkpointer=MemorySaver(),
                chat_history=[
                    ChatPrompt(role="user", content="nonono"),
                ],
            )
            result_content = []
            result = agent.execute(ExecuteKwargs(stream=True))
            result_content = list(result)

            # 验证错误消息被正确捕获
            # 当前实现：RUN_ERROR 后跟 RUN_FINISHED 作为结束信号
            error_events = [
                c for c in result_content if c.startswith("data: ") and json.loads(c[6:]).get("type") == "RUN_ERROR"
            ]
            assert len(error_events) >= 1
            error_payload = json.loads(error_events[0][6:])
            assert error_payload["message"].startswith("模型调用异常: Authentication failed for model gptoss-999b")
            # 最后一条事件应为 RUN_FINISHED
            last_content = result_content[-1]
            assert last_content.startswith("data: ")
            assert json.loads(last_content[6:])["type"] == "RUN_FINISHED"

    def test_tool_call_error_case(self):
        """case 6: 工具调用错误处理

        测试工具执行时抛出异常的情况，验证错误能被正确捕获并继续执行。
        使用MockResponse模拟工具调用流程：
        1. 第一次返回工具调用
        2. 工具执行抛出异常
        3. 第二次返回对错误的处理结果
        """
        llm = MockChatModel(
            mock_responses=[
                # 第一个响应：返回工具调用
                MockResponse(
                    content="",
                    tool_calls=[{"name": "get_weather_error", "args": {"location": "深圳"}, "id": "call_1"}],
                ),
                # 第二个响应：返回对工具错误的处理（agent会收到工具错误并继续）
                MockResponse(content="抱歉，获取天气信息时出现错误，请稍后再试。"),
            ],
            stream_chunk_size=2,
            loop=False,  # 不循环使用响应
        )
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(role="user", content="今天深圳天气"),
            ],
            tools=[get_weather_error],
        )

        results = []
        for each in agent.execute(ExecuteKwargs(stream=True)):
            _each = json.loads(each[6:])
            results.append(_each)

        # 验证1：工具调用开始事件
        tool_call_start_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_START]
        assert len(tool_call_start_events) > 0, "应该有工具调用开始事件"

        # 验证2：工具名称正确
        tool_names = [e.get("toolCallName") for e in tool_call_start_events]
        assert "get_weather_error" in tool_names, f"应该调用了get_weather_error工具，实际: {tool_names}"

        # 验证3：最终文本响应应该是第二个MockResponse的内容
        assert_content_type_equal(results, EventType.TEXT_MESSAGE_CONTENT, "抱歉，获取天气信息时出现错误，请稍后再试。")

        # 验证4：工具调用结果事件
        tool_call_result_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_RESULT]
        assert len(tool_call_result_events) > 0, "应该有工具调用结果事件"
        assert tool_call_result_events[0].get("isError") is True, "工具调用结果事件应该包含错误信息"

    def test_mcp_tool_fetch_failed_event(self):
        """case 7: MCP工具拉取失败事件

        测试 make_mcp_tools 在流开始前即失败时，错误能通过自定义事件返回事件流：
        1. 传入 mcp_fetch_failures 模拟拉取失败
        2. 流式执行后断言出现 mcp_tool_fetch_failed 自定义事件
        3. 断言事件 payload 含 server_name、message，且流正常继续输出模型内容
        """
        mcp_failures = [
            {
                "server_name": "test-mcp-server",
                "message": "获取MCP工具列表失败: Connection refused",
                "error_type": "ConnectionError",
            }
        ]
        llm = MockChatModel(responses=["你好，我可以帮你。"], stream_chunk_size=2)
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="你好")],
            mcp_fetch_failures=mcp_failures,
        )
        results = [json.loads(each[6:]) for each in agent.execute(ExecuteKwargs(stream=True))]
        # 首条事件为 MESSAGES_SNAPSHOT（AidevAGUIAgent.run 每次 SSE 先下发消息快照）
        assert results[0].get("type") == EventType.MESSAGES_SNAPSHOT.value, "首条事件应为 MESSAGES_SNAPSHOT"
        assert results[1].get("type") == EventType.RUN_STARTED.value, "第二条事件应为 RUN_STARTED"
        run_finished_indices = [i for i, e in enumerate(results) if e.get("type") == EventType.RUN_FINISHED.value]
        mcp_ev_indices = [
            i
            for i, e in enumerate(results)
            if e.get("type") == EventType.CUSTOM and e.get("name") == CustomMessageType.TEMP_MESSAGE.value
        ]
        assert mcp_ev_indices, "应有 temp_message 事件"
        assert run_finished_indices, "应有 RUN_FINISHED 事件"
        assert mcp_ev_indices[0] == 2, "temp_message 应紧跟在 RUN_STARTED 后"
        assert max(mcp_ev_indices) < min(run_finished_indices), "temp_message 应在 RUN_FINISHED 前"
        old_events = [
            e
            for e in results
            if e.get("type") == EventType.CUSTOM and e.get("name") == CustomMessageType.MCP_TOOL_FETCH_FAILED.value
        ]
        assert not old_events, "不应再返回 mcp_tool_fetch_failed 事件"
        ev = assert_custom_event_exists(results, CustomMessageType.TEMP_MESSAGE)
        value = ev.get("value") or {}
        assert value.get("status") == "error"
        assert "test-mcp-server" in (value.get("message") or "")
        assert "获取MCP工具列表失败" in (value.get("message") or "")
        assert_content_type_equal(results, EventType.TEXT_MESSAGE_CONTENT, "你好，我可以帮你。")

    def test_mcp_tool_fetch_failed_event_merged(self):
        """case 7b: 多条 MCP 拉取失败合并为一条 temp_message 事件"""
        mcp_failures = [
            {
                "server_name": "mcp-a",
                "message": "获取MCP工具列表失败: Connection refused",
                "error_type": "ConnectionError",
            },
            {"server_name": "mcp-b", "message": "获取MCP工具列表失败: Timeout", "error_type": "TimeoutError"},
        ]
        llm = MockChatModel(responses=["收到。"], stream_chunk_size=2)
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="hi")],
            mcp_fetch_failures=mcp_failures,
        )
        results = [json.loads(each[6:]) for each in agent.execute(ExecuteKwargs(stream=True))]
        mcp_events = [
            e
            for e in results
            if e.get("type") == EventType.CUSTOM and e.get("name") == CustomMessageType.TEMP_MESSAGE.value
        ]
        assert len(mcp_events) == 1, "多条失败应合并为一条 CUSTOM 事件"
        temp_message_index = next(
            i
            for i, e in enumerate(results)
            if e.get("type") == EventType.CUSTOM and e.get("name") == CustomMessageType.TEMP_MESSAGE.value
        )
        assert temp_message_index == 2, "合并后的 temp_message 应在 MESSAGES_SNAPSHOT + RUN_STARTED 后"
        value = mcp_events[0].get("value") or {}
        assert value.get("status") == "error"
        assert "mcp-a" in (value.get("message") or "")
        assert "Connection refused" in (value.get("message") or "")
        assert "mcp-b" in (value.get("message") or "")
        assert "Timeout" in (value.get("message") or "")

    def test_knowledge_base(self):
        """case 8: 知识库"""
        with open("tests/mock_data/knowledgebase.json") as fi:
            knowledgebase = json.load(fi)
        with open("tests/mock_data/knowledge_query.json") as fi:
            knowledge_query_result = json.load(fi)

        # Mock _query_instance 属性以返回固定的知识库查询结果
        with patch.object(BkRetriever, "_query_instance", return_value=knowledge_query_result) as mocked_query_instance:
            agent = ChatCompletionAgent(
                chat_model=MockChatModel(responses=["根据知识库，云桌面黑屏的处理方法是重启"]),
                checkpointer=MemorySaver(),
                chat_history=[
                    ChatPrompt(role="user", content="云桌面黑屏怎么处理?"),
                ],
                knowledge_query_options=KnowledgeSettings(knowledge_bases=[knowledgebase]),
            )
            results = []
            for each in agent.execute(ExecuteKwargs(stream=True)):
                _each = json.loads(each[6:])
                results.append(_each)
            assert_content_type_equal(results, EventType.TEXT_MESSAGE_CONTENT, "根据知识库，云桌面黑屏的处理方法是重启")
            mocked_query_instance.assert_called_once()

            # 验证知识库相关的自定义消息类型
            assert_custom_event_exists(results, CustomMessageType.KNOWLEDGE_RAG_START)
            assert_custom_event_exists(results, CustomMessageType.KNOWLEDGE_RAG_END)
            assert_custom_event_exists(results, CustomMessageType.KNOWLEDGE_RAG_TEXT_CONTENT)
            assert_custom_event_exists(results, CustomMessageType.KNOWLEDGE_RAG_RESULT)

    def test_stop_during_long_tool_streaming(self):
        """case 9: 耗时工具执行中主动停止，验证流式输出在停止后正常结束且为部分结果

        流程：先触发耗时工具调用，在工具执行期间调用 stop()，
        断言流式输出包含工具调用开始事件，且未包含完整最终文本（或流已结束）。
        """
        thread_id = "test_stop_during_tool"
        llm = MockChatModel(
            mock_responses=[
                MockResponse(
                    content="",
                    tool_calls=[{"name": "slow_task", "args": {"seconds": 1.5}, "id": "call_slow"}],
                ),
                MockResponse(content="根据结果，耗时任务已完成。"),
            ],
            stream_chunk_size=2,
            loop=False,
        )
        agent = ChatCompletionAgent(
            thread_id=thread_id,
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="执行一个慢任务")],
            tools=[slow_task],
        )
        results = []
        stream_done = threading.Event()

        def consume():
            nonlocal results
            for each in agent.execute(ExecuteKwargs(stream=True)):
                _each = json.loads(each[6:])
                results.append(_each)
            stream_done.set()

        t = threading.Thread(target=consume)
        t.start()
        time.sleep(0.5)
        agent.stop()
        stream_done.wait(timeout=5.0)
        t.join(timeout=3.0)
        assert not t.is_alive(), "消费线程应在超时内结束"

        tool_start_events = [r for r in results if r.get("type") == EventType.TOOL_CALL_START]
        assert len(tool_start_events) >= 1, "流式输出应包含工具调用开始事件"
        assert any(e.get("toolCallName") == "slow_task" for e in tool_start_events), "应调用了 slow_task 工具"
        # 主动停止后流应正常结束；可能收到工具结果或部分最终回复（取决于取消检查时机）
        assert stream_done.is_set(), "流式消费应在超时内结束"

    def test_with_system_prompt(self):
        """case 10: 系统提示词（mock）"""
        llm = MockChatModel(responses=["<result>云桌面黑屏处理步骤</result>"], stream_chunk_size=3)
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(
                    role="system",
                    content="Please return the output in below format:\nresponse format: <result>...</result>",
                ),
                ChatPrompt(role="user", content="云桌面黑屏怎么处理?"),
            ],
        )
        results = []
        for each in agent.execute(ExecuteKwargs(stream=True)):
            _each = json.loads(each[6:])
            results.append(_each)

        text_deltas = [e.get("delta", "") for e in results if e.get("type") == EventType.TEXT_MESSAGE_CONTENT]
        final_text = "".join(text_deltas).strip()
        assert final_text == "<result>云桌面黑屏处理步骤</result>"


class TestOnComplete:
    """测试 _on_complete 回调：流结束时通知 event_handler 更新会话状态"""

    @pytest.mark.parametrize(
        "event_handler, should_call",
        [
            pytest.param(None, False, id="no_handler"),
            pytest.param(lambda e: None, False, id="plain_callable_without_method"),
        ],
    )
    def test_on_complete_noop(self, event_handler, should_call):
        """event_handler 为 None 或不含 set_streaming_finished 时不报错"""
        agent = ChatCompletionAgent(
            chat_model=MockChatModel(responses=["ok"]),
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="hi")],
            event_handler=event_handler,
        )
        agent._on_complete()

    def test_on_complete_calls_set_streaming_finished(self):
        """event_handler 拥有 set_streaming_finished 时应被调用"""
        mock_handler = MagicMock(spec=BaseSessionWriter)
        agent = ChatCompletionAgent(
            chat_model=MockChatModel(responses=["ok"]),
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="hi")],
            event_handler=mock_handler,
        )
        agent._on_complete()
        mock_handler.set_streaming_finished.assert_called_once()

    def test_on_complete_invoked_during_stream(self):
        """端到端验证：流式执行结束后 on_complete 被触发"""
        mock_handler = MagicMock(spec=BaseSessionWriter)
        llm = MockChatModel(responses=["hello"], stream_chunk_size=2)
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="hi")],
            event_handler=mock_handler,
        )
        list(agent.execute(ExecuteKwargs(stream=True)))
        mock_handler.set_streaming_finished.assert_called_once()


class TestChatModelClientCleanup:
    @pytest.mark.asyncio
    async def test_owned_client_is_closed_once(self):
        model = ChatModel.get_setup_instance(
            model="primary",
            base_url="https://llm-gateway.example.com/v1",
        )
        client = model.http_async_client
        close_spy = AsyncMock(wraps=client.aclose)
        agent = ChatCompletionAgent(chat_model=model, chat_model_non_thinking=model)

        with patch.object(client, "aclose", close_spy):
            await agent._aclose_chat_models()

        close_spy.assert_awaited_once()
        assert client.is_closed
        assert model._owns_http_async_client is False

    def test_non_streaming_execute_closes_owned_client(self):
        model = ChatModel.get_setup_instance(
            model="primary",
            base_url="https://llm-gateway.example.com/v1",
        )
        client = model.http_async_client
        close_spy = AsyncMock(wraps=client.aclose)
        agent = ChatCompletionAgent(chat_model=model)
        agent_e = MagicMock()
        agent_e.ainvoke = AsyncMock(return_value={"messages": [AIMessage(content="done", id="message-id")]})

        with (
            patch.object(agent, "_update_aidev_agent_header"),
            patch.object(agent, "_get_agent", return_value=(agent_e, {})),
            patch.object(agent, "_sync_checkpoint_messages"),
            patch.object(client, "aclose", close_spy),
        ):
            result = agent._execute([HumanMessage(content="hello")], ExecuteKwargs(stream=False))

        assert result["choices"][0]["delta"]["content"] == "done"
        close_spy.assert_awaited_once()
        assert client.is_closed


@pytest.mark.skipif(
    not all([settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
class TestCommonAgentChatStreamingLive:
    """测试聊天代理的流式响应功能"""

    def setup_method(self):
        self.llm = ChatModel.get_setup_instance(model="dsv32-reasoner")

    def test_knowledge_base(self):
        """case 1: 知识库"""
        with open("tests/mock_data/knowledgebase.json") as fi:
            knowledgebase = json.load(fi)
        agent = ChatCompletionAgent(
            chat_model=self.llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(role="user", content="云桌面黑屏怎么处理?"),
            ],
            knowledge_query_options=KnowledgeSettings(knowledge_bases=[knowledgebase]),
        )
        with open("text.log", "w") as fo:
            result = agent.execute(ExecuteKwargs(stream=True))
            for each in result:
                fo.write(each)

    def test_tool_call_legacy(self):
        """case 2: 工具调用 legacy streaming"""
        agent = ChatCompletionAgent(
            chat_model=self.llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(role="user", content="今天广州天气怎么样?"),
            ],
            tools=[get_weather],
        )
        with open("text.log", "w") as fo:
            result = agent.execute(ExecuteKwargs(stream=True, legacy_streaming=True))
            for each in result:
                try:
                    each = json.dumps(json.loads(each[6:]), ensure_ascii=False) + "\n"
                except json.JSONDecodeError:
                    fo.write(each)
                    continue
                fo.write(each)

    def test_knowledge_base_legacy(self):
        """case 3: 知识库 legacy streaming"""
        with open("tests/mock_data/knowledgebase.json") as fi:
            knowledgebase = json.load(fi)
        agent = ChatCompletionAgent(
            chat_model=self.llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(role="user", content="云桌面黑屏怎么处理?"),
            ],
            knowledge_query_options=KnowledgeSettings(knowledge_bases=[knowledgebase]),
        )
        with open("text.log", "w") as fo:
            result = agent.execute(ExecuteKwargs(stream=True, legacy_streaming=True))
            for each in result:
                fo.write(each)

    def test_tool_call_new(self):
        """case 4: 工具调用 new streaming"""
        agent = ChatCompletionAgent(
            chat_model=self.llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(role="user", content="今天广州天气怎么样?"),
            ],
            tools=[get_weather],
        )
        with open("text.log", "w") as fo:
            result = agent.execute(ExecuteKwargs(stream=True))
            for each in result:
                try:
                    each = json.dumps(json.loads(each[6:]), ensure_ascii=False) + "\n"
                except json.JSONDecodeError:
                    fo.write(each)
                    continue
                fo.write(each)


class TestCommonAgentChatStreamingWithAgentLegacyStreaming:
    """测试聊天代理的流式响应功能"""

    def test_basic_chat_openai(self):
        """case 1: 基础聊天测试"""
        llm = MockChatModel(
            responses=["你好\n我可以帮你什么?"],
            reasoning_contents=["用户希望我帮他复述一下上下文"],
            stream_chunk_size=2,
        )
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(
                    id="1",
                    role="system",
                    content="You are a professional translator, please help translate the user input to English.",
                ),
                ChatPrompt(id="2", role="user", content="안녕하세요"),
                ChatPrompt(id="3", role="assistant", content="Hello, how can I help you?"),
                ChatPrompt(id="4", role="user", content="复述一下上下文的内容"),
            ],
        )
        results = []
        for each in agent.execute(ExecuteKwargs(stream=True, legacy_streaming=True)):
            if each == "data: [DONE]\n\n":
                continue
            _each = json.loads(each[6:])
            results.append(_each)
        # Legacy stream uses "event": "think" / "text" and "content"
        think_contents = [e.get("content", "") for e in results if e.get("event") == "think"]
        text_contents = [e.get("content", "") for e in results if e.get("event") == "text"]
        assert "".join(think_contents) == "用户希望我帮他复述一下上下文\n"
        assert "".join(text_contents) == "你好\n我可以帮你什么?"

    def test_basic_chat_deepseek(self):
        """case 2: 基础聊天测试"""
        llm = MockChatModel(
            responses=['```json\n{\n  "action": "Final Answer",\n  "action_input": "你好\\n我可以帮你什么?"\n}\n```'],
            reasoning_contents=["用户希望我帮他复述一下上下文"],
            stream_chunk_size=2,
        )
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[
                ChatPrompt(
                    id="1",
                    role="system",
                    content="You are a professional translator, please help translate the user input to English.",
                ),
                ChatPrompt(id="2", role="user", content="안녕하세요"),
                ChatPrompt(id="3", role="assistant", content="Hello, how can I help you?"),
                ChatPrompt(id="4", role="user", content="复述一下上下文的内容"),
            ],
            model_context_options=ModelContextSettings(llm_code_agent_type="deepseek"),
        )
        results = []
        for each in agent.execute(ExecuteKwargs(stream=True, legacy_streaming=True)):
            if each == "data: [DONE]\n\n":
                continue
            _each = json.loads(each[6:])
            results.append(_each)
        # Legacy stream uses "event": "think" / "text" and "content"
        think_contents = [e.get("content", "") for e in results if e.get("event") == "think"]
        text_contents = [e.get("content", "") for e in results if e.get("event") == "text"]
        assert "用户希望我帮他复述一下上下文" in "".join(think_contents)
        normalized_text = "".join(text_contents).strip().strip('"')
        assert normalized_text == "你好\n我可以帮你什么?"


def _make_dummy_chat_ctx():
    """构造仅满足 ``ChatAgentBuilder.__init__`` 的最小化 ctx
    （``_handle_last_human_message`` 在 ``session_context_data=[]`` 时直接 return）。
    """
    from aidev_agent.services.agent import AgentBuildContext

    ctx = MagicMock(spec=AgentBuildContext)
    ctx.session_context_data = []
    return ctx


def test_chat_agent_builder_ignores_none_extra_in_last_user_message():
    """最后一条 user 消息 extra=None 时，应按无指定资源处理。"""
    from aidev_agent.services.agent.chat import ChatAgentBuilder

    ctx = _make_dummy_chat_ctx()
    ctx.session_context_data = [{"role": PromptRole.USER.value, "content": "hi", "extra": None}]

    builder = ChatAgentBuilder(ctx)

    assert builder._specific_resources == []


def test_build_chat_history_prepends_config_role_prompts_once():
    """角色提示词由 ChatAgentBuilder 统一构建，插件层不需要提前拼上下文。"""
    from aidev_agent.services.agent.chat import ChatAgentBuilder

    ctx = _make_dummy_chat_ctx()
    ctx.agent_code = "role_prompt-test"
    ctx.extra = {}
    ctx.agent_config.role_prompts = [
        {"role": PromptRole.SYSTEM.value, "content": "system prompt"},
        {"role": PromptRole.PAUSE.value, "content": "pause prompt"},
        {"role": "hidden-user", "content": "hidden user prompt"},
    ]

    history = ChatAgentBuilder(ctx).build_chat_history(
        [{"role": PromptRole.USER.value, "content": "hi"}],
    )

    assert [(item.role, item.content) for item in history] == [
        (PromptRole.SYSTEM.value, "system prompt"),
        (PromptRole.PAUSE.value, "pause prompt"),
        (PromptRole.USER.value, "hidden user prompt"),
        (PromptRole.USER.value, "hi"),
    ]


class TestFilterUnmatchedToolCalls:
    """测试过滤没有匹配工具结果的 assistant 消息"""

    def test_filter_assistant_without_tool_calls(self):
        """case 1: assistant 消息没有 tool_calls，应该保留"""
        from aidev_agent.services.agent.chat import ChatAgentBuilder

        chat_history = [
            ChatPrompt(id="1", role="user", content="你好"),
            ChatPrompt(id="2", role="assistant", content="你好！有什么我可以帮助你的吗？"),
            ChatPrompt(id="3", role="user", content="今天天气怎么样？"),
        ]

        builder = ChatAgentBuilder(_make_dummy_chat_ctx())
        filtered = builder._filter_unmatched_tool_calls(chat_history)

        assert len(filtered) == 3, "没有 tool_calls 的消息应该全部保留"

    def test_filter_assistant_with_matched_tool_calls(self):
        """case 2: assistant 消息有 tool_calls 且有对应的 tool 结果，应该保留"""
        from aidev_agent.services.agent.chat import ChatAgentBuilder

        chat_history = [
            ChatPrompt(id="1", role="user", content="今天广州天气怎么样？"),
            ChatPrompt(
                id="2",
                role="assistant",
                content="让我查一下天气。",
                builtin_property={
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "function": {"name": "get_weather", "arguments": '{"location": "广州"}'},
                        }
                    ]
                },
            ),
            ChatPrompt(
                id="3",
                role="tool",
                content="广州今天多云，25度",
                builtin_property={"tool_call_id": "call_abc123"},
            ),
            ChatPrompt(id="4", role="assistant", content="广州今天多云，温度25度。"),
        ]

        builder = ChatAgentBuilder(_make_dummy_chat_ctx())
        filtered = builder._filter_unmatched_tool_calls(chat_history)

        assert len(filtered) == 4, "完整匹配的工具调用链应该保留"
        assert filtered[1].role == "assistant", "assistant 消息应该保留"
        assert filtered[2].role == "tool", "tool 消息应该保留"

    def test_filter_assistant_with_unmatched_tool_calls(self):
        """case 3: assistant 消息有 tool_calls 但没有对应的 tool 结果，应该被过滤"""
        from aidev_agent.services.agent.chat import ChatAgentBuilder

        chat_history = [
            ChatPrompt(id="1", role="user", content="今天广州天气怎么样？"),
            ChatPrompt(
                id="2",
                role="assistant",
                content="让我查一下天气。",
                builtin_property={
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "function": {"name": "get_weather", "arguments": '{"location": "广州"}'},
                        }
                    ]
                },
            ),
            # 没有 tool 结果消息
            ChatPrompt(id="4", role="assistant", content="抱歉，查询失败。"),
        ]

        builder = ChatAgentBuilder(_make_dummy_chat_ctx())
        filtered = builder._filter_unmatched_tool_calls(chat_history)

        # 有 tool_calls 但没有结果的 assistant 消息被过滤
        assert len(filtered) == 2, "没有匹配结果的 assistant 消息应该被过滤"
        # 第一条是 user
        assert filtered[0].role == "user"
        # 第二条是 assistant（没有 tool_calls 的那条，id=4）
        assert filtered[1].role == "assistant"
        assert filtered[1].id == "4"

    def test_filter_multiple_tool_calls_partial_match(self):
        """case 4: assistant 消息有多个 tool_calls，仅部分有对应结果，保留消息但移除未匹配的 tool_calls"""
        from aidev_agent.services.agent.chat import ChatAgentBuilder

        chat_history = [
            ChatPrompt(id="1", role="user", content="帮我查询广州和深圳的天气"),
            ChatPrompt(
                id="2",
                role="assistant",
                content="我来帮你查询两个城市的天气。",
                builtin_property={
                    "tool_calls": [
                        {
                            "id": "call_gz",
                            "function": {"name": "get_weather", "arguments": '{"location": "广州"}'},
                        },
                        {
                            "id": "call_sz",
                            "function": {"name": "get_weather", "arguments": '{"location": "深圳"}'},
                        },
                    ]
                },
            ),
            # 只有广州的天气结果，深圳的缺失
            ChatPrompt(
                id="3",
                role="tool",
                content="广州今天多云，25度",
                builtin_property={"tool_call_id": "call_gz"},
            ),
            ChatPrompt(id="4", role="assistant", content="广州今天多云。"),
        ]

        builder = ChatAgentBuilder(_make_dummy_chat_ctx())
        filtered = builder._filter_unmatched_tool_calls(chat_history)

        # assistant 消息应该保留，但只有 call_gz 这个 tool_call
        assert len(filtered) == 4, "部分匹配时应该保留 assistant 消息"
        # 验证消息顺序和内容
        assert filtered[0].role == "user"
        assert filtered[0].id == "1"
        # assistant 消息保留，但 tool_calls 只剩一个
        assert filtered[1].role == "assistant"
        assert filtered[1].id == "2"
        # 验证 tool_calls 只保留了匹配的那个
        remaining_calls = filtered[1].builtin_property.get("tool_calls", [])
        assert len(remaining_calls) == 1, "应该只保留匹配的 tool_call"
        assert remaining_calls[0]["id"] == "call_gz"
        # tool 消息保留
        assert filtered[2].role == "tool"
        assert filtered[2].id == "3"
        # 最后的 assistant 消息保留
        assert filtered[3].role == "assistant"
        assert filtered[3].id == "4"

    def test_filter_multiple_unmatched_assistant_messages(self):
        """case 5: 多条连续的 assistant 消息都有 tool_calls，只有最后一条有完整结果"""
        from aidev_agent.services.agent.chat import ChatAgentBuilder

        chat_history = [
            ChatPrompt(id="1", role="user", content="帮我创建需求"),
            ChatPrompt(
                id="2",
                role="assistant",
                content="好的，我来帮你创建。",
                builtin_property={
                    "tool_calls": [{"id": "call_1", "function": {"name": "create_story", "arguments": "{}"}}]
                },
            ),
            ChatPrompt(
                id="3",
                role="assistant",
                content="参数格式有问题，重试。",
                builtin_property={
                    "tool_calls": [{"id": "call_2", "function": {"name": "create_story", "arguments": "{}"}}]
                },
            ),
            ChatPrompt(
                id="4",
                role="assistant",
                content="再次尝试。",
                builtin_property={
                    "tool_calls": [{"id": "call_3", "function": {"name": "create_story", "arguments": "{}"}}]
                },
            ),
            ChatPrompt(
                id="5",
                role="assistant",
                content="最终成功了。",
                builtin_property={
                    "tool_calls": [{"id": "call_4", "function": {"name": "create_story", "arguments": "{}"}}]
                },
            ),
            ChatPrompt(
                id="6",
                role="tool",
                content="创建成功",
                builtin_property={"tool_call_id": "call_4"},
            ),
            ChatPrompt(id="7", role="assistant", content="需求已创建完成。"),
        ]

        builder = ChatAgentBuilder(_make_dummy_chat_ctx())
        filtered = builder._filter_unmatched_tool_calls(chat_history)

        # 前 3 条 assistant 消息(id=2,3,4)的 tool_calls 都没有匹配的结果，应该被过滤
        # id=5 的 assistant 有匹配结果，应该保留
        # 结果: user, assistant(id=5, 有tool_calls且全部匹配), tool, assistant(id=7, 无tool_calls)
        assert len(filtered) == 4, "所有 tool_calls 都没有结果的 assistant 消息应该被过滤"
        # 验证保留的消息
        assert filtered[0].role == "user"
        assert filtered[0].id == "1"
        # id=5 的 assistant 消息有 tool_calls 且全部匹配，应该保留
        assert filtered[1].id == "5", "有完整匹配的 assistant 消息应该保留"
        assert filtered[1].role == "assistant"
        assert filtered[2].role == "tool"
        assert filtered[2].id == "6"
        # id=7 的 assistant 消息没有 tool_calls，应该保留
        assert filtered[3].id == "7", "没有 tool_calls 的 assistant 消息应该保留"
        assert filtered[3].role == "assistant"

    def test_filter_empty_chat_history(self):
        """case 6: 空聊天历史，应该返回空列表"""
        from aidev_agent.services.agent.chat import ChatAgentBuilder

        builder = ChatAgentBuilder(_make_dummy_chat_ctx())
        filtered = builder._filter_unmatched_tool_calls([])

        assert filtered == [], "空聊天历史应该返回空列表"


# =====================================================================
# 取消/暂停场景测试
# =====================================================================


def _run_cancel_in_thread(agent, cancel_signal_fn, wait_signal_fn, cancel_after=0.5, timeout=15.0):
    """辅助函数：在子线程中消费流，满足条件后触发取消，返回 (sse_results, writer_created_contents)

    Args:
        agent: ChatCompletionAgent 实例（需已设置 event_handler=_ConcreteWriter）
        cancel_signal_fn: 取消函数，如 GeneratorStreamingHelper.cancel(thread_id)
        wait_signal_fn: 等待事件，流开始后触发取消
        cancel_after: wait_signal 触发后等待秒数
        timeout: 流结束超时
    """
    writer = agent.event_handler
    results = []
    stream_done = threading.Event()

    def consume():
        for each in agent.execute(ExecuteKwargs(stream=True)):
            results.append(json.loads(each[6:]))
        stream_done.set()

    t = threading.Thread(target=consume)
    t.start()
    wait_signal_fn.wait(timeout=10.0)
    time.sleep(cancel_after)
    cancel_signal_fn()
    stream_done.wait(timeout=timeout)
    t.join(timeout=5.0)
    return results, writer


class TestCancelScenarios:
    """取消场景端到端测试：验证取消后的事件流和 session 回写

    核心场景：
    - 取消 + 无 AI 文本输出（thinking/tool/MCP 等阶段）→ RUN_ERROR → writer 补写"用户已取消"
    - 取消 + 有 AI 文本输出（TEXT_MESSAGE_CONTENT 已出现）→ RUN_FINISHED(cancelled) → writer 正常回写
    - 模型错误 → RUN_ERROR(message=错误信息) → writer 回写错误消息 + error=True
    """

    def test_cancel_without_ai_output(self):
        """取消 + 无 AI 输出（工具调用阶段）→ 流正常结束，writer 补写暂停消息"""
        writer = _ConcreteWriter()
        llm = MockChatModel(
            mock_responses=[
                MockResponse(
                    content="", tool_calls=[{"name": "slow_task", "args": {"seconds": 5.0}, "id": "call_slow"}]
                ),
                MockResponse(content="任务已完成"),
            ],
            stream_chunk_size=2,
            loop=False,
        )
        thread_id = "test_cancel_no_output"
        agent = ChatCompletionAgent(
            thread_id=thread_id,
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="执行一个慢任务")],
            tools=[slow_task],
            event_handler=writer,
        )

        first_event = threading.Event()

        results = []
        stream_done = threading.Event()

        def consume():
            for each in agent.execute(ExecuteKwargs(stream=True)):
                results.append(json.loads(each[6:]))
                if not first_event.is_set():
                    first_event.set()
            stream_done.set()

        t = threading.Thread(target=consume)
        t.start()
        first_event.wait(timeout=10.0)
        time.sleep(0.5)
        GeneratorStreamingHelper.cancel(thread_id)
        stream_done.wait(timeout=15.0)
        t.join(timeout=5.0)

        # 流应有结束事件
        final_events = [r for r in results if r.get("type") in (EventType.RUN_ERROR, EventType.RUN_FINISHED)]
        assert len(final_events) >= 1, "流应有结束事件"
        # writer 应有回写内容或取消标记
        assert writer.is_cancelled or len(writer.created_contents) > 0

    def test_cancel_with_ai_output(self):
        """取消 + 有 AI 输出 → 流正常结束，writer 回写已有内容"""
        writer = _ConcreteWriter()
        llm = MockChatModel(
            mock_responses=[
                MockResponse(content="让我帮你查一下。"),
                MockResponse(
                    content="", tool_calls=[{"name": "slow_task", "args": {"seconds": 5.0}, "id": "call_slow"}]
                ),
                MockResponse(content="查询完成"),
            ],
            stream_chunk_size=2,
            loop=False,
        )
        thread_id = "test_cancel_with_output"
        agent = ChatCompletionAgent(
            thread_id=thread_id,
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="执行一个慢任务")],
            tools=[slow_task],
            event_handler=writer,
        )

        text_started = threading.Event()
        results = []
        stream_done = threading.Event()

        def consume():
            for each in agent.execute(ExecuteKwargs(stream=True)):
                _each = json.loads(each[6:])
                results.append(_each)
                if _each.get("type") == EventType.TEXT_MESSAGE_START and not text_started.is_set():
                    text_started.set()
            stream_done.set()

        t = threading.Thread(target=consume)
        t.start()
        text_started.wait(timeout=10.0)
        time.sleep(0.5)
        GeneratorStreamingHelper.cancel(thread_id)
        stream_done.wait(timeout=15.0)
        t.join(timeout=5.0)

        final_events = [r for r in results if r.get("type") in (EventType.RUN_ERROR, EventType.RUN_FINISHED)]
        assert len(final_events) >= 1, "流应有结束事件"
        assistant_contents = [c for c in writer.created_contents if c.get("role") == PromptRole.ASSISTANT.value]
        assert len(assistant_contents) >= 1

    def test_model_error_writes_error_message(self):
        """模型错误 → RUN_ERROR + writer 回写错误消息 + error=True"""
        writer = _ConcreteWriter()
        llm = MockChatModel(responses=[""], sleep_time=0)

        with patch.object(llm, "_astream", side_effect=Exception("Authentication failed")):
            agent = ChatCompletionAgent(
                chat_model=llm,
                checkpointer=MemorySaver(),
                chat_history=[ChatPrompt(role="user", content="hi")],
                event_handler=writer,
            )
            results = [json.loads(each[6:]) for each in agent.execute(ExecuteKwargs(stream=True))]

        error_events = [r for r in results if r.get("type") == EventType.RUN_ERROR]
        assert len(error_events) >= 1
        assert "Authentication failed" in error_events[0].get("message", "")

        error_contents = [
            c
            for c in writer.created_contents
            if c.get("role") == PromptRole.ASSISTANT.value and c.get("status") == "fail"
        ]
        assert len(error_contents) >= 1
        prop = error_contents[0].get("property", {})
        assert prop.get("builtin_property", {}).get("error") is True
        assert writer.is_cancelled is False

    def test_normal_finish_with_writer(self):
        """回归：正常完成 → writer 回写 status=complete，不设置 _is_cancelled"""
        writer = _ConcreteWriter()
        llm = MockChatModel(responses=["你好，我可以帮你。"], stream_chunk_size=2)
        agent = ChatCompletionAgent(
            chat_model=llm,
            checkpointer=MemorySaver(),
            chat_history=[ChatPrompt(role="user", content="你好")],
            event_handler=writer,
        )
        results = [json.loads(each[6:]) for each in agent.execute(ExecuteKwargs(stream=True))]

        finished_events = [r for r in results if r.get("type") == EventType.RUN_FINISHED]
        assert len(finished_events) >= 1
        assert finished_events[0].get("runId") != RunId.CANCELLED

        assert writer.is_cancelled is False
        assistant_contents = [c for c in writer.created_contents if c.get("role") == PromptRole.ASSISTANT.value]
        assert len(assistant_contents) >= 1
        assert assistant_contents[0].get("status") == "complete"


# =====================================================================
# BaseSessionWriter 取消回写单元测试
# =====================================================================


class TestSessionWriterCancelUnit:
    """BaseSessionWriter 取消/暂停回写逻辑的单元测试

    覆盖 writer 级别的边界场景（不易通过端到端触发）：
    - 取消 + 仅有 thinking/streaming 部分内容 → 补写"用户已取消"
    - 取消 + model_end 已回写 → 不补写暂停消息
    - RUN_FINISHED(cancelled) + 无 AI 输出 → 补写暂停消息
    - 真正运行错误 → 回写错误消息 + builtin_property.error=True
    - 常量一致性
    """

    def test_cancel_error_with_thinking_writes_reasoning_and_paused(self):
        """取消 + thinking 内容 → 回写 reasoning + 补写"用户已取消" + status=fail"""
        writer = _ConcreteWriter()
        writer._thinking_content = "正在深度思考中..."
        writer.handle_run_error(RunErrorEvent(type=EventType.RUN_ERROR, message=RunId.CANCELLED_MESSAGE))

        assert writer.is_cancelled is True
        assert any(c.get("role") == PromptRole.REASONING.value for c in writer.created_contents)
        assert any(
            c.get("role") == PromptRole.ASSISTANT.value
            and c.get("status") == "fail"
            and c.get("content") == "用户已取消"
            for c in writer.created_contents
        )

    def test_cancel_error_no_content_writes_only_paused(self):
        """取消 + 完全无内容 → 仅补写"用户已取消" + status=fail"""
        writer = _ConcreteWriter()
        writer.handle_run_error(RunErrorEvent(type=EventType.RUN_ERROR, message=RunId.CANCELLED_MESSAGE))

        assert len(writer.created_contents) == 1
        assert writer.created_contents[0]["content"] == "用户已取消"
        assert writer.created_contents[0]["status"] == "fail"

    def test_cancel_run_finished_no_output_writes_paused(self):
        """RUN_FINISHED(cancelled) + 无 AI 输出 → 补写"用户已取消"（Flow Agent 任务已启动场景）"""
        writer = _ConcreteWriter()
        writer.handle_run_finished(
            RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="t1", run_id=RunId.CANCELLED)
        )

        assert writer.is_cancelled is True
        assert any(c.get("content") == "用户已取消" and c.get("status") == "fail" for c in writer.created_contents)

    def test_cancel_with_model_end_written_no_paused(self):
        """取消 + model_end 已回写 → 不补写暂停消息（AI 已输出文本场景）"""
        writer = _ConcreteWriter()
        writer._model_end_written = True
        writer.handle_run_finished(
            RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="t1", run_id=RunId.CANCELLED)
        )

        assert not any(c.get("content") == "用户已取消" and c.get("status") == "fail" for c in writer.created_contents)

    def test_real_error_writes_error_with_builtin_flag(self):
        """真正运行错误 → 回写错误消息 + builtin_property.error=True"""
        writer = _ConcreteWriter()
        writer.handle_run_error(RunErrorEvent(type=EventType.RUN_ERROR, message="模型调用异常"))

        assert writer.is_cancelled is False
        error = next(c for c in writer.created_contents if c.get("status") == "fail")
        assert error.get("content") == "模型调用异常"
        assert error.get("property", {}).get("builtin_property", {}).get("error") is True

    def test_normal_finish_thinking_only_writes_empty_assistant(self):
        """回归：正常完成 + 仅有 thinking → 空 assistant(status=complete)，非"用户已取消" """
        writer = _ConcreteWriter()
        writer._thinking_content = "思考过程..."
        writer.handle_run_finished(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id="t1", run_id="run-123"))

        assert any(c.get("role") == PromptRole.REASONING.value for c in writer.created_contents)
        assistant = next(c for c in writer.created_contents if c.get("role") == PromptRole.ASSISTANT.value)
        assert assistant.get("status") == "complete"
        assert assistant.get("content") != "用户已取消"

    def test_constants_consistency(self):
        """PAUSED_CONTENT_MESSAGE 和 RunId.CANCELLED_MESSAGE 应一致为"用户已取消" """
        assert BaseSessionWriter.PAUSED_CONTENT_MESSAGE == RunId.CANCELLED_MESSAGE == "用户已取消"


# ---------------------------------------------------------------------------
# TestAgentFactory2Chat: 验证 AgentFactory → ChatBuilder → ChatCompletionAgent
# 字段映射正确性
# ---------------------------------------------------------------------------


def _build_factory_raw(**overrides) -> dict:
    """构造完整的平台原始数据，模拟 retrieve_agent_config 返回值。"""
    raw = {
        "agent_name": "Factory Test Agent",
        "conversation_settings": {
            "opening_remark": "Hello!",
            "commands": [],
        },
        "prompt_setting": {
            "content": [{"role": "system", "content": "你是一个翻译助手"}],
            "llm_code": "test-llm-v1",
            "non_thinking_llm": "test-llm-lite",
            "llm_token_limit": 28000,
            "max_tokens": 20480,
            "tool_output_compress_thrd": 4096,
            "support_upload": {"vision": True},
            "temperature": 0.7,
        },
        "intent_recognition": {
            "agent_type": "deepseek_r1",
            "knowledges": [],
        },
        "knowledgebase_settings": {
            "knowledgebases": [10, 20],
            "retriever_code": "default_retriever",
            "query_function": "semantic",
            "document_fragment_count": 0,
            "knowledge_resource_fine_grained_score_type": "LLM",
            "knowledge_resource_reject_threshold": [0.5, 0.68],
            "independent_query_mode": "REWRITE",
            "polish": False,
            "origin": True,
            "knowledge_template_id": 1,
            "is_response_when_no_knowledgebase_match": True,
            "rejection_message": "抱歉，无法回答",
        },
        "related_tools": ["tool-a", "tool-b"],
        "related_skills": [{"skill_id": "s1"}],
        "mcp_server_config": {"mcpServers": {}},
    }
    raw.update(overrides)
    return raw


class _FactoryStubRM(BaseResourceManager):
    """Stub resource_manager，mock retrieve_agent_config 和其他 retrieve/construct 方法。"""

    def __init__(self, raw=None):
        super().__init__(app_code="test-code", app_secret="test-secret")
        self._raw = raw or _build_factory_raw()

    def retrieve_agent_config(self, agent_code, version=None, **kwargs):
        return self._raw

    def get_client(self, **kwargs):
        return MagicMock()

    def retrieve_knowledgebase(self, id, **kwargs):
        return {"id": id, "name": f"kb-{id}"}

    def retrieve_knowledge(self, id, **kwargs):
        return {"id": id, "name": f"knowledge-{id}"}

    def construct_tool(self, tool_code, **kwargs):
        mock_tool = MagicMock()
        mock_tool.name = tool_code
        return mock_tool

    def construct_mcp(self, mcp_config, username=None, executor_info=None, **kwargs):
        from aidev_agent.packages.langchain_core.tools.base import McpToolsResult

        return McpToolsResult(tools=[], fetch_failures=[])

    def resolve_access_token(self, username=None):
        return "test-token"


def _build_legacy_agent_config() -> AgentConfig:
    """构造外部旧 resource_manager 可能返回的旧版 AgentConfig。"""
    return AgentConfig.model_validate(
        {
            "agent_code": "legacy-agent",
            "agent_name": "Legacy Agent",
            "chat_model": "test-llm-v1",
            "non_thinking_llm": "test-llm-lite",
            "role_prompts": [{"role": "system", "content": "legacy role"}],
            "knowledgebase_ids": [10],
            "knowledge_ids": [100],
            "tool_codes": [],
            "mcp_server_config": {},
            "related_skills": [],
            "model_context_options_data": {},
            "knowledge_query_options_data": {},
            "agent_options": {
                "intent_recognition_options": {
                    "agent_type": "deepseek_r1",
                    "tool_output_compress_thrd": 4096,
                    "with_index_specific_search_init": False,
                },
                "knowledge_query_options": {
                    "llm_token_limit": 28000,
                    "document_fragment_count": 3,
                    "knowledge_resource_rough_recall_topk": 99,
                    "rejection_message": "旧拒答",
                },
            },
        }
    )


class TestAgentFactory2Chat:
    """验证 AgentFactory 使用 ChatBuilder 后 ChatCompletionAgent 各字段被正确赋值。"""

    @staticmethod
    def _build_agent(raw=None):
        """通过 AgentInstanceFactory.build_agent 构建并返回 ChatCompletionAgent。"""
        from aidev_agent.enums import AgentBuildType
        from aidev_agent.enums import AgentType as AT
        from aidev_agent.services.agent.factory import AgentInstanceFactory

        rm = _FactoryStubRM(raw=raw or _build_factory_raw())
        with patch.object(ChatModel, "get_setup_instance", return_value=MagicMock()):
            agent = AgentInstanceFactory.build_agent(
                agent_code="test-agent",
                agent_type=AT.CHAT,
                build_type=AgentBuildType.DIRECT,
                resource_manager=rm,
                checkpointer=MemorySaver(),
            )

        return agent

    def test_legacy_agent_config_fallback_options_for_builder(self):
        """外部旧 AgentConfig 仅返回 agent_options 时，Builder 应迁移出新配置。"""
        from aidev_agent.enums import AgentType as AT
        from aidev_agent.services.agent.chat import ChatAgentBuilder
        from aidev_agent.services.agent.registry import AgentBuildContext

        ctx = AgentBuildContext(
            agent_code="legacy-agent",
            agent_type=AT.CHAT,
            resource_manager=_FactoryStubRM(),
            agent_config=_build_legacy_agent_config(),
        )
        builder = ChatAgentBuilder(ctx)

        mcs = builder.build_model_context_options()
        kq = builder.build_knowledge_query_options()

        assert isinstance(mcs, ModelContextSettings)
        assert mcs.llm_code_agent_type == "deepseek_r1"
        assert mcs.tool_output_compress_thrd == 4096
        assert mcs.llm_token_limit == 28000
        assert kq.knowledge_resource_rough_recall_topk == 3
        assert kq.rejection_message == "旧拒答"
        assert kq.with_index_specific_search_init is False

    def test_get_agent_uses_migrated_legacy_agent_options(self):
        """migration_v1 后，_get_agent 应向下传新配置且不传旧字段。"""
        agent_cls = MagicMock()
        agent_cls.get_agent_executor.return_value = (MagicMock(), {})
        legacy_config = _build_legacy_agent_config()
        agent = ChatCompletionAgent(
            chat_model=MockChatModel(responses=["hi"]),
            checkpointer=MemorySaver(),
            chat_model_non_thinking=MockChatModel(responses=["hi"]),
            agent_cls=agent_cls,
            agent_options=legacy_config.agent_options,
            knowledge_bases=[{"id": 10}],
            knowledges=[{"id": 100}],
        )
        agent.migration_v1()

        agent._get_agent([HumanMessage(content="hi")], execute_kwargs=ExecuteKwargs())

        kwargs = agent_cls.get_agent_executor.call_args.kwargs
        assert "agent_options" not in kwargs
        assert kwargs["model_context_options"].llm_code_agent_type == "deepseek_r1"
        assert kwargs["model_context_options"].llm_token_limit == 28000
        assert kwargs["knowledge_query_options"].knowledge_resource_rough_recall_topk == 3
        assert kwargs["knowledge_query_options"].knowledge_bases == [{"id": 10}]
        assert kwargs["knowledge_query_options"].knowledge_items == [{"id": 100}]

    def test_execute_migration_v1_handles_legacy_non_thinking_llm_and_agent_options(self):
        """execute 入口应迁移旧 non_thinking_llm 与旧 agent_options。"""
        legacy_config = _build_legacy_agent_config()
        migrated_non_thinking = MockChatModel(responses=["non-thinking"])
        agent = ChatCompletionAgent(
            chat_model=MockChatModel(responses=["hi"]),
            checkpointer=MemorySaver(),
            non_thinking_llm="legacy-lite",
            agent_options=legacy_config.agent_options,
            messages=[HumanMessage(content="hi")],
        )

        with (
            patch.object(ChatModel, "get_setup_instance", return_value=migrated_non_thinking) as mock_setup,
            patch.object(agent, "_execute", return_value="ok") as mock_execute,
        ):
            result = agent.execute(ExecuteKwargs())

        assert result == "ok"
        mock_setup.assert_called_once_with(model="legacy-lite")
        assert agent.chat_model_non_thinking is migrated_non_thinking
        assert agent.model_context_options.llm_code_agent_type == "deepseek_r1"
        assert agent.knowledge_query_options.knowledge_resource_rough_recall_topk == 3
        mock_execute.assert_called_once()

    @pytest.mark.parametrize(
        "prompt_content, expected_role, expected_content",
        [
            # collection 类型：hidden-system → 转为 system
            (
                [{"role": "hidden-system", "content": "你是一个专业的中英文翻译官"}],
                "system",
                "你是一个专业的中英文翻译官",
            ),
            # user_define 类型：system 保持不变
            (
                [{"role": "system", "content": "你是一个人工智能助手"}],
                "system",
                "你是一个人工智能助手",
            ),
        ],
    )
    def test_chat_history_with_role_prompt(self, prompt_content, expected_role, expected_content):
        """role_prompts 中的 hidden-system / system 角色应被正确拼接到 chat_history 头部"""
        raw = _build_factory_raw()
        raw["prompt_setting"]["content"] = prompt_content
        agent = self._build_agent(raw=raw)
        # chat_history 头部应为 role_history 中的系统提示词
        assert len(agent.chat_history) >= 1
        first = agent.chat_history[0]
        assert first.role == expected_role
        assert first.content == expected_content

    def test_chat_model_from_llm_code(self):
        """prompt_setting.llm_code → chat_model（通过 ChatModel.get_setup_instance），同时验证 model_name 和 temperature"""
        captured_calls = []

        def _capture_setup_instance(**kwargs):
            captured_calls.append(kwargs)
            mock_model = MagicMock()
            mock_model.model_name = kwargs.get("model", "")
            return mock_model

        from aidev_agent.enums import AgentBuildType
        from aidev_agent.enums import AgentType as AT
        from aidev_agent.services.agent.factory import AgentInstanceFactory

        rm = _FactoryStubRM(raw=_build_factory_raw())
        with patch.object(ChatModel, "get_setup_instance", side_effect=_capture_setup_instance):
            agent = AgentInstanceFactory.build_agent(
                agent_code="test-agent",
                agent_type=AT.CHAT,
                build_type=AgentBuildType.DIRECT,
                resource_manager=rm,
                checkpointer=MemorySaver(),
            )

        assert agent.chat_model is not None
        # 第一次调用是 build_chat_model
        assert captured_calls[0]["model"] == "test-llm-v1"
        assert captured_calls[0]["temperature"] == 0.7
        assert captured_calls[0]["max_tokens"] == 20480
        assert agent.model_name == "test-llm-v1"

    def test_chat_model_non_thinking_from_prompt_setting(self):
        """prompt_setting.non_thinking_llm → chat_model_non_thinking（通过 ChatModel.get_setup_instance）"""
        captured_calls = []

        def _capture_setup_instance(**kwargs):
            captured_calls.append(kwargs)
            mock_model = MagicMock()
            mock_model.model_name = kwargs.get("model", "")
            return mock_model

        from aidev_agent.enums import AgentBuildType
        from aidev_agent.enums import AgentType as AT
        from aidev_agent.services.agent.factory import AgentInstanceFactory

        rm = _FactoryStubRM(raw=_build_factory_raw())
        with patch.object(ChatModel, "get_setup_instance", side_effect=_capture_setup_instance):
            agent = AgentInstanceFactory.build_agent(
                agent_code="test-agent",
                agent_type=AT.CHAT,
                build_type=AgentBuildType.DIRECT,
                resource_manager=rm,
                checkpointer=MemorySaver(),
            )

        assert agent.chat_model_non_thinking is not None
        # 第二次调用是 build_chat_model_non_thinking
        assert captured_calls[1]["model"] == "test-llm-lite"

    def test_chat_model_non_thinking_fallback_to_chat_model(self):
        """non_thinking_llm 未配置时回退到 llm_code，chat_model_non_thinking 使用主模型"""
        captured_calls = []

        def _capture_setup_instance(**kwargs):
            captured_calls.append(kwargs)
            mock_model = MagicMock()
            mock_model.model_name = kwargs.get("model", "")
            return mock_model

        from aidev_agent.enums import AgentBuildType
        from aidev_agent.enums import AgentType as AT
        from aidev_agent.services.agent.factory import AgentInstanceFactory

        raw = _build_factory_raw()
        raw["prompt_setting"].pop("non_thinking_llm", None)
        rm = _FactoryStubRM(raw=raw)
        with patch.object(ChatModel, "get_setup_instance", side_effect=_capture_setup_instance):
            agent = AgentInstanceFactory.build_agent(
                agent_code="test-agent",
                agent_type=AT.CHAT,
                build_type=AgentBuildType.DIRECT,
                resource_manager=rm,
                checkpointer=MemorySaver(),
            )

        # non_thinking_llm 回退到 llm_code，所以 chat_model_non_thinking 使用主模型
        assert agent.chat_model_non_thinking is not None
        assert captured_calls[1]["model"] == "test-llm-v1"

    def test_model_context_options_fields(self):
        """llm_token_limit / max_tokens / tool_output_compress_thrd → model_context_options"""
        agent = self._build_agent()
        mcs = agent.model_context_options
        assert isinstance(mcs, ModelContextSettings)
        assert mcs.llm_token_limit == 28000
        assert mcs.tool_output_compress_thrd == 4096

    def test_intent_recognition_agent_type_to_llm_code_agent_type(self):
        """intent_recognition.agent_type → model_context_options.llm_code_agent_type"""
        agent = self._build_agent()
        assert agent.model_context_options.llm_code_agent_type == "deepseek_r1"

    def test_support_vision_from_support_upload(self):
        """prompt_setting.support_upload.vision → support_vision"""
        agent = self._build_agent()
        assert agent.support_vision is True

    def test_support_vision_false(self):
        """support_upload.vision=False 时 support_vision 为 False"""
        raw = _build_factory_raw()
        raw["prompt_setting"]["support_upload"] = {"vision": False}
        agent = self._build_agent(raw=raw)
        assert agent.support_vision is False

    def test_knowledge_query_options_from_knowledgebase_settings(self):
        """knowledgebase_settings 相关配置 → knowledge_query_options，document_fragment_count=0 不映射 rough_recall_topk"""
        agent = self._build_agent()
        kq = agent.knowledge_query_options
        assert isinstance(kq, KnowledgeSettings)
        assert kq.is_response_when_no_knowledgebase_match is True
        assert kq.rejection_message == "抱歉，无法回答"
        assert kq.knowledge_resource_fine_grained_score_type.value == "LLM"
        assert kq.knowledge_resource_reject_threshold == (0.5, 0.68)
        assert kq.independent_query_mode.value == "REWRITE"
        assert kq.knowledge_template_id == 1
        assert kq.knowledge_resource_rough_recall_topk == KnowledgeSettings().knowledge_resource_rough_recall_topk

    def test_knowledge_bases_populated(self):
        """knowledgebase_settings.knowledgebases → knowledge_bases（_get_agent 时合并到 knowledge_query_options）"""
        agent = self._build_agent()
        assert len(agent.knowledge_bases) == 2
        assert agent.knowledge_bases[0]["id"] == 10
        assert agent.knowledge_bases[1]["id"] == 20

    def test_related_skills(self):
        """related_skills → skills"""
        agent = self._build_agent()
        assert agent.skills == [{"skill_id": "s1"}]

    def test_tools_from_related_tools(self):
        """related_tools → tools"""
        agent = self._build_agent()
        assert len(agent.tools) == 2


# ---------------------------------------------------------------------------
# TestTerminalResumeReplay: resume 的 graph 已终态时从 checkpoint 重放
# 覆盖三个新增私有方法的核心分支，纯逻辑、不依赖真实 LLM / graph。
# ---------------------------------------------------------------------------

# chat.py 内被 patch 的模块级符号路径
_CHAT_MODULE = "aidev_agent.services.agent.chat"


def _parse_sse(chunk: str) -> dict:
    """解析 EventEncoder().encode(...) 产出的 "data: {json}\\n\\n" 形态。"""
    return json.loads(chunk[len("data: ") :])


def _fake_graph_state(next_nodes=(), interrupts=None, messages=None):
    """构造一个最小的 LangGraph StateSnapshot 替身（仅含被读取的字段）。"""
    task = SimpleNamespace(interrupts=list(interrupts or []))
    return SimpleNamespace(
        next=tuple(next_nodes),
        tasks=[task],
        values={"messages": list(messages or [])},
    )


def _seed_agent() -> ChatCompletionAgent:
    """方法不依赖 self 的运行期状态，用最小种子实例即可。"""
    return ChatCompletionAgent(chat_model=MockChatModel(responses=["x"]), checkpointer=MemorySaver())


def _mock_agui_entry(emit_approval_finished: bool = False) -> MagicMock:
    entry = MagicMock()
    entry._should_emit_resume_approval_finished.return_value = emit_approval_finished
    return entry


class TestTerminalResumeReplay:
    """终态 resume 从 checkpoint 重放的单元测试"""

    # ---------------- _terminal_replay_event_stream ----------------

    def test_replay_event_stream_emits_expected_sequence(self):
        """终态重放应产出 RUN_STARTED → RUN_FINISHED（续流不下发 MESSAGES_SNAPSHOT）"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=False)
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input)]
        types_seq = [e["type"] for e in events]
        assert types_seq == [
            EventType.RUN_STARTED,
            EventType.RUN_FINISHED,
        ]
        # 续流场景不应下发 MESSAGES_SNAPSHOT
        assert EventType.MESSAGES_SNAPSHOT not in types_seq
        run_finished = events[-1]
        assert run_finished["runId"] == "r1"
        assert run_finished["threadId"] == "t1"

    def test_replay_event_stream_run_id_fallback_when_missing(self):
        """agent_input.run_id 缺失时应回退到自动生成的 run_id（RUN_STARTED 与 RUN_FINISHED 一致）"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=False)
        agent_input = SimpleNamespace(thread_id="t1", run_id=None)

        events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input)]
        started = next(e for e in events if e["type"] == EventType.RUN_STARTED)
        finished = next(e for e in events if e["type"] == EventType.RUN_FINISHED)
        assert started["runId"]
        assert started["runId"] == finished["runId"]

    def test_replay_event_stream_prepends_approval_finished(self):
        """审批续流场景应在最前面补一条终态 RUN_FINISHED（更新中断卡片）"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=True)
        agui_entry._build_resume_approval_finished_event.return_value = RunFinishedEvent(
            type=EventType.RUN_FINISHED, thread_id="t1", run_id="approval-run"
        )
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input)]
        types_seq = [e["type"] for e in events]
        assert types_seq == [
            EventType.RUN_FINISHED,  # 审批终态卡片
            EventType.RUN_STARTED,
            EventType.RUN_FINISHED,
        ]
        assert events[0]["runId"] == "approval-run"

    def test_replay_event_stream_swallows_approval_finished_error(self):
        """审批终态事件构造异常时不应中断重放（仍输出 RUN_STARTED/RUN_FINISHED）"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=True)
        agui_entry._build_resume_approval_finished_event.side_effect = RuntimeError("boom")
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input)]
        types_seq = [e["type"] for e in events]
        assert types_seq == [
            EventType.RUN_STARTED,
            EventType.RUN_FINISHED,
        ]

    def test_replay_event_stream_emits_ai_text_message(self):
        """checkpoint 片段含 AIMessage 文本 → 在 RUN_STARTED/RUN_FINISHED 之间补发流式增量事件"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=False)
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")
        replayable = [AIMessage(content="hello world", id="ai-1")]

        events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input, replayable)]
        types_seq = [e["type"] for e in events]
        assert types_seq == [
            EventType.RUN_STARTED,
            EventType.TEXT_MESSAGE_START,
            EventType.TEXT_MESSAGE_CONTENT,
            EventType.TEXT_MESSAGE_END,
            EventType.RUN_FINISHED,
        ]
        # message_id 须保留 DB 原值，前端按 id 合并不会产生新卡片
        text_events = [
            e
            for e in events
            if e["type"]
            in (
                EventType.TEXT_MESSAGE_START,
                EventType.TEXT_MESSAGE_CONTENT,
                EventType.TEXT_MESSAGE_END,
            )
        ]
        assert all(e["messageId"] == "ai-1" for e in text_events)
        content_event = next(e for e in events if e["type"] == EventType.TEXT_MESSAGE_CONTENT)
        assert content_event["delta"] == "hello world"

    def test_replay_event_stream_emits_tool_call_with_args(self):
        """checkpoint 片段含 AIMessage(tool_calls) + ToolMessage → 完整补发 TOOL_CALL_* 三段 + RESULT"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=False)
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")
        replayable = [
            AIMessage(
                content="",
                id="ai-1",
                tool_calls=[{"id": "call-1", "name": "my_tool", "args": {"x": 1}, "type": "tool_call"}],
            ),
            ToolMessage(content="ok", id="tool-1", tool_call_id="call-1"),
        ]

        events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input, replayable)]
        types_seq = [e["type"] for e in events]
        assert types_seq == [
            EventType.RUN_STARTED,
            EventType.TOOL_CALL_START,
            EventType.TOOL_CALL_ARGS,
            EventType.TOOL_CALL_END,
            EventType.TOOL_CALL_RESULT,
            EventType.RUN_FINISHED,
        ]
        # tool_call_id 链路保持一致
        tc_events = [
            e
            for e in events
            if e["type"]
            in (
                EventType.TOOL_CALL_START,
                EventType.TOOL_CALL_ARGS,
                EventType.TOOL_CALL_END,
                EventType.TOOL_CALL_RESULT,
            )
        ]
        assert all(e["toolCallId"] == "call-1" for e in tc_events)
        args_event = next(e for e in events if e["type"] == EventType.TOOL_CALL_ARGS)
        assert json.loads(args_event["delta"]) == {"x": 1}
        result_event = next(e for e in events if e["type"] == EventType.TOOL_CALL_RESULT)
        assert result_event["content"] == "ok"

    def test_replay_event_stream_skips_human_and_system_messages(self):
        """checkpoint 片段中的 Human/System 消息不应下发（前端历史已持有）"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=False)
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")
        replayable = [
            HumanMessage(content="hi", id="u-1"),
            SystemMessage(content="sys", id="s-1"),
            AIMessage(content="reply", id="ai-1"),
        ]

        events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input, replayable)]
        # 只补发 AIMessage 的 TEXT_MESSAGE_* 三段
        types_seq = [e["type"] for e in events]
        assert types_seq == [
            EventType.RUN_STARTED,
            EventType.TEXT_MESSAGE_START,
            EventType.TEXT_MESSAGE_CONTENT,
            EventType.TEXT_MESSAGE_END,
            EventType.RUN_FINISHED,
        ]

    def test_replay_event_stream_swallows_streaming_error(self):
        """checkpoint 转流式事件失败时不应中断 RUN_FINISHED 收尾，前端仍能正常关闭 run"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=False)
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")
        replayable = [AIMessage(content="x", id="ai-1")]

        with patch(
            f"{_CHAT_MODULE}.langchain_messages_to_streaming_events",
            side_effect=RuntimeError("boom"),
        ):
            events = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input, replayable)]

        # 即便补发失败，仍要保证 RUN_STARTED → RUN_FINISHED 的最小骨架
        types_seq = [e["type"] for e in events]
        assert types_seq == [
            EventType.RUN_STARTED,
            EventType.RUN_FINISHED,
        ]

    def test_replay_event_stream_no_replayable_messages_keeps_minimal_sequence(self):
        """replayable_messages 为 None / 空列表 → 退化为最小 RUN_STARTED + RUN_FINISHED 序列"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry(emit_approval_finished=False)
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        # None
        events_none = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input, None)]
        # 空 list
        events_empty = [_parse_sse(e) for e in agent._terminal_replay_event_stream(agui_entry, agent_input, [])]

        for events in (events_none, events_empty):
            assert [e["type"] for e in events] == [
                EventType.RUN_STARTED,
                EventType.RUN_FINISHED,
            ]

    def test_build_replay_returns_stream_when_terminal(self):
        """终态 + 有可重放消息 → 返回可迭代的重放事件流"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry()
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")
        state = _fake_graph_state(messages=[HumanMessage(content="hi", id="1"), AIMessage(content="ok", id="2")])

        with patch(f"{_CHAT_MODULE}.run_coro_sync", return_value=state) as mock_run:
            replay = agent._build_terminal_resume_replay(
                agui_entry, agent_input, MagicMock(), {"configurable": {"thread_id": "session"}}
            )

        assert replay is not None
        events = [_parse_sse(e) for e in replay]
        types_seq = [e["type"] for e in events]
        # 续流重放序列为 RUN_STARTED → RUN_FINISHED，不下发 MESSAGES_SNAPSHOT
        assert EventType.MESSAGES_SNAPSHOT not in types_seq
        assert EventType.RUN_STARTED in types_seq
        assert EventType.RUN_FINISHED in types_seq
        # aget_state 应被调用，且重放查询定位到 agent_input.thread_id
        mock_run.assert_called_once()

    def test_build_replay_uses_agent_input_thread_id_in_cfg(self):
        """aget_state 的 cfg 应把 thread_id 显式指向 agent_input.thread_id"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry()
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")
        agent_e = MagicMock()
        state = _fake_graph_state(messages=[HumanMessage(content="hi", id="1")])

        with patch(f"{_CHAT_MODULE}.run_coro_sync", return_value=state):
            agent._build_terminal_resume_replay(
                agui_entry, agent_input, agent_e, {"configurable": {"thread_id": "session"}}
            )

        replay_cfg = agent_e.aget_state.call_args.args[0]
        assert replay_cfg["configurable"]["thread_id"] == "t1"

    def test_build_replay_returns_none_when_not_terminal(self):
        """graph 仍有 next 节点（未终态）→ 返回 None，由调用方回退正常 astream"""
        agent = _seed_agent()
        state = _fake_graph_state(next_nodes=("agent",), messages=[HumanMessage(content="hi", id="1")])
        with patch(f"{_CHAT_MODULE}.run_coro_sync", return_value=state):
            replay = agent._build_terminal_resume_replay(
                _mock_agui_entry(), SimpleNamespace(thread_id="t1", run_id="r1"), MagicMock(), {}
            )
        assert replay is None

    def test_build_replay_returns_none_when_pending_interrupt(self):
        """终态但首个 task 仍有 pending interrupt → 返回 None"""
        agent = _seed_agent()
        state = _fake_graph_state(
            interrupts=[{"value": "need approval"}], messages=[HumanMessage(content="hi", id="1")]
        )
        with patch(f"{_CHAT_MODULE}.run_coro_sync", return_value=state):
            replay = agent._build_terminal_resume_replay(
                _mock_agui_entry(), SimpleNamespace(thread_id="t1", run_id="r1"), MagicMock(), {}
            )
        assert replay is None

    def test_build_replay_returns_none_when_no_replayable_messages(self):
        """终态但仅有 SystemMessage（无可交付内容）→ 返回 None"""
        agent = _seed_agent()
        state = _fake_graph_state(messages=[SystemMessage(content="sys", id="0")])
        with patch(f"{_CHAT_MODULE}.run_coro_sync", return_value=state):
            replay = agent._build_terminal_resume_replay(
                _mock_agui_entry(), SimpleNamespace(thread_id="t1", run_id="r1"), MagicMock(), {}
            )
        assert replay is None

    def test_build_replay_returns_none_on_aget_state_error(self):
        """aget_state 查询异常 → 吞掉异常并返回 None（回退 astream，不阻断续流）"""
        agent = _seed_agent()
        with patch(f"{_CHAT_MODULE}.run_coro_sync", side_effect=Exception("checkpoint unavailable")):
            replay = agent._build_terminal_resume_replay(
                _mock_agui_entry(), SimpleNamespace(thread_id="t1", run_id="r1"), MagicMock(), {}
            )
        assert replay is None

    # ---------------- _build_resume_aware_producer ----------------

    def test_producer_non_resume_uses_astream(self):
        """非 resume → 直接走正常 astream，不触发 checkpoint 查询（普通新流零行为变化）"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry()
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        with (
            patch.object(agent, "_build_terminal_resume_replay") as mock_replay,
            patch(f"{_CHAT_MODULE}.async_to_sync_generator", return_value=iter(["X"])),
        ):
            producer = agent._build_resume_aware_producer(agui_entry, agent_input, agent_e=None, cfg=None, resume=False)
            out = list(producer)

        assert out == ["X"]
        mock_replay.assert_not_called()
        agui_entry.run.assert_called_once_with(agent_input)

    def test_producer_resume_missing_context_uses_astream(self):
        """resume=True 但缺少 agent_e/cfg → 不查 checkpoint，直接 astream"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry()
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        with (
            patch.object(agent, "_build_terminal_resume_replay") as mock_replay,
            patch(f"{_CHAT_MODULE}.async_to_sync_generator", return_value=iter(["X"])),
        ):
            producer = agent._build_resume_aware_producer(agui_entry, agent_input, agent_e=None, cfg=None, resume=True)
            out = list(producer)

        assert out == ["X"]
        mock_replay.assert_not_called()

    def test_producer_terminal_resume_uses_replay(self):
        """resume=True 且终态 → 走 checkpoint 重放，不再跑 astream"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry()
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        with (
            patch.object(agent, "_build_terminal_resume_replay", return_value=iter(["R1", "R2"])) as mock_replay,
            patch(f"{_CHAT_MODULE}.async_to_sync_generator") as mock_astream,
        ):
            producer = agent._build_resume_aware_producer(
                agui_entry,
                agent_input,
                agent_e=MagicMock(),
                cfg={"configurable": {}},
                resume=True,
            )
            out = list(producer)

        assert out == ["R1", "R2"]
        mock_replay.assert_called_once()
        mock_astream.assert_not_called()

    def test_producer_resume_non_terminal_falls_back_to_astream(self):
        """resume=True 但非终态（replay 返回 None）→ 回退正常 astream"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry()
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        with (
            patch.object(agent, "_build_terminal_resume_replay", return_value=None) as mock_replay,
            patch(f"{_CHAT_MODULE}.async_to_sync_generator", return_value=iter(["X"])),
        ):
            producer = agent._build_resume_aware_producer(
                agui_entry,
                agent_input,
                agent_e=MagicMock(),
                cfg={"configurable": {}},
                resume=True,
            )
            out = list(producer)

        assert out == ["X"]
        mock_replay.assert_called_once()
        agui_entry.run.assert_called_once_with(agent_input)

    def test_producer_is_lazy(self):
        """producer 必须惰性：未被拉取前不应触发 checkpoint 查询或 astream"""
        agent = _seed_agent()
        agui_entry = _mock_agui_entry()
        agent_input = SimpleNamespace(thread_id="t1", run_id="r1")

        with (
            patch.object(agent, "_build_terminal_resume_replay") as mock_replay,
            patch(f"{_CHAT_MODULE}.async_to_sync_generator") as mock_astream,
        ):
            agent._build_resume_aware_producer(
                agui_entry,
                agent_input,
                agent_e=MagicMock(),
                cfg={"configurable": {}},
                resume=True,
            )
            # 仅构造、未迭代

        mock_replay.assert_not_called()
        mock_astream.assert_not_called()
        agui_entry.run.assert_not_called()
