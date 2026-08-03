# @blueking/chat-helper SDK API 参考

> 版本：`@blueking/chat-helper@0.0.12-beta.12`（peerDep `vue ^3.5.24`）。本文档已同步 HITL（human in the loop）中断/恢复、flow-agent 操作、模型列表（`getLlms`）等能力。

## 基础配置

```typescript
import { useChatHelper, AGUIProtocol } from '@blueking/chat-helper';

const protocol = new AGUIProtocol({
  onStart: () => console.log('开始响应'),
  onMessage: (event) => console.log('事件:', event),
  onDone: () => console.log('响应完成'),
  onError: (error) => console.error('错误:', error),
});

const chatHelper = useChatHelper({
  requestData: {
    urlPrefix: 'https://your-api.com/api/',
    // 支持：对象 | 函数 | ref | computed（每次请求读取最新值）
    headers: () => ({
      Authorization: `Bearer ${getToken()}`,
    }),
    data: () => ({
      app_id: 'your-app-id',
    }),
    // headers: computed(() => ({ Authorization: `Bearer ${token.value}` })),
  },
  protocol,
});

// 原子组件模式必须：注入消息模块到 protocol
protocol.injectMessageModule(chatHelper.message);

// 解构模块
const { agent, session, message, http } = chatHelper;
```

---

## HTTP 错误处理

### 全局错误处理器

```typescript
chatHelper.onError(
  (error) => {
    // error 是 IRequestError：带 code / config / response
    console.error(error.code, error.message);
  },
  { ignoreErrors: [/\/llms\//] }, // 字符串包含匹配或正则，命中则不上报
);
```

所有请求（`request` 与 `streamRequest`）的失败都会经过该处理器，且在抛出前调用。

### 错误 message 的解析规则

`FetchClient` 会按下列顺序从响应体中提取业务错误信息，命中即返回，全部落空才退化为 `Request failed with status code {status}`：

| 优先级 | 响应体形态 | 典型来源 |
|--------|-----------|---------|
| 1 | `{ error: { code, message, data } }` | aidev 插件 `APIRenderer`、新版网关 |
| 2 | `{ result, code, message, data }` | 旧版蓝鲸标准，如 blueapps 登录态失效（401） |
| 3 | `{ detail }` | DRF 原生异常 |

`IRequestError.code` 取自响应体中的业务错误码（如 `"403"`、`"1306000"`），仅在无法解析时才为 `'ERR_BAD_RESPONSE'`。HTTP 200 + 业务码异常（`code` 不为 `0` / `'success'`）走同一套解析。

### 超时与取消的区分

超时和用户主动取消都表现为 `AbortError`，SDK 内部靠标记区分：

- **用户取消**（`config.controller.abort()`）：静默返回 `undefined`，不触发 `onError`
- **超时**（默认 30s，`config.timeout` 可调）：抛出 `code` 为 `'ECONNABORTED'` 的错误，会触发 `onError`

空响应体（如 204）不再因读取业务码而抛 TypeError，直接返回 `undefined`。

---

## 核心架构

`chat-helper` 采用**中介者模式**协调模块通信：

| 模块 | 职责 | 响应式数据 |
|------|------|-----------|
| agent | AI 代理管理、聊天发送、**HITL 中断/恢复**、flow 用户操作、**可用模型列表** | `info`, `isInfoLoading`, `isChatting`, `models`, `isModelsLoading` |
| session | 会话 CRUD、切换、反馈、**审批轮询** | `list`, `current`, `isXxxLoading` |
| message | 消息 CRUD、状态管理、**flow-agent 任务查询** | `list`, `isListLoading`, `isDeleteLoading` |
| http | 底层 HTTP 请求（`agent`/`session`/`message`/`fetchClient`） | - |

**数据流向**：
```
用户操作 → Agent/Session/Message → Mediator → HTTP → 后端 API
                    ↑                                      ↓
                    ←────────── 流式事件/响应数据 ←─────────
```

---

## Agent 模块

### 响应式数据

