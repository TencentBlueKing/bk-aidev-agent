# 个人记忆接入

个人记忆一期使用平台权威 schema 提供 memory_write、memory_update、memory_search。SDK 不自行复制提示词；平台负责用户隔离、持久化、TTL、检索和自动抽取整理。平台发布需要配置 memory 的 APIGateway 路由、迁移和后台 worker/beat；接入方升级 SDK 后，标准聊天入口自动接入。

## 默认启用

使用 ChatCompletionAgent、AgentInstanceFactory 或 SDK 生成的标准模板时，无需新增接入代码；启停由平台智能体配置页管理。SDK 从每次请求已有的 ResourceManager、认证用户、会话 ID 和完整聊天记录构建 PersonalMemoryRuntime，自动加入三项记忆工具和回答完成回调。身份来自认证构建上下文，不能通过模型参数或 ExecuteKwargs.executor 覆盖。

SDK 每次请求先探测平台 schema。平台接口未部署、响应不合法或服务暂不可用时，本次聊天跳过记忆，下次请求重新探测。记忆 HTTP 请求使用 2 秒超时；工具和完成回调失败时保留原有聊天流程。缺少认证用户时跳过自动接入，不将应用身份当作个人身份。允许先发布 SDK，再发布平台服务。

SDK 保留完整宿主聊天记录，不使用被截断或改写的模型输入替代会话快照。已有消息 ID 保持不变，缺失 ID 使用会话和消息内容生成稳定标识；会话日期优先读取历史记录的创建时间。每条消息分别保留 created_at 或 timestamp，转换为带时区的 ISO 时间；无时区时间按 UTC 处理。标准入口补入的当前消息和最终回答也带时间，同一运行时重复提交相同回答保持时间不变。未完成的 assistant 消息不参与抽取。

跨轮回读优先使用 builtin_property.message_id 作为来源身份，数据库主键仅作旧历史兼容回退。本轮用户 ID 和接收时间随持久化事件保存，原始时间使用 builtin_property.source_timestamp，避免落库时间替换来源时间。模型结束原因随事件保存在 builtin_property.finish_reason；历史回读与当前回答使用同一结束原因判定，截断或过滤的回答不会在下一轮重新作为完整证据上传。旧历史未保存的消息身份和结束原因无法自动恢复。

取消、停止或运行错误时，尚未完成的流式片段也保存相应的 finish_reason，记忆回读会排除这些片段；聊天展示状态保持原有行为。已收到 model_end 的完整回答不会因随后取消而被追溯标为未完成。

SDK 调用 `/openapi/aidev/agents/v1/memory/` 智能体运行时入口，沿用应用凭证，同时将每次调用的 username 写入网关认证字段 `bk_username`，按该用户解析 access_token。username 不保证自动存在：只配置应用凭证的宿主必须补齐真实认证用户，空值或纯空白在调用前被拒绝。网关与平台还会核对用户认证状态；`X-BKAIDEV-USER` 不能指定记忆归属，也不能用自定义认证头覆盖 ResourceManager 凭证。

显式提供 access_token 时，ResourceManager 的 username 必须与该次调用用户一致。共享图的动态用户不能复用固定用户的 token，应使用可按用户解析凭证的 ResourceManager 或按请求创建绑定用户的实例。

平台同时提供 `/openapi/aidev/private/v1/memory/` 用户入口，沿用用户态鉴权和个人 OAuth 支持；个人记忆不提供 app 类入口。两入口共用 `(tenant_id, username, agent_code)` 归属；同一用户在同一智能体内跨会话复用，其他智能体、用户或租户保持隔离。

## 自定义图接入

完全绕过标准 ChatCompletionAgent，直接调用 CommonQAAgent 或 ReActAgentBuilder 的自定义宿主，可以显式提供以下运行时。此时宿主负责认证用户、会话 ID、日期和已完成消息快照，消息 ID 和最终回答 ID 应保持稳定。显式运行时默认将接口错误抛给宿主；需要容错时可设置 `best_effort=True` 和 `request_timeout`。

```python
from aidev_agent.core.tools.memory import PersonalMemoryRuntime
from aidev_agent.services.common_agent.agent import CommonQAAgent

# 以下数据来自宿主认证和会话管理，不来自模型输出。
runtime = PersonalMemoryRuntime(
    context_provider=lambda config: {
        "agent_code": "example-agent",
        "username": authenticated_username,
        "session_id": session_id,
        "session_date": session_date,
        "messages": completed_messages,
    },
    manager=request_resource_manager,
    reference_model=reference_model,
)
agent, config = CommonQAAgent.get_agent_executor(
    llm=chat_model,
    personal_memory_runtime=runtime,
)
```

