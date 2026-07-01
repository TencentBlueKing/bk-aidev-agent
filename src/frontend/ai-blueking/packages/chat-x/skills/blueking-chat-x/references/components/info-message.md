# InfoMessage 信息消息

> 能力域：消息系统 ｜ 导入：`import { InfoMessage } from '@blueking/chat-x'` ｜ since 1.0.0

渲染居中的系统信息提示。 源码位置：src/components/chat-message/info-message/info-message.vue。

**关联**：message-render（由 MessageRender 在 role 为 info 时创建）、message-container（嵌入消息列表时由 MessageContainer 统一布局与滚动）

---

# InfoMessage 信息消息
## 源码事实

- **源码位置**：`src/components/chat-message/info-message/info-message.vue`
- **能力域**：消息系统
- **能力说明**：渲染居中的系统信息提示。

> **能力域**：消息系统

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
  <InfoMessage :content="content" />
</template>

<script setup lang="ts">
  import { InfoMessage } from '@blueking/chat-x';

  const content = '以下是新的对话';
</script>
```

**渲染效果**

## 多行信息

`content` 传入字符串数组时，每个元素渲染为一个独立的文字浮标，均居中排列在同一条虚线上：

```vue
<template>
  <InfoMessage :content="['会话已重置', '以下是新的对话']" />
</template>

<script setup lang="ts">
  import { InfoMessage } from '@blueking/chat-x';
</script>
```

**渲染效果**

## 典型使用场景

**会话分隔**

**时间节点**

**上下文清除**

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
