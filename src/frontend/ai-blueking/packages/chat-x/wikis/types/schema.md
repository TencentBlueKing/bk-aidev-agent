---
name: 用户问题 Schema
slug: schema
category: type
description: human-in-the-loop 用户单选、多选问题的 JSON Schema 与推导类型。
aiSummary: >
  schema.ts 导出 UserSingleChoiceQuestionSchema、UserMultiChoiceQuestionSchema、UserQuestionSchema 及 FromSchema 推导类型。
  BaseInterrupt.responseSchema 会根据 InterruptReason.UserSingleChoice / UserMultiChoice 约束问题响应结构。
relatedComponents:
  - slug: interrupt-message
    relation: 中断消息可携带 responseSchema 描述用户响应结构
sinceVersion: 2.0.0
domain: message
---

# 用户问题 Schema

> **分类**：type

`src/ag-ui/types/schema.ts` 定义 human-in-the-loop 用户问题的 JSON Schema，并通过 `json-schema-to-ts` 推导 TypeScript 类型。该文件已从 `@blueking/chat-x` 包入口导出。

## UserSingleChoiceQuestionSchema

单选问题的响应结构，`question` 为字符串：

```typescript
import type { FromSchema } from 'json-schema-to-ts';

const UserSingleChoiceQuestionSchema = {
  properties: {
    question: {
      enum: [],
      type: 'string',
    },
  },
  required: ['question'],
  type: 'object',
} as const;

type UserSingleChoiceQuestion = FromSchema<typeof UserSingleChoiceQuestionSchema>;
```

## UserMultiChoiceQuestionSchema

多选问题的响应结构，`question` 为字符串数组，且要求唯一：

```typescript
import type { FromSchema } from 'json-schema-to-ts';

const UserMultiChoiceQuestionSchema = {
  properties: {
    question: {
      items: {
        enum: [],
        type: 'string',
      },
      uniqueItems: true,
      type: 'array',
    },
  },
  required: ['question'],
  type: 'object',
} as const;

type UserMultiChoiceQuestion = FromSchema<typeof UserMultiChoiceQuestionSchema>;
```

## 兼容导出

`UserQuestionSchema` 与 `UserQuestion` 保留为多选问题的别名：

```typescript
const UserQuestionSchema = UserMultiChoiceQuestionSchema;
type UserQuestion = UserMultiChoiceQuestion;
```

## 与 Interrupt 的关系

`BaseInterrupt.responseSchema` 会根据中断原因约束响应结构：

```typescript
type BaseInterrupt<T extends InterruptReason, M extends Record<string, any>> = {
  responseSchema?: T extends InterruptReason.UserMultiChoice
    ? UserMultiChoiceQuestionSchema
    : UserSingleChoiceQuestionSchema;
  // ...其他字段
};
```

## 使用示例

```typescript
import {
  InterruptReason,
  UserMultiChoiceQuestionSchema,
  type BaseInterrupt,
} from '@blueking/chat-x';

const interrupt: BaseInterrupt<InterruptReason.UserMultiChoice, Record<string, never>> = {
  id: 'interrupt_question',
  reason: InterruptReason.UserMultiChoice,
  toolCallId: 'tool_call_question',
  responseSchema: UserMultiChoiceQuestionSchema,
};

const payload = {
  question: ['选项 A', '选项 B'],
};
```

## 关联文档

- [中断类型 Interrupt](./interrupt.md) — `BaseInterrupt.responseSchema`
- [常量枚举 Constants](./constants.md) — `InterruptReason.UserSingleChoice` / `UserMultiChoice`
