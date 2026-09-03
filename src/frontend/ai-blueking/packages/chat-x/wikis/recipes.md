---
name: 用例食谱
slug: recipes
category: guide
description: >
  场景驱动的快速参考，每个场景给出组件组合和最小代码示例。
aiSummary: >
  用例食谱提供 11 个常见场景的快速实现指南，每个场景包含所需组件列表和最小代码。
  场景覆盖基础对话、流式输出、工具调用、知识库检索、推理展示、快捷指令、
  划词选择、文件上传、图片预览、多选导出、自定义消息类型。
relatedComponents: []
sinceVersion: '1.0.0'
---

# 用例食谱

以下为常见集成场景的**最小思路**与示例片段；实际项目请补齐类型、错误处理与业务接口。

### 基础对话

**所需组件**：`ChatInput` + `MessageContainer` + `useMessageGroup`

最简对话：输入区展示消息列表，业务维护 `messages` 并分组后传入容器。

```vue
<script setup lang="ts">
  import { ChatInput, MessageContainer, useMessageGroup, MessageStatus, type Message } from '@blueking/chat-x';
  import { computed, ref as deepRef } from 'vue';

  const messages = deepRef<Message[]>([]);
  const messageStatus = deepRef(MessageStatus.Complete);
  const input = deepRef('');
  const selectedUserMessages = deepRef<Message[]>([]);
  const { messageGroups } = useMessageGroup({
    messages: computed(() => messages.value),
    selectedUserMessages,
  });

  async function onSend() {
    /* 写入用户消息并请求模型，更新 messages */
  }
</script>

<template>
  <MessageContainer
    :messages="messages"
    :message-groups="messageGroups"
    :message-status="messageStatus"
  />
  <ChatInput
    v-model="input"
    :message-status="messageStatus"
    :on-send-message="onSend"
  />
</template>
```

### 流式输出

**所需组件**：`ChatInput` + `MessageContainer` + `MessageStatus`

流式过程中将 `messageStatus` 设为 `MessageStatus.Streaming`，输入区会呈现停止生成；停止时触发 `MessageContainer` 的 `stopStreaming` 或业务中断请求。

```vue
<script setup lang="ts">
  import { MessageContainer, MessageStatus } from '@blueking/chat-x';
  import { ref as deepRef } from 'vue';

  const messageStatus = deepRef(MessageStatus.Streaming);
  function stop() {
    messageStatus.value = MessageStatus.Stop;
  }
</script>

<template>
  <MessageContainer
    :messages="[]"
    :message-groups="[]"
    :message-status="messageStatus"
    @stop-streaming="stop"
  />
</template>
```

### 工具调用

**所需组件**：`AssistantMessage`（`toolCalls`）+ `ToolMessage`（注入到 `toolCall.toolMessage`）

在助手消息上声明 `toolCalls`；`useMessageGroup` 会将后续 `Tool` 角色消息挂到对应 `toolCall` 上。

```vue
<script setup lang="ts">
  import { MessageContentType, MessageRole, MessageStatus, type AssistantMessage } from '@blueking/chat-x';

  const assistant: AssistantMessage = {
    id: 1,
    messageId: 1,
    role: MessageRole.Assistant,
    content: '',
    status: MessageStatus.Complete,
    toolCalls: [
      {
        id: 'call-1',
        type: MessageContentType.Function,
        function: { name: 'getWeather', arguments: '{}' },
      },
    ],
  };
</script>
```

### 知识库检索

**所需组件**：`ActivityMessage` + `activityType: MessageContentType.KnowledgeRag`

用于展示检索过程与引用片段，内容结构需符合 `KnowledgeRagMessageContent`。

```vue
<script setup lang="ts">
  import { MessageContentType, MessageRole, MessageStatus, type ActivityMessage } from '@blueking/chat-x';

  const rag: ActivityMessage = {
    id: 1,
    messageId: 1,
    role: MessageRole.Activity,
    activityType: MessageContentType.KnowledgeRag,
    content: { content: '检索摘要…', referenceDocument: [] },
    status: MessageStatus.Complete,
  };
</script>
```

### 推理展示

**所需组件**：`ReasoningMessage`（由 `MessageRender` 根据消息角色渲染）

将一条消息的 `role` 设为 `MessageRole.Reasoning`，`content` 为字符串数组（推理步骤）；组件侧支持折叠/展开（详见 `ReasoningMessage` 组件文档）。

```vue
<script setup lang="ts">
  import { MessageRole, MessageStatus, type ReasoningMessage } from '@blueking/chat-x';

  const reasoning: ReasoningMessage = {
    id: 1,
    messageId: 1,
    role: MessageRole.Reasoning,
    content: ['第一步…', '第二步…'],
    status: MessageStatus.Complete,
  };
</script>
```

### 快捷指令

