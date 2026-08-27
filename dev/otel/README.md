# AIDev Agent 本地指标验证

该环境验证完整路径：Agent 指标 API 埋点 → bkplugin OTLP/HTTP 直连（仅本地）→
OpenTelemetry Collector → Prometheus → Grafana 预置仪表盘。生产环境默认由源进程的
OpenTelemetry Reader 定期生成累计快照，经 `plugin_schedule` 队列交给 Celery Worker，
再按 BKM 自定义指标协议推送到 `${PROXY_IP}:10205/v2/push/`。

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
本地镜像固定为 Grafana `10.4.19`，仪表盘使用该版本生成的 schema 39，保持与线上
Grafana 10.x 的兼容性；后续编辑和导出也应继续使用 10.x 环境。

## 蓝鲸监控仪表盘

线上蓝鲸监控导入版位于
`grafana/components/aidev-agent-metrics-bkmonitor.json`。它参考
`monitor-as-code/grafana/components/bkaidev-resource.json`，使用
`bkmonitor-timeseries-datasource`、`source/promqlAlias` 查询结构和蓝鲸监控变量协议；
保留与本地版相同的 34 个面板、过滤维度和 PromQL 计算语义。

该文件不在本地 Grafana provisioning 的 `grafana/dashboards` 目录中，不会覆盖或加载为
本地 Prometheus 仪表盘。修改本地版面板后，可重新生成独立的蓝鲸监控配置：

```bash
cd dev/otel
make dashboard-bkmonitor
```

该配置固定使用 UID `cfjy28njb6ghsd` 的“蓝鲸监控 - 指标数据”数据源。蓝鲸监控版默认
查询最近 1 小时，按 1 分钟、5 分钟或 1 小时窗口计算速率和 P95；本地 Prometheus 版
仍保持最近 15 分钟和 5 秒刷新。

## 发送 mock 指标

`make start` 默认同时模拟 4 个 Handler。每个 Handler 有一个持续运行的基础槽位，
另外两个槽位按随机间隔启停新的 Agent Run，因此活跃 Run 会在 `4～12` 之间变化。
可以在启动时覆盖参数：

```bash
make start N=3 MODELS=mock-a,mock-b,mock-c ITERATIONS=400 INTERVAL=1.5
```

使用 `-n/--concurrency` 指定每个 Handler 的并发上限。例如 `-n 5` 时，每个 Handler
同时运行 1～5 个 Run，总活跃 Agent 数在 `4～20` 之间变化；`-n 1` 时固定为 4：

```bash
make start N=5
```

默认启用 `mock-log-analysis-a`、`mock-log-analysis-b`、`mock-log-analysis-c` 三个
mock 模型，实际 Run 会按模型列表轮询分配。启动时可指定任意 1～n 个逗号分隔的模型名：

```bash
make start N=3 MODELS=mock-a,mock-b,mock-c
```

也可以使用 `AIDEV_MOCK_MODELS=mock-a,mock-b`；模型名仅作为本地指标的低基数过滤维度。

每个 Run 会真实执行 `30～120s`，耗时随机分配给 6 次 LLM、4 次 Tool、Agent processing
和 finalizing 阶段；LLM TTFT 不超过对应的 LLM 调用耗时。Mock 不再每 1.5 秒瞬时上报
一个伪造的长耗时完成样本，因此 Agent 并发、进入/完成速率和耗时满足真实生命周期关系。
同一 `--seed` 会得到可重复的耗时与模型分配序列。

如果只需要前台运行 mock，不重启 Podman 服务：

```bash
make mock N=3 ITERATIONS=40 INTERVAL=1.5
```

原有的 `AIDEV_MOCK_CONCURRENCY`、`AIDEV_MOCK_ITERATIONS`、
`AIDEV_MOCK_INTERVAL_SECONDS` 环境变量仍可使用，命令参数优先。可以通过 `--seed`
让耗时和运行槽位行为可重复验证。

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
编码大小生成合并前 SSE 逻辑事件数、合并后物理写入数和物理消息 Payload 大小；
模型/工具正文不会进入指标标签或 OTLP resource。

等待 2～5 秒后可以观察活跃 Run 和阶段；首批完成耗时、迭代、SSE 和 Broker 指标需要等待
至少 30 秒。也可以直接在 Prometheus 查询：

```promql
{__name__=~"gen_ai_invoke_agent_duration.*"}
```

“活跃 Agent Run”统计正在执行的 Run，不代表已持久化但空闲的历史 session。
当前阶段按 `processing`、`llm`、`tool`、`finalizing`、`mixed` 互斥统计；具体 Run 身份
需要查看 Trace 或日志。平均 Agent 迭代次数把一次 LLM 推理定义为一次迭代；范围内没有
已完成 Run 时显示 `No data`，不显示伪造的 0。

仪表盘提供以下多选过滤器，`All` 使用正则 `.*`：

- `Agent Code`、`Agent Version`：作用于全部面板；
- `Request Model`：作用于全部 LLM 面板；`Response Model` 只有调用结束后可用，因此只作用于
  LLM 已结束调用耗时和完成速率；
