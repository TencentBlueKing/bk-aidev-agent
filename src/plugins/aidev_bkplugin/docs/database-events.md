# 审批恢复结果交付企业微信

平台调用 Web 进程的 `chat` 接口恢复原会话时，Web 仍返回本次执行的输出；wxbot
通过数据库订阅收到同一次执行的结果，并在现有长连接上发送新消息。不重新调用
Agent，不创建新会话，也不要求两个进程共用 Redis 或进程内事件总线。

## 启用

默认关闭。启用前需在应用的 Django 环境执行 `migrate aidev_bkplugin`，再为 Web
和 wxbot **同时**配置 `BKAPP_AIDEV_DATABASE_EVENTS_ENABLED=1`。
两端必须加载匹配的 SDK / 插件版本，使用同一个应用标识、数据库和会话环境。
不需要为 wxbot 新增表，通用表由 bkplugin 的迁移维护。

wxbot 在普通 Chat 请求获取原 session_code 后、消费 Agent 输出前，绑定订阅。
绑定信息包括应用、机器人、原会话、已校验的用户与原发送目标。后续 `/new` 不
改变旧会话的绑定。启用前已产生、且没有订阅的历史审批不自动补发；不能根据
“当前最新会话”猜测原接收方。

## 调用顺序

1. 用户在企微发起会话，wxbot 获取原 session_code 并保存订阅，再发送审批卡片。
2. 审批平台按原协议调用 Web `chat`，携带原 session_code 及 resume/interruptId。
3. bkplugin 的 AgentBuilder 用 EventResourceManager 包装原 ResourceManager，
   委托原有鉴权、模型配置等能力，仅把发布操作交给 DatabaseEventBus。
4. aidev_agent 的实际恢复生产者在 RUN_STARTED 入队并 flush 后发布
   AIDEV_CHAT_RESUME_READY。它不代表“审批通过”，不用于更新原审批卡。
5. 本次执行的 AG-UI 事件照常进入 Web 响应和会话持久化流程。非流式 HTTP
   回调内部也走同一恢复路径，最终聚合为原有 JSON 响应形态，执行次数仍为一次。
6. 生产者完成会话写入与队列收尾后，发布 FINISHED 或 FAILED，携带本次执行
   的展示事件快照；不携带 STATE_SNAPSHOT、MESSAGES_SNAPSHOT 或全量历史。
7. DatabaseEventBus 为每个匹配订阅持久化独立投递记录。Web 返回给调用方的结果
   不会“消费掉” wxbot 的投递。
8. wxbot 的独立消费者领取记录，用现有 AG-UI 渲染器生成文本及下一张
   Ask-user / 审批卡片，经现有连接的 send_message 发往原用户或群。
9. 每条消息收到发送成功确认后记录进度，全部完成才确认整条投递。下次原生
   卡片点击仍走现有身份校验、结构化答案和原会话恢复流程。

本版是**结束或再次中断后的结果交付**，不是逐 token/逐段实时转发。READY 只做
通知与审计；wxbot 处理 FINISHED/FAILED 才发送结果。HTTP 调用者可以继续流式接收。

## 分层与事件

| 模块 | 职责 |
| --- | --- |
| aidev_agent.events | 定义通用事件名称与 AG-UI CUSTOM 外壳 |
| ResourceManager | publish_event / event_publishing_enabled 扩展点，默认 no-op / False |
| aidev_agent 恢复生产者 | 发布实际执行的生命周期和展示结果，不依赖 Django 或 wxbot |
| bkplugin DatabaseEventBus | 持久订阅、事务内生成投递、领取租约、进度、确认及失败重试 |
| wxbot | 保存可信原路由、消费订阅、复用现有卡片渲染与长连接发送 |

| CUSTOM.name | 触发点 | 用途 |
| --- | --- | --- |
| AIDEV_CHAT_RESUME_READY | 实际恢复的 RUN_STARTED 已 flush | 通知执行已开始；不能当作审批结果 |
| AIDEV_CHAT_RESUME_FINISHED | 本次执行正常收尾并完成持久化 | 交付本次完整结果；可能再次进入人机交互 |
| AIDEV_CHAT_RESUME_FAILED | 本次执行发生 RUN_ERROR 或收尾失败 | 交付错误结果或恢复失败提示 |

