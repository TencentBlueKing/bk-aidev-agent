"""读取平台 OpenAPI 企微渠道配置。

- 顶层：channel_id、channel_name、channel_type、channel_icon、connection_type、websocket_connected、config
- config：bot_id、secret、ws_url、contact、rtx_callback_url、rtx_token、rtx_encoding_aes_key
- connection_type 只在顶层；expose_channel_payload 会从 config 弹出
- contact 由 OpenAPI 写入 config，不在顶层
"""

from typing import Any


def find_rtx_channel(channels: list[dict[str, Any]] | None) -> dict[str, Any]:
    for channel in channels or []:
        if not isinstance(channel, dict):
            continue
        if channel.get("channel_type") == "rtx":
            return channel
    return {}


def get_channel_config(channel: dict[str, Any]) -> dict[str, Any]:
    config = channel.get("config")
    return config if isinstance(config, dict) else {}


def get_connection_type(channel: dict[str, Any]) -> str:
    return channel.get("connection_type") or ""


def get_channel_contact(channel: dict[str, Any]) -> str:
    return get_channel_config(channel).get("contact", "")
