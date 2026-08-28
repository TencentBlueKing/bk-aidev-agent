"""启动企业微信机器人长连接。"""

import os

from aidev_agent.utils.tracing import setup_tracing
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from aidev_wxbot.api.bkaidev import BkAiDevApi
from aidev_wxbot.wxaibot.channel_config import find_rtx_channel, get_channel_config, get_connection_type
from aidev_wxbot.wxaibot.long_connection import (
    LongConnectionConfigError,
    WxAiBotLongConnectionConfig,
    WxAiBotLongConnectionService,
)


class Command(BaseCommand):
    help = "启动企业微信智能机器人长连接接入服务"

    def _retrieve_channel(self):
        try:
            channels = BkAiDevApi().retrieve_agent_channel_configs("rtx")
        except Exception as error:
            raise CommandError(f"获取企微渠道配置失败，无法启动长连接服务: {error}") from error

        return find_rtx_channel(channels)

    def handle(self, *args, **options):
        if not getattr(settings, "WXAIBOT_WS_ENABLED", False):
            raise CommandError("WXAIBOT_WS_ENABLED 未开启，拒绝启动企微机器人长连接服务")

        # 必须早于任何出站请求：instrument 之后建立的 requests 会话才会带上 traceparent
        setup_tracing(console=getattr(settings, "WXAIBOT_TRACE_CONSOLE", False))

        channel = self._retrieve_channel()
        if not channel:
            raise CommandError("未找到已启用的企微渠道，请确认平台 RTX 渠道已启用，且当前 app_code 能拉到该渠道")

        connection_type = get_connection_type(channel)
        if connection_type != "websocket":
            raise CommandError(
                f"企微渠道未配置长连接接入，当前 connection_type={connection_type or '未配置'}，期望 websocket"
            )

        channel_config = get_channel_config(channel)
        raw_config = {
            "bot_id": os.getenv("BKAPP_WXAIBOT_WS_BOT_ID") or channel_config.get("bot_id"),
            "secret": os.getenv("BKAPP_WXAIBOT_WS_SECRET") or channel_config.get("secret"),
            "ws_url": os.getenv("BKAPP_WXAIBOT_WS_URL") or channel_config.get("ws_url"),
        }

        try:
            config = WxAiBotLongConnectionConfig.from_settings(**raw_config)
        except LongConnectionConfigError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS(f"启动企微机器人长连接服务, bot_id={config.bot_id}"))
        WxAiBotLongConnectionService(config).run()
