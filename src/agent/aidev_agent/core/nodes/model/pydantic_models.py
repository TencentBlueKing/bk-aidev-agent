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

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

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
    """

    use_structured_response: bool = Field(
        default=False,
        description="构建提示词时是否使用结构化响应模式",
    )
    enable_parallel_tool_calls: bool = Field(
        default=True,
        description="是否允许并行工具调用（如果模型支持）",
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
    role_prompt: str = Field(
        default="你是一个智能助手。",
        description="注入到聊天提示词模板中的角色/系统提示词",
    )
    use_general_knowledge_on_miss: bool = Field(
        default=False,
        description="当检索/记忆未命中时，是否允许使用通用知识回答。如果为 False，智能体应使用 rejection_message 响应",
    )
    prefix: Optional[str] = Field(
        default=None,
        description="注入到提示词中的可选前缀（例如产品/领域上下文）",
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
