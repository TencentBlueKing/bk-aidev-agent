---
status: active
updated: 2026-07-14
type: guide
---

# Craw 适配层（packages/craw）

> Craw = CLI 形态 Agent 内核（OpenClaw / Hermes / …）以本机 API 服务（localhost / 同容器 / 同 Pod）运行的统一称谓。本包把「AIDEV Agent 对接这类内核」所需的 Proxy 与配置同步组件沉淀进 SDK。
>
> ⚠️ 术语澄清：这里的「周期任务（cron）」指内核**原生的定时调度能力**（OpenClaw `cron.*` / Hermes 定时任务，如「每工作日 9 点汇总告警」），由内核到点执行——**不是**本包 `CrawSyncer` 做的「定期写 SOUL.md」。`CrawSyncer` 是配置/人设同步的运维工具，与 cron 周期任务是两回事。

## 定位

AIDEV 插件（bk_plugin / Django 应用）此前对接 OpenClaw、Hermes 时各写了一套转发 Agent 与 registry 覆盖。本包将其泛化为 SDK 组件：

- 连接差异（URL / 认证 / 会话头）下沉到**后端**（`OpenClawBackend` / `HermesBackend`），新增内核只写差异点；
- 转发 Agent、SSE→AG-UI 翻译、registry 接管、配置同步全部复用。

## 组件与两条链路

```
AIDEV 平台/插件                     SDK packages/craw                 craw（本机 API 服务）
┌──────────────┐   ①对话转发   ┌─────────────────────┐    HTTP     ┌──────────────────┐
│ agent_registry│──CHAT 接管──▶│ CrawCompletionAgent │──localhost─▶│ OpenClaw :18789  │
│ (enable_chat_ │              │  └─ CrawBackend     │             │ Hermes  :8642    │
│  takeover)    │              ├─────────────────────┤             │ /v1/chat/        │
│ celery beat 等│──②配置同步──▶│ CrawSyncer          │──read/write▶│  completions     │
└──────────────┘              │  read: health/状态   │  共享卷/HTTP │ SOUL.md +        │
                              │  write: Prompt/MCP/  │             │ agent-config.json│
                              │        Skills 产物   │             └──────────────────┘
                              └─────────────────────┘
   周期任务(cron) = 内核原生定时调度（OpenClaw cron.* / Hermes 定时任务），非本包 CrawSyncer
```

1. **对话转发（Proxy）**：`CrawCompletionAgent` 实现 SDK `AgentProtocol`（`build`/`execute`/`stop`），把 CHAT 执行转发给 craw 的 OpenAI 兼容 `/v1/chat/completions`；流式 SSE 逐 chunk 翻译成 AG-UI 事件（`RUN_STARTED → TEXT_MESSAGE_* → RUN_FINISHED`），经 `event_handler` 自动落库；非流式返回与原生 `ChatCompletionAgent` 同构。
2. **配置同步（CrawSyncer，可选运维工具）**：`CrawSyncer.run_cycle()` = read（`backend.health()` + 可选状态文件）+ write（把平台 Agent 定义下发到 craw home：全部产物先写 staging（默认 0600；跨 UID 共享卷经 `BKAI_CRAW_ARTIFACT_MODE` 放宽，如 0644）并读回校验，再逐个原子切换——任一产物失败时正式文件零改动，不会出现新旧混合版本；写入全程 openat + O_NOFOLLOW，共享卷上的 symlink 替换无法把写入引出 home）。同步粒度由 provider 决定：`soul_provider()` 只下发人设 `SOUL.md`（最小形态）；`artifacts_provider()` 下发一组产物 `{相对路径: 内容}`，配合 `agent_config_to_artifacts(config)` 可把平台 `AgentConfig` 渲染成 `SOUL.md`（Prompt）+ `agent-config.json`（聚合 MCP / Skills / tools）整组下发。宿主把 `run_cycle` 挂 celery beat 即可；本地模拟用 `run_forever(max_cycles=N)`。**这是配置/人设同步，不是周期任务（cron）**——后者是内核原生能力（OpenClaw `cron.*` / Hermes 定时任务），由用户对话下单或经内核 cron 接口排期，内核到点执行并投递结果。内核如何**消费**这些产物（`agent apply` 应用成运行时人设与工具）是部署侧机制，不在本层职责内；平台 `AgentConfig` 不含内核运行期 Memory，故同步 Prompt / MCP / Skills 三类。

## 用户 Token 隔离

