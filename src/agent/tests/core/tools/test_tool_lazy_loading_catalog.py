# -*- coding: utf-8 -*-
"""延迟工具目录（REQ-2 / REQ-3 / REQ-9；AC-1 / AC-12 / AC-13 / AC-19）。

集合与 schema 查询的唯一事实源：目录中间件与绑定裁剪共用本类；
目录文本渲染在 ToolDirectoryMiddleware，本类不承担任何 prompt 拼接职责。
是否启用延迟加载由装配层（graph）一次性判定，本类不读配置、也不判定阈值。
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest
from aidev_agent.core.tools.tool_lazy_loading import catalog as catalog_module
from aidev_agent.core.tools.tool_lazy_loading.catalog import LazyToolCatalog
from aidev_agent.core.tools.tool_lazy_loading.meta_tools import (
    CALL_DESCRIPTION,
    CALL_TOOL_NAME,
    DESCRIBE_DESCRIPTION,
    DESCRIBE_TOOL_NAME,
    META_TOOL_NAMES,
    make_meta_tools,
)
from langchain_core.tools import BaseTool
from langgraph.prebuilt.tool_node import ToolNode


class FakeTool(BaseTool):
    """最小可用工具：只提供 name / description。"""

    name: str
    description: str = "fake tool"

    def _run(self, **kwargs) -> str:
        return "ok"


def make_tools(count: int, *, prefix: str = "tool", description: str = "desc") -> list[FakeTool]:
    return [FakeTool(name=f"{prefix}_{index}", description=f"{description}-{index}") for index in range(count)]


def make_catalog(*, tools) -> LazyToolCatalog:
    return LazyToolCatalog(deferred_tools=tools)


def factory_does_not_touch(catalog: LazyToolCatalog) -> bool:
    """纯工厂自证：调用后快照长度与实例身份序列逐项不变，且无新增实例字段。"""
    before_ids = [id(tool) for tool in catalog.deferred()]
    before_fields = set(vars(catalog))
    make_meta_tools(catalog)
    return [id(tool) for tool in catalog.deferred()] == before_ids and set(vars(catalog)) == before_fields


class TestVisibleSets:
    """可见 / 内置 / 延迟集合划分（REQ-2 / REQ-3）。"""

    def test_visible_is_original_snapshot_after_factory(self):
        """快照在工厂调用前后逐项不变：元工具永远不进可见集合。"""
        tools = make_tools(3)
        catalog = make_catalog(tools=tools)
        ids_before = [id(tool) for tool in catalog.deferred()]
        describe_tool, call_tool = make_meta_tools(catalog)
        assert [id(tool) for tool in catalog.deferred()] == ids_before
        assert catalog.deferred() == tools
        assert not ({id(describe_tool), id(call_tool)} & {id(tool) for tool in catalog.deferred()})
        assert set(META_TOOL_NAMES) == {DESCRIBE_TOOL_NAME, "tool_call"}

    def test_builtin_names_not_describable_or_executable(self):
        """内置工具不在 catalog：tool_describe / tool_call 按名查不到，只覆盖延迟工具。"""
        builtin = FakeTool(name="builtin_a")
        catalog = make_catalog(tools=make_tools(2))
        assert catalog.executable(builtin.name) is None
        assert "error" in catalog.describe([builtin.name])[0]
        assert catalog.executable("tool_0") is not None

    def test_catalog_does_not_filter(self):
        """catalog 不做请求级过滤：可见集合恒为装配期定型的快照（过滤在装配期完成）。"""
        tools = make_tools(5)
        catalog = make_catalog(tools=tools)
        assert factory_does_not_touch(catalog)

        assert [t.name for t in catalog.deferred()] == [f"tool_{index}" for index in range(5)]


class TestDescribe:
    """按名取 schema（REQ-4 的 catalog 侧）。"""

    def test_describe_returns_schema_and_error_per_name(self):
        catalog = make_catalog(tools=[FakeTool(name="known", description="已知工具")])
        results = catalog.describe(["known", "unknown"])
        assert results[0]["name"] == "known"
        assert results[0]["description"] == "已知工具"
        assert results[0]["parameters"]["type"] == "object"
        assert "error" in results[1] and results[1]["name"] == "unknown"

    def test_describe_never_executes_tool(self):
        """describe 只读定义，不触发 _run。"""
        calls: list[str] = []

        class CountingTool(FakeTool):
            def _run(self, **kwargs) -> str:
                calls.append(self.name)
                return "ok"

        tool = CountingTool(name="counting", description="d")
        catalog = make_catalog(tools=[tool])
        catalog.describe(["counting"])
        assert calls == []

    def test_executable_excludes_meta_tools(self):
        """元工具名不在原始快照里，``executable`` 自然拒绝，无需名字白名单。"""
        tools = make_tools(2)
        catalog = make_catalog(tools=tools)
        describe_tool, call_tool = make_meta_tools(catalog)
        assert catalog.executable("tool_0") is tools[0]
        assert catalog.executable(describe_tool.name) is None
        assert catalog.executable(call_tool.name) is None
        assert catalog.executable("missing") is None


class TestCatalogRegressions:
    @pytest.mark.parametrize("name", ["tool_call", "tool_describe"])
    def test_unregistered_meta_name_is_business_tool(self, name):
        business = FakeTool(name=name)
        catalog = make_catalog(tools=[business])
        assert catalog.deferred() == [business]
        assert catalog.executable(name) is business
        assert "error" not in catalog.describe([name])[0]

    @pytest.mark.parametrize("name", ["tool_call", "tool_describe"])
    def test_factory_keeps_standard_names_when_business_tools_occupy_them(self, name):
        """业务工具占名（含首选让名前缀）时工厂仍返回固定标准名、描述原样，业务同名工具仍可执行。"""
        business = [FakeTool(name=name), FakeTool(name=f"aidev_lazy__{name}")]
        catalog = make_catalog(tools=business)
        describe, call = make_meta_tools(catalog)
        assert {describe.name, call.name} == set(META_TOOL_NAMES)
        assert catalog.deferred() == business
        assert catalog.executable(name) is business[0]
        assert catalog.executable(f"aidev_lazy__{name}") is business[1]
        assert {describe.description, call.description} == {DESCRIBE_DESCRIPTION, CALL_DESCRIPTION}

    def test_factory_does_not_mutate_catalog_or_returned_objects(self):
        """工厂纯性：调用后 catalog 字段与快照身份序列不变，返回对象名 / 描述恒为固定值。"""
        from aidev_agent.core.tools.tool_lazy_loading.meta_tools import make_meta_tools as factory

        tools = [FakeTool(name=name, description="业务描述") for name in (*META_TOOL_NAMES, "other")]
        catalog = make_catalog(tools=tools)
        assert factory_does_not_touch(catalog)
        describe, call = factory(catalog)
        assert (describe.name, call.name) == (DESCRIBE_TOOL_NAME, CALL_TOOL_NAME)
        assert (describe.description, call.description) == (DESCRIBE_DESCRIPTION, CALL_DESCRIPTION)
        assert [tool.description for tool in catalog.deferred()] == ["业务描述"] * 3

    def test_dict_schema_preserves_required_and_defs_without_aliasing(self):
        schema = {
            "type": "object",
            "properties": {"query": {"$ref": "#/$defs/Query"}},
            "required": ["query"],
            "$defs": {"Query": {"type": "string"}},
        }
        target = FakeTool(name="dictionary", args_schema=schema)
        catalog = make_catalog(tools=[target])
        parameters = catalog.describe([target.name])[0]["parameters"]
        assert parameters == target.tool_call_schema
        parameters["required"].clear()
        assert schema["required"] == ["query"]

    def test_business_metadata_cannot_claim_builtin_origin(self):
        business = FakeTool(name="business", metadata={"sdk_builtin_tool": True})
        catalog = make_catalog(tools=[business])
        assert catalog.deferred() == [business]


# 元工具名一律由调用方从 ``meta_tools`` 精确二元组取各实例的 name，catalog 不再提供名字访问器
META_NAME_ACCESSORS = ["meta_describe_name", "meta_call_name"]

RENDERING_ATTRIBUTES = [
    "directory_text",
    "directory_header",
    "_directory_cache",
    "DIRECTORY_HEADER_TEMPLATE",
    "DIRECTORY_DESCRIPTION_LIMIT",
]


class TestNoMetaNameAccessors:
    """catalog 不提供元工具名访问器：连类属性也不存在，也不提供空目录时的默认名回落。"""

    @pytest.mark.parametrize("name", META_NAME_ACCESSORS)
    def test_accessor_absent_on_class_and_instance(self, name):
        catalog = make_catalog(tools=make_tools(2))
        assert factory_does_not_touch(catalog)
        assert not hasattr(LazyToolCatalog, name)
        assert not hasattr(catalog, name)

    @pytest.mark.parametrize("name", META_NAME_ACCESSORS)
    def test_accessor_absent_when_meta_tools_empty(self, name):
        """没有任何元工具登记位，也不回落到默认名：没有可造假的名字来源。"""
        catalog = make_catalog(tools=make_tools(2))
        assert not hasattr(catalog, "meta_tools")
        assert not hasattr(LazyToolCatalog, name)
        assert not hasattr(catalog, name)


# 已删除的反向引用 API：catalog 不得再持有元工具 / ToolNode，也不得回填快照
REMOVED_BACKREF_API = ["meta_tools", "meta_tool_names", "tool_node", "_is_meta", "set_all_tools"]
META_CONSTANTS = ["DESCRIBE_TOOL_NAME", "CALL_TOOL_NAME", "META_TOOL_NAMES"]


class TestNoReverseReferences:
    """catalog 是原始快照：类与实例都不再有元工具 / ToolNode 反向引用（环一 / 环二同时切断）。"""

    @pytest.mark.parametrize("name", REMOVED_BACKREF_API)
    def test_backref_api_absent_on_class_and_instance(self, name):
        catalog = make_catalog(tools=make_tools(2))
        make_meta_tools(catalog)
        assert not hasattr(LazyToolCatalog, name)
        assert not hasattr(catalog, name)

    @pytest.mark.parametrize("name", META_CONSTANTS)
    def test_meta_name_constants_not_known_by_catalog(self, name):
        """默认名常量迁到 meta_tools：catalog 模块不再知道任何元工具名。"""
        assert not hasattr(catalog_module, name)

    def test_instance_holds_no_tool_or_node_instances(self):
        """实例字段只保留原始工具，嵌套列表不含元工具或执行节点。"""
        tools = make_tools(2)
        catalog = make_catalog(tools=tools)
        describe_tool, call_tool = make_meta_tools(catalog)
        values = [value for value in vars(catalog).values() if not isinstance(value, (str, frozenset))]
        nested = [item for value in values if isinstance(value, list) for item in value] + values
        assert tools and {id(tool) for tool in nested if isinstance(tool, BaseTool)} == {id(tool) for tool in tools}
        assert not [value for value in nested if isinstance(value, ToolNode)]


class TestNoRenderingResponsibility:
    """catalog 只做查询：不得残留 prompt 渲染方法、截断常量与缓存。"""

    @pytest.mark.parametrize("name", RENDERING_ATTRIBUTES)
    def test_catalog_has_no_rendering_attributes(self, name):
        catalog = make_catalog(tools=make_tools(2))
        assert factory_does_not_touch(catalog)
        assert not hasattr(LazyToolCatalog, name)
        assert not hasattr(catalog, name)
        assert not hasattr(catalog_module, name)

    @pytest.mark.parametrize("name", ["is_active", "enabled", "threshold", "_use_structured_response"])
    def test_catalog_has_no_runtime_switch(self, name):
        """是否启用由装配层一次性判定：catalog 不得残留开关位或阈值判定。"""
        assert not hasattr(LazyToolCatalog, name)
        assert not hasattr(make_catalog(tools=make_tools(1)), name)

    def test_catalog_constructor_takes_no_structured_response(self):
        """structured_chat 判定已上移到 graph：构造器不再接收该参数。"""
        assert "use_structured_response" not in inspect.signature(LazyToolCatalog.__init__).parameters

    def test_catalog_does_not_import_config(self):
        """catalog 不读配置：不得 import aidev_agent.config（否则可能重新长出阈值判定）。"""
        tree = ast.parse(Path(catalog_module.__file__).read_text(encoding="utf-8"))
        modules = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        modules |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        assert not [m for m in modules if m in {"aidev_agent.config", "aidev_agent.config.settings"}]

    def test_catalog_does_not_import_graphs(self):
        """catalog 侧依赖方向不变：不得反向 import graphs / nodes 侧模块。"""
        tree = ast.parse(Path(catalog_module.__file__).read_text(encoding="utf-8"))
        modules = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        modules |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        assert not [m for m in modules if m.startswith(("aidev_agent.core.graphs", "aidev_agent.core.nodes"))]