**所需组件**：`ShortcutBtns`（内置于 `ChatInput`）+ `ShortcutRender` + `ChatInput`

选择快捷指令后由 `ShortcutRender` 渲染表单，提交后通过 `@shortcutSubmit` / `onUserShortcutConfirm` 写回业务与输入区。

```vue
<script setup lang="ts">
  import { ChatContainer, type Shortcut } from '@blueking/chat-x';
  import { ref as deepRef } from 'vue';

  const input = deepRef('');
  const shortcuts = deepRef<Shortcut[]>([]);
</script>

<template>
  <ChatContainer
    v-model="input"
    :messages="[]"
    :shortcuts="shortcuts"
    :on-send-message="async () => {}"
  />
</template>
```

### 划词选择

**所需组件**：`AiSelection`

监听文档级选区并在气泡中展示快捷指令；**同一页面建议只挂载一个** `AiSelection`，并绑定 `v-model:visible`。

```vue
<script setup lang="ts">
  import { AiSelection } from '@blueking/chat-x';
  import { ref as deepRef } from 'vue';

  const visible = deepRef(false);
</script>

<template>
  <AiSelection v-model:visible="visible" />
</template>
```

### 文件上传

**所需组件**：`ChatInput`（`onUpload` + 内部 `uploadFiles` / `UserMessage` 的 `inputContent`）

为 `ChatInput` 提供 `onUpload`，返回带 `download_url` 的结果；发送消息时由组件将文件并入用户消息内容。

```vue
<script setup lang="ts">
  import { ChatInput, MessageStatus } from '@blueking/chat-x';
  import { ref as deepRef } from 'vue';

  const input = deepRef('');
  async function onUpload(files: File[]) {
    return files.map(file => ({ download_url: URL.createObjectURL(file) }));
  }
</script>

<template>
  <ChatInput
    v-model="input"
    :message-status="MessageStatus.Complete"
    :on-upload="onUpload"
    :on-send-message="async () => {}"
  />
</template>
```

### 图片预览

**所需组件**：`AiImage` + `ImagePreviewGroup`

在 `ImagePreviewGroup` 包裹下使用多个 `AiImage`，点击缩略图进入组内多图预览。

```vue
<script setup lang="ts">
  import { AiImage, ImagePreviewGroup } from '@blueking/chat-x';
</script>

<template>
  <ImagePreviewGroup>
    <AiImage src="https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400" />
    <AiImage src="https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400" />
  </ImagePreviewGroup>
</template>
```

### 多选导出

**所需组件**：`MessageContainer`（`enableSelection` + `v-model:selected-user-messages`）+ `SelectionFooter`

开启多选后由容器维护勾选状态；底部用 `SelectionFooter` 做全选、取消与确认（导出逻辑由业务在 `@confirm` 中实现）。

```vue
<script setup lang="ts">
  import { MessageContainer, SelectionFooter, MessageStatus, useMessageGroup, type Message } from '@blueking/chat-x';
  import { computed, ref as deepRef } from 'vue';

  const messages = deepRef<Message[]>([]);
  const selectedUserMessages = deepRef<Message[]>([]);
  const { messageGroups } = useMessageGroup({
    messages: computed(() => messages.value),
    selectedUserMessages,
  });
</script>

<template>
  <MessageContainer
    v-model:selected-user-messages="selectedUserMessages"
    enable-selection
    :messages="messages"
    :message-groups="messageGroups"
    :message-status="MessageStatus.Complete"
  />
  <SelectionFooter
    :is-all-selected="false"
    :selected-count="selectedUserMessages.length"
    @cancel="() => {}"
    @confirm="() => {}"
    @toggle-all="() => {}"
  />
</template>
```

### 自定义消息类型

**所需组件**：`MessageContainer` 默认插槽 + `MessageRender` + `declare global` 扩展 `AIBluekingMessageMap`

在全局合并接口中注册自定义消息形状；在 `MessageContainer` 的 `#default` 中按 `message` 分支，未覆盖的类型交给 `MessageRender`。

```vue
<script setup lang="ts">
  import { MessageContainer, MessageRender, useMessageGroup, MessageStatus, type Message } from '@blueking/chat-x';
  import { computed, ref as deepRef } from 'vue';

  declare global {
    interface AIBluekingMessageMap {
      // 在此合并自定义角色与消息类型，例如：
      // [MessageRole.Custom]: MyCustomMessage;
    }
  }

  const messages = deepRef<Message[]>([]);
  const selectedUserMessages = deepRef<Message[]>([]);
  const { messageGroups } = useMessageGroup({
    messages: computed(() => messages.value),
    selectedUserMessages,
  });
</script>

<template>
  <MessageContainer
    :messages="messages"
    :message-groups="messageGroups"
    :message-status="MessageStatus.Complete"
  >
    <template #default="{ message }">
      <MessageRender :message="message" />
    </template>
  </MessageContainer>
</template>
```
