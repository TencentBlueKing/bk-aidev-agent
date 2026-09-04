# Craw 隔离运行时：共用插件模板与发布约定

> 只描述公开模板与平台约定。不要把环境域名、真实空间 / 知识库 ID 或凭据写进仓库。

普通智能体与协作智能体共用 `template/builtin/`。模板在 URL 初始化阶段调用
`enable_chat_takeover()`；未设置 `BKAI_CRAW_BACKEND` 时立即返回，保持原生 ReAct，
因此普通智能体行为不变。

## 共用模板

```bash
python -m cookiecutter /path/to/bk-aidev-agent --directory template/builtin --no-input
```

插件代码、应用态 `AgentResourceManager`、聊天窗、pre-release 和 API 网关定义均来自同一模板。
协作智能体不维护第二份 Python 插件模板，也不把平台配置或凭据复制进源码。

## Craw 部署外壳

Craw 仍需要 OpenClaw/Hermes 内核，因此部署侧在共用插件代码外增加最小 Docker 外壳：

- 固定 digest 的内核基础镜像；
- 一个同时管理 craw 内核与 gunicorn 的 supervisor；
- `BKAI_CRAW_BACKEND=openclaw` 等 loopback 配置；
- 用户 token → MCP 的本机 egress。

这是构建形态差异，不是第二套业务模板。可直接部署的公共运行时位于 `runtime/craw/`，与
SDK 和 `template/builtin/` 同仓交付。PaaS 从该仓库的内部镜像克隆此目录；基础镜像由
`create_ai_agent_app` 通过 `docker_build_args.CRAW_BASE_IMAGE` 注入，公开源码不保存内部地址。
普通智能体继续使用源码包 + buildpack。

## 配置与身份

1. PaaS 自动注入当前隔离应用的 `BKPAAS_APP_ID` / `BKPAAS_APP_SECRET`。
2. 运行时沿用 `template/builtin` 的 `AgentResourceManager`，以应用态身份从对应环境的 AIDEV
   Gateway/Stage 拉取同名 Agent 配置。
3. 不要求 `BKAI_AIDEV_API_KEY`，也不通过 PaaS 环境变量复制 Agent 配置快照。
4. OpenClaw 模型请求经过 loopback egress，由 egress 注入当前 PaaS 应用身份；应用密钥不写入
   OpenClaw 配置。
5. 登录用户 token 只在对话租约期间进入 MCP egress；无租约请求返回 401，token 不落盘。

Gateway 名称和 Stage 与普通模板一样由发布环境提供，不应根据隔离应用 code 自行推导，也不应
硬编码正式环境地址。

## 运行约束

- 内核和两个 egress 只监听 `127.0.0.1`；对外仅暴露插件 HTTP 服务。
- 当前单副本使用 `MESSAGE_HANDLER_TYPE=inmemory`；需要多副本时再接 RabbitMQ。
- 未绑定数据库增强服务时，单副本可使用本机 SQLite；需要持久会话或多副本时再切共享数据库。
- OpenClaw HTTP 转发需要启用 `/v1/chat/completions`。
- 配置在启动期装配，平台配置变更后通过重新部署生效。
