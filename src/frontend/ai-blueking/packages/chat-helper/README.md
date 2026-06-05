# @blueking/chat-helper

一个用于 Vue3 的聊天助手工具包，提供完整的 AI 对话功能，支持流式响应、会话管理、消息管理等功能。

## 特性

- 🚀 **Vue3 Composition API**：基于 Vue3 的响应式系统，提供流畅的开发体验
- 💬 **完整的会话管理**：支持多会话创建、切换、更新和删除
- 📨 **消息管理**：支持消息列表、添加、修改、删除和批量操作
- 🤖 **AI Agent 集成**：轻松接入 AI 代理，获取代理信息和进行对话
- 🌊 **流式响应**：支持 SSE（Server-Sent Events）流式响应，实时展示 AI 回复
- 🎯 **中介者模式**：模块间通过中介者协调通信，降低耦合度
- 🔧 **高度可定制**：支持自定义拦截器、自定义 Protocol、自定义请求配置
- 📝 **TypeScript 支持**：完整的类型定义，提供良好的类型提示

## 安装

```bash
npm install @blueking/chat-helper
```

## 快速开始

```typescript
import { useChatHelper } from '@blueking/chat-helper';

// 在 Vue 组件中使用
const chatHelper = useChatHelper({
  requestData: {
    urlPrefix: 'https://your-api-domain.com/api/',
    headers: {
      Authorization: 'Bearer your-token',
    },
  },
});

// 解构返回的模块
const { agent, session, message, http } = chatHelper;
```

## 架构设计

`@blueking/chat-helper` 采用**中介者模式（Mediator Pattern）**进行架构设计，将复杂的模块间通信集中到中介者对象中，降低了各模块之间的耦合度。

### 核心模块

- **Agent 模块**：管理 AI 代理相关功能，包括获取代理信息、开始聊天、停止聊天等
- **Session 模块**：管理聊天会话，包括会话列表、创建、切换、更新和删除
- **Message 模块**：管理聊天消息，包括消息列表、添加、修改和删除
- **HTTP 模块**：底层 HTTP 请求封装，提供各种 API 调用方法和 SSE 流式响应支持
- **Mediator 模块**：中介者，协调各模块之间的通信，避免模块间直接依赖

### 数据流向

```
用户操作 → Agent/Session/Message 模块 → Mediator → HTTP 模块 → 后端 API
                    ↑                                            ↓
                    ←────────── 响应数据/流式事件 ←─────────────
```

### Protocol 系统

`@blueking/chat-helper` 提供了可扩展的 Protocol 系统来处理 SSE 流式响应：

- **ISSEProtocol 接口**：定义了流式响应的处理接口
- **AGUIProtocol 实现**：默认的 AGUI 协议实现，支持丰富的事件类型
- **自定义 Protocol**：用户可以实现自己的 Protocol 来处理特定的流式响应格式

## useChatHelper 返回数据说明

`useChatHelper` 返回一个包含四个模块的对象：

### 1. agent - 代理模块

管理 AI 代理相关功能。

```typescript
const { agent } = chatHelper;

// 响应式数据
agent.info; // Ref<IAgentInfo | null> - agent 信息
agent.isInfoLoading; // Ref<boolean> - agent 信息加载状态

// 方法
agent.getAgentInfo(); // () => Promise<void> - 获取 agent 信息
agent.chat(userInput, sessionCode, url?, config?); // (userInput: string, sessionCode: string, url?: string, config?: IRequestConfig) => Promise<void> - 开始聊天（流式响应）
agent.stopChat(); // () => Promise<void> - 停止聊天
```

**参数说明**：

- `userInput`: 用户输入的消息内容，必需参数
- `sessionCode`: 会话代码，必需参数，标识当前聊天会话
- `url`: 可选参数，自定义聊天接口地址，默认为 `'chat_completion/'`
- `config`: 可选参数，额外的请求配置（如自定义 headers、data 等）

**使用示例**：

```vue
<template>
  <div>
    <div v-if="agent.isInfoLoading">加载中...</div>
    <div v-else-if="agent.info">
      <h2>{{ agent.info.agentName }}</h2>
      <p>{{ agent.info.conversationSettings?.openingRemark }}</p>
    </div>
    <input
      v-model="userInput"
      placeholder="请输入消息..."
    />
    <button @click="startChat">开始对话</button>
    <button @click="agent.stopChat">停止对话</button>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { useChatHelper } from '@blueking/chat-helper';

  const { agent, session } = useChatHelper({
    /* ... */
  });

  const userInput = ref('');

  onMounted(() => {
    agent.getAgentInfo();
  });

  const startChat = () => {
    if (session.current?.sessionCode && userInput.value.trim()) {
      agent.chat(userInput.value, session.current.sessionCode);
      userInput.value = ''; // 清空输入框
    }
  };
</script>
```

**高级用法 - 自定义请求配置**：

```typescript
// 使用自定义 URL
agent.chat('你好', sessionCode, 'custom_chat_endpoint/');

// 使用自定义请求配置
agent.chat('你好', sessionCode, undefined, {
  headers: {
    'X-Custom-Header': 'value',
  },
  data: {
    temperature: 0.7,
    max_tokens: 1000,
  },
});

// 同时使用自定义 URL 和配置
agent.chat('你好', sessionCode, 'custom_chat_endpoint/', {
  headers: {
    'X-Custom-Header': 'value',
  },
});
```

### 2. session - 会话模块

管理聊天会话的创建、切换、更新和删除。

```typescript
const { session } = chatHelper;

// 响应式数据
session.list; // Ref<ISession[]> - 会话列表
session.current; // Ref<ISession | null> - 当前会话
session.isListLoading; // Ref<boolean> - 列表加载状态
session.isCurrentLoading; // Ref<boolean> - 当前会话加载状态
session.isCreateLoading; // Ref<boolean> - 创建会话加载状态
session.isUpdateLoading; // Ref<boolean> - 更新会话加载状态
session.isDeleteLoading; // Ref<boolean> - 删除会话加载状态

// 方法
session.getSessions(); // () => Promise<void> - 获取会话列表
session.chooseSession(sessionCode); // (sessionCode: string) => Promise<void> - 选择会话
session.getSession(sessionCode); // (sessionCode: string) => Promise<void> - 获取单个会话
session.createSession(session); // (session: ISession) => Promise<void> - 创建会话
session.updateSession(session); // (session: ISession) => Promise<void> - 更新会话
session.deleteSession(sessionCode); // (sessionCode: string) => Promise<void> - 删除会话
```

**使用示例**：