| 属性 | 类型 | 说明 |
|------|------|------|
| info | `Ref<IAgentInfo \| null>` | Agent 信息 |
| isInfoLoading | `Ref<boolean>` | 是否正在加载信息 |
| isChatting | `Ref<boolean>` | 是否正在聊天 |
| models | `Ref<ILlmItem[]>` | 可用模型列表（`getLlms` 成功后写入） |
| isModelsLoading | `Ref<boolean>` | 是否正在加载模型列表 |

### 方法

#### getAgentInfo

获取 Agent 信息。

```typescript
await agent.getAgentInfo();

// 获取后通过 info 访问
const agentName = agent.info.value?.agentName;
const commands = agent.info.value?.conversationSettings?.commands;
const openingRemark = agent.info.value?.conversationSettings?.openingRemark;
const predefinedQuestions = agent.info.value?.conversationSettings?.predefinedQuestions;
const resources = agent.info.value?.resources;
// 上传支持：组件侧跟随选中模型 property.support_vision；快捷指令仍可用 command.supportUpload
const commandUpload = commands?.[0]?.supportUpload?.vision;
// agent.promptSetting.supportUpload 仍可由后端返回，但 ChatBot 附件按钮不再以此为准
const agentSupportUpload = agent.info.value?.promptSetting?.supportUpload?.vision;
```

#### getLlms

拉取可用模型列表（`GET llms/`），写入 `agent.models`；未传 `llm_type` 时默认 `chat.completion`。

```typescript
const list = await agent.getLlms({ llm_type: 'chat.completion' });
// agent.models.value === list
```

#### chat

发送消息。

```typescript
await agent.chat(
  userInput: string | IUserMessage['content'],  // 支持文本或多模态内容
  sessionCode: string,
  url?: string,                  // 自定义 chat 端点
  config?: RequestConfig,
  property?: IMessageProperty,   // 第 5 个参数：引用内容 / 快捷键等消息属性
  model?: string,                // 第 6 个参数：热切换 llm_code（须在 GET llms/ 列表内）
);

// 带额外参数（通过第 5 个参数 property 传递）
await agent.chat(userInput, sessionCode, undefined, undefined, {
  extra: { cite: '引用内容' },
});

// 模型热切换
await agent.chat(userInput, sessionCode, undefined, undefined, property, 'hy3-preview');

// 自定义请求参数（如 temperature）走 config.data，不要把 model 塞进 data
await agent.chat(userInput, sessionCode, undefined, {
  data: { temperature: 0.8 },
});
```

> `property` 会随乐观更新的用户消息写入 `message.list`，用于承载 `cite`（引用）、`command`（快捷键）、`context`、`resources` 等信息。

#### stopChat

停止当前聊天（**后端中止**）。请求后端停止本次会话生成。

```typescript
await agent.stopChat(sessionCode: string);  // POST session_content/stop/
```

失败时会 reject（`ChatBusinessManager.stopGeneration` 也会向上抛，由 ChatBot 转成 `@error` 事件），调用方需自行 catch。

#### abortChat

中止当前聊天（**纯前端中止**）。仅在前端 `abort` 当前 SSE 连接，后端仍继续处理。切换会话时内部会自动调用。

```typescript
agent.abortChat();  // 无参数，abort 当前 AbortController
```

> 区分：`abortChat()` 只断开前端连接（后端不停）；`stopChat(sessionCode)` 通知后端真正停止生成。

#### streamRequest

底层流式请求原语。`chat` / `resendMessage` / `resumeStreamingChat` / HITL 恢复均通过它发起。可直接用于恢复中断（携带 `resume`）。

```typescript
agent.streamRequest({
  sessionCode: string,
  url?: string,
  config?: IRequestConfig,
  resume?: IResume,        // HITL：恢复中断，写入 execute_kwargs.resume
  input?: string,          // 直接传入用户输入（不经 createAndPlusMessage）
  lastMessageId?: string,  // 恢复流式时定位最后一条消息
});
// 实际请求：POST chat_completion/
//   { session_code, input, execute_kwargs: { stream: true, persist_input, last_message_id, resume } }
```

