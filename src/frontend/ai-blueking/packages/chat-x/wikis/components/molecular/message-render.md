---
name: MessageRender 消息渲染器
slug: message-render
category: molecular
description: 统一的消息渲染入口，通过 `message.role` 字段自动派发到对应的子组件。整个渲染过程由一个 `computed` 属性完成，无额外状态。
aiSummary: >
  MessageRender 是单条消息的渲染入口，根据 message.role 派发到 UserMessage、AssistantMessage、ReasoningMessage、
  ToolMessage、ActivityMessage、InfoMessage、LoadingMessage 等。Assistant 默认通过插槽用 ContentRender 渲染正文，可被默认插槽覆盖。
  无独立状态，通常由 MessageContainer 内部调用而非业务直接挂载。
relatedComponents:
  - slug: message-container
    relation: 在 MessageContainer 中按组调用以渲染每条消息
  - slug: assistant-message
    relation: role 为 assistant 时渲染 AI 回复与工具调用
  - slug: user-message
    relation: role 为 user 时渲染用户消息
sinceVersion: 1.0.0
domain: message
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import MessageRenderComp from '../../../src/components/chat-message/message-render/message-render.vue'

  const assistantMsg = {
    id: '1',
    messageId: 1,
    role: 'assistant',
    content: `## Vue 3 组合式 API

**组合式 API（Composition API）** 是 Vue 3 引入的一种新方式，让你可以用函数的形式组织组件逻辑。

核心优势：

- 更好的逻辑复用（自定义 Composable）
- 更清晰的代码组织
- 完整的 TypeScript 类型推断

\`\`\`typescript
import { ref, computed } from 'vue';

export function useCounter(initialValue = 0) {
  const count = ref(initialValue);
  const double = computed(() => count.value * 2);

  function increment() {
    count.value++;
  }

  return { count, double, increment };
}
\`\`\`
`,
    status: 'complete',
  };

  const assistantStreamingMsg = ref({
    id: '2',
    messageId: 2,
    role: 'assistant',
    content: '正在为你生成答案，请稍候...',
    status: 'streaming',
  });

  const assistantErrorMsg = {
    id: '3',
    messageId: 3,
    role: 'assistant',
    content: '抱歉，生成回答时发生了错误，请重试。',
    status: 'error',
  };

  const userMsg = {
    id: '4',
    messageId: 4,
    role: 'user',
    content: '你好，请帮我解释一下什么是 Vue 3 的组合式 API',
    status: 'complete',
  };

  const infoMsg = {
    id: '5',
    messageId: 5,
    role: 'info',
    content: '以下是新的对话',
    status: 'complete',
  };

  const reasoningMsg = {
    id: '6',
    messageId: 6,
    role: 'reasoning',
    content: [
      '用户询问的是 Vue 3 的组合式 API，这是一个前端框架的核心概念...',
      '需要从以下几个方面解释：1. 什么是组合式 API；2. 与选项式 API 的区别；3. 核心函数介绍',
      '补充代码示例会更清晰直观，选择 useCounter 作为示例...',
    ],
    status: 'complete',
    duration: 3200,
  };

  const toolMsg = {
    id: '7',
    messageId: 7,
    role: 'tool',
    content: JSON.stringify({
      result: 'success',
      data: {
        city: '北京',
        temperature: 22,
        humidity: 45,
        weather: '晴',
        wind: '东北风 3 级',
      },
    }, null, 2),
    status: 'complete',
    toolCallId: 'call_weather_001',
    duration: 1200,
  };

  const activityMsg = {
    id: '8',
    messageId: 8,
    role: 'activity',
    content: {
      content: '从知识库检索到 Vue 3 组合式 API 相关文档',
      referenceDocument: [
        { name: 'Vue 3 官方文档 - 组合式 API 简介', url: 'https://cn.vuejs.org/guide/extras/composition-api-faq.html', originFile: 'composition-api-faq.html' },
        { name: 'Vue 3 迁移指南', url: 'https://v3-migration.vuejs.org/zh/', originFile: 'migration.html' },
      ],
    },
    status: 'complete',
    activityType: 'knowledge_rag',
  };

  const loadingMsg = {
    id: '9',
    messageId: 9,
    role: 'loading',
    content: '',
    status: 'pending',
  };

  const handleAction = async (tool) => {
    console.log('消息操作:', tool.id, tool);
  };
