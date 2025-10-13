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
from unittest.mock import Mock

import pytest
from aidev_agent.core.extend.agent.qa import (
    CommonQAStreamingMixIn,
    StructuredChatCommonQAAgent,
    ToolCallingCommonQAAgent,
)
from aidev_agent.enums import StreamEventType
from aidev_agent.utils import Empty
from langchain_core.messages import AIMessageChunk


class MockAgent:
    """模拟 Agent 用于测试"""

    def stream_events(self, input_, config=None, version="v2", timeout=2):
        """模拟 stream_events 方法"""


class TestCommonQAStreamingMixIn:
    """测试 CommonQAStreamingMixIn 的 stream_standard_event 方法"""

    @pytest.fixture
    def mock_tool_calling_agent(self):
        """创建一个 mock 的 ToolCallingCommonQAAgent 实例"""
        agent = Mock(spec=ToolCallingCommonQAAgent)
        agent.LOADING_AGENT_MESSAGE = "正在思考..."
        agent.think_symbols = ["<think>\n", "\n</think>\n"]
        agent.final_answer_prefixes = ["Final Answer:", "最终答案："]
        agent.final_answer_suffixes = ["\n```\n", "\n```"]
        agent.end_content = "<｜end▁of▁sentence｜>"
        agent.llm = Mock()
        agent._yield_ret = CommonQAStreamingMixIn._yield_ret.__get__(agent, type(agent))
        agent.check_and_append = CommonQAStreamingMixIn.check_and_append.__get__(agent, type(agent))
        agent.common_filter = CommonQAStreamingMixIn.common_filter.__get__(agent, type(agent))
        agent.cache_filter = CommonQAStreamingMixIn.cache_filter.__get__(agent, type(agent))
        agent.stream_standard_event = CommonQAStreamingMixIn.stream_standard_event.__get__(agent, type(agent))
        return agent

    @pytest.fixture
    def mock_structured_chat_agent(self):
        """创建一个 mock 的 StructuredChatCommonQAAgent 实例"""
        agent = Mock(spec=StructuredChatCommonQAAgent)
        agent.LOADING_AGENT_MESSAGE = "正在思考..."
        agent.think_symbols = ["<think>\n", "\n</think>\n"]
        agent.final_answer_prefixes = ["Final Answer:", "最终答案："]
        agent.final_answer_suffixes = ["\n```\n", "\n```"]
        agent.end_content = "<｜end▁of▁sentence｜>"
        agent.llm = Mock()
        agent._yield_ret = CommonQAStreamingMixIn._yield_ret.__get__(agent, type(agent))
        agent.check_and_append = CommonQAStreamingMixIn.check_and_append.__get__(agent, type(agent))
        agent.common_filter = CommonQAStreamingMixIn.common_filter.__get__(agent, type(agent))
        agent.cache_filter = CommonQAStreamingMixIn.cache_filter.__get__(agent, type(agent))
        agent.stream_standard_event = CommonQAStreamingMixIn.stream_standard_event.__get__(agent, type(agent))
        return agent

    def test_loading_event_type(self, mock_tool_calling_agent):
        """测试 LOADING 事件类型（通过 Empty 触发）"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            yield Empty
            yield Empty
            # 添加一个正常的内容以确保流程完整
            chunk = AIMessageChunk(content="完成")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 验证产生了 LOADING 消息（在 data: 格式的字符串中）
        loading_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("content") == "正在思考...":
                    loading_events.append(data)

        assert len(loading_events) >= 1

    def test_text_event_type_tool_calling(self, mock_tool_calling_agent):
        """测试 TEXT 事件类型（ToolCallingCommonQAAgent）"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟普通文本内容
            chunk = AIMessageChunk(content="这是一个测试回答")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        text_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.TEXT.value:
                    text_events.append(data)

        assert len(text_events) > 0
        assert any("测试回答" in e.get("content", "") for e in text_events)

    def test_think_event_type_tool_calling(self, mock_tool_calling_agent):
        """测试 THINK 事件类型（ToolCallingCommonQAAgent - reasoning_content）"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟 reasoning_content
            chunk = AIMessageChunk(content="", additional_kwargs={"reasoning_content": "让我思考一下..."})
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "run_id": "test_run_1",
            }
            # 模拟最终答案
            chunk2 = AIMessageChunk(content="最终答案")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk2},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        think_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value:
                    think_events.append(data)

        assert len(think_events) > 0
        assert any("思考" in e.get("content", "") for e in think_events)

    def test_think_event_type_tool_call(self, mock_tool_calling_agent):
        """测试 THINK 事件类型（ToolCallingCommonQAAgent - tool_call）"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟工具调用 - 工具名称
            chunk1 = AIMessageChunk(content="", tool_call_chunks=[{"name": "weather_query"}])
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk1},
                "run_id": "test_run_1",
            }
            # 模拟工具调用 - 参数
            chunk2 = AIMessageChunk(content="", tool_call_chunks=[{"args": '{"city": "深圳"}'}])
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk2},
                "run_id": "test_run_1",
            }
            # 模拟工具调用结束
            yield {
                "event": "on_tool_end",
                "data": {"output": "深圳今天晴天，温度25度"},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        think_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value:
                    think_events.append(data)

        assert len(think_events) > 0
        # 验证包含工具调用相关内容
        all_content = "".join(e.get("content", "") for e in think_events)
        assert "weather_query" in all_content or "Agent Action" in all_content

    def test_reference_doc_event_type(self, mock_tool_calling_agent):
        """测试 REFERENCE_DOC 事件类型"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟 reference_doc 自定义事件
            yield {
                "event": "on_custom_event",
                "data": {
                    "reference_doc": [
                        {"file_path": "/path/to/doc1.txt", "score": 0.95},
                        {"file_path": "/path/to/doc2.txt", "score": 0.88},
                    ]
                },
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        reference_doc_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.REFERENCE_DOC.value:
                    reference_doc_events.append(data)

        assert len(reference_doc_events) > 0
        assert "documents" in reference_doc_events[0]
        assert len(reference_doc_events[0]["documents"]) == 2

    def test_done_event_type(self, mock_tool_calling_agent):
        """测试 DONE 事件类型"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            chunk = AIMessageChunk(content="测试完成")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 验证最后一个事件是 DONE
        assert results[-1] == "data: [DONE]\n\n"

        # 验证倒数第二个事件包含 DONE event type
        done_events = []
        for r in results[:-1]:
            if r.startswith("data: "):
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.DONE.value:
                    done_events.append(data)

        assert len(done_events) > 0

    def test_error_event_type(self, mock_tool_calling_agent):
        """测试 ERROR 事件类型（通过异常触发）"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟抛出异常
            raise RuntimeError("测试错误")

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 验证产生了错误事件
        error_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.ERROR.value:
                    error_events.append(data)

        assert len(error_events) > 0

    def test_custom_event_compress_log(self, mock_tool_calling_agent):
        """测试自定义事件 - compress_log"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_custom_event",
                "data": {"compress_log": "Token 超限，尝试压缩..."},
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        think_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value:
                    think_events.append(data)

        assert len(think_events) > 0
        assert any("压缩" in e.get("content", "") for e in think_events)

    def test_custom_event_intent_recognition(self, mock_tool_calling_agent):
        """测试自定义事件 - intent_recognition_result"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_custom_event",
                "data": {"intent_recognition_result": "识别到用户意图：查询天气"},
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        think_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value:
                    think_events.append(data)

        assert len(think_events) > 0
        assert any("意图" in e.get("content", "") for e in think_events)

    def test_custom_event_custom_return_chunk(self, mock_tool_calling_agent):
        """测试自定义事件 - custom_return_chunk"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_custom_event",
                "data": {"custom_return_chunk": "自定义返回内容"},
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        text_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.TEXT.value:
                    text_events.append(data)

        assert len(text_events) > 0
        assert any("自定义返回内容" in e.get("content", "") for e in text_events)

    def test_custom_event_custom_agent_finish(self, mock_tool_calling_agent):
        """测试自定义事件 - custom_agent_finish"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            yield {
                "event": "on_custom_event",
                "data": {"custom_agent_finish": "Agent 执行完成"},
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        text_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.TEXT.value:
                    text_events.append(data)

        assert len(text_events) > 0
        assert any("完成" in e.get("content", "") for e in text_events)

    def test_front_end_display_control(self, mock_tool_calling_agent):
        """测试 front_end_display 控制"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 关闭前端显示
            yield {
                "event": "on_custom_event",
                "data": {"front_end_display": False},
            }
            # 这条消息不应该被显示
            chunk = AIMessageChunk(content="不应该显示的内容")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "run_id": "test_run_1",
            }
            # 重新开启前端显示
            yield {
                "event": "on_custom_event",
                "data": {"front_end_display": True},
            }
            # 这条消息应该被显示
            chunk2 = AIMessageChunk(content="应该显示的内容")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk2},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        all_content = ""
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.TEXT.value:
                    all_content += data.get("content", "")

        assert "不应该显示的内容" not in all_content
        assert "应该显示的内容" in all_content

    def test_structured_chat_final_answer(self, mock_structured_chat_agent):
        """测试 StructuredChatCommonQAAgent 的 Final Answer 处理"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟思考过程
            chunk1 = AIMessageChunk(content="让我思考一下...")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk1},
                "run_id": "test_run_1",
            }
            # 模拟 Final Answer 前缀
            chunk2 = AIMessageChunk(content="Final Answer:")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk2},
                "run_id": "test_run_1",
            }
            # 模拟最终答案
            chunk3 = AIMessageChunk(content="这是最终答案")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk3},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_structured_chat_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        think_events = []
        text_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value:
                    think_events.append(data)
                elif data.get("event") == StreamEventType.TEXT.value:
                    text_events.append(data)

        # 验证思考过程和最终答案分离
        assert len(think_events) > 0
        assert len(text_events) > 0

    def test_tool_output_error_handling(self, mock_tool_calling_agent):
        """测试工具输出错误处理"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟工具调用错误
            yield {
                "event": "on_tool_end",
                "data": {"output": "invalid_tool is not a valid tool, try one of [tool1, tool2]"},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果
        think_events = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value:
                    think_events.append(data)

        assert len(think_events) > 0
        all_content = "".join(e.get("content", "") for e in think_events)
        assert "工具调用失败" in all_content or "invalid_tool" in all_content

    def test_skip_thought_parameter(self, mock_tool_calling_agent):
        """测试 skip_thought 参数

        注意：skip_thought=True 时，会跳过所有 on_chat_model_stream 事件的处理，
        因此这个测试主要验证 skip_thought 参数的存在性和基本功能。
        """
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟 reasoning_content（应该被跳过）
            chunk = AIMessageChunk(content="", additional_kwargs={"reasoning_content": "思考内容"})
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "run_id": "test_run_1",
            }
            # 模拟文本内容（也会被跳过，因为 skip_thought=True）
            chunk2 = AIMessageChunk(content="文本内容")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk2},
                "run_id": "test_run_1",
            }
            # 模拟自定义事件（不会被跳过）
            yield {
                "event": "on_custom_event",
                "data": {"custom_return_chunk": "自定义内容"},
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        # 使用 skip_thought=True
        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_, skip_thought=True))

        # 解析结果
        think_events = []
        text_events = []
        done_events = []
        for r in results:
            if r == "data: [DONE]\n\n":
                continue
            if r.startswith("data: "):
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value:
                    think_events.append(data)
                elif data.get("event") == StreamEventType.TEXT.value:
                    text_events.append(data)
                elif data.get("event") == StreamEventType.DONE.value:
                    done_events.append(data)

        # 验证 on_chat_model_stream 的思考内容被跳过
        assert len(think_events) == 0
        # 验证自定义事件的文本内容被保留，或至少有 DONE 事件
        assert len(text_events) > 0 or len(done_events) > 0

    def test_elapsed_time_in_think_event(self, mock_tool_calling_agent):
        """测试 THINK 事件中的 elapsed_time"""
        mock_agent_e = MockAgent()

        def mock_stream_events(*args, **kwargs):
            # 模拟 reasoning_content
            chunk = AIMessageChunk(content="", additional_kwargs={"reasoning_content": "思考中..."})
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "run_id": "test_run_1",
            }
            # 模拟切换到文本内容
            chunk2 = AIMessageChunk(content="答案")
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk2},
                "run_id": "test_run_1",
            }

        mock_agent_e.stream_events = mock_stream_events

        cfg = {}
        input_ = {"input": "test"}

        results = list(mock_tool_calling_agent.stream_standard_event(mock_agent_e, cfg, input_))

        # 解析结果，查找带 elapsed_time 的 think event
        think_events_with_time = []
        for r in results:
            if r.startswith("data: ") and r != "data: [DONE]\n\n":
                data = json.loads(r[6:])
                if data.get("event") == StreamEventType.THINK.value and "elapsed_time" in data:
                    think_events_with_time.append(data)

        # 验证存在带 elapsed_time 的 think event
        assert len(think_events_with_time) > 0
        assert think_events_with_time[0]["elapsed_time"] >= 0
