# -*- coding: utf-8 -*-
"""模型节点包。

本包组织了模型节点实现（`build_model_node`）及其
强耦合的上下文处理工具（前身在 `aidev_agent.core.nodes.context_processor` 下）。
"""

from .basic_middleware import get_beijing_now
from .chat_history_assembly import convert_chat_history_to_messages
from .context_assembly import ContextAssembly
from .node import ModelState, build_model_node
from .pydantic_models import (
    RETRYABLE_EXCEPTIONS,
    ModelNodeSettings,
    RecoveryException,
    RecoveryNudgeError,
    RecoveryPrefillError,
    RecoveryRetryableException,
    RecoveryRetryError,
    RetryableRateLimitError,
    TruncationError,
)
from .quality_gate import QualityGate
from .token_compression import (
    ChatHistoryCompressionMiddleware,
    CompressionState,
    KnowledgeCompressionMiddleware,
    KnowledgeCompressor,
    ToolOutputCompressor,
    ToolOutputLengthCompressionMiddleware,
    ToolOutputTokenCompressionMiddleware,
)
from .tool_call_repair import ParsedToolCall, parse_standalone_plain_text_tool_call_blocks
from .utils import promote_plain_text_tool_call_message, should_promote_message

__all__ = [
    "ChatHistoryCompressionMiddleware",
    "CompressionState",
    "ContextAssembly",
    "KnowledgeCompressionMiddleware",
    "KnowledgeCompressor",
    "ModelState",
    "ModelNodeSettings",
    "ParsedToolCall",
    "QualityGate",
    "RecoveryException",
    "RecoveryNudgeError",
    "RecoveryPrefillError",
    "RecoveryRetryError",
    "RecoveryRetryableException",
    "RETRYABLE_EXCEPTIONS",
    "RetryableRateLimitError",
    "ToolOutputCompressor",
    "ToolOutputLengthCompressionMiddleware",
    "ToolOutputTokenCompressionMiddleware",
    "TruncationError",
    "build_model_node",
    "convert_chat_history_to_messages",
    "get_beijing_now",
    "parse_standalone_plain_text_tool_call_blocks",
    "promote_plain_text_tool_call_message",
    "should_promote_message",
]
