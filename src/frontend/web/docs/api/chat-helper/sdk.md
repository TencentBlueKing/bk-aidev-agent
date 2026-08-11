# SDK 模块 (chat-helper)

`@blueking/chat-helper` 是 AI 小鲸的业务 SDK 层，提供与后端 API 通信、状态管理、流式协议处理等核心能力。

## useChatHelper()

SDK 的入口函数，创建并返回一个包含 Agent、Session、Message 三大模块的 chatHelper 实例。

### 参数

```typescript
function useChatHelper(options?: IUseChatHelperOptions): IChatHelper
```

| 参数      | 类型                    | 说明             |
| --------- | ----------------------- | ---------------- |
| `options` | `IUseChatHelperOptions` | 配置选项（可选） |

#### IUseChatHelperOptions

| 属性                    | 类型                                         | 说明                                             |
| ----------------------- | -------------------------------------------- | ------------------------------------------------ |
| `requestData`           | `{ urlPrefix, headers, data }`               | 请求配置                                         |
| `requestData.urlPrefix` | `string`                                     | API 地址前缀                                     |
| `requestData.headers`   | `MaybeRequestValue<Record<string, string>>`  | 自定义请求头（对象 / 函数 / `ref` / `computed`） |
| `requestData.data`      | `MaybeRequestValue<Record<string, unknown>>` | 附加数据（GET 等 → query，POST 等 → body）       |
| `protocol`              | `AGUIProtocol`                               | 自定义协议实例（可选）                           |
| `interceptors`          | `object`                                     | 请求/响应拦截器（可选）                          |

### 返回值

| 属性      | 类型            | 说明             |
| --------- | --------------- | ---------------- |
| `agent`   | `AgentModule`   | Agent 模块       |
| `session` | `SessionModule` | Session 模块     |
| `message` | `MessageModule` | Message 模块     |
| `http`    | `HttpClient`    | HTTP 客户端实例  |
| `reset`   | `() => void`    | 重置所有模块状态 |

### 基本用法

```typescript
import { useChatHelper } from "@blueking/chat-helper"

import { computed, ref } from "vue"

const token = ref(getToken())

const chatHelper = useChatHelper({
  requestData: {
    urlPrefix: "/api/ai",
    headers: computed(() => ({ Authorization: `Bearer ${token.value}` })),
    data: () => ({ app_id: "my-app" }),
  },
})

// 使用各模块
await chatHelper.agent.getAgentInfo()
await chatHelper.session.getSessions()
```

## Agent 模块

Agent 模块负责与 AI Agent 交互，包括获取 Agent 信息和发起聊天。

### 响应式属性

| 属性              | 类型                      | 说明                                 |
| ----------------- | ------------------------- | ------------------------------------ |
| `info`            | `Ref<IAgentInfo \| null>` | Agent 信息                           |
| `isInfoLoading`   | `Ref<boolean>`            | 是否正在加载 Agent 信息              |
| `isChatting`      | `Ref<boolean>`            | 是否正在聊天（流式响应中）           |
| `models`          | `Ref<ILlmItem[]>`         | 可用模型列表（`getLlms` 成功后写入） |
| `isModelsLoading` | `Ref<boolean>`            | 是否正在加载模型列表                 |

### 方法

| 方法                  | 类型                                                                      | 说明                                                                      |
| --------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| `getAgentInfo`        | `() => Promise<IAgentInfo>`                                               | 获取 Agent 信息                                                           |
| `getLlms`             | `(params?: ILlmListQuery, config?) => Promise<ILlmItem[]>`                | 获取可用模型列表（`GET llms/`，未传 `llm_type` 时默认 `chat.completion`） |
| `chat`                | `(input, sessionCode, url?, config?, property?, model?) => Promise<void>` | 发起聊天；`model` 为热切换 `llm_code`                                     |
| `stopChat`            | `(sessionCode: string) => void`                                           | 停止当前聊天                                                              |
| `resumeStreamingChat` | `(sessionCode: string, url?, config?, model?) => Promise<void>`           | 恢复流式聊天                                                              |
| `resendMessage`       | `(id, sessionCode, content?, url?, config?) => Promise<void>`             | 重发消息                                                                  |

### 用法示例

```typescript
const { agent } = chatHelper

// 获取 Agent 信息
const info = await agent.getAgentInfo()
console.log("Agent 名称:", info.agentName)

// 拉取可用模型
const llmList = await agent.getLlms({ llm_type: "chat.completion" })
// agent.models 同步更新

// 发起聊天
await agent.chat("帮我写一个快速排序", "session-123")

// 模型热切换：第 6 个参数为 llm_code（须在 GET llms/ 列表内）
await agent.chat("换个模型再答", "session-123", undefined, undefined, undefined, "hy3-preview")

// 自定义请求参数（如 temperature）走 config.data，不要把 model 塞进 data
await agent.chat("创意回答", "session-123", undefined, {
  data: { temperature: 0.8 },
})

// 监听聊天状态
watch(agent.isChatting, (chatting) => {
  console.log(chatting ? "正在回复..." : "回复完成")
})

// 停止聊天
agent.stopChat("session-123")

// 重发消息
await agent.resendMessage("msg-456", "session-123")
```

