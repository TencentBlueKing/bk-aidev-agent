# ReasoningMessage 推理消息

> 能力域：消息系统 ｜ 未从包入口导出：内部组件（入口的同名导出是 TS 类型，不是组件） ｜ since 0.0.20

渲染推理过程，覆盖加载、错误与 Markdown 内容展示。 源码位置：src/components/chat-message/reasoning-message/reasoning-message.vue。

**关联**：message-render（由 MessageRender 在 role 为 reasoning 时创建）、assistant-message（推理结束后通常紧跟 Assistant 的正式回复）、markdown-content（内容区通过 Markdown 渲染推理文本）

---

# ReasoningMessage 推理消息

## 源码事实

- **源码位置**：`src/components/chat-message/reasoning-message/reasoning-message.vue`
- **能力域**：消息系统
- **能力说明**：渲染推理过程，覆盖加载、错误与 Markdown 内容展示。

> **导出说明**：`ReasoningMessage` **未**从包入口导出（入口同名是 TS interface）。消费方经 `MessageRender` / `MessageContainer` 使用。下文 `ReasoningMessageComp` 为文档站内部示例。

AI 思维链（Chain-of-Thought）推理过程展示组件。由**可点击标题栏**和**内容区域**组成，内容区支持 Markdown 渲染。`duration` 传入后自动折叠一次，用户可随时点击标题展开/收起。

## 组件结构

```
┌─────────────────────────────────────────────────┐
│  .ai-reasoning-message-title（可点击，toggle 折叠）│
│  ┌──────┐  标题文案（思考中/已思考完成/思考失败）  ▶ │
│  │ 加载图标│                               折叠图标 │
│  └──────┘                                        │
└─────────────────────────────────────────────────┘
▼ 展开时显示（v-show）
┌─────────────────────────────────────────────────┐
│  .ai-reasoning-message-content                  │
│  <MarkdownContent> × content.length              │
│  （Error 时改为 CommonErrorContent）              │
│  .ai-markdown-body { color: #979ba5 }（灰色文字）   │
└─────────────────────────────────────────────────┘
```

## 基础用法

```vue
<template>
  <MessageRender :message="message" />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.Reasoning,
    status: MessageStatus.Complete,
    content: ['让我分析一下这个问题...', '首先需要考虑以下几个方面...'],
  };
</script>
```

**渲染效果**

## 状态与视觉效果

| `status`                       | 标题文案           | 加载图标      | 标题 CSS 类   |
| ------------------------------ | ------------------ | ------------- | ------------- |
| `pending` / `streaming` / 其他 | 思考中             | `AiLoading` ✓ | `is-thinking` |
| `complete` / `success`         | 已思考完成（耗时） | 无            | `is-complete` |
| `error`                        | 思考失败           | 无            | `is-error`    |

> **说明**：`streaming` 通过 `switch` 的 `default` 分支显示"思考中"，与 `pending` 效果相同。

### 思考中（pending / streaming）

### 完成状态（带耗时）

`duration` 传入后：

1. 标题显示"已思考完成 (耗时：x.xs)"
2. **自动折叠一次**（watch 触发后 `stop()`，后续不再自动折叠）
3. 用户点击标题可重新展开

### 错误状态（error）

`status: 'error'` 时，标题显示"思考失败"，内容区改为 `CommonErrorContent` 渲染（将 `content` 数组 join `\n` 后传入）：

## 折叠控制

### 自动折叠机制

组件内部 watch `duration` prop（`{ immediate: true }`）：

- 当 `duration` **首次变为真值**时，将 `collapsed` 设为 `true` 并停止 watcher
- **一次性行为**：watcher 停止后，后续 `duration` 变化不再触发自动折叠

```typescript
// 组件内部逻辑（简化）
const { stop } = watch(
  () => props.duration,
  async duration => {
    if (duration) {
      collapsed.value = true;
      await nextTick();
      stop?.(); // 停止 watcher，后续 duration 变化不再自动折叠
    }
  },
  { immediate: true },
);
```

### 手动控制折叠状态

通过 `v-model:collapsed` 从外部读取或设置折叠状态：

