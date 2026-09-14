from __future__ import annotations

from typing import TYPE_CHECKING, Tuple

from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.pydantic_models import AgentExecutorKwargs

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable, RunnableConfig


class CommonQAAgent:
    """SDK 默认通用智能体实现，与 ``CommonAgentProtocol`` 结构兼容。

    自定义场景：继承本类并重写 :meth:`get_agent_executor`，在 plugin 的 ``apps.ready`` 中
    通过 ``common_agent_factory.replace_defaults(MyAgent())`` 注入实例。
    """

    @classmethod
    def get_agent_executor(cls, **kwargs) -> Tuple["Runnable", "RunnableConfig"]:
        """创建 Agent 执行器（graph + runnable config）。

        - ChatCompletionAgent 会传入来自 BkAi 配置平台的“通用 kwargs”。
        - CommonQAAgent 在这里统一将 kwargs 标准化为 `AgentExecutorKwargs`（支持 extra='allow' 透传扩展字段）。
        - 然后使用 `ReActAgentBuilder` 的 fluent API（set_bkai_options / set_xxx / add_xxx）完成构建。

        返回：
            (compiled_graph, runnable_config)
        """
        options = AgentExecutorKwargs.model_validate(kwargs)
        builder = ReActAgentBuilder().set_bkai_options(options)  # .enable_security_runtime(False)
        agent, cfg = builder.build()
        return agent, cfg
