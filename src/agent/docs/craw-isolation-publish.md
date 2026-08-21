# Craw 隔离运行时：从模板到发布

> 这份说明只描述公开模板与平台约定。不要把环境域名、内网控制台、真实空间 / 知识库 ID、凭据写进仓库。

默认 `agent_runtime=chat` 仍是原来的 buildpack 插件。任务（协作）智能体选 `agent_runtime=craw`，把 CHAT 执行交给同容器 craw 内核。

## 模板怎么用

生成时显式传入运行时，不要把真实镜像仓库写进 cookiecutter 默认值：

```bash
python -m cookiecutter /path/to/bk-aidev-agent/template --no-input \
  agent_runtime=craw \
  craw_base_image=craw-runtime:local
```

`craw-runtime:local` 只是占位。构建时用 `--build-arg CRAW_BASE_IMAGE=...` 或生成时改 `craw_base_image`，指向你们自己的内核镜像。基镜像需要提供：craw 网关入口（默认 `/usr/local/bin/docker-entrypoint.sh`）、`tini`、Python 3.11。

未设 `BKAI_CRAW_BACKEND` 时，`bk_plugin/patch/urls.py` 里的 `enable_chat_takeover()` 零影响。craw 运行时模板会把它设成 `openclaw`。

## 平台创建 / 发布 / 部署

1. 在 AIDEV 上创建智能体配置（Prompt / 模型 / Skill / MCP / 知识库）。
2. 发布应用时选用本模板且 `agent_runtime=craw`，**不要**走普通对话插件的 buildpack 路径。
3. 应用创建应走隔离应用接口（Dockerfile 构建），而不是常规 BkApp。
4. 把生成应用的 `app_code` / `saas_url` / 插件网关地址写回该智能体记录，主站对话才能调度到这套运行时。
5. 在应用控制台填写凭据：`BKAI_AIDEV_API_KEY`、`OPENCLAW_GATEWAY_TOKEN` 或 `BKAI_CRAW_API_KEY`。不要写进 Git。

内核只监听 `127.0.0.1`。对外只暴露插件的 HTTP 入口（`/chat-window/`、`/bk_plugin/plugin_api/chat_completion/`）。

## 和官方 chat 模板的差别

| 项 | `chat`（默认） | `craw` |
|---|---|---|
| 构建 | buildpack | Dockerfile overlay |
| Web 进程 | gunicorn | tini + craw-supervisor + gunicorn |
| CHAT 执行 | 原生 ReAct | `CrawCompletionAgent` → localhost 内核 |
| 消息后端 | rabbitmq | inmemory（单副本；多副本前再换共享队列） |

## 已知边界

- craw 当前对话转发走 OpenAI 兼容 HTTP，正文 AG-UI 可用。内核内部工具活动需要 WebSocket 才能映射成 `TOOL_CALL_*` 卡片，那是后续增量，不在本模板第一版。
- `CrawSyncer` 可挂 celery beat，把平台 Agent 定义同步到 craw home。home 路径用环境变量，不要写死部署主机路径。
- 配置变更若在启动期物化，改平台配置后需要重新部署才会生效。