```vue
<!-- 文档站内部示例：组件本体支持 v-model:collapsed；消费方一般经 MessageRender 渲染 -->
<template>
  <button @click="collapsed = !collapsed">
    {{ collapsed ? '展开推理' : '收起推理' }}
  </button>
  <ReasoningMessageComp
    v-model:collapsed="collapsed"
    :content="content"
    :status="status"
    :duration="duration"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageStatus } from '@blueking/chat-x';

  const collapsed = ref(false);
  const status = MessageStatus.Complete;
  const duration = 2800;
  const content = ['经过分析，结论如下...', '具体原因是...'];
</script>
```

## 在 MessageContainer 中使用

`MessageContainer` 会自动将 `role: 'reasoning'` 的消息渲染为 `ReasoningMessage`，无需手动引入：

```vue
<script setup lang="ts">
  import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';

  const messages = [
    {
      id: '1',
      messageId: '1',
      role: MessageRole.User,
      content: '如何实现 TypeScript 中的深拷贝？',
      status: MessageStatus.Complete,
    },
    {
      id: '2',
      messageId: '2',
      role: MessageRole.Reasoning,
      content: [
        '用户问的是 TypeScript 深拷贝，需要考虑几种常见方案...',
        'JSON.parse/stringify 有局限性（函数、循环引用等）...',
        'structuredClone 是更现代的选择，但需要注意兼容性...',
      ],
      status: MessageStatus.Complete,
      duration: 2800, // 毫秒，传入后自动折叠
    },
    {
      id: '3',
      messageId: '3',
      role: MessageRole.Assistant,
      content: 'TypeScript 中实现深拷贝有以下几种方式...',
      status: MessageStatus.Complete,
    },
  ];
</script>
```

## API

### Props

组件 Props 继承自 `Partial<ReasoningMessage>`：

| 属性名    | 类型                 | 说明                                                                           |
| --------- | -------------------- | ------------------------------------------------------------------------------ |
| content   | `string \| string[]` | 推理内容；字符串数组时每项独立渲染为 `MarkdownContent`；字符串时自动包装为数组 |
| status    | `MessageStatus`      | 消息状态，决定标题文案、加载图标和 CSS 类                                      |
| duration  | `number`             | 推理耗时（毫秒）；传入后标题追加耗时信息，并**触发一次自动折叠**               |
| id        | `number \| string`   | 消息 ID（接收但不使用）                                                        |
| messageId | `number \| string`   | 消息唯一标识（接收但不使用）                                                   |

### v-model

| 属性名    | 类型      | 默认值  | 说明                                                       |
| --------- | --------- | ------- | ---------------------------------------------------------- |
| collapsed | `boolean` | `false` | 内容折叠状态；`duration` 首次传入时组件内部自动设为 `true` |

### 状态说明

| `status`           | 标题文案                             | 加载图标 | 标题背景        |
| ------------------ | ------------------------------------ | -------- | --------------- |
| `pending`          | 思考中                               | ✓        | `#f0f1f5`       |
| `streaming` / 其他 | 思考中（default 分支）               | ✓        | `#f0f1f5`       |
| `complete`         | 已思考完成（含 duration 则追加耗时） | ✗        | `#f0f1f5`       |
| `success`          | 已思考完成（同 complete）            | ✗        | `#f0f1f5`       |
| `error`            | 思考失败                             | ✗        | `#fff0f0`（红） |

## 类型定义

```typescript
import { MessageRole, MessageStatus, type ReasoningMessage } from '@blueking/chat-x';

// ReasoningMessage 继承自 BaseMessage<MessageRole.Reasoning, string[]>
interface ReasoningMessage {
  id: string | number;
  messageId: string | number;
  role: MessageRole.Reasoning; // 'reasoning'
  status: MessageStatus;
  content: string[]; // TS 类型为 string[]，组件内部实际兼容 string
  duration?: number; // 推理耗时（毫秒）
  name?: string;
}
```

> `MessageStatus` 完整取值见 [常量枚举](../../types/constants)。本组件完成态识别 `complete` / `success`（与标题文案表一致）。

## 关联组件

- [MessageRender](/components/message/message-render) — reasoning 角色由其实例化
- [AssistantMessage](/components/message/assistant-message) — 推理后常接正式回答
- [MarkdownContent](/components/rendering/markdown-content) — 推理正文 Markdown 渲染
