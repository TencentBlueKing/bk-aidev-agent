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

BK Plugin 指本仓库的 `aidev_bkplugin` Python 包。`BKAI_CHAT_CELERY_ENABLED` 默认值为 `1`，普通 HTTP Chat 在视图入口通过 `ChatDispatcher` 投递 Celery。Web 完成鉴权、参数校验及会话准备，不构建 Agent。显式传入的历史先写入会话；worker 从 SESSION 读取完整历史并构建一次 Agent，保留命令切换和 resume 语义，不再读完历史后用消息快照覆盖。

流式调用链为 `Chat API → ChatDispatcher → bkai_agent_task → worker 构建 Agent → ProducerOnlyRunner`。同一次 HTTP 请求返回 `text/event-stream`，先发送 SSE 注释以刷新响应头，再等待 worker 启动回执并转发共享事件；不返回任务 ID 要求客户端轮询。启动失败或等待超时输出 SSE 错误与结束事件。同步请求等待 worker 结果，继续返回原 JSON 响应。

attach 要求已有 `session_code` 和 `stream=True`，先通过用户态会话查询校验访问权限，再接入已有事件流，不投递、不构建 Agent、不保存输入或创建新 turn。worker 的流式 producer 不注册消费者；同步 resume 使用 inline producer 并在 worker 内聚合事件。`get_producer_runner()` 只负责 worker 内 producer 的执行策略；移除 SDK 的 `RemoteProducerRunner`、Web 的 `CeleryChatRunner` 及 AgentBuilder 的远端注入开关。关闭 Celery 时，原 HTTP 本地执行路径保留；直接使用 SDK/AgentBuilder 的代码保持本地策略，原插件异步入口保持自己的 Celery 调度。

启用前：

1. Web 和 worker 更新到同一版本。本轮任务协议从 v1 改为 v2；升级前暂停入口并排空旧任务，避免新旧消息混用。本功能不新增调度表或数据库迁移。
2. 配置共享 Redis 或其他支持回放的跨进程消息后端；InMemory 会明确拒绝远端调度。Web 和 worker 必须共享消息后端、broker 和应用配置，并继续使用原有会话及 checkpoint 存储。
3. worker 消费 `bkai_agent_task` 队列，并加载 `aidev_bkplugin.tasks`。实际并发由 worker pool 和 `--concurrency` 决定；runner 不额外扩张任务并发。
4. `BKAI_CHAT_CELERY_ENABLED` 默认开启，部署前须准备好上述依赖。需要回退本地执行时，在 Web 和 worker 设置 `BKAI_CHAT_CELERY_ENABLED=0`，并先排空已提交任务。旧变量 `BKAPP_CHAT_CELERY_ENABLED` 不再读取。远端投递仅在 HTTP Chat 视图入口发生，worker 构建不再需要关闭调度的开关。

模板通过 `bin/start_celery.sh` 启动 worker，`BKAI_CELERY_CONCURRENCY` 控制线程并发，未设置或为空时默认 `16`。一个 worker 的三个队列共享这 16 个执行槽位，副本数仍为 1；已有应用需同步启动脚本及 `app_desc.yml`，仅升级插件包不会修改已有启动命令。

`BKAPP_CHAT_QUEUE_TIMEOUT` 默认为 300 秒，限制任务排队及启动等待；`BKAPP_CHAT_WAIT_TIMEOUT` 默认为 1800 秒，限制 Web 等待同步结果的时间，不是运行任务的强制终止时间。worker 启动前检查有效期；过期不执行模型。Web 等待启动回执后使用实际 `run_id` 接管事件流，避免误读上轮回放；attach 只等待并消费已有流，不投递新任务。

同步和流式执行复用共享消息后端的 producer 锁，锁由 worker 获取和释放；不增加数据库排队占位。worker 在原消息后端的任务专属通道发送已启动、同步结果或错误类型回执，通道名按应用、租户、会话及任务隔离。Web 收到回执后按后端策略清理；未读取的回执数据沿用后端保留期。回执不是持久化任务状态，不参与加锁、领取或请求去重。

停止请求继续使用现有取消信号。worker 领取时检查会话级 stop；流式 producer 启动时会在清理队列前保留本轮取消意图，运行期间仍按实际 `run_id` 检查。排队停止沿用信号的有效期，不提供超出原信号生命周期的持久化撤销；排队过久应由任务有效期兜底。取消同步模型执行仍受原同步执行路径的能力限制。

任务协议 v2 仅传 JSON 执行参数、会话标识、身份及 Trace carrier，不传完整历史或知识配置快照，不传 Agent、闭包或认证凭据。worker 默认使用 `LLMOverrideResourceManager`，按用户名及租户从本地配置恢复认证。使用自定义资源管理器的应用须在 Django settings 配置 `BKAI_CHAT_RESOURCE_MANAGER_FACTORY` 为可调用工厂，接收 `username`、`model`、`tenant_id`，在 worker 内构建原资源实现。工厂由受信任的应用配置决定，不能来自请求 JSON。

生产锁保证不会同时生产，不保证任务完成后的重复投递不再次执行；沿用现有语义，不承诺 exactly-once 或持久化请求幂等。worker 异常退出后使用原消息后端的锁释放/过期与流心跳机制，不再遗留 building/running 数据库记录。Web 等待超时不代表运行中的任务已终止。

BK Plugin 沿用 `dispatch_async()` 的 Celery 入口，直接调用 `run_bkplugin_background_agent_task.delay(...)`，只传可 JSON 序列化的执行参数和 Trace carrier。worker 用任务级 Resource Manager 包装器提供 `run_producer_inline`，资源访问和认证仍委托原实现，不修改全局注册器或实例，在当前任务内执行 producer，并在 EOD 提交和终态回调完成后返回。worker 不再次投递任务；生产锁仍由 worker 内的消息处理器获取和释放。Trace 在任务入口恢复，并在成功或失败后释放，避免污染下一任务。

原插件后台路径仍有异步事件循环、心跳与清理线程，不代表整个 SDK 无线程。跨进程 SSE 续流仍需共享消息后端，InMemory 只适用于单进程。普通 Chat 的远端投递不改变原插件后台任务的去重、取消与重连契约。

已关闭 executor 的 DNS 提交异常仍需结合进程生命周期排查。本改动消除 worker 依赖独立 producer 线程的生命周期风险，并不证明线上 executor 关闭来源。
