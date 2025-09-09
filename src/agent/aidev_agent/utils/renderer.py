from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


class SafeJinjaEnvironment:
    _instance = None
    _env = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 创建安全的沙盒环境
            cls._env = SandboxedEnvironment(
                undefined=StrictUndefined,  # 严格模式，未定义变量时抛出异常
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )
            # 禁用危险的全局函数
            cls._env.globals.clear()
        return cls._instance

    def render(self, template_str: str, variables: dict) -> str:
        """安全渲染模板"""
        try:
            template = self._env.from_string(template_str)
            return template.render(**variables).strip()
        except Exception as e:
            raise ValueError(f"Template rendering failed: {str(e)}")