```vue
<template>
  <div>
    <ul v-if="!session.isListLoading">
      <li
        v-for="item in session.list"
        :key="item.sessionCode"
        @click="session.chooseSession(item.sessionCode)"
        :class="{ active: session.current?.sessionCode === item.sessionCode }"
      >
        {{ item.sessionName }}
      </li>
    </ul>
    <button @click="createNewSession">新建会话</button>
  </div>
</template>

<script setup lang="ts">
  import { onMounted } from 'vue';
  import { useChatHelper } from '@blueking/chat-helper';

  const { session } = useChatHelper({
    /* ... */
  });

  onMounted(() => {
    session.getSessions();
  });

  const createNewSession = () => {
    session.createSession({
      sessionName: '新会话',
      sessionCode: `session_${Date.now()}`,
      // ... 其他会话属性
    });
  };
</script>
```

### 3. message - 消息模块

管理聊天消息的获取、添加、修改和删除。

```typescript
const { message } = chatHelper;

// 响应式数据
message.list; // Ref<IMessage[]> - 消息列表
message.isListLoading; // Ref<boolean> - 列表加载状态
message.isDeleteLoading; // Ref<boolean> - 删除加载状态
message.isBatchDeleteLoading; // Ref<boolean> - 批量删除加载状态

// 方法
message.getMessages(sessionCode); // (sessionCode: string) => Promise<void> - 获取消息列表
message.plusMessage(message); // (message: IMessage) => Promise<void> - 添加消息
message.modifyMessage(message); // (message: IMessage) => void - 修改消息
message.deleteMessage(id); // (id: string) => Promise<void> - 删除消息
message.batchDeleteMessages(ids); // (ids: string[]) => Promise<void> - 批量删除消息
message.getCurrentLoadingMessage(); // () => IMessage | undefined - 获取当前加载中的消息
message.getMessageByMessageId(id); // (id: string) => IMessage | undefined - 根据消息 ID 获取消息
```

**方法说明**：

- `getMessages`: 获取指定会话的所有消息列表
- `plusMessage`: 主动添加一条新消息到列表（会先调用后端接口创建消息，然后添加到列表最前面）
- `modifyMessage`: 修改已存在的消息（本地更新，不调用接口）
- `deleteMessage`: 删除单条消息（调用接口删除并从列表中移除）
- `batchDeleteMessages`: 批量删除多条消息（调用接口批量删除并从列表中移除）
- `getCurrentLoadingMessage`: 获取当前正在加载/流式传输中的 AI 响应消息（状态为 Pending 或 Streaming）
- `getMessageByMessageId`: 根据消息 ID 从列表中查找消息

**使用示例**：

```vue
<template>
  <div class="message-list">
    <div
      v-for="msg in message.list"
      :key="msg.messageId"
      class="message-item"
    >
      <div class="role">{{ msg.role }}</div>
      <div class="content">
        <!-- 根据消息类型显示不同内容 -->
        <div v-if="msg.role === 'user'">
          {{ typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content) }}
        </div>
        <div v-else-if="msg.role === 'assistant'">
          {{ msg.content || '' }}
        </div>
      </div>
      <button @click="message.deleteMessage(msg.messageId)">删除</button>
    </div>
    <button
      @click="batchDelete"
      :disabled="message.isBatchDeleteLoading"
    >
      批量删除选中消息
    </button>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useChatHelper } from '@blueking/chat-helper';

  const { message } = useChatHelper({
    /* ... */
  });

  const selectedIds = ref<string[]>([]);

  const batchDelete = () => {
    if (selectedIds.value.length > 0) {
      message.batchDeleteMessages(selectedIds.value);
    }
  };
</script>
```

### 4. http - HTTP 模块

底层 HTTP 请求模块，提供各种 API 调用方法。

```typescript
const { http } = chatHelper;

// 包含以下子模块：
http.agent; // Agent API
http.session; // Session API
http.message; // Message API
```

一般情况下，您不需要直接使用 `http` 模块，因为 `agent`、`session` 和 `message` 模块已经封装了常用的业务逻辑。

## 配置选项

### requestData（必需）

配置 HTTP 请求的基础信息。

```typescript
useChatHelper({
  requestData: {
    // API 基础路径（必需）
    urlPrefix: 'https://your-api-domain.com/api/',

    // 额外的请求数据（可选）
    data: {
      appId: 'your-app-id',
      version: '1.0.0',
    },
    // 或者使用函数动态返回
    data: () => ({
      appId: getAppId(),
      timestamp: Date.now(),
    }),

    // 额外的请求头（可选）
    headers: {
      Authorization: 'Bearer your-token',
      'X-Custom-Header': 'value',
    },
    // 或者使用函数动态返回
    headers: () => ({
      Authorization: `Bearer ${getToken()}`,
      'X-Request-ID': generateRequestId(),
    }),

    // 也支持 Vue ref / computed（每次请求读取最新值）
    // headers: computed(() => ({ Authorization: `Bearer ${token.value}` })),
    // data: ref({ app_id: currentAppId.value }),
  },
});
```

**响应式写法说明**：

- `headers` / `data` 支持：普通对象、零参函数、`ref`、`computed`，以及「函数返回 ref/computed」。
- 每次发起 HTTP 请求前都会重新解析，修改 `.value` 或替换外层 ref 后，后续请求自动使用新值。
- `data` 对 POST/PUT/PATCH/DELETE 合并进请求体；对 GET/HEAD/OPTIONS 合并进 query（`params`），不会写入 body。

### interceptors（可选）

配置请求和响应拦截器，用于统一处理请求和响应。

```typescript
useChatHelper({
  requestData: {
    /* ... */
  },
  interceptors: {
    // 请求拦截器
    request: config => {
      // 在发送请求之前做些什么
      console.log('Request:', config);

      // 添加自定义请求头
      config.headers = {
        ...config.headers,
        'X-Request-Time': new Date().toISOString(),
      };

      // 必须返回 config
      return config;
    },

    // 响应拦截器
    response: response => {
      // 对响应数据做些什么
      console.log('IResponse:', response);

      // 可以在这里做统一的错误处理
      if (response.data.code !== 0) {
        console.error('API Error:', response.data.message);
      }

      // 必须返回 response
      return response;
    },
  },
});
```

**拦截器使用场景**：

1. **请求拦截器**：

   - 添加认证 token
   - 添加请求时间戳
   - 添加请求 ID
   - 记录请求日志
   - 请求参数加密

2. **响应拦截器**：
   - 统一错误处理
   - 响应数据解密
   - 数据格式转换
   - 记录响应日志
   - 刷新 token

### protocol（可选）

自定义 SSE（Server-Sent Events）协议处理器，用于处理流式响应。

#### 使用默认 protocol

如果不提供 `protocol` 配置，系统会使用默认的 `AGUIProtocol`：

