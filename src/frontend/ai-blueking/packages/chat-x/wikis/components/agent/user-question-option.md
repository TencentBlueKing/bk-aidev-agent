---
name: UserQuestionOption 用户问题选项
slug: user-question-option
kind: component
domain: agent
description: UserQuestionChoice 内部选项行，处理单选/多选状态和 Others 输入。
aiSummary: >
  UserQuestionChoice 内部选项行，处理单选/多选状态和 Others 输入。
  源码位置：src/components/chat-message/interrupt-message/user-question/user-question-option.vue。
relatedComponents: []
sinceVersion: 1.0.0
---

# UserQuestionOption 用户问题选项

> **能力域**：Agent 能力

## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/user-question/user-question-option.vue`
- **能力说明**：UserQuestionChoice 内部选项行，处理单选/多选状态和 Others 输入。

## API 摘要

### Props

- `{ option: NormalizedUserQuestionOption; othersText?: string; selected: boolean; }`

### Emits

- `{ (e: 'confirm'): void; (e: 'select'): void; (e: 'update:othersText', value: string): void; }`

### Slots

- 无。

### Expose

- 无。

## 组件依赖

- 无组件依赖或仅依赖基础库。

## 使用建议

- 优先通过 [UserQuestionChoice](/components/agent/user-question-choice) 或 [UserQuestionCard](/components/agent/user-question-card) 使用；直接使用前请确认 props 数据结构来自对应类型定义。
