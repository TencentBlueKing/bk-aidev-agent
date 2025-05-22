"""
Sample configuration to override default settings

Sample for update config
override_config = {
    "chat_model": "deepseek-r1",  # Example: Override the default chat model
    "non_thinking_llm": "deepseek-v3",  # Example: Override the non-thinking model
    "knowledgebase_ids": [1, 2, 3],  # Example: List of knowledgebase IDs
    "knowledge_ids": [101, 102, 103],  # Example: List of knowledge IDs
    "tool_codes": ["tool1", "tool2"],  # Example: List of tool codes
    "role_prompt": "You are a helpful assistant.",  # Example: Custom role prompt
    "sync_config_from_aidev": True  # Example: Enable syncing config from AIDev
}
"""

override_config = {}