```typescript
useChatHelper({
  requestData: {
    /* ... */
  },
  // 不配置 protocol，使用默认的 AGUIProtocol
});
```

#### 使用 protocol 钩子函数

`AGUIProtocol` 提供了四个生命周期钩子函数，您可以在创建 protocol 实例时传入：

```typescript
import { useChatHelper, AGUIProtocol } from '@blueking/chat-helper';

const { agent } = useChatHelper({
  requestData: {
    urlPrefix: 'https://your-api-domain.com/api/',
  },
  protocol: new AGUIProtocol({
    // 流式响应开始时调用
    onStart: () => {
      console.log('开始接收流式响应');
      // 显示加载动画
      // 禁用发送按钮
    },
    // 每次接收到事件时调用
    onMessage: event => {
      console.log('接收到事件:', event);
      // 记录事件日志
      // 更新进度条
      // 触发自定义事件
    },
    // 流式响应完成时调用
    onDone: () => {
      console.log('流式响应完成');
      // 隐藏加载动画
      // 启用发送按钮
      // 播放完成提示音
    },
    // 发生错误时调用
    onError: error => {
      console.error('流式响应错误:', error);
      // 显示错误提示
      // 恢复 UI 状态
      // 上报错误日志
    },
  }),
});
```

**钩子函数使用场景**：

- **onStart**：显示加载状态、禁用输入框、重置 UI 状态
- **onMessage**：记录事件日志、更新进度、触发自定义事件、实时分析数据
- **onDone**：隐藏加载状态、启用输入框、播放提示音、保存会话历史
- **onError**：显示错误提示、恢复 UI 状态、上报错误、重试逻辑

#### 自定义 protocol

如果您需要自定义流式响应的处理逻辑，可以实现 `ISSEProtocol` 接口：

```typescript
import { useChatHelper, type ISSEProtocol, type IMessageModule } from '@blueking/chat-helper';

class CustomProtocol implements ISSEProtocol {
  private messageModule: IMessageModule;

  constructor({ message }: { message: IMessageModule }) {
    this.messageModule = message;
  }

  onStart() {
    console.log('Stream started');
    // 在流式响应开始时执行
  }

  onMessage(event: unknown) {
    console.log('Received event:', event);
    // 处理每个 SSE 事件
    // 您可以根据事件类型更新消息列表
    this.messageModule.plusMessage(/* ... */);
  }

  onDone() {
    console.log('Stream completed');
    // 在流式响应完成时执行
  }

  onError(error: Error) {
    console.error('Stream error:', error);
    // 处理错误
  }
}

// 使用自定义 protocol
const { agent, message } = useChatHelper({
  requestData: {
    /* ... */
  },
  protocol: new CustomProtocol({ message }),
});
```

#### 扩展默认 protocol - 重写事件处理钩子

`AGUIProtocol` 为每种事件类型都提供了对应的处理方法（钩子），您可以继承并重写这些方法来自定义行为：

```typescript
import {
  AGUIProtocol,
  type ITextMessageChunkEvent,
  type IRunErrorEvent,
  type IThinkingStartEvent,
  type IToolCallStartEvent,
} from '@blueking/chat-helper';

class MyCustomProtocol extends AGUIProtocol {
  // 重写文本消息流式处理
  handleTextMessageChunkEvent(event: ITextMessageChunkEvent) {
    // 自定义处理逻辑
    console.log('接收到文本块:', event.delta);

    // 调用父类方法（保留默认行为）
    super.handleTextMessageChunkEvent(event);

    // 额外的自定义逻辑
    // 例如：实时语音播报、敏感词过滤等
    if (event.delta.includes('重要')) {
      this.highlightImportantContent(event.messageId);
    }
  }

  // 重写思考开始事件
  handleThinkingStartEvent(event: IThinkingStartEvent) {
    console.log('AI 开始思考:', event.title);

    // 显示思考动画
    this.showThinkingAnimation();

    // 调用父类方法
    super.handleThinkingStartEvent(event);
  }

  // 重写工具调用开始事件
  handleToolCallStartEvent(event: IToolCallStartEvent) {
    console.log('调用工具:', event.toolCallName);

    // 显示工具调用提示
    this.showToolCallNotification(event.toolCallName);

    // 调用父类方法
    super.handleToolCallStartEvent(event);
  }

  // 重写错误处理
  handleRunErrorEvent(event: IRunErrorEvent) {
    console.error('运行错误:', event.message);

    // 自定义错误提示
    this.showCustomErrorMessage(event.message);

    // 上报错误
    this.reportError(event);

    // 调用父类方法
    super.handleRunErrorEvent(event);
  }

  // 自定义辅助方法
  private highlightImportantContent(messageId: string) {
    // 高亮重要内容
  }

  private showThinkingAnimation() {
    // 显示思考动画
  }

  private showToolCallNotification(toolName: string) {
    // 显示工具调用通知
  }

  private showCustomErrorMessage(message: string) {
    // 显示自定义错误消息
  }

  private reportError(event: IRunErrorEvent) {
    // 上报错误到监控系统
  }
}

const { agent } = useChatHelper({
  requestData: {
    /* ... */
  },
  protocol: new MyCustomProtocol({
    onStart: () => console.log('开始对话'),
    onDone: () => console.log('对话完成'),
  }),
});
```

**常用的事件处理钩子**：

| 钩子方法                                | 说明               | 使用场景               |
| --------------------------------------- | ------------------ | ---------------------- |
| `handleRunStartedEvent`                 | 运行开始           | 创建新消息、初始化状态 |
| `handleRunFinishedEvent`                | 运行完成           | 更新消息状态、保存历史 |
| `handleRunErrorEvent`                   | 运行错误           | 错误提示、状态恢复     |
| `handleTextMessageStartEvent`           | 文本消息开始       | 准备文本容器           |
| `handleTextMessageChunkEvent`           | 文本消息块（流式） | 实时显示文本、语音播报 |
| `handleTextMessageEndEvent`             | 文本消息结束       | 完成文本渲染           |
| `handleThinkingStartEvent`              | 思考开始           | 显示思考动画           |
| `handleThinkingTextMessageContentEvent` | 思考内容           | 显示思考过程           |
| `handleThinkingEndEvent`                | 思考结束           | 隐藏思考动画、统计时间 |
| `handleToolCallStartEvent`              | 工具调用开始       | 显示工具调用提示       |
| `handleToolCallArgsEvent`               | 工具参数           | 显示调用参数           |
| `handleToolCallResultEvent`             | 工具结果           | 显示调用结果           |
| `handleToolCallEndEvent`                | 工具调用结束       | 完成工具调用展示       |
| `handleMessagesSnapshotEvent`           | 消息快照           | 同步多端消息状态       |
| `handleActivityDeltaEvent`              | 活动增量更新       | 实时更新活动状态       |
| `handleActivitySnapshotEvent`           | 活动快照           | 获取完整活动状态       |
| `handleStateDeltaEvent`                 | 状态增量更新       | 实时更新状态           |
| `handleStateSnapshotEvent`              | 状态快照           | 获取完整状态状态       |
| `handleStepFinishedEvent`               | 步骤完成           | 完成步骤任务           |
| `handleStepStartedEvent`                | 步骤开始           | 开始步骤任务           |
| `handleCustomEvent`                     | 自定义事件         | 自定义事件处理         |
| `handleRawEvent`                        | 原始事件           | 原始事件处理           |
| `handleReferenceDocumentCustomEvent`    | 参考文档自定义事件 | 参考文档自定义事件处理 |

