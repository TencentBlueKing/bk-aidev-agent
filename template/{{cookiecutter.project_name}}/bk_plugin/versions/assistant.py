"""
通用 assistant agent 插件入口
"""

from logging import getLogger

from aidev_agent.core.utils.local import request_local
from aidev_bkplugin.services.agent import run_bkplugin_invoke
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

logger = getLogger(__name__)


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
        execute_kwargs: dict | None = None

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
        execute_kwargs = {
            "type": "object",
            "title": "工单调用信息",
            "properties": {
                "caller_bk_app_code": {"type": "string", "title": "调用者BK应用ID"},
                "caller_bk_biz_env": {"type": "string", "title": "调用者BK业务环境"},
                "caller_bk_biz_id": {"type": "number", "title": "调用者BK业务ID"},
                "caller_executor": {"type": "string", "title": "调用人"},
                "caller_order_type": {"type": "string", "title": "调用AI工单类型"},
            },
        }

    def execute(self, inputs: Inputs, context: Context):
        logger.info(f"inputs: {inputs}")
        username = None
        if context.data.executor:
            user = get_user_model().objects.filter(username=context.data.executor).first()
            if user:
                request_local.request.user = user
                username = user.username
        execute_kwargs = inputs.execute_kwargs or {}
        if inputs.session_code:
            execute_kwargs["session_code"] = inputs.session_code
        result = run_bkplugin_invoke(
            inputs.chat_history or [],
            execute_kwargs,
            inputs.input or "",
            username=username,
        )
        if not isinstance(result, str):
            context.outputs = {"output": result["choices"][0]["delta"]["content"]}
        else:
            context.outputs = {"output": result}
