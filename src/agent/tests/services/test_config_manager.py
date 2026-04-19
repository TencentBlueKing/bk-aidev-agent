import time
from typing import Optional
from unittest.mock import Mock

from aidev_agent.api.abstract_client import AbstractBKAidevResourceManager
from aidev_agent.services.config_manager import AgentConfig, AgentConfigManager, CachedEntry


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

    # Verify cache contains the entry (cache key is (agent_code, version_or_latest))
    assert ("test_agent_1", "latest") in AgentConfigManager._config_cache


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
    cached_entry = AgentConfigManager._config_cache[("test_agent_2", "latest")]
    cached_entry.timestamp = time.time() - AgentConfigManager.CACHE_TTL - 1  # Make it 61 seconds old

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
    assert ("agent_a", "latest") in AgentConfigManager._config_cache
    assert ("agent_b", "latest") in AgentConfigManager._config_cache

    # Get config again for both agents (should use cache)
    config1_cached = AgentConfigManager.get_config("agent_a", mock_manager)
    config2_cached = AgentConfigManager.get_config("agent_b", mock_manager)

    # Verify the resource manager was NOT called again
    assert mock_manager.call_count == 2

    # Verify the cached configs are the same as originals
    assert config1 is config1_cached
    assert config2 is config2_cached


def test_version_passes_through_to_resource_manager():
    """version 必须透传到 resource_manager.retrieve_agent_config"""
    AgentConfigManager._config_cache.clear()
    mock_manager = MockResourceManager()

    AgentConfigManager.get_config("agent_v", mock_manager, version="v2")
    assert mock_manager.last_version == "v2"

    # 不传 version → 走 latest
    AgentConfigManager.get_config("agent_v_latest", mock_manager)
    assert mock_manager.last_version is None


def test_version_isolates_cache_slot():
    """同一 agent_code 不同 version 走独立缓存槽，互不污染"""
    AgentConfigManager._config_cache.clear()
    mock_manager = MockResourceManager()

    config_latest = AgentConfigManager.get_config("agent_v", mock_manager)
    assert mock_manager.call_count == 1
    config_v1 = AgentConfigManager.get_config("agent_v", mock_manager, version="v1")
    assert mock_manager.call_count == 2
    config_v2 = AgentConfigManager.get_config("agent_v", mock_manager, version="v2")
    assert mock_manager.call_count == 3

    # 三个 slot 同时存在
    assert ("agent_v", "latest") in AgentConfigManager._config_cache
    assert ("agent_v", "v1") in AgentConfigManager._config_cache
    assert ("agent_v", "v2") in AgentConfigManager._config_cache

    # 同 version 复访命中缓存
    AgentConfigManager.get_config("agent_v", mock_manager, version="v1")
    assert mock_manager.call_count == 3

    # 不同版本 config 实例彼此独立
    assert config_latest is not config_v1
    assert config_v1 is not config_v2
