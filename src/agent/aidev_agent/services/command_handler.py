import logging
from abc import ABC, abstractmethod

from aidev_agent.utils.renderer import SafeJinjaEnvironment

logger = logging.getLogger("agent_command")

"""
新版快捷指令前后端协议
{
    "session_code": session_code,
    "role": "user",
    "content": "xxxx",
    "property": {
        "extra": {
            "cite": "待翻译文本: 你好, 语言: english",
            "command": "translate",
            "context": [
                {
                    "content": "你好",
                    "context_type": "textarea",
                    "__label": "待翻译文本",
                    "__key": "content",
                    "__value": "你好"
                },
                {
                    "language": "english",
                    "context_type": "select",
                    "__label": "语言",
                    "__key": "language",
                    "__value": "english"
                }
            ],
            "anchor_path_resources": {

            }
        }
    }
}
"""


class CommandHandler(ABC):
    """
    快捷指令处理器基类
    """

    agent_code = None  # 智能体代码
    command = None  # 指令名称

    def __init__(self):
        self.jinja_env = SafeJinjaEnvironment()

    @abstractmethod
    def get_template(self) -> str:
        """获取命令对应的提示词模板"""

    def extract_context_vars(self, context: list[dict]) -> dict[str, str]:
        """
        从上下文中提取模板变量（通用实现可被重写）
        """
        variables = {}
        for item in context:
            if "__key" in item and "__value" in item:
                variables[item["__key"]] = item["__value"]
        return variables

    def process_content(self, context: list[dict]) -> str:
        """
        处理内容（使用Jinja2模板和变量）
        """
        template = self.get_template()
        variables = self.extract_context_vars(context)

        return self.jinja_env.render(template, variables)


class TranslateCommandHandler(CommandHandler):
    """
    快捷指令: 翻译
    keyword: language 目标语言
    keyword: content 待翻译的内容
    """

    command = "translate"

    def get_template(self) -> str:
        return """
        请将以下内容翻译为{{ language }}:
        {{ content }}
        翻译要求: 确保翻译准确无误，无需冗余回答内容
        """

    def extract_context_vars(self, context: list[dict]) -> dict[str, str]:
        variables = super().extract_context_vars(context)
        # 特殊处理：确保必须有content变量
        if "content" not in variables:
            raise ValueError("Translation requires 'content' in context")
        return variables


class ExplanationCommandHandler(CommandHandler):
    """
    快捷指令: 解释
    keyword: content 待解释的内容
    """

    command = "explanation"

    def get_template(self) -> str:
        return """
        请解释以下内容{{ content }}
        解释要求: 确保解释准确无误，无需冗余回答内容
        """


class CommonCommandHandler(CommandHandler):
    def __init__(self, command: str, template: str):
        super().__init__()
        self._template = template
        self.command = command

    def get_template(self) -> str:
        return self._template


class CommonCommandHandlerBuilder:
    @classmethod
    def build(cls, command_id, command_template) -> CommonCommandHandler:
        return CommonCommandHandler(command_id, command_template)


class CommandProcessor:
    _handlers: dict[str, type[CommandHandler]] = {}

    @classmethod
    def register_handler(cls, command: str, handler: type[CommandHandler]):
        """
        注册快捷指令
        """
        cls._handlers[command] = handler

    def process_command(self, command_data: dict) -> str:
        """
        处理快捷指令
        """
        if not (command := command_data.get("command")):
            logger.warning("CommandProcessor: No command found in data->[%s]", command_data)
            raise ValueError("No command found in data")

        if (handler_class := self._handlers.get(command)) is None:
            logger.warning("CommandProcessor: No handler registered for command->[%s]", command)
            raise ValueError(f"No handler registered for command: {command}")

        try:
            logger.info("CommandProcessor: Processing command->[%s]", command)
            return handler_class().process_content(command_data.get("context", []))
        except ValueError as e:
            logger.warning("CommandProcessor: Command processing failed->[%s]", str(e))
            raise e


# 注册处理器 exsample
# CommandProcessor.register_handler("translate", TranslateCommandHandler)
# CommandProcessor.register_handler("explanation", ExplanationCommandHandler)
