# 个人记忆接入

个人记忆一期使用平台权威 schema 提供 memory_write、memory_update、memory_search。`memory_update` 来自原始算法交付说明 README 的“2.2 替换与遗忘”及 `memory_update_atomic.py`，用于按用户意图替换或遗忘；后台抽取与整理仍自动执行。SDK 不自行复制提示词；平台负责用户隔离、持久化、TTL、检索和自动抽取整理。平台发布需要配置 memory 的 APIGateway 路由、迁移和后台 worker/beat；接入方升级 SDK 后，标准聊天入口自动接入。

## 默认启用

使用 ChatCompletionAgent、AgentInstanceFactory 或 SDK 生成的标准模板时，无需新增接入代码；启停由平台智能体配置页管理。SDK 从每次请求已有的 ResourceManager、认证用户、会话 ID 和当前轮输入构建 PersonalMemoryRuntime，自动加入三项记忆工具和回答完成回调。身份来自认证构建上下文，不能通过模型参数或 ExecuteKwargs.executor 覆盖。

SDK 在启用状态下每次请求实时探测平台 schema。平台返回未启用或缺少有效启用标记时抑制重复探测 60 秒；接口调用失败时抑制 30 秒，期间聊天跳过记忆，期限后重新探测。平台声明启用后，身份或 schema 校验失败时不缓存，下次请求重试。缓存仅针对空间灰度关闭或探测失败，按资源管理器类型、租户、应用、智能体和用户隔离；空间灰度开启可能延迟至缓存到期。配置关闭在探测前直接返回，不写入关闭缓存，因此再次开启在下次聊天触发时立即读取原配置结果。记忆 HTTP 请求使用 2 秒超时；工具和完成回调失败时保留原有聊天流程。平台以 HTTP 400 验证错误明确返回 INACTIVE_SOURCE 时，自动工具保留该业务代码并返回固定的“该来源对应的记忆已失效，本次未重复保存；新的表达可以重新记忆。”提示，标记不可重试；不暴露原始错误响应。缺少认证用户时跳过自动接入，不将应用身份当作个人身份。平台与 SDK 使用匹配的新协议版本。

普通聊天仍保留宿主历史供模型理解；记忆输入遵循已确认的触发范围。单次 `memory_write` / `memory_update` 只提交本次指定的 `text` 及当前输入，或 `role` 明确选择的最近完整原文，不把其他历史附带提交。单轮 `complete_round` 只提交当前用户输入与本轮最终回答；自定义图也不会把完整图状态合并成自动抽取输入。重新开启从新触发生效，不补抽取关闭期间的旧问答。

当前输入按消息 ID 回查宿主原文与来源时间，避免模型输入的截断或改写污染记忆。单次原文选择沿用完成资格、稳定消息 ID、正文与时间规则；它是一次明确保存操作，与自动补抽取历史不同。

跨轮回读优先使用 builtin_property.message_id 作为来源身份，数据库主键仅作旧历史兼容回退。本轮用户 ID 和接收时间随持久化事件保存，原始时间使用 builtin_property.source_timestamp，避免落库时间替换来源时间。模型结束原因随事件保存在 builtin_property.finish_reason；历史回读与当前回答使用同一结束原因判定，截断或过滤的回答不会在下一轮重新作为完整证据上传。旧历史未保存的消息身份和结束原因无法自动恢复。

模型调用结束时，SDK 在同步执行的完成回调中记录 `response_metadata.source_timestamp`；优先使用提供方原始 `created_at` / `timestamp`，缺失时使用宿主此刻生成的带时区时间。该时间在流式最终消息、结构化转换、图完成快照及 Raw/Custom model_end 事件间保留，并持久化为 `builtin_property.source_timestamp`。消息深拷贝、重复事件及下一轮回读不会改用数据库写入时间。关闭记忆时仅增加完成元数据，聊天内容、工具行为和已有回调保持原样。