也可使用 `ReActAgentBuilder.enable_personal_memory(runtime)`。运行时上下文在每次工具调用时读取。默认构建工具时会拉取一次 schema，因此 context_provider 必须在构建时能解析认证用户。动态用户身份的宿主可以先拉取完整发现结果，通过 runtime 的 `schemas` 参数传入，随后从 RunnableConfig 解析每次调用的用户和会话；同一运行时的 Agent 身份固定。

成功完成模型回答后，图进入 memory_complete 节点：收集完成的消息、识别本轮实际引用并调用平台 complete_round。工具调用中断、异常退出或没有最终回答时，不提交完成事件。最终回答 ID 为空也不会提交，宿主必须确保消息身份完整。

标准入口接收本轮用户输入时即生成消息 ID 和带时区的接收时间，账本与模型输入共用该身份；不会为缺少时间戳的旧历史补写当前时间。最终回答的 `finish_reason` 为 `length`、`max_tokens`、`content_filter` 或 `incomplete` 时，不提交完成事件；这些未完成助手片段也不会从图历史补入完整快照。正常结束及未提供结束原因的既有模型响应保持兼容。

## 引用与 TTL

检索结果以 ToolMessage.artifact 传递，并限定在最后一条 HumanMessage 之后的当前回答轮次。use_count 不代表引用次数。

若宿主已具备明确的引用信息，可在最终 AIMessage.additional_kwargs 中提供 `personal_memory_references`。否则 SDK 用 reference_model 审核完成回答与当前轮次检索正文，选择实际用于回答的记忆；未配置时 Builder 采用主模型。模型判断存在质量误差，需要在线验收。审计输出必须是当前轮次检索到的 ID 子集；审计失败或无法确定时提交空集合，避免错误续期，仍提交会话抽取。

审计使用独立的模型配置副本，关闭副本的流式输出、缓存与模型回调，同时清空本次调用的回调。绑定模型和 fallback 模型也分别隔离，主模型及共享客户端保持原配置。不支持隔离的 Runnable 会放弃本次审计并上报空引用。平台以会话 ID 和回答 ID 去重；同轮引用多条分块、重复回调都只记一次。两个不同完成回答在同一 TTL 周期内引用，才会触发续期。

## 验证范围

新增测试覆盖标准聊天入口自动接入、完整历史保留、稳定消息 ID、缺失身份跳过、平台未部署时正常回答，以及工具和完成回调故障容错。另覆盖工具参数与宿主身份分离、工具 artifact、完成回答快照、检索与引用的区别、前轮结果隔离、未完成回答过滤、非法审计输出、动态身份和图结束回调。同时回归已有 ReAct Builder 与资源管理方法。平台测试覆盖 MySQL 5.7 事务、真实 Milvus dense/BM25 与生命周期。

真实线上模型、消息代理和部署环境中的定时任务尚需联调验收。


## 智能体开关与重新开启

平台智能体配置页提供个人记忆开关，立即对该 Agent 全部用户和版本生效；不需要新增个人设置页面。标准 ChatCompletionAgent 使用构建上下文中的真实 agent_code，子 Agent 使用自身编码，不继承父 Agent 的记忆空间。手工构建运行时须在 context_provider 返回 agent_code；缺少身份时跳过自动记忆。

ResourceManager.memory_schemas 必须传 username 与 agent_code，返回 `{enabled, agent_enabled, rollout_enabled, agent_code, memory_epoch, enabled_at, schemas}`。PersonalMemoryRuntime 的 schemas 参数接受该完整发现结果，校验 Agent 一致性和启用代次。关闭时自动入口返回 None，不附加工具或提交完成快照；平台不可用时保留正常聊天。每个 Agent/用户/轮次重新构造运行时，不跨 Agent 复用。

工具参数不包含 Agent 身份。运行时在 HTTP 请求顶层添加 agent_code 和 memory_epoch，context 只包含会话证据。平台始终执行隔离和代次校验，因此中途关闭后的旧运行时不能写入；旧 SDK 未提供 Agent/代次时平台拒绝请求，正常聊天继续。

关闭清理未完成作业，重开只处理新消息，不恢复历史作业。SDK 和平台均按新 enabled_at 过滤旧消息与无时间戳历史，防止完整会话快照补学关闭期间内容；新回答使用宿主时间戳，不能由模型编造。已保存记忆保留，短期 TTL 继续运行。平台先迁移部署、同步网关资源，再升级 SDK；旧共享数据不会自动分配给任何 Agent。

## 空间灰度

Agent 默认开启；最终 enabled 由服务端根据 Agent 所属空间的灰度和 Agent 自身开关共同决定。agent_enabled 保留配置值，rollout_enabled 表示空间灰度。两个入口和后台任务使用同一策略，撤回灰度同样清理未完成任务并使旧 epoch 失效，重新放开只接受新消息。

通过聊天 API 调用远端 Agent 的客户端，由远端 SDK 管理记忆，无需在客户端集成记忆运行时、注册记忆工具或提交完成事件。
