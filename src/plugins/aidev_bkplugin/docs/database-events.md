# 审批恢复结果交付企业微信

平台调用 Web 进程的 `chat` 接口恢复原会话时，Web 仍返回本次执行的输出；wxbot
通过数据库订阅收到同一次执行的结果，并在现有长连接上发送新消息。不重新调用
Agent，不创建新会话，也不要求两个进程共用 Redis 或进程内事件总线。

## 启用

默认开启：未设置 `BKAI_EVENT_DATABASE_ENABLED` 时，Web 发布数据库事件，
wxbot 注册订阅并消费投递。升级后启动进程前，必须先在应用的 Django 环境执行
`migrate aidev_bkplugin`，确保事件表已创建。

如需关闭，为 Web 和 wxbot **同时**配置 `BKAI_EVENT_DATABASE_ENABLED=0`；
显式设置 `=1` 可开启。后续新增的 Agent 配置统一使用 `BKAI_` 前缀，并在
`aidev_agent/config.py` 定义。
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
   AIDEV_CHAT_RESUME_READY。它不代表“审批通过”；wxbot 按原用户、session_code
   和 interruptIds 查询平台已落库的原审批结果，确认通过或拒绝后另发结果卡。
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

正文是**结束或再次中断后的结果交付**，不是逐 token/逐段实时转发。审批结果卡
可在 READY 消费时先行发送，正文仍在 FINISHED/FAILED 时交付。HTTP 调用者可以
继续流式接收。

## 审批结果卡与旧卡点击

- 通过或拒绝后发送新的结果卡，保留原标题、说明、单号、提交时间及跳转链接；
  底部显示“审批已通过”或“审批已拒绝”，不包含取消按钮。当前平台没有可信
  实际审批人字段，不使用候选 approvers 或点击用户拼接“由 xx”。
- 原卡不能通过后台审批回调主动刷新。用户再次点击原卡时仍校验原会话、目标
  和身份；平台返回 already_finalized 后，使用同一渲染函数替换底部为实际终态，
  不再次取消或恢复会话。更新需要有效签名及本次点击回调窗口，不复用旧 req_id。
- 查询精确匹配被恢复的中断，不只读最新一条，避免延迟消费时将下一次审批结果
  误写到原卡。记录缺失、未终态或相互冲突则重试，不将 READY 当作审批通过。
- 首次发送前，将结果卡快照保存到本条 EventDelivery.route 的内部 approvalMessages
  字段，不改变订阅路由。重试或进程重启复用同一内容及消息序号，不新增数据表。
- Ask-user 不产生审批结果卡；取消已有点击卡片确认，不再额外发送取消通知。
- 结果查询或发送失败沿用投递重试；同一会话后续事件等待其交付或重试耗尽，
  不影响 Web 的 HTTP 输出，也不重跑 Agent。历史已确认的 READY 不自动重放。

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
| AIDEV_CHAT_RESUME_READY | 实际恢复的 RUN_STARTED 已 flush | 通知执行已开始；wxbot 另查可信审批结果后发结果卡 |
| AIDEV_CHAT_RESUME_FINISHED | 本次执行正常收尾并完成持久化 | 交付本次完整结果；可能再次进入人机交互 |
| AIDEV_CHAT_RESUME_FAILED | 本次执行发生 RUN_ERROR 或收尾失败 | 交付错误结果或恢复失败提示 |

value 使用 schemaVersion=1，包含 eventId、occurredAt、appCode、sessionCode、
threadId、turnId、runId、interruptIds；终态还包含 events 与 persisted。
这些 ID 分别描述应用、会话、图线程、会话轮次、运行及中断，不能相互替代。
终态 checkpoint 重放及队列接管不会再次发布本次业务事件。

开启 OTel 时，仅传递 W3C traceparent/tracestate；wxbot.event.consume 延续生产者
trace。事件内容、接收者及完整异常不会作为该 span 的属性。

恢复事件在 Agent 返回流之前同步捕获入口 Trace 上下文，每次执行独立保存。
即使入口 span 已结束、流在其他线程或上下文中消费，READY 和终态事件仍使用同一
入口快照；wxbot 消费和发送 span 由该快照关联。队列初始化、取消标识准备和后台执行
仍在开始消费流时触发，未消费的流不启动任务、不发布事件。入口没有有效上下文或未安装
OTel 时不制造 Trace ID，也不借用之后消费者的上下文。

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
- 后台不主动更新旧卡，不复用过期 req_id；结果另发新卡，旧卡仅在有效点击后更新。
- 本次只覆盖 AG-UI Chat 的 resume，不补齐 HTTP 轮询卡片能力，不更改 Flow、
  legacy streaming、跨环境恢复、Web checkpoint 或审批回调鉴权协议。

## 验证

新测试位于 `tests/database_events/`，通过本插件的 `make test` 入口运行。
测试环境需同时安装/加载当前 aidev-agent 和 aidev-wxbot，以及本插件测试依赖。
跨进程用例会绑定本机随机端口，使用独立临时 SQLite 文件，不使用真实服务配置。

- Web 流式回调 + 独立 wxbot 消费者：双方获得同次执行内容。
- Web 非流式回调 + 独立 wxbot 消费者：JSON 返回与企微交付并存。
- Web 先结束、wxbot 后上线：补收审批结果卡、正文和下一张 Ask-user 卡片。
- 每个跨进程场景断言执行一次、原会话和群目标不变、两条生命周期投递均确认。
- 覆盖幂等发布、订阅隔离、原路由保护、租约过期、发送进度重试、停机未确认、
  订阅停用及迁移一致性。
- 审批通过/拒绝文案、延迟读取原中断、结果卡快照重试、无效租约禁止发送；
  wxbot 卡片测试覆盖重复点击旧卡只更新实际终态、不重复恢复。

HTTP View、ResourceManager 注入、核心生产者、数据库及企微渲染/消费者使用
实际代码；鉴权平台、模型执行和企微网络发送使用测试替身。因此这些测试证明
进程间交付机制，不等同于真实审批平台、LLM、企业微信端到端验收。数据库验证
基于 SQLite；实现避免 MySQL 8 专用锁语法，MySQL 5.7 的部署验收仍需另行执行。
