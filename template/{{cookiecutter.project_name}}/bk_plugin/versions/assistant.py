"""
通用 assistant agent 插件入口
"""

from aidev_agent.core.utils.local import request_local
from aidev_agent.services.chat import ChatPrompt, ExecuteKwargs
from aidev_bkplugin.services.agent import (
    build_chat_completion_agent_by_chat_history,
    get_agent_role_info,
)
from bk_plugin_framework.kit import (
    Context,
    ContextRequire,
    Field,
    FormModel,
    InputsModel,
    OutputsModel,
    Plugin,
)
from django.contrib.auth import get_user_model


class CommonAgent(Plugin):
    class Meta:
        # 固定,不需要修改,一旦修改会影响访问路径
        version = "1.0.0assistant"
        desc = "Common AI agent from AIDev"

    class Inputs(InputsModel):
        command: str | None
        input: str | None
        session_code: str | None
        chat_history: list[dict] | None
        context: list | None

    class Outputs(OutputsModel):
        intermediate_steps: list
        chat_history: list
        output: str
        input: str

    class ContextInputs(ContextRequire):
        executor: str = Field(title="任务执行人")

    class InputsForm(FormModel):
        command = {"ui:component": {"name": "bk-input", "props": {"type": "string"}}}
        input = {"ui:component": {"name": "bk-input", "props": {"type": "string"}}}
        session_code = {"ui:component": {"name": "bk-input", "props": {"type": "string"}}}
        chat_history = {
            "type": "array",
            "title": "chat_history",
            "items": {
                "type": "object",
                "title": "history",
                "properties": {
                    "role": {"type": "string", "title": "role"},
                    "content": {"type": "string", "title": "content"},
                },
            },
        }

    def execute(self, inputs: Inputs, context: Context):
        chat_history = (
            [ChatPrompt(role=each["role"], content=each["content"]) for each in inputs.chat_history]
            if inputs.chat_history
            else []
        )
        if context.data.executor:
            user = get_user_model().objects.filter(username=context.data.executor).first()
            if user:
                request_local.request.user = user
        role_contents = get_agent_role_info()
        if role_contents:
            chat_history = role_contents + chat_history
        if inputs.input:
            if inputs.chat_history:
                chat_history.append(ChatPrompt(role="user", content=inputs.input))
            else:
                chat_history = [ChatPrompt(role="user", content=inputs.input)]
        chat_completion_agent = build_chat_completion_agent_by_chat_history(chat_history)
        result = chat_completion_agent.execute(ExecuteKwargs(stream=False))
        if not isinstance(result, str):
            context.outputs = {"output": result["choices"][0]["delta"]["content"]}
        else:
            context.outputs = {"output": result}
