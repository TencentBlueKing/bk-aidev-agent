# -*- coding: utf-8 -*-
"""``AgentExecutor.run_chat_completion_with_thread_id`` 的回归测试：thread_id 路径下的 OO 装配语义。"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

try:
    import django  # noqa: F401

    _has_django = True
except ImportError:
    _has_django = False

# 避免 agent 模块加载时依赖 pkg_resources（get_agent_version 用）
if "pkg_resources" not in sys.modules:
    sys.modules["pkg_resources"] = MagicMock()
sys.modules.setdefault("aidev_bkplugin.models", MagicMock())


@pytest.mark.skipif(not _has_django, reason="Django and plugin env required")
class TestRunChatCompletionWithThreadId:
    def test_requires_input_text(self):
        from aidev_bkplugin.services.agent_execution import AgentExecutor

        ek = MagicMock()
        ek.session_code = None
        with pytest.raises(ValueError, match="input_text is required"):
            AgentExecutor.run_chat_completion_with_thread_id(
                thread_id="t1",
                input_text="",
                username="user1",
                execute_kwargs=ek,
            )

    def test_wires_session_code_and_returns_result(self):
        """OO 装配契约：``AgentBuilder.by_thread_id`` 返回 (agent, session_code)，
        ``AgentExecutor.execute_with_save`` 拿到该 session_code 执行；ek.session_code 同步注入。

        ``AgentExecutor.run_chat_completion_with_thread_id`` 内部通过 ``cls(...)`` 构造实例，
        因此 patch 类后既要 mock 类构造（``mock_executor_cls.return_value``）也要让该 mock 的
        ``execute_with_save`` 受控。
        """
        from aidev_bkplugin.services.agent_execution import AgentExecutor

        with (
            patch("aidev_bkplugin.services.agent_execution.AgentBuilder") as mock_builder_cls,
            patch.object(AgentExecutor, "execute_with_save") as mock_execute_with_save,
        ):
            mock_builder = mock_builder_cls.return_value
            mock_agent = MagicMock(name="agent_instance")
            mock_builder.by_thread_id.return_value = (mock_agent, "session-abc")
            mock_builder.turn_id = "turn-1"
            mock_execute_with_save.return_value = iter(["data: {}"])

            ek = MagicMock()
            ek.stream = True
            ek.session_code = None
            ek.version = None

            result, session_code = AgentExecutor.run_chat_completion_with_thread_id(
                thread_id="thread-1",
                input_text="hello",
                username="tester",
                execute_kwargs=ek,
            )

            assert session_code == "session-abc"
            assert ek.session_code == "session-abc"
            assert ek.turn_id == "turn-1"
            assert result is not None

            mock_builder.by_thread_id.assert_called_once_with(
                thread_id="thread-1",
                input_text="hello",
                save_content=True,
                version=None,
                channel_type=None,
            )
            mock_execute_with_save.assert_called_once_with(mock_agent, ek, "session-abc", turn_id="turn-1")

    def test_applies_transient_system_prompt_and_clarification_override(self):
        from aidev_agent.enums import PromptRole
        from aidev_bkplugin.services.agent_execution import AgentExecutor

        with (
            patch("aidev_bkplugin.services.agent_execution.AgentBuilder") as mock_builder_cls,
            patch.object(AgentExecutor, "execute_with_save", return_value=iter(["data: {}"])),
        ):
            agent = SimpleNamespace(
                chat_history=[],
                knowledge_query_options=SimpleNamespace(enable_query_clarification=True),
                event_handler=None,
            )
            builder = mock_builder_cls.return_value
            builder.by_thread_id.return_value = (agent, "session-abc")
            builder.turn_id = "turn-1"
            builder.session_manager = MagicMock()
            execute_kwargs = SimpleNamespace(stream=True, session_code=None, version=None)

            AgentExecutor.run_chat_completion_with_thread_id(
                thread_id="thread-1",
                input_text="query",
                username="tester",
                execute_kwargs=execute_kwargs,
                transient_system_prompt="execute completely",
                enable_query_clarification=False,
                temperature=0.1,
            )

        mock_builder_cls.assert_called_once_with(username="tester", temperature=0.1)
        assert agent.chat_history[0].role == PromptRole.SYSTEM.value
        assert agent.chat_history[0].content == "execute completely"
        assert agent.knowledge_query_options.enable_query_clarification is False
