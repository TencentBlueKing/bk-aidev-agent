# -*- coding: utf-8 -*-
"""后台 Agent 流式终态写入回归测试。"""

import sys
from unittest.mock import MagicMock, patch

import pytest

if "pkg_resources" not in sys.modules:
    sys.modules["pkg_resources"] = MagicMock()

sys.modules.setdefault("aidev_bkplugin.models", MagicMock())
_bk_plugin_framework = MagicMock()
_bk_plugin_framework.kit.decorators.inject_user_token = lambda func: func
sys.modules.setdefault("bk_plugin_framework", _bk_plugin_framework)
sys.modules.setdefault("bk_plugin_framework.kit", _bk_plugin_framework.kit)
sys.modules.setdefault("bk_plugin_framework.kit.decorators", _bk_plugin_framework.kit.decorators)


class TestAgentExecutorCompletion:
    def test_drain_does_not_write_terminal_state(self):
        from aidev_agent.services.event_handlers.base import BaseSessionWriter
        from aidev_bkplugin.services.agent_execution import AgentExecutor

        lifecycle = []

        def stream():
            yield "chunk"
            lifecycle.append("drained")

        handler = MagicMock(spec=BaseSessionWriter)
        agent = MagicMock(event_handler=handler)
        execute_kwargs = MagicMock(stream=True)
        with patch.object(AgentExecutor, "execute_with_save", return_value=stream()):
            AgentExecutor.run_agent_to_completion(agent, execute_kwargs, "session-abc", MagicMock())

        assert execute_kwargs.background_only is True
        assert lifecycle == ["drained"]
        handler.set_streaming_finished.assert_not_called()

    def test_does_not_set_finished_when_stream_drain_fails(self):
        from aidev_agent.services.event_handlers.base import BaseSessionWriter
        from aidev_bkplugin.services.agent_execution import AgentExecutor

        def failing_stream():
            yield "chunk"
            raise RuntimeError("producer heartbeat timeout")

        handler = MagicMock(spec=BaseSessionWriter)
        agent = MagicMock(event_handler=handler)
        execute_kwargs = MagicMock(stream=True)
        with (
            patch.object(AgentExecutor, "execute_with_save", return_value=failing_stream()),
            pytest.raises(RuntimeError, match="heartbeat timeout"),
        ):
            AgentExecutor.run_agent_to_completion(agent, execute_kwargs, "session-abc", MagicMock())

        handler.set_streaming_finished.assert_not_called()