#### pollResumeSession

HITL 审批轮询。检测最后一条消息是否为待审批的中断消息（`MessageRole.Interrupt` 且 ticket 处于 `Pending`/`Draft`），若是则轮询 `is_resume/`；可继续时自动以 `resume: { interruptId, status: Resolved }` 重新发起 `streamRequest`，否则 30s 后重试（会话不匹配时停止）。

```typescript
agent.pollResumeSession(sessionCode: string);
```

#### clearLongPollTimer

清除 `pollResumeSession` 的长轮询定时器。

```typescript
agent.clearLongPollTimer();
```

#### userOperationStreamRequest

用户操作（flow 节点重试/跳过、审批取消）后触发流式续聊。

```typescript
await agent.userOperationStreamRequest(
  sessionCode: string,
  operation: UserOperation,         // FlowNodeRetry / FlowNodeSkip / ApprovalCancel
  payload: IUserOperationPayload,
  config?: IRequestConfig
);
// 先 POST user_operation/；
// 非 ApprovalCancel 操作 → 继续 streamRequest；
// ApprovalCancel → 清除长轮询并重新 pollResumeSession
```

#### resumeStreamingChat

恢复流式聊天（页面刷新后恢复）。

```typescript
await agent.resumeStreamingChat(sessionCode: string);
```

#### resendMessage

编辑并重发消息。

```typescript
await agent.resendMessage(
  messageId: string | number,
  sessionCode: string,
  newContent?: string | IUserMessage['content'],  // 支持多模态
  url?: string,
  config?: RequestConfig
);
```

### 类型定义

```typescript
interface ISupportUpload {
  vision: boolean;
}

interface IAgentInfo {
  agentName?: string;
  resources?: IAgentResourceItem[];
  saasUrl?: string;
  chatGroup?: { enabled: boolean; staff: string[]; username: string };
  conversationSettings?: {
    commands?: IAgentCommand[];
    enableChatSession?: boolean;
    openingRemark?: string;
    predefinedQuestions?: string[];
  };
  promptSetting?: {
    content?: IMessage[];
    supportUpload?: ISupportUpload;  // Agent 级别的上传支持
  };
}

interface IAgentCommand {
  id: string;
  name: string;
  alias?: string;
  icon?: string;
  agentId: number;
  status: string;
  content: string | null;
  components: IAgentCommandComponent[];
  supportUpload?: ISupportUpload;  // Command 级别的上传支持
}

/** 可用模型项（对齐 GET llms/ 与 chat-x IModelOption） */
interface ILlmItem {
  id: number;
  llm_code: string;   // chat_completion 热切换传此值
  llm_name: string;   // ModelSelector v-model 选中值
  llm_type: string;
  max_token_size: number;
  property: ILlmProperty;
  space_auth_mode: string;
  user_auth_mode: string;
  base_model?: string;
  description?: string;
  disabled?: boolean;
  icon?: string;
  tag_names?: string[];
}

interface ILlmListQuery {
  fuzzy?: string;
  llm_type?: string;   // 默认 chat.completion
  supports?: string;
}

// 消息属性：由 chat() 第 5 个参数 / 消息 property 字段承载
interface IMessageProperty {
  [key: string]: unknown;
  extra?: {
    [key: string]: unknown;
    cite?: string | { data: Array<{ key: string; value: string }>; title: string; type: string };
    command?: string;                          // 快捷键命令
    context?: Array<Record<string, unknown>>;  // 上下文信息
    resources?: Array<Record<string, unknown>>;// @ 选择的资源列表
  };
}
```

---

## Session 模块

### 响应式数据

| 属性 | 类型 | 说明 |
|------|------|------|
| list | `Ref<ISession[]>` | 会话列表 |
| current | `Ref<ISession \| null>` | 当前会话 |
| isListLoading | `Ref<boolean>` | 是否正在加载列表 |
| isDeleteLoading | `Ref<boolean>` | 是否正在删除 |
| isBatchDeleteLoading | `Ref<boolean>` | 是否正在批量删除 |

