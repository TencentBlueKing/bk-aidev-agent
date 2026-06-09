---
name: 中断类型 Interrupt
slug: interrupt
category: type
description: AG-UI human-in-the-loop 中断相关类型，含 Interrupt、UserQuestion、InterruptMessage 与 resume 回调。
aiSummary: >
  定义 RunFinishedOutcome、BaseInterrupt、AIDevToolApprovalInterrupt、UserQuestionInterrupt、BaseResume、InterruptMessage 与 OnInterruptResume。
  与 MessageRole.Interrupt、InterruptMessageRender、UserQuestionCard、ToolApprovalCard 配合，对应 RUN_FINISHED outcome。
relatedComponents:
  - slug: interrupt-message
    relation: 根据 outcome.interrupts 与 reason 渲染中断 UI，success 时回显 UserQuestion 回答
  - slug: user-question-card
    relation: UserQuestion 交互面板，挂载在 ChatInput 上方
  - slug: tool-approval-card
    relation: AIDevToolApproval 专用卡片
  - slug: message-render
    relation: role 为 interrupt 时派发 InterruptMessageRender
sinceVersion: 2.0.0
domain: message
---

# 中断类型 Interrupt

> **分类**：type

AG-UI [Interrupts](https://docs.ag-ui.com/drafts/interrupts) 协议相关类型，定义在 `src/ag-ui/types/interrupt.ts`，由 `@blueking/chat-x` 导出。

中断链路分为两段：

1. Agent 返回 `RUN_FINISHED { outcome: { type: 'interrupt', interrupts } }`，前端渲染等待用户处理的 UI。
2. 用户操作后调用 `onInterruptResume(payload, interrupt?)`，业务侧按 `payload.operation` 分支处理，并将 `payload` 作为 `RunAgentInput.resume` 回传给 Agent。

## InterruptResumeOperation

统一标识用户在「中断消息 / 活动消息」上触发的、需回传 Agent 处理的动作：

```typescript
enum InterruptResumeOperation {
  /** 主动取消第三方工具审批 */
  ApprovalCancel = 'approval_cancel',
  /** 重试失败的流程节点（bkflow） */
  FlowNodeRetry = 'flow_node_retry',
  /** 跳过失败的流程节点（bkflow） */
  FlowNodeSkip = 'flow_node_skip',
}
```

业务侧通过 `onInterruptResume` 回调的 `payload.operation` 字段进行分支处理；新增操作类型只需扩展此枚举，回调契约与透传链路保持不变。

## RunFinishedOutcome

`RUN_FINISHED` 事件的 `outcome` 联合类型：

```typescript
type RunFinishedOutcome =
  | { interrupts: Interrupt[]; type: 'interrupt' }
  | { type: 'success' };
```

| `type`        | 说明                                                                 |
| ------------- | -------------------------------------------------------------------- |
| `'interrupt'` | 等待用户响应；`interrupts` 驱动 UI 渲染审批卡片、用户问题面板等       |
| `'success'`   | 用户已通过 `resume` 处理；若 `result.reason === UserQuestion` 则回显回答内容 |

## BaseInterrupt

所有中断项的公共结构：

```typescript
type BaseInterrupt<T extends InterruptReason, M extends Record<string, any>> = {
  expiresAt?: string;
  id: string;
  message?: string;
  metadata?: M;
  properties?: Record<string, any>;
  reason: T;
  toolCallId: string;
};
```

## AIDevToolApprovalInterrupt

AI Dev 第三方工具审批中断，`reason` 为 `InterruptReason.AIDevToolApproval`（`'aidev:tool_approval'`）：

```typescript
type AIDevToolApprovalInterrupt = BaseInterrupt<
  InterruptReason.AIDevToolApproval,
  {
    ticket: {
      approvers: string[];
      sn: string;
      status: APPROVAL_STATUS;
      submit_time: string;
      title: string;
      url: string;
    };
  }
>;
```

## UserQuestionInterrupt

用户回答问题中断，`reason` 为 `InterruptReason.UserQuestion`（`'aidev:user_question'`）。交互面板由 `ChatContainer` 挂载到 `ChatInput` 上方。

```typescript
type UserQuestionInterrupt = BaseInterrupt<
  InterruptReason.UserQuestion,
  {
    questions: UserQuestionItem[];
  }
>;

type UserQuestionItem = {
  header: string;
  /** 是否多选；仅选择题语义，自定义表单类问题可不传 */
  multiSelect?: boolean;
  options?: UserQuestionOptionItem[];
  question: string;
};

type UserQuestionOptionItem = {
  description: string;
  label: string;
};
```

约定：

- `multiSelect: false` 表示单选题，`true` 表示多选题；**不传**时 UI 不展示单选/多选标签，默认选择题组件仍按单选行为处理。
- 前端会为每道**选择题**追加 `label: 'others'` 的自由输入项；后端无需重复下发该选项。
- 当用户选择 Others 时，`answer[].description` 为用户输入文本。
- 业务可通过 `UserQuestionCard` 的 `#question` slot 渲染自定义表单；作答有效时调用 `setAnswer` 回传 `UserQuestionAnswerItem`，无效时传 `undefined`。

## Interrupt

当前支持的中断联合类型：

```typescript
type Interrupt =
  | AIDevToolApprovalInterrupt
  | UserQuestionInterrupt
  | BaseInterrupt<InterruptReason, Record<string, any>>;
```

## InterruptResume 联合类型

```typescript
type InterruptResume = FlowNodeResume | ToolApprovalResume | UserQuestionResume;
```

| 类型                 | `operation` / `reason`              | 说明                                                         |
| -------------------- | ----------------------------------- | ------------------------------------------------------------ |
| `ToolApprovalResume` | `InterruptResumeOperation.ApprovalCancel` | 第三方工具审批取消                                           |
| `FlowNodeResume`     | `flow_node_retry` / `flow_node_skip` | FlowAgent 失败节点重试 / 跳过；**无**对应 `Interrupt` 项     |
| `UserQuestionResume` | `InterruptReason.UserQuestion`（`reason` 字段） | 用户回答问题                                                 |

### ToolApprovalResume

```typescript
type ToolApprovalResume = {
  operation: InterruptResumeOperation.ApprovalCancel;
  payload: { interrupt_id: number | string };
};
```

### FlowNodeResume

流程节点不属于 interrupt，节点定位信息（`task_id` / `node_id`）随 `payload` 回传；此时 `onInterruptResume` 的第二个 `interrupt` 参数**不传**。

```typescript
type FlowNodeResume = {
  operation: InterruptResumeOperation.FlowNodeRetry | InterruptResumeOperation.FlowNodeSkip;
  payload: {
    node_id: string;
    task_id: number;
  };
};
```

## BaseResume / UserQuestionResume

`UserQuestion` 的 resume payload 为单个对象，与 `chat-helper` 的 `IResume` 保持一致：

```typescript
type BaseResume<T extends InterruptReason, P extends Record<string, any>> = {
  interruptId: string;
  payload: P;
  reason: T;
  status: 'cancelled' | 'resolved';
};

type UserQuestionAnswerItem = {
  answer: UserQuestionOptionItem[];
  multiSelect?: boolean;
  question: string;
};

type UserQuestionResume = BaseResume<
  InterruptReason.UserQuestion,
  {
    answers: UserQuestionAnswerItem[];
  }
>;
```

示例：

```typescript
const resume: UserQuestionResume = {
  interruptId: 'interrupt_user_question',
  reason: InterruptReason.UserQuestion,
  status: 'resolved',
  payload: {
    answers: [
      {
        question: '请选择语言',
        multiSelect: true,
        answer: [
          { label: 'Java', description: 'Java' },
          { label: 'others', description: 'Rust' },
        ],
      },
    ],
  },
};
```

## InterruptMessage

`MessageRole.Interrupt` 对应的消息类型，`content` 承载 outcome、可选说明文案与 resume 结果：

```typescript
type InterruptMessage = BaseMessage<
  MessageRole.Interrupt,
  {
    message?: string;
    outcome?: RunFinishedOutcome;
    result?: BaseResume<InterruptReason>;
    runId?: string;
    threadId?: string;
  }
>;
```

| 字段       | 说明                                                         |
| ---------- | ------------------------------------------------------------ |
| `message`  | 消息组顶部可选说明文案，由 `InterruptMessageRender` 展示     |
| `outcome`  | `type: 'interrupt'` 时从 `interrupts` 渲染交互；`success` 时进入已处理态 |
| `result`   | 用户 resume 后回传的单对象 payload；`UserQuestion` 会用于会话内回显 |
| `runId`    | 关联 AG-UI run 标识                                          |
| `threadId` | 关联会话线程标识                                             |

## OnInterruptResume

用户完成中断操作或 FlowAgent 节点操作后的回调（由 `ChatContainer` / `MessageContainer` / `MessageRender` 透传）：

```typescript
type OnInterruptResume = (
  payload: InterruptResume,
  interrupt?: Interrupt,
) => Promise<void> | void;
```

| 参数        | 说明                                                                                                       |
| ----------- | ---------------------------------------------------------------------------------------------------------- |
| `payload`   | 用户操作产生的 resume 负载；通过 `payload.operation`（或 `UserQuestionResume.reason`）区分动作类型         |
| `interrupt` | 原始中断项；审批取消、用户问题等中断来源**必传**；FlowAgent 节点重试 / 跳过等非中断来源**不传**             |

| `payload.operation`              | 触发场景                         | `interrupt` |
| -------------------------------- | -------------------------------- | ----------- |
| `approval_cancel`                | `ToolApprovalCard` 取消审批      | 必传        |
| `flow_node_retry` / `flow_node_skip` | `FlowAgentContent` 失败节点操作 | 不传        |
| —（`UserQuestionResume`）        | `UserQuestionCard` 提交回答      | 必传        |

## 使用示例

```typescript
import {
  APPROVAL_STATUS,
  InterruptReason,
  InterruptResumeOperation,
  MessageRole,
  MessageStatus,
  type InterruptMessage,
  type OnInterruptResume,
} from '@blueking/chat-x';

const message: InterruptMessage = {
  id: 'msg_interrupt_1',
  messageId: 'msg_interrupt_1',
  role: MessageRole.Interrupt,
  status: MessageStatus.Pending,
  content: {
    message: '需要您处理以下中断',
    outcome: {
      type: 'interrupt',
      interrupts: [
        {
          id: 'interrupt_approval_1',
          reason: InterruptReason.AIDevToolApproval,
          toolCallId: 'tool_call_approval_1',
          metadata: {
            ticket: {
              approvers: ['张三'],
              sn: 'REV-2026-04-24-001',
              status: APPROVAL_STATUS.PENDING,
              submit_time: '2026-04-24 14:30:15',
              title: '算法方案评审单',
              url: 'https://example.com/tickets/REV-2026-04-24-001',
            },
          },
        },
        {
          id: 'interrupt_question_1',
          reason: InterruptReason.UserQuestion,
          toolCallId: 'tool_call_question_1',
          message: '请选择实现方案',
          metadata: {
            questions: [
              {
                header: '请选择实现方案',
                multiSelect: false,
                question: '你希望采用哪种排序实现？',
                options: [
                  { label: 'basic', description: '基础冒泡排序' },
                  { label: 'optimized', description: '提前终止优化版' },
                ],
              },
            ],
          },
        },
      ],
    },
  },
};

const handleInterruptResume: OnInterruptResume = async (payload, interrupt) => {
  if ('operation' in payload) {
    switch (payload.operation) {
      case InterruptResumeOperation.ApprovalCancel:
        console.log('取消审批', payload.payload.interrupt_id, interrupt?.id);
        break;
      case InterruptResumeOperation.FlowNodeRetry:
      case InterruptResumeOperation.FlowNodeSkip:
        console.log('流程节点操作', payload.operation, payload.payload);
        break;
    }
    return;
  }
  // UserQuestionResume
  console.log('用户问题 resume', interrupt?.id, payload);
};
```

## 关联文档

- [常量枚举 Constants](./constants.md) — `InterruptReason`、`APPROVAL_STATUS`
- [消息类型 Messages](./messages.md) — `InterruptMessage` 在消息联合类型中的位置
- [InterruptMessage 中断消息](../components/agent/interrupt-message)
- [UserQuestionCard 用户问题中断](../components/agent/user-question-card)
- [ToolApprovalCard 审批卡片](../components/agent/tool-approval-card)
