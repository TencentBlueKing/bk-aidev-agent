# @blueking/chat-helper SDK API 参考

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
    headers: () => ({
      Authorization: `Bearer ${getToken()}`,
    }),
    data: () => ({
      app_id: 'your-app-id',
    }),
  },
  protocol,
});

// 原子组件模式必须：注入消息模块到 protocol
protocol.injectMessageModule(chatHelper.message);

// 解构模块
const { agent, session, message, http } = chatHelper;
```

---

## 核心架构

`chat-helper` 采用**中介者模式**协调模块通信：

| 模块 | 职责 | 响应式数据 |
|------|------|-----------|
| agent | AI 代理管理、聊天发送 | `info`, `isInfoLoading`, `isChatting` |
| session | 会话 CRUD、切换、反馈 | `list`, `current`, `isXxxLoading` |
| message | 消息 CRUD、状态管理 | `list`, `isListLoading` |
| http | 底层 HTTP 请求 | - |

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
// 上传支持（vision 模式）
const supportUpload = agent.info.value?.promptSetting?.supportUpload?.vision;
// 单个 command 的上传支持
const commandUpload = commands?.[0]?.supportUpload?.vision;
```

#### chat

发送消息。

```typescript
await agent.chat(
  userInput: string | IUserMessage['content'],  // 支持文本或多模态内容
  sessionCode: string,
  url?: string,       // 自定义 chat 端点
  config?: RequestConfig
);

// 带额外参数
await agent.chat(userInput, sessionCode, undefined, {
  data: {
    property: { extra: { cite: '引用内容' } },
  },
});
```

#### stopChat

停止当前聊天。

```typescript
agent.stopChat(sessionCode: string);  // 需传入 sessionCode
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

### ISession 接口

```typescript
interface ISession {
  sessionCode: string;
  sessionName: string;
  sessionContentCount?: number;
  createdAt?: string;
  updatedAt?: string;
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
  expiredAt?: string
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

### 核心事件类型

| 事件 | 说明 | 使用场景 |
|------|------|----------|
| `TextMessageStart/Chunk/End` | 文本消息流式传输 | 实时显示 AI 回复 |
| `ThinkingStart/End` | 思考过程 | 显示推理步骤 |
| `ToolCallStart/Args/Result/End` | 工具调用 | 展示工具执行 |
| `RunError` | 运行错误 | 错误处理 |
| `MessagesSnapshot` | 消息快照 | 多端同步 |

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
