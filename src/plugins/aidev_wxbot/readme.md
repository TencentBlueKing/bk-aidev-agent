# aidev-wxbot-plugin

A WeChat bot plugin for bkaidev platform.

## Description

This plugin provides WeChat bot functionality for the bkaidev platform, enabling automated message handling and responses.

## Features

- WeChat message callback handling
- Automated message processing
- Integration with bkaidev platform

## Installation

```bash
pip install aidev_wxbot
```

## Usage

Configure the plugin in your bkaidev platform and set up the WeChat bot callback URL.

For WebSocket long connections, the Agent executor supports 10 active sessions by default and queues up to 16
additional sessions. A single-chat sender or group chat may only have one reply in flight: while one is generating,
further requests are rejected with a terminal response, and the active run is never cancelled implicitly. The
rejection tells the sender to send `/stop` only when the running reply is their own — `/stop` and `/new` act on the
sender alone, since each group member keeps a separate conversation (the platform derives `session_code` from the
username). Different conversations still execute concurrently. Long-connection Chat requests use the
SDK retry strategy for model rate limits without changing the legacy HTTP callback strategy. The default stream
timeout is 600 seconds so an in-progress retry can finish. Override `BKAPP_WXAIBOT_AGENT_MAX_WORKERS`,
`BKAPP_WXAIBOT_AGENT_MAX_PENDING`, and `BKAPP_WXAIBOT_WS_STREAM_TIMEOUT_SEC` when the deployment's upstream Agent or
database capacity requires different limits. Health logs expose active, pending, peak, submitted, rejected, and
busy-rejected counts for capacity verification.

## License

MIT License
