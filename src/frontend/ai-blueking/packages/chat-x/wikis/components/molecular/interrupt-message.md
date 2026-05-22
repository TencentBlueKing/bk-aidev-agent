---
name: InterruptMessage 中断消息
slug: interrupt-message
category: molecular
description: human-in-the-loop 中断消息渲染器，按 Interrupt.reason 派发专用卡片或兜底文案。
aiSummary: >
  InterruptMessageRender 读取 content.outcome.interrupts，展示 content.message 说明，并按 reason 映射 ToolApprovalCard 等子组件；
  未注册 reason 时展示兜底文案。由 MessageRender 在 interrupt 角色下调用，导出名为 InterruptMessageRender。
relatedComponents:
  - slug: message-render
    relation: role 为 interrupt 时渲染本组件
  - slug: tool-approval-card
    relation: AIDevToolApproval 专用子卡片
  - slug: message-container
    relation: 透传 onInterruptResume；末条为 interrupt 时不触发组 hover
sinceVersion: 2.0.0
domain: message
---

<script lang="ts" setup>
  import InterruptMessageRender from '../../../src/components/chat-message/interrupt-message/interrupt-message.vue'
  import { APPROVAL_STATUS, InterruptReason, MessageRole, MessageStatus } from '../../../src/ag-ui/types/constants'

  const pendingMessage = {
    id: 'demo-interrupt-pending',
    messageId: 'demo-interrupt-pending',
    role: MessageRole.Interrupt,
    status: MessageStatus.Pending,
    content: {
      message: '算法方案评审单需要您关注',
      outcome: {
        type: 'interrupt' as const,
        interrupts: [
          {
            id: 'interrupt_demo_pending',
            reason: InterruptReason.AIDevToolApproval,
            toolCallId: 'tool_call_demo_pending',
            message: '算法方案评审单需要您关注',
            metadata: {
              ticket: {
                approvers: ['张三', '李四'],
                sn: 'REV-2026-04-24-001',
                status: APPROVAL_STATUS.PENDING,
                submit_time: '2026-04-24 14:30:15',
                title: '算法方案评审单',
                url: 'https://example.com/review-tickets/REV-2026-04-24-001',
              },
            },
          },
        ],
      },
    },
  }

  const unsupportedMessage = {
    id: 'demo-interrupt-fallback',
    messageId: 'demo-interrupt-fallback',
    role: MessageRole.Interrupt,
    status: MessageStatus.Complete,
    content: {
      message: '以下中断类型暂未实现专用卡片：',
      outcome: {
        type: 'interrupt' as const,
        interrupts: [
          {
            id: 'interrupt_unsupported',
            reason: 'unknown_reason' as InterruptReason,
            toolCallId: 'tool_call_unsupported',
            message: '暂不支持的中断类型示例',
          },
        ],
      },
    },
  }

  const resumedMessage = {
    id: 'demo-interrupt-resumed',
    messageId: 'demo-interrupt-resumed',
    role: MessageRole.Interrupt,
    status: MessageStatus.Complete,
    content: {
      message: '您已确认关注该评审单',
      outcome: { type: 'success' as const },
      result: { interruptId: 'interrupt_resumed', status: 'acknowledged' },
    },
  }

  const handleInterruptResume = async (interrupt: { id: string }, payload?: Record<string, unknown>) => {
    console.log('resume', interrupt.id, payload)
  }
</script>

# InterruptMessage 中断消息

> **层级**：分子组件 · **功能域**：消息展示

human-in-the-loop 中断消息渲染器（导出名 **`InterruptMessageRender`**）。对应 `MessageRole.Interrupt`，解析 `content.outcome` 渲染审批卡片或兜底提示。

> 通常由 [MessageRender](./message-render.md) 自动调用，无需业务侧直接引入。

## 渲染架构

```
InterruptMessageRender
├── content.message（可选）→ 顶部说明文案
└── content.outcome.type === 'interrupt'
      └── v-for interrupts
            ├── reason === aidev:tool_approval → ToolApprovalCard
            └── 未注册 reason → 兜底块（item.message 或「暂不支持的中断消息」）

content.outcome.type === 'success' → 不渲染任何中断卡片
```

| `InterruptReason`              | 子组件              |
| ------------------------------ | ------------------- |
| `aidev:tool_approval`          | `ToolApprovalCard`  |
| 其他 / 未注册                  | 兜底文案区域        |

## 基础用法（待审批）

```vue
<template>
  <InterruptMessageRender
    :id="message.id"
    :message-id="message.messageId"
    :role="message.role"
    :status="message.status"
    :content="message.content"
    :on-interrupt-resume="handleInterruptResume"
  />
</template>

<script setup lang="ts">
  import {
    InterruptMessageRender,
    APPROVAL_STATUS,
    InterruptReason,
    MessageRole,
    MessageStatus,
    type InterruptMessage,
  } from '@blueking/chat-x';

  const message: InterruptMessage = {
    id: 'msg_interrupt',
    messageId: 'msg_interrupt',
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
                url: 'https://example.com/tickets/001',
              },
            },
          },
        ],
      },
    },
  };

  const handleInterruptResume = async (interrupt, payload) => {
    console.log(interrupt.id, payload);
  };
</script>
```

**渲染效果**

<div class="demo">
  <InterruptMessageRender
    v-bind="pendingMessage"
    :on-interrupt-resume="handleInterruptResume"
  />
</div>

## 已 resume（outcome.success）

`outcome.type === 'success'` 时不渲染中断卡片，仅保留可选顶部 `content.message`：

```vue
<InterruptMessageRender
  :content="{ message: '您已确认关注该评审单', outcome: { type: 'success' } }"
  role="interrupt"
/>
```

**渲染效果**

<div class="demo">
  <InterruptMessageRender v-bind="resumedMessage" />
</div>

## 不支持的中断类型（兜底）

```vue
<InterruptMessageRender :content="unsupportedContent" role="interrupt" />
```

**渲染效果**

<div class="demo">
  <InterruptMessageRender v-bind="unsupportedMessage" />
</div>

## 在 MessageContainer 中使用

配置 `onInterruptResume`，由容器经 `MessageRender` 透传到本组件：

```vue
<MessageContainer
  :messages="messages"
  :on-interrupt-resume="handleInterruptResume"
/>
```

当消息组**最后一条**为 `role: 'interrupt'` 时，容器**不会**在鼠标移入时设置 `isHover`，避免误显 AI 工具栏遮挡审批卡片。

## API

### Props

继承 `Partial<InterruptMessage>` 的字段（`id`、`messageId`、`role`、`content`、`status` 等），并额外支持：

| 属性名            | 类型               | 默认值 | 说明                                      |
| ----------------- | ------------------ | ------ | ----------------------------------------- |
| content           | `InterruptMessage['content']` | — | 含 `message`、`outcome`、`result` 等      |
| onInterruptResume | `OnInterruptResume` | —     | 用户完成中断操作后的回调（可选）          |

### Events / Slots / Expose

无。

## 类型定义

```typescript
import type { Interrupt, InterruptMessage, OnInterruptResume } from '@blueking/chat-x';
```

详见 [中断类型 Interrupt](../../types/interrupt.md)。

## 关联组件

- [ToolApprovalCard](./tool-approval-card.md) — AI Dev 审批单卡片
- [MessageRender](./message-render.md) — 按 `role` 派发
- [MessageContainer](./message-container.md) — 列表容器与 `onInterruptResume` 透传
