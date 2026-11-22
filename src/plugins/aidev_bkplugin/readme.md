# AI 小鲸后台服务

本插件需与智能体模板配合使用，用于开发和管理智能体插件。

审批 Web 回调与企业微信跨进程联动见 [DatabaseEventBus 使用说明](docs/database-events.md)。

## Chat 流式响应的 Celery 进度事件

新任务的 SSE 使用 AG-UI 的 `RAW` 事件，客户端可按 `event.type` 区分阶段。

| event.type | 触发时机 | 对应 span |
| --- | --- | --- |
| `celery_enqueued` | Web 的 `send_task` 成功返回 | `bkplugin.chat.enqueue` |
| `celery_received` | worker 进入任务函数、通过启动校验并发送接单回执，Web 读到该回执 | `bkplugin.chat.worker.received` |

等待期间继续发送 `heartbeat`（`waiting for worker`）。接单时 Agent 尚待构建；Web 仍等到 `started` 回执带回 run ID 后才接入业务流。接单进度回执发送失败会记录日志，业务任务继续执行。重新连接已有流不会重复投递或生成这两个事件。

## 管理命令的指标和 Trace 采集

通过 `manage.py` 或 `django-admin` 运行一次性管理命令（如 `migrate`、
`collectstatic`、`shell`）时，插件同时关闭指标和 Trace，避免进程退出时等待上报，
也不会为初始化 OT 获取远程配置。
该策略同时覆盖直连 OTLP 和经 Celery 上报，即使环境或平台配置启用了指标也不会启动。

`runserver`、`celery`（含 worker/beat）、`run_wxaibot_ws` 保留原有指标和 Trace 配置；
直接启动的 Gunicorn、Celery 不受影响。常规应用日志不变。
策略位于插件初始化入口，已有模板升级插件即可生效，无需修改 `bin/manage.py`。

## 本地调试智能体插件

### 环境准备

在开始前，请确保已安装以下工具：
- `uv`: Python 包管理工具
- `cookiecutter`: 项目模板工具

### SDK 打包

在 Git 仓库根目录执行以下命令，构建小鲸智能体插件：

```bash
make build-aidev-bkplugin
```

### 生成测试智能体

使用 cookiecutter 快速生成示例智能体，可在任意目录执行：

```bash
GIT_ROOT=$(git rev-parse --show-toplevel)
cd /tmp
python -m cookiecutter ${GIT_ROOT} --directory template/builtin --no-input
```