**实际应用示例**：

```typescript
class EnhancedProtocol extends AGUIProtocol {
  private audioPlayer: AudioPlayer;
  private analytics: Analytics;

  constructor(options) {
    super(options);
    this.audioPlayer = new AudioPlayer();
    this.analytics = new Analytics();
  }

  // 实时语音播报
  handleTextMessageChunkEvent(event: ITextMessageChunkEvent) {
    super.handleTextMessageChunkEvent(event);

    // 将文本转换为语音播放
    if (this.audioPlayer.isEnabled()) {
      this.audioPlayer.speak(event.delta);
    }
  }

  // 统计思考时间
  handleThinkingEndEvent(event: IThinkingEndEvent) {
    super.handleThinkingEndEvent(event);

    // 记录思考时长用于分析
    this.analytics.trackThinkingTime(event.timestamp);
  }

  // 工具调用监控
  handleToolCallStartEvent(event: IToolCallStartEvent) {
    super.handleToolCallStartEvent(event);

    // 记录工具使用情况
    this.analytics.trackToolUsage(event.toolCallName);

    // 显示工具调用进度
    showNotification(`正在调用工具: ${event.toolCallName}`);
  }
}
```

**钩子函数最佳实践**：

1. **始终调用父类方法**：重写钩子时，记得调用 `super.handleXxxEvent(event)` 以保留默认行为
2. **避免阻塞操作**：钩子函数应该快速执行，避免长时间运行的同步操作
3. **错误处理**：在钩子中添加 try-catch，避免错误影响整体流程
4. **按需重写**：只重写需要自定义的钩子，不需要重写所有方法
5. **类型安全**：使用 TypeScript 类型定义，确保事件参数类型正确

```typescript
class SafeProtocol extends AGUIProtocol {
  handleTextMessageChunkEvent(event: ITextMessageChunkEvent) {
    try {
      // 自定义逻辑
      this.customLogic(event);

      // 调用父类方法
      super.handleTextMessageChunkEvent(event);
    } catch (error) {
      console.error('处理文本消息块时出错:', error);
      // 即使出错也要调用父类方法，保证基本功能
      super.handleTextMessageChunkEvent(event);
    }
  }

  private customLogic(event: ITextMessageChunkEvent) {
    // 您的自定义逻辑
  }
}
```

**AGUIProtocol 支持的所有事件类型**：

<details>
<summary>点击展开完整事件列表</summary>

**运行相关事件**：

- `RunStarted` - 运行开始，创建新的 AI 响应消息
- `RunFinished` - 运行完成，标记消息为完成状态
- `RunError` - 运行错误，显示错误信息

**文本消息事件**：

- `TextMessageStart` - 文本消息开始，创建文本内容容器
- `TextMessageChunk` - 文本消息块，流式接收文本内容（最常用）
- `TextMessageContent` - 文本消息内容，追加文本内容
- `TextMessageEnd` - 文本消息结束，标记文本为完成状态

**思考过程事件**：

- `ThinkingStart` - 思考开始，显示 AI 思考标题
- `ThinkingTextMessageStart` - 思考文本开始
- `ThinkingTextMessageContent` - 思考文本内容，流式接收思考过程
- `ThinkingTextMessageEnd` - 思考文本结束
- `ThinkingEnd` - 思考结束，计算思考时长

**工具调用事件**：

- `ToolCallStart` - 工具调用开始，显示调用的工具名称
- `ToolCallChunk` - 工具调用块，流式接收调用信息
- `ToolCallArgs` - 工具参数，接收工具调用参数
- `ToolCallResult` - 工具结果，接收工具执行结果
- `ToolCallEnd` - 工具调用结束，标记工具调用完成

**步骤相关事件**：

- `StepStarted` - 步骤开始，多步骤任务中的单步开始
- `StepFinished` - 步骤完成，单步任务完成

**状态同步事件**：

- `MessagesSnapshot` - 消息快照，用于多端消息同步
- `StateSnapshot` - 状态快照，完整状态信息
- `StateDelta` - 状态增量更新，使用 JSON Patch 格式
- `ActivitySnapshot` - 活动快照，完整活动信息
- `ActivityDelta` - 活动增量更新，使用 JSON Patch 格式

**其他事件**：

- `Raw` - 原始事件，透传底层 AI 服务的原始事件
- `Custom` - 自定义事件，用户自定义的事件类型

</details>

## 实战场景

### 场景 1：带输入框的聊天界面

使用独立的 `ref` 管理用户输入：

```vue
<template>
  <div class="chat-interface">
    <div class="messages">
      <div
        v-for="msg in message.list"
        :key="msg.id"
      >
        <!-- 消息渲染 -->
      </div>
    </div>
    <div class="input-box">
      <textarea
        v-model="userInput"
        @keydown.enter.prevent="handleSend"
        placeholder="输入消息，按 Enter 发送..."
        :disabled="isStreaming"
      />
      <button
        @click="handleSend"
        :disabled="!canSend"
      >
        {{ isStreaming ? '发送中...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { useChatHelper } from '@blueking/chat-helper';

  const { agent, message, session } = useChatHelper({
    /* ... */
  });
  const isStreaming = ref(false);
  const userInput = ref('');

  const canSend = computed(
    () => !isStreaming.value && userInput.value.trim().length > 0 && session.current?.sessionCode,
  );

  const handleSend = () => {
    if (canSend.value) {
      isStreaming.value = true;
      const input = userInput.value;
      userInput.value = ''; // 立即清空输入框
      agent.chat(input, session.current!.sessionCode).finally(() => {
        isStreaming.value = false;
      });
    }
  };
</script>
```

### 场景 2：消息批量管理

实现消息的选择和批量删除功能：

