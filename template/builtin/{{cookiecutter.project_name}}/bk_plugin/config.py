# -*- coding: utf-8 -*-

"""
智能体将自动从平台获取配置做为默认配置，同时，如果在 `AGENT_CONFIG` 中定义的配置，将覆盖平台获取的配置。
"""

AGENT_CONFIG = {
    # 使用的 LLM（联系接口人获取可使用的 LLM 模型名称列表）。
    "chat_model": "",
    # 非深度思考模型
    "non_thinking_llm": "",
    # 在 AIDev 站点上传知识，然后将对应的知识库 ID 或者知识 ID 填在此处，可以在 agent 使用的时候检索对应范围的知识。
    # 通常来讲，选择的知识越多，检索速度也会越慢，检索效果也会越差。一般建议只选择该 agent 需要使用的知识，不要选择无关知识。
    "knowledgebase_ids": [],
    "knowledge_ids": [],
    # 在 AIDev 站点注册工具，然后将对应的工具 tool_code 填在此处，可以在 agent 使用的时候调用相关工具。
    "tool_codes": [],
    # 需要指定的角色
    # 示例: [{"role": "system", "content": "你是一个帮助用户解决问题的助手。"}]
    "role_prompts": [],
}
