# QuestionsContainer 问题容器占位

> 能力域：辅助能力 ｜ 导入：`import { QuestionsContainer } from '@blueking/chat-x'` ｜ since 1.0.0

源码为空文件，没有 props、emits、slots 或渲染能力；不建议作为功能组件使用。 源码位置：src/components/ai-questions/questions-container.vue。

**关联**：user-question-card（用户问题中断交互请使用实际可渲染的问题卡片组件）、user-question-option（用户问题选项行由实际中断组件承载）、interrupt-message（HITL 中断消息由 InterruptMessage 分发到具体问题组件）

---

# QuestionsContainer 问题容器占位

> **能力域**：辅助能力

`QuestionsContainer` 当前只是保留在源码目录中的空文件，占位路径为 `src/components/ai-questions/questions-container.vue`。它没有模板、脚本、样式、props、emits、slots 或任何渲染行为。

本文档保留该条目，是为了在组件总览和 MCP 文档检索中明确说明：它不是当前可用能力。

## 源码事实

- **源码位置**：`src/components/ai-questions/questions-container.vue`
- **文件大小**：`0` 字节
- **能力说明**：源码为空文件，没有 props、emits、slots 或渲染能力；不建议作为功能组件使用。

## 当前状态

| 项目     | 状态 |
| -------- | ---- |
| 模板     | 无   |
| 脚本逻辑 | 无   |
| 样式     | 无   |
| Props    | 无   |
| Emits    | 无   |
| Slots    | 无   |
| Expose   | 无   |

## 不可用示例

下面的写法不会产生任何可见 UI，也不会承载问题列表逻辑：

```vue
<template>
  <!-- 不建议使用：当前组件为空文件 -->
  <QuestionsContainer />
</template>
```

## 推荐替代

如果要展示用户问题中断或选项交互，请使用已经实现的中断消息组件链路：

```vue
<template>
  <InterruptMessage :message="message" />
</template>
```

或在具体场景中使用：

- [InterruptMessage](../agent/interrupt-message.md) — 中断消息分发入口。
- [UserQuestionCard](../agent/user-question-card.md) — 用户问题中断交互面板。
- [UserQuestionOption](../agent/user-question-option.md) — 用户问题选项行。

## API

### Props

- 无。

### Emits

- 无。

### Slots

- 无。

### Expose

- 无。

## 使用建议

- 不建议在业务中使用该组件。
- 如果后续补齐实现，需要同步更新本文档的能力说明、示例、API 与关联组件。
