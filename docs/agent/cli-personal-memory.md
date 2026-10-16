# CLI 接入个人记忆

CLI 本地执行模型和工具循环时，使用 PrivateResourceManager 调用平台 private API。若 CLI 只调用远端 Agent 的聊天接口，由远端标准 SDK 管理记忆，CLI 不重复注册工具或提交完成事件。

## 身份与配置

记忆归属为 `(tenant_id, username, agent_code)`，同一用户在同一 Agent 内跨会话复用。租户和用户由网关认证上下文决定，不能通过 CLI 请求体或请求头自行选择。CLI 已登录用户的 OAuth access_token 放入 X-Bkapi-Authorization；不需要在终端保存平台或 Agent 的应用密钥。

agent_code 必须是平台已注册、当前用户有空间访问权限的 Agent。CLI 选择已有 Agent 时使用其编码；独立运行的 CLI Agent 应先注册稳定的 Agent，再使用其配置页管理记忆。OAuth 客户端编码、当前工作目录和会话 ID 均不能代替 Agent 编码。切换用户或 Agent 时重新创建 manager 和运行时；不要跨用户共享 token。

Agent 的记忆开关默认开启。最终是否启用取决于 Agent 所属空间是否放开灰度，以及 Agent 自身开关。空间由服务端从 Agent 记录读取，伪造 space_id 不能绕过灰度。CLI 无需配置灰度白名单，也不因使用 private API 获得灰度豁免。

## 使用 SDK

```python
from aidev_agent.packages.resource_manager import PrivateResourceManager
from aidev_agent.services.agent.memory import automatic_personal_memory

# 以下变量均由 CLI 登录、Agent 选择及会话管理提供，不来自模型参数。
manager = PrivateResourceManager(
    endpoint=apigw_stage_url,
    access_token=user_access_token,
    username=authenticated_username,
    agent_code=selected_agent_code,
)
runtime = automatic_personal_memory(
    manager,
    authenticated_username,
    session_id,
    history=completed_history_records,
    messages=current_messages,
    agent_code=selected_agent_code,
)
if runtime is not None:
    builder.enable_personal_memory(runtime)
```

endpoint 是带 stage 的网关基地址，例如 `https://example.com/stage/`。适配器只实现个人记忆所需的三个资源方法，不替代整个 ResourceManagerProtocol，也不将无关资源调用切换到 private；CLI 的知识库、Skill、MCP 等资源继续由对应适配器处理。默认注册器仍使用 AgentResourceManager，CLI 无需修改全局注册器。

completed_history_records 使用宿主账本记录，包含 role、content、稳定 id、created_at/timestamp 和完成状态；current_messages 为带稳定 ID 与时间的 LangChain 消息。每轮对话重新创建 runtime，以重新发现平台策略。不要把被模型改写或截断的输入当成完整账本，也不要给旧消息重新打上当前时间。

使用 ReActAgentBuilder 时，图会添加记忆工具并在成功回答后执行完成节点。CLI 若已有自己的执行循环，可将 runtime.make_tools() 加入工具集，在最终回答完成后调用 `runtime.complete({"messages": actual_messages}, config)`；最终 AIMessage 必须有稳定 ID。中断、失败和未完成的流式回答不提交；重试同一轮保持消息和回答 ID、时间戳不变。引用使用工具返回的 artifact 和实际完成回答，不能把所有召回结果都视为引用。

自动适配使用 2 秒 HTTP 超时；未进入灰度、Agent 关闭、旧平台或临时故障时保留普通聊天。记忆请求失败不会切换到 agents/app 入口，也不会降级为不带 Agent 的共享记忆。

## HTTP 协议

基地址之后拼接以下路径，三个接口均使用用户 OAuth：

| 方法 | 路径 | 请求与用途 |
| --- | --- | --- |
| GET | `/openapi/aidev/private/v1/memory/schemas/?agent_code=AGENT` | 每轮发现策略及三项工具 schema |
| POST | `/openapi/aidev/private/v1/memory/tool/` | `{agent_code, memory_epoch, name, call, context}` |
| POST | `/openapi/aidev/private/v1/memory/complete_round/` | `{agent_code, memory_epoch, round_id, memory_ids, context}` |

响应沿用平台 `{result, data, code, message}` 封装。发现结果包含 enabled（实际生效）、agent_enabled（配置）、rollout_enabled（空间灰度）、agent_code、memory_epoch、enabled_at、schemas。enabled=false 时 schemas 为空，CLI 不提供记忆工具、不提交完成快照。

context 包含 session_id、session_date、messages；每条消息为 `{message_id, role, text, complete, timestamp}`，时间使用带时区的 ISO 格式。memory_epoch 必须使用本轮发现结果，由宿主注入顶层请求，不能由模型指定。完整 round 提交在 SQL 中幂等落盘，返回 job_id 后抽取整理异步执行；CLI 无需等待抽取结束。

撤回空间灰度或关闭 Agent 后，平台清理未完成任务、递增受影响 Agent 的 epoch，已经发出的模型 RPC 无法撤回，但迟到结果不能提交。重新放开后获取新 epoch，按 enabled_at 只提交新消息；已保存的记忆仍保留，短期 TTL 继续运行。