```vue
<template>
  <div class="message-manager">
    <div class="toolbar">
      <button @click="selectAll">全选</button>
      <button @click="clearSelection">取消选择</button>
      <button
        @click="batchDelete"
        :disabled="selectedIds.length === 0 || message.isBatchDeleteLoading"
      >
        {{ message.isBatchDeleteLoading ? '删除中...' : `删除选中 (${selectedIds.length})` }}
      </button>
    </div>

    <div class="messages">
      <div
        v-for="msg in message.list"
        :key="msg.messageId"
        @click="toggleSelection(msg.messageId)"
        :class="{ selected: selectedIds.includes(msg.messageId) }"
      >
        <input
          type="checkbox"
          :checked="selectedIds.includes(msg.messageId)"
          @click.stop
        />
        <!-- 消息内容 -->
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useChatHelper } from '@blueking/chat-helper';

  const { message } = useChatHelper({
    /* ... */
  });
  const selectedIds = ref<string[]>([]);

  const toggleSelection = (id: string) => {
    const index = selectedIds.value.indexOf(id);
    if (index > -1) {
      selectedIds.value.splice(index, 1);
    } else {
      selectedIds.value.push(id);
    }
  };

  const selectAll = () => {
    selectedIds.value = message.list.value.filter(msg => msg.messageId).map(msg => msg.messageId!);
  };

  const clearSelection = () => {
    selectedIds.value = [];
  };

  const batchDelete = async () => {
    if (selectedIds.value.length > 0) {
      await message.batchDeleteMessages(selectedIds.value);
      selectedIds.value = [];
    }
  };
</script>
```

### 场景 3：自定义聊天参数

根据不同场景使用不同的聊天配置：

```vue
<template>
  <div class="custom-chat">
    <div class="settings">
      <label>
        温度:
        <input
          v-model.number="temperature"
          type="range"
          min="0"
          max="1"
          step="0.1"
        />
        {{ temperature }}
      </label>
      <label>
        最大tokens:
        <input
          v-model.number="maxTokens"
          type="number"
        />
      </label>
      <label>
        模式:
        <select v-model="mode">
          <option value="default">默认</option>
          <option value="creative">创意</option>
          <option value="precise">精确</option>
        </select>
      </label>
    </div>

    <textarea
      v-model="userInput"
      placeholder="输入消息..."
    />
    <button @click="sendWithConfig">发送</button>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useChatHelper } from '@blueking/chat-helper';

  const { agent, session } = useChatHelper({
    /* ... */
  });

  const userInput = ref('');
  const temperature = ref(0.7);
  const maxTokens = ref(1000);
  const mode = ref('default');

  const sendWithConfig = () => {
    if (!session.current?.sessionCode || !userInput.value.trim()) return;

    // 根据模式设置不同的端点
    const endpoint =
      mode.value === 'creative'
        ? 'chat_completion_creative/'
        : mode.value === 'precise'
        ? 'chat_completion_precise/'
        : undefined;

    // 自定义请求参数
    agent.chat(userInput.value, session.current.sessionCode, endpoint, {
      data: {
        temperature: temperature.value,
        max_tokens: maxTokens.value,
        mode: mode.value,
      },
      headers: {
        'X-Chat-Mode': mode.value,
      },
    });

    userInput.value = ''; // 清空输入框
  };
</script>
```

## 完整示例

以下是一个完整的聊天应用示例：

```vue
<template>
  <div class="chat-app">
    <!-- 会话列表 -->
    <aside class="session-list">
      <button @click="createNewSession">新建会话</button>
      <ul>
        <li
          v-for="item in session.list"
          :key="item.sessionCode"
          @click="session.chooseSession(item.sessionCode)"
          :class="{ active: session.current?.sessionCode === item.sessionCode }"
        >
          {{ item.sessionName }}
          <button @click.stop="session.deleteSession(item.sessionCode)">删除</button>
        </li>
      </ul>
    </aside>

    <!-- 消息区域 -->
    <main class="message-area">
      <div v-if="message.isListLoading">加载中...</div>
      <div
        v-else
        class="message-list"
      >
        <div
          v-for="msg in message.list"
          :key="msg.messageId"
          :class="['message-item', msg.role]"
        >
          <div class="message-content">
            <template v-if="msg.role === 'user'">
              {{ typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content) }}
            </template>
            <template v-else-if="msg.role === 'assistant'">
              {{ msg.content || '' }}
            </template>
          </div>
          <button @click="message.deleteMessage(msg.messageId)">删除</button>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <input
          v-model="userInput"
          @keyup.enter="sendMessage"
          placeholder="输入消息..."
          :disabled="isStreaming"
        />
        <button
          @click="sendMessage"
          :disabled="isStreaming"
        >
          {{ isStreaming ? '生成中...' : '发送消息' }}
        </button>
        <button
          @click="agent.stopChat"
          :disabled="!isStreaming"
        >
          停止生成
        </button>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';
  import { useChatHelper, AGUIProtocol } from '@blueking/chat-helper';

  const isStreaming = ref(false);
  const userInput = ref('');

  const { agent, session, message } = useChatHelper({
    requestData: {
      urlPrefix: 'https://your-api-domain.com/api/',
      headers: () => ({
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      }),
    },
    interceptors: {
      request: config => {
        console.log('Request:', config.url);
        return config;
      },
      response: response => {
        if (response.data.code !== 0) {
          console.error('API Error:', response.data.message);
        }
        return response;
      },
    },
    protocol: new AGUIProtocol({
      onStart: () => {
        isStreaming.value = true;
        console.log('开始接收 AI 响应');
      },
      onMessage: event => {
        // 可以在这里添加自定义事件处理
        console.log('收到事件:', event.type);
      },
      onDone: () => {
        isStreaming.value = false;
        console.log('AI 响应完成');
      },
      onError: error => {
        isStreaming.value = false;
        console.error('AI 响应错误:', error);
        alert('发生错误，请重试');
      },
    }),
  });

  onMounted(async () => {
    await agent.getAgentInfo();
    await session.getSessions();
    if (session.list.value.length > 0) {
      await session.chooseSession(session.list.value[0].sessionCode);
    }
  });

  const createNewSession = () => {
    session.createSession({
      sessionName: `会话 ${new Date().toLocaleString()}`,
      sessionCode: `session_${Date.now()}`,
    });
  };

  const sendMessage = () => {
    if (session.current?.sessionCode && userInput.value.trim()) {
      agent.chat(userInput.value, session.current.sessionCode);
      userInput.value = ''; // 清空输入框
    }
  };
</script>

<style scoped>
  .chat-app {
    display: flex;
    height: 100vh;
  }

  .session-list {
    width: 250px;
    border-right: 1px solid #ddd;
    padding: 20px;
  }

  .message-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 20px;
  }

  .message-list {
    flex: 1;
    overflow-y: auto;
  }

  .message-item {
    margin-bottom: 20px;
    padding: 10px;
    border-radius: 8px;
  }

  .message-item.user {
    background-color: #e3f2fd;
    margin-left: 20%;
  }

  .message-item.assistant {
    background-color: #f5f5f5;
    margin-right: 20%;
  }

  .input-area {
    display: flex;
    gap: 10px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
  }
</style>
```

