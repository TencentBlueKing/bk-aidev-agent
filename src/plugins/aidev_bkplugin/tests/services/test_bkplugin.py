# -*- coding: utf-8 -*-
"""标准运维插件核心契约：Session 轮询 + Chat / Flow 编排。"""

import sys
from unittest.mock import ANY, MagicMock, patch

import pytest

try:
    import django  # noqa: F401

    _has_django = True
except ImportError:
    _has_django = False

if "pkg_resources" not in sys.modules:
    sys.modules["pkg_resources"] = MagicMock()

_bk_plugin_framework = MagicMock()
_bk_plugin_framework.kit.decorators.inject_user_token = lambda func: func
sys.modules.setdefault("bk_plugin_framework", _bk_plugin_framework)
sys.modules.setdefault("bk_plugin_framework.kit", _bk_plugin_framework.kit)
sys.modules.setdefault("bk_plugin_framework.kit.decorators", _bk_plugin_framework.kit.decorators)

from aidev_agent.enums import AgentType, ChatContentStatus, PromptRole, SessionsStatus  # noqa: E402
from aidev_agent.services.messages_handler import RetryableHeartbeatTimeoutError  # noqa: E402
from aidev_bkplugin.enums import PluginPollTaskState  # noqa: E402
from aidev_bkplugin.services.agent_session import SessionManager  # noqa: E402


class _FakeApi:
    def __init__(self, contents, status=SessionsStatus.FINISHED.value):
        self._contents = contents
        self._status = status

    def retrieve_chat_session(self, *, path_params, headers):
        return {"data": {"status": self._status}}

    def get_chat_session_contents(self, *, params, headers):
        return {"data": self._contents}


def _patch_poll_client(monkeypatch, contents, status):
    monkeypatch.setattr(SessionManager, "_client", lambda self: type("C", (), {"api": _FakeApi(contents, status)})())


@pytest.mark.parametrize(
    "status,contents,turn_id,expected",
    [
        (SessionsStatus.RUNNING.value, [], "", (PluginPollTaskState.RUNNING, "")),
        (
            SessionsStatus.FINISHED.value,
            [{"role": PromptRole.ASSISTANT.value, "status": ChatContentStatus.COMPLETE.value, "content": "done"}],
            "",
            (PluginPollTaskState.SUCCESS, "done"),
        ),
        (
            SessionsStatus.FINISHED.value,
            [
                {
                    "role": PromptRole.AI.value,
                    "status": ChatContentStatus.SUCCESS.value,
                    "content": "old",
                    "property": {"turn_id": "t-old"},
                },
                {
                    "role": PromptRole.AI.value,
                    "status": ChatContentStatus.SUCCESS.value,
                    "content": "hit",
                    "property": {"turn_id": "t-now"},
                },
                {
                    "role": PromptRole.AI.value,
                    "status": ChatContentStatus.SUCCESS.value,
                    "content": "other",
                    "property": {"turn_id": "t-x"},
                },
            ],
            "t-now",
            (PluginPollTaskState.SUCCESS, "hit"),
        ),
        (
            SessionsStatus.FINISHED.value,
            [{"role": PromptRole.USER.value, "status": ChatContentStatus.COMPLETE.value, "content": "hi"}],
            "",
            (PluginPollTaskState.SUCCESS, ""),
        ),
    ],
)
def test_poll_task_state(status, contents, turn_id, expected, monkeypatch):
    _patch_poll_client(monkeypatch, contents, status)
    assert SessionManager("alice").poll_task_state("sc", turn_id=turn_id) == expected


def test_prepare_session_turn_uses_user_content_turn_id(monkeypatch):
    sm = SessionManager("alice")
    monkeypatch.setattr(sm, "get_or_create_by_thread_id", lambda tid: "sc-1")
    saved: list[tuple[str, str]] = []

    def _save(session_code, role, content, **kw):
        saved.append((role, kw.get("turn_id", "")))
        return {"property": {"turn_id": kw.get("turn_id") or "generated-turn"}}

    monkeypatch.setattr(sm, "save_content", _save)

    assert sm.prepare_session_turn("thread-a", input_text="q") == ("sc-1", "generated-turn")
    assert saved == [(PromptRole.USER.value, "")]


