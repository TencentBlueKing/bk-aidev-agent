# -*- coding: utf-8 -*-
"""工具延迟加载的目录中间件。

``ToolDirectoryMiddleware``（模板管道）只在装配期判定为启用工具延迟加载时经
``node_options_kwargs`` 安装（判定在 ``graph._prepare_agent_tools``，只读一次配置）；
**安装后无条件执行**，不在运行期再读任何开关。模型绑定集合（内置 + 元工具）由装配期直接选定，
不经中间件裁剪。

目录只读原始 catalog；目录名是 SDK 固定契约，外部重名由去重层让名，不由目录或图层追踪恢复。

目录文本跨 ReAct 轮次经 ``ctx.assembly_cache`` 复用（由 ``ContextAssembly.get_chat_prompt_template``
在模板管道执行前注入）；观测（token 估算 / 摘要日志）不在本模块，由后续观测接线负责。
"""

from __future__ import annotations

from dataclasses import dataclass

from aidev_agent.core.nodes.model.pydantic_models import NextFunction, ProcessorContext
from aidev_agent.core.tools.tool_lazy_loading.catalog import LazyToolCatalog
from aidev_agent.core.tools.tool_lazy_loading.meta_tools import CALL_TOOL_NAME, DESCRIBE_TOOL_NAME

# 目录段说明：`{describe}` / `{call}` 按中间件字段渲染，默认即固定元工具名（字段可显式覆盖，但装配层只用默认值）
DIRECTORY_HEADER_TEMPLATE = (
    "\n\n# 可延迟加载的工具\n"
    "下列工具的完整参数定义未直接提供。需要使用时先调用 {describe}(names=[...]) 获取参数 schema，"
    "再用 {call}(name=..., arguments={{...}}) 执行；不要直接调用这些工具名。\n"
)

# 单条描述在目录中的最大展示长度（只影响目录，不影响 tool_describe 返回的完整描述）
DIRECTORY_DESCRIPTION_LIMIT = 200

# ``ProcessorContext.assembly_cache`` 中目录缓存的命名空间：{catalog: 目录文本}。
# 键用 catalog 对象身份（``LazyToolCatalog`` 未定义 __eq__/__hash__），不同装配共享同一 cache 时互不串。
DIRECTORY_CACHE_KEY = "tool_lazy_loading_directory"


@dataclass
class ToolDirectoryMiddleware:
    """把可延迟加载的工具目录追加到 system prompt（模板管道）。"""

    catalog: LazyToolCatalog
    describe_tool_name: str = DESCRIBE_TOOL_NAME
    call_tool_name: str = CALL_TOOL_NAME

    def render_directory(self) -> str:
        """system prompt 中的工具目录段：说明段 + 每个延迟工具的「名称: 折叠并截断的描述」。"""
        header = DIRECTORY_HEADER_TEMPLATE.format(describe=self.describe_tool_name, call=self.call_tool_name)
        lines = [header]
        for tool in self.catalog.deferred():
            description = (getattr(tool, "description", "") or "").strip().replace("\n", " ")
            if len(description) > DIRECTORY_DESCRIPTION_LIMIT:
                description = description[:DIRECTORY_DESCRIPTION_LIMIT] + "…"
            lines.append(f"- {getattr(tool, 'name', '')}: {description}\n")
        return "".join(lines)

    def __call__(self, ctx: ProcessorContext, next: NextFunction) -> None:
        cache = ctx.assembly_cache
        if cache is None:
            directory = self.render_directory()
        else:
            namespace = cache.setdefault(DIRECTORY_CACHE_KEY, {})
            directory = namespace.get(self.catalog)
            if directory is None:
                directory = namespace[self.catalog] = self.render_directory()
        # 目录是数据而非模板源码；各目录中间件使用独立变量，避免互相覆盖。
        variable = f"tool_lazy_loading_directory_{len(ctx.variables)}"
        ctx.variables[variable] = directory
        placeholder = "{{ " + variable + " }}" if ctx.prompt_slots.template_format == "jinja2" else "{" + variable + "}"
        ctx.prompt_slots.system = (ctx.prompt_slots.system or "") + placeholder
        next()
