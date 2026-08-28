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
additional sessions. Requests from the same single-chat sender or group chat are serialized through a bounded,
in-process FIFO queue instead of cancelling the active run; different conversations still execute concurrently. The
per-conversation queue accepts 10 waiting requests by default and returns an explicit terminal response when full.
Long-connection Chat requests use the SDK retry strategy for model rate limits without changing the legacy HTTP
callback strategy. The default stream timeout is 600 seconds so an in-progress retry can finish. Override
`BKAPP_WXAIBOT_AGENT_MAX_WORKERS`, `BKAPP_WXAIBOT_AGENT_MAX_PENDING`, `BKAPP_WXAIBOT_WS_GROUP_QUEUE_SIZE`, and
`BKAPP_WXAIBOT_WS_STREAM_TIMEOUT_SEC` when the deployment's upstream Agent or database capacity requires different
limits. Health logs expose active, queued, pending, peak, submitted, dequeued, and rejected counts for capacity
verification.

## License

MIT License