### SessionStatus 枚举

会话运行状态，用于 HITL / 恢复场景判断。

```typescript
enum SessionStatus {
  Running = 'running',
  Finished = 'finished',
  Failed = 'failed',
  Cancelled = 'cancelled',
}
```

> `resumeStreamingChat` 仅在 `session.current.value?.status === SessionStatus.Running` 时才重连流式（页面刷新恢复）。

### ISession 接口

```typescript
interface ISession {
  sessionCode: string;
  sessionName: string;
  sessionContentCount?: number;  // 会话消息数量，判断是否有内容
  status?: SessionStatus;        // 会话运行状态
  isTemporary?: boolean;         // 是否临时会话
  model?: string;                // 模型
  rate?: number;                 // 评分
  comment?: string;              // 评论
  createdAt?: string;
  updatedAt?: string;
  // 其余：anchorPathResources?, tools?, roleInfo?, sessionProperty?
}
```

### 方法

#### getSessions

获取会话列表。

```typescript
await session.getSessions();
```

#### chooseSession

选择会话（推荐使用）。

```typescript
await session.chooseSession(sessionCode: string);

// 带选项
await session.chooseSession(sessionCode, {
  loadMessages: boolean,  // 是否加载消息列表，默认 true
});

// 空会话跳过消息加载
const hasContent = (targetSession.sessionContentCount ?? 0) > 0;
await session.chooseSession(sessionCode, { loadMessages: hasContent });
```

**注意**：`chooseSession` 会自动：
- 停止当前聊天
- 设置当前会话
- 加载消息列表（除非 `loadMessages: false`）

#### createSession

创建会话。

```typescript
await session.createSession(
  session: Partial<ISession>,
  options?: {
    loadMessages?: boolean,  // 默认 false（新会话无消息）
  }
);

await session.createSession({
  sessionCode: `new_session_${Date.now()}`,
  sessionName: '新会话',
});
```

#### updateSession

更新会话。

```typescript
await session.updateSession(session: ISession);

await session.updateSession({
  ...currentSession,
  sessionName: '新名称',
});
```

#### deleteSession

删除单个会话。如果删除的是当前会话，自动切换到列表第一个。

```typescript
await session.deleteSession(sessionCode: string);
```

#### batchDeleteSessions

批量删除会话。自动处理列表更新和当前会话切换：
- 如果当前会话在删除列表中且仍有剩余会话，切换到第一个
- 如果全部删除，清空当前会话和消息列表

```typescript
await session.batchDeleteSessions(sessionCodes: string[]);

// 示例：删除所有会话
const allCodes = session.list.value.map(s => s.sessionCode);
await session.batchDeleteSessions(allCodes);

// 示例：删除选中的会话
await session.batchDeleteSessions(['session_1', 'session_2']);
```

#### renameSession

AI 自动重命名会话。

```typescript
await session.renameSession(sessionCode: string);
```

#### getSessionFeedbackReasons

获取反馈原因列表（用于 like/unlike 弹窗展示）。

```typescript
const reasons: string[] = await session.getSessionFeedbackReasons(
  rate: number  // 5 = like, 0 = unlike
);
```

#### postSessionFeedback

提交会话反馈。

```typescript
await session.postSessionFeedback({
  sessionCode: string,
  sessionContentIds: (string | number)[],  // 用户消息 ID 列表
  rate: number,          // 5 = like, 0 = unlike
  labels: string[],      // 反馈原因列表
  comment: string,       // 自定义原因
});
```

#### uploadFile

上传文件。

```typescript
const result = await session.uploadFile(
  sessionCode: string,
  file: File
);
// result: 上传结果对象（具体结构由后端定义）
```

#### isResumeSession（HITL 审批轮询端点）

查询会话中断是否可恢复（审批是否通过）。通常无需手动调用，由 `agent.pollResumeSession` 内部使用。

