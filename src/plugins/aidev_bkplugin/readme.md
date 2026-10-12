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
（默认 `bkai_agent_task`）。Web 只准备会话和读取 SSE；普通聊天、Flow 轮询和审批续流的
事件生产在 worker 槽位中执行，不再由 Web 守护线程运行。

升级时同时安装对应版本的 `aidev-agent` 和 `aidev-bkplugin`，先执行应用的数据库迁移
（新增 `0003_web_agent_task`），再启动 Web 和 Celery。两类进程须使用同一数据库以及
同一 Redis 或 RabbitMQ 事件后端；进程内消息队列不支持此模式。现有模板的 Celery
启动命令已订阅 `bkai_agent_task`，本地联调也必须启动该 worker。

`AIDEV_WEB_TASK_WAIT_TIMEOUT` 是 Django 设置，默认 300 秒。排队期间 SSE 返回心跳；
超时仍未被领取的任务不会稍后再运行。超时发生在已运行任务时，仅终止当前 HTTP 等待，
不自动重复执行工具；客户端可使用 `stream_mode=attach` 重新连接。执行状态与最后一个
非流式结果保存在 `WebAgentTask`，每个应用/会话保留一条记录。

同会话正在排队或运行时，相同请求只投递一次，不同请求返回冲突错误。worker 使用原子
状态转换领取任务，禁用自动业务重试。worker 进程异常退出后的记录可能停留在运行态；
应确认原执行已退出并检查会话/工具结果后，由运维处理该记录，不能直接重复执行工具。

审批等待使用 Celery countdown 重试，等待期间不占 worker 槽位。实际续流仍占用槽位直到
事件生产结束。心跳、事件传输和延迟清理的辅助线程不属于智能体执行并发。

默认资源管理器只传递用户名和模型选择，应用凭证由 worker 本地读取，不写入任务参数。
自定义 `get_resource_manager()` 的应用须在 Web/worker 启动时均调用
`services.plugin_resource_manager.register_task_resource_manager(name, manager_type, encode, decode)`。
`encode` 返回 JSON 可序列化的非敏感配置引用，`decode` 根据这些引用在 worker 本地重建
相同身份、agent_code 和鉴权语义的资源管理器；不要传递客户端对象或凭证。未注册的类型
会明确报错，不会静默退回默认应用身份。
