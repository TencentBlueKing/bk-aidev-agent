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

Agent work is submitted to the shared Bkplugin executor, which supports 16 active tasks by default and queues up to 32
additional tasks across channels. A single-chat sender or group chat may only have one reply in flight: while one is generating,
further requests are rejected with a terminal response, and the active run is never cancelled implicitly. The
rejection tells the sender to send `/stop` only when the running reply is their own — `/stop` and `/new` act on the
sender alone, since each group member keeps a separate conversation (the platform derives `session_code` from the
username). Different conversations still execute concurrently. Long-connection Chat requests use the
SDK retry strategy for model rate limits without changing the legacy HTTP callback strategy. The default stream
timeout is 600 seconds so an in-progress retry can finish. Override `BKAPP_AIDEV_AGENT_MAX_WORKERS`,
`BKAPP_AIDEV_AGENT_MAX_PENDING`, and `BKAPP_WXAIBOT_WS_STREAM_TIMEOUT_SEC` when the deployment's upstream Agent or
database capacity requires different limits. Stream cleanup runs in a separate Bkplugin-owned bounded executor
(2 workers and 32 pending tasks by default); override `BKAPP_AIDEV_AGENT_CLEANUP_MAX_WORKERS` and
`BKAPP_AIDEV_AGENT_CLEANUP_MAX_PENDING` only when upstream cleanup behavior requires it. Health logs expose generation
and cleanup executor usage, drain timeouts/rejections, and busy-rejected counts for capacity verification.

## WebSocket tracing

With the existing Agent OpenTelemetry integration enabled, each inbound message starts an independent
`wxbot.message.receive` trace. This short intake span ends after dispatch; the child
`wxbot.long_connection.session` span stays open while consuming Agent output and awaiting reply/card acknowledgments.
Context is propagated through asynchronous tasks and explicitly copied into the bounded Agent and cleanup executors.
No OpenTelemetry dependency or exporter is required to keep message processing operational.

| Span | Operation |
| --- | --- |
| `wxbot.message.receive` / `wxbot.message.prepare` | Receive and prepare an inbound message |
| `wxbot.identity.convert_to_rtx` | Convert the sender identity; `wxbot.identity.fallback` indicates fallback |
| `wxbot.agent.stream` | Execute/consume Agent output within the message trace |
| `wxbot.approval_card.build` | Inspect the terminal approval event; `wxbot.approval.pending` indicates a card was built |
| `wxbot.reply_stream` / `wxbot.approval_card.send` | Await stream/card sends, reconnect waits and retries |
| `wxbot.message.reply` / `wxbot.message.welcome` | Send non-stream replies |
| `wxbot.approval.cancel` / `wxbot.approval_card.update` | Process an approval cancellation and update the card |
| `wxbot.channel_config.fetch` / `wxbot.connection.connect` | Fetch channel configuration and establish the initial connection |

Platform identity/configuration requests carry W3C trace headers. Send spans expose `wecom.send.attempts`,
`wecom.send.retries`, `wecom.disconnected_wait_ms`, and successful `wecom.ack.errcode=0` / `wecom.ack.received=true`.
Retry events and failed spans record only error types and numeric acknowledgment error codes, never message bodies,
usernames, card URLs, tokens or raw exception messages/stacks. A successful acknowledgment is not proof that the
client displayed the card. `wxbot_message_received`, `wxbot_ws_stream_started`, and approval-card result/retry logs
include `trace_id` for correlation. For log-only export, the existing `aidev_otel_span` event exposes span names,
parent IDs, status and duration; detailed attributes/events are available through the trace exporter.

## License

MIT License