```typescript
const canResume: boolean = await session.isResumeSession(sessionCode: string);
// GET session/{sessionCode}/is_resume/ → boolean
```

---

## Message 模块

### 响应式数据

| 属性 | 类型 | 说明 |
|------|------|------|
| list | `Ref<IMessage[]>` | 消息列表 |
| isListLoading | `Ref<boolean>` | 是否正在加载列表 |
| isDeleteLoading | `Ref<boolean>` | 是否正在删除 |

### 方法

#### getMessages

获取消息列表。

```typescript
await message.getMessages(sessionCode: string);
```

#### plusMessage

添加消息（仅本地）。

```typescript
message.plusMessage(message: IMessage);
```

#### createAndPlusMessage

创建并添加消息（调用接口）。

```typescript
await message.createAndPlusMessage(message: IMessage);
```

#### modifyMessage

修改消息（仅本地）。

```typescript
message.modifyMessage(message: IMessage);
```

#### deleteMessages

批量删除消息。

```typescript
await message.deleteMessages(messages: IMessage[]);
// SDK 只使用 user message 的 id 调用后端 API，
// 但会从前端列表中移除所有传入的消息
```

#### shareMessages

分享消息。

```typescript
const result = await message.shareMessages(
  sessionCode: string,
  messages: IMessage[],
  expiredAt?: number   // 过期时间戳（可选）
);

// result: { share_page: string, share_token: string }
```

#### getCurrentLoadingMessage

获取当前加载中的消息。

```typescript
const loadingMsg = message.getCurrentLoadingMessage();
```

#### getMessageByMessageId

根据 ID 获取消息。

```typescript
const msg = message.getMessageByMessageId(id: string | number);
```

#### clearMessages

清空当前会话的所有消息（内部调用 `deleteMessages(list.value)`，同步删除后端数据）。

```typescript
await message.clearMessages();
```

#### getFlowAgentTaskInfo / getFlowAgentTaskNodeInfo

获取 flow-agent（流程引擎）任务信息与节点详情，用于流程编排消息的详情展示。

```typescript
await message.getFlowAgentTaskInfo(taskId: number);
// GET flow_agent/{taskId}/task_info/

await message.getFlowAgentTaskNodeInfo(taskId: number, nodeId: string);
// GET flow_agent/{taskId}/task_node_info/{nodeId}/ → IFlowAgentTaskNodeInfo
```

### message HTTP 层补充方法

以下方法定义在 `http.message`（`chatHelper.http.message`）层，供上层封装调用：

| 方法 | 请求 | 说明 |
|------|------|------|
| `batchDeleteMessages(ids)` | POST `session_content/batch_delete/` `{ ids }` | 按 user message id 批量删除 |
| `retryFlowAgentTaskNode(sessionCode, nodeId, taskId)` | POST `flow_agent/{sessionCode}/node/{nodeId}/retry/` | 重试流程节点 |
| `skipFlowAgentTaskNode(sessionCode, nodeId, taskId)` | POST `flow_agent/{sessionCode}/node/{nodeId}/skip/` | 跳过流程节点 |
| `userOperation(sessionCode, operation, payload)` | POST `user_operation/` `{ session_code, operation, payload }` | HITL / flow 用户操作 |

> `message.deleteMessages` 底层即调用 `http.message.batchDeleteMessages`。flow 节点重试/跳过与审批取消建议通过 `agent.userOperationStreamRequest` 调用（会自动续聊/轮询）。

---

## HITL / 中断与恢复协议（interrupt & resume）

human-in-the-loop 用于**工具审批**（tool approval）与**向用户提问**（user question）两类场景。中断不是独立的事件类型，而是标准 `RUN_FINISHED` 事件的一种 **outcome**。

### 相关枚举

