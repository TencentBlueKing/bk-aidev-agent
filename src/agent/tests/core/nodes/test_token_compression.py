# -*- coding: utf-8 -*-
"""测试 Token 压缩中间件。"""

from unittest.mock import MagicMock, patch

import pytest
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.core.nodes.model.token_compression import (
    _KNOWLEDGE_COMMON_COMPRESSOR_USR_PROMPT,
    _TOOL_OUTPUT_SPECIFIC_COMPRESSOR_SYS_PROMPT,
    _TOOL_OUTPUT_SPECIFIC_COMPRESSOR_USR_PROMPT,
    BaseCompressionMiddleware,
    ChatHistoryCompressionMiddleware,
    CompressionState,
    KnowledgeCompressionMiddleware,
    ToolOutputLengthCompressionMiddleware,
    ToolOutputTokenCompressionMiddleware,
    _ensure_compression_state,
)
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage


# ============================================================================
# CompressionState 测试
# ============================================================================
class TestCompressionState:
    def test_default_values(self):
        state = CompressionState()
        assert state.knowledge_hash is None
        assert state.knowledge_cache is None
        assert state.knowledge_compressed is False
        assert state.tool_output_compressed is False
        assert state.tool_output_compressed_ids == set()
        assert state.chat_history_removed == 0

    def test_from_legacy_with_old_keys(self):
        raw = {
            "context_compressed": True,
            "chat_history_compression_count": 5,
            "knowledge_hash": "abc123",
        }
        state = CompressionState.from_legacy(raw)
        assert state.knowledge_compressed is True
        assert state.chat_history_removed == 5
        assert state.knowledge_hash == "abc123"

    def test_from_legacy_with_new_keys(self):
        raw = {
            "knowledge_compressed": True,
            "chat_history_removed": 3,
            "tool_output_compressed": True,
            "tool_output_compressed_ids": ["id1", "id2"],
        }
        state = CompressionState.from_legacy(raw)
        assert state.knowledge_compressed is True
        assert state.chat_history_removed == 3
        assert state.tool_output_compressed is True
        assert state.tool_output_compressed_ids == {"id1", "id2"}


class TestEnsureCompressionState:
    def test_creates_new_state_if_missing(self):
        ctx = ProcessorContext(state={}, config={}, metadata={})
        state = _ensure_compression_state(ctx)
        assert isinstance(state, CompressionState)
        assert ctx.metadata["_compression_state"] is state

    def test_returns_existing_state(self):
        existing = CompressionState(knowledge_compressed=True)
        ctx = ProcessorContext(state={}, config={}, metadata={"_compression_state": existing})
        state = _ensure_compression_state(ctx)
        assert state is existing

    def test_migrates_legacy_dict(self):
        ctx = ProcessorContext(state={}, config={}, metadata={"_compression_state": {"context_compressed": True}})
        state = _ensure_compression_state(ctx)
        assert isinstance(state, CompressionState)
        assert state.knowledge_compressed is True


# ============================================================================
# BaseCompressionMiddleware 测试
# ============================================================================
class TestBaseCompressionMiddleware:
    def test_is_overflow_returns_false_when_no_limit(self):
        middleware = BaseCompressionMiddleware(token_limit=None)
        ctx = ProcessorContext(state={}, config={})
        assert middleware._is_overflow(ctx) is False

    def test_is_overflow_returns_false_when_under_limit(self):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 500

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        middleware = BaseCompressionMiddleware(token_limit=1000, token_margin=100)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={},
        )
        assert middleware._is_overflow(ctx) is False

    def test_is_overflow_returns_true_when_over_limit(self):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 950

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        middleware = BaseCompressionMiddleware(token_limit=1000, token_margin=100)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={},
        )
        # 950 > 1000 - 100 = 900
        assert middleware._is_overflow(ctx) is True


