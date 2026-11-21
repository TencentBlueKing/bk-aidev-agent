# aidev-agent-adapter

独立安装的协作智能体适配插件。首版直接读取 AIDev 平台指定智能体版本的配置，将 Prompt、MCP 和 Skill 写入 OpenClaw / Hermes 专用配置目录，并通过官方 ACP 客户端输出可续传的 AG-UI 事件。

本模块不依赖 Django，不启动 Agent Channel Service，不定义其 WSS 消息契约。后续 Worker 可组合 `PlatformClient`、`ConfigSynchronizer`、`Adapter.submit()` 和 `Adapter.events()`。

## 安装与本地验证

在本插件目录执行：

```sh
make init
make test
make lint
make build
```

要求 Python 3.11+。运行环境另外安装 `openclaw` 或 `hermes`；依赖锁文件锁定 ACP / AG-UI 客户端版本。构建后的 wheel 可独立安装。

## 启动配置

配置文件由部署端写入实例私有目录，不提交实际配置或凭据。最小结构如下：

```json
{
  "endpoint": "https://aidev.example.com",
  "agent_code": "example-agent",
  "agent_app_code": "example-agent-app",
  "tenant_id": "example-tenant",
  "version": "1.0.0",
  "engine": "openclaw",
  "root": "/var/lib/aidev-adapter/example-instance",
  "include_prompt": true,
  "mcp_names": ["docs"],
  "skill_ids": [1],
  "skill_versions": {"1": "2.0"},
  "download_origins": ["https://artifacts.example.com"],
  "mcp_auth_origins": ["https://mcp.example.com"],
  "poll_seconds": 60,
  "prompt_timeout": 300
}
```

- 部署端注入 `AIDEV_ACCESS_TOKEN`；平台要求应用认证时额外注入 `AIDEV_APP_SECRET`。不使用命令行参数传递凭据。
- `endpoint` 是 AIDev OpenAPI 前缀之前的部署地址（可含网关路由前缀），客户端追加 `/openapi/aidev/resource/v1/`。
- `agent_app_code` 用于当前平台配置接口路径及 `bk_app_code`；`agent_code` 是实例注册关联标识，二者不隐式互换。
- `version` 必填，指定 Agent 配置版本，不自动追随最新 Agent 发布版本。`watch` 轮询同一指定版本；切换发布版本由部署端更新配置并创建新运行实例。
- `skill_versions` 可按 Skill ID 显式锁定版本；未设置时使用平台当次返回的 Skill 展示版本（可能是最新版本），不能据此宣称冻结了 Agent 历史绑定版本。详情响应与锁定版本不符则失败，不回退到最新版本。
- 省略 `mcp_names` / `skill_ids` 同步该智能体绑定的全部资源；空数组表示不启用该类资源。指定未绑定资源时失败。
- `engine` 支持 `openclaw`、`hermes`；`command` 可覆盖默认的 `openclaw acp` / `hermes acp` 参数列表，不经过 shell。
- `native_config` 提供部署端的引擎基础配置（例如模型设置），同步器覆盖所管理的 workspace / MCP 字段。`engine_env` 仅供显式的引擎启动环境；平台鉴权变量不会自动传入子进程。
- 不同平台地址、租户、智能体、用户 token 和引擎必须使用不同的 `root`。首版用身份摘要绑定目录；本次身份范围增加平台地址，旧格式目录会拒绝复用，需新建实例目录，不能直接删除旧日志绕过检查；token 轮换需新建实例目录，不自动继承旧会话。目录必须为当前用户所有，不能经过符号链接。

## 使用

```sh
# 先从平台拉取配置；输出 revision、快照目录及引擎环境变量，不输出配置内容
uv run aidev-agent-adapter --config /path/to/private/config.json sync

# 定期更新配置；失败保留上次完整快照
uv run aidev-agent-adapter --config /path/to/private/config.json watch

# 从标准输入读取一次 Chat，输出逐行 JSON 事件信封
printf '你好' | uv run aidev-agent-adapter --config /path/to/private/config.json chat --thread-id thread-1 --run-id run-1

# 离线补发指定序号之后的事件；不请求平台、不启动引擎
uv run aidev-agent-adapter --config /path/to/private/config.json replay --run-id run-1 --after 3
```

`chat` 是单次验证入口，退出时关闭 ACP 子进程。常驻 Worker 应保留同一个 `Adapter` 对象处理多轮请求，并在退出时调用 `close()`。运行中的 Worker 用 `events(run_id, after)` 续传；CLI `replay` 使用独占日志锁，不能同时读取仍在运行的实例。

## 平台配置与落盘契约

| 来源 / 资源 | 处理方式 |
| --- | --- |
| `GET agent/{agent_app_code}/?version=...` | 校验返回身份和 `allowed_access=true`，使用当前平台的 Prompt / MCP / Skill 绑定结构 |
| `prompt_setting.content` | 接受 system / developer 角色的文本列表，按顺序合并；不把 user / assistant 历史消息静默提升为系统指令 |
| `mcp_server_config.mcpServers` | 保留选定服务器和 `selected_tools`；精确工具名映射为引擎白名单，拒绝会扩大范围的通配符 |
| `GET agents/skill/{id}/?version=...&agent_version=...` | 对比返回 Skill id / version。当前平台可能返回最新版本而非历史绑定版本；提供 `skill_versions` 才能明确要求固定版本，响应不一致均停止同步 |
| Skill ZIP 下载 | 仅访问 HTTPS 允许域，不携带平台认证，不跟随重定向；校验 MD5、下载及解压大小、路径和文件类型 |
| OpenClaw | `workspace/SOUL.md`、`workspace/skills/<code>/`、`openclaw.json` 的 `mcp.servers` 和默认 workspace |
| Hermes | `SOUL.md`、`skills/<code>/`、`config.yaml` 的 `mcp_servers`；以 `HERMES_HOME` 选择专用目录 |