```typescript
// 运行完成结果类型
enum RunFinishedOutcomeType { Success = 'success', Interrupt = 'interrupt' }

// 中断原因
enum InterruptReason {
  AIDevToolApproval = 'aidev:tool_approval',  // 工具审批
  UserQuestion = 'aidev:user_question',       // 向用户提问
}

// 恢复状态
enum ResumeStatus { Resolved = 'resolved', Cancelled = 'cancelled' }

// 审批单状态
enum ApprovalInterruptTicketStatus {
  Abandoned = 'abandoned', Approved = 'approved', Cancelled = 'cancelled',
  Draft = 'draft', Expired = 'expired', Rejected = 'rejected', Pending = 'pending',
}

// 用户操作类型
enum UserOperation {
  FlowNodeRetry = 'flow_node_retry',
  FlowNodeSkip = 'flow_node_skip',
  ApprovalCancel = 'approval_cancel',
}
```

### 核心类型

```typescript
// 通用中断
interface IInterrupt<T extends InterruptReason, P extends Record<string, unknown>> {
  id: string;
  reason: T;
  message?: string;
  toolCallId?: string;
  responseSchema?: JSONSchema4;
  expiresAt?: string;
  metadata?: P;
}

// 工具审批中断
type IApprovalInterrupt = IInterrupt<
  InterruptReason.AIDevToolApproval,
  {
    ticket: {
      approvers: string[];
      sn: string;
      status: ApprovalInterruptTicketStatus;
      submit_time: string;
      title: string;
      url: string;
    };
  }
>;

// 向用户提问中断
type IUserQuestionInterrupt = IInterrupt<
  InterruptReason.UserQuestion,
  {
    questions: {
      header: string;
      multiSelect?: boolean;
      options?: { description: string; label: string }[];
      question: string;
    }[];
  }
>;

// 恢复载荷
interface IResume {
  interruptId: string;
  status: ResumeStatus;
  payload?: {
    answers: {
      answer: { description: string; label: string }[];
      multiSelect?: boolean;
      question: string;
    }[];
  };
}

// 运行完成 outcome
type IRunFinishedOutcome =
  | { type: RunFinishedOutcomeType.Success }
  | { type: RunFinishedOutcomeType.Interrupt; interrupts: Array<IApprovalInterrupt | IUserQuestionInterrupt> };

// RUN_FINISHED 事件（承载 outcome 与二次恢复 result）
interface IRunFinishedEvent extends IBaseEvent {
  result?: IResume;
  runId: number;
  threadId: string;
  type: EventType.RunFinished;
  outcome?: IRunFinishedOutcome;
}

// 中断消息（写入 message.list 的消息）
interface IInterruptMessage extends IBaseMessage {
  role: MessageRole.Interrupt;
  content: IRunFinishedEvent;
}

// 用户操作载荷
type IUserOperationPayload =
  | { node_id: string; task_id: string }
  | { interrupt_id: number | string };
```

### 中断流程

1. **中断到达**：流式过程中若 `RUN_FINISHED` 事件的 `outcome.type === Interrupt`，`AGUIProtocol.handleRunFinishedEvent` 会向 `message.list` 追加一条 `role: MessageRole.Interrupt`、`status: Pending` 的消息，`content` 即完整的 `IRunFinishedEvent`。
2. **中断解决（原地更新）**：后续 `handleToolCallResultEvent`（工具审批返回结果）或 `CustomEventName.ApprovalResult` 自定义事件会**原地更新**该中断消息 —— 设置 `content.result` / 将 `outcome.type` 改为 `Success` / 标记 `Complete`。

### 恢复流程

- **发送恢复**：所有恢复都通过 `agent.streamRequest` 发起，将 `resume` 写入 `chat_completion/` 的请求体 `execute_kwargs.resume`：
  ```typescript
  agent.streamRequest({
    sessionCode,
    resume: { interruptId, status: ResumeStatus.Resolved /* 或 Cancelled */, payload },
  });
  ```
