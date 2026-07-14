# craw 本地模拟（colima）

用两个容器模拟 AIDEV agent 对接 craw（OpenClaw 内核 API 服务）的两条链路：

1. **agent --localhost--> craw**：agent 容器以 `network_mode: service:openclaw` 共享网络栈，经 `127.0.0.1:18789` 调 `/v1/chat/completions`（等价 K8s 同 Pod 的 localhost 语义）；
2. **agent --read/write--> craw（周期任务）**：共享卷（openclaw 侧挂 `/workspace`），`CrawSyncer` 周期 health 读 + `SOUL.md` 写 + 读回校验。

## 前提

- colima（或任意 docker daemon）运行中；
- 本地有 craw 侧镜像（`bkai-openclaw-agent`）与 agent 侧镜像（`AGENT_IMAGE`，内含 SDK 运行依赖 `/app/.venv`，如你的业务插件镜像）；
- 凭据文件：`cp agent.env.example agent.env` 按注释填写（`agent.env` 已 gitignore，不入库；可用 `ENV_FILE` 指到别处）。

## 运行（三个变体）

```bash
./run.sh          # openclaw 变体：SDK 直连（up → 场景1 → 场景2 → 核验 SOUL.md → ALL PASS）
./run-hermes.sh   # hermes 变体：hermes gateway api_server（场景脚本共用）
./run-plugin.sh   # 插件集成变体：业务插件(Django) 经 SDK craw 接管 CHAT → OpenClaw
                  #   验证 /bk_plugin/plugin_api/chat_completion/ 非流式 + AG-UI 流式
```

hermes 变体要点：entrypoint `BKAI_HERMES_MODE=ci` 分支 `exec "$@"` 直跑
`hermes gateway`，api_server 平台经 `API_SERVER_ENABLED/KEY/PORT/HOST` env 启用
（loopback 即可——共享网络栈可达）。

插件变体要点：不重建镜像，dev SDK 挂到 venv site-packages 覆盖已装
`aidev_agent`（plugin entrypoint 硬 export PYTHONPATH=/app，PYTHONPATH 注入不可行），
插件代码经 `PLUGIN_SRC` 挂 `/app/bk_plugin`（含 craw registry 覆盖薄壳，
薄壳写法见 docs/craw-adapter.md「接入方式」）。

期望输出（节选）：

```
[2/3] non-stream content: 'pong'
[3/3] stream events: ['RUN_STARTED', 'TEXT_MESSAGE_START', ..., 'RUN_FINISHED']
SCENARIO-1 PASS
cycle 1/2: ok=True ... verified=True
SCENARIO-2 PASS
ALL PASS
```

## 说明

- agent 容器把 `bk-aidev-agent/src/agent` 挂到 `/sdk-src` 并以 `PYTHONPATH` 优先加载——跑的是**开发中的 SDK 源码**，改代码无需重建镜像；
- 场景脚本：`scenario_chat.py`（健康探测 + 非流式 + 流式 AG-UI 事件）、`scenario_sync.py`（`CrawSyncer.run_forever` 两周期）；
- `MESSAGE_HANDLER_TYPE=inmemory` 避免依赖 RabbitMQ；
- 换 Hermes 后端：镜像换 `bkai-hermes-agent`，`BKAI_CRAW_BACKEND=hermes` + `BKAI_CRAW_API_URL` 指向其 api_server 端口。

## 亲手验证（逐层手动）

环境起来后（`docker compose --env-file <凭据文件> up -d --wait`），四条路自己敲：

