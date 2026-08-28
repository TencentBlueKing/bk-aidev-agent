# -*- coding: utf-8 -*-
"""``AgentBuilder`` OO 入口：装配 event_handler / checkpointer，确保 thread 路径顺序正确。"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# models 已由 tests.settings 的测试专用 AppConfig 真实注册，setdefault 在此仅作兜底；
# bk_plugin_framework 测试环境未安装，必须 mock 才能导入 views/services。
sys.modules.setdefault("aidev_bkplugin.models", MagicMock())
sys.modules.setdefault("bk_plugin_framework", MagicMock())
sys.modules.setdefault("bk_plugin_framework.kit", MagicMock())
sys.modules.setdefault("bk_plugin_framework.kit.decorators", MagicMock(inject_user_token=lambda func: func))

# 必须在模块级导入：tests/views 下的用例会用假模块永久替换 sys.modules["aidev_bkplugin.views.base"]，
# 到测试执行期再 import 只能拿到 MagicMock。
from aidev_bkplugin.views.base import PluginResourceManager  # noqa: E402


def _patch_factories():
    return (
        patch("aidev_bkplugin.services.agent_builder.AgentInstanceFactory.build_agent"),
        patch("aidev_bkplugin.services.agent_builder.common_agent_factory.get"),
        patch("aidev_bkplugin.services.agent_builder.AgentHelper.get_client"),
        patch("aidev_bkplugin.services.agent_builder.AgentHelper.get_checkpointer"),
    )


def test_by_session_code_passes_version_and_attaches_event_handler():
    from aidev_bkplugin.services.agent_builder import AgentBuilder

    build_p, factory_p, client_p, checkpointer_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p, checkpointer_p:
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

    build_p, factory_p, client_p, checkpointer_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p, checkpointer_p:
        mock_factory.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        builder = AgentBuilder(username="alice", session_manager=sm, turn_id="turn-1")
        agent_instance, session_code = builder.by_thread_id_with_chat_history(
            "t-1",
            history,
            channel_type="rtx",
        )

    assert session_code == "session-xyz"
    assert agent_instance is mock_build.return_value
    sm.get_or_create_by_thread_id.assert_called_once_with("t-1", channel_type="rtx")
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

    build_p, factory_p, client_p, checkpointer_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p, checkpointer_p:
        mock_factory.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        AgentBuilder(username="alice", session_manager=sm).by_thread_id("t-1", "hello", save_content=False)

    sm.save_content.assert_not_called()


def test_by_session_code_passes_user_resource_manager():
    from aidev_agent.packages.resource_manager.agent import AgentResourceManager
    from aidev_bkplugin.services.agent_builder import AgentBuilder

    build_p, factory_p, client_p, checkpointer_p = _patch_factories()
    with build_p as mock_build, factory_p as mock_factory, client_p, checkpointer_p:
        mock_factory.return_value = MagicMock()
        mock_build.return_value = MagicMock()
        AgentBuilder(username="alice").by_session_code("sc-1")

    rm = mock_build.call_args.kwargs["resource_manager"]
    assert isinstance(rm, AgentResourceManager)
    assert rm.username == "alice"


def test_llm_override_resource_manager_overrides_chat_model_only():
    """model 热切换核心：LLMOverrideResourceManager 仅覆盖 chat_model，保留 non_thinking_llm。

    直接测 resource manager 的 get_agent_config，不走 AgentBuilder 全链路，
    避免引入 checkpointer / factory 等 builder 装配副作用。
    """
    from aidev_agent.packages.resource_manager.agent import AgentResourceManager
    from aidev_bkplugin.services.agent_builder import LLMOverrideResourceManager

    config = MagicMock(name="agent_config")
    config.chat_model = "orig-chat"
    config.non_thinking_llm = "orig-nt"
    with patch.object(AgentResourceManager, "get_agent_config", return_value=config):
        result = LLMOverrideResourceManager(username="alice", model="hy3-preview").get_agent_config("x")
    assert result.chat_model == "hy3-preview"
    assert result.non_thinking_llm == "orig-nt"


def test_llm_override_resource_manager_positional_args_are_username_and_model():
    """位置参数契约：前两位必须是 username、model。

    凭证参数曾被插到最前面，导致 ``LLMOverrideResourceManager("alice", "gpt")``
    被静默解读为 app_code/app_secret，用户名与模型双双丢失。
    """
    from aidev_bkplugin.services.agent_builder import LLMOverrideResourceManager

    rm = LLMOverrideResourceManager("alice", "hy3-preview")

    assert rm.username == "alice"
    assert rm.model == "hy3-preview"
    # 凭证是 keyword-only，不会被位置参数误占
    with pytest.raises(TypeError):
        LLMOverrideResourceManager("alice", "hy3-preview", "app-code")


def test_plugin_resource_manager_forwards_credentials_to_base():
    """PluginResourceManager 同样保持 (username, model) 位置顺序，并透传 keyword-only 凭证。"""
    rm = PluginResourceManager("alice", "hy3-preview", app_code="ac", app_secret="as")

    assert (rm.username, rm.model) == ("alice", "hy3-preview")
    assert (rm.app_code, rm.app_secret) == ("ac", "as")