@pytest.mark.skipif(not _has_django, reason="Django and plugin env required")
class TestBkpluginExecution:
    @pytest.mark.parametrize("agent_type", [AgentType.FLOW, AgentType.CHAT])
    def test_dispatch_async_returns_storage(self, agent_type):
        from aidev_bkplugin.services.agent_bkplugin import build_bkplugin_runner

        with (
            patch("aidev_bkplugin.services.agent_bkplugin.AgentConfigFetcher.get_info") as mock_info,
            patch("aidev_bkplugin.services.agent_bkplugin.SessionManager") as mock_sm_cls,
        ):
            mock_info.return_value = {"agent_type": agent_type.value, "prompt_setting": {"content": []}}
            mock_sm = mock_sm_cls.return_value
            mock_sm.prepare_session_turn.return_value = ("sess-1", "turn-1")
            task = MagicMock()
            fake_tasks = MagicMock(run_bkplugin_background_agent_task=task)
            agent = build_bkplugin_runner(
                chat_history=[],
                execute_kwargs={"session_code": "thread-1"},
                input_text="hi",
                username="alice",
            )
            with patch.dict(sys.modules, {"aidev_bkplugin.tasks": fake_tasks}):
                storage = agent.dispatch_async()

        mock_sm.prepare_session_turn.assert_called_once_with("thread-1", input_text="hi", turn_id=ANY)
        assert storage["turn_id"] and storage["agent_type"] == agent_type.value
        task.delay.assert_called_once()
        assert task.delay.call_args.kwargs["execute_payload"]["turn_id"] == "turn-1"
        assert task.delay.call_args.kwargs["execute_payload"]["stream"] is True

    def test_enqueue_background_uses_delay(self):
        from aidev_bkplugin.services.agent_bkplugin import BkpluginChat

        task = MagicMock()
        fake_tasks = MagicMock(run_bkplugin_background_agent_task=task)
        agent = BkpluginChat(
            chat_history=[],
            execute_kwargs={},
            username="alice",
        )
        with patch.dict(sys.modules, {"aidev_bkplugin.tasks": fake_tasks}):
            storage = agent._enqueue_background(
                "sess-1",
                "turn-1",
                {"turn_id": "turn-1"},
                chat_context=[{"role": "user", "content": "hi"}],
            )

        task.delay.assert_called_once_with(
            session_code="sess-1",
            execute_payload={"turn_id": "turn-1", "stream": True},
            username="alice",
            agent_type_value=AgentType.CHAT.value,
            chat_context=[{"role": "user", "content": "hi"}],
        )
        assert storage == {
            "session_code": "sess-1",
            "turn_id": "turn-1",
            "plugin_username": "alice",
            "agent_type": AgentType.CHAT.value,
        }

    def test_serial_chat_execute(self):
        from aidev_bkplugin.services.agent_bkplugin import build_bkplugin_runner

        with (
            patch("aidev_bkplugin.services.agent_bkplugin.AgentConfigFetcher.get_info") as mock_info,
            patch("aidev_bkplugin.services.agent_bkplugin.SessionManager") as mock_sm_cls,
            patch("aidev_bkplugin.services.agent_bkplugin.build_chat_agent_for_session") as mock_build,
        ):
            mock_info.return_value = {"agent_type": AgentType.CHAT.value, "prompt_setting": {"content": []}}
            mock_sm = mock_sm_cls.return_value
            mock_sm.prepare_session_turn.return_value = ("sess-chat", "turn-chat")
            mock_agent = MagicMock(execute=MagicMock(return_value={"choices": [{"delta": {"content": "ok"}}]}))
            mock_build.return_value = mock_agent
            agent = build_bkplugin_runner(
                chat_history=[{"role": "user", "content": "prev"}],
                execute_kwargs={"session_code": "thread-1"},
                input_text="hi",
                username="alice",
            )
            result = agent.execute()

        assert result == "ok"
        assert agent.session_code == "sess-chat"
        assert [x["content"] for x in mock_build.call_args.kwargs["chat_context"]] == ["prev", "hi"]
        assert mock_build.call_args.kwargs["turn_id"] == "turn-chat"
        mock_sm.save_ai_response.assert_called_once_with(
            "sess-chat", {"choices": [{"delta": {"content": "ok"}}]}, turn_id=ANY
        )

    def test_build_chat_context_prepends_role_prompts(self, monkeypatch):
        from aidev_agent.pydantic_models import ChatPrompt
        from aidev_bkplugin.services.agent_bkplugin import BkpluginChat

        role_prompts = [ChatPrompt(role="system", content="role-x")]
        fake_fetcher = MagicMock()
        fake_fetcher.get_role_info.return_value = role_prompts
        monkeypatch.setattr("aidev_bkplugin.services.agent_bkplugin.AgentConfigFetcher", fake_fetcher)

        chat = BkpluginChat(
            chat_history=[{"role": "user", "content": "hi"}],
            execute_kwargs={},
            username="alice",
        )
        context = chat._build_chat_context()

        assert [item["role"] for item in context] == ["system", "user"]
        assert context[0]["content"] == "role-x"

    def test_serial_flow_execute(self):
        from aidev_bkplugin.enums import PluginPollTaskState
        from aidev_bkplugin.services.agent_bkplugin import BkpluginFlow, build_bkplugin_runner

        with (
            patch("aidev_bkplugin.services.agent_bkplugin.AgentConfigFetcher.get_info") as mock_info,
            patch.object(BkpluginFlow, "invoke_agent") as mock_invoke_agent,
            patch("aidev_bkplugin.services.agent_bkplugin.SessionManager") as mock_sm_cls,
        ):
            mock_info.return_value = {"agent_type": AgentType.FLOW.value}
            mock_sm = mock_sm_cls.return_value
            mock_sm.prepare_session_turn.return_value = ("sess-flow", "turn-flow")
            mock_sm.poll_task_state.return_value = (PluginPollTaskState.SUCCESS, "flow out")
            agent = build_bkplugin_runner(
                chat_history=[],
                execute_kwargs={"session_code": "thread-1"},
                input_text="hi",
                username="alice",
            )
            result = agent.execute()

        mock_sm.poll_task_state.assert_called_once_with("sess-flow", turn_id=ANY)
        assert mock_invoke_agent.call_args.args[1]["turn_id"] == "turn-flow"
        assert result == "flow out" and agent.session_code == "sess-flow"

    def test_build_runner_from_plugin_uses_duck_typed_inputs(self):
        from aidev_bkplugin.services.agent_bkplugin import build_bkplugin_runner_from_plugin

        inputs = MagicMock(
            execute_kwargs={"session_code": "thread-x"},
            session_code="thread-x",
            chat_history=[{"role": "user", "content": "prev"}],
            input="hi",
            context=[{"k": "v"}],
        )
        ctx = MagicMock(data=MagicMock(executor="alice"))

        with (
            patch("aidev_bkplugin.services.agent_bkplugin.AgentConfigFetcher.get_info") as mock_info,
            patch("aidev_bkplugin.services.agent_bkplugin.resolve_executor_username") as mock_resolve,
        ):
            mock_info.return_value = {"agent_type": AgentType.CHAT.value, "prompt_setting": {"content": []}}
            mock_resolve.return_value = "alice"
            runner = build_bkplugin_runner_from_plugin(inputs, ctx)

        assert runner.username == "alice"
        assert runner.input_text == "hi"
        assert runner.execute_kwargs["session_code"] == "thread-x"
        assert runner.plugin_context == [{"k": "v"}]
        mock_resolve.assert_called_once_with("alice")

    def test_run_worker_skips_save_stream_failure_when_session_finished(self, monkeypatch):
        """心跳超时误报：producer 实际已完成（session=FINISHED），不应覆盖为 FAILED。"""
        from aidev_bkplugin.services.agent_bkplugin import BkpluginChat

        agent = BkpluginChat(chat_history=[], execute_kwargs={}, username="alice")
        monkeypatch.setattr(agent, "invoke_agent", MagicMock(side_effect=RuntimeError("生产者心跳超时")))
        mock_sm = MagicMock()
        mock_sm.retrieve_session.return_value = {"status": SessionsStatus.FINISHED.value}
        monkeypatch.setattr("aidev_bkplugin.services.agent_bkplugin.SessionManager", lambda username: mock_sm)

        agent.run_worker("sess-1", {"turn_id": "t1"})

        mock_sm.retrieve_session.assert_called_once_with("sess-1")
        mock_sm.save_stream_failure.assert_not_called()

    def test_run_worker_calls_save_stream_failure_when_session_running(self, monkeypatch):
        """producer 真崩溃：session 仍 RUNNING 时应写失败。"""
        from aidev_bkplugin.services.agent_bkplugin import BkpluginChat

        agent = BkpluginChat(chat_history=[], execute_kwargs={}, username="alice")
        monkeypatch.setattr(agent, "invoke_agent", MagicMock(side_effect=RuntimeError("producer crashed")))
        mock_sm = MagicMock()
        mock_sm.retrieve_session.return_value = {"status": SessionsStatus.RUNNING.value}
        monkeypatch.setattr("aidev_bkplugin.services.agent_bkplugin.SessionManager", lambda username: mock_sm)

        agent.run_worker("sess-1", {"turn_id": "t1"})

        mock_sm.save_stream_failure.assert_called_once_with("sess-1", ANY, turn_id="t1")

    def test_run_worker_skips_session_update_for_retryable_heartbeat_timeout(self, monkeypatch):
        """消费者心跳超时可重试，不应更新 session 终态。"""
        from aidev_bkplugin.services.agent_bkplugin import BkpluginChat

        agent = BkpluginChat(chat_history=[], execute_kwargs={}, username="alice")
        monkeypatch.setattr(
            agent,
            "invoke_agent",
            MagicMock(side_effect=RetryableHeartbeatTimeoutError("生产者心跳超时")),
        )
        manager_factory = MagicMock()
        monkeypatch.setattr("aidev_bkplugin.services.agent_bkplugin.SessionManager", manager_factory)

        agent.run_worker("sess-1", {"turn_id": "t1"})

        manager_factory.assert_not_called()

    def test_execute_skips_session_update_for_retryable_heartbeat_timeout(self, monkeypatch):
        """同步消费遇到可重试心跳超时，也不应覆盖 session 状态。"""
        from aidev_bkplugin.services.agent_bkplugin import BkpluginChat

        agent = BkpluginChat(chat_history=[], execute_kwargs={"session_code": "sess-1"}, username="alice")
        monkeypatch.setattr(
            agent,
            "_do_execute",
            MagicMock(side_effect=RetryableHeartbeatTimeoutError("生产者心跳超时")),
        )
        manager_factory = MagicMock()
        monkeypatch.setattr("aidev_bkplugin.services.agent_bkplugin.SessionManager", manager_factory)

        with pytest.raises(RetryableHeartbeatTimeoutError):
            agent.execute()

        manager_factory.assert_not_called()
