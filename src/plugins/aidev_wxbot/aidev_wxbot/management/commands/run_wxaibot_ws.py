"""启动企业微信机器人长连接。"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from aidev_wxbot.api.bkaidev import BkAiDevApi
from aidev_wxbot.wxaibot.long_connection import (
    LongConnectionConfigError,
    WxAiBotLongConnectionConfig,
    WxAiBotLongConnectionService,
)


class Command(BaseCommand):
    help = "启动企业微信智能机器人长连接接入服务"

    def _retrieve_channel_config(self):
        try:
            configs = BkAiDevApi().retrieve_agent_channel_configs("rtx")
        except Exception as error:
            self.stderr.write(self.style.WARNING(f"获取企微渠道配置失败，将使用默认值: {error}"))
            return {}

        for item in configs or []:
            if item.get("channel_type") == "rtx":
                return item.get("config") or {}
        return {}

    def handle(self, *args, **options):
        if not getattr(settings, "WXAIBOT_WS_ENABLED", False):
            raise CommandError("WXAIBOT_WS_ENABLED 未开启，拒绝启动企微机器人长连接服务")

        env_config = {
            "bot_id": os.getenv("BKAPP_WXAIBOT_WS_BOT_ID"),
            "secret": os.getenv("BKAPP_WXAIBOT_WS_SECRET"),
            "ws_url": os.getenv("BKAPP_WXAIBOT_WS_URL"),
        }
        channel_config = self._retrieve_channel_config() if not all(env_config.values()) else {}
        options.update(
            {
                "bot_id": env_config["bot_id"] or channel_config.get("bot_id") or "",
                "secret": env_config["secret"] or channel_config.get("secret") or "",
                "ws_url": env_config["ws_url"] or channel_config.get("ws_url") or "",
            }
        )

        try:
            config = WxAiBotLongConnectionConfig.from_settings(**options)
        except LongConnectionConfigError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS("启动企微机器人长连接服务"))
        service = WxAiBotLongConnectionService(config)
        service.run()
