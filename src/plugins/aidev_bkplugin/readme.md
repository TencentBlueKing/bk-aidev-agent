# AI 小鲸后台服务

本插件需与智能体模板配合使用，用于开发和管理智能体插件。

Linux Web 实例可设置环境变量 `BKAI_CHAT_LOCAL_PRODUCER_LIMIT=2`，让最多两个 Chat producer 在独立 Python 进程中运行。默认值为 0，全部交给 Celery。并发已满时新请求直接投递 Celery。本地进程冷启动会重新初始化 Django，仍使用应用配置的共享消息后端交付事件和结果。

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
