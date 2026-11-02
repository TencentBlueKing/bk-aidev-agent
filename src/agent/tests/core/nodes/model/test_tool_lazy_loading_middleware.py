# -*- coding: utf-8 -*-
"""目录中间件与目录缓存（REQ-3 / REQ-5 / REQ-9 / REQ-10）。

- 模板管道：ToolDirectoryMiddleware 无条件渲染目录段并追加到 system prompt 末尾。
- 绑定集合（内置 + 元工具）由 graph 装配期直接选定，不经中间件；此处按同样形态构造 assembly。

目录中间件只在装配期判定为启用时被安装（判定在 graph），安装后不再读任何开关，
故本文件不覆盖「未启用」形态（由 tests/core/graphs/test_react.py 的整图用例覆盖）。
- 目录段按 catalog 缓存在 ``ctx.assembly_cache`` 的 ``tool_lazy_loading_directory`` 命名空间下，跨 ReAct 轮次复用。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List

import aidev_agent.core.graphs.react.tool_lazy_loading_middleware as middleware_module
import pytest
from aidev_agent.core.graphs.react.tool_lazy_loading_middleware import (
    DIRECTORY_CACHE_KEY,
    DIRECTORY_DESCRIPTION_LIMIT,
    DIRECTORY_HEADER_TEMPLATE,
    ToolDirectoryMiddleware,
)
from aidev_agent.core.nodes.model.basic_middleware import BaseVariablesMiddleware
from aidev_agent.core.nodes.model.context_assembly import ContextAssembly
from aidev_agent.core.nodes.model.pydantic_models import ProcessorContext
from aidev_agent.core.tools.tool_lazy_loading.catalog import LazyToolCatalog
from aidev_agent.core.tools.tool_lazy_loading.meta_tools import make_meta_tools
from langchain_core.tools import BaseTool


class FakeTool(BaseTool):
    name: str
    description: str = "fake"

    def _run(self, **kwargs) -> str:  # type: ignore[override]
        return "ok"


def make_tools(count: int, *, prefix: str) -> List[FakeTool]:
    return [FakeTool(name=f"{prefix}_{index}", description=f"{prefix} 描述 {index}") for index in range(count)]


def assemble(catalog: LazyToolCatalog):
    """装配期形态（与 graph 一致）：模型只绑定元工具（内置工具不在 catalog，此处不涉及）。

    返回 (绑定工具, (describe_name, call_name))；catalog 保持不可变，元工具名由工厂返回的实例名提供。
    """
    describe_tool, call_tool = make_meta_tools(catalog)
    return [describe_tool, call_tool], (describe_tool.name, call_tool.name)


DIRECTORY_NAMES = {"describe_tool_name": "tool_describe", "call_tool_name": "tool_call"}


def render_for(catalog: LazyToolCatalog) -> str:
    """按装配期注入的真实元工具名渲染目录（不读 catalog 的元工具）。"""
    _, names = assemble(catalog)
    return ToolDirectoryMiddleware(
        catalog=catalog, describe_tool_name=names[0], call_tool_name=names[1]
    ).render_directory()


def build_assembly(catalog: LazyToolCatalog) -> ContextAssembly:
    bound, (describe_name, call_name) = assemble(catalog)
    assembly = ContextAssembly(tools=bound)
    assembly.add_middleware(
        "template",
        ToolDirectoryMiddleware(catalog=catalog, describe_tool_name=describe_name, call_tool_name=call_name),
    )
    return assembly


def make_catalog(*, deferred_count: int = 30):
    return LazyToolCatalog(deferred_tools=make_tools(deferred_count, prefix="biz"))


def rendered_system(ctx: ProcessorContext) -> str:
    return ctx.chat_prompt_template.format_messages(**ctx.variables)[0].content


def run_pipelines(assembly: ContextAssembly, config=None):
    ctx = ProcessorContext(
        state={"messages": []}, config=config or {"configurable": {"thread_id": "thread-1"}}, llm=None
    )
    tools = assembly.get_choice_tools(ctx)
    assembly.get_chat_prompt_template(ctx)
    assembly.get_chat_prompt_variables(ctx)
    return tools, rendered_system(ctx), ctx


class TestDirectoryLiteralRendering:
    @pytest.mark.parametrize(
        "description",
        ["{{ 7 * 7 }}", "{% if missing %}hidden{% endif %}", "{% endraw %}", "{{ broken", "x" * 195 + "{{ broken }}"],
    )
    @pytest.mark.parametrize("template_format", ["jinja2", "f-string"])
    def test_directory_is_literal_after_variable_pipeline(self, description, template_format):
        tool = FakeTool(name="tool_{{ unknown }}", description=description)
        catalog = LazyToolCatalog(deferred_tools=[tool])
        assembly = ContextAssembly()

        def template(ctx, next):
            ctx.prompt_slots.template_format = template_format
            ctx.prompt_slots.system = "prefix {{ query }}" if template_format == "jinja2" else "prefix {query}"
            next()

        assembly.add_middleware("template", template)
        assembly.add_middleware("template", ToolDirectoryMiddleware(catalog))
        assembly.add_middleware("variable", BaseVariablesMiddleware())
        for _ in range(2):
            ctx = make_ctx()
            ctx.state["query"] = "rendered"
            run_full(assembly, ctx)
            assert rendered_system(ctx) == "prefix rendered" + render_for(catalog)


class TestDirectoryInjection:
    """模板管道（AC-15 / AC-12）。"""

    def test_directory_appended_when_active(self):
        """目录段追加在 system prompt 末尾，内容与 render_directory 一致。"""
        catalog = make_catalog(deferred_count=30)
        _, system, ctx = run_pipelines(build_assembly(catalog))
        assert system.endswith(render_for(catalog))
        assert "- biz_0: biz 描述 0" in system

    def test_prompt_text_exact(self):
        """逐字回归：header 原文（``\\n\\n`` 开头、末尾换行）+ 按延迟集合顺序的每条目录行。"""
        catalog = make_catalog(deferred_count=30)
        _, system, _ = run_pipelines(build_assembly(catalog))
        header = (
            "\n\n# 可延迟加载的工具\n"
            "下列工具的完整参数定义未直接提供。需要使用时先调用 tool_describe(names=[...]) 获取参数 schema，"
            "再用 tool_call(name=..., arguments={...}) 执行；不要直接调用这些工具名。\n"
        )
        expected = header + "".join(f"- biz_{i}: biz 描述 {i}\n" for i in range(30))
        assert not expected.startswith("- ")
        assert system == expected

    def test_description_truncated_in_directory_only(self):
        """截断边界：超过 200 字符的描述在目录中以 `…` 结尾，describe 仍返回完整原文。"""
        long_description = "x" * (DIRECTORY_DESCRIPTION_LIMIT + 100)
        tool = FakeTool(name="long_tool", description=long_description)
        catalog = LazyToolCatalog(deferred_tools=[tool])
        rendered = render_for(catalog)
        lines = [line for line in rendered.splitlines() if line.startswith("- ")]
        assert lines == [f"- long_tool: {'x' * DIRECTORY_DESCRIPTION_LIMIT}…"]
        assert catalog.describe(["long_tool"])[0]["description"] == long_description

    def test_description_at_limit_not_truncated(self):
        """截断边界：恰为 200 字符的描述原样保留、不补 `…`。"""
        exact = "y" * DIRECTORY_DESCRIPTION_LIMIT
        tool = FakeTool(name="edge_tool", description=exact)
        catalog = LazyToolCatalog(deferred_tools=[tool])
        assert f"- edge_tool: {exact}\n" in render_for(catalog)

    def test_newline_folded_in_directory(self):
        """换行折叠：描述内换行替换为空格，不能凭换行伪造目录条目。"""
        tool = FakeTool(name="multi", description="  line1\n\nline2  ")
        catalog = LazyToolCatalog(deferred_tools=[tool])
        lines = render_for(catalog).rsplit("\n", 1)[0].splitlines()
        assert lines[-1:] == ["- multi: line1  line2"]

    def test_directory_lists_name_and_description_in_order(self):
        """目录行按延迟集合顺序列出「名称: 描述」。"""
        tools = [FakeTool(name="b_tool", description="B 描述"), FakeTool(name="a_tool", description="A 描述")]
        catalog = LazyToolCatalog(deferred_tools=tools)
        lines = render_for(catalog).rsplit("\n", 1)[0].splitlines()
        assert lines[-2:] == ["- b_tool: B 描述", "- a_tool: A 描述"]

    def test_directory_stable_across_calls(self):
        """同一 catalog 多次渲染结果一致（无缓存也须稳定）。"""
        catalog = make_catalog(deferred_count=4)
        middleware = ToolDirectoryMiddleware(catalog=catalog, **DIRECTORY_NAMES)
        assert middleware.render_directory() == middleware.render_directory()

    def test_directory_without_deferred_tools(self):
        """超阈值但全为内置工具时目录只有说明段（AC-13）。"""
        catalog = make_catalog(deferred_count=0)
        text = ToolDirectoryMiddleware(catalog=catalog, **DIRECTORY_NAMES).render_directory()
        assert text == DIRECTORY_HEADER_TEMPLATE.format(describe="tool_describe", call="tool_call")
        assert "- " not in text

    def test_default_fields_render_standard_meta_names(self):
        """只给 catalog 构造（节点默认路径）：说明段用标准元工具名，延迟工具行完整。"""
        catalog = make_catalog(deferred_count=2)
        text = ToolDirectoryMiddleware(catalog=catalog).render_directory()
        header = text.splitlines()[3]  # 空行、标题、"# 可延迟加载的工具" 之后是说明段
        assert " tool_describe(names=[...])" in header and " tool_call(name=..., arguments=" in header
        assert text.endswith("- biz_0: biz 描述 0\n- biz_1: biz 描述 1\n")

    @pytest.mark.parametrize("describe_name, call_name", [("d_fn", "c_fn"), ("aidev_lazy__tool_describe", "tool_call")])
    def test_explicit_fields_override_defaults(self, describe_name, call_name):
        """显式字段优先于默认值（API 保留）：装配层只用默认固定名，此处锁定字段覆盖能力本身。"""
        catalog = make_catalog(deferred_count=1)
        middleware = ToolDirectoryMiddleware(
            catalog=catalog, describe_tool_name=describe_name, call_tool_name=call_name
        )
        header = middleware.render_directory().splitlines()[3]
        assert f" {describe_name}(names=[...])" in header and f" {call_name}(name=" in header
        # 说明段只出现两个字段值，不再夹带标准名
        rendered = set(re.findall(r" (\S+)\(", header))
        assert rendered == {describe_name, call_name}

    def test_both_pipelines_agree_across_runs(self):
        """AC-15：同一 config 连续两次，tools 与 system prompt 逐项一致。"""
        catalog = make_catalog(deferred_count=30)
        assembly = build_assembly(catalog)
        config = {"configurable": {"thread_id": "same-thread"}}

        first_tools, first_system, _ = run_pipelines(assembly, config)
        second_tools, second_system, _ = run_pipelines(assembly, config)

        assert [t.name for t in first_tools] == [t.name for t in second_tools]
        assert first_system == second_system


@dataclass
class CountingDirectory(ToolDirectoryMiddleware):
    """按 render_directory 的真实调用计数；文本仍由父类实现渲染。"""

    calls: List[str] = field(default_factory=list)

    def render_directory(self) -> str:
        self.calls.append("render")
        return super().render_directory()


def make_ctx(cache=None) -> ProcessorContext:
    return ProcessorContext(
        state={"messages": []}, config={"configurable": {"thread_id": "thread-1"}}, llm=None, assembly_cache=cache
    )


def build_counting_assembly(catalog: LazyToolCatalog):
    """返回 (assembly, counting middleware)：目录中间件换成计数版，其余与 build_assembly 一致。"""
    bound, (describe_name, call_name) = assemble(catalog)
    middleware = CountingDirectory(catalog=catalog, describe_tool_name=describe_name, call_tool_name=call_name)
    assembly = ContextAssembly(tools=bound)
    assembly.add_middleware("template", middleware)
    return assembly, middleware


def run_full(assembly: ContextAssembly, ctx: ProcessorContext):
    """真实模型请求顺序：模板、变量装配，然后选择绑定工具。"""
    assembly.get_chat_prompt_template(ctx)
    assembly.get_chat_prompt_variables(ctx)
    return assembly.get_choice_tools(ctx)


class TestDirectoryCache:
    """目录段经 ctx.assembly_cache 跨轮次复用（按 catalog 身份隔离）。"""

    def test_single_render_across_two_fresh_contexts(self):
        """同一 ContextAssembly + 两个新建 ctx：目录只渲染一次，第二轮命中同一缓存文本。"""
        catalog = make_catalog(deferred_count=30)
        assembly, middleware = build_counting_assembly(catalog)
        first, second = make_ctx(), make_ctx()

        run_full(assembly, first)
        run_full(assembly, second)

        rendered = render_for(catalog)
        assert len(middleware.calls) == 1
        assert rendered_system(first) == rendered
        assert rendered_system(second) == rendered
        assert assembly._cache[DIRECTORY_CACHE_KEY][catalog] == rendered

    def test_cache_shared_across_contexts_renders_once(self):
        """直接运行目录中间件的上下文可复用已注入的同一缓存。"""
        catalog = make_catalog(deferred_count=30)
        middleware = CountingDirectory(catalog=catalog, **DIRECTORY_NAMES)
        cache: dict = {}

        middleware(make_ctx(cache), lambda: None)
        middleware(make_ctx(cache), lambda: None)

        rendered = render_for(catalog)
        assert len(middleware.calls) == 1
        assert cache[DIRECTORY_CACHE_KEY][catalog] == rendered

    def test_fresh_assemblies_render_independently_without_leakage(self):
        """两个新鲜 ContextAssembly（各自 _cache）：各自渲染一次，互不串目录。"""
        first_catalog = make_catalog(deferred_count=30)
        second_catalog = make_catalog(deferred_count=31)
        first_assembly, first_middleware = build_counting_assembly(first_catalog)
        second_assembly, second_middleware = build_counting_assembly(second_catalog)

        first_ctx, second_ctx = make_ctx(), make_ctx()
        run_full(first_assembly, first_ctx)
        run_full(second_assembly, second_ctx)

        assert len(first_middleware.calls) == 1
        assert len(second_middleware.calls) == 1
        assert first_assembly._cache is not second_assembly._cache
        assert "- biz_30: biz 描述 30" not in rendered_system(first_ctx)
        assert "- biz_30: biz 描述 30" in rendered_system(second_ctx)

    @pytest.mark.parametrize("same_names", [False, True])
    def test_two_catalogs_share_cache_without_collision(self, same_names):
        """同一 cache 依次处理两个不同 catalog：namespace 两个键，各自文本不串（同名工具也不串）。"""
        first_catalog = make_catalog(deferred_count=30)
        tools = [FakeTool(name="audit_0", description="audit 描述")] + make_tools(
            30, prefix="biz" if same_names else "ops"
        )
        # 第二个 catalog 同样只持原始快照：延迟工具本体、元工具由装配期另行提供
        second_catalog = LazyToolCatalog(deferred_tools=tools)
        assembly = ContextAssembly(tools=first_catalog.deferred())
        assembly.add_middleware("template", ToolDirectoryMiddleware(catalog=first_catalog, **DIRECTORY_NAMES))
        assembly.add_middleware("template", ToolDirectoryMiddleware(catalog=second_catalog, **DIRECTORY_NAMES))

        first_ctx, second_ctx = make_ctx(), make_ctx()
        run_full(assembly, first_ctx)
        run_full(assembly, second_ctx)

        namespace = assembly._cache[DIRECTORY_CACHE_KEY]
        assert set(namespace) == {first_catalog, second_catalog}
        assert "- audit_0: audit 描述" in rendered_system(second_ctx)
        assert "- biz_0:" in rendered_system(first_ctx)
        assert (
            namespace[second_catalog]
            == ToolDirectoryMiddleware(catalog=second_catalog, **DIRECTORY_NAMES).render_directory()
        )
        # 同名场景下第二个 catalog 只有 31 个可见工具（audit_0 + biz_0..29），停在第 29 条
        expected_second = "- biz_29: biz 描述 29" if same_names else "- ops_0: ops 描述 0"
        assert expected_second in rendered_system(second_ctx)

    def test_none_cache_renders_every_time(self):
        """ctx.assembly_cache 为 None：每次真实渲染，目录中间件不写任何缓存条目。"""
        catalog = make_catalog(deferred_count=30)
        middleware = CountingDirectory(catalog=catalog, **DIRECTORY_NAMES)
        texts = []
        for _ in range(2):
            ctx = make_ctx()
            middleware(ctx, lambda: None)
            ctx.chat_prompt_template = ContextAssembly._assemble_template(ctx.prompt_slots)
            texts.append(rendered_system(ctx))
            assert ctx.assembly_cache is None

        rendered = render_for(catalog)
        assert texts == [rendered, rendered]
        assert len(middleware.calls) == 2

    def test_existing_assembly_cache_entries_survive_both_pipelines(self):
        catalog = make_catalog(deferred_count=30)
        assembly, middleware = build_counting_assembly(catalog)
        sentinel = object()
        assembly._cache["compression_state"] = sentinel
        first, second = make_ctx(), make_ctx()
        run_full(assembly, first)
        run_full(assembly, second)
        assert first.assembly_cache is second.assembly_cache is assembly._cache
        assert second.assembly_cache["compression_state"] is sentinel
        assert middleware.calls == ["render"]

    def test_context_from_another_assembly_uses_owning_cache(self):
        catalog = make_catalog(deferred_count=30)
        first, _ = build_counting_assembly(catalog)
        second, counter = build_counting_assembly(catalog)
        ctx = make_ctx()
        run_full(first, ctx)
        ctx.chat_prompt_template = None
        run_full(second, ctx)
        assert ctx.assembly_cache is second._cache
        assert first._cache is not second._cache
        assert counter.calls == ["render"]

    def test_variables_pipeline_preserves_directory_cache(self):
        """模板管道写入的目录缓存不被随后的 variables 管道抹掉（同一 ctx 连续两条管道）。"""
        catalog = make_catalog(deferred_count=30)
        assembly, middleware = build_counting_assembly(catalog)
        ctx = make_ctx()

        assembly.get_chat_prompt_template(ctx)
        shared_cache = ctx.assembly_cache
        assembly.get_chat_prompt_variables(ctx)

        assert shared_cache is ctx.assembly_cache
        assert shared_cache[DIRECTORY_CACHE_KEY][catalog] == middleware.render_directory()


class BrokenTokenizerLlm:
    """任何 token 估算调用都会硬失败，用来证明中间件不碰 llm tokenizer。"""

    def __init__(self):
        self.get_num_tokens_calls = 0

    def get_num_tokens(self, text):  # noqa: ANN001
        self.get_num_tokens_calls += 1
        raise AssertionError("middleware must not call get_num_tokens")


class TestNoObservability:
    """中间件不写日志、不做 token 估算（AC-18 延后到观测接线）。"""

    def test_never_touches_llm_tokenizer_and_binds_all(self):
        catalog = make_catalog(deferred_count=30)
        assembly = build_assembly(catalog)
        llm = BrokenTokenizerLlm()
        ctx = ProcessorContext(state={"messages": []}, config={}, llm=llm)

        tools = assembly.get_choice_tools(ctx)
        assembly.get_chat_prompt_template(ctx)

        assert [t.name for t in tools] == ["tool_describe", "tool_call"]
        assert llm.get_num_tokens_calls == 0
        assert rendered_system(ctx).endswith(render_for(catalog))

    def test_emits_no_logs(self, caplog):
        catalog = make_catalog(deferred_count=30)
        logger_name = "aidev_agent.core.graphs.react.tool_lazy_loading_middleware"
        with caplog.at_level(logging.DEBUG, logger=logger_name):
            run_pipelines(build_assembly(catalog))

        assert [r for r in caplog.records if r.name == logger_name] == []

    @pytest.mark.parametrize("name", ["estimate_tokens", "_thread_id", "_log_active", "_schemas_text"])
    def test_observability_symbols_absent(self, name):
        owner = middleware_module if name in {"estimate_tokens", "_thread_id"} else ToolDirectoryMiddleware
        assert not hasattr(owner, name)


class TestBusinessMetaNameBinding:
    @pytest.mark.parametrize("name", ["tool_call", "tool_describe"])
    def test_binding_preserves_business_and_actual_meta_identity(self, name):
        """业务工具占元工具名：header 用固定名，业务同名工具行按自己的名字出现在目录里。"""
        business = [FakeTool(name=name), FakeTool(name="padding")]
        catalog = LazyToolCatalog(deferred_tools=[t for t in business if t is not business[1]])
        _, system, _ = run_pipelines(build_assembly(catalog))
        assert f"- {name}: fake" in system
        header = system.split("# 可延迟加载的工具")[1].split("\n")[1]
        assert " tool_describe(names=[...])" in header and " tool_call(name=..., arguments=" in header

    def test_header_names_are_fixed_under_business_collision(self):
        """业务工具占满原名与让名前缀名：header 仍是固定名，业务工具行按自己的名字出现。"""
        occupied = ["tool_describe", "tool_call", "aidev_lazy__tool_describe", "aidev_lazy__tool_call"]
        business = [FakeTool(name=name) for name in occupied]
        catalog = LazyToolCatalog(deferred_tools=[t for t in business if t is not business[1]])
        _, system, _ = run_pipelines(build_assembly(catalog))
        # tool_call 在目录里是同名的延迟业务工具（不再被当成元工具改名）；其余三个按原名出现
        listed = ["tool_describe", "aidev_lazy__tool_describe", "aidev_lazy__tool_call"]
        assert all(f"- {name}: fake" in system for name in listed)
        assert " tool_describe(names=[...])" in system and " tool_call(name=..., arguments=" in system