- **审批轮询**：`agent.pollResumeSession(sessionCode)` 检测到待审批的中断消息（ticket 处于 `Pending`/`Draft`）后，轮询 `GET session/{code}/is_resume/`；返回 `true` 时自动以 `resume: { interruptId, status: Resolved }` 重新发起 `streamRequest`；返回 `false` 则 30s 后重试（会话切换后停止）。
- **用户操作**（flow 节点重试/跳过、审批取消）：`agent.userOperationStreamRequest(sessionCode, operation, payload)` → `POST user_operation/`；非 `ApprovalCancel` 操作会继续 `streamRequest`，`ApprovalCancel` 则清除长轮询并重新 `pollResumeSession`。

### 说明：无 `onInterruptResume`

> chat-helper **本身不提供** `onInterruptResume` 之类的 UI 级钩子。它只暴露原语：`streamRequest`（携带 `IResume`）、`userOperationStreamRequest`、`pollResumeSession`，以及 `IResume` / `IInterrupt` 等类型形状。中断卡片渲染、审批交互、`onInterruptResume` 回调等属于 **chat-x / ai-blueking** UI 层职责。

---

## AGUIProtocol 事件系统

### 生命周期钩子

```typescript
const protocol = new AGUIProtocol({
  onStart: () => { /* 流式开始 */ },
  onMessage: (event) => { /* 每个事件 */ },
  onDone: () => { /* 流式完成 */ },
  onError: (error) => { /* 发生错误 */ },
});
```

### 消息模块注入

原子组件模式（直接使用 chat-x + chat-helper，不通过 ChatBot/AIBlueking）时，必须手动注入消息模块：

```typescript
const protocol = new AGUIProtocol({ ... });
const chatHelper = useChatHelper({ ..., protocol });

// 必须调用！否则流式消息无法正确写入消息列表
protocol.injectMessageModule(chatHelper.message);
```

> ChatBot 独立模式内部已自动处理此步骤。AIBlueking 通过 useChatBootstrap 处理。

### 核心事件类型（EventType）

| 事件 | 说明 | 使用场景 |
|------|------|----------|
| `TextMessageStart/Content/Chunk/End` | 文本消息流式传输 | 实时显示 AI 回复 |
| `ThinkingStart/End`、`ThinkingTextMessageStart/Content/End` | 思考过程 | 显示推理步骤 |
| `ToolCallStart/Args/Chunk/Result/End` | 工具调用 | 展示工具执行 |
| `RunStarted / RunFinished / RunError` | 运行开始/结束/错误 | 生命周期、**HITL 中断**（见下）、错误处理 |
| `StepStarted / StepFinished` | 多步骤工作流 | 步骤追踪 |
| `StateSnapshot / StateDelta`、`ActivitySnapshot / ActivityDelta` | 状态 / 活动 | 状态与活动同步 |
| `MessagesSnapshot` | 消息快照 | 多端同步 |
| `Custom` | 自定义事件（见 CustomEventName） | flow-agent / 知识库 RAG / 审批结果等 |
| `Raw` | 透传底层原始事件 | 调试 |

> **消息角色映射**：
> - `ThinkingStart/ThinkingTextMessage*` → `MessageRole.Reasoning` 消息，其 `content` 为 `string[]`（每个思考块一个字符串），`duration` 在 `ThinkingEnd` 写入。
> - `RunFinished` 的 `outcome.type === Interrupt` → 追加 `MessageRole.Interrupt` 消息（详见 HITL 章节）。

### 自定义事件（CustomEventName）

`EventType.Custom` 事件按 `name` 分发（`handleCustomEvent`），多数用于驱动 `MessageRole.Activity` 活动消息。

```typescript
enum CustomEventName {
  FlowAgentStart = 'flow_agent_start',
  FlowAgentUpdate = 'flow_agent_update',
  FlowAgentResult = 'flow_agent_result',
  FlowAgentEnd = 'flow_agent_end',
  KnowledgeRagStart = 'knowledge_rag_start',
  KnowledgeRagTextContent = 'knowledge_rag_text_content',
  KnowledgeRagResult = 'knowledge_rag_result',
  KnowledgeRagEnd = 'knowledge_rag_end',
  ReferenceDocument = 'reference_document',
  TempMessage = 'temp_message',
  ApprovalResult = 'approval_result',   // HITL：审批结果，原地更新中断消息
}
```

