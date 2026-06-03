---
name: UserQuestionCard 用户问题中断
slug: user-question-card
kind: component
domain: agent
description: 渲染 UserQuestion 中断的待回答面板，支持单选、多选、Others 与跳过。
aiSummary: >
  渲染 UserQuestion 中断的待回答面板，支持单选、多选、Others 与跳过。
  源码位置：src/components/chat-message/interrupt-message/user-question/user-question-card.vue。
relatedComponents:
  - slug: interrupt-message
    relation: outcome.success 时挂载 UserQuestionAnsweredCard 回显回答
  - slug: chat-container
    relation: 检测最近待回答 UserQuestion 并把 UserQuestionCard 放在输入区上方
  - slug: interrupt
    relation: 定义 UserQuestionInterrupt 与 UserQuestionResume 协议
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import {
    InterruptReason,
    UserQuestionAnsweredCard,
    UserQuestionCard,
  } from '../../../src'

  const pendingInterrupt = {
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
            { label: 'basic', description: '基础冒泡排序：代码最短，适合教学' },
            { label: 'optimized', description: '优化版冒泡排序：有序时提前终止' },
          ],
        },
        {
          header: '请选择实现方案',
          multiSelect: true,
          question: '请选择输出语言',
          options: [
            { label: 'TypeScript', description: 'TypeScript' },
            { label: 'Python', description: 'Python' },
          ],
        },
      ],
    },
  }

  const answered = [
    {
      question: '你希望采用哪种冒泡排序实现？',
      multiSelect: false,
      answer: [{ label: 'optimized', description: '优化版冒泡排序：有序时提前终止' }],
    },
    {
      question: '请选择输出语言',
      multiSelect: true,
      answer: [
        { label: 'TypeScript', description: 'TypeScript' },
        { label: 'others', description: 'Rust' },
      ],
    },
  ]

  const handleResume = async (payload, interrupt) => {
    console.log('user question resume', payload, interrupt)
  }
</script>

# UserQuestionCard 用户问题中断
## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/user-question/user-question-card.vue`
- **能力域**：Agent 能力
- **能力说明**：渲染 UserQuestion 中断的待回答面板，支持单选、多选、Others 与跳过。



> **能力域**：Agent 能力

`UserQuestionCard` 用于渲染 `InterruptReason.UserQuestion`（`'aidev:user_question'`）中断。它通常由 `ChatContainer` 自动挂载到 `ChatInput` 上方，用户回答后通过 `onInterruptResume(payload, interrupt)` 回传 `UserQuestionResume`。

## 交互能力

- **单选 / 多选**：每道题通过 `multiSelect` 控制选择行为。
- **Others 自由输入**：前端自动为每道题追加 `label: 'others'` 输入项，输入文本写入 `answer[].description`。
- **完成校验**：所有题目均已作答后才允许点击「完成」；选择 Others 时必须输入非空文本。
- **跳过**：点击「跳过」返回 `status: 'cancelled'` 与空 `answers`。
- **自由文本兜底**：当存在待回答 UserQuestion 且业务配置了 `onInterruptResume` 时，用户也可以直接在 `ChatInput` 输入文本；容器会将文本转换为单条 Others 回答。

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

<div class="demo">
  <UserQuestionCard
    :interrupt="pendingInterrupt"
    :on-resume="handleResume"
  />
</div>

## 已回答回显

`InterruptMessageRender` 在 `content.outcome.type === 'success'` 且 `content.result.reason === InterruptReason.UserQuestion` 时，会在会话内渲染 `UserQuestionAnsweredCard`。

```vue
<UserQuestionAnsweredCard
  :answers="answers"
  status="resolved"
/>
```

**渲染效果**

<div class="demo">
  <UserQuestionAnsweredCard
    :answers="answered"
    status="resolved"
  />
</div>

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

如果没有配置 `onInterruptResume`，自由文本输入不会被截获，仍按普通 `onSendMessage` 发送，避免用户输入被静默清空。

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

### Events / Slots / Expose

无。

## 关联文档

- [中断类型 Interrupt](../../types/interrupt.md)
- [InterruptMessage 中断消息](/components/agent/interrupt-message)
- [ChatContainer 聊天容器](/components/setup/chat-container)
