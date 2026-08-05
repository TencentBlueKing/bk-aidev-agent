# UserQuestionCard 用户问题中断

> 能力域：Agent 能力 ｜ 导入：`import { UserQuestionCard } from '@blueking/chat-x'` ｜ since 1.0.0

渲染 UserQuestion 中断的待回答面板；一次一题分页切换，支持单选/多选、Others、跳过与已完成进度。源码位置：src/components/chat-message/interrupt-message/user-question/user-question-card.vue。

**关联**：interrupt-message（outcome.success 时挂载 UserQuestionAnsweredCard 回显回答）、chat-container（检测最近待回答 UserQuestion 并把 UserQuestionCard 放在输入区上方）、interrupt（定义 UserQuestionInterrupt 与 UserQuestionResume 协议）

---

# UserQuestionCard 用户问题中断
## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/user-question/user-question-card.vue`
- **能力域**：Agent 能力
- **能力说明**：渲染 UserQuestion 中断的待回答面板；一次一题分页切换，支持单选/多选、Others、跳过与已完成进度。

> **能力域**：Agent 能力

`UserQuestionCard` 用于渲染 `InterruptReason.UserQuestion`（`'aidev:user_question'`）中断。它通常由 `ChatContainer` 自动挂载到 `ChatInput` 上方，用户回答后通过 `onInterruptResume(payload, interrupt)` 回传 `UserQuestionResume`。

## 交互能力

- **一次一题**：正文只展示当前题；标题栏右侧提供 `< 当前题 / 总题数 >` 切换定位（单题为 `1 / 1`），首末题对应箭头禁用。
- **自动跳转**：单选预设选项从未答变为有效答时，自动跳到下一题（最后一题停留）；多选与 Others 不自动跳，靠箭头切换。
- **已完成进度**：Footer 左侧展示「已完成 N 题」；右侧为「跳过」+「完成」。
- **单选 / 多选**：每道题通过 `multiSelect` 控制选择行为；未传时不展示单选/多选标签，默认仍按单选处理。
- **Others 自由输入**：默认 [UserQuestionChoice](/components/agent/user-question-choice) 为每道题追加 `label: 'others'` 输入项，输入文本写入 `answer[].description`。
- **自定义作答形态**：通过 `#question` slot 可替换默认选择题，渲染任意表单；作答有效时调用 `setAnswer` 回传 `UserQuestionAnswerItem`，无效时传 `undefined`。
- **完成校验**：所有题目均已作答（`setAnswer` 收到有效答案）后才允许点击「完成」。
- **跳过**：点击「跳过」返回 `status: 'cancelled'` 与空 `answers`。
- **输入框发送**：存在待回答 UserQuestion 时，用户也可在 `ChatInput` 直接发送；`ChatContainer` 会调用 `onSendMessage` 并在第三参数附带与「跳过」等价的 skip `payload` 及 `interrupt`，输入框内容不会自动清空。

## 数据协议

待回答中断：

```typescript
const interrupt = {
  id: 'interrupt_user_question',
  reason: InterruptReason.UserQuestion,
  toolCallId: 'tool_call_user_question',
  message: '请选择实现方案',
  metadata: {
    questions: [
      {
        header: '请选择实现方案',
        multiSelect: false,
        question: '你希望采用哪种冒泡排序实现？',
        options: [
          { label: 'basic', description: '基础冒泡排序' },
          { label: 'optimized', description: '优化版冒泡排序' },
        ],
      },
    ],
  },
};
```

完成回答后生成的 resume：

```typescript
const payload = {
  interruptId: 'interrupt_user_question',
  reason: InterruptReason.UserQuestion,
  status: 'resolved',
  payload: {
    answers: [
      {
        question: '你希望采用哪种冒泡排序实现？',
        multiSelect: false,
        answer: [{ label: 'optimized', description: '优化版冒泡排序' }],
      },
    ],
  },
};
```

## 基础用法

> 业务侧通常不直接使用本组件；推荐构造 `InterruptMessage` 后交给 `ChatContainer` / `MessageContainer` 渲染。下面示例用于说明组件 API 和 payload 形状。

```vue
<template>
  <UserQuestionCard
    :interrupt="pendingInterrupt"
    :on-resume="handleResume"
  />
</template>

<script setup lang="ts">
  import { InterruptReason, UserQuestionCard, type OnInterruptResume } from '@blueking/chat-x';

  const pendingInterrupt = {
    id: 'interrupt_user_question',
    reason: InterruptReason.UserQuestion,
    toolCallId: 'tool_call_user_question',
    metadata: {
      questions: [
        {
          header: '请选择实现方案',
          multiSelect: false,
          question: '你希望采用哪种实现？',
          options: [{ label: 'basic', description: '基础冒泡排序' }],
        },
      ],
    },
  };

  const handleResume: OnInterruptResume = async (payload, interrupt) => {
    console.log(interrupt.id, payload);
  };
</script>
```

