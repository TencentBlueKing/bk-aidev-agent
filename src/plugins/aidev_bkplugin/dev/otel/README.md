# AIDev Agent 本地指标验证

该环境验证完整路径：Agent 指标 API 埋点 → bkplugin OTLP/HTTP exporter →
OpenTelemetry Collector → Prometheus → Grafana 预置仪表盘。

## 启动

```bash
docker compose up -d
```

macOS 上使用 Podman 时可执行 `podman compose up -d`。

Collector 接收端口为 `4317`（gRPC）和 `4318`（HTTP），Prometheus 为
<http://localhost:9090>，Grafana 为 <http://localhost:3000/d/aidev-agent-metrics>。

## 发送 mock 指标

在仓库根目录执行：

```bash
cd src/plugins/aidev_bkplugin
uv run --no-sync python dev/otel/mock_agent_metrics.py
```

等待 2～5 秒后刷新 Grafana。也可以直接在 Prometheus 查询：

```promql
{__name__=~"gen_ai_invoke_agent_duration.*"}
```

## 使用真实 bkplugin 请求

平台下发的 `agent_info.otel_info` 解码后可使用：

```json
{
  "otel_url": "http://localhost:4318",
  "otel_token": "",
  "metrics": {
    "enabled": true,
    "export_interval_millis": 1000,
    "export_timeout_millis": 5000
  }
}
```

如果 bkplugin 也运行在 Docker 中，将地址改为
`http://host.docker.internal:4318`，或改为同一 Compose 网络内的
`http://otel-collector:4318`。

环境变量仍可覆盖本地配置：

```bash
export BKAI_AGENT_OTEL_ENABLED=true
export BKAI_AGENT_ENABLE_METRICS=true
export BKAI_AGENT_OTEL_EXPORTER_TYPE=http
export BKAI_AGENT_OTEL_ENDPOINTS='[{"url":"http://localhost:4318","token":"","exporter_type":"http"}]'
```

完成后执行 `docker compose down`（Podman 使用 `podman compose down`）停止环境。