</script>

# MessageRender 消息渲染器

> **层级**：分子组件 · **功能域**：消息展示

统一的消息渲染入口，通过 `message.role` 字段自动派发到对应的子组件。整个渲染过程由一个 `computed` 属性完成，无额外状态。

## 渲染架构

```
MessageRender
│
├── props.message.role
│     │
│     ├── 'user'       → UserMessage（转发 message + onAction / onInputConfirm /
│     │                               onShortcutConfirm / messageToolsStatus / tippyOptions）
│     │
│     ├── 'assistant'  → AssistantMessage（转发 message + default slot）
│     │                    └── default slot 默认回退到 ContentRender
│     │
│     ├── 'info'       → InfoMessage（转发 message）
│     ├── 'reasoning'  → ReasoningMessage（转发 message）
│     ├── 'tool'       → ToolMessage（转发 message）
│     ├── 'activity'   → ActivityMessage（转发 message）
│     ├── 'loading'    → LoadingMessage（转发 message）
│     │
│     └── 其他 / 未知   → null（不渲染任何内容）
```

> **重要**：`onAction`、`onInputConfirm`、`onShortcutConfirm`、`messageToolsStatus`、`tippyOptions` 这五个 prop **只转发给 `UserMessage`**。`AssistantMessage` 的工具栏由 `MessageContainer` 的 `MessageTools` 组件管理，`MessageRender` 不负责传递。

## 基础用法

```vue
<template>
  <MessageRender
    :message="message"
    :on-action="handleAction"
  />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus, type Message, type IToolBtn } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Assistant,
    content: '你好！我是 AI 助手，有什么可以帮你的吗？',
    status: MessageStatus.Complete,
  };

  const handleAction = async (tool: IToolBtn) => {
    console.log('消息操作:', tool.id);
  };
</script>
```

**渲染效果**

<div class="demo">
  <MessageRenderComp :message="assistantMsg" :on-action="handleAction" />
</div>

## 各角色消息

### 用户消息（user）

`onAction`、`onInputConfirm`、`onShortcutConfirm`、`messageToolsStatus` 在此角色下生效。

```vue
<script setup lang="ts">
  import { MessageRole, MessageStatus, type Message, type IToolBtn, type TagSchema } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.User,
    content: '你好，请帮我解释一下什么是 Vue 3 的组合式 API',
    status: MessageStatus.Complete,
  };

  const handleAction = async (tool: IToolBtn) => {
    console.log('用户消息操作:', tool.id); // delete / copy 等
  };
  const handleInputConfirm = async (content: Message['content'], docSchema: TagSchema) => {
    console.log('编辑确认:', content);
  };
  const handleShortcutConfirm = async (formModel: Record<string, unknown>) => {
    console.log('快捷指令提交:', formModel);
  };
</script>
```

**渲染效果**

<div class="demo">
  <MessageRenderComp :message="userMsg" :on-action="handleAction" />
</div>

### AI 助手消息（assistant）

`message` 中的全部字段（含 `toolCalls`）直接透传给 `AssistantMessage`。

```vue
<script setup lang="ts">
  import { MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '2',
    messageId: '2',
    role: MessageRole.Assistant,
    content: `## Vue 3 组合式 API\n\n**组合式 API** 是 Vue 3 引入的一种新方式...`,
    status: MessageStatus.Complete,
  };
