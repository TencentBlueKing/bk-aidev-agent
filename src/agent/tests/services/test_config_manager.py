import time
from unittest.mock import Mock

from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager, CachedEntry


class MockResourceManager(AbstractBKAidevResourceManager):
    """Mock resource manager for testing"""

    def __init__(self, config_data=None):
        self.config_data = config_data or {}
        self.call_count = 0

    def retrieve_knowledgebase(self, id: int, **kwargs) -> dict:
        return {"id": id, "name": f"Knowledgebase {id}"}

    def retrieve_knowledge(self, id: int, **kwargs) -> dict:
        return {"id": id, "name": f"Knowledge {id}"}

    def get_chat_session_context(self, session_code: str, **kwargs) -> list[dict]:
        return []

    def retrieve_agent_config(self, agent_code: str, **kwargs) -> dict:
        self.call_count += 1
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

    def construct_tool(self, tool_code: str, **kwargs):
        pass

    def knowledge_query(self, data: dict) -> dict:
        return {}


def test_cached_entry_is_expired():
    """Test CachedEntry is_expired method"""
    # Create a cached entry with current timestamp
    config = Mock(spec=AgentConfig)
    entry = CachedEntry(config, time.time())

    # Should not be expired immediately
    assert not entry.is_expired()

    # Should not be expired within TTL
    assert not entry.is_expired(ttl=10)

    # Create an expired entry (61 seconds old)
    old_entry = CachedEntry(config, time.time() - 61)

    # Should be expired with default TTL (60 seconds)
    assert old_entry.is_expired()

    # Should be expired with shorter TTL
    assert old_entry.is_expired(ttl=30)

    # Should not be expired with longer TTL
    assert not old_entry.is_expired(ttl=120)


def test_cache_storage_and_retrieval():
    """Test that config is properly cached and retrieved"""
    # Clear any existing cache
    AgentConfigManager._config_cache.clear()

    # Create mock resource manager
    mock_manager = MockResourceManager()

    # Get config for the first time
    config1 = AgentConfigManager.get_config("test_agent_1", mock_manager)

    # Verify the resource manager was called
    assert mock_manager.call_count == 1

    # Get config for the second time (should use cache)
    config2 = AgentConfigManager.get_config("test_agent_1", mock_manager)

    # Verify the resource manager was NOT called again
    assert mock_manager.call_count == 1

    # Verify the configs are the same object (cached)
    assert config1 is config2

    # Verify cache contains the entry
    assert "test_agent_1" in AgentConfigManager._config_cache


def test_cache_expiration():
    """Test that cache expires correctly"""
    # Clear any existing cache
    AgentConfigManager._config_cache.clear()

    # Create mock resource manager
    mock_manager = MockResourceManager()

    # Get config for the first time
    config1 = AgentConfigManager.get_config("test_agent_2", mock_manager)
    assert mock_manager.call_count == 1

    # Manually expire the cache entry
    cached_entry = AgentConfigManager._config_cache["test_agent_2"]
    cached_entry.timestamp = time.time() - 61  # Make it 61 seconds old

    # Get config again (should refresh due to expiration)
    config2 = AgentConfigManager.get_config("test_agent_2", mock_manager)

    # Verify the resource manager was called again
    assert mock_manager.call_count == 2

    # Verify the configs are different objects
    assert config1 is not config2


def test_force_refresh():
    """Test that force_refresh bypasses cache"""
    # Clear any existing cache
    AgentConfigManager._config_cache.clear()

    # Create mock resource manager
    mock_manager = MockResourceManager()

    # Get config for the first time
    config1 = AgentConfigManager.get_config("test_agent_3", mock_manager)
    assert mock_manager.call_count == 1

    # Get config again with force_refresh=True (should bypass cache)
    config2 = AgentConfigManager.get_config("test_agent_3", mock_manager, force_refresh=True)

    # Verify the resource manager was called again
    assert mock_manager.call_count == 2

    # Verify the configs are different objects
    assert config1 is not config2


def test_multiple_agents_cache_isolation():
    """Test that different agents have isolated caches"""
    # Clear any existing cache
    AgentConfigManager._config_cache.clear()

    # Create mock resource manager
    mock_manager = MockResourceManager()

    # Get config for two different agents
    config1 = AgentConfigManager.get_config("agent_a", mock_manager)
    config2 = AgentConfigManager.get_config("agent_b", mock_manager)

    # Verify the resource manager was called twice
    assert mock_manager.call_count == 2

    # Verify the configs are different
    assert config1 is not config2
    assert config1.agent_code == "agent_a"
    assert config2.agent_code == "agent_b"

    # Verify cache contains both entries
    assert "agent_a" in AgentConfigManager._config_cache
    assert "agent_b" in AgentConfigManager._config_cache

    # Get config again for both agents (should use cache)
    config1_cached = AgentConfigManager.get_config("agent_a", mock_manager)
    config2_cached = AgentConfigManager.get_config("agent_b", mock_manager)

    # Verify the resource manager was NOT called again
    assert mock_manager.call_count == 2

    # Verify the cached configs are the same as originals
    assert config1 is config1_cached
    assert config2 is config2_cached
