# -*- coding: utf-8 -*-
"""延迟工具目录（Catalog）。

`LazyToolCatalog` 是延迟工具与 schema 查询的唯一事实源：只持有装配期过滤后的延迟工具快照，
提供「延迟集合 / 按名取 schema / 按名取可执行工具」查询；内置工具直接绑定，不在此处。
快照在构造后不再变化：元工具实例不进入本类（不持有、不登记、不引用），
故本类与元工具、ToolNode 之间不存在任何反向依赖；调用方从 ``meta_tools`` 工厂取元工具二元组。
**是否启用延迟加载不在这里判定**：由装配层（``graph._prepare_agent_tools``）一次性决定，
只有在判定为启用时才会构造本类并安装目录中间件，本类不读任何配置。

目录文本的渲染由 `ToolDirectoryMiddleware` 负责，本类不承担任何 prompt 拼接职责。
"""

from __future__ import annotations

import copy
from typing import Any, List, Optional, Sequence

from langchain_core.tools import BaseTool


def _tool_name(tool: Any) -> str:
    try:
        name = getattr(tool, "name", "")
    except AttributeError:
        return ""
    return name if isinstance(name, str) else ""


class LazyToolCatalog:
    """延迟加载模式下的工具目录。

    只持有延迟工具：内置工具直接绑定给模型，``tool_describe`` / ``tool_call`` 不覆盖它们。

    Args:
        deferred_tools: 装配期过滤、去重后的延迟工具快照（外部工具，不含内置与元工具）。
    """

    def __init__(self, *, deferred_tools: Sequence[BaseTool]) -> None:
        self._deferred_tools: List[BaseTool] = list(deferred_tools)

    # ------------------------------------------------------------------
    # 集合查询
    # ------------------------------------------------------------------
    def deferred(self) -> List[BaseTool]:
        """延迟工具（描述进目录、schema 按需取）。"""
        return list(self._deferred_tools)

    # ------------------------------------------------------------------
    # describe
    # ------------------------------------------------------------------
    def describe(self, names: Sequence[str]) -> List[dict]:
        """按名称返回工具的描述与完整参数 schema（不执行工具、不建立远程连接）。"""
        by_name = {_tool_name(t): t for t in self._deferred_tools}
        results: List[dict] = []
        for name in names:
            tool = by_name.get(name)
            if tool is None:
                results.append({"name": name, "error": f"工具 {name} 不存在或当前不可见，无法获取参数定义"})
                continue
            results.append(
                {
                    "name": name,
                    "description": getattr(tool, "description", "") or "",
                    "parameters": self.parameters_schema(tool),
                }
            )
        return results

    def executable(self, name: str) -> Optional[BaseTool]:
        """``tool_call`` 可代为执行的延迟工具。

        只按名查延迟快照：内置工具、元工具与代理工具从不在快照里，递归代理因此天然不可执行，无需名字白名单。
        """
        for tool in self._deferred_tools:
            if _tool_name(tool) == name:
                return tool
        return None

    @staticmethod
    def parameters_schema(tool: Any) -> dict:
        """工具的完整参数 JSON Schema（不实例化、不触发远程初始化）。

        ``args_schema`` 为 dict 时（MCP / 平台工具常见形态）原样深拷贝返回，required / $defs 不丢。
        """
        schema = getattr(tool, "tool_call_schema", None)
        if isinstance(schema, dict):
            return copy.deepcopy(schema)
        if schema is not None and hasattr(schema, "model_json_schema"):
            return schema.model_json_schema()
        args_schema = getattr(tool, "args_schema", None)
        if isinstance(args_schema, dict):
            return copy.deepcopy(args_schema)
        if isinstance(args_schema, type):
            return args_schema.model_json_schema()
        return {"type": "object", "properties": {}}