助手记忆证据使用转换后真正完成的可见正文，来源正文完整保留首尾空白、换行与大小写；非空资格判断可忽略空白，聊天展示沿用既有 writer 规则。Markdown 代码片段和引用内容保留，缩进代码的必要前导缩进不作为外层空白删除，避免历史回读再次误判为隐藏思考。结构化解析与工具提升完成后，内部终态事件携带规范 `source_text`，随 `builtin_property.source_text` 保存；当前快照、历史回读与无账本回流使用同一正文、消息 ID 和原始完成时间。聊天展示仍保留原有 content，隐藏推理和 JSON 包装不会作为最终回答的记忆来源。终态回写保留完整会话属性（含 turn_id）；缺失事件或回写失败时历史证据仍不合格。用户来源正文不做这项规范化。

旧助手历史若没有有效来源完成时间，仅有数据库 `created_at` 不能确定回答何时完成，因此保持未知；显式的宿主 `timestamp` 仍可作为来源时间。这类旧记录仍可展示及用于普通聊天，若宿主明确提供 status=complete 或 memory_source_complete=true，则保留来源正文且时间保持未知；未提供明确完成契约的旧记录不作为助手证据。启停不再按来源时间过滤消息。仅有流式片段及 RUN_FINISHED、未捕获 model_end 的记录显式标为 memory_source_complete=false，不补造完成时间。用户历史的兼容时间规则保持不变。

恢复会话时，SDK 同时识别账本的来源 ID 和模型输入中的数据库 ID，保留账本原始内容与时间，不将同一条历史用户消息再次作为本轮输入加入。旧宿主缺少账本记录时，补入消息仅保留宿主提供的时间；缺失时间保持未知；是否进入记忆由本次触发范围决定，不按启用时间过滤。标准聊天入口明确接收的新用户输入仍使用接收时生成的 ID 与时间。

需要结构化解析或工具提升时，原始模型输出先以 `memory_source_complete=false` 保存。SDK 根据实际转换后的 tool_calls、正文和 finish_reason 发内部完成事件，只更新 builtin_property 的记忆资格；事件未到或更新失败时保守排除，早到、晚到和重复事件都保持幂等。工具请求及未完成的转换结果不会在下一轮被当成完整回答；原聊天正文、展示状态与工具执行不变。外部宿主若提供明确完成契约，可沿用既有 finish_reason / tool_calls 字段，SDK 不通过猜测正文来恢复旧记录的转换语义。

取消、停止或运行错误时，尚未完成的流式片段也保存相应的 finish_reason，记忆回读会排除这些片段；聊天展示状态保持原有行为。已收到 model_end 的完整回答不会因随后取消而被追溯标为未完成。

SDK 调用 `/openapi/aidev/agents/v1/memory/` 智能体运行时入口，沿用应用凭证，同时将每次调用的 username 写入网关认证字段 `bk_username`，按该用户解析 access_token。username 不保证自动存在：只配置应用凭证的宿主必须补齐真实认证用户，空值或纯空白在调用前被拒绝。网关与平台还会核对用户认证状态；`X-BKAIDEV-USER` 不能指定记忆归属，也不能用自定义认证头覆盖 ResourceManager 凭证。

显式提供 access_token 时，ResourceManager 的 username 必须与该次调用用户一致。共享图的动态用户不能复用固定用户的 token，应使用可按用户解析凭证的 ResourceManager 或按请求创建绑定用户的实例。

平台同时提供 `/openapi/aidev/private/v1/memory/` 用户入口，沿用用户态鉴权和个人 OAuth 支持；个人记忆不提供 app 类入口。两入口共用 `(tenant_id, username, agent_code)` 归属；同一用户在同一智能体内跨会话复用，其他智能体、用户或租户保持隔离。