</script>
```

**渲染效果**

<div class="demo">
  <MessageRenderComp :message="assistantMsg" :on-action="handleAction" />
</div>

### 信息消息（info）

`content` 为字符串或字符串数组，渲染居中虚线分隔条。

<div class="demo">
  <MessageRenderComp :message="infoMsg" />
</div>

### 推理消息（reasoning）

`content` 为字符串数组，`duration` 为推理耗时（毫秒）。

<div class="demo">
  <MessageRenderComp :message="reasoningMsg" />
</div>

### 工具调用结果（tool）

在 `MessageContainer` 中通常不独立渲染（被注入到 AssistantMessage），单独使用时如下：

<div class="demo">
  <MessageRenderComp :message="toolMsg" />
</div>

### 活动消息（activity）

<div class="demo">
  <MessageRenderComp :message="activityMsg" />
</div>

### 加载消息（loading）

由 `MessageContainer` 自动注入，无需手动使用。

<div class="demo">
  <MessageRenderComp :message="loadingMsg" />
</div>

## 消息状态

### 流式输出（streaming）

`status: 'streaming'` 时，`AssistantMessage` 内部展示打字光标，内容可实时追加：

```vue
<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';

  const message = ref<Message>({
    id: '1',
    messageId: '1',
    role: MessageRole.Assistant,
    content: '',
    status: MessageStatus.Streaming,
  });

  // 模拟流式输出：逐步追加内容
  const chunks = ['正在', '为你', '生成', '答案...'];
  let i = 0;
  const timer = setInterval(() => {
    if (i < chunks.length) {
      message.value.content += chunks[i++];
    } else {
      message.value.status = MessageStatus.Complete;
      clearInterval(timer);
    }
  }, 300);
</script>
```

**渲染效果**

<div class="demo">
  <MessageRenderComp :message="assistantStreamingMsg" />
</div>

### 错误状态（error）

```vue
<script setup lang="ts">
  import { MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Assistant,
    content: '抱歉，生成回答时发生了错误，请重试。',
    status: MessageStatus.Error,
  };
</script>
```

**渲染效果**

<div class="demo">
  <MessageRenderComp :message="assistantErrorMsg" :on-action="handleAction" />
</div>

## 自定义内容渲染（default slot）

`default` slot **仅对 `role: 'assistant'` 生效**，用于替换默认的 `ContentRender`。未提供 slot 时回退渲染 `<ContentRender :content="message.content" :status="message.status" />`。

```vue
<template>
  <MessageRender
    :message="message"
    :on-action="handleAction"
  >
    <template #default="{ content, status }">
      <!-- 完全接管内容区域渲染 -->
      <MyMarkdownRenderer
        :content="content"
        :streaming="status === 'streaming'"
      />
    </template>
  </MessageRender>
</template>
```

slot 参数类型与 `AssistantMessage` 的 slot 保持一致（`Partial<AssistantMessage>`），主要使用：

| 参数      | 类型            | 说明         |
| --------- | --------------- | ------------ |
| `content` | `string`        | 消息内容     |
| `status`  | `MessageStatus` | 当前消息状态 |

## 与 MessageContainer 配合

在 `MessageContainer` 的 `default` slot 中使用，可替换默认的 `MessageRender` 渲染逻辑：

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="messageStatus"
    :on-agent-action="handleAgentAction"
    :on-user-action="handleUserAction"
    @stop-streaming="handleStopStreaming"
  >
    <template #default="{ message, messageToolsStatus }">
      <!-- 自定义 MessageRender 的行为 -->
      <MessageRender
        :message="message"
        :message-tools-status="messageToolsStatus"
        :on-action="handleUserAction"
        :on-input-confirm="handleInputConfirm"
      >
        <template
          v-if="message.role === 'assistant'"
          #default="{ content, status }"
        >
          <MyCustomContent
            :content="content"
            :status="status"
          />
        </template>
      </MessageRender>
    </template>
  </MessageContainer>
</template>
```