```bash
ENVF=./agent.env   # 按需替换

# ① 裸 API：宿主机直连 craw（openclaw 变体已映射 18789；浏览器开 http://127.0.0.1:18789 是 dashboard，令牌=OPENCLAW_GATEWAY_TOKEN）
curl -fsS http://127.0.0.1:18789/healthz
curl -sS http://127.0.0.1:18789/v1/chat/completions \
  -H "Authorization: Bearer craw-local-sim" -H "Content-Type: application/json" \
  -d '{"model":"openclaw","messages":[{"role":"user","content":"你是谁"}],"stream":false}'

# ② SDK 对话：交互式多轮 REPL（流式吐字；单发在末尾直接带问题）
docker compose --env-file $ENVF exec agent \
  /app/.venv/bin/python /sdk-src/examples/craw_local_sim/chat.py

# ③ 周期读写：窗口 A 盯 craw 侧文件，窗口 B 跑 sync，看 synced_at 每周期刷新
docker compose --env-file $ENVF exec openclaw sh -c \
  'while true; do date; head -3 /workspace/SOUL.md 2>/dev/null; echo ---; sleep 2; done'
docker compose --env-file $ENVF exec -T agent \
  /app/.venv/bin/python /sdk-src/examples/craw_local_sim/scenario_sync.py

# ④ 整链（插件变体 ./run-plugin.sh 起来后）：
curl -sS http://127.0.0.1:8000/bk_plugin/plugin_api/chat_completion/ \
  -H "X-BKAIDEV-USER: demo-user" -H "Content-Type: application/json" \
  -d '{"input":"你是谁","execute_kwargs":{"stream":true}}'
```

旁路观察：`docker compose --env-file $ENVF logs -f openclaw`（craw 侧请求进出）。
注意各变体共用 compose 项目名，请一次只跑一个变体。

## MCP 用户 Token 隔离实测

```bash
./run-hermes.sh                        # 先起 hermes 变体（agent.env 需提供 BKAI_CLI_SRC=bkai-cli 仓路径 + 双 token）
POOL_AGENT=<agent-code> ./run-isolation.sh   # 池模式反代 + REAL/FAKE 双身份 → ISOLATION PASS
```

前提：凭据文件含 `REAL_MCP_ACCESS_TOKEN`（有效 AIDEV 用户 token）与
`FAKE_MCP_ACCESS_TOKEN`（任意假串）。脚本验证四件事：

1. 双身份 chat 都通（对话不因身份 token 无效而挂，隔离只作用于 MCP）；
2. `mcp-probe`：REAL → `accessible`（蓝鲸网关 200）、FAKE → `rejected`（4xx）；
3. 两身份 identityId（`sha256(token)[:16]`）不同 → 各自独立内核
   `~/.bkai/hermes-pool/<identityId>/`，且与 SDK `CrawIdentity.identity_id` 一致；
4. token 不落盘：每身份 config.yaml 的 mcp_servers 已重写到 loopback egress
   （`/egress/<identityId>/<slug>/`），headers 只有 `X-Bkai-Egress-Key`，
   用户 token 仅存 egress 内存、传输层注入。

判定面基线（可单独手测）：对 config.yaml 里任一 mcp server URL 直接发 MCP
initialize，`x-bkapi-authorization: {"access_token": <token>}` —— REAL 200 / FAKE 400。

对话自证（问两个身份同一句「列出你的 MCP 并实际调用一个验证」）：

```bash
# 换 X-Bkai-Access-Token 分别用 $REAL_MCP_ACCESS_TOKEN / $FAKE_MCP_ACCESS_TOKEN：
curl -s --max-time 280 -X POST http://127.0.0.1:8788/v1/chat/completions \
  -H "Authorization: Bearer pool-entry-token" -H "X-Bkai-Access-Token: <token>" \
  -H "Content-Type: application/json" \
  -d '{"model":"hermes-agent","messages":[{"role":"user","content":"列出你当前可调用的 MCP 服务器和工具，并实际调用一个最轻量的只读工具，如实汇报结果"}],"stream":false}'
```

实测：REAL 身份列出其可用的 MCP 工具并实调成功；FAKE 身份如实回答
「没有已接入的 MCP 服务器」。模型自报需与传输层核对——`grep '\[egress\]' /tmp/pool.log`
可见 REAL 身份全部通过网关鉴权、FAKE 身份全 400，两者吻合。

## 清理

```bash
docker compose --env-file <凭据文件> down -v
```
