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

from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool

from .pydantic_models import Middleware, ProcessorContext, PromptSlots


class MiddlewarePipeline:
    """类似 Koa/Express 的同步中间件执行链。"""

    def __init__(self) -> None:
        self._middlewares: list[Middleware] = []

    @property
    def middlewares(self) -> list[Middleware]:
        return list(self._middlewares)

    def add(self, middleware: Middleware, *, prepend: bool = False) -> None:
        if prepend:
            self._middlewares.insert(0, middleware)
        else:
            self._middlewares.append(middleware)

    # Backwards-compatible alias
    def use(self, middleware: Middleware, *, prepend: bool = False) -> None:
        self.add(middleware, prepend=prepend)

    def execute(self, ctx: ProcessorContext) -> None:
        middlewares = self._middlewares

        def dispatch(idx: int) -> None:
            if idx >= len(middlewares):
                return

            called = False

            def next_() -> None:
                nonlocal called
                if called:
                    raise RuntimeError("next() called multiple times")
                called = True
                dispatch(idx + 1)

            middlewares[idx](ctx, next_)

        dispatch(0)


class ContextAssembly:
    """上下文组件：通过三条 MiddlewarePipeline 组织工具/模板/变量构建逻辑。

    ContextAssembly 仅负责：
    - 保存三条中间件管道（tool/template/variable）
    - 提供中间件注册能力（add_middleware / add_*_middleware）
    - 提供 get_tools / get_prompt / get_variables 等统一查询接口

    注意：中间件的“加载/装配”（例如 BaseToolsMiddleware、SpecialVariablesMiddleware 等）
    应由 build_model_node 决定并完成，ContextAssembly 本身不持有这些中间件的配置字段。
    """

    def __init__(
        self,
        *,
        tools: Optional[List[BaseTool]] = None,
    ):
        self._all_tools: List[BaseTool] = tools or []

        # 用于存储跨 ReAct 周期的数据（例如：messages 切割缓存、压缩状态等）
        self._cache: Dict[str, Any] = {}

        # ===== Middlewares (initialized but empty) =====
        # 中间件的具体加载由 build_model_node 完成
        self._tool_pipeline = MiddlewarePipeline()
        self._template_pipeline = MiddlewarePipeline()
        self._variable_pipeline = MiddlewarePipeline()

    # ---------------------------------------------------------------------
    # Middleware injection
    # ---------------------------------------------------------------------

    def add_middleware(self, pipeline: str, middleware: Middleware, *, prepend: bool = False) -> None:
        """向指定 pipeline 注入自定义中间件。

        pipeline 可选值："tool"/"template"/"variable"（或其复数形式）。
        """

        key = pipeline.lower()
        if key in {"tool", "tools"}:
            self._tool_pipeline.add(middleware, prepend=prepend)
        elif key in {"template", "templates"}:
            self._template_pipeline.add(middleware, prepend=prepend)
        elif key in {"variable", "variables"}:
            self._variable_pipeline.add(middleware, prepend=prepend)
        else:
            raise ValueError(f"Unknown pipeline: {pipeline}")

    def append_system_prompt(self, content: str) -> None:
        """追加内容到 system prompt。

        This registers a template middleware that runs late in the pipeline.
        """

        def middleware(ctx: ProcessorContext, next: Any) -> None:
            ctx.prompt_slots.system += content
            next()

        self.add_middleware("template", middleware)

    def prepend_system_prompt(self, content: str) -> None:
        """前置内容到 system prompt。

        This registers a template middleware that runs late in the pipeline.
        """

        def middleware(ctx: ProcessorContext, next: Any) -> None:
            ctx.prompt_slots.system = content + ctx.prompt_slots.system
            next()

        self.add_middleware("template", middleware)

    @staticmethod
    def _assemble_template(slots: PromptSlots, *, prompt_mode: str = "tool_calling") -> ChatPromptTemplate:
        """Assemble a ChatPromptTemplate from PromptSlots.

        prompt_mode:
          - tool_calling: system + placeholders + human + (optional) scratchpad placeholder
          - structured_chat: human(system) + placeholders + human(human+scratchpad embedded)
        """

        messages: list[Any] = []

        if prompt_mode == "structured_chat":
            messages.append(("human", slots.system))
            if slots.chat_history_slot:
                messages.append(("placeholder", "{chat_history}"))
            messages.append(("human", slots.human))
            return ChatPromptTemplate.from_messages(messages, template_format=slots.template_format)

        # default: tool_calling
        messages.append(("system", slots.system))
        if slots.chat_history_slot:
            messages.append(("placeholder", "{chat_history}"))
        messages.append(("human", slots.human))
        if slots.agent_scratchpad_slot:
            messages.append(("placeholder", "{agent_scratchpad}"))
        return ChatPromptTemplate.from_messages(messages, template_format=slots.template_format)

    # ---------------------------------------------------------------------
    # Public API (backwards compatible)
    # ---------------------------------------------------------------------

    def get_choice_tools(self, ctx: ProcessorContext) -> List[BaseTool]:
        """获取工具列表（通过 tool pipeline 处理）。"""
        ctx.tools = self._all_tools
        self._tool_pipeline.execute(ctx)
        return ctx.tools

    def get_chat_prompt_template(self, ctx: ProcessorContext) -> ChatPromptTemplate:
        """获取 prompt 模板（通过 template pipeline 处理）。"""
        # NOTE: make sure we always start from a clean slots object.
        ctx.prompt_slots = PromptSlots()

        self._template_pipeline.execute(ctx)

        if ctx.chat_prompt_template is None:
            prompt_mode = ctx.metadata.get("prompt_mode", "tool_calling")
            ctx.chat_prompt_template = self._assemble_template(ctx.prompt_slots, prompt_mode=prompt_mode)

        if ctx.chat_prompt_template is None:
            raise RuntimeError("chat_prompt_template is not set")

        return ctx.chat_prompt_template

    def get_chat_prompt_variables(self, ctx: ProcessorContext) -> Dict[str, Any]:
        """获取 prompt 变量（通过 variable pipeline 处理）。"""
        ctx.assembly_cache = self._cache

        self._variable_pipeline.execute(ctx)

        # 回写消息切分缓存（实例级）
        if ctx.assembly_cache is not None:
            self._cache = ctx.assembly_cache

        return ctx.variables
