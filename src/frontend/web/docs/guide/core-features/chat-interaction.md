# 聊天交互

AI 小鲸 v2.0 提供了完整的聊天交互能力，基于 AG-UI 协议实现流式对话，支持多种消息类型和丰富的内容渲染。

## 消息发送流程

用户发送消息后，数据经过以下流程到达后端并返回响应：

![消息发送流程](/images/guide/message-send-flow.png)

**核心步骤说明**：

1. **ChatBot 组件**：接收用户输入，构建消息内容和 `property`（引用、快捷指令等附加信息）
2. **[ChatBusinessManager](/guide/internals/manager-pattern)**：业务管理器，负责设置 `isGenerating` 状态、触发 `send-message` 事件、调用 SDK
3. **agentModule.chat()**：AG-UI SDK 的核心方法，发起 SSE 流式请求
4. **[AGUIProtocol](/guide/core-features/chat-interaction#流式响应)**：解析 SSE 事件流，将不同类型的事件分发给对应的处理方法

## 流式响应

AI 小鲸的流式输出基于 `AGUIProtocol` 协议实现。`AGUIProtocol` 是 `@blueking/chat-helper` 提供的核心协议类，实现了 `ISSEProtocol` 接口。

### 协议生命周期回调

```typescript
const protocol = new AGUIProtocol({
  onStart: () => {
    // 流式响应开始，SSE 连接建立
    console.log('流式响应开始');
  },
  onMessage: (event: IEvent) => {
    // 每次接收到一个 AG-UI 事件
    // 协议内部会自动分发到对应的 handle 方法
    console.log('收到事件:', event.type);
  },
  onDone: () => {
    // 流式响应完成，SSE 连接关闭
    console.log('流式响应完成');
  },
  onError: (error: unknown) => {
    // 流式响应出错
    console.error('流式响应错误:', error);
  },
});
```

### AG-UI 事件类型

协议支持以下主要事件类型（`EventType` 枚举）：

| 事件类型 | 说明 |
|---------|------|
| `RUN_STARTED` | 运行开始 |
| `RUN_FINISHED` | 运行完成，消息标记为 Complete |
| `RUN_ERROR` | 运行出错，创建错误消息 |
| `TEXT_MESSAGE_START` | 文本消息开始，创建空的 Assistant 消息 |
| `TEXT_MESSAGE_CONTENT` | 文本消息内容增量（流式输出） |
| `TEXT_MESSAGE_END` | 文本消息结束 |
| `TEXT_MESSAGE_CHUNK` | 文本消息块（简化版流式输出） |
| `THINKING_START` | 深度思考开始，创建 Reasoning 消息 |
| `THINKING_TEXT_MESSAGE_CONTENT` | 思考内容增量 |
| `THINKING_END` | 深度思考结束，附带 duration |
| `TOOL_CALL_START` | 工具调用开始 |
| `TOOL_CALL_ARGS` | 工具调用参数（流式） |
| `TOOL_CALL_RESULT` | 工具调用结果 |
| `TOOL_CALL_END` | 工具调用结束 |
| `CUSTOM` | 自定义事件（如知识库检索、参考文档等） |
| `MESSAGES_SNAPSHOT` | 消息快照，用于多端同步 |

### 小鲸扩展协议

AI 小鲸通过 `BluekingProtocol` 类扩展了 `AGUIProtocol`，添加了额外的事件发射能力：

```typescript
import { createBluekingProtocol } from '@blueking/ai-blueking';

const protocol = createBluekingProtocol({
  eventEmitter,                // 事件发射器，用于组件间通信
  onStart: () => { },          // 流式开始
  onMessage: (event) => { },   // 接收事件
  onDone: () => { },           // 流式完成
  onError: (error) => { },     // 发生错误
});
```

## 消息类型

AI 小鲸支持丰富的消息角色类型，由 `MessageRole` 枚举定义。以下是常见的消息角色：

| 角色 (MessageRole) | 说明 | 场景 |
|---|---|---|
| `User` | 用户消息 | 用户输入的文本、引用内容等 |
| `Assistant` | AI 助手回复 | AI 生成的文本回复、工具调用 |
| `Reasoning` | 深度思考 | AI 的思考过程，可折叠展示 |
| `Tool` | 工具调用结果 | 工具执行的返回结果 |
| `Activity` | 活动消息 | 知识库检索、参考文档等流程状态 |
| `Info` | 信息消息 | 系统提示信息 |
| `System` | 系统消息 | 系统级别的消息 |

此外还有 `Guide`（引导消息）、`Developer`（开发者消息）等扩展角色，以及多种 `Hidden*` 和 `Template*` 角色用于内部流程控制。

### 消息状态

每条消息都有 `MessageStatus` 状态标识：

```typescript
enum MessageStatus {
  Pending = 'pending',       // 等待中
  Streaming = 'streaming',   // 流式输出中
  Complete = 'complete',     // 已完成
  Error = 'error',           // 出错
  Stop = 'stop',             // 被用户停止
}
```

## 内容渲染

AI 小鲸支持多种内容渲染格式：

- **Markdown**：支持标题、列表、表格、链接、图片等标准 Markdown 语法
- **蓝鲸行内富文本**（v2.1.4-beta.6+）：`::bk{color=red; bold}重点:/bk::` 等安全行内样式，详见 [蓝鲸行内富文本](/guide/core-features/markdown-inline-style)
- **代码高亮**：支持语法高亮、行号显示、代码复制
- **LaTeX 公式**：通过 KaTeX 渲染数学公式
- **Mermaid 图表**：支持流程图、时序图、甘特图等 Mermaid 图表

所有 Markdown 内容都经过安全处理，防止 XSS 攻击。**不解析任意 HTML 标签**；若需彩色标题、背景高亮等，请让模型使用蓝鲸行内富文本语法，并在 AIDev Agent 系统提示词中约定格式（参见上文链接中的 LLM 配置示例）。

## 停止生成

当 AI 正在生成内容时，可以通过以下方式停止：

```typescript
// 方式 1：通过 ChatBot 组件 expose
chatBotRef.value.stopChat();

// 方式 2：通过 AIBlueking 组件 expose
aiBluekingRef.value.stopChat();
```

**内部流程**：

```
stopChat()
  → ChatBusinessManager.stopChat()
    → agentModule.stopChat(sessionCode)    // 调用后端停止接口
    → isGenerating = false
    → emit('stop')
```

## 错误处理

AI 小鲸提供了多层错误处理机制：

1. **AGUIProtocol.onError**：捕获 SSE 连接级别的错误，自动创建一条 `MessageStatus.Error` 的错误消息
2. **RUN_ERROR 事件**：后端通过事件流返回的运行时错误，同样会创建错误消息
3. **ChatBusinessManager 错误事件**：业务层面的错误，通过 `chat-error` 内部事件传播
4. **sdk-error 事件**：对外暴露的统一错误事件，可在组件上监听

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    @sdk-error="handleError"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = 'https://your-api-endpoint.com/assistant/';

const handleError = (data: { apiName: string; code: number; message: string }) => {
  console.error(`API 错误 [${data.apiName}]:`, data.message);
};
</script>
```

## 代码示例：监听流式事件

### 使用 ChatBot 独立模式

```vue
<template>
  <ChatBot
    ref="chatBotRef"
    url="/api/ai/assistant/"
    placeholder="请输入您的问题..."
    hello-text="你好，我是 AI 小鲸，有什么可以帮助你的？"
    @send-message="onSendMessage"
    @receive-start="onReceiveStart"
    @receive-end="onReceiveEnd"
    @stop="onStop"
    @error="onError"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';

const chatBotRef = ref<InstanceType<typeof ChatBot> | null>(null);

const onSendMessage = (message: string) => {
  console.log('用户发送:', message);
};

const onReceiveStart = () => {
  console.log('AI 开始响应');
};

const onReceiveEnd = () => {
  console.log('AI 响应完成');
};

const onStop = () => {
  console.log('用户停止了生成');
};

const onError = (error: Error) => {
  console.error('发生错误:', error.message);
};

// 通过 expose 方法编程式操作
const sendProgrammatically = async () => {
  await chatBotRef.value?.sendMessage('帮我写一个 Hello World');
};

const stopGeneration = () => {
  chatBotRef.value?.stopChat();
};
</script>
```

### 使用 useChatBootstrap 自定义流式监听

```typescript
import { useChatBootstrap } from '@blueking/ai-blueking';

const { chatHelper, protocol, isReady } = useChatBootstrap({
  url: '/api/ai/assistant/',
  protocolCallbacks: {
    onStart: () => {
      console.log('流式开始');
    },
    onMessage: (event) => {
      // 可以在这里自定义处理每个 AG-UI 事件
      console.log('收到事件:', event);
    },
    onDone: () => {
      console.log('流式完成');
    },
    onError: (error) => {
      console.error('流式错误:', error);
    },
  },
});
```
