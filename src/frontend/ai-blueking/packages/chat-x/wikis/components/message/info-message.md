---
name: InfoMessage 信息消息
slug: info-message
kind: component
domain: message
description: 渲染居中的系统信息提示；带 fork_info 时渲染为分支会话的「从其他会话中继续」分隔线。
aiSummary: >
  渲染居中的系统信息提示；property.fork_info 存在时渲染为可点击的「从其他会话中继续」分隔线，点击回调 onForkSourceClick(forkInfo)。
  源码位置：src/components/chat-message/info-message/info-message.vue。
relatedComponents:
  - slug: message-render
    relation: 由 MessageRender 在 role 为 info 时创建
  - slug: message-container
    relation: 嵌入消息列表时由 MessageContainer 统一布局与滚动
sinceVersion: 0.0.20
exportStatus: internal
---

<script lang="ts" setup>
  import InfoMessageComp from '../../../src/components/chat-message/info-message/info-message.vue'

  const forkProperty = {
    fork_info: { source_session_code: 'a1b2c3d4', source_content_id: 1052, last_copied_content_id: 1053 },
  }
  const handleForkSourceClick = (forkInfo) => {
    console.log('fork source click', forkInfo)
  }
</script>

# InfoMessage 信息消息

## 源码事实

- **源码位置**：`src/components/chat-message/info-message/info-message.vue`
- **能力域**：消息系统
- **能力说明**：渲染居中的系统信息提示；`property.fork_info` 存在时渲染为分支会话的分叉点分隔线。

> **导出说明**：`InfoMessage` **未**从包入口导出（入口同名是 TS interface）。消费方经 `MessageRender` / `MessageContainer` 使用。下文 `InfoMessageComp` 为文档站内部示例。

系统信息分隔组件，在聊天消息列表中以**左右虚线夹中文案**的形式展示非对话类信息（会话重置、时间节点、状态变更等）。

## 视觉原理

根节点 `.ai-info-message` 为横向 flex：两侧通过 `::before` / `::after` 拉伸出虚线（主题边框色），中间 `.ai-info-message-body` 承载文案（主题次要文案色）。整块正常占位，避免旧实现 `height: 0` 导致内容被裁切遮挡：

```
─────── 以下是新的对话 ───────
```

多行时，多条 `.ai-info-message-content` 在 body 内纵向排列（`gap: 4px`），两侧虚线仍夹住整块文案区域。
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

`content` 传入字符串数组时，每个元素渲染为一行居中文案，在中间 body 内纵向排列，两侧虚线夹住整块区域：

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

## 分支会话分叉点

分支会话（由 AI 消息工具栏的「新建分支会话」创建）里，后端会写入一条 `role: 'info'` 且带 `property.fork_info` 的提示消息。识别到 `fork_info` 时，组件不再显示后端 `content`，改为渲染「分支图标 + 蓝色文案『从其他会话中继续』」的可点击分隔线（根节点追加 `is-fork`）。点击或回车时调用 `onForkSourceClick(forkInfo)`，由业务方据 `source_session_code` 切回来源会话。

```vue
<template>
  <MessageRender
    :message="message"
    :on-fork-source-click="handleForkSourceClick"
  />
</template>

<script setup lang="ts">
  import { type MessageForkInfo, MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '2001',
    messageId: '2001',
    role: MessageRole.Info,
    content: '其他会话中继续',
    status: MessageStatus.Complete,
    property: {
      fork_info: { source_session_code: 'a1b2c3d4', source_content_id: 1052, last_copied_content_id: 1053 },
    },
  };

  const handleForkSourceClick = (forkInfo: MessageForkInfo) => {
    // 切回 forkInfo.source_session_code；来源会话已删除时由业务方兜底（如进入新会话）
  };
</script>
```

**渲染效果**

<div class="demo">
  <InfoMessageComp
    content="其他会话中继续"
    :property="forkProperty"
    :on-fork-source-click="handleForkSourceClick"
  />
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
| content   | `string \| string[]` | 信息内容。字符串渲染单行；数组在中间区域纵向多行展示，两侧虚线夹住整块 |
| id        | `number \| string`   | 消息 ID（接收但不使用，由 MessageContainer 管理）                  |
| messageId | `number \| string`   | 消息唯一标识（接收但不使用）                                       |
| status    | `MessageStatus`      | 消息状态（接收但不使用，组件无状态相关渲染逻辑）                   |
| role      | `MessageRole.Info`   | 消息角色，固定为 `'info'`                                          |
| property  | `{ fork_info?: MessageForkInfo; ... }` | 消息属性。存在 `fork_info` 时渲染为「从其他会话中继续」分隔线，不再显示 `content` |
| onForkSourceClick | `(forkInfo: MessageForkInfo) => void` | 点击 / 回车分叉点分隔线时调用，参数为 `property.fork_info` |

> **说明**：`content` 的 TypeScript 类型定义为 `string`（与 `BaseMessage` 泛型一致），但组件模板内部通过 `Array.isArray(content) ? content : [content]` 实际兼容字符串数组。

## 安全性

`content` 通过 Vue 模板文本插值（`{{ text }}`）渲染，**不解析 HTML**，传入 `<script>` 等特殊字符会被转义为纯文本，无 XSS 风险。

## 类型定义

```typescript
import { MessageRole, MessageStatus } from '@blueking/chat-x';

// InfoMessage 继承自 BaseMessage<MessageRole.Info, string>
interface InfoMessage {
  id: number | string;
  messageId: number | string;
  role: MessageRole.Info; // 'info'
  status: MessageStatus;
  content: string; // TS 类型为 string，实际组件兼容 string[]
  name?: string;
  property?: BaseMessage['property'] & {
    /** 分支会话的分叉点提示；存在时渲染为「从其他会话中继续」分隔线 */
    fork_info?: MessageForkInfo;
  };
}

/** 分叉点信息，字段与后端 property.fork_info 一致 */
type MessageForkInfo = {
  last_copied_content_id?: number | string;
  source_content_id: number | string;
  source_session_code: string;
};

enum MessageRole {
  Info = 'info',
  // ...
}
```

## 关联组件

- [MessageRender](/components/message/message-render) — info 角色由其实例化
- [MessageContainer](/components/setup/message-container) — 列表内嵌时的外层容器