模型工具 FORGET 只接受 active 短期记忆；active 长期记忆只能在平台管理页由管理员遗忘。状态只有 active/inactive；inactive 历史只读，失效原因由平台独立保存。旧来源不能恢复失效记录，新的真实表达允许生成新 ID；普通遗忘不代表持续禁止记忆这类信息。SDK 动态采用平台 schema，不增加层级过滤或模型参数。topic 保留为辅助标签，正文是记忆内容的主要依据；此约定由平台工具与算法落实，SDK 不改写正文生成标签。

## 自定义图接入

完全绕过标准 ChatCompletionAgent，直接调用 CommonQAAgent 或 ReActAgentBuilder 的自定义宿主，可以显式提供以下运行时。此时宿主负责认证用户、会话 ID、日期和当前轮已完成消息，消息 ID 和最终回答 ID 应保持稳定。显式运行时默认将接口错误抛给宿主；需要容错时可设置 `best_effort=True` 和 `request_timeout`。

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

标准 ChatModel / ChatOpenAI 的审计副本使用独立的 HTTP 传输选项：默认每阶段 2 秒超时，关闭客户端传输重试；自定义宿主可用运行时的 `reference_timeout` 设置正的有限秒数。它与平台接口的 `request_timeout` 独立，不修改主模型及其客户端。绑定参数不能取消审计超时，fallback 的每个模型分别受该限制；这不是整个审计的总期限。无法访问底层 OpenAI 客户端的自定义 completion client 会放弃审计并上报空引用，其他自定义模型由宿主负责设置有限的传输等待。取消图只取消等待者，已发送的同步请求在传输超时后释放执行器；已完成答案仍可提交抽取，审计失败不增加引用。生产延迟、吞吐及模型引用质量仍需单独验收。

## 验证范围

新增测试覆盖标准聊天入口自动接入、当前轮输入隔离、重开不补抽取、单次明确来源选择、稳定消息 ID、缺失身份跳过、平台未部署时正常回答，以及工具和完成回调故障容错。另覆盖工具参数与宿主身份分离、工具 artifact、完成回答快照、检索与引用的区别、前轮结果隔离、未完成回答过滤、非法审计输出、动态身份和图结束回调。同时回归已有 ReAct Builder 与资源管理方法。平台测试覆盖 MySQL 5.7 事务、真实 Milvus dense/BM25 与生命周期。

真实线上模型、消息代理和部署环境中的定时任务尚需联调验收。


## 草稿、调试与发布版本

个人记忆的 `memory_settings` 与普通智能体配置一起编辑、保存、发布和回滚。保存草稿只影响调试，正式运行使用对应发布版本。标准 ChatCompletionAgent 直接使用原配置接口已经选好的 `memory_settings` 决定是否构建记忆运行时，不新增配置版本字段或另查一遍配置。子智能体沿用自身配置。

`ResourceManager.memory_schemas` 传入 `username` 和 `agent_code`，返回 `{enabled, agent_code, schemas}`；其中 `enabled` 只表示平台空间灰度。工具与完成事件携带 Agent 编码、当前触发内容和认证身份，不携带配置版本。自定义宿主也应先使用自身正常加载的记忆配置决定是否构建显式运行时。

关闭配置后，后续聊天不创建记忆工具或完成事件；已受理的工作自然完成。重新开启从新的触发生效，单轮只提交当前问答，不补抽取旧历史。短期 TTL、显式遗忘、任务租约、幂等与索引一致性保持独立。

## 空间灰度

最终 `enabled` 同时要求对应版本的 `memory_settings.enabled` 和所属空间的灰度开放。`BKAPP_MEMORY_ROLLOUT_SPACES` 默认空名单关闭，只控制新请求准入。后台已经受理的作业不再次检查该开关。进程滚动更新可能短暂使用不同名单，不保证瞬时撤回。

新协议与平台同时升级，不保留旧的启停代次或来源时间窗口。个人环境按平台部署说明清理旧记忆存储后重建。通过聊天 API 调用远端 Agent 的客户端由远端 SDK 管理记忆，无需自行注册工具或提交完成事件。