- `Tool Name`：作用于 Tool 活跃数和耗时面板；
- `Message Handler`：作用于 SSE 与消息发布面板，值为实际生效的 handler。

“活跃 Agent Run”展示当前仍在执行的 Run 总数，并应与各 Agent 阶段并发之和一致；
“活跃智能体数量”展示至少有一个 Run 正在执行的 Agent Code 去重数，同一 Agent Code 的多个并发 Run
只计为 1。两者都不是累计会话次数。“Agent 阶段并发”展示当前值与时间走势；耗时类折线图统一展示 P95，
其中“Agent 阶段耗时 P95”只统计已经结束的阶段，
因为运行中的阶段尚未产生 Histogram 样本。阶段累计时间占比来自阶段切换时的直接计时，互斥阶段
在同一窗口内合计约 100%，不再用子调用累计值除以已完成 Run 数估算耗时分配。
Agent 首 Token 趋势按 Agent Code 展示流式 Run 从开始到首个 Token 的 P95，非流式 Run 不产生样本；
顶部同名卡片是所选 Agent 的聚合摘要。LLM 展示按模型
拆分的并发、完成速率和已结束调用耗时；Tool 展示按工具名称拆分的并发和已结束调用耗时。
“SSE 输出与物理消息”以与发布速率面板一致的折线和表格图例展示每个查询窗口的
SSE 逻辑事件数量、物理消息数量及 SSE/物理消息压缩比，并按 Handler 名称升序，
不再按 SSE 事件类型拆分；“Broker 发布侧”展示合并前逻辑事件速率、
合并后物理消息速率、所选时段按 Agent Code 去重的 Handler 分布、应用序列化 Payload IO、消息大小和
Handler 写入耗时，并按 Handler 名称升序展示。
Payload IO 不等于 RabbitMQ/Redis 的网络、磁盘 IO；队列积压、消费 lag 和真实 IO 仍需
对应 Broker 的原生 exporter。

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
curl 'http://localhost:9090/api/v1/query?query=aidev_agent_active'
curl 'http://localhost:9090/api/v1/query?query=aidev_agent_phase_active'
curl 'http://localhost:9090/api/v1/query?query=gen_ai_client_operation_active'
curl 'http://localhost:9090/api/v1/query?query=gen_ai_execute_tool_active'
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
    "export_interval_millis": 10000,
    "export_timeout_millis": 30000,
    "export_via_celery": true,
    "agent_data_id": 1001,
    "agent_access_token": "<由平台下发>",
    "agent_push_url": "http://proxy.example:10205/v2/push/",
    "agent_target": "127.0.0.1"
  }
}
```

`otel_url/otel_token` 继续用于 Trace；指标使用 Agent 命名空间下的
`agent_data_id/agent_access_token/agent_push_url` 独立配置，不能复用 Trace token。
`agent_push_url` 未配置时会根据 Worker 的 `PROXY_IP` 自动生成
`http://${PROXY_IP}:10205/v2/push/`；`agent_target` 未配置时使用指标源进程所在主机名。
`data_id`、`access_token` 与完整 URL 不进入 Celery 消息，Broker 中只有不可逆端点指纹和
不含凭据的指标数据。Worker 按以下协议补齐凭据并推送：

```json
{
  "data_id": 1001,
  "access_token": "***",
  "data": [
    {
      "metrics": {"aidev_agent_active": 3},
      "target": "127.0.0.1",
      "dimension": {"agent_info_code": "ai-demo"},
      "timestamp": 1786300118338
    }
  ]
}
```

OTel Counter 转成 BKM 的 `*_total`；Histogram 转成累计 `*_bucket`（`le` 维度）、
`*_sum` 和 `*_count`，因此现有速率与 P95 查询语义保持不变。这里不依赖 Celery Beat：
各产生指标的进程负责按 `export_interval_millis` 截取自己的累计快照，Celery Worker 只负责
可靠隔离实际网络请求，避免 Worker 无法读取其他进程内存中的 OTel 聚合器。
生产默认周期为 10 秒；显式下发 `export_interval_millis` 时仍以配置值为准。本地 mock 为了缩短
仪表盘验证等待时间，继续使用 1 秒周期。

本地生成项目默认使用 `BKAI_AGENT_ENABLE_METRICS=false` 强制关闭指标，该显式环境变量的优先级
高于平台下发的 `otel_info.metrics.enabled`。需要联调 BKM 时改为 `true` 并配置以下参数；平台下发的
`otel_info.metrics.agent_*` 仍优先于同名连接参数环境变量：

```bash
BKAI_AGENT_ENABLE_METRICS=true
BKAI_AGENT_METRICS_HOST=proxy.example
BKAI_AGENT_METRICS_DATA_ID=1001
BKAI_AGENT_METRICS_TOKEN=<本地密钥>
BKAI_AGENT_METRICS_TARGET=127.0.0.1
```

如果 bkplugin 也运行在 Docker 中，将地址改为
`http://host.docker.internal:4318`，或改为同一 Compose 网络内的
`http://otel-collector:4318`。

本地 Collector 场景必须关闭 Celery/BKM 转发，由 mock 自动设置
`export_via_celery=false`；真实 bkplugin 如需直连本地 Collector，也可临时使用相同配置。

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
