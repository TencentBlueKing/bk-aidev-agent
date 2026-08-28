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

标准 `make e2e` 只验证 API/登录、AI 小鲸与智能体对话、指标与可观测性；数据库与消息服务仅作为智能体运行所需的真实底层依赖，不单独形成健康结论。企业微信不进入默认范围，可通过独立模块按需执行。

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
make e2e-metrics
make e2e-wxbot
make e2e-browser                 # 默认打开 AI 小鲸 headed 浏览器检查
make e2e-browser modules=api     # 也可指定模块
```

`api` 模块对照模板 README 的“API 调用”章节验证：登录身份解析、远端 Session 生命周期、应用探活与应用态 Session、应用态/用户态非流式对话、`1.0.0assistant` 蓝鲸插件同步调用、AG-UI SSE 事件顺序，以及 `text + image_url` 多模态消息协议。

`ai-blueking` 模块重点覆盖页面与 Agent 配置、同步对话、SSE 正常终态、多轮上下文、断线后 attach
回放、生成中停止及重复停止、`ask_user_question` 提问卡片答题续流。需要用 RabbitMQ 验证这些会话状态机时执行：

```bash
MESSAGE_HANDLER_TYPE=rabbitmq make e2e-ai-blueking
```

`wxbot` 模块在本机启动一个只模拟企微远端协议的 WebSocket 服务，被测侧仍使用官方企微 SDK、Django、SQLite、Redis 和 RabbitMQ。它验证渠道配置读取、长连接认证、心跳、首包响应、RabbitMQ 轮询转发，以及 `/help`、`/new`、生成中的 `/stop`。执行方式：

```bash
make e2e-wxbot
```

HTML 报告会把每条企微输入、流式响应帧和完整 WebSocket 请求/回复放在同一个 `scenario_id` 下。由此可以从“功能健康概览”直接确认长连接、轮询和三个指令是否正常，再展开查看对应的协议帧和智能体调用链。

默认 `headless=true`，适合流水线。交互检查可执行 `make e2e headless=false`，然后使用内置浏览器打开 `E2E_APP_URL` 和本次报告。每一次 runner 执行（包括配置或基础设施失败）都会生成：

- `dev/e2e/reports/<timestamp>/report.html`
- `dev/e2e/reports/<timestamp>/result.json`
- `dev/e2e/reports/latest.html`

报告按“先判断功能是否正常，再查看诊断证据”的顺序组织：

- 功能健康概览：默认按 API/登录、AI 小鲸与对话、可观测性纵向分区，每个组件内使用自适应场景卡片列出本次实际执行通过或失败的功能及覆盖说明；执行 `e2e-wxbot` 时会增加企业微信分区，未执行的数据库与消息、企微不会显示为已验证。
- 场景证据关联：每个场景使用稳定的 `scenario_id` 关联断言、会话和 API 调用；健康项展示证据数量，点击“查看证据”直接定位到对应证据区。
- 完整诊断证据：场景证据区展示断言输出和发送给智能体的会话内容；接口按 `chain_id` 把测试端请求与其触发的“智能体 → 远端 mock”调用合并为一条请求链，再逐层展开查看每次调用的方法、URL、请求 Headers/Body、响应状态、响应 Headers/Body 和耗时。业务场景开始前没有父请求的公共启动调用单独归档，不作为某个功能正常的证据。

报告落盘前会递归遮蔽 access token、Authorization、cookie、密码、签名和 API key 等敏感字段；除敏感字段外不截断请求或响应内容。

这些运行产物和 `.env` 都已忽略，不会提交。若只需扩展测试框架并做快速回归，执行 `make -C dev/e2e test`。

Grafana 仪表盘地址为 <http://127.0.0.1:3000/d/aidev-agent-metrics>，Prometheus 为 <http://127.0.0.1:9090>。指标模块会检查 Prometheus 可查询，以及 Grafana 中预置的智能体仪表盘可读取。
