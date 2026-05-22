---
name: 中断类型 Interrupt
slug: interrupt
category: type
description: AG-UI human-in-the-loop 中断相关类型，含 Interrupt、InterruptMessage 与 resume 回调。
aiSummary: >
  定义 RunFinishedOutcome、BaseInterrupt、AIDevToolApprovalInterrupt、InterruptMessage 与 OnInterruptResume。
  与 MessageRole.Interrupt 及 InterruptMessageRender 组件配合，对应 RUN_FINISHED outcome.type === interrupt。
relatedComponents:
  - slug: interrupt-message
    relation: 根据 outcome.interrupts 与 reason 渲染中断 UI
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

## RunFinishedOutcome

`RUN_FINISHED` 事件的 `outcome` 联合类型：

```typescript
type RunFinishedOutcome =
  | { interrupts: Interrupt[]; type: 'interrupt' }
  | { type: 'success' };
```

| `type`        | 说明                                                                 |
| ------------- | -------------------------------------------------------------------- |
| `'interrupt'` | 等待用户响应；`interrupts` 驱动 UI 渲染审批卡片等                     |
| `'success'`   | 用户已通过 `resume` 处理；`InterruptMessageRender` 不渲染中断卡片 |

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

## Interrupt

当前支持的中断联合类型（可扩展）：

```typescript
type Interrupt =
  | AIDevToolApprovalInterrupt
  | BaseInterrupt<InterruptReason, Record<string, any>>;
```

## InterruptMessage

`MessageRole.Interrupt` 对应的消息类型，`content` 承载 outcome 与可选说明文案：

```typescript
type InterruptMessage = BaseMessage<
  MessageRole.Interrupt,
  {
    message?: string;
    outcome?: RunFinishedOutcome;
    result?: unknown;
    runId?: string;
    threadId?: string;
  }
>;
```

| 字段       | 说明                                                         |
| ---------- | ------------------------------------------------------------ |
| `message`  | 消息组顶部可选说明文案，由 `InterruptMessageRender` 展示     |
| `outcome`  | `type: 'interrupt'` 时从 `interrupts` 渲染卡片；`success` 时不渲染 |
| `result`   | 用户 resume 后回传的 payload，便于持久化与回放                 |
| `runId`    | 关联 AG-UI run 标识                                          |
| `threadId` | 关联会话线程标识                                             |

## OnInterruptResume

用户完成中断操作后的回调（由 `MessageContainer` / `MessageRender` 透传）：

```typescript
type OnInterruptResume = (
  interrupt: Interrupt,
  payload?: Record<string, any>,
) => Promise<void> | void;
```

## 使用示例

```typescript
import {
  APPROVAL_STATUS,
  InterruptReason,
  MessageRole,
  MessageStatus,
  type InterruptMessage,
} from '@blueking/chat-x';

const message: InterruptMessage = {
  id: 'msg_interrupt_1',
  messageId: 'msg_interrupt_1',
  role: MessageRole.Interrupt,
  status: MessageStatus.Pending,
  content: {
    message: '算法方案评审单需要您关注',
    outcome: {
      type: 'interrupt',
      interrupts: [
        {
          id: 'interrupt_1',
          reason: InterruptReason.AIDevToolApproval,
          toolCallId: 'tool_call_1',
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
      ],
    },
  },
};
```

## 关联文档

- [常量枚举 Constants](./constants.md) — `InterruptReason`、`APPROVAL_STATUS`
- [消息类型 Messages](./messages.md) — `InterruptMessage` 在消息联合类型中的位置
- [InterruptMessage 中断消息](../components/molecular/interrupt-message.md)
- [ToolApprovalCard 审批卡片](../components/molecular/tool-approval-card.md)
