# Craw 隔离运行时：从模板到发布

> 只描述公开模板与平台约定。不要把环境域名、内网控制台、真实空间 / 知识库 ID、凭据写进仓库。

对话插件走 `template/builtin/`。协作智能体走独立 cookiecutter：`template/craw/`。

## 模板怎么用

```bash
python -m cookiecutter /path/to/bk-aidev-agent --directory template/craw --no-input \
  craw_base_image=craw-runtime:local \
  aidev_agent_version=2.2.2rc17
```

`craw-runtime:local` 只是占位。平台生成时必须注入固定 digest 的 `craw_base_image` 和已发布的 `aidev_agent_version`，不要等到 PaaS 构建阶段再补 build arg。基镜像需要提供：craw 网关入口（默认 `/usr/local/bin/docker-entrypoint.sh`）、`tini`、Python 3.11，以及可用的 Python 包索引策略。

Dockerfile 会在基镜像之上创建 `/app/.venv`，按生成后的 `requirements.txt` 安装 `aidev-agent`、`aidev-bkplugin` 和 gunicorn，再复制插件源码；不要假设纯 OpenClaw 基镜像已经包含 Proxy 依赖。`requirements.txt` 是镜像构建锁，模板不携带可能与动态 SDK 版本冲突的 `uv.lock`；生成项目做本地开发时可运行 `uv lock` 生成自己的锁文件。

`bk_plugin` 与 `template/builtin` 相同。只在 `bk_plugin/patch/urls.py` 挂了 `enable_chat_takeover()`。不要改 `extend/agent.py`。本模板会把 `BKAI_CRAW_BACKEND` 设成 `openclaw`。

## 平台创建 / 发布 / 部署

1. 在 AIDEV 上创建智能体配置（Prompt / 模型 / Skill / MCP / 知识库）。
2. 发布应用时选用 `template/craw`，**不要**走 `template/builtin` 的 buildpack 路径。
3. 应用创建应走隔离应用接口（Dockerfile 构建），而不是常规 BkApp。
4. 把生成应用的 `app_code` / 插件入口写回该智能体记录。
5. 在应用控制台填写凭据：`BKAI_AIDEV_API_KEY`、`OPENCLAW_GATEWAY_TOKEN` 或 `BKAI_CRAW_API_KEY`。不要写进 Git。

内核只监听 `127.0.0.1`。对外只暴露插件 HTTP 入口（`/chat-window/`、`/bk_plugin/plugin_api/chat_completion/`）。

## 和官方 `template/builtin` 的差别

| 项 | `template/builtin` | `template/craw` |
|---|---|---|
| 构建 | buildpack | Dockerfile overlay |
| Web 进程 | gunicorn + celery | tini + craw-supervisor + gunicorn |
| CHAT 执行 | 原生 ReAct | `CrawCompletionAgent` → localhost 内核 |
| 消息后端 | rabbitmq | inmemory（单副本） |

## 已知边界

- craw 当前对话转发走 OpenAI 兼容 HTTP，正文 AG-UI 可用。内核内部工具活动需要 WebSocket 才能映射成 `TOOL_CALL_*` 卡片，那是后续增量。
- 配置变更若在启动期物化，改平台配置后需要重新部署才会生效。