每次同步先完整下载、校验、构建版本目录，再原子切换 `current`。新版本不会携带已经移除的 Skill / MCP；旧版本保留供正在运行的实例使用。已生成的受管文件被修改、增加、删除、替换为链接或改变权限时拒绝复用；引擎自行写入的 MEMORY 等非受管数据可保留。Skill 脚本仅保留所有者执行权限。快照及事件数据是私有文件，包含资源配置或对话内容，不能提交到 Git；部署端负责加密存储、磁盘配额和按实例生命周期清理。

MCP 首版只支持 HTTPS SSE / Streamable HTTP，不执行平台下发的本地命令。蓝鲸认证仅向 `mcp_auth_origins` 或平台同源地址注入用户 access token；不复制应用密钥。工具白名单是引擎配置约束，服务端仍须独立校验用户授权。

Skill 首版同步包文件，不安装包内依赖、不执行安装脚本，也不配置平台 Skill 的独立执行沙箱。依赖和运行环境由镜像提供；需要额外环境变量的 Skill 须经部署配置明确注入。

## 配置生效与引擎前提

配置同步与 ACP Chat 是两条独立路径。`sync` / `watch` 发布配置，**不表示运行中的引擎已加载新配置**。`Adapter` 固定使用创建时的快照；切换版本须在空闲边界关闭旧 Adapter、按新快照启动引擎和 Adapter。首版不在进行中的对话里热切换配置。

OpenClaw 的 `openclaw acp` 是连接现有 Gateway 的桥接进程，并不启动 Gateway。部署方必须使用 `sync` 输出的 `OPENCLAW_CONFIG_PATH` 启动对应的专用 Gateway，并为 ACP bridge 配置相同的连接地址 / 鉴权。向 bridge 传递配置文件不能证明远端 Gateway 已使用该文件。Hermes 使用 `HERMES_HOME` 启动 `hermes acp`。两者的模型配置由部署方提供。

参考：[OpenClaw ACP](https://docs.openclaw.ai/cli/acp)、[OpenClaw MCP](https://docs.openclaw.ai/tools/mcp)、[Hermes MCP](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)、[ACP Python SDK](https://agentclientprotocol.github.io/python-sdk/quickstart/)。原生配置格式按这些公开契约实现，真实部署应固定引擎版本并联调验收。

## ACP → AG-UI 与重连

输出是适配器内部的事件信封，`event` 字段才是标准 AG-UI 事件；下游应解包后按 AG-UI 对外输出。这不是 Channel WSS 或 AG-UI HTTP/SSE 的完整实现。

```json
{
  "threadId": "thread-1",
  "runId": "run-1",
  "sequence": 1,
  "eventId": "run-1:1",
  "event": {"type": "RUN_STARTED", "threadId": "thread-1", "runId": "run-1"}
}
```

- 每个实例最多接受 `max_pending_runs` 个未完成请求（默认 32），过载拒绝新请求，已接收 run 的重连续传仍可进行。
- 同一实例串行调用引擎，运行期间按 thread 复用 ACP session；事件关联 run / thread / message / tool id。
- 文本生成 START / CONTENT / END，在工具调用和 messageId 切换处结束文本段；工具后的无 messageId 文本开启新消息。工具 rawInput 按完整快照更新，在终态输出一次 ARGS，再输出 END / RESULT。计划、思考和非文本消息以 CUSTOM 保留。
- 正常 prompt 响应产生一次 RUN_FINISHED，保留 stopReason（包括 cancelled）；断连、超时、主动中止等产生 RUN_ERROR，执行结果标记未知，不把工具执行结果假定为失败或成功。
- 相同 run_id + thread_id + 输入 + 配置版本只执行一次；冲突复用拒绝。事件先持久化再交给消费者，按 sequence 补发，拒绝超出已持久化范围或非整数的游标。下游按 eventId 去重，不按文本内容去重。
- 下游消费者断开不取消 Chat；ACP 断开后隔离连接，不自动重放输入。进程重启后在同一事务中补齐未结束的文本 / 工具事件，再把未完成请求标记未知，可重放旧事件，但不自动恢复 ACP 会话上下文；继续已发送过 prompt 的旧 thread 会显式报错，需新建 thread；只在排队中被取消、未发送过 prompt 的 thread 可以继续。
- ACP 没有统一的源事件 replay id。此处保证的是适配器日志续传及同一日志内的请求去重，**不承诺外部工具副作用 exactly-once**。同一 ACP session 内的通知关联遵循协议的 prompt 生命周期，无法识别引擎违反协议而发出的跨轮迟到通知。
- 权限请求默认拒绝；不声明客户端文件 / 终端能力。后续 Channel 用户确认流程需要独立接入。

## 验证范围

测试用模拟 AIDev HTTP 接口和真实 stdio JSON-RPC 测试进程，覆盖配置同步、资源移除、失败回退、鉴权隔离、工具过滤、归档攻击、事件转换、断线续传、请求去重、取消和重启恢复。

未使用真实平台凭据，未运行 OpenClaw / Hermes 模型调用，也未验证 PaaS 实例与 Channel WSS 链路。部署验收须补充：真实网关路由与用户授权、固定引擎版本的配置加载、带依赖的 Skill、MCP 工具权限及外部副作用。
