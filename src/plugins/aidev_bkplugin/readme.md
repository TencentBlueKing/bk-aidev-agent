# AI 小鲸后台服务

本插件需与智能体模板配合使用，用于开发和管理智能体插件。

Linux Web 实例默认最多同时运行 5 个本地 Chat producer。通过环境变量 `BKAI_CHAT_LOCAL_PRODUCER_LIMIT` 调整并发上限；设为 `0` 时全部交给 Celery。并发已满时新请求直接投递 Celery。本地进程冷启动会重新初始化 Django，仍使用应用配置的共享消息后端交付事件和结果。

在 `bkplugin.chat.request`、`bkplugin.chat.enqueue`、`bkplugin.chat.producer.dispatch` 或 `bkplugin.chat.worker` 上查看 `bkplugin.chat.producer.backend`。`local` 表示已启动本地进程，`celery` 表示走 Celery 投递路径。

两种后端的执行 span 均为 `bkplugin.chat.worker`，父 span 为 Web 端的 `bkplugin.chat.enqueue`。流式请求中，`worker.prepare` 记录同步构造流的耗时。从 `worker` 开始到 `worker.started` 成功结束，是执行端发布就绪回执所用的时间。

RabbitMQ Stream 的每次就绪回执发布都记录为 `worker.started` 下的 `agent.messaging.publish_receipt`。可恢复的连接错误在队列期限内最多重试一次。Web 端的 `bkplugin.chat.web.startup_receipt` 记录实际读取结果 `started`、`error` 或 `timeout`。如果 broker 已交付而发布确认丢失，Web 可以读到 `started`，请结合 `worker.started` 的状态及 SSE 终态判断执行结果。

同一应用、系统用户和临时目录下的 Gunicorn worker 共用名额。子进程持有文件锁直至退出，worker 轮换后仍占用原名额并继续执行；原 HTTP 流断开时客户端可按现有协议续接。Pod 或容器退出会终止其中的本地进程。

审批 Web 回调与企业微信跨进程联动见 [DatabaseEventBus 使用说明](docs/database-events.md)。

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
