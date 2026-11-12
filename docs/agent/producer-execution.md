# Producer 执行策略

SDK 默认在线程中运行 producer。构建 Chat 或 Flow Agent 时可通过 `producer_runner` 注入进程内执行回调；回调接收无参 `produce`，同步执行时返回 `None`，启动线程时返回已启动的线程。回调必须恰好启动一次，不能仅排队后返回 `None`。执行上下文在启动前捕获，启动失败会释放 producer 锁。

```python
from aidev_agent.services.agent import AgentInstanceFactory
from aidev_agent.services.messages_handler.producer import run_producer_inline

agent = AgentInstanceFactory.build_agent(
    # 其他构建参数沿用调用方配置
    producer_runner=run_producer_inline,
)
```

同步执行适用于已经位于后台 worker 的调用；HTTP SSE 入口保留默认线程模式，否则会等生产结束后才消费输出。回调属于构建期对象，不接受请求 JSON 输入，也不进入序列化模型。

BK Plugin 沿用 `dispatch_async()` 的 Celery `delay` 入口，只传可 JSON 序列化的执行参数和 Trace carrier。worker 重建 Agent 后注入 `run_producer_inline`，在当前任务内执行 producer，并在 EOD 提交和终态回调完成后返回。worker 不再次投递任务；生产锁仍由 worker 内的消息处理器获取和释放。Trace 在任务入口恢复，并在成功或失败后释放，避免污染下一任务。

此路径仍有异步事件循环、心跳与清理线程，不代表整个 SDK 无线程。跨进程 SSE 续流仍需共享消息后端，InMemory 只适用于单进程；此改动不新增消息队列的排队预占、持久化去重或 exactly-once 保证。Celery 的重复投递、取消和重连遵循现有会话与消息后端语义。

已关闭 executor 的 DNS 提交异常仍需结合进程生命周期排查。本改动消除 worker 依赖独立 producer 线程的生命周期风险，并不证明线上 executor 关闭来源。
