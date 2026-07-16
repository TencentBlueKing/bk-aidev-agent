"""
通用 assistant agent 插件入口

- 1.0.0assistant：同步调用，5 分钟超时限制
- 2.0.0sse：流式轮询，基于 wait_poll 机制突破超时限制
"""

from logging import getLogger
from typing import Any

from aidev_agent.enums import AgentType
from aidev_bkplugin.enums import PluginPollTaskState
from aidev_bkplugin.services import (
    build_bkplugin_runner_from_plugin,
    poll_bkplugin_agent,
    record_plugin_poll_failure,
)
from bk_plugin_framework.constants import State
from bk_plugin_framework.kit import (
    Context,
    ContextRequire,
    Field,
    FormModel,
    InputsModel,
    OutputsModel,
    Plugin,
)

logger = getLogger(__name__)
POLL_INTERVAL_SECONDS = 5


class CommonInputsFormMixin:
    input = {
        "ui:component": {
            "name": "bk-input",
            "props": {"type": "string", "placeholder": "本轮提问内容"},
        }
    }
    session_code = {
        "ui:component": {
            "name": "bk-input",
            "props": {"type": "string", "placeholder": "会话 ID，多轮续聊时填写，单轮建议留空"},
        }
    }
    command = {
        "ui:component": {
            "name": "bk-input",
            "props": {"type": "string", "placeholder": "命令 -- 快捷指令调用"},
        }
    }
    chat_history = {
        "type": "array",
        "title": "chat_history",
        "items": {
            "type": "object",
            "title": "history",
            "properties": {
                "role": {
                    "type": "string",
                    "title": "role",
                    "ui:component": {
                        "name": "bk-input",
                        "props": {"type": "string", "placeholder": "消息角色，如 user / assistant / system"},
                    },
                },
                "content": {
                    "type": "string",
                    "title": "content",
                    "ui:component": {
                        "name": "bk-input",
                        "props": {"type": "string", "placeholder": "该条历史消息的文本内容"},
                    },
                },
            },
        },
    }
    execute_kwargs = {
        "type": "object",
        "title": "工单调用信息",
        "properties": {
            "caller_bk_app_code": {"type": "string", "title": "调用者BK应用ID"},
            "caller_bk_biz_env": {"type": "string", "title": "调用者BK业务环境"},
            "caller_bk_biz_id": {"type": "string", "title": "调用者BK业务ID"},
            "caller_executor": {"type": "string", "title": "调用人"},
            "caller_order_type": {"type": "string", "title": "调用AI工单类型"},
        },
    }


class AssistantInputs(InputsModel):
    """须在 InputsModel 上用 Field 声明，否则 schema 无 chat_history，InputsForm 合并会 KeyError。"""

    command: str | None = Field(default=None, title="command")
    input: str | None = Field(default=None, title="input")
    session_code: str | None = Field(default=None, title="session_code")
    chat_history: list[dict[str, Any]] | None = Field(default=None, title="chat_history")
    context: list[Any] | None = Field(default=None, title="context")
    execute_kwargs: dict[str, Any] | None = Field(default=None, title="execute_kwargs")


class AssistantOutputs(OutputsModel):
    intermediate_steps: list[Any] = Field(default_factory=list, title="intermediate_steps")
    chat_history: list[Any] = Field(default_factory=list, title="chat_history")
    output: str = Field(default="", title="output")
    input: str = Field(default="", title="input")
    session_code: str = Field(default="", title="session_code")


class AssistantContextInputs(ContextRequire):
    executor: str = Field(title="任务执行人")


# ---------------------------------------------------------------------------
# 1.0.0assistant — 同步版本
# ---------------------------------------------------------------------------


class CommonAgent(Plugin):
    class Meta:
        # 固定,不需要修改,一旦修改会影响访问路径
        version = "1.0.0assistant"
        desc = "Common AI agent from AIDev"

    Inputs = AssistantInputs
    Outputs = AssistantOutputs
    ContextInputs = AssistantContextInputs

    class InputsForm(CommonInputsFormMixin, FormModel):
        pass

    def execute(self, inputs: Inputs, context: Context):
        runner = build_bkplugin_runner_from_plugin(inputs, context)
        output = runner.execute()
        context.outputs = {
            "output": output,
            "input": inputs.input or "",
            "session_code": runner.session_code,
            "intermediate_steps": [],
            "chat_history": inputs.chat_history or [],
        }


# ---------------------------------------------------------------------------
# 2.0.0sse — 流式轮询版本
# ---------------------------------------------------------------------------


class CommonAgentSSE(Plugin):
    class Meta:
        version = "2.0.0sse"
        desc = "Common AI agent with streaming support via polling"

    Inputs = AssistantInputs
    Outputs = AssistantOutputs
    ContextInputs = AssistantContextInputs

    class InputsForm(CommonInputsFormMixin, FormModel):
        pass

    def execute(self, inputs: Inputs, context: Context):
        if context.state is State.EMPTY:
            return self._start_stream(inputs, context)
        if context.state is State.POLL:
            return self._poll_stream(inputs, context)
        logger.warning("[CommonAgentSSE] unexpected state=%s", context.state)

    def _start_stream(self, inputs: Inputs, context: Context):
        """EMPTY：先分流 chat/flow，再写入轮询上下文。"""
        storage = build_bkplugin_runner_from_plugin(inputs, context).dispatch_async()
        context.storage.update(storage)
        self.wait_poll(interval=POLL_INTERVAL_SECONDS)

    def _poll_stream(self, inputs: Inputs, context: Context):
        """POLL：后台 Agent 已在 EMPTY 阶段启动；这里只轮询主站直到结束。"""
        session_code = context.storage.get("session_code") or ""
        if not session_code:
            raise self.Error("poll 缺少 session_code")

        try:
            state, detail, agent_type = poll_bkplugin_agent(context.storage)
        except Exception as e:
            logger.exception("[CommonAgentSSE] poll error session_code=%s", session_code)
            record_plugin_poll_failure(context.storage, f"轮询主站失败: {e}")
            raise self.Error(f"轮询主站失败: {e}") from e

        if state == PluginPollTaskState.FAILED:
            record_plugin_poll_failure(context.storage, detail or "Agent 执行失败")
            raise self.Error(detail or "Agent 执行失败")
        if state == PluginPollTaskState.SUCCESS:
            output = detail or ""
            if agent_type is AgentType.FLOW and not output:
                logger.info(
                    "[CommonAgentSSE] flow finished without assistant output, session_code=%s",
                    session_code,
                )
            context.outputs = {
                "output": output,
                "input": inputs.input or "",
                "session_code": session_code,
                "intermediate_steps": [],
                "chat_history": inputs.chat_history or [],
            }
            return

        self.wait_poll(interval=POLL_INTERVAL_SECONDS)
