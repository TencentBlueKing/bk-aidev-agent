# -*- coding: utf-8 -*-
"""enable_chat_takeover：env 门控 / 可逆 / 失败降级。"""

import pytest

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw import CrawCompletionAgent, enable_chat_takeover
from aidev_agent.services.agent.registry import agent_registry


@pytest.fixture
def restore_chat_registration():
    original = agent_registry.must_get(AgentType.CHAT)
    yield
    agent_registry.remove(AgentType.CHAT)
    agent_registry.register(AgentType.CHAT, original, priority=0)


class TestEnableChatTakeover:
    def test_noop_without_env(self, monkeypatch):
        monkeypatch.delenv("BKAI_CRAW_BACKEND", raising=False)
        before = agent_registry.must_get(AgentType.CHAT)
        assert enable_chat_takeover() is False
        assert agent_registry.must_get(AgentType.CHAT) is before

    def test_unknown_backend_keeps_native(self, monkeypatch):
        monkeypatch.setenv("BKAI_CRAW_BACKEND", "no-such-kernel")
        before = agent_registry.must_get(AgentType.CHAT)
        assert enable_chat_takeover() is False
        assert agent_registry.must_get(AgentType.CHAT) is before

    @pytest.mark.parametrize("backend_name", ["openclaw", "hermes"])
    def test_takeover_registers_craw_agent(self, monkeypatch, restore_chat_registration, backend_name):
        monkeypatch.setenv("BKAI_CRAW_BACKEND", backend_name)
        assert enable_chat_takeover() is True
        assert agent_registry.must_get(AgentType.CHAT) is CrawCompletionAgent