value 使用 schemaVersion=1，包含 eventId、occurredAt、appCode、sessionCode、
threadId、turnId、runId、interruptIds；终态还包含 events 与 persisted。
这些 ID 分别描述应用、会话、图线程、会话轮次、运行及中断，不能相互替代。
终态 checkpoint 重放及队列接管不会再次发布本次业务事件。

开启 OTel 时，仅传递 W3C traceparent/tracestate；wxbot.event.consume 延续生产者
trace。事件内容、接收者及完整异常不会作为该 span 的属性。

DatabaseEventBus 的 subscribe 注册的是持久订阅身份及路由，不是 Python 回调。
其他插件可以注册自己的 subscriber/name/session_code，独立领取、确认投递并执行
自己的处理逻辑；不要求 wxbot 和 Web 在同一进程调用 subscribe(callback)。

## 存储与恢复边界

- EventSubscription：不可被静默覆盖的订阅路由，property 为插件扩展 JSON。
- EventDelivery：事件快照、原路由副本、状态、租约、重试次数及消息发送进度。
- 同一应用/会话/订阅者按顺序领取；不同订阅者各自确认，不互相抢走结果。
- 消费者离线时记录保持 pending；重新上线后补收。租约为 120 秒，单次发送
  等待上限 45 秒，发送前后续租。过期租约可重新领取，旧消费者不能再确认。
- 发送失败指数退避，最多 8 次；耗尽后保留 failed 供排查，不自动重跑 Agent。
- 属于至少一次交付：发送成功但进度尚未写入时进程崩溃，仍可能重复发送。
  企微没有可用的端到端幂等确认时，不承诺 exactly-once。
- READY 写入失败会在生产者收尾时重试。数据库持续不可用或生产者在终态事件
  写入前退出，尚不能保证结果补投；应告警并人工核对原会话，不通过自动重跑
  已审批工具修复。此实现不是跨平台会话写入与事件表的分布式事务。
- 记录包含本次回复、工具展示数据和路由，按会话数据保护；不要把 envelope、
  property 或完整异常写入日志。部署需配置终态记录保留/清理策略，未投递记录
  不应按普通日志直接清理。当前版本不自动删除事件或修改用户订阅。
- 不更新后台审批完成前发出的旧卡片，不复用过期 req_id。后续结果使用新消息。
- 本次只覆盖 AG-UI Chat 的 resume，不补齐 HTTP 轮询卡片能力，不更改 Flow、
  legacy streaming、跨环境恢复、Web checkpoint 或审批回调鉴权协议。

## 验证

新测试位于 `tests/database_events/`，通过本插件的 `make test` 入口运行。
测试环境需同时安装/加载当前 aidev-agent 和 aidev-wxbot，以及本插件测试依赖。
跨进程用例会绑定本机随机端口，使用独立临时 SQLite 文件，不使用真实服务配置。

- Web 流式回调 + 独立 wxbot 消费者：双方获得同次执行内容。
- Web 非流式回调 + 独立 wxbot 消费者：JSON 返回与企微交付并存。
- Web 先结束、wxbot 后上线：补收正文和下一张 Ask-user 卡片。
- 每个跨进程场景断言执行一次、原会话和群目标不变、两条生命周期投递均确认。
- 覆盖幂等发布、订阅隔离、原路由保护、租约过期、发送进度重试、停机未确认、
  订阅停用及迁移一致性。

HTTP View、ResourceManager 注入、核心生产者、数据库及企微渲染/消费者使用
实际代码；鉴权平台、模型执行和企微网络发送使用测试替身。因此这些测试证明
进程间交付机制，不等同于真实审批平台、LLM、企业微信端到端验收。数据库验证
基于 SQLite；实现避免 MySQL 8 专用锁语法，MySQL 5.7 的部署验收仍需另行执行。
