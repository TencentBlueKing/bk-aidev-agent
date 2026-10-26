# -*- coding: utf-8 -*-
"""延迟加载元工具：按名称描述工具，以及由 ToolNode 解包执行的单工具代理。"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, List, Optional

from langchain_core.tools import BaseTool, InjectedToolArg, InjectedToolCallId, ToolException
from langgraph.prebuilt.tool_node import ToolRuntime
from pydantic import BaseModel, ConfigDict, Field
from pydantic.json_schema import SkipJsonSchema

from .catalog import LazyToolCatalog

logger = logging.getLogger(__name__)

# 元工具的固定生效名：工厂构造的实例恒用这两个名字，不随 catalog 内容改动
DESCRIBE_TOOL_NAME = "tool_describe"
CALL_TOOL_NAME = "tool_call"
META_TOOL_NAMES: frozenset[str] = frozenset({DESCRIBE_TOOL_NAME, CALL_TOOL_NAME})

_INJECTED_RUNTIME = Annotated[ToolRuntime, SkipJsonSchema(), InjectedToolArg]


class ToolDescribeInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    names: List[str] = Field(description="工具名列表，按名称精确匹配（支持一次传多个）")
    runtime: _INJECTED_RUNTIME = None
    tool_call_id: Annotated[str, InjectedToolCallId] = ""


class ToolCallInput(BaseModel):
    """一次只执行一个工具，不接受旧的 calls 列表。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    name: str = Field(min_length=1, description="目标工具名")
    arguments: dict = Field(default_factory=dict, description="目标工具的参数对象")
    runtime: _INJECTED_RUNTIME = None
    tool_call_id: Annotated[str, InjectedToolCallId] = ""


DESCRIBE_DESCRIPTION = (
    "获取「可延迟加载的工具」目录中工具的描述与完整参数 JSON Schema。"
    "只读取已装配的工具定义，不执行目标工具、不触发远程连接。"
    '先调用 tool_describe(names=["工具名"]) 获取 schema，'
    '再调用 tool_call(name="工具名", arguments={...}) 执行；不要直接调用目录中的工具名。'
    "names 可一次传多个；不存在或不可见的名字逐条返回 error。"
)

CALL_DESCRIPTION = (
    "执行「可延迟加载的工具」目录中的一个工具，经过与标准 tool call 相同的"
    "工具级审批、命令级安全校验、结果截断与脱敏、去重与超时链路。"
    '先用 tool_describe 获取参数 schema，再用 tool_call(name="工具名", arguments={...}) 执行；'
    "已明确参数时可直接调用。入参是 name 与 arguments，每次只执行一个工具；"
    "需要多个工具时请分多次调用，不接受工具列表。"
    "原样返回目标工具结果和状态更新，目标工具抛异常时原样抛出，不将失败包装成成功。"
    "不要直接调用目录中的工具名；不可经本工具执行 tool_describe / tool_call 自身。"
)


class ToolDescribeTool(BaseTool):
    name: str = DESCRIBE_TOOL_NAME
    description: str = DESCRIBE_DESCRIPTION
    args_schema: type[BaseModel] = ToolDescribeInput
    catalog: Any = None

    def _run(
        self, names: Optional[List[str]] = None, runtime: Any = None, tool_call_id: str = "", **kwargs: Any
    ) -> str:
        return self._describe(names or [])

    async def _arun(
        self, names: Optional[List[str]] = None, runtime: Any = None, tool_call_id: str = "", **kwargs: Any
    ) -> str:
        return self._describe(names or [])

    def _describe(self, names: List[str]) -> str:
        results = (
            self.catalog.describe(names)
            if self.catalog is not None
            else [{"name": name, "error": "延迟工具目录不可用"} for name in names]
        )
        logger.info("[ToolLazyLoading] describe names=%s ok=%s", names, sum("error" not in item for item in results))
        return json.dumps({"results": results}, ensure_ascii=False, default=str)


class ToolCallTool(BaseTool):
    """单工具代理的 schema 载体：执行由 ToolNode 在包装链之前解包为目标工具调用。

    能走到本体的只有不可执行目标（不存在 / 不可见 / 元工具自身），统一报错。
    """

    name: str = CALL_TOOL_NAME
    description: str = CALL_DESCRIPTION
    args_schema: type[BaseModel] = ToolCallInput
    catalog: Any = None
    # describe 元工具的实际实例名：错误提示用它，不持有 describe 实例
    describe_tool_name: str = DESCRIBE_TOOL_NAME

    def _run(self, name: str, arguments: Optional[dict] = None, **kwargs: Any) -> str:
        raise ToolException(self._error(name))

    async def _arun(self, name: str, arguments: Optional[dict] = None, **kwargs: Any) -> str:
        raise ToolException(self._error(name))

    def _error(self, name: str) -> str:
        if self.catalog is None:
            return "延迟工具目录不可用"
        logger.info("[ToolLazyLoading] tool_call rejected name=%s", name)
        return f"工具 {name} 不存在或当前不可执行，请先调用 {self.describe_tool_name} 确认可用工具"


def make_meta_tools(catalog: LazyToolCatalog | None = None) -> tuple[ToolDescribeTool, ToolCallTool]:
    """构造元工具二元组：固定 SDK 标准名，不读 catalog 内容、不改名、不改描述。

    元工具名是稳定契约（模型提示词、审批、日志都依赖它）；与业务工具重名时由装配层
    在目录快照之前给业务副本让名，工厂本身**不修改**传入的 catalog，也不改写 catalog。
    """
    return ToolDescribeTool(catalog=catalog), ToolCallTool(catalog=catalog)
