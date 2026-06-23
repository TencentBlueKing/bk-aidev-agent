# UserQuestionAnsweredCard 用户问题回答回显

> 能力域：Agent 能力 ｜ 导入：`import { UserQuestionAnsweredCard } from '@blueking/chat-x'` ｜ since 1.0.0

在 UserQuestion resume 成功后回显用户回答或取消状态。 源码位置：src/components/chat-message/interrupt-message/user-question/user-question-answered-card.vue。

**关联**：interrupt-message（outcome.success 且 reason 为 UserQuestion 时挂载本组件）、user-question-card（待回答面板，与本组件成对出现）

---

# UserQuestionAnsweredCard 用户问题回答回显

> **能力域**：Agent 能力

## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/user-question/user-question-answered-card.vue`
- **能力说明**：在 UserQuestion resume 成功后回显用户回答或取消状态。

由 [InterruptMessageRender](/components/agent/interrupt-message) 在 `content.outcome.type === 'success'` 且 `result.reason === InterruptReason.UserQuestion` 时渲染。默认逐条展示选择题答案；业务可通过 `#answer` slot 自定义回显形态（如自定义表单字段）。

## 基础用法

```vue
<template>
  <UserQuestionAnsweredCard
    :answers="answers"
    status="resolved"
  />
</template>

<script setup lang="ts">
  import { UserQuestionAnsweredCard, type UserQuestionAnswerItem } from '@blueking/chat-x';

  const answers: UserQuestionAnswerItem[] = [
    {
      question: '你希望采用哪种实现？',
      multiSelect: false,
      answer: [{ label: 'optimized', description: '优化版' }],
    },
  ];
</script>
```

**渲染效果**

## 已取消（跳过）

```vue
<UserQuestionAnsweredCard
  :answers="[]"
  status="cancelled"
/>
```

**渲染效果**

## 自定义回显（#answer slot）

当待回答阶段使用了自定义 `#question` 表单时，可通过 `#answer` slot 自定义回显：

```vue
<UserQuestionAnsweredCard
  :answers="answers"
  status="resolved"
>
  <template #answer="{ item, index, status }">
    <MyCustomAnswerView :data="item" :index="index" :status="status" />
  </template>
</UserQuestionAnsweredCard>
```

`InterruptMessageRender`、`MessageRender`、`MessageContainer` 提供 `#answeredQuestion` slot，参数与 `#answer` 一致，逐层透传至本组件。使用 `ChatContainer` 时若覆盖了 `#message` 插槽，需在自定义 `MessageRender` 中继续透传 `#answeredQuestion`。

## API

### Props

| 属性名  | 类型                         | 默认值       | 说明                                   |
| ------- | ---------------------------- | ------------ | -------------------------------------- |
| answers | `UserQuestionAnswerItem[]`   | —            | **必填**，已回答内容列表               |
| status  | `'resolved' \| 'cancelled'` | `'resolved'` | resume 状态：`resolved` 已回复，`cancelled` 已取消（跳过） |

### Slots

| 插槽名 | 参数                                              | 说明                                                         |
| ------ | ------------------------------------------------- | ------------------------------------------------------------ |
| answer | `{ item, index, status }`                         | 自定义单题回答回显；未覆盖时默认渲染 `answer[].description \|\| label` |

| 参数   | 类型                              | 说明                     |
| ------ | --------------------------------- | ------------------------ |
| item   | `UserQuestionAnswerItem`          | 当前题的回答数据         |
| index  | `number`                          | 题目序号（从 0 开始）    |
| status | `'resolved' \| 'cancelled'`      | 与 Props.status 一致     |

### Events / Expose

无。

## 关联文档

- [InterruptMessage 中断消息](/components/agent/interrupt-message)
- [UserQuestionCard 用户问题中断](/components/agent/user-question-card)
- [中断类型 Interrupt](../../types/interrupt.md)
