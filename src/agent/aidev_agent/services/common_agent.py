from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Dict, Tuple

from aidev_agent.core.graphs.react.graph import ReActAgentBuilder
from aidev_agent.services.pydantic_models import AgentExecutorKwargs

if TYPE_CHECKING:
    from langchain_core.runnables import Runnable, RunnableConfig

    from aidev_agent.services.pydantic_models import AgentExecutorKwargs


class CommonQAAgent:
    """
    普通用户直接使用 CommonQAAgent 即可，会进行 agent 自适应路由
    高级用户需根据使用情况继承不同的 agent，并在 CommonQAAgent 中注册使用
    NOTE: 这里先继承自 ToolCallingCommonQAAgent，因为 aidev.resource.chat_completion.logic.ChatCompletionApp.get_window
    中需要使用到 ensure_memory_window。待开发侧确认各类需要使用 CommonQAAgent 成员函数/属性的场景。
    """

    agent_classes: ClassVar[Dict] = {}

    @classmethod
    def register_agent_class(cls, key, agent_class):
        cls.agent_classes[key] = agent_class

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
        builder = ReActAgentBuilder().set_bkai_options(options)
        agent, cfg = builder.build()
        return agent, cfg
