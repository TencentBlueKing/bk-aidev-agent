# 用户问题 Schema

> since 2.0.0

schema.ts 仍导出 UserSingleChoiceQuestionSchema、UserMultiChoiceQuestionSchema、UserQuestionSchema 及 FromSchema 推导类型； 新的 aidev:user_question 中断不再通过 BaseInterrupt.responseSchema 区分单选/多选，而是在 metadata.questions[].multiSelect 中描述题型。

**关联**：interrupt（新 UserQuestionInterrupt 与 UserQuestionResume 协议）、user-question-card（根据 metadata.questions 渲染单选、多选与 Others 输入）

---

# 用户问题 Schema

> **分类**：type

`src/ag-ui/types/schema.ts` 保留了历史 JSON Schema 工具导出：

- `UserSingleChoiceQuestionSchema`
- `UserMultiChoiceQuestionSchema`
- `UserQuestionSchema`
- `UserSingleChoiceQuestion`
- `UserMultiChoiceQuestion`
- `UserQuestion`

新的 `InterruptReason.UserQuestion`（`'aidev:user_question'`）协议不再依赖 `BaseInterrupt.responseSchema`，而是在 `UserQuestionInterrupt.metadata.questions[]` 中用 `multiSelect` 描述单选 / 多选题，并通过 `UserQuestionResume.payload.answers` 回传回答。

## 新协议入口

```typescript
type UserQuestionItem = {
  header: string;
  multiSelect: boolean;
  options?: UserQuestionOptionItem[];
  question: string;
};

type UserQuestionResume = {
  interruptId: string;
  reason: InterruptReason.UserQuestion;
  status: 'cancelled' | 'resolved';
  payload: {
    answers: UserQuestionAnswerItem[];
  };
};
```

完整结构见 [中断类型 Interrupt](./interrupt.md#userquestioninterrupt)。

## 历史导出

### UserSingleChoiceQuestionSchema

```typescript
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
```

### UserMultiChoiceQuestionSchema

```typescript
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
```

### UserQuestionSchema

`UserQuestionSchema` 与 `UserQuestion` 仍为 `UserMultiChoiceQuestionSchema` / `UserMultiChoiceQuestion` 的别名。

## 关联文档

- [中断类型 Interrupt](./interrupt.md)
- [UserQuestionCard 用户问题中断](../components/agent/user-question-card)