## 钩子函数综合示例

以下是一个结合所有钩子函数的实际应用示例：

```vue
<template>
  <div class="chat-container">
    <!-- 状态指示器 -->
    <div
      v-if="status"
      class="status-bar"
      :class="status.type"
    >
      {{ status.message }}
    </div>

    <!-- 消息列表 -->
    <div class="messages">
      <div
        v-for="msg in message.list"
        :key="msg.messageId"
        class="message"
      >
        <template
          v-for="content in msg.content"
          :key="content.id"
        >
          <!-- 显示思考过程 -->
          <div
            v-if="content.type === 'thinking'"
            class="thinking"
          >
            <span class="icon">🤔</span>
            <strong>{{ content.data.title }}</strong>
            <span v-if="content.data.duration"> ({{ content.data.duration }}ms) </span>
          </div>

          <!-- 显示工具调用 -->
          <div
            v-if="content.type === 'tool_call'"
            class="tool-call"
          >
            <span class="icon">🔧</span>
            <strong>{{ content.data.toolCallName }}</strong>
          </div>

          <!-- 显示文本内容 -->
          <div
            v-if="content.type === 'text'"
            class="text"
          >
            {{ content.data }}
          </div>
        </template>
      </div>
    </div>

    <!-- 输入区域 -->
    <div class="input-area">
      <input
        v-model="userInput"
        @keyup.enter="sendMessage"
        placeholder="输入消息..."
        :disabled="isStreaming"
      />
      <button
        @click="sendMessage"
        :disabled="isStreaming"
      >
        发送
      </button>
      <button
        @click="stopStreaming"
        :disabled="!isStreaming"
      >
        停止
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import {
    useChatHelper,
    AGUIProtocol,
    type IThinkingStartEvent,
    type IToolCallStartEvent,
    type IRunErrorEvent,
  } from '@blueking/chat-helper';

  const isStreaming = ref(false);
  const status = ref<{ type: string; message: string } | null>(null);
  const userInput = ref('');

  // 自定义 Protocol，添加各种钩子
  class CustomChatProtocol extends AGUIProtocol {
    // 思考开始时显示通知
    handleThinkingStartEvent(event: IThinkingStartEvent) {
      status.value = {
        type: 'thinking',
        message: `AI 正在思考: ${event.title}`,
      };
      super.handleThinkingStartEvent(event);
    }

    // 工具调用时显示通知
    handleToolCallStartEvent(event: IToolCallStartEvent) {
      status.value = {
        type: 'tool',
        message: `正在调用工具: ${event.toolCallName}`,
      };
      super.handleToolCallStartEvent(event);
    }

    // 错误处理
    handleRunErrorEvent(event: IRunErrorEvent) {
      status.value = {
        type: 'error',
        message: `错误: ${event.message}`,
      };
      super.handleRunErrorEvent(event);

      // 3秒后清除错误提示
      setTimeout(() => {
        status.value = null;
      }, 3000);
    }
  }

  const { agent, session, message } = useChatHelper({
    requestData: {
      urlPrefix: 'https://your-api-domain.com/api/',
    },
    protocol: new CustomChatProtocol({
      // 开始接收响应
      onStart: () => {
        isStreaming.value = true;
        status.value = {
          type: 'streaming',
          message: '正在接收 AI 响应...',
        };
      },
      // 每个事件
      onMessage: event => {
        console.log('事件:', event);
      },
      // 响应完成
      onDone: () => {
        isStreaming.value = false;
        status.value = {
          type: 'success',
          message: 'AI 响应完成',
        };
        setTimeout(() => {
          status.value = null;
        }, 2000);
      },
      // 响应错误
      onError: error => {
        isStreaming.value = false;
        status.value = {
          type: 'error',
          message: `连接错误: ${error.message}`,
        };
      },
    }),
  });

  const sendMessage = () => {
    if (session.current?.sessionCode && userInput.value.trim()) {
      agent.chat(userInput.value, session.current.sessionCode);
      userInput.value = ''; // 清空输入框
    }
  };

  const stopStreaming = () => {
    agent.stopChat();
  };
</script>

<style scoped>
  .status-bar {
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 4px;
  }

  .status-bar.thinking {
    background-color: #e3f2fd;
  }

  .status-bar.tool {
    background-color: #fff3e0;
  }

  .status-bar.error {
    background-color: #ffebee;
    color: #c62828;
  }

  .status-bar.success {
    background-color: #e8f5e9;
  }

  .thinking {
    background-color: #f5f5f5;
    padding: 8px;
    margin: 4px 0;
    border-radius: 4px;
  }

  .tool-call {
    background-color: #fff3e0;
    padding: 8px;
    margin: 4px 0;
    border-radius: 4px;
  }
</style>
```

## 类型定义

所有类型都已导出，您可以在 TypeScript 项目中使用：

```typescript
import type {
  // 主要配置和模块类型
  IUseChatHelperOptions,
  IAgentModule,
  ISessionModule,
  IMessageModule,
  IHttpModule,

  // 核心数据类型
  IMessage,
  ISession,
  IAgentInfo,

  // 消息相关枚举
  MessageRole, // 消息角色：user, assistant, system, tool, activity, reasoning 等
  MessageStatus, // 消息状态：pending, streaming, complete, error, stop
  MessageType, // 消息类型：text, binary, function

  // 协议相关
  ISSEProtocol,
  AGUIProtocol,

  // 事件类型（用于自定义 Protocol）
  IEvent,
  IRunStartedEvent,
  IRunFinishedEvent,
  IRunErrorEvent,
  ITextMessageChunkEvent,
  IThinkingStartEvent,
  IThinkingEndEvent,
  IToolCallStartEvent,
  // ... 更多事件类型
} from '@blueking/chat-helper';
```

### MessageRole 枚举

消息支持多种角色类型：

```typescript
enum MessageRole {
  User = 'user', // 用户消息
  Assistant = 'assistant', // AI 助手消息
  System = 'system', // 系统消息
  Tool = 'tool', // 工具调用结果
  Activity = 'activity', // 活动消息
  Reasoning = 'reasoning', // 推理过程
  Developer = 'developer', // 开发者消息
  Guide = 'guide', // 引导消息
  Info = 'info', // 信息消息
  Pause = 'pause', // 暂停消息
  Placeholder = 'placeholder', // 占位消息
  Hidden = 'hidden', // 隐藏消息
  HiddenUser = 'hidden-user', // 隐藏的用户消息
  HiddenAssistant = 'hidden-assistant', // 隐藏的助手消息
  HiddenSystem = 'hidden-system', // 隐藏的系统消息
  HiddenGuide = 'hidden-guide', // 隐藏的引导消息
  TemplateUser = 'template-user', // 用户消息模板
  TemplateAssistant = 'template-assistant', // 助手消息模板
  TemplateSystem = 'template-system', // 系统消息模板
  TemplateGuide = 'template-guide', // 引导消息模板
  TemplateHidden = 'template-hidden', // 隐藏消息模板
}
```

