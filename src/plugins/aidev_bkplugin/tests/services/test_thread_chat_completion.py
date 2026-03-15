# -*- coding: utf-8 -*-
"""run_chat_completion_with_thread_id 与 ChatCompletionViewSet thread_id 分支回归测试。需在具备 Django + aidev_bkplugin 环境中运行。"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

try:
    import django  # noqa: F401

    _has_django = True
except ImportError:
    _has_django = False

# 避免 agent 模块导入时依赖 pkg_resources（get_agent_version 用）
if "pkg_resources" not in sys.modules:
    sys.modules["pkg_resources"] = MagicMock()


@pytest.mark.skipif(not _has_django, reason="Django and plugin env required")
class TestRunChatCompletionWithThreadId:
    """统一入口 run_chat_completion_with_thread_id 行为。"""

    def test_requires_input_text(self):
        from aidev_bkplugin.services.agent import run_chat_completion_with_thread_id

        ek = MagicMock()
        ek.session_code = None
        with pytest.raises(ValueError, match="input_text is required"):
            run_chat_completion_with_thread_id(
                thread_id="t1",
                input_text="",
                username="user1",
                execute_kwargs=ek,
            )

    def test_wires_session_code_and_returns_result(self):
        from aidev_bkplugin.services.agent import run_chat_completion_with_thread_id

        with (
            patch("aidev_bkplugin.services.agent.build_chat_completion_agent_by_thread_id") as mock_build,
            patch("aidev_bkplugin.services.agent.execute_agent_with_save") as mock_exec,
        ):
            mock_build.return_value = (MagicMock(), "session-abc")
            mock_exec.return_value = iter(["data: {}"])
            ek = MagicMock()
            ek.stream = True
            ek.session_code = None
            result, session_code = run_chat_completion_with_thread_id(
                thread_id="thread-1",
                input_text="hello",
                username="tester",
                execute_kwargs=ek,
            )
            assert session_code == "session-abc"
            assert ek.session_code == "session-abc"
            assert result is not None


@pytest.mark.skipif(not _has_django, reason="Django and plugin env required")
class TestBuildChatCompletionAgentByThreadIdWithChatHistory:
    def test_persists_chat_history_before_building_agent(self):
        from aidev_bkplugin.services.agent import build_chat_completion_agent_by_thread_id_with_chat_history

        history = [
            SimpleNamespace(role="user", content="hello"),
            SimpleNamespace(role="assistant", content="hi"),
        ]

        with (
            patch("aidev_bkplugin.services.agent.get_or_create_session_by_thread_id") as mock_session,
            patch("aidev_bkplugin.services.agent.save_session_content") as mock_save,
            patch("aidev_bkplugin.services.agent.agent_factory.get") as mock_agent_factory,
            patch("aidev_bkplugin.services.agent.agent_config_factory.get") as mock_config_factory,
            patch("aidev_bkplugin.services.agent.AgentInstanceFactory.build_agent") as mock_build,
        ):
            mock_session.return_value = "session-abc"
            mock_agent_factory.return_value = MagicMock()
            mock_config_factory.return_value = MagicMock()
            mock_build.return_value = MagicMock()

            agent_instance, session_code = build_chat_completion_agent_by_thread_id_with_chat_history(
                thread_id="thread-1",
                chat_history=history,
                username="tester",
            )

        assert agent_instance is mock_build.return_value
        assert session_code == "session-abc"
        assert mock_save.call_args_list == [
            call(session_code="session-abc", role="user", content="hello", username="tester"),
            call(session_code="session-abc", role="assistant", content="hi", username="tester"),
        ]
        mock_build.assert_called_once()
        assert mock_build.call_args.kwargs["session_code"] == "session-abc"

    def test_skips_persist_when_chat_history_is_empty(self):
        from aidev_bkplugin.services.agent import build_chat_completion_agent_by_thread_id_with_chat_history

        with (
            patch("aidev_bkplugin.services.agent.get_or_create_session_by_thread_id") as mock_session,
            patch("aidev_bkplugin.services.agent.save_session_content") as mock_save,
            patch("aidev_bkplugin.services.agent.agent_factory.get") as mock_agent_factory,
            patch("aidev_bkplugin.services.agent.agent_config_factory.get") as mock_config_factory,
            patch("aidev_bkplugin.services.agent.AgentInstanceFactory.build_agent") as mock_build,
        ):
            mock_session.return_value = "session-empty"
            mock_agent_factory.return_value = MagicMock()
            mock_config_factory.return_value = MagicMock()
            mock_build.return_value = MagicMock()

            agent_instance, session_code = build_chat_completion_agent_by_thread_id_with_chat_history(
                thread_id="thread-2",
                chat_history=[],
                username="tester",
            )

        assert agent_instance is mock_build.return_value
        assert session_code == "session-empty"
        mock_save.assert_not_called()
