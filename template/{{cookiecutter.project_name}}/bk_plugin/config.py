# 是否从AIDev平台同步最新配置
# 1.True:获取此智能体最新配置，覆盖配置
# 2.False:仅使用源码配置
SYNC_CONFIG_FROM_AIDEV = False

"""
如果 SYNC_CONFIG_FROM_AIDEV 非 True,则可以通过下面的配置覆盖现有的配置
AGENT_CONFIG = {
    "chat_model": "deepseek-r1",  # 示例：覆盖默认的聊天模型
    "non_thinking_llm": "deepseek-v3",  # 示例：覆盖非思考模型
    "knowledgebase_ids": [1, 2, 3],  # 示例：知识库ID列表
    "knowledge_ids": [101, 102, 103],  # 示例：知识ID列表
    "tool_codes": ["tool1", "tool2"],  # 示例：工具代码列表
    "role_prompt": "You are a helpful assistant.",  # 示例：自定义角色提示
}
"""
AGENT_CONFIG = {}
