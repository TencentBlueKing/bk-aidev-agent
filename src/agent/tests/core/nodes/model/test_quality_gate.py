# -*- coding: utf-8 -*-

from unittest.mock import Mock, patch

import pytest
from aidev_agent.core.nodes.model.pydantic_models import ModelChainState, ProcessorContext
from aidev_agent.core.nodes.model.quality_gate import (
    QualityGate,
    ResponseRoute,
)
from aidev_agent.core.nodes.model.utils import (
    detect_thinking_exhaustion,
    has_content_after_think_block,
    has_prior_tool_results,
    is_truncated,
    strip_think_blocks,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

# ---------------------------------------------------------------------------
# 测试恢复状态
# ---------------------------------------------------------------------------


class TestModelChainState:
    def test_max_tokens_override_default(self):
        rs = ModelChainState()
        assert rs.max_tokens_override is None

    def test_max_tokens_override_set(self):
        rs = ModelChainState(max_tokens_override=16384)
        assert rs.max_tokens_override == 16384


# ---------------------------------------------------------------------------
# 测试辅助函数
# ---------------------------------------------------------------------------


class TestHelperFunctions:
    @pytest.mark.parametrize(
        "content, expected",
        [
            ("<think>content</think>", ""),
            ("<thinking>deep</thinking>", ""),
            ("<reasoning>logic</reasoning>", ""),
        ],
    )
    def test_strip_think_blocks(self, content, expected):
        assert strip_think_blocks(content) == expected

    def test_has_content_after_think_block(self):
        assert has_content_after_think_block("<think>x</think>visible") is True
        assert has_content_after_think_block("<think>x</think>") is False

    def test_detect_thinking_exhaustion(self):
        assert detect_thinking_exhaustion("<think>lots of thought</think>") is True
        assert detect_thinking_exhaustion("<think>thought</think>answer") is False

    def test_is_truncated(self):
        msg = AIMessage(content="x", response_metadata={"finish_reason": "length"})
        assert is_truncated(msg) is True
        msg2 = AIMessage(content="x", response_metadata={"finish_reason": "stop"})
        assert is_truncated(msg2) is False

    @pytest.mark.parametrize(
        "messages, expected",
        [
            ([ToolMessage(content="r", tool_call_id="1")], True),
            ([HumanMessage(content="hi"), ToolMessage(content="r", tool_call_id="1")], True),
            ([HumanMessage(content="hi")], False),
            ([], False),
            (
                [AIMessage(content="ai"), HumanMessage(content="hi"), ToolMessage(content="r", tool_call_id="1")],
                True,
            ),
            ([ToolMessage(content="r", tool_call_id="1"), HumanMessage(content="hi")], False),
        ],
    )
    def test_has_prior_tool_results(self, messages, expected):
        assert has_prior_tool_results(messages) is expected


# ---------------------------------------------------------------------------
# 测试任务完成度判断（SRE3-6-35B-A3B-nothinking judge）
# ---------------------------------------------------------------------------


def _make_ctx(response, messages=None):
    """构造测试用 ProcessorContext。

    默认关闭 enable_custom_event——测试不在 LangChain run 上下文中，
    dispatch_custom_event 会因无 parent run id 抛 RuntimeError。
    """
    if messages is None:
        messages = [HumanMessage(content="问题")]
    return ProcessorContext(
        state={"messages": messages},
        config=RunnableConfig(),
        messages=messages,
        model_chain_state=ModelChainState(),
        response=response,
        metadata={"enable_custom_event": False},
    )


class TestTaskJudgment:
    """测试 SRE3-6-35B-A3B-nothinking 任务完成度判断。"""

    @pytest.mark.parametrize(
        "judge_response, expect_route",
        [
            ("已完成", ResponseRoute.NORMAL_COMPLETION),
            ("不确定", ResponseRoute.NORMAL_COMPLETION),
            ("未完成", ResponseRoute.RECOVERY_RETRY),
        ],
    )
    def test_judge_routes_by_completion(self, judge_response, expect_route):
        mock_llm = Mock()
        mock_llm.invoke.return_value = AIMessage(content=judge_response)
        gate = QualityGate(judge_llm=mock_llm, enable_judge_response=True)
        response = AIMessage(content="这是回答")
        messages = [HumanMessage(content="用户问题")]
        ctx = _make_ctx(response, messages)
        route = gate.validate_response(ctx)
        assert route == expect_route

    def test_judge_fail_open_on_exception(self):
        mock_llm = Mock()
        mock_llm.invoke.side_effect = RuntimeError("timeout")
        gate = QualityGate(judge_llm=mock_llm, enable_judge_response=True)
        response = AIMessage(content="回答")
        ctx = _make_ctx(response)
        route = gate.validate_response(ctx)
        assert route == ResponseRoute.NORMAL_COMPLETION

    def test_judge_fail_open_when_no_judge_llm(self):
        """judge_llm=None → fail-open（跳过判断，视为已完成）。"""
        gate = QualityGate(judge_llm=None, enable_judge_response=True)
        response = AIMessage(content="回答")
        ctx = _make_ctx(response)
        route = gate.validate_response(ctx)
        assert route == ResponseRoute.NORMAL_COMPLETION

    def test_extract_last_human_input(self):
        gate = QualityGate()
        messages = [
            HumanMessage(content="第一个问题"),
            AIMessage(content="第一个回答"),
            HumanMessage(content="第二个问题"),
        ]
        assert gate._extract_last_human_input(messages) == "第二个问题"

    def test_judge_think_block_stripped(self):
        mock_llm = Mock()
        mock_llm.invoke.return_value = AIMessage(content="已完成")
        gate = QualityGate(judge_llm=mock_llm, enable_judge_response=True)
        think_content = "<think>admiration</think>visible answer"
        response = AIMessage(content=think_content)
        ctx = _make_ctx(response)
        gate.validate_response(ctx)
        # 验证传给判断 LLM 的 HumanMessage 不含 think 块
        call_args = mock_llm.invoke.call_args[0][0]
        human_msg = next(m for m in call_args if isinstance(m, HumanMessage))
        assert "admiration" not in human_msg.content
        assert "visible answer" in human_msg.content


class TestEnableJudgeResponseSwitch:
    """测试 enable_judge_response 开关。"""

    def test_disabled_skips_judgment(self):
        """enable_judge_response=False → 有内容直接 NORMAL_COMPLETION，不调用 judgment LLM。"""
        mock_llm = Mock()
        gate = QualityGate(judge_llm=mock_llm, enable_judge_response=False)
        response = AIMessage(content="回答")
        ctx = _make_ctx(response)
        route = gate.validate_response(ctx)
        assert route == ResponseRoute.NORMAL_COMPLETION
        mock_llm.invoke.assert_not_called()

    def test_enabled_invokes_judgment(self):
        """enable_judge_response=True + judge_llm 已配置 → 有内容时调用 judgment LLM。"""
        mock_llm = Mock()
        mock_llm.invoke.return_value = AIMessage(content="已完成")
        gate = QualityGate(judge_llm=mock_llm, enable_judge_response=True)
        response = AIMessage(content="回答")
        ctx = _make_ctx(response)
        route = gate.validate_response(ctx)
        assert route == ResponseRoute.NORMAL_COMPLETION
        mock_llm.invoke.assert_called_once()


class TestFrontEndDisplayEvents:
    """测试判断 LLM 调用前后的 front_end_display 事件派发。"""

    @patch("aidev_agent.core.nodes.model.quality_gate.conditional_dispatch_custom_event")
    def test_events_dispatched_around_invoke(self, mock_dispatch):
        """invoke 前派发 front_end_display=False，invoke 后派发 front_end_display=True。"""
        mock_llm = Mock()
        mock_llm.invoke.return_value = AIMessage(content="已完成")
        gate = QualityGate(judge_llm=mock_llm, enable_judge_response=True)
        response = AIMessage(content="回答")
        ctx = _make_ctx(response)
        gate.validate_response(ctx)

        # 应该派发 2 次：False（关闭前端显示）→ True（恢复）
        assert mock_dispatch.call_count == 2
        first_call = mock_dispatch.call_args_list[0]
        second_call = mock_dispatch.call_args_list[1]
        assert first_call.args == ("custom_event", {"front_end_display": False})
        assert second_call.args == ("custom_event", {"front_end_display": True})

    @patch("aidev_agent.core.nodes.model.quality_gate.conditional_dispatch_custom_event")
    def test_front_end_display_restored_on_exception(self, mock_dispatch):
        """invoke 抛异常时，finally 仍恢复 front_end_display=True（fail-open）。"""
        mock_llm = Mock()
        mock_llm.invoke.side_effect = RuntimeError("timeout")
        gate = QualityGate(judge_llm=mock_llm, enable_judge_response=True)
        response = AIMessage(content="回答")
        ctx = _make_ctx(response)
        route = gate.validate_response(ctx)

        assert route == ResponseRoute.NORMAL_COMPLETION  # fail-open
        # 仍应派发 2 次：False → True（finally 恢复）
        assert mock_dispatch.call_count == 2
        assert mock_dispatch.call_args_list[-1].args == ("custom_event", {"front_end_display": True})