- `CrawIdentity` 携带 `username` + `access_token`；请求时经 `X-Bkai-Access-Token` 头透传给 craw 侧——与 bkai-cli 池模式反代（`bkai hermes proxy expose --pool`）的身份路由契约一致，由前置反代按身份做每用户内核 / MCP 凭证隔离。
- 本层日志只落 `identity_id`（`sha256(token)[:16]`），原始 token 不入日志、不落盘。
- Hermes 后端额外携带 `X-Hermes-Session-Id`（会话粘滞）与 `X-Hermes-Session-Key`（记忆按用户隔离；上游要求启用 Bearer 才接受，未配 api_key 时自动不发）。
- 隔离链已实测（`examples/craw_local_sim/run-isolation.sh`）：SDK `CrawIdentity.identity_id` 与池路由 identityId 同 hash 契约；REAL/FAKE 双身份经池分流到独立内核，MCP 探测分别 accessible / rejected，用户 token 不落盘（每身份 config.yaml 只含 `X-Bkai-Egress-Key`）。对话行为面同步验证：同题问两身份，REAL 列出全部 MCP 工具并实调成功、FAKE 如实报无可用 MCP，与 egress 传输层流水吻合（方法见 sim README「对话自证」）。

## 接入方式

推荐挂点：宿主 **ROOT_URLCONF 尾部**（bk_plugin 形态即 `bk_plugin/patch/urls.py` 末尾）——
settings 已就绪、应用已加载，早于首个请求的 registry 查找；避免在 settings 导入期
挂载（craw 包的传递依赖可能触发 Django 配置未就绪的循环导入）。已在真实二开插件
页面级验证的完整薄壳：

```python
# —— craw 内核接管（opt-in）：env BKAI_CRAW_BACKEND 未设时零影响，保持原生 ReAct
try:
    from aidev_agent.packages.craw import enable_chat_takeover
except ImportError:  # SDK 版本尚无 craw 包，保持原生
    pass
else:
    enable_chat_takeover()
```

Django `AppConfig.ready` 亦可作为挂点（同样晚于 settings 就绪）。

## 环境变量矩阵

| 变量 | 作用 | 默认 |
|---|---|---|
| `BKAI_CRAW_BACKEND` | 接管门控 + 后端选择（`openclaw` / `hermes`） | 未设 = 不接管（原生 ReAct） |
| `BKAI_CRAW_API_URL` | craw API 地址 | openclaw `http://127.0.0.1:18789` / hermes `http://127.0.0.1:8642` |
| `BKAI_CRAW_API_KEY` | Bearer 令牌（gateway token / API_SERVER_KEY） | 空 |
| `BKAI_CRAW_MODEL` | model 字段（openclaw 语义为**选 agent** 非 LLM） | `openclaw` / `hermes-agent` |
| `BKAI_CRAW_TIMEOUT` | HTTP 超时秒 | 300 |
| `BKAI_CRAW_HOME` | 周期任务文件面根目录（共享卷路径） | 未设 = 跳过文件写 |
| `BKAI_CRAW_SYNC_INTERVAL` | `run_forever` 周期秒 | 60 |

Legacy env（既有插件迁移兼容，统一 env 优先）：`BKAI_OPENCLAW_GATEWAY_URL` / `OPENCLAW_GATEWAY_TOKEN` / `BKAI_OPENCLAW_MODEL`；`BKAI_HERMES_API_URL` / `BKAI_HERMES_API_KEY` / `BKAI_HERMES_MODEL` / `BKAI_HERMES_TIMEOUT`。

## 本地验证

`examples/craw_local_sim/`（见其 [README](../examples/craw_local_sim/README.md)）用 colima 模拟三个变体，均两轮稳定通过：

- `./run.sh`：openclaw 后端 SDK 直连（两条链路）；
- `./run-hermes.sh`：hermes 后端（gateway api_server，`API_SERVER_*` env 启用，loopback + 共享网络栈）；
- `./run-plugin.sh`：真实消费方集成——业务插件（Django）经 extend 层薄壳触发 `enable_chat_takeover()`，整链 `/bk_plugin/plugin_api/chat_completion/` 非流式 + AG-UI 流式实测。

单元测试：`make test path=tests/packages/craw`。

## 扩展新内核

1. 继承 `BaseCrawBackend`，给出 `name` / `default_model` / `default_api_url` / `health_path` 与 legacy env 名，差异头覆写 `extra_headers()`；
2. `craw_backend_registry.register(MyBackend.name, MyBackend)`（参照 `packages/craw/__init__.py`）；
3. `BKAI_CRAW_BACKEND=<name>` 即生效；tests 参照 `tests/packages/craw/`。

## 已知边界

- craw 内核自身就是完整 agent（会话循环 / 工具编排在 craw 侧），因此接管发生在 `agent_registry` 层而非 executor 层——不能再被 LangGraph ReAct 套一层。
- MCP 凭证的传输层注入（egress 网关）由 bkai-cli 侧反代实现，本包只负责身份透传；不要在本包内实现凭证落盘。
- 文件面读写要求 agent 与 craw 可见同一目录（同容器 / 共享卷 / 同 Pod emptyDir）；纯 HTTP 面无此要求。
