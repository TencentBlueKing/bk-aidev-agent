---
name: UserQuestionChoice 用户问题选择题
slug: user-question-choice
kind: component
domain: agent
description: UserQuestionCard 默认的选择题渲染组件，封装单选/多选、Others 输入与答案组装。
aiSummary: >
  UserQuestionCard 默认的选择题渲染组件，封装单选/多选、Others 输入与答案组装。
  源码位置：src/components/chat-message/interrupt-message/user-question/user-question-choice.vue。
relatedComponents:
  - slug: user-question-card
    relation: 默认通过 #question slot 回退渲染本组件
  - slug: user-question-option
    relation: 内部逐条渲染选项行
  - slug: interrupt
    relation: 答案结构遵循 UserQuestionAnswerItem
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import UserQuestionChoice from '../../../src/components/chat-message/interrupt-message/user-question/user-question-choice.vue'

  const singleQuestion = {
    header: '请选择实现方案',
    multiSelect: false,
    question: '你希望采用哪种冒泡排序实现？',
    options: [
      { label: 'basic', description: '基础冒泡排序：代码最短，适合教学' },
      { label: 'optimized', description: '优化版冒泡排序：有序时提前终止' },
    ],
  }

  const multiQuestion = {
    header: '请选择实现方案',
    multiSelect: true,
    question: '请选择输出语言',
    options: [
      { label: 'TypeScript', description: 'TypeScript' },
      { label: 'Python', description: 'Python' },
    ],
  }

  const handleAnswer = (answer) => {
    console.log('answer changed', answer)
  }

  const handleConfirm = () => {
    console.log('confirm')
  }
</script>

# UserQuestionChoice 用户问题选择题

> **能力域**：Agent 能力

## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/user-question/user-question-choice.vue`
- **能力说明**：封装 UserQuestion 的选择题交互，负责选项归一化、单选/多选切换、Others 输入校验与 `UserQuestionAnswerItem` 组装。

`UserQuestionChoice` 是 [UserQuestionCard](/components/agent/user-question-card) 在 `#question` slot 未覆盖时的**默认渲染**。业务侧也可单独使用，配合 `useUserQuestion` 的 `setAnswer` 接入自定义面板。

## 交互能力

- **单选 / 多选**：由 `question.multiSelect` 控制；未传时不展示单选/多选标签，但仍按单选行为处理。
- **Others 自由输入**：前端自动在选项末尾追加 `label: 'others'` 输入项。
- **实时同步答案**：选择或输入变化时 emit `answer`；作答有效时回传已组装的 `UserQuestionAnswerItem`，无效时回传 `undefined`。
- **Enter 确认**：Others 输入框按 Enter 触发 `confirm`，等价于点击「完成」按钮（需上层已全部作答）。

## 基础用法（单选）

```vue
<template>
  <UserQuestionChoice
    :question="singleQuestion"
    @answer="handleAnswer"
    @confirm="handleConfirm"
  />
</template>

<script setup lang="ts">
  import { UserQuestionChoice, type UserQuestionAnswerItem } from '@blueking/chat-x';

  const singleQuestion = {
    header: '请选择实现方案',
    multiSelect: false,
    question: '你希望采用哪种冒泡排序实现？',
    options: [
      { label: 'basic', description: '基础冒泡排序' },
      { label: 'optimized', description: '优化版冒泡排序' },
    ],
  };

  const handleAnswer = (answer: UserQuestionAnswerItem | undefined) => {
    console.log(answer);
  };
</script>
```

**渲染效果**

<div class="demo">
  <UserQuestionChoice
    :question="singleQuestion"
    @answer="handleAnswer"
    @confirm="handleConfirm"
  />
</div>

## 多选

```vue
<UserQuestionChoice
  :question="multiQuestion"
  @answer="handleAnswer"
/>
```

**渲染效果**

<div class="demo">
  <UserQuestionChoice
    :question="multiQuestion"
    @answer="handleAnswer"
  />
</div>

## 在 UserQuestionCard 中使用

通常无需直接使用本组件；`UserQuestionCard` 默认已在 `#question` slot 回退中挂载：

```vue
<UserQuestionCard :interrupt="interrupt" :on-resume="handleResume" />
```

如需替换某一题的渲染，覆盖 `#question` slot 即可；未覆盖时仍回退到 `UserQuestionChoice`。

## API

### Props

| 属性名   | 类型               | 默认值 | 说明                         |
| -------- | ------------------ | ------ | ---------------------------- |
| question | `UserQuestionItem` | —      | **必填**，含 `options` 等字段 |

### Events

| 事件名  | 参数                                      | 说明                                                         |
| ------- | ----------------------------------------- | ------------------------------------------------------------ |
| answer  | `(answer: UserQuestionAnswerItem \| undefined)` | 作答变化；有效时回传已组装答案，无效（未选/ Others 空）时 `undefined` |
| confirm | —                                         | 用户在 Others 输入框按 Enter 时触发，上层可绑定「完成」逻辑   |

### Slots / Expose

无。

## 关联文档

- [UserQuestionCard 用户问题中断](/components/agent/user-question-card)
- [UserQuestionOption 用户问题选项](/components/agent/user-question-option)
- [中断类型 Interrupt](../../types/interrupt.md)