# ============================================================================
# KnowledgeCompressionMiddleware 测试
# ============================================================================
class TestKnowledgeCompressionMiddleware:
    def test_skips_when_no_context(self):
        middleware = KnowledgeCompressionMiddleware(token_limit=1000)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=MagicMock(),
            chat_prompt_template=MagicMock(),
            variables={},  # no context
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1

    def test_skips_when_not_overflow(self):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 500

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        middleware = KnowledgeCompressionMiddleware(token_limit=1000, token_margin=100)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={"context": "some context"},
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1
        assert ctx.variables["context"] == "some context"

    @patch("aidev_agent.core.nodes.model.token_compression.conditional_dispatch_custom_event")
    def test_compresses_when_overflow_and_func_provided(self, mock_dispatch):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 950

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        compressor_func = MagicMock(return_value="compressed context")

        middleware = KnowledgeCompressionMiddleware(
            knowledge_compressor_func=compressor_func,
            token_limit=1000,
            token_margin=100,
        )
        ctx = ProcessorContext(
            state={},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={"context": "original context", "query": "test query"},
            metadata={
                "provided_chat_history": [],
            },
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1
        assert ctx.variables["context"] == "compressed context"
        compressor_func.assert_called_once()

    def test_uses_cache_on_repeated_call(self):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 500  # not overflow

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        middleware = KnowledgeCompressionMiddleware(token_limit=1000)

        # Pre-populate compression state with cache
        state = CompressionState(
            knowledge_hash="abc123",
            knowledge_cache="cached context",
            knowledge_compressed=True,
        )

        ctx = ProcessorContext(
            state={},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={"context": "original context"},
            metadata={"_compression_state": state},
        )

        # Mock the hash to match
        with patch.object(KnowledgeCompressionMiddleware, "_compute_hash", return_value="abc123"):
            next_called = []
            middleware(ctx, lambda: next_called.append(True))

        assert ctx.variables["context"] == "cached context"


# ============================================================================
# ChatHistoryCompressionMiddleware 测试
# ============================================================================
class TestChatHistoryCompressionMiddleware:
    def test_skips_when_no_chat_history(self):
        middleware = ChatHistoryCompressionMiddleware(token_limit=1000)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=MagicMock(),
            chat_prompt_template=MagicMock(),
            variables={},
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1

    @patch("aidev_agent.core.nodes.model.token_compression.conditional_dispatch_custom_event")
    def test_removes_messages_when_overflow(self, mock_dispatch):
        # First call returns overflow, subsequent calls return under limit
        call_count = [0]

        def mock_get_tokens(*args):
            call_count[0] += 1
            if call_count[0] <= 2:
                return 950  # overflow
            return 500  # under limit

        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.side_effect = mock_get_tokens

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        middleware = ChatHistoryCompressionMiddleware(token_limit=1000, token_margin=100)
        ctx = ProcessorContext(
            state={"messages": []},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={
                "chat_history": [
                    HumanMessage(content="msg1"),
                    AIMessage(content="msg2"),
                    HumanMessage(content="msg3"),
                ]
            },
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1
        # Should have removed some messages
        state = _ensure_compression_state(ctx)
        assert state.chat_history_removed > 0

    def test_applies_previous_removal_count(self):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 500

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        state = CompressionState(chat_history_removed=1)

        middleware = ChatHistoryCompressionMiddleware(token_limit=1000)
        ctx = ProcessorContext(
            state={"messages": []},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={
                "chat_history": [
                    HumanMessage(content="msg1"),
                    AIMessage(content="msg2"),
                    HumanMessage(content="msg3"),
                ]
            },
            metadata={"_compression_state": state},
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        # Should skip first message due to previous removal
        assert len(ctx.variables["chat_history"]) == 2


# ============================================================================
# ToolOutputCompressionMiddleware 测试
# ============================================================================
class TestToolOutputLengthCompressionMiddleware:
    """测试基于字符长度的工具输出压缩中间件。"""

    def test_tool_output_len_calculation(self):
        messages = [
            HumanMessage(content="hello"),
            ToolMessage(content="result1", tool_call_id="1"),
            ToolMessage(content="result2", tool_call_id="2"),
            AIMessage(content="response"),
        ]
        length = ToolOutputLengthCompressionMiddleware._tool_output_len(messages)
        assert length == len("result1") + len("result2")

    def test_get_query_from_variables(self):
        ctx = ProcessorContext(
            state={},
            config={},
            variables={"query": "test query"},
        )
        query = ToolOutputLengthCompressionMiddleware._get_query(ctx)
        assert query == "test query"

    def test_get_query_from_state_input(self):
        ctx = ProcessorContext(
            state={"input": "state input"},
            config={},
            variables={},
        )
        query = ToolOutputLengthCompressionMiddleware._get_query(ctx)
        assert query == "state input"

    def test_skips_when_under_threshold(self):
        middleware = ToolOutputLengthCompressionMiddleware(tool_output_compress_thrd=5000)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=MagicMock(),
            metadata={"tool_messages": [ToolMessage(content="short", tool_call_id="1")]},
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1


class TestToolOutputTokenCompressionMiddleware:
    """测试基于 Token 超限的工具输出压缩中间件。"""

    def test_skips_when_no_llm(self):
        middleware = ToolOutputTokenCompressionMiddleware(token_limit=1000)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=None,
            metadata={"tool_messages": [ToolMessage(content="x" * 10000, tool_call_id="1")]},
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1

    def test_skips_when_not_overflow(self):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 500

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        middleware = ToolOutputTokenCompressionMiddleware(token_limit=1000, token_margin=100)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={},
            metadata={"tool_messages": [ToolMessage(content="x" * 200, tool_call_id="1")]},
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        assert len(next_called) == 1

    def test_skips_already_compressed(self):
        mock_llm = MagicMock()
        mock_llm.get_num_tokens_from_messages.return_value = 950

        mock_template = MagicMock()
        mock_template._format_prompt_with_error_handling.return_value = MagicMock(messages=[])

        state = CompressionState(
            tool_output_compressed=True,
            tool_output_compressed_ids={"1"},
        )

        middleware = ToolOutputTokenCompressionMiddleware(token_limit=1000, token_margin=100)
        ctx = ProcessorContext(
            state={},
            config={},
            llm=mock_llm,
            chat_prompt_template=mock_template,
            variables={},
            metadata={
                "tool_messages": [ToolMessage(content="x" * 200, tool_call_id="1", name="test_tool")],
                "_compression_state": state,
            },
        )

        next_called = []
        middleware(ctx, lambda: next_called.append(True))

        # Should not compress because tool_call_id "1" is already in compressed_ids
        assert len(next_called) == 1


# ============================================================================
# Prompt 模板测试
# ============================================================================
class TestPromptTemplates:
    def test_common_compressor_prompt_renders(self):
        result = _KNOWLEDGE_COMMON_COMPRESSOR_USR_PROMPT.render(content="test content")
        assert "test content" in result

    def test_specific_compressor_sys_prompt_renders(self):
        result = _TOOL_OUTPUT_SPECIFIC_COMPRESSOR_SYS_PROMPT.render(candidate_tool_name="my_tool")
        assert "my_tool" in result

    def test_specific_compressor_usr_prompt_renders(self):
        result = _TOOL_OUTPUT_SPECIFIC_COMPRESSOR_USR_PROMPT.render(
            provided_chat_history="[history]",
            candidate_tool_name="my_tool",
            candidate_tool_result="result data",
            query="user question",
        )
        assert "[history]" in result
        assert "my_tool" in result
        assert "result data" in result
        assert "user question" in result


# ============================================================================
# KnowledgeCompressor 测试
# ============================================================================
class TestKnowledgeCompressor:
    def test_compress_list_content(self):
        """测试列表内容并发压缩"""
        from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "compressed"
        mock_llm.invoke.return_value = mock_response

        compressor = KnowledgeCompressor(llm=mock_llm)

        with patch("aidev_agent.core.nodes.model.token_compression._compression_executor") as mock_executor:
            mock_future = MagicMock()
            mock_future.result.return_value = "compressed"
            mock_executor.submit.return_value = mock_future

            result = compressor([], "test query", ["content1"])

        assert isinstance(result, list)

    def test_compress_empty_list(self):
        """测试空列表不触发压缩"""
        from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor

        mock_llm = MagicMock()
        compressor = KnowledgeCompressor(llm=mock_llm)

        result = compressor([], "test query", [])

        assert result == []
        mock_llm.invoke.assert_not_called()

    def test_raises_error_for_non_list_context(self):
        """测试非列表类型的 context 抛出异常"""
        from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor

        mock_llm = MagicMock()
        compressor = KnowledgeCompressor(llm=mock_llm)

        with pytest.raises(TypeError) as exc_info:
            compressor([], "test query", "not a list")

        assert "context 必须是列表类型" in str(exc_info.value)

    def test_common_compressor_type(self):
        """测试 common 压缩模式"""
        from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "summary"
        mock_llm.invoke.return_value = mock_response

        compressor = KnowledgeCompressor(llm=mock_llm, compressor_type="common")

        with patch("aidev_agent.core.nodes.model.token_compression._compression_executor") as mock_executor:
            mock_future = MagicMock()
            mock_future.result.return_value = "summary"
            mock_executor.submit.return_value = mock_future

            result = compressor([], "test query", ["original content"])

        assert result == ["summary"]

    def test_invalid_compressor_type(self):
        """测试无效的压缩模式"""
        from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor

        mock_llm = MagicMock()
        compressor = KnowledgeCompressor(llm=mock_llm, compressor_type="invalid")

        with pytest.raises(TypeError) as exc_info:
            compressor([], "test query", "content")

        assert "context 必须是列表类型" in str(exc_info.value)

    @patch("aidev_agent.core.nodes.model.token_compression.HUNYUAN_SPECIFIC_RESPONSE", "hunyuan_response")
    def test_hunyuan_specific_response_not_compressed(self):
        """测试混元特殊回复不进行压缩"""
        from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "hunyuan_response"
        mock_llm.invoke.return_value = mock_response

        compressor = KnowledgeCompressor(llm=mock_llm)

        with patch("aidev_agent.core.nodes.model.token_compression._compression_executor") as mock_executor:
            mock_future = MagicMock()
            mock_future.result.return_value = "original content"
            mock_executor.submit.return_value = mock_future

            result = compressor([], "test query", ["original content"])

        assert result == ["original content"]

    def test_returns_original_on_failure(self):
        """测试失败时返回原始内容（列表模式）"""
        from aidev_agent.core.nodes.model.token_compression import KnowledgeCompressor

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = Exception("always fail")

        compressor = KnowledgeCompressor(llm=mock_llm)

        # 测试列表模式下失败时返回原始内容
        result = compressor([], "test query", ["content1", "content2"])

        assert result == ["content1", "content2"]


# ============================================================================
# KnowledgeCompressor Prompt 模板测试
# ============================================================================
class TestKnowledgeCompressorPromptTemplates:
    def test_knowledge_common_compressor_prompt_renders(self):
        from aidev_agent.core.nodes.model.token_compression import _KNOWLEDGE_COMMON_COMPRESSOR_USR_PROMPT

        result = _KNOWLEDGE_COMMON_COMPRESSOR_USR_PROMPT.render(content="test content")
        assert "test content" in result

    def test_knowledge_specific_compressor_prompt_exists(self):
        from aidev_agent.core.nodes.model.token_compression import _KNOWLEDGE_SPECIFIC_COMPRESSOR_SYS_PROMPT

        assert "知识文档" in _KNOWLEDGE_SPECIFIC_COMPRESSOR_SYS_PROMPT
        assert "相关性判断" in _KNOWLEDGE_SPECIFIC_COMPRESSOR_SYS_PROMPT

    def test_knowledge_specific_compressor_usr_prompt_renders(self):
        from aidev_agent.core.nodes.model.token_compression import _KNOWLEDGE_SPECIFIC_COMPRESSOR_USR_PROMPT

        result = _KNOWLEDGE_SPECIFIC_COMPRESSOR_USR_PROMPT.render(
            provided_chat_history="[history]",
            candidate_context="knowledge content",
            query="user question",
        )
        assert "[history]" in result
        assert "knowledge content" in result
        assert "user question" in result