## Session 模块

Session 模块管理会话的完整生命周期。

### 响应式属性

| 属性                   | 类型                    | 说明                 |
| ---------------------- | ----------------------- | -------------------- |
| `list`                 | `Ref<ISession[]>`       | 会话列表             |
| `current`              | `Ref<ISession \| null>` | 当前会话             |
| `isListLoading`        | `Ref<boolean>`          | 是否正在加载会话列表 |
| `isDeleteLoading`      | `Ref<boolean>`          | 是否正在删除会话     |
| `isBatchDeleteLoading` | `Ref<boolean>`          | 是否正在批量删除     |

### 方法

| 方法                        | 类型                                                          | 说明             |
| --------------------------- | ------------------------------------------------------------- | ---------------- |
| `getSessions`               | `() => Promise<ISession[]>`                                   | 获取会话列表     |
| `chooseSession`             | `(code: string, options?) => Promise<void>`                   | 选择并切换会话   |
| `createSession`             | `(session: Partial<ISession>, options?) => Promise<ISession>` | 创建新会话       |
| `updateSession`             | `(session: Partial<ISession>) => Promise<void>`               | 更新会话信息     |
| `deleteSession`             | `(code: string) => Promise<void>`                             | 删除会话         |
| `batchDeleteSessions`       | `(codes: string[]) => Promise<void>`                          | 批量删除会话     |
| `renameSession`             | `(code: string) => Promise<void>`                             | 重命名会话       |
| `getSessionFeedbackReasons` | `(rate: string) => Promise<string[]>`                         | 获取反馈原因列表 |
| `postSessionFeedback`       | `(params: object) => Promise<void>`                           | 提交反馈         |
| `uploadFile`                | `(code: string, file: File) => Promise<void>`                 | 上传文件到会话   |

### 用法示例

```typescript
const { session } = chatHelper

// 获取会话列表
const sessions = await session.getSessions()

// 创建新会话
const newSession = await session.createSession({
  sessionName: "新对话",
})

// 切换会话
await session.chooseSession("session-abc-123")

// 删除会话
await session.deleteSession("session-abc-123")

// 重命名
await session.renameSession("session-abc-123")
```

## Message 模块

Message 模块管理当前会话的消息列表。

### 响应式属性

| 属性              | 类型              | 说明                 |
| ----------------- | ----------------- | -------------------- |
| `list`            | `Ref<IMessage[]>` | 消息列表             |
| `isListLoading`   | `Ref<boolean>`    | 是否正在加载消息列表 |
| `isDeleteLoading` | `Ref<boolean>`    | 是否正在删除消息     |

### 方法

| 方法                       | 类型                                                        | 说明                   |
| -------------------------- | ----------------------------------------------------------- | ---------------------- |
| `getMessages`              | `(code: string) => Promise<IMessage[]>`                     | 获取指定会话的消息列表 |
| `plusMessage`              | `(msg: IMessage) => void`                                   | 添加消息到列表         |
| `createAndPlusMessage`     | `(msg: Partial<IMessage>) => IMessage`                      | 创建消息并添加到列表   |
| `modifyMessage`            | `(msg: Partial<IMessage>) => void`                          | 修改消息               |
| `deleteMessages`           | `(msgs: IMessage[]) => Promise<void>`                       | 删除消息               |
| `shareMessages`            | `(code, msgs, expiredAt?) => Promise<{ shareUrl: string }>` | 分享消息               |
| `getCurrentLoadingMessage` | `() => IMessage \| undefined`                               | 获取当前正在加载的消息 |
| `getMessageByMessageId`    | `(id: string) => IMessage \| undefined`                     | 根据 ID 获取消息       |

### HTTP 层 `http.message.getMessages`

业务层 `message.getMessages` 仅接收 `sessionCode`。若需要 `limit` / `fuzzy` 等查询参数，请直接使用 HTTP 层：

```typescript
// (sessionCode, limit?, config?, fuzzy?) => Promise<IMessage[]>
// GET session_content/content/ — fuzzy 置于末尾，不影响既有 limit/config 调用
const { http } = chatHelper
const filtered = await http.message.getMessages("session-123", undefined, undefined, "关键词")
```

### 用法示例

```typescript
const { message } = chatHelper

// 获取消息列表
const messages = await message.getMessages("session-123")

// 手动添加消息
message.plusMessage({
  id: "msg-1",
  role: "user",
  content: "你好",
})

// 删除消息
await message.deleteMessages([targetMessage])

// 分享消息
const { shareUrl } = await message.shareMessages("session-123", selectedMessages)
```

