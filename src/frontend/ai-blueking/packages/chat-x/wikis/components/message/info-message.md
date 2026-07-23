---
name: InfoMessage 信息消息
slug: info-message
kind: component
domain: message
description: 渲染居中的系统信息提示。
aiSummary: >
  渲染居中的系统信息提示。
  源码位置：src/components/chat-message/info-message/info-message.vue。
relatedComponents:
  - slug: message-render
    relation: 由 MessageRender 在 role 为 info 时创建
  - slug: message-container
    relation: 嵌入消息列表时由 MessageContainer 统一布局与滚动
sinceVersion: 0.0.20
---

<script lang="ts" setup>
  import InfoMessageComp from '../../../src/components/chat-message/info-message/info-message.vue'
</script>

# InfoMessage 信息消息

## 源码事实

- **源码位置**：`src/components/chat-message/info-message/info-message.vue`
- **能力域**：消息系统
- **能力说明**：渲染居中的系统信息提示。

> **导出说明**：`InfoMessage` **未**从包入口导出（入口同名是 TS interface）。消费方经 `MessageRender` / `MessageContainer` 使用。下文 `InfoMessageComp` 为文档站内部示例。

系统信息分隔组件，在聊天消息列表中以**居中虚线分隔条**的形式展示非对话类信息（会话重置、时间节点、状态变更等）。

## 视觉原理

组件通过 `height: 0` + `border-bottom: 1px dashed #dcdee5` 生成一条贯穿全宽的虚线，内容文字区域设置白色背景"浮"在虚线中央，形成"文字刻在分隔线上"的视觉效果：

```
───── ─ ─ 以下是新的对话 ─ ─ ─────
```

## 基础用法

`content` 传入字符串，渲染单行分隔信息：

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Info,
    content: '以下是新的对话',
    status: MessageStatus.Complete,
  };
</script>
```

**渲染效果**

<div class="demo">
  <InfoMessageComp content="以下是新的对话" />
</div>

## 多行信息

`content` 传入字符串数组时，每个元素渲染为一个独立的文字浮标，均居中排列在同一条虚线上：

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  // 运行时 content 兼容 string[]（TS 类型声明多为 string）
  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Info,
    content: ['会话已重置', '以下是新的对话'],
    status: MessageStatus.Complete,
  };
</script>
```

**渲染效果**

<div class="demo">
  <InfoMessageComp :content="['会话已重置', '以下是新的对话']" />
</div>

## 典型使用场景

**会话分隔**

<div class="demo">
  <InfoMessageComp content="以下是新的对话" />
</div>

**时间节点**

<div class="demo">
  <InfoMessageComp content="2024-01-15 14:30" />
</div>

**上下文清除**

<div class="demo">
  <InfoMessageComp :content="['上下文已清除', '新对话从这里开始']" />
</div>

## 在 MessageContainer 中使用

`InfoMessage` 通常不需要单独引入，`MessageContainer`（或 `MessageRender`）会对 `role: 'info'` 的消息自动渲染：

```vue
<template>
  <MessageContainer :messages="messages" />
</template>

<script setup lang="ts">
  import { MessageContainer, MessageRole, MessageStatus } from '@blueking/chat-x';

  const messages = [
    {
      id: '1',
      messageId: '1',
      role: MessageRole.User,
      content: '请帮我分析一下这份报告。',
      status: MessageStatus.Complete,
    },
    // info 消息：role 为 'info'，content 为字符串
    {
      id: '2',
      messageId: '2',
      role: MessageRole.Info, // 'info'
      content: '上下文已达上限，已自动清除历史对话',
      status: MessageStatus.Complete,
    },
    {
      id: '3',
      messageId: '3',
      role: MessageRole.Assistant,
      content: '好的，我来帮你分析这份报告...',
      status: MessageStatus.Complete,
    },
  ];
</script>
```

## API

### Props

组件 Props 继承自 `Partial<InfoMessage>`，所有字段均可选：

| 属性名    | 类型                 | 说明                                                               |
| --------- | -------------------- | ------------------------------------------------------------------ |
| content   | `string \| string[]` | 信息内容。字符串渲染单行，数组渲染多个文字浮标，均居中排列在虚线上 |
| id        | `number \| string`   | 消息 ID（接收但不使用，由 MessageContainer 管理）                  |
| messageId | `number \| string`   | 消息唯一标识（接收但不使用）                                       |
| status    | `MessageStatus`      | 消息状态（接收但不使用，组件无状态相关渲染逻辑）                   |
| role      | `MessageRole.Info`   | 消息角色，固定为 `'info'`                                          |

> **说明**：`content` 的 TypeScript 类型定义为 `string`（与 `BaseMessage` 泛型一致），但组件模板内部通过 `Array.isArray(content) ? content : [content]` 实际兼容字符串数组。

## 安全性

`content` 通过 Vue 模板文本插值（`{{ text }}`）渲染，**不解析 HTML**，传入 `<script>` 等特殊字符会被转义为纯文本，无 XSS 风险。

## 类型定义

```typescript
import { MessageRole, MessageStatus } from '@blueking/chat-x';

// InfoMessage 继承自 BaseMessage<MessageRole.Info, string>
type InfoMessage = {
  id: number | string;
  messageId: number | string;
  role: MessageRole.Info; // 'info'
  status: MessageStatus;
  content: string; // TS 类型为 string，实际组件兼容 string[]
  name?: string;
};

enum MessageRole {
  Info = 'info',
  // ...
}
```

## 关联组件

- [MessageRender](/components/message/message-render) — info 角色由其实例化
- [MessageContainer](/components/setup/message-container) — 列表内嵌时的外层容器
