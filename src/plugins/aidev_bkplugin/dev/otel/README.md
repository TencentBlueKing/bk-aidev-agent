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
PYTHONPATH=../../agent uv run --no-sync python dev/otel/mock_agent_metrics.py
```

等待 2～5 秒后刷新 Grafana。也可以直接在 Prometheus 查询：

```promql
{__name__=~"gen_ai_invoke_agent_duration.*"}
```

“当前活跃 Agent 执行数”统计正在执行的 Agent run，不代表已持久化但空闲的
历史 session。平均智能体轮数和平均工具调用次数按 Grafana 当前选择的时间范围，
使用该范围内的累计增量计算；范围内没有已完成调用时显示 `No data`，不显示伪造的 0。

指标身份维度包含 `agent.info.code`、`agent.info.name` 和
`agent.info.sdk_version`；不包含固定值 `agent.info.type`。Agent 版本由 bkplugin
从平台下发并解码后的 `agent_info.agent_sdk_version` 获取，缺失时使用 `unknown`。

## 查看原始指标数据

Collector 的 `debug` exporter 会把每批 OTLP `MetricData`（resource、scope、data
point 和聚合值）输出到容器日志：

```bash
docker compose logs -f otel-collector
```

Prometheus exporter 的原始 exposition 文本可通过以下命令查看：

```bash
curl http://localhost:8889/metrics
curl 'http://localhost:9090/api/v1/query?query=aidev_session_active'
```

本地 Collector 已开启 `resource_to_telemetry_conversion`，因此 OTLP resource
属性 `agent.info.sdk_version` 会在 Prometheus 中显示为标签
`agent_info_sdk_version`。

Prometheus 保存的是按 scrape 时间采集的聚合时间序列，不是逐次 Agent 事件；如果要
定位单次执行，请结合对应 Trace，而不是尝试从 Counter 或 Histogram 反推事件明细。

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
