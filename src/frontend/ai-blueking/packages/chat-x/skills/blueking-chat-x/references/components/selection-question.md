# SelectionQuestion 选择问题占位

> 能力域：辅助能力 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

源码为空文件，没有 props、emits、slots 或渲染能力；不建议作为功能组件使用。 源码位置：src/components/ai-questions/selection-question.vue。

**关联**：user-question-card（选择类问题交互请使用实际可渲染的问题卡片组件）、user-question-option（单个选项行由实际问题组件渲染）、interrupt-message（HITL 中断消息由 InterruptMessage 分发到具体问题组件）

---

# SelectionQuestion 选择问题占位

> **能力域**：辅助能力

`SelectionQuestion` 当前只是保留在源码目录中的空文件，占位路径为 `src/components/ai-questions/selection-question.vue`。它没有模板、脚本、样式、props、emits、slots 或任何选择交互能力。

本文档保留该条目，是为了明确它不是当前可用的问题选择组件，避免业务误接入。

## 源码事实

- **源码位置**：`src/components/ai-questions/selection-question.vue`
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

下面的写法不会产生选择题 UI，也不会发出确认事件：

```vue
<template>
  <!-- 不建议使用：当前组件为空文件 -->
  <SelectionQuestion />
</template>
```

## 推荐替代

选择类用户问题请走中断消息链路，由已实现的组件负责展示选项和处理确认：

```vue
<template>
  <UserQuestionCard
    :content="content"
    @confirm="handleConfirm"
  />
</template>
```

相关文档：

- [UserQuestionCard](../agent/user-question-card.md) — 用户问题中断交互面板。
- [UserQuestionOption](../agent/user-question-option.md) — 用户问题选项行。
- [InterruptMessage](../agent/interrupt-message.md) — 中断消息分发入口。

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
- 如果后续补齐实现，需要同步更新本文档的示例、选择交互事件、API 与关联组件。
