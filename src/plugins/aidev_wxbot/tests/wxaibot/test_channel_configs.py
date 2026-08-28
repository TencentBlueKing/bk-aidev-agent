# -*- coding: utf-8 -*-
"""企微机器人渠道配置契约测试。形状对齐 bk-aidev PR #1950 OpenAPI。"""

from unittest.mock import MagicMock

from django.core.management.base import CommandError

from aidev_wxbot.management.commands.run_wxaibot_ws import Command
from aidev_wxbot.wxaibot.channel_config import (
    find_rtx_channel,
    get_channel_config,
    get_channel_contact,
    get_connection_type,
)

# 平台 OpenAPI 实测返回：connection_type / websocket_connected 在顶层；
# config 含 bot_id / secret / ws_url / contact / rtx_callback_url，不含 connection_type。
WEBSOCKET_CHANNEL = {
    "channel_id": 1,
    "channel_name": "企业微信机器人",
    "channel_type": "rtx",
    "channel_icon": "",
    "connection_type": "websocket",
    "websocket_connected": False,
    "config": {
        "bot_id": "bot-1",
        "secret": "secret-1",
        "ws_url": "wss://openws.work.weixin.qq.com",
        "contact": "admin_rtx",
        "rtx_callback_url": "https://example.com/wxbot_callback/",
    },
}


def test_command_returns_rtx_channel(monkeypatch):
    api = MagicMock()
    api.retrieve_agent_channel_configs.return_value = [WEBSOCKET_CHANNEL]
    monkeypatch.setattr("aidev_wxbot.management.commands.run_wxaibot_ws.BkAiDevApi", lambda: api)

    assert Command()._retrieve_channel() == WEBSOCKET_CHANNEL


def test_reads_openapi_channel_fields():
    assert find_rtx_channel([WEBSOCKET_CHANNEL]) == WEBSOCKET_CHANNEL
    assert get_connection_type(WEBSOCKET_CHANNEL) == "websocket"
    assert get_channel_config(WEBSOCKET_CHANNEL) == WEBSOCKET_CHANNEL["config"]
    assert get_channel_contact(WEBSOCKET_CHANNEL) == "admin_rtx"
    assert "connection_type" not in WEBSOCKET_CHANNEL["config"]


def test_find_rtx_channel_uses_channel_type_not_type():
    assert find_rtx_channel([{"type": "rtx", "config": {}}]) == {}
    assert find_rtx_channel([WEBSOCKET_CHANNEL])["channel_type"] == "rtx"


def test_ignores_connection_type_inside_config():
    channel = {
        "channel_type": "rtx",
        "config": {"connection_type": "websocket", "bot_id": "bot-1"},
    }
    assert get_connection_type(channel) == ""


def test_command_errors_when_rtx_channel_missing(monkeypatch):
    monkeypatch.setattr(Command, "_retrieve_channel", lambda _self: {})
    monkeypatch.setattr("aidev_wxbot.management.commands.run_wxaibot_ws.settings.WXAIBOT_WS_ENABLED", True)

    try:
        Command().handle()
    except CommandError as error:
        assert "未找到已启用的企微渠道" in str(error)
    else:
        raise AssertionError("expected CommandError")


def test_command_starts_single_websocket_service(monkeypatch):
    service = MagicMock()
    monkeypatch.setattr(Command, "_retrieve_channel", lambda _self: WEBSOCKET_CHANNEL)
    monkeypatch.setattr("aidev_wxbot.management.commands.run_wxaibot_ws.WxAiBotLongConnectionService", service)
    monkeypatch.setattr("aidev_wxbot.management.commands.run_wxaibot_ws.settings.WXAIBOT_WS_ENABLED", True)
    for env_name in ("BKAPP_WXAIBOT_WS_BOT_ID", "BKAPP_WXAIBOT_WS_SECRET", "BKAPP_WXAIBOT_WS_URL"):
        monkeypatch.delenv(env_name, raising=False)

    Command().handle()

    config = service.call_args.args[0]
    assert config.bot_id == "bot-1"
    assert config.secret == "secret-1"
    assert config.ws_url == "wss://openws.work.weixin.qq.com"
    service.return_value.run.assert_called_once_with()