## AGUIProtocol

AG-UI 协议处理器，负责解析流式响应中的事件并将其转换为消息更新。

### FetchClient 全局错误处理（≥ v2.1.4-beta.25）

`FetchClient` 新增 `onError` 方法，可注册全局错误处理器，所有 HTTP 错误（普通请求与 SSE 流）均经过统一分发：

```typescript
import { useChatHelper } from "@blueking/chat-helper"

const chatHelper = useChatHelper({
  requestData: { urlPrefix: "/api/ai" },
})

// 注册全局错误处理器
chatHelper.http.onError(
  (error) => {
    console.error("HTTP 错误:", error.message)
    // 可用于日志上报、自定义 toast 等
  },
  {
    // 忽略特定 URL 模式的错误（可选）
    ignoreErrors: ["/api/health", /session\/upload/],
  },
)
```

| 参数                   | 类型                             | 说明                                    |
| ---------------------- | -------------------------------- | --------------------------------------- |
| `handler`              | `(error: IRequestError) => void` | 错误处理器                              |
| `options.ignoreErrors` | `Array<string \| RegExp>`        | 忽略的 URL 模式（字符串包含匹配或正则） |

### 构造函数钩子

```typescript
const protocol = new AGUIProtocol({
  onStart: () => void,
  onMessage: (event: AGUIEvent) => void,
  onDone: () => void,
  onError: (error: Error) => void,
});
```

| 钩子        | 说明               |
| ----------- | ------------------ |
| `onStart`   | 流式连接建立时触发 |
| `onMessage` | 收到每个事件时触发 |
| `onDone`    | 流式传输完成时触发 |
| `onError`   | 发生错误时触发     |

### 注入消息模块

```typescript
protocol.injectMessageModule(messageModule)
```

> **重要**：在原子模式下使用 AGUIProtocol 时，必须调用 `injectMessageModule` 注入 Message 模块，否则协议处理器无法更新消息列表。

### AG-UI 事件类型

| 事件类型           | 说明                         |
| ------------------ | ---------------------------- |
| `TextMessageStart` | 文本消息开始                 |
| `TextMessageChunk` | 文本消息分块（流式文本片段） |
| `TextMessageEnd`   | 文本消息结束                 |
| `ThinkingStart`    | 思考/推理开始                |
| `ThinkingEnd`      | 思考/推理结束                |
| `ToolCallStart`    | 工具调用开始                 |
| `ToolCallArgs`     | 工具调用参数                 |
| `ToolCallResult`   | 工具调用结果                 |
| `ToolCallEnd`      | 工具调用结束                 |
| `RunError`         | 运行错误                     |
| `MessagesSnapshot` | 消息快照（全量消息同步）     |

### 自定义协议扩展

你可以继承 `AGUIProtocol` 来实现自定义的协议处理逻辑：

```typescript
import { AGUIProtocol } from "@blueking/chat-helper"

class MyProtocol extends AGUIProtocol {
  constructor() {
    super({
      onStart: () => {
        console.log("流式开始")
      },
      onMessage: (event) => {
        // 自定义事件处理
        if (event.type === "TextMessageChunk") {
          this.handleTextChunk(event)
        }
      },
      onDone: () => {
        console.log("流式结束")
      },
      onError: (error) => {
        console.error("流式错误:", error)
      },
    })
  }

  handleTextChunk(event) {
    // 自定义文本块处理逻辑
  }
}

// 使用自定义协议
const chatHelper = useChatHelper({
  requestData: { urlPrefix: "/api/ai" },
  protocol: new MyProtocol(),
})
```

## 状态映射

`chat-helper` 的状态可以映射为 `chat-x` UI 组件所需的状态值：

| chat-helper 状态             | chat-x 状态               | 说明       |
| ---------------------------- | ------------------------- | ---------- |
| `agent.isChatting === true`  | `MessageStatus.Streaming` | 流式输出中 |
| `agent.isChatting === false` | `MessageStatus.Complete`  | 输出完成   |
| 聊天出错                     | `MessageStatus.Error`     | 发生错误   |
| 用户停止生成                 | `MessageStatus.Stop`      | 已停止     |

### 映射示例

```typescript
import { computed } from "vue"
import { useChatHelper } from "@blueking/chat-helper"
import { MessageStatus } from "@blueking/chat-x"

const chatHelper = useChatHelper({ requestData: { urlPrefix: "/api/ai" } })

const messageStatus = computed(() => {
  if (chatHelper.agent.isChatting.value) {
    return MessageStatus.Streaming
  }
  return MessageStatus.Complete
})
```

将该 `messageStatus` 传入 `ChatInput` 和 `MessageContainer` 组件即可实现状态联动。
