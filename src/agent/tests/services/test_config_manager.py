from typing import Optional

from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.services.config_manager import AgentConfigManager


class MockResourceManager(AbstractBKAidevResourceManager):
    """Mock resource manager for testing"""

    def __init__(self, config_data=None):
        self.config_data = config_data or {}
        self.call_count = 0
        self.last_version = None

    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict:
        return {"id": id, "name": f"Knowledgebase {id}"}

    def retrieve_knowledge(self, id: int, **kwargs) -> dict:
        return {"id": id, "name": f"Knowledge {id}"}

    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]:
        return []

    def retrieve_agent_config(self, agent_code: str, version: Optional[str] = None, **kwargs) -> dict:
        self.call_count += 1
        self.last_version = version
        if agent_code in self.config_data:
            return self.config_data[agent_code]
        return {
            "agent_name": f"Test Agent {agent_code}",
            "prompt_setting": {
                "llm_code": "test-model",
                "non_thinking_llm": "test-non-thinking-model",
                "content": [{"role": "system", "content": "Test role prompt"}],
            },
            "related_tools": ["tool1", "tool2"],
            "conversation_settings": {"opening_remark": "Hello!", "commands": []},
            "intent_recognition": {},
            "knowledgebase_settings": {"knowledgebases": []},
        }

    def retrieve_skill(self, skill_id: str, version: str, **kwargs) -> dict:
        return {"id": skill_id, "version": version}

    def construct_tool(self, tool_code: str, **kwargs):
        pass

    def knowledge_query(self, data: dict) -> dict:
        return {}


def test_get_config_always_calls_resource_manager():
    """SDK 不再做进程内缓存，每次调用都应该实时打到 resource_manager。"""
    mock_manager = MockResourceManager()

    config1 = AgentConfigManager.get_config("test_agent_1", mock_manager)
    config2 = AgentConfigManager.get_config("test_agent_1", mock_manager)

    assert mock_manager.call_count == 2
    assert config1 is not config2
    assert config1.agent_code == "test_agent_1"
    assert config2.agent_code == "test_agent_1"


def test_version_passes_through_to_resource_manager():
    """version 必须透传到 resource_manager.retrieve_agent_config。"""
    mock_manager = MockResourceManager()

    AgentConfigManager.get_config("agent_v", mock_manager, version="v2")
    assert mock_manager.last_version == "v2"

    AgentConfigManager.get_config("agent_v_latest", mock_manager)
    assert mock_manager.last_version is None
