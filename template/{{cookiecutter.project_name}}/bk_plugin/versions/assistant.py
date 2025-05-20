"""
通用 assistant agent 插件。

若非定制开发，只修改 assistant_components.py 文件即可，请勿修改本文件。
"""

from bk_plugin_framework.kit import (
    Context,
    ContextRequire,
    Field,
    FormModel,
    InputsModel,
    OutputsModel,
    Plugin,
)
from langchain_openai.chat_models.base import _convert_message_to_dict


class CommonAgent(Plugin):
    class Meta:
        # 固定,不需要修改,一旦修改会影响访问路径
        version = "1.0.0assistant"
        desc = "Common AI agent from AIDev"

    class Inputs(InputsModel):
        command: str | None
        input: str | None
        session_code: str | None
        chat_history: list | None
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
        # TODO:  build agent and run
        agent_e, cfg = self.create_agent_instance(inputs)
        ret = agent_e.invoke(inputs.dict(), config=cfg)
        ret["chat_history"] = [_convert_message_to_dict(m) for m in ret["chat_history"]]
        context.outputs = ret
