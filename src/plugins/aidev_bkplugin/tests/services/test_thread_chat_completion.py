# -*- coding: utf-8 -*-
"""run_chat_completion_with_thread_id 与 ChatCompletionViewSet thread_id 分支回归测试。需在具备 Django + aidev_bkplugin 环境中运行。"""

import sys
from unittest.mock import MagicMock, patch

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