| name 分组 | 驱动的消息 | 说明 |
|-----------|-----------|------|
| `FlowAgentStart/Update/Result/End` | `MessageRole.Activity`（`ActivityType.FlowAgent`） | 流程编排任务的开始/节点更新/结果/结束 |
| `KnowledgeRagStart/TextContent/Result/End` | `MessageRole.Activity`（`ActivityType.KnowledgeRag`） | 知识库 RAG 意图识别与召回 |
| `ReferenceDocument` | `MessageRole.Activity`（`ActivityType.ReferenceDocument`） | 参考文档 |
| `TempMessage` | `MessageRole.Assistant`（临时） | 临时提示消息 |
| `ApprovalResult` | 原地更新中断消息 | value 类型为 `IRunFinishedEvent` |

### 自定义 Protocol

```typescript
import { AGUIProtocol, type ITextMessageChunkEvent } from '@blueking/chat-helper';

class CustomProtocol extends AGUIProtocol {
  handleTextMessageChunkEvent(event: ITextMessageChunkEvent) {
    console.log('接收文本:', event.delta);
    super.handleTextMessageChunkEvent(event);
  }

  handleThinkingStartEvent(event) {
    showThinkingAnimation();
    super.handleThinkingStartEvent(event);
  }
}
```

---

## 配置模式

### 动态请求配置

```typescript
useChatHelper({
  requestData: {
    urlPrefix: '/api/',
    headers: () => ({
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      'X-Request-ID': crypto.randomUUID(),
    }),
    data: () => ({
      app_id: getCurrentAppId(),
      tenant_id: getTenantId(),
    }),
  },
});
```

### 请求/响应拦截器

```typescript
useChatHelper({
  requestData: { urlPrefix: '/api/' },
  interceptors: {
    request: (config) => {
      console.log('Request:', config.url);
      return config;
    },
    response: (response) => {
      if (response.data.code !== 0) {
        showError(response.data.message);
      }
      return response;
    },
  },
});
```

---

## 状态映射

### chat-helper → chat-x

| chat-helper 状态 | chat-x 状态 | 场景 |
|-----------------|-------------|------|
| `agent.isChatting = true` | `MessageStatus.Streaming` | 流式响应中 |
| `agent.isChatting = false` | `MessageStatus.Complete` | 响应完成 |
| `agent.isChatting = true` | `MessageToolsStatus.Disabled` | 流式响应时禁用工具栏 |

### 状态计算示例

```typescript
import { computed } from 'vue';
import { MessageStatus, MessageToolsStatus } from '@blueking/chat-x';

const messageStatus = computed(() =>
  agent.isChatting.value ? MessageStatus.Streaming : MessageStatus.Complete
);

const messageToolsStatus = computed(() =>
  messageStatus.value === MessageStatus.Streaming
    ? MessageToolsStatus.Disabled
    : undefined
);
```

---

## 最佳实践

### 1. 组件卸载时清理

```typescript
onBeforeUnmount(() => {
  agent.stopChat(session.current.value?.sessionCode ?? '');
});
```

### 2. 使用 chooseSession 切换会话

```typescript
// 推荐：自动停止聊天、加载消息
await session.chooseSession(sessionCode);

// 不推荐：手动操作
agent.stopChat(sessionCode);
session.current.value = ...;
message.getMessages(sessionCode);
```

### 3. 使用枚举而非字符串

```typescript
import { MessageStatus, MessageRole } from '@blueking/chat-helper';

// 推荐
if (msg.status === MessageStatus.Streaming) { }

// 不推荐
if (msg.status === 'streaming') { }
```

### 4. Protocol 钩子快速返回

```typescript
// 推荐：不阻塞
onMessage: (event) => {
  console.log(event);
  asyncOperation();  // 不 await
}

// 不推荐：阻塞
onMessage: async (event) => {
  await someAsyncOperation();
}
```