### MessageStatus 枚举

消息状态定义：

```typescript
enum MessageStatus {
  Pending = 'pending', // 等待中
  Streaming = 'streaming', // 流式传输中
  Complete = 'complete', // 已完成
  Error = 'error', // 错误
  Stop = 'stop', // 已停止
}
```

### IMessage 类型

消息是联合类型，根据 `role` 字段不同有不同的结构：

```typescript
// 用户消息
interface IUserMessage {
  messageId?: string;
  role: MessageRole.User;
  status: MessageStatus;
  content: string | IInputContent[]; // 支持文本或多媒体内容
}

// AI 助手消息
interface IAssistantMessage {
  messageId?: string;
  role: MessageRole.Assistant;
  status: MessageStatus;
  content?: string;
  toolCalls?: IToolCall[]; // 工具调用信息
}

// 工具消息
interface IToolMessage {
  messageId?: string;
  role: MessageRole.Tool;
  status: MessageStatus;
  content: string;
  toolCallId: string;
  duration?: number;
  error?: string;
}

// ... 更多消息类型
```

## API 参考

### useChatHelper(options)

创建 Chat Helper 实例。

**参数：**

- `options.requestData` (必需)

  - `urlPrefix: string` - API 基础路径
  - `data?: Record<string, unknown> | (() => Record<string, unknown>)` - 额外的请求数据
  - `headers?: Record<string, string> | (() => Record<string, string>)` - 额外的请求头

- `options.interceptors` (可选)

  - `request?: (config: IRequestConfig) => IRequestConfig` - 请求拦截器
  - `response?: (response: IResponse) => IResponse` - 响应拦截器

- `options.protocol` (可选) - 自定义 SSE Protocol 实例，默认使用 `AGUIProtocol`

**返回值：**

```typescript
{
  agent: IAgentModule,      // Agent 模块
  session: ISessionModule,  // Session 模块
  message: IMessageModule,  // Message 模块
  http: IHttpModule         // HTTP 模块
}
```

### Agent 模块 API

#### agent.info

- **类型**：`Ref<IAgentInfo | null>`
- **说明**：当前 Agent 的信息，包括名称、会话设置、预定义问题等

#### agent.isInfoLoading

- **类型**：`Ref<boolean>`
- **说明**：Agent 信息是否正在加载

#### agent.getAgentInfo()

- **返回值**：`Promise<void>`
- **说明**：获取 Agent 信息，结果保存在 `agent.info` 中

#### agent.chat(userInput, sessionCode, url?, config?)

- **参数**：
  - `userInput: string` - 用户输入的消息内容
  - `sessionCode: string` - 会话代码
  - `url?: string` - 自定义聊天接口地址，默认为 `'chat_completion/'`
  - `config?: IRequestConfig` - 额外的请求配置
- **返回值**：`Promise<void>`
- **说明**：开始与 AI 进行聊天，支持流式响应。会先创建一条用户消息，然后发起流式请求

#### agent.stopChat()

- **返回值**：`Promise<void>`
- **说明**：停止当前的聊天流式响应

### Session 模块 API

#### session.list

- **类型**：`Ref<ISession[]>`
- **说明**：会话列表

#### session.current

- **类型**：`Ref<ISession | null>`
- **说明**：当前选中的会话

#### session.isListLoading / isCurrentLoading / isCreateLoading / isUpdateLoading / isDeleteLoading

- **类型**：`Ref<boolean>`
- **说明**：各操作的加载状态

#### session.getSessions()

- **返回值**：`Promise<void>`
- **说明**：获取会话列表，结果保存在 `session.list` 中

#### session.chooseSession(sessionCode)

- **参数**：`sessionCode: string` - 会话代码
- **返回值**：`Promise<void>`
- **说明**：选择会话，会停止当前聊天、设置 `session.current`，并自动加载该会话的消息列表

#### session.getSession(sessionCode)

- **参数**：`sessionCode: string` - 会话代码
- **返回值**：`Promise<void>`
- **说明**：获取单个会话信息，结果保存在 `session.current` 中

#### session.createSession(session)

- **参数**：`session: ISession` - 会话数据
- **返回值**：`Promise<void>`
- **说明**：创建新会话，创建成功后会添加到列表并自动选中

#### session.updateSession(session)

- **参数**：`session: ISession` - 会话数据
- **返回值**：`Promise<void>`
- **说明**：更新会话信息

#### session.deleteSession(sessionCode)

- **参数**：`sessionCode: string` - 会话代码
- **返回值**：`Promise<void>`
- **说明**：删除会话，如果删除的是当前会话，会自动切换到第一个会话

### Message 模块 API

#### message.list

- **类型**：`Ref<IMessage[]>`
- **说明**：消息列表

#### message.isListLoading / isDeleteLoading / isBatchDeleteLoading

- **类型**：`Ref<boolean>`
- **说明**：各操作的加载状态

#### message.getMessages(sessionCode)

- **参数**：`sessionCode: string` - 会话代码
- **返回值**：`Promise<void>`
- **说明**：获取指定会话的消息列表

#### message.plusMessage(message)

- **参数**：`message: IMessage` - 消息数据
- **返回值**：`Promise<void>`
- **说明**：添加新消息，会先调用接口创建，然后添加到列表最前面

#### message.modifyMessage(message)

- **参数**：`message: IMessage` - 消息数据
- **返回值**：`void`
- **说明**：修改消息（仅本地更新，不调用接口）

#### message.deleteMessage(id)

- **参数**：`id: string` - 消息 ID
- **返回值**：`Promise<void>`
- **说明**：删除单条消息

#### message.batchDeleteMessages(ids)

- **参数**：`ids: string[]` - 消息 ID 数组
- **返回值**：`Promise<void>`
- **说明**：批量删除多条消息

#### message.getCurrentLoadingMessage()

- **返回值**：`IMessage | undefined`
- **说明**：获取当前正在加载或流式传输中的 AI 消息（状态为 Pending 或 Streaming）

#### message.getMessageByMessageId(id)

- **参数**：`id: string` - 消息 ID
- **返回值**：`IMessage | undefined`
- **说明**：根据消息 ID 从列表中查找消息

