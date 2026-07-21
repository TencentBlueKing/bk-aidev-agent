# -*- coding: utf-8 -*-
"""``AgentBuilder`` OO 入口：装配 event_handler / checkpointer，确保 thread 路径顺序正确。"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _patch_factories():
    return (
        patch("aidev_bkplugin.services.agent_builder.AgentInstanceFactory.build_agent"),
        patch("aidev_bkplugin.services.agent_builder.common_agent_factory.get"),
        patch("aidev_bkplugin.services.agent_builder.AgentHelper.get_client"),
    )


def test_by_session_code_passes_version_and_attaches_event_handler():
    from aidev_bkplugin.services.agent_builder import AgentBuilder

    build_p, factory_p, client_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p:
        mock_factory.return_value = MagicMock(name="agent_cls")
        mock_build.return_value = MagicMock(name="agent")
        AgentBuilder(username="alice").by_session_code("sc-1", version="v2")

    kwargs = mock_build.call_args.kwargs
    assert kwargs["session_code"] == "sc-1"
    assert kwargs["version"] == "v2"
    assert kwargs["event_handler"] is not None
    assert kwargs["checkpointer"] is not None


def test_by_thread_id_with_chat_history_persists_then_builds():
    """Builder 走 SessionManager 实例方法路径：先 ensure session → 写入 history → 装配 agent。"""
    from aidev_bkplugin.services.agent_builder import AgentBuilder

    history = [
        SimpleNamespace(role="user", content="hello"),
        SimpleNamespace(role="assistant", content="hi"),
        SimpleNamespace(role="user", content="new question"),
    ]
    sm = MagicMock(name="session_manager")
    sm.get_or_create_by_thread_id.return_value = "session-xyz"

    build_p, factory_p, client_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p:
        mock_factory.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        builder = AgentBuilder(username="alice", session_manager=sm, turn_id="turn-1")
        agent_instance, session_code = builder.by_thread_id_with_chat_history("t-1", history)

    assert session_code == "session-xyz"
    assert agent_instance is mock_build.return_value
    sm.get_or_create_by_thread_id.assert_called_once_with("t-1")
    sm.save_chat_history.assert_called_once_with("session-xyz", history[:-1])
    sm.save_content.assert_called_once_with(
        session_code="session-xyz",
        role="user",
        content="new question",
        turn_id="turn-1",
    )


def test_by_thread_id_skips_save_when_save_content_false():
    from aidev_bkplugin.services.agent_builder import AgentBuilder

    sm = MagicMock()
    sm.get_or_create_by_thread_id.return_value = "session-xyz"

    build_p, factory_p, client_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p:
        mock_factory.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        AgentBuilder(username="alice", session_manager=sm).by_thread_id("t-1", "hello", save_content=False)

    sm.save_content.assert_not_called()


def test_by_session_code_passes_llm_override_resource_manager():
    from aidev_agent.packages.resource_manager.agent import AgentResourceManager
    from aidev_bkplugin.services.agent_builder import AgentBuilder, LLMOverrideResourceManager

    build_p, factory_p, client_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p:
        mock_factory.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        AgentBuilder(username="alice").by_session_code("sc-1")

    rm = mock_build.call_args.kwargs["resource_manager"]
    assert isinstance(rm, LLMOverrideResourceManager)
    assert isinstance(rm, AgentResourceManager)
    assert rm.username == "alice"
    assert rm.llm == ""


def test_by_session_code_attaches_llm_to_resource_manager():
    from aidev_bkplugin.services.agent_builder import AgentBuilder, LLMOverrideResourceManager

    build_p, factory_p, client_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p:
        mock_factory.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        AgentBuilder(username="alice", llm="gpt-4").by_session_code("sc-1")

    rm = mock_build.call_args.kwargs["resource_manager"]
    assert isinstance(rm, LLMOverrideResourceManager)
    assert rm.llm == "gpt-4"


def test_llm_override_resource_manager_overrides_chat_model_when_llm_set():
    from aidev_agent.packages.resource_manager.agent import AgentResourceManager
    from aidev_bkplugin.services.agent_builder import LLMOverrideResourceManager

    config = MagicMock(name="agent_config")
    with patch.object(AgentResourceManager, "get_agent_config", return_value=config):
        rm = LLMOverrideResourceManager(username="alice", llm="gpt-4")
        result = rm.get_agent_config("x")
    assert result is config
    assert config.chat_model == "gpt-4"
    assert config.non_thinking_llm == "gpt-4"


def test_llm_override_resource_manager_keeps_original_when_llm_empty():
    from aidev_agent.packages.resource_manager.agent import AgentResourceManager
    from aidev_bkplugin.services.agent_builder import LLMOverrideResourceManager

    config = MagicMock(name="agent_config")
    config.chat_model = "orig"
    config.non_thinking_llm = "orig"
    with patch.object(AgentResourceManager, "get_agent_config", return_value=config):
        LLMOverrideResourceManager(username="alice", llm="").get_agent_config("x")
    assert config.chat_model == "orig"
    assert config.non_thinking_llm == "orig"
