"""Session commands share routing across HTTP polling and WebSocket callbacks."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from aidev_bkplugin.services.agent_session import SessionManager
from aidev_wxbot.wxaibot import views
from aidev_wxbot.wxaibot.long_connection import _LongConnectionViewSet


@pytest.fixture(params=["polling", "websocket"])
def command_case(request, monkeypatch):
    view = views.WxAiBotViewSet() if request.param == "polling" else _LongConnectionViewSet(MagicMock())
    record = MagicMock(thread_id="original-thread")
    lookup = MagicMock(return_value=record)
    monkeypatch.setattr(views.AgentSession.objects, "get", lookup)
    manager = MagicMock(spec=SessionManager, agent_code="test-agent")
    manager.generate_session_code.side_effect = SessionManager.generate_session_code
    manager.retrieve_session.return_value = {"session_name": "old"}
    manager_cls = MagicMock(return_value=manager)
    monkeypatch.setattr(views, "SessionManager", manager_cls)
    link = MagicMock(side_effect=lambda code, **_: f"https://agent.example.com/chat-window/?session={code}")
    monkeypatch.setattr(views.AgentHelper, "build_session_detail_url", link)
    return SimpleNamespace(
        view=view,
        record=record,
        lookup=lookup,
        manager=manager,
        manager_cls=manager_cls,
        link=link,
        mode=request.param,
        context=SimpleNamespace(sender_id="alice", group_id="group-1"),
    )


@pytest.mark.parametrize("command", ["/title 日志 查询", "/web"])
@pytest.mark.parametrize("entry", ["single", "mention", "fallback"])
def test_commands_preserve_original_user_session(command_case, command, entry):
    case = command_case
    if entry == "single":
        response, content = case.view._handle_single_chat(command, "s1", case.context)
    elif entry == "mention":
        response, content = case.view._process_mention(f"@bot {command}", 4, "s1", case.context)
    else:
        response, content = case.view._process_mention_fallback(f"@bot {command}", "s1", case.context)
    code = SessionManager.generate_session_code("alice", "test-agent", "original-thread")
    case.lookup.assert_called_once_with(group_id="group-1" if case.mode == "polling" else "group-1:alice")
    case.manager_cls.assert_called_once_with(username="alice")
    case.manager.retrieve_session.assert_called_once_with(code)
    assert response["stream"]["finish"] and response["stream"]["id"] == "s1" and content == ""
    if command.startswith("/title"):
        case.manager.update_session_name.assert_called_once_with(code, "日志 查询")
        assert "已修改" in response["stream"]["content"]
        case.link.assert_not_called()
    else:
        assert f"https://agent.example.com/chat-window/?session={code}" in response["stream"]["content"]
        case.manager.update_session_name.assert_not_called()
    case.manager.get_or_create_by_thread_id.assert_not_called()
    case.record.update_session.assert_not_called()


@pytest.mark.parametrize("command", ["/title", "/title " + "长" * 256, "/title a\nb", "/web something"])
def test_invalid_command_arguments_do_not_touch_sessions(command_case, command):
    case = command_case
    response = case.view._resolve_builtin_command(command, "s1", case.context)
    assert "用法" in response["stream"]["content"]
    case.lookup.assert_not_called()
    case.manager_cls.assert_not_called()


@pytest.mark.parametrize("command", ["/titlex", "/website", "请用 /title 命名", "1A；2BC"])
def test_ordinary_text_is_not_misidentified_as_a_command(command_case, command):
    case = command_case
    assert case.view._resolve_builtin_command(command, "s1", case.context) is None
    case.lookup.assert_not_called()


@pytest.mark.parametrize("missing", ["local", "platform", "permission"])
@pytest.mark.parametrize("command", ["/title 新标题", "/web"])
def test_missing_or_inaccessible_session_is_never_created(command_case, missing, command):
    case = command_case
    if missing == "local":
        case.lookup.side_effect = views.AgentSession.DoesNotExist
    elif missing == "platform":
        case.manager.retrieve_session.return_value = {}
    else:
        case.manager.retrieve_session.side_effect = PermissionError("private detail")
    response = case.view._resolve_builtin_command(command, "s1", case.context)
    assert response["stream"]["finish"]
    assert "当前没有" in response["stream"]["content"] or "操作未成功" in response["stream"]["content"]
    assert "private detail" not in response["stream"]["content"]
    case.manager.get_or_create_by_thread_id.assert_not_called()
    case.manager.update_session_name.assert_not_called()
    case.link.assert_not_called()


def test_failed_title_update_never_reports_success(command_case):
    case = command_case
    case.manager.update_session_name.side_effect = RuntimeError("private detail")
    response = case.view._resolve_builtin_command("/title 新标题", "s1", case.context)
    assert "操作未成功" in response["stream"]["content"]
    assert "已修改" not in response["stream"]["content"]


@pytest.mark.parametrize("url", ["", "javascript:alert(1)", "/relative"])
def test_web_missing_or_unsafe_configuration_is_explicit(command_case, url):
    case = command_case
    case.link.side_effect = None
    case.link.return_value = url
    response = case.view._resolve_builtin_command("/web", "s1", case.context)
    assert "检查配置" in response["stream"]["content"]