## API

### Props

| 属性名             | 类型                                                                       | 默认值 | 说明                                              |
| ------------------ | -------------------------------------------------------------------------- | ------ | ------------------------------------------------- |
| message            | `Partial<Message>`                                                         | —      | **必填**，消息对象，`role` 字段决定渲染哪个子组件 |
| messageToolsStatus | `MessageToolsStatus`                                                       | —      | 工具按钮状态；**仅转发给 `UserMessage`**          |
| onAction           | `(tool: IToolBtn) => Promise<string[] \| void>`                            | —      | 工具操作回调；**仅转发给 `UserMessage`**          |
| onInputConfirm     | `(content: UserMessage['content'], docSchema: TagSchema) => Promise<void>` | —      | 用户编辑确认回调；**仅转发给 `UserMessage`**      |
| onShortcutConfirm  | `(formModel: Record<string, unknown>) => Promise<void>`                    | —      | 用户快捷指令提交回调；**仅转发给 `UserMessage`**  |
| tippyOptions       | `Partial<Omit<TippyOptions, 'getReferenceClientRect' \| 'triggerTarget'>>` | —      | 自定义 Tippy 配置；**仅转发给 `UserMessage`**     |

### Slots

| 插槽名     | 参数                                         | 说明                                                                                                    |
| ---------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| codeHeader | `{ language: string; token: Token[] }`       | 代码块头部自定义操作区域，透传给 ContentRender → MarkdownContent → CodeContent；**仅对 assistant 生效** |
| default    | `{ content: string, status: MessageStatus }` | 替换 AssistantMessage 的内容区域渲染；**仅对 `role: 'assistant'` 生效**                                 |

## 消息类型映射

| `MessageRole` | 渲染组件           | prop 路由                                                                                               | 说明                  |
| ------------- | ------------------ | ------------------------------------------------------------------------------------------------------- | --------------------- |
| `user`        | `UserMessage`      | `message` + `onAction` + `onInputConfirm` + `onShortcutConfirm` + `messageToolsStatus` + `tippyOptions` | 用户发送的消息        |
| `assistant`   | `AssistantMessage` | `message` + `default slot`                                                                              | AI 助手回复消息       |
| `info`        | `InfoMessage`      | `message`                                                                                               | 系统信息 / 会话分隔符 |
| `reasoning`   | `ReasoningMessage` | `message`                                                                                               | AI 思考过程（可折叠） |
| `tool`        | `ToolMessage`      | `message`                                                                                               | 工具调用返回结果      |
| `activity`    | `ActivityMessage`  | `message`                                                                                               | 知识检索 / 引用文档   |
| `loading`     | `LoadingMessage`   | `message`（字段被忽略，组件无 Props）                                                                   | 等待响应的加载占位    |
| 其他 / 未知   | —                  | —                                                                                                       | 返回 `null`，不渲染   |

## 类型定义

```typescript
import { MessageRole, MessageStatus, MessageToolsStatus, type Message, type IToolBtn } from '@blueking/chat-x';

// 消息角色
enum MessageRole {
  User = 'user',
  Assistant = 'assistant',
  Info = 'info',
  Reasoning = 'reasoning',
  Tool = 'tool',
  Activity = 'activity',
  Loading = 'loading',
}

// 消息状态
enum MessageStatus {
  Pending = 'pending',
  Streaming = 'streaming',
  Complete = 'complete',
  Error = 'error',
  Stop = 'stop',
  Disabled = 'disabled',
}

// 工具按钮状态（仅转发给 UserMessage）
enum MessageToolsStatus {
  Disabled = 'disabled',
  Hidden = 'hidden',
}
```

## 关联组件

- [MessageContainer](./message-container.md) — 内部按组调用以渲染每条消息
- [AssistantMessage](./assistant-message.md) — assistant 角色派发目标
- [UserMessage](./user-message.md) — user 角色派发目标
