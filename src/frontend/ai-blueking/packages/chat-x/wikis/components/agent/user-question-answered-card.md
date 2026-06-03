---
name: UserQuestionAnsweredCard 用户问题回答回显
slug: user-question-answered-card
kind: component
domain: agent
description: 在 UserQuestion resume 成功后回显用户回答或取消状态。
aiSummary: >
  在 UserQuestion resume 成功后回显用户回答或取消状态。
  源码位置：src/components/chat-message/interrupt-message/user-question/user-question-answered-card.vue。
relatedComponents: []
sinceVersion: 1.0.0
---

# UserQuestionAnsweredCard 用户问题回答回显

> **能力域**：Agent 能力

## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/user-question/user-question-answered-card.vue`
- **能力说明**：在 UserQuestion resume 成功后回显用户回答或取消状态。

## API 摘要

### Props

- `{ answers: UserQuestionAnswerItem[]; // resume 状态：resolved=已回复，cancelled=已取消（跳过） status?: 'cancelled' | 'resolved'; }`

### Emits

- 无。

### Slots

- 无。

### Expose

- 无。

## 组件依赖

- 无组件依赖或仅依赖基础库。

## 使用建议

- 优先通过上层组合组件使用；直接使用前请确认 props 数据结构来自对应类型定义。
