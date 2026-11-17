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

BK Plugin 指本仓库的 `aidev_bkplugin` Python 包。`BKAI_CHAT_CELERY_ENABLED` 默认值为 `0`，显式设为 `1` 后，普通 Chat 由 `AgentBuilder` 注入 `CeleryChatRunner`。Chat 在 SDK 执行入口委托 runner，模型执行、resume 和回复持久化交给 worker；Web 保留鉴权、会话准备和共享事件流消费。插件原有后台入口继续沿用下文的 worker inline 策略。

流式调用链为 `Chat.execute → CeleryChatRunner → bkai_agent_task → run_chat_producer → ProducerOnlyRunner`。Web 在 producer 就绪后立即消费共享消息，不等 worker 完成；流式 worker 不注册消费者，不与 Web 抢事件。attach 只接管已有任务，不再投递。

上述 `ProducerOnlyRunner` 仅用于 Web 流式请求。同步请求使用 inline 策略；启用事件发布的同步 resume 在 worker 内消费 AG-UI 事件并聚合答案，内部流独占 producer 锁，任务入口不重复加锁。普通同步 invoke 没有内部流，由 worker 执行层获取和释放生产锁。接入侧统一使用 `ProducerResourceManager` 包装器选择策略，原资源管理器继续提供认证与资源访问。

启用前：

1. Web 和 worker 更新到同一版本。本功能不新增调度表或数据库迁移。
2. 配置共享 Redis 或其他支持回放的跨进程消息后端；InMemory 会明确拒绝远端调度。Web 和 worker 必须共享消息后端、broker 和应用配置，并继续使用原有会话及 checkpoint 存储。
3. worker 消费 `bkai_agent_task` 队列，并加载 `aidev_bkplugin.tasks`。实际并发由 worker pool 和 `--concurrency` 决定；runner 不额外扩张任务并发。
4. `BKAI_CHAT_CELERY_ENABLED` 默认关闭，普通 Chat 保持本地执行。准备好上述依赖后，在 Web 和 worker 设置 `BKAI_CHAT_CELERY_ENABLED=1` 开启；设为 `0` 回退前先排空已提交任务。旧变量 `BKAPP_CHAT_CELERY_ENABLED` 不再读取。worker 重建 Agent 时显式关闭再次投递。

模板通过 `bin/start_celery.sh` 启动 worker，`BKAI_CELERY_CONCURRENCY` 控制线程并发，未设置或为空时默认 `16`。一个 worker 的三个队列共享这 16 个执行槽位，副本数仍为 1；已有应用需同步启动脚本及 `app_desc.yml`，仅升级插件包不会修改已有启动命令。

`BKAPP_CHAT_QUEUE_TIMEOUT` 默认为 300 秒，限制任务排队及启动等待；`BKAPP_CHAT_WAIT_TIMEOUT` 默认为 1800 秒，限制 Web 等待同步结果的时间，不是运行任务的强制终止时间。worker 启动前检查有效期；过期不执行模型。Web 等待启动回执后使用实际 `run_id` 接管事件流，避免误读上轮回放；attach 只等待并消费已有流，不投递新任务。

同步和流式执行复用共享消息后端的 producer 锁，锁由 worker 获取和释放；不增加数据库排队占位。worker 在原消息后端的任务专属通道发送已启动、同步结果或错误类型回执，通道名按应用、租户、会话及任务隔离。Web 收到回执后按后端策略清理；未读取的回执数据沿用后端保留期。回执不是持久化任务状态，不参与加锁、领取或请求去重。

停止请求继续使用现有取消信号。worker 领取时检查会话级 stop；流式 producer 启动时会在清理队列前保留本轮取消意图，运行期间仍按实际 `run_id` 检查。排队停止沿用信号的有效期，不提供超出原信号生命周期的持久化撤销；排队过久应由任务有效期兜底。取消同步模型执行仍受原同步执行路径的能力限制。

任务协议仅传 JSON 执行参数、身份、历史快照和 Trace carrier，不传 Agent、闭包或认证凭据。worker 默认使用 `LLMOverrideResourceManager`，按用户名及租户从本地配置恢复认证。使用自定义资源管理器的应用须在 Django settings 配置 `BKAI_CHAT_RESOURCE_MANAGER_FACTORY` 为可调用工厂，接收 `username`、`model`、`tenant_id`，在 worker 内构建原资源实现。工厂由受信任的应用配置决定，不能来自请求 JSON。

生产锁保证不会同时生产，不保证任务完成后的重复投递不再次执行；沿用现有语义，不承诺 exactly-once 或持久化请求幂等。worker 异常退出后使用原消息后端的锁释放/过期与流心跳机制，不再遗留 building/running 数据库记录。Web 等待超时不代表运行中的任务已终止。

BK Plugin 沿用 `dispatch_async()` 的 Celery 入口，直接调用 `run_bkplugin_background_agent_task.delay(...)`，只传可 JSON 序列化的执行参数和 Trace carrier。worker 用任务级 Resource Manager 包装器提供 `run_producer_inline`，资源访问和认证仍委托原实现，不修改全局注册器或实例，在当前任务内执行 producer，并在 EOD 提交和终态回调完成后返回。worker 不再次投递任务；生产锁仍由 worker 内的消息处理器获取和释放。Trace 在任务入口恢复，并在成功或失败后释放，避免污染下一任务。

原插件后台路径仍有异步事件循环、心跳与清理线程，不代表整个 SDK 无线程。跨进程 SSE 续流仍需共享消息后端，InMemory 只适用于单进程。普通 Chat 的远端投递不改变原插件后台任务的去重、取消与重连契约。

已关闭 executor 的 DNS 提交异常仍需结合进程生命周期排查。本改动消除 worker 依赖独立 producer 线程的生命周期风险，并不证明线上 executor 关闭来源。
