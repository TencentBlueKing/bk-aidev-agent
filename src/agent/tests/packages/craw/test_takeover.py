# -*- coding: utf-8 -*-
"""enable_chat_takeover：env 门控 / 可逆 / 失败降级 / 失败不留半接管态。"""

import pytest

from aidev_agent.enums import AgentType
from aidev_agent.packages.craw import CrawCompletionAgent, craw_backend_registry, enable_chat_takeover
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


class TestNoPartialTakeover:
    """接管失败绝不留半接管态：报告 False 时 registry 必须保持原样。"""

    def test_backend_missing_declared_attrs_keeps_native(self, monkeypatch):
        class _BrokenBackend:
            """满足旧协议最小面（name / default_model）但缺 api_url / model 的自定义后端。"""

            name = "broken-kernel"
            default_model = "x"

        craw_backend_registry.register("broken-kernel", _BrokenBackend)
        try:
            monkeypatch.setenv("BKAI_CRAW_BACKEND", "broken-kernel")
            before_item = agent_registry.values[AgentType.CHAT]
            assert enable_chat_takeover() is False
            # 值与优先级都必须原样保留——失败时不允许 CHAT 实际被 craw 接管
            after_item = agent_registry.values[AgentType.CHAT]
            assert after_item.value is before_item.value
            assert after_item.priority == before_item.priority
            assert after_item.value is not CrawCompletionAgent
        finally:
            craw_backend_registry.remove("broken-kernel")
