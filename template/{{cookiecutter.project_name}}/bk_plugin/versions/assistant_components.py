from typing import List

from pydantic import BaseModel


# --------------------------------------------配置区-------------------------------------------- #
# 使用的 LLM（联系接口人获取可使用的 LLM 模型名称列表）。
class PluginConfig(BaseModel):
    # 使用的 LLM（联系接口人获取可使用的 LLM 模型名称列表）。
    chat_model: str = "{{cookiecutter.chat_model}}"

    # 非深度思考模型
    non_thinking_llm: str = "{{cookiecutter.non_thinking_llm}}"

    # 在 AIDev 站点上传知识，然后将对应的知识库 ID 或者知识 ID 填在此处，可以在 agent 使用的时候检索对应范围的知识。
    # 通常来讲，选择的知识越多，检索速度也会越慢，检索效果也会越差。一般建议只选择该 agent 需要使用的知识，不要选择无关知识。
    knowledgebase_ids: List[int] = {{cookiecutter.knowledgebase_ids}}  # 知识库 ID 的列表
    knowledge_ids: List[int] = {{cookiecutter.knowledge_ids}}  # 知识（文件/文件夹） ID 的列表

    # 在 AIDev 站点注册工具，然后将对应的工具 ID 填在此处，可以在 agent 使用的时候调用相关工具。
    tool_codes: List[str] = {{cookiecutter.tool_codes}}

    # 在 CommonQAAgent 内置 prompt 的基础上，用户自定义的增量 prompt。
    # 目前内部实现方式是将用户自定义的增量 prompt 直接拼接到 CommonQAAgent 内置 prompt 上。
    # 因此，该 prompt 更适合只需简单的、与 CommonQAAgent 内置 prompt 没有冲突的自定义场景，
    # 例如要求 agent 根据用户最新提问使用的语言（中/英文）进行自适应的答复等场景。
    # 对于复杂的自定义 prompt 需求，请参考 README_AGENT_PLUGIN.md [情况二] 的内容，
    # 直接重写完整的 agent prompt 并注册到 CommonQAAgent 中进行替换。
    role_prompt: str = "{{cookiecutter.role_prompt}}"


# --------------------------------------------配置区-------------------------------------------- #

config = PluginConfig()
