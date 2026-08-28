# bk-aidev-agent 本地 E2E

这套环境只 mock 智能体以外的远端服务（登录、AIDev Session/Agent 配置、LLM）。Django 应用、SQLite、Redis、RabbitMQ 和消息往返都真实运行；SQLite 是默认且隔离的本地数据库，MySQL 5.7 保留为可选兼容性基线。指标启用时复用 `dev/otel`，链路为 Agent → OTel Collector → Prometheus → Grafana。

## 快速开始

```bash
cp dev/e2e/.env.example dev/e2e/.env
# 按需填写 E2E_USERNAME，或填写优先级更高的 E2E_ACCESS_TOKEN
make e2e-setup
make e2e-up
make e2e
make e2e-down
```

默认数据库为 SQLite，不需要额外容器。若要执行 MySQL 5.7 兼容性检查，启动和执行时使用同一个选择：

```bash
make e2e-up db=mysql
make e2e db=mysql
make e2e-down
```

`.env` 同时配置了 access token 和 username 时，测试先向本地登录 mock 校验 access token，再使用其解析出的 username 调用本地应用；不会把 token 写入日志、JSON 或 HTML。两者都没配置时本次执行失败，但仍生成报告。

## 分模块执行

```bash
make e2e-api
make e2e-ai-blueking
make e2e-message
make e2e-metrics
make e2e-wxbot
make e2e-browser                 # 默认打开 AI 小鲸 headed 浏览器检查
make e2e-browser modules=api     # 也可指定模块
```

默认 `headless=true`，适合流水线。交互检查可执行 `make e2e headless=false`，然后使用内置浏览器打开 `E2E_APP_URL` 和本次报告。每一次 runner 执行（包括配置或基础设施失败）都会生成：

- `dev/e2e/reports/<timestamp>/report.html`
- `dev/e2e/reports/<timestamp>/result.json`
- `dev/e2e/reports/latest.html`

这些运行产物和 `.env` 都已忽略，不会提交。若只需扩展测试框架并做快速回归，执行 `make -C dev/e2e test`。

Grafana 仪表盘地址为 <http://127.0.0.1:3000/d/aidev-agent-metrics>，Prometheus 为 <http://127.0.0.1:9090>。指标模块会检查 Prometheus 可查询，以及 Grafana 中预置的智能体仪表盘可读取。
