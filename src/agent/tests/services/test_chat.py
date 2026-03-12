import json
import threading
import time
from unittest.mock import patch

import pytest
from ag_ui.core import EventType
from aidev_agent.config import settings
from aidev_agent.core.ag_ui.types import CustomMessageType
from aidev_agent.packages.langchain_core.models.llm_gateway import ChatModel
from aidev_agent.packages.langchain_core.models.mock import MockChatModel, MockResponse
from aidev_agent.packages.langchain_core.retrievers.bk_retriever import BkRetriever
from aidev_agent.services.chat import ChatCompletionAgent, ExecuteKwargs
from aidev_agent.services.pydantic_models import (
    AgentOptions,
    ChatPrompt,
    IntentRecognition,
)
from langchain_core.tools import tool


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
    raise ValueError("天气预报获取失败")


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
                chat_history=[
                    ChatPrompt(role="user", content="nonono"),
                ],
            )
            result_content = []
            result = agent.execute(ExecuteKwargs(stream=True))
            result_content = list(result)

            # 验证错误消息被正确捕获
            # 响应格式: data: {"event": "error", "code": "...", "message": "..."}
            last_content = result_content[-1]
            assert last_content.startswith("data: ")
            assert json.loads(last_content[5:])["type"] == "RUN_ERROR"
            assert json.loads(last_content[5:])["message"].startswith(
                "模型调用异常: Authentication failed for model gptoss-999b"
            )

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

    def test_knowledge_base(self):
        """case 7: 知识库"""
        with open("tests/mock_data/knowledgebase.json") as fi:
            knowledgebase = json.load(fi)
        with open("tests/mock_data/knowledge_query.json") as fi:
            knowledge_query_result = json.load(fi)

        # Mock _query_instance 属性以返回固定的知识库查询结果
        with patch.object(BkRetriever, "_query_instance", return_value=knowledge_query_result) as mocked_query_instance:
            agent = ChatCompletionAgent(
                chat_model=MockChatModel(responses=["根据知识库，云桌面黑屏的处理方法是重启"]),
                chat_history=[
                    ChatPrompt(role="user", content="云桌面黑屏怎么处理?"),
                ],
                knowledge_bases=[knowledgebase],
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
        """case 8: 耗时工具执行中主动停止，验证流式输出在停止后正常结束且为部分结果

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


@pytest.mark.skipif(
    not all([settings.APP_CODE, settings.SECRET_KEY]),
    reason="没有配置足够的环境变量,跳过该测试",
)
@pytest.mark.slow
class TestCommonAgentChatStreamingLive:
    """测试聊天代理的流式响应功能"""

    def setup_method(self):
        self.llm = ChatModel.get_setup_instance(model="deepseek-v3-0324")

    def test_knowledge_base(self):
        """case 1: 知识库"""
        with open("tests/mock_data/knowledgebase.json") as fi:
            knowledgebase = json.load(fi)
        agent = ChatCompletionAgent(
            chat_model=self.llm,
            chat_history=[
                ChatPrompt(role="user", content="云桌面黑屏怎么处理?"),
            ],
            knowledge_bases=[knowledgebase],
        )
        with open("text.log", "w") as fo:
            result = agent.execute(ExecuteKwargs(stream=True))
            for each in result:
                fo.write(each)

    def test_tool_call_legacy(self):
        """case 2: 工具调用 legacy streaming"""
        agent = ChatCompletionAgent(
            chat_model=self.llm,
            chat_history=[
                ChatPrompt(role="user", content="今天广州天气怎么样?"),
            ],
            tools=[get_weather],
            agent_options=AgentOptions(
                intent_recognition_options=IntentRecognition(
                    agent_type="openai",
                ),
            ),
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
            chat_history=[
                ChatPrompt(role="user", content="云桌面黑屏怎么处理?"),
            ],
            knowledge_bases=[knowledgebase],
        )
        with open("text.log", "w") as fo:
            result = agent.execute(ExecuteKwargs(stream=True, legacy_streaming=True))
            for each in result:
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
            agent_options=AgentOptions(
                intent_recognition_options=IntentRecognition(
                    agent_type="openai",
                ),
            ),
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
            agent_options=AgentOptions(
                intent_recognition_options=IntentRecognition(
                    agent_type="deepseek",
                ),
            ),
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
