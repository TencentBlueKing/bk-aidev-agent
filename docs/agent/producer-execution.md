# Producer 执行策略

SDK 默认在线程中运行 producer。Chat 和 Flow 从构建时已有的 Resource Manager 获取可选的 `get_producer_runner()` 能力，不再逐层传递独立的 `producer_runner` 参数。基类默认返回 `None`；未实现新方法的既有自定义资源管理器继续使用线程，不要求修改 `ResourceManagerProtocol`。该方法可返回进程内执行回调；回调接收无参 `produce`，同步执行时返回 `None`，启动线程时返回已启动的线程。回调必须恰好启动一次，不能仅排队后返回 `None`。执行上下文在启动前捕获，启动失败会释放 producer 锁。

```python
from aidev_agent.packages.resource_manager.agent import AgentResourceManager
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.messages_handler.producer import run_producer_inline

class WorkerResources(AgentResourceManager):
    def get_producer_runner(self):
        return run_producer_inline


agent = AgentInstanceFactory.build_agent(
    # 其他构建参数沿用调用方配置
    resource_manager=WorkerResources(),
)
```

同步执行适用于已经位于后台 worker 的调用。HTTP SSE 入口不能直接使用 inline 回调，否则会等生产结束后才消费输出。回调属于构建期对象，不接受请求 JSON 输入，也不进入序列化模型。

## 普通 Chat 转入 Celery

BK Plugin 指本仓库的 `aidev_bkplugin` Python 包。开启 `BKAPP_CHAT_CELERY_ENABLED=1` 后，`AgentBuilder` 注入的 `get_producer_runner()` 返回 `CeleryChatRunner`。普通 Chat 在 SDK 执行入口委托 runner，模型执行、resume 和回复持久化交给 worker；Web 保留鉴权、会话准备和共享事件流消费。插件原有后台入口继续沿用下文的 worker inline 策略。

调用链为 `Chat.execute → CeleryChatRunner → bkai_agent_task → run_chat_producer → ProducerOnlyRunner`。同步请求等待任务结果；流式请求在 producer 就绪后立即消费共享消息，不等 worker 完成。worker 不注册消费者，不与 Web 抢事件。attach 只接管已有任务，不再投递。

启用前：

1. Web 和 worker 更新到同一版本，并执行 Django 数据迁移 `migrate`，创建 `ChatExecution` 表。
2. 配置共享 Redis 或其他跨进程消息后端；InMemory 会明确拒绝远端调度。Web 和 worker 必须共享数据库、消息后端、broker 和应用配置。
3. worker 消费 `bkai_agent_task` 队列，并加载 `aidev_bkplugin.tasks`。实际并发由 worker pool 和 `--concurrency` 决定；runner 不额外扩张任务并发。
4. 在 Web 和 worker 设置 `BKAPP_CHAT_CELERY_ENABLED=1`。默认 `0` 保留兼容行为，关闭开关前先排空已提交任务。

`BKAPP_CHAT_QUEUE_TIMEOUT` 默认为 300 秒，限制排队时间；`BKAPP_CHAT_WAIT_TIMEOUT` 默认为 1800 秒，限制 Web 等待结果/启动的时间，不是运行任务的强制终止时间。每个应用、租户、会话只有一个活动调度记录；相同请求复用任务，不同轮次不能覆盖活动任务。排队取消和过期会阻止迟到 worker 执行；带 `run_id` 的停止只影响匹配的运行。未提供 `run_id` 时停止当前会话任务。

任务协议仅传 JSON 执行参数、身份、历史快照和 Trace carrier，不传 Agent、闭包或认证凭据。worker 默认使用 `LLMOverrideResourceManager`，按用户名及租户从本地配置恢复认证。使用自定义资源管理器的应用须在 Django settings 配置 `BKAI_CHAT_RESOURCE_MANAGER_FACTORY` 为可调用工厂，接收 `username`、`model`、`tenant_id`，在 worker 内构建原资源实现。工厂由受信任的应用配置决定，不能来自请求 JSON。

数据库状态与 broker 投递不是分布式事务，不能承诺 exactly-once。worker 异常退出后，已进入 building/running 的记录不会自动重试，以免重复执行工具；必须确认旧 worker 已退出、消息生产锁已释放后再处理该会话记录。Web 等待超时不代表任务已终止。此版本尚未提供运行中任务的租约恢复或自动清理管理命令。

BK Plugin 沿用 `dispatch_async()` 的 Celery 入口，直接调用 `run_bkplugin_background_agent_task.delay(...)`，只传可 JSON 序列化的执行参数和 Trace carrier。worker 用任务级 Resource Manager 包装器提供 `run_producer_inline`，资源访问和认证仍委托原实现，不修改全局注册器或实例，在当前任务内执行 producer，并在 EOD 提交和终态回调完成后返回。worker 不再次投递任务；生产锁仍由 worker 内的消息处理器获取和释放。Trace 在任务入口恢复，并在成功或失败后释放，避免污染下一任务。

原插件后台路径仍有异步事件循环、心跳与清理线程，不代表整个 SDK 无线程。跨进程 SSE 续流仍需共享消息后端，InMemory 只适用于单进程。普通 Chat 的调度记录不改变原插件后台任务的去重、取消与重连契约。

已关闭 executor 的 DNS 提交异常仍需结合进程生命周期排查。本改动消除 worker 依赖独立 producer 线程的生命周期风险，并不证明线上 executor 关闭来源。
