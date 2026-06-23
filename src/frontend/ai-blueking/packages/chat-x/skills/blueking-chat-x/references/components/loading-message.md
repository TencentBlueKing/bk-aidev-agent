# LoadingMessage 加载消息

> 能力域：消息系统 ｜ 导入：`import { LoadingMessage } from '@blueking/chat-x'` ｜ since 1.0.0

消息列表中的加载占位，默认使用 AiLoading，也支持默认插槽覆盖。 源码位置：src/components/chat-message/loading-message/loading-message.vue。

**关联**：message-container（在消息列表末尾自动追加 Loading 消息组）、message-render（role 为 loading 时由 MessageRender 渲染）、ai-loading（内部使用 AiLoading 基础组件）

---

# LoadingMessage 加载中消息
## 源码事实

- **源码位置**：`src/components/chat-message/loading-message/loading-message.vue`
- **能力域**：消息系统
- **能力说明**：消息列表中的加载占位，默认使用 AiLoading，也支持默认插槽覆盖。

> **能力域**：消息系统

加载等待状态组件，展示 AI 正在处理请求时的过渡动画。由旋转渐变环 + 脉冲星形图标（蓝→紫→粉渐变）和"请求中..."文案组成。支持通过默认插槽自定义加载文案。

> **提示**：此组件通常**不需要手动使用**，`MessageContainer` 会在满足条件时自动注入。

## 渲染效果

## 基础用法

组件无 Props，直接引入渲染即可：

```vue
<template>
  <LoadingMessage />
</template>

<script setup lang="ts">
  import { LoadingMessage } from '@blueking/chat-x';
</script>
```

## 自定义加载文案

通过默认插槽可覆盖默认的"请求中..."文案：

```vue
<template>
  <LoadingMessage>正在思考中，请稍候...</LoadingMessage>
</template>

<script setup lang="ts">
  import { LoadingMessage } from '@blueking/chat-x';
</script>
```

## 动画说明

`LoadingMessage` 内部使用 `AiLoading` 组件（18px），由两层动画叠加：

| 图层       | 动画                                | 周期 |
| ---------- | ----------------------------------- | ---- |
| 旋转渐变环 | `rotate(0 → 360deg)`，线性          | 0.8s |
| 脉冲星形   | `scale(0.5 → 1 → 0.5)`，ease-in-out | 0.8s |

颜色均使用线性渐变：`#235DFA`（蓝）→ `#8A77EC`（紫）→ `#EB8CEC`（粉）。

## 在 MessageContainer 中的自动注入

`MessageContainer` 在构建消息分组列表时，检测到**消息列表最后一条为用户消息**（`role === 'user'`）时，自动在末尾追加一个 Loading 消息组：

```typescript
// MessageContainer 内部逻辑（简化）
if (messages.at(-1)?.role === MessageRole.User) {
  list.push({
    messages: [
      {
        role: MessageRole.Loading, // 'loading'
        content: '',
        status: MessageStatus.Pending,
        id: 'loading',
        messageId: '',
      },
    ],
    type: MessageRole.Loading,
  });
}
```

当下一条 AI 消息（`role: 'assistant'`）到来后，最后一条不再是用户消息，Loading 组自动消失。

**触发示例**：

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="messageStatus"
    :on-agent-action="handleAgentAction"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageContainer, MessageRole, MessageStatus } from '@blueking/chat-x';

  const messageStatus = ref(MessageStatus.Pending);

  // 最后一条是 user 消息 → MessageContainer 自动追加 LoadingMessage
  const messages = ref([
    {
      id: '1',
      messageId: '1',
      role: MessageRole.User,
      content: '请帮我写一段 Vue 3 组合式 API 的示例代码',
      status: MessageStatus.Complete,
    },
  ]);

  const handleAgentAction = async () => {};
</script>
```

## 注意事项

- **无 Props**：`LoadingMessage` 组件内部没有 `defineProps`，`MessageRender` 向其传入 message 对象的字段均被忽略
- **默认插槽**：可通过默认插槽自定义加载文案，未传入时显示内置的 "请求中..."
- **i18n 支持**：默认文案 "请求中..." 通过内置 `t()` 函数处理，英文环境自动显示 "Requesting..."
- **选择模式**：`MessageContainer` 开启 `enableSelection` 时，Loading 消息组不显示复选框
- **自动生命周期**：Loading 组随消息列表变化自动插入/移除，无需手动控制

## API

### Props

组件无 Props。

> `MessageRender` 渲染 `role: 'loading'` 消息时会传入 message 对象字段，但 `LoadingMessage` 内部无 `defineProps`，所有传入字段均被忽略。

### Slots

| 插槽名  | 说明                                            |
| ------- | ----------------------------------------------- |
| default | 自定义加载文案，默认内容为 i18n 文案"请求中..." |

## 类型定义

```typescript
import { MessageRole, MessageStatus } from '@blueking/chat-x';

// MessageContainer 自动注入的 Loading 消息结构
type LoadingMessageData = {
  id: 'loading';
  messageId: '';
  role: MessageRole.Loading; // 'loading'
  content: '';
  status: MessageStatus.Pending;
};

enum MessageRole {
  Loading = 'loading',
  // ...
}
```

## 使用场景

- **等待 AI 响应**：用户消息发出后、AI 首个 token 到达前的过渡状态，由 `MessageContainer` 自动管理
- **手动控制场景**：在自定义聊天布局中手动展示加载态（直接引入即可，无需任何配置）
- **自定义文案**：通过默认插槽传入自定义加载提示文案，满足不同业务场景的文案需求

## 关联组件

- [MessageContainer](/components/setup/message-container) — 自动注入加载组
- [MessageRender](/components/message/message-render) — loading 角色派发
- [AiLoading](/components/helper/ai-loading) — 内部动画组件
