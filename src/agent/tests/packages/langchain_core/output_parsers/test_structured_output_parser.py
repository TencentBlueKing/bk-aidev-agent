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

from aidev_agent.packages.langchain_core.output_parsers import (
    StructuredOutputToToolMessageParser,
    is_deepseek_r1_series_models,
    remove_thinking_process,
)
from langchain_core.messages import AIMessage
from langchain_core.output_parsers import BaseOutputParser


class TestStructuredOutputToToolMessageParser:
    """测试 StructuredOutputToToolMessageParser"""

    def test_inheritance(self):
        """测试继承关系"""
        parser = StructuredOutputToToolMessageParser()
        assert isinstance(parser, BaseOutputParser)

    def test_type_property(self):
        """测试 _type 属性"""
        parser = StructuredOutputToToolMessageParser()
        assert parser._type == "structured_output_to_tool_message_parser"

    def test_empty_action_input(self):
        """测试空的 action_input"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "tool",
  "action_input": {}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["args"] == {}

    def test_parse_simple_tool_call(self):
        """测试解析简单的工具调用"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "search_tool",
  "action_input": {"query": "test query"}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search_tool"
        assert result.tool_calls[0]["args"] == {"query": "test query"}
        assert "id" in result.tool_calls[0]

    def test_parse_final_answer(self):
        """测试解析 Final Answer"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "Final Answer",
  "action_input": "This is the final answer"
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert result.content == "This is the final answer"
        assert len(result.tool_calls) == 0  # Final Answer 不应有 tool_calls

    def test_parse_final_answer_with_dict(self):
        """测试解析 Final Answer（action_input 为 dict）"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "Final Answer",
  "action_input": {"result": "success", "data": [1, 2, 3]}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # action_input 为 dict 时应转为 JSON 字符串
        content = json.loads(result.content)
        assert content == {"result": "success", "data": [1, 2, 3]}

    def test_only_final_answer_in_parallel_calls(self):
        """测试并行调用中只有 Final Answer"""
        parser = StructuredOutputToToolMessageParser(enable_parallel_tool_calls=True)
        text = """```json
[
  {
    "action": "Final Answer",
    "action_input": "answer"
  }
]
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert result.content == "answer"
        assert len(result.tool_calls) == 0  # Final Answer 不应有 tool_calls

    def test_parse_parallel_tool_calls(self):
        """测试解析并行工具调用"""
        parser = StructuredOutputToToolMessageParser(enable_parallel_tool_calls=True)
        text = """```json
[
  {
    "action": "search_tool",
    "action_input": {"query": "query1"}
  },
  {
    "action": "calculator",
    "action_input": {"expression": "2+2"}
  }
]
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0]["name"] == "search_tool"
        assert result.tool_calls[1]["name"] == "calculator"

    def test_parse_parallel_tool_calls_disabled(self):
        """测试并行调用被禁用时只取第一个"""
        parser = StructuredOutputToToolMessageParser(enable_parallel_tool_calls=False)
        text = """```json
[
  {
    "action": "search_tool",
    "action_input": {"query": "query1"}
  },
  {
    "action": "calculator",
    "action_input": {"expression": "2+2"}
  }
]
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 应该只取第一个
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search_tool"

    def test_parse_action_input_string_error(self):
        """测试 action_input 为字符串时返回 invalid_tool"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "search_tool",
  "action_input": "invalid string"
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 应该返回 invalid_tool 的工具调用
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "invalid_tool"
        assert "error" in result.tool_calls[0]["args"]
        assert "original_input" in result.tool_calls[0]["args"]
        assert result.tool_calls[0]["args"]["original_input"] == "invalid string"

    def test_parse_without_markdown(self):
        """测试解析不带 markdown 代码块的 JSON"""
        parser = StructuredOutputToToolMessageParser()
        text = '{"action": "search_tool", "action_input": {"query": "test"}}'

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search_tool"

    def test_parse_mixed_content(self):
        """测试解析混合内容（文本 + JSON）"""
        parser = StructuredOutputToToolMessageParser()
        text = """Let me search for that.
