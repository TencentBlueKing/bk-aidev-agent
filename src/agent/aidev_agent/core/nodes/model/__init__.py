# -*- coding: utf-8 -*-
"""Model node package.

This package groups the model node implementation (`build_model_node`) and its
strongly-coupled context processing utilities (previously under
`aidev_agent.core.nodes.context_processor`).
"""

from .basic_middleware import get_beijing_now
from .context_assembly import ContextAssembly
from .node import ModelState, build_model_node
from .pydantic_models import ModelNodeSettings
from .token_compression import (
    ChatHistoryCompressionMiddleware,
    CompressionState,
    KnowledgeCompressionMiddleware,
    KnowledgeCompressor,
    ToolOutputCompressor,
    ToolOutputLengthCompressionMiddleware,
    ToolOutputTokenCompressionMiddleware,
)

__all__ = [
    "ChatHistoryCompressionMiddleware",
    "CompressionState",
    "ContextAssembly",
    "KnowledgeCompressionMiddleware",
    "KnowledgeCompressor",
    "ModelState",
    "ModelNodeSettings",
    "ToolOutputCompressor",
    "ToolOutputLengthCompressionMiddleware",
    "ToolOutputTokenCompressionMiddleware",
    "build_model_node",
    "get_beijing_now",
]
