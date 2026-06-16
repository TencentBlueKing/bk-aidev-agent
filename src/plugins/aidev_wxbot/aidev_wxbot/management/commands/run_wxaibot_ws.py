"""启动企业微信机器人长连接。"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from aidev_wxbot.wxaibot.long_connection import (
    LongConnectionConfigError,
    WxAiBotLongConnectionConfig,
    WxAiBotLongConnectionService,
)


class Command(BaseCommand):
    help = "启动企业微信智能机器人长连接接入服务"

    def add_arguments(self, parser):
        parser.add_argument("--bot-id", dest="bot_id", help="企微机器人 BotID")
        parser.add_argument("--secret", dest="secret", help="企微机器人长连接 Secret")
        parser.add_argument("--ws-url", dest="ws_url", help="自定义 WebSocket 地址")
        parser.add_argument(
            "--reconnect-interval-ms",
            dest="reconnect_interval_ms",
            type=int,
            help="重连基础间隔，单位毫秒",
        )
        parser.add_argument(
            "--max-reconnect-attempts",
            dest="max_reconnect_attempts",
            type=int,
            help="最大重连次数，-1 表示无限重连",
        )
        parser.add_argument(
            "--heartbeat-interval-ms",
            dest="heartbeat_interval_ms",
            type=int,
            help="心跳间隔，单位毫秒",
        )
        parser.add_argument(
            "--request-timeout-ms",
            dest="request_timeout_ms",
            type=int,
            help="请求超时，单位毫秒",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "WXAIBOT_WS_ENABLED", False):
            raise CommandError("WXAIBOT_WS_ENABLED 未开启，拒绝启动企微机器人长连接服务")

        try:
            config = WxAiBotLongConnectionConfig.from_settings(**options)
        except LongConnectionConfigError as error:
            raise CommandError(str(error)) from error

        self.stdout.write(self.style.SUCCESS("启动企微机器人长连接服务"))
        service = WxAiBotLongConnectionService(config)
        service.run()