## 最佳实践

### 1. 错误处理

建议在使用 API 时添加适当的错误处理：

```typescript
const { session } = useChatHelper({
  /* ... */
});

const loadSessions = async () => {
  try {
    await session.getSessions();
  } catch (error) {
    console.error('加载会话列表失败:', error);
    // 显示错误提示给用户
  }
};
```

### 2. 加载状态管理

利用响应式的加载状态提供更好的用户体验：

```vue
<template>
  <div>
    <div v-if="session.isListLoading">
      <Spinner />
      加载中...
    </div>
    <ul v-else>
      <li
        v-for="item in session.list"
        :key="item.sessionCode"
      >
        {{ item.sessionName }}
      </li>
    </ul>
  </div>
</template>
```

### 3. 会话切换

切换会话时，`chooseSession` 会自动停止当前聊天并加载新会话的消息：

```typescript
// ✅ 推荐：使用 chooseSession
await session.chooseSession(sessionCode);

// ❌ 不推荐：手动操作
agent.stopChat();
session.current.value = session.list.value.find(s => s.sessionCode === sessionCode);
message.getMessages(sessionCode);
```

### 4. 消息 ID 使用

代码中使用 `messageId` 字段作为消息的唯一标识：

```typescript
// ✅ 正确
message.deleteMessage(msg.messageId);

// ❌ 错误
message.deleteMessage(msg.id);
```

### 5. 动态请求配置

对于需要动态获取的配置（如 token），使用函数形式：

```typescript
useChatHelper({
  requestData: {
    urlPrefix: 'https://api.example.com/',
    // ✅ 使用函数动态获取
    headers: () => ({
      Authorization: `Bearer ${localStorage.getItem('token')}`,
      'X-Request-ID': generateRequestId(),
    }),
  },
});
```

### 6. Protocol 钩子函数

使用 Protocol 钩子函数时，注意不要阻塞事件处理：

```typescript
new AGUIProtocol({
  onMessage: async event => {
    // ❌ 不推荐：阻塞事件处理
    await someAsyncOperation();
    console.log(event);
  },

  onMessage: event => {
    // ✅ 推荐：快速处理，异步操作不阻塞
    console.log(event);
    someAsyncOperation(); // 不 await
  },
});
```

### 7. 内存管理

在组件卸载时，记得停止正在进行的聊天：

```typescript
import { onUnmounted } from 'vue';

const { agent } = useChatHelper({
  /* ... */
});

onUnmounted(() => {
  agent.stopChat();
});
```

### 8. 消息状态判断

使用枚举类型进行状态判断，避免硬编码字符串：

```typescript
import { MessageStatus, MessageRole } from '@blueking/chat-helper';

// ✅ 推荐：使用枚举
if (msg.status === MessageStatus.Streaming && msg.role === MessageRole.Assistant) {
  // 显示流式动画
}

// ❌ 不推荐：硬编码字符串
if (msg.status === 'streaming' && msg.role === 'assistant') {
  // 显示流式动画
}
```

## 常见问题

### Q: 如何处理流式响应中的错误？

A: 使用 Protocol 的 `onError` 钩子函数：

```typescript
useChatHelper({
  requestData: {
    /* ... */
  },
  protocol: new AGUIProtocol({
    onError: error => {
      console.error('流式响应错误:', error);
      // 显示错误提示
      showErrorMessage('AI 响应出错，请重试');
    },
  }),
});
```

### Q: 如何自定义不同端点的聊天行为？

A: 使用 `agent.chat` 的 `url` 和 `config` 参数：

```typescript
// 使用不同的端点
agent.chat(userInput, sessionCode, 'custom_chat/');

// 添加自定义参数
agent.chat(userInput, sessionCode, undefined, {
  data: {
    temperature: 0.8,
    model: 'gpt-4',
  },
});
```

### Q: 消息列表如何实现自动滚动到底部？

A: 使用 Vue 的 `watch` 监听消息列表变化：

```typescript
import { watch, nextTick, ref } from 'vue';

const messageContainer = ref<HTMLElement>();
const { message } = useChatHelper({
  /* ... */
});

watch(
  () => message.list.value.length,
  async () => {
    await nextTick();
    messageContainer.value?.scrollTo({
      top: messageContainer.value.scrollHeight,
      behavior: 'smooth',
    });
  },
);
```

### Q: 如何判断 AI 是否正在回复？

A: 使用 `message.getCurrentLoadingMessage()` 方法：

```typescript
const { message } = useChatHelper({
  /* ... */
});

const isAIResponding = computed(() => {
  return message.getCurrentLoadingMessage() !== undefined;
});
```

### Q: 如何实现多租户或多应用场景？

A: 使用动态的 `data` 配置：

```typescript
const currentAppId = ref('app-1');

useChatHelper({
  requestData: {
    urlPrefix: 'https://api.example.com/',
    data: () => ({
      app_id: currentAppId.value,
      tenant_id: getTenantId(),
    }),
  },
});
```

### Q: 如何自定义流式事件的处理逻辑？

A: 继承 `AGUIProtocol` 并重写对应的事件处理方法：

```typescript
class MyProtocol extends AGUIProtocol {
  handleTextMessageChunkEvent(event: ITextMessageChunkEvent) {
    // 自定义逻辑：例如敏感词过滤
    const filteredText = filterSensitiveWords(event.delta);

    // 调用父类方法继续处理
    super.handleTextMessageChunkEvent({
      ...event,
      delta: filteredText,
    });
  }
}

useChatHelper({
  requestData: {
    /* ... */
  },
  protocol: new MyProtocol(),
});
```

### Q: 如何实现消息的本地缓存？

A: 使用 `watch` 监听消息变化并保存到本地存储：

```typescript
import { watch } from 'vue';

const { message, session } = useChatHelper({
  /* ... */
});

// 监听消息变化并缓存
watch(
  () => message.list.value,
  newList => {
    if (session.current?.sessionCode) {
      localStorage.setItem(`messages_${session.current.sessionCode}`, JSON.stringify(newList));
    }
  },
  { deep: true },
);

// 加载缓存
const loadCachedMessages = (sessionCode: string) => {
  const cached = localStorage.getItem(`messages_${sessionCode}`);
  if (cached) {
    message.list.value = JSON.parse(cached);
  }
};
```

## 贡献指南

欢迎提交 Issue 和 Pull Request！

在提交 PR 之前，请确保：

1. 代码通过 ESLint 检查
2. 添加了必要的类型定义
3. 更新了相关文档

## 更新日志

查看 [CHANGELOG.md](./CHANGELOG.md) 了解版本更新历史。

## License

MIT License

Copyright (C) 2021 THL A29 Limited, a Tencent company. All rights reserved.
