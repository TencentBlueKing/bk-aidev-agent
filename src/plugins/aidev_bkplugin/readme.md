# AI 小鲸后台服务

本插件需与智能体模板配合使用，用于开发和管理智能体插件。

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

### Web 聊天的 Celery 执行

Web 聊天通过 `aidev_bkplugin.run_web_agent.delay()` 投递到 `BKAI_AGENT_TASK`
（默认 `bkai_agent_task`）。Web 准备会话并读取 SSE，worker 构建和执行智能体。
普通聊天、Flow 轮询和审批续流复用 SDK 原有执行与流式线程机制；无需修改 SDK，
不新增任务模型或数据库迁移。

Web 和 worker 须配置同一个可共享的 Celery result backend，用于返回非流式结果和
传播启动失败。任务显式开启结果保存，并沿用 Celery 的结果过期配置。流式事件仍走
现有 Redis 或 RabbitMQ 回放后端，Web 和 worker 使用相同连接配置；进程内消息队列
不支持跨进程。现有模板的 Celery 启动命令已订阅 `bkai_agent_task`，本地联调也须启动 worker。

`AIDEV_WEB_TASK_WAIT_TIMEOUT` 是 Django 设置，默认 300 秒。排队期间 SSE 返回心跳；
超过排队期限的任务由 worker 拒绝执行。HTTP 等待超时不会终止已经开始的任务，
客户端可用 `stream_mode=attach` 读取现有事件。attach 不投递新任务；没有事件或活跃
producer 时沿用 SDK 的 attach-unavailable 行为。

任务使用 Celery 默认确认方式，不自动重试模型和工具执行。会话流锁、取消及回放行为
沿用 SDK；不额外提供请求去重或任务状态表。审批等待通过 countdown 重试释放 worker，
审批完成后在 worker 中执行已有续流逻辑。

默认资源管理器只传递用户名和模型选择，应用凭证由 worker 本地读取，不写入任务参数。
自定义 `get_resource_manager()` 的应用须在 Web/worker 启动时均调用
`services.plugin_resource_manager.register_task_resource_manager(name, manager_type, encode, decode)`。
`encode` 返回 JSON 可序列化的非敏感配置引用，`decode` 根据这些引用在 worker 本地重建
相同身份、agent_code 和鉴权语义的资源管理器；不要传递客户端对象或凭证。未注册的类型
会明确报错，不会静默退回默认应用身份。