**渲染效果**

## 已回答回显

`InterruptMessageRender` 在 `content.outcome.type === 'success'` 且 `content.result.reason === InterruptReason.UserQuestion` 时，会在会话内渲染 `UserQuestionAnsweredCard`。

```vue
<UserQuestionAnsweredCard
  :answers="answers"
  status="resolved"
/>
```

**渲染效果**

## ChatContainer 自动挂载

`ChatContainer` 内部通过 `useMessageGroup` 查找最近一条 `outcome.type === 'interrupt'` 的 `UserQuestion`，并在 `ChatInput` 的 `#interrupt` 插槽中渲染 `UserQuestionCard`：

```vue
<ChatContainer
  v-model="inputValue"
  :messages="messages"
  :on-interrupt-resume="handleResume"
  :on-send-message="handleSendMessage"
/>
```

- 卡片内「完成 / 跳过」→ `onInterruptResume(payload, interrupt)`
- 输入框直接发送 → `onSendMessage(content, docSchema, { interrupt, payload })`，其中 `payload` 由 `buildSkipResumePayload(interrupt)` 生成（`status: 'cancelled'`）

## 工具函数 buildSkipResumePayload

从 `@blueking/chat-x` 导出，用于构造 UserQuestion 的 skip resume（与卡片「跳过」及输入框发送时容器注入的 `options.payload` 一致）：

```typescript
import { buildSkipResumePayload, InterruptReason } from '@blueking/chat-x';

const payload = buildSkipResumePayload(interrupt);
// {
//   interruptId: interrupt.id,
//   reason: InterruptReason.UserQuestion,
//   status: 'cancelled',
//   payload: { answers: [] },
// }
```

## 自定义题目渲染（#question slot）

默认每道题由 [UserQuestionChoice](/components/agent/user-question-choice) 渲染；业务可覆盖 `#question` slot 接入自定义表单：

```vue
<template>
  <UserQuestionCard
    :interrupt="pendingInterrupt"
    :on-resume="handleResume"
  >
    <template #question="{ question, qIndex, answer, setAnswer, confirm }">
      <!-- 自定义表单：作答有效时 setAnswer(answerItem)，无效时 setAnswer(undefined) -->
      <MyCustomForm
        :model="question"
        @change="setAnswer"
        @submit="confirm"
      />
    </template>
  </UserQuestionCard>
</template>
```

`ChatContainer` 提供同名 `#interruptQuestion` slot，参数与 `#question` 一致，透传自输入区上方的 `UserQuestionCard`。

## API

### UserQuestionCard Props

| 属性名    | 类型                    | 默认值 | 说明                                   |
| --------- | ----------------------- | ------ | -------------------------------------- |
| interrupt | `UserQuestionInterrupt` | —      | **必填**，含 `metadata.questions`      |
| onResume  | `OnInterruptResume`     | —      | 完成 / 跳过时触发，签名为 `(payload, interrupt)` |

### UserQuestionAnsweredCard Props

| 属性名  | 类型                         | 默认值       | 说明                         |
| ------- | ---------------------------- | ------------ | ---------------------------- |
| answers | `UserQuestionAnswerItem[]`   | —            | 已回答内容列表               |
| status  | `'resolved' \| 'cancelled'` | `'resolved'` | 回显状态，决定展示已回复/已取消 |

### UserQuestionCard Slots

| 插槽名   | 参数                                                                                                              | 说明                                                                 |
| -------- | ----------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| question | `{ question, qIndex, answer, setAnswer, confirm }`                                                                | 自定义单题渲染；未覆盖时回退 [UserQuestionChoice](/components/agent/user-question-choice) |

slot 参数说明：

| 参数       | 类型                                              | 说明                                           |
| ---------- | ------------------------------------------------- | ---------------------------------------------- |
| question   | `UserQuestionItem`                                | 原始题目数据                                   |
| qIndex     | `number`                                          | 题目序号（从 0 开始）                          |
| answer     | `UserQuestionAnswerItem \| undefined`             | 当前题已组装答案，`undefined` 表示未作答       |
| setAnswer  | `(answer: UserQuestionAnswerItem \| undefined) => void` | 写入/清空当前题答案                            |
| confirm    | `() => void`                                      | 触发「完成」，等价点击底部完成按钮（需全部已答） |

### Events / Expose

无。

## 关联文档

- [中断类型 Interrupt](../../types/interrupt.md)
- [UserQuestionChoice 选择题](/components/agent/user-question-choice)
- [InterruptMessage 中断消息](/components/agent/interrupt-message)
- [ChatContainer 聊天容器](/components/setup/chat-container)
