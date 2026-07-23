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

from __future__ import annotations

import os
from contextlib import suppress
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from langgraph.store.base import BaseStore


class NextFunction(Protocol):
    def __call__(self) -> None: ...


@dataclass
class PromptSlots:
    """模板槽位，用于中间件逐步填充/修改。"""

    system: str = ""
    human: str = ""

    # placeholders
    chat_history_slot: bool = True
    agent_scratchpad_slot: bool = True

    # 模板格式
    template_format: Literal["jinja2", "f-string"] = "jinja2"


@dataclass
class ModelChainState:
    """模型节点恢复循环的每次调用恢复计数器。

    跟踪多层恢复链的重试计数和回退数据，
    处理模型响应异常（空内容、仅思考响应、截断等）。
    """

    empty_content_retries: int = 0
    thinking_prefill_retries: int = 0
    post_tool_empty_retried: bool = False
    length_continue_retries: int = 0
    truncated_tool_call_retries: int = 0
    max_tokens_override: int | None = None  # D-10

    # 所有恢复类型的统一上限（从 ModelNodeSettings.max_model_retries 注入）。
    # 4 个分类计数器（empty_content_retries / thinking_prefill_retries /
    # length_continue_retries / truncated_tool_call_retries）仍保留用于
    # 日志和路由判断，但上限统一为 max_retries。
    max_retries: int = 10


@dataclass
class ProcessorContext:
    """中间件共享上下文。

    - 输入：state/config/store/llm 等
    - 输出：tools/chat_prompt_template/variables
    - metadata：中间件间共享的扩展数据
    """

    # 本次运行时的 LangGraph 相关参数，state/config/store
    state: Dict[str, Any]
    config: RunnableConfig
    store: Optional["BaseStore"] = None
    # 模型相关配置
    llm: Optional[BaseChatModel] = None
    # 输出-工具
    tools: List[BaseTool] = field(default_factory=list)
    # 输出-模板槽位（template pipeline 中间件逐步填充）
    prompt_slots: PromptSlots = field(default_factory=PromptSlots)
    chat_prompt_template: Optional[ChatPromptTemplate] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    # 中间件间通信
    metadata: Dict[str, Any] = field(default_factory=dict)
    # 跨 ReAct 周期的缓存（由 ContextAssembly 注入，用于存储消息切割缓存、压缩状态等）
    assembly_cache: Optional[Dict[str, Any]] = None
    # 注意：max_tokens_override 不在此处——它在 ModelChainState 上
    messages: List[BaseMessage] = field(default_factory=list)
    model_chain_state: Optional[ModelChainState] = None
    response: Optional[AIMessage | AnyMessage] = None


class Middleware(Protocol):
    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None: ...


# =============================================================================
# Settings (from settings.py)
# =============================================================================


DEFAULT_ENABLE_PARALLEL_TOOL_CALLS: bool = True


class ModelNodeSettings(BaseModel):
    """Settings for `build_model_node`.

    This model centralizes configuration for building the model node and its
    related ContextAssembly.

    Note: this model may contain internal-only extension points (excluded from
    serialization) for graph-layer composition.
    """

    use_structured_response: bool = Field(
        default=False,
        description="构建提示词时是否使用结构化响应模式",
    )
    enable_parallel_tool_calls: bool = Field(
        default=True,
        description="是否允许并行工具调用（如果模型支持）",
    )
    max_model_retries: int = Field(
        default=10,
        description="模型调用失败或返回无效消息时的最大重试次数。默认为 10。可通过环境变量 MODEL_MAX_RETRIES 配置。",
    )

    # ---------------------------------------------------------------------
    # Stability / recovery settings
    # ---------------------------------------------------------------------

    use_tool_call_promotion: bool = Field(
        default=True,
        description="是否启用纯文本工具调用提升（将文本中的工具调用格式解析为原生 tool_calls）",
    )
    enable_judge_response: bool = Field(
        default=True,
        description="是否启用任务完成度评估。关闭后 has_content 分支直接返回 NORMAL_COMPLETION，省去每次正常响应的额外判断 LLM 调用",
    )

    # ---------------------------------------------------------------------
    # ContextAssembly configuration
    # ---------------------------------------------------------------------

    enable_query_clarification: bool = Field(
        default=True,
        description="当用户查询模糊时是否启用查询澄清",
    )
    rejection_message: str = Field(
        default="抱歉，没有找到相关信息。",
        description="当智能体决定拒绝回答时使用的兜底消息",
    )
    use_general_knowledge_on_miss: bool = Field(
        default=False,
        description="当检索/记忆未命中时，是否允许使用通用知识回答。如果为 False，智能体应使用 rejection_message 响应",
    )
    use_deepseek_r1_models_process: bool = Field(
        default=True,
        description="是否在变量管道中启用 DeepSeek R1 模型特定处理",
    )
    tool_output_compress_thrd: int = Field(
        default=5000,
        description="将工具输出插入提示词变量之前进行压缩的阈值，字符数限制",
    )
    tool_output_compressor_type: str = Field(
        default="specific",
        description="ToolOutputCompressionMiddleware 使用的压缩器类型。",
    )
    token_limit: Optional[int] = Field(
        default=None,
        description="压缩中间件的 token 限制。如果为 None，则禁用基于 token 限制的压缩",
    )
    token_margin: int = Field(
        default=100,
        description="检查 token 溢出时预留的 token 余量",
    )

    # ---------------------------------------------------------------------
    # Extension points (internal)
    # ---------------------------------------------------------------------

    @model_validator(mode="before")
    @classmethod
    def validate_max_model_retries(cls, values: Any) -> Any:
        """如果未显式设置 max_model_retries，则尝试从环境变量 MODEL_MAX_RETRIES 读取。"""
        # 只有当 max_model_retries 没有在 values 中显式提供时，才检查环境变量
        if "max_model_retries" not in values:
            env_val = os.getenv("MODEL_MAX_RETRIES")
            if env_val is not None:
                with suppress(ValueError):
                    values["max_model_retries"] = int(env_val)
        return values

    extra_template_middlewares: list[Any] = Field(
        default_factory=list,
        description="(internal) Extra template pipeline middlewares injected by graph layer.",
        exclude=True,
    )

    extra_tool_middlewares: list[Any] = Field(
        default_factory=list,
        description="(internal) Extra tool pipeline middlewares injected by graph layer.",
        exclude=True,
    )


# =============================================================================
# Recovery Exceptions（从 recovery_exceptions.py 迁移而来 — D-14）
# =============================================================================


class RecoveryException(Exception):
    """所有恢复触发异常的基类。"""

    def __init__(self, response: AIMessage, message: str = ""):
        self.response = response
        super().__init__(message or self.__class__.__name__)


class RecoveryRetryableException(RecoveryException):
    """可重试异常的中间基类（被 RunnableRetry 捕获）。"""


class RecoveryNudgeError(RecoveryRetryableException):
    """工具后空响应 — 发送提示并重试。"""


class RecoveryPrefillError(RecoveryRetryableException):
    """仅思考响应 — 追加 prefill 并重试。"""


class TruncationError(RecoveryRetryableException):
    """截断响应 — 继续或重建 chain 并重试。"""


class RecoveryRetryError(RecoveryRetryableException):
    """空内容 — 简单重试。"""


class RetryableRateLimitError(RecoveryRetryableException):
    """429 限流 — 睡眠后重试。"""


RETRYABLE_EXCEPTIONS: tuple[type[RecoveryRetryableException], ...] = (
    RecoveryNudgeError,
    RecoveryPrefillError,
    TruncationError,
    RecoveryRetryError,
    RetryableRateLimitError,
)
