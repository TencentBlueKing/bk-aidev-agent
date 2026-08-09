# AIDev Agent 本地指标验证

该环境验证完整路径：Agent 指标 API 埋点 → bkplugin OTLP/HTTP exporter →
OpenTelemetry Collector → Prometheus → Grafana 预置仪表盘。

## 启动

在仓库根目录执行，一条命令会使用 Podman 启动 Collector、Prometheus、Grafana，
并在当前终端运行默认 mock：

```bash
cd dev/otel
make start
```

默认 mock 持续约 10 分钟；执行期间可直接观察终端输出，`Ctrl+C` 只停止 mock。
在另一个终端查看 Podman 服务状态：

```bash
make status
```

Collector 接收端口为 `4317`（gRPC）和 `4318`（HTTP），Prometheus 为
<http://localhost:9090>，Grafana 为 <http://localhost:3000/d/aidev-agent-metrics>。

## 发送 mock 指标

`make start` 默认同时模拟 4 个 Handler，每个 Handler 每轮随机启动 1～3 个 Agent Run，
因此“当前活跃 Agent 执行数”会在 `4～12` 之间变化。可以在启动时覆盖参数：

```bash
make start N=3 MODELS=mock-a,mock-b,mock-c ITERATIONS=400 INTERVAL=1.5
```

使用 `-n/--concurrency` 指定每个 Handler 的并发上限。例如 `-n 5` 时，每个 Handler
每轮随机启动 1～5 个 Run，总活跃 Agent 数在 `4～20` 之间变化；`-n 1` 时固定为 4：

```bash
make start N=5
```

默认启用 `mock-log-analysis-a`、`mock-log-analysis-b`、`mock-log-analysis-c` 三个
mock 模型，实际 Run 会按模型列表轮询分配。启动时可指定任意 1～n 个逗号分隔的模型名：

```bash
make start N=3 MODELS=mock-a,mock-b,mock-c
```

也可以使用 `AIDEV_MOCK_MODELS=mock-a,mock-b`；模型名仅作为本地指标的低基数过滤维度。

每个 Run 的 Agent 总耗时随机控制在 `30～120s`，再随机分配给 6 次 LLM、4 次 Tool
和 Agent 自身处理，三类阶段累计值严格等于 Agent 总耗时；LLM TTFT 不超过对应的
LLM 调用耗时。同一 `--seed` 会得到可重复的并发和耗时序列。

如果只需要前台运行 mock，不重启 Podman 服务：

```bash
make mock N=3 ITERATIONS=40 INTERVAL=1.5
```

原有的 `AIDEV_MOCK_CONCURRENCY`、`AIDEV_MOCK_ITERATIONS`、
`AIDEV_MOCK_INTERVAL_SECONDS` 环境变量仍可使用，命令参数优先。可以通过 `--seed`
让每轮并发变化可重复验证。

mock 使用“日志查询与聚合总结”场景，模拟 6 次 LLM 调用和 4 次工具调用。
`activate_skill` 来自实际验证链路；其余日志工具统一使用
`inspect_log_fields`、`search_logs`、`aggregate_logs` 脱敏别名。业务 ID、索引集 ID、
时间、节点、日志正文和总结均为不可回推的合成数据，不保留原会话的真实内容。

默认同步生成 `inmemory`、`rabbitmq`、`rabbitmq_stream`、`redis` 四组指标。
如只需验证单个 Message Handler，可显式指定：

```bash
make start HANDLER=redis N=3
```

可选值为 `all`、`inmemory`、`rabbitmq`、`rabbitmq_stream`、`redis`；
`AIDEV_MOCK_MESSAGE_HANDLER` 环境变量也继续兼容。mock 会按模型与工具输出的
编码大小生成 SSE 事件大小、响应大小、合并前逻辑事件数和合并后物理写入数；
模型/工具正文不会进入指标标签或 OTLP resource。

等待 2～5 秒后刷新 Grafana。也可以直接在 Prometheus 查询：

```promql
{__name__=~"gen_ai_invoke_agent_duration.*"}
```

“当前活跃 Agent 执行数”统计正在执行的 Agent run，不代表已持久化但空闲的
历史 session。平均智能体轮数和平均工具调用次数按 Grafana 当前选择的时间范围，
使用该范围内的累计增量计算；范围内没有已完成调用时显示 `No data`，不显示伪造的 0。

仪表盘提供以下多选过滤器，`All` 使用正则 `.*`：

- `Agent Code`、`Agent Version`：作用于全部面板；
- `Request Model`：作用于 LLM 耗时、并发和 Token 面板；
- `Message Handler`：作用于 SSE 与消息发布面板，值为实际生效的 handler；
- `Token Type`：区分 `input`、`output`、`cache_creation`、`cache_read`；
- `SSE Event Type`：按 SSE 协议事件类型过滤。

“Agent 总耗时与子阶段累计耗时”展示 Agent 总耗时以及每次调用累计的 LLM、Tool、Agent
自身处理耗时。子调用并行时这些阶段不是严格互斥的墙钟时间，单次调用的精确分配应查看
Trace。“Broker 写入压力与合并效果”区分合并前逻辑事件数和合并后物理写入数，并按
`aidev.message.handler.type` 展示实际使用的 `inmemory`、`rabbitmq`、`rabbitmq_stream`
或 `redis`。

指标身份维度包含 `agent.info.code`、`agent.info.name` 和
`agent.info.sdk_version`；不包含固定值 `agent.info.type`。Agent 版本由 bkplugin
从平台下发并解码后的 `agent_info.agent_sdk_version` 获取，缺失时使用 `unknown`。
bkplugin 同时设置标准 Resource 属性 `service.instance.id`，用于区分同一服务的不同进程；
仪表盘按 Agent 聚合该属性，因此多进程活跃数能够正确求和，但不把实例 ID 暴露为业务过滤器。

## 查看原始指标数据

Collector 的 `debug` exporter 会把每批 OTLP `MetricData`（resource、scope、data
point 和聚合值）输出到容器日志：

```bash
podman compose logs -f otel-collector
```

Prometheus exporter 的原始 exposition 文本可通过以下命令查看：

```bash
curl http://localhost:8889/metrics
curl 'http://localhost:9090/api/v1/query?query=aidev_session_active'
curl 'http://localhost:9090/api/v1/query?query=gen_ai_client_operation_active'
curl 'http://localhost:9090/api/v1/query?query=aidev_message_publish_count_total'
```

本地 Collector 已开启 `resource_to_telemetry_conversion`，因此 OTLP resource
属性 `agent.info.sdk_version` 会在 Prometheus 中显示为标签
`agent_info_sdk_version`。

Prometheus 保存的是按 scrape 时间采集的聚合时间序列，不是逐次 Agent 事件；如果要
定位单次执行，请结合对应 Trace，而不是尝试从 Counter 或 Histogram 反推事件明细。

本地观测配置和 mock 测试均位于 `dev/otel`。执行以下命令同时验证 bkplugin exporter
和本地观测场景：

```bash
make test
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

完成后停止全部 Podman 服务：

```bash
make stop
```