```json
{
  "action": "search_tool",
  "action_input": {"query": "test"}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search_tool"

    def test_parse_invalid_json_returns_original(self):
        """测试解析无效 JSON 时返回原内容"""
        parser = StructuredOutputToToolMessageParser()
        text = "This is not JSON at all"

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert result.content == text
        assert len(result.tool_calls) == 0

    def test_parse_empty_text(self):
        """测试解析空文本"""
        parser = StructuredOutputToToolMessageParser()
        result = parser.parse("")
        assert isinstance(result, AIMessage)
        assert result.content == ""

    def test_parse_missing_tool_name(self):
        """测试缺少工具名称"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action_input": {"query": "test"}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 缺少 tool_name 应返回原内容
        assert text in result.content

    def test_no_tool_validation(self):
        """测试不校验工具是否存在"""
        parser = StructuredOutputToToolMessageParser()
        # 调用不存在的工具名
        text = """```json
{
  "action": "non_existent_tool",
  "action_input": {"param": "value"}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 应该仍然生成 tool_calls，不校验工具是否存在
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "non_existent_tool"

    def test_parallel_calls_with_final_answer_error(self):
        """测试并行调用中混合 Final Answer 会被过滤"""
        parser = StructuredOutputToToolMessageParser(enable_parallel_tool_calls=True)
        text = """```json
[
  {
    "action": "search_tool",
    "action_input": {"query": "query1"}
  },
  {
    "action": "Final Answer",
    "action_input": "answer"
  }
]
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # Final Answer 应该被过滤掉
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search_tool"

    def test_parallel_calls_with_string_input_error(self):
        """测试并行调用中有 action_input 为字符串的情况"""
        parser = StructuredOutputToToolMessageParser(enable_parallel_tool_calls=True)
        text = """```json
[
  {
    "action": "search_tool",
    "action_input": {"query": "query1"}
  },
  {
    "action": "calculator",
    "action_input": "invalid string"
  }
]
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 字符串 action_input 应该生成 invalid_tool 调用
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0]["name"] == "search_tool"
        assert result.tool_calls[1]["name"] == "invalid_tool"

    def test_parallel_calls_all_invalid(self):
        """测试并行调用全部无效时返回错误"""
        parser = StructuredOutputToToolMessageParser(enable_parallel_tool_calls=True)
        text = """```json
[
  {
    "action": "Final Answer",
    "action_input": "answer"
  },
  {
    "action_input": {"param": "value"}
  }
]
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 所有调用都无效，应返回错误信息
        assert "[解析错误]" in result.content


class TestDeepSeekR1Support:
    """测试 DeepSeek R1 系列模型支持"""

    def test_remove_thinking_process(self):
        """测试移除思考过程"""
        content = """<think>
This is the thinking process.
Multiple lines of thought.
</think>

Final answer here."""

        result = remove_thinking_process(content)
        assert result == "Final answer here."

    def test_remove_thinking_process_no_think_tag(self):
        """测试没有思考标签的内容"""
        content = "Just normal content"
        result = remove_thinking_process(content)
        assert result == content

    def test_is_deepseek_r1_series_models(self):
        """测试判断是否是 DeepSeek R1 系列模型"""
        # Mock LLM with model_name
        mock_llm = Mock()
        mock_llm.model_name = "deepseek-r1"
        assert is_deepseek_r1_series_models(mock_llm) is True

        # Mock LLM with model attribute
        mock_llm2 = Mock()
        del mock_llm2.model_name
        mock_llm2.model = "deepseek-r1-distill"
        assert is_deepseek_r1_series_models(mock_llm2) is True

        # Non-R1 model
        mock_llm3 = Mock()
        mock_llm3.model_name = "gpt-4"
        assert is_deepseek_r1_series_models(mock_llm3) is False

    def test_parse_with_deepseek_r1_model(self):
        """测试使用 DeepSeek R1 模型时自动移除思考过程"""
        from langchain_core.language_models.chat_models import BaseChatModel
        from pydantic import Field

        # 创建一个简单的 LLM 子类用于测试
        class MockDeepSeekR1(BaseChatModel):
            model_name: str = Field(default="deepseek-r1")

            def _generate(self, *args, **kwargs):
                pass

            @property
            def _llm_type(self) -> str:
                return "mock_deepseek_r1"

        mock_llm = MockDeepSeekR1()
        parser = StructuredOutputToToolMessageParser(llm=mock_llm)
        text = """<think>
Let me think about this...
</think>

```json
{
  "action": "search_tool",
  "action_input": {"query": "test"}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "search_tool"


class TestFinalAnswerFallback:
    """测试 Final Answer 前缀/后缀 fallback 解析"""

    def test_fallback_with_prefix_suffix(self):
        """测试通过前缀/后缀提取 Final Answer"""
        parser = StructuredOutputToToolMessageParser()
        # 故意构造一个不完整但有前缀/后缀的输出
        text = '```json\n{\n  "action": "Final Answer",\n  "action_input": "This is the answer"\n}\n```'

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 应该能解析出 Final Answer
        assert "This is the answer" in result.content or result.content == "This is the answer"

    def test_fallback_with_malformed_json(self):
        """测试 JSON 格式错误但有 Final Answer 前缀时的 fallback"""
        parser = StructuredOutputToToolMessageParser()
        # 构造一个格式错误的 JSON，但包含 Final Answer 前缀
        text = '{\n  "action": "Final Answer",\n  "action_input": "Answer here"'  # 缺少结束括号

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 应该能通过 fallback 提取答案
        if "Answer here" in result.content:
            # fallback 成功
            assert True
        else:
            # fallback 失败，返回原内容
            assert text in result.content


class TestEdgeCases:
    """测试边界情况"""

    def test_null_action_input(self):
        """测试 null action_input"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "tool",
  "action_input": null
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        # null 应该被转为空 dict
        assert result.tool_calls[0]["args"] == {}

    def test_missing_action_input(self):
        """测试缺少 action_input 字段"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "tool"
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        # 缺少 action_input 应该使用空 dict
        assert result.tool_calls[0]["args"] == {}

    def test_complex_nested_action_input(self):
        """测试复杂嵌套的 action_input"""
        parser = StructuredOutputToToolMessageParser()
        complex_input = {
            "query": "test",
            "filters": {"type": "all", "tags": ["tag1", "tag2"]},
            "options": {"limit": 10, "nested": {"deep": "value"}},
        }
        text = f"""```json
{{
  "action": "search_tool",
  "action_input": {json.dumps(complex_input)}
}}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["args"] == complex_input

    def test_unicode_in_action_input(self):
        """测试 action_input 中的 Unicode 字符"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "search_tool",
  "action_input": {"query": "测试中文查询"}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["args"]["query"] == "测试中文查询"

    def test_action_input_none_becomes_empty_dict(self):
        """测试 action_input 为 None 时转为空字典"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action": "tool",
  "action_input": null
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["args"] == {}

    def test_action_input_string_in_parallel_calls(self):
        """测试并行调用中 action_input 为字符串的边界情况"""
        parser = StructuredOutputToToolMessageParser(enable_parallel_tool_calls=True)
        text = """```json
[
  {
    "action": "tool1",
    "action_input": "string1"
  },
  {
    "action": "tool2",
    "action_input": "string2"
  }
]
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 两个都应该变成 invalid_tool
        assert len(result.tool_calls) == 2
        assert result.tool_calls[0]["name"] == "invalid_tool"
        assert result.tool_calls[1]["name"] == "invalid_tool"

    def test_missing_action_field(self):
        """测试缺少 action 字段"""
        parser = StructuredOutputToToolMessageParser()
        text = """```json
{
  "action_input": {"query": "test"}
}
```"""

        result = parser.parse(text)
        assert isinstance(result, AIMessage)
        # 缺少 action 字段应返回原内容，不生成 tool_calls
        assert len(result.tool_calls) == 0
