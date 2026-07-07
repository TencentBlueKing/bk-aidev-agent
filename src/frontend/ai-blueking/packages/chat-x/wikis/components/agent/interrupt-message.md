---
name: InterruptMessage 中断消息
slug: interrupt-message
kind: component
domain: agent
description: 渲染 human-in-the-loop 中断消息，分发工具审批，并按 reason 回显 resume 结果。
aiSummary: >
  渲染 human-in-the-loop 中断消息，分发工具审批，并按 reason 回显 resume 结果（审批单 / 用户回答）。
  源码位置：src/components/chat-message/interrupt-message/interrupt-message.vue。
relatedComponents:
  - slug: message-render
    relation: role 为 interrupt 时渲染本组件
  - slug: user-question-card
    relation: UserQuestion 待回答面板与回答回显
  - slug: tool-approval-card
    relation: AIDevToolApproval 专用子卡片
  - slug: message-container
    relation: 透传 onInterruptResume；末条为 interrupt 时不触发组 hover
sinceVersion: 1.0.0
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
      result: {
        interruptId: 'interrupt_resumed',
        reason: InterruptReason.AIDevToolApproval,
        status: 'resolved',
        payload: {
          metadata: {
            ticket: {
              approvers: ['张三', '李四'],
              sn: 'REV-2026-04-24-001',
              status: APPROVAL_STATUS.APPROVED,
              submit_time: '2026-04-24 14:30:15',
              title: '算法方案评审单',
              url: 'https://example.com/review-tickets/REV-2026-04-24-001',
            },
          },
        },
      },
    },
  }

  const userQuestionMessage = {
    id: 'demo-user-question',
    messageId: 'demo-user-question',
    role: MessageRole.Interrupt,
    status: MessageStatus.Pending,
    content: {
      message: '请补充以下信息后继续',
      outcome: {
        type: 'interrupt' as const,
        interrupts: [
          {
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
                    { label: 'optimized', description: '提前终止优化版' },
                  ],
                },
              ],
            },
          },
        ],
      },
    },
  }

  const userQuestionAnsweredMessage = {
    id: 'demo-user-question-answered',
    messageId: 'demo-user-question-answered',
    role: MessageRole.Interrupt,
    status: MessageStatus.Complete,
    content: {
      outcome: { type: 'success' as const },
      result: {
        interruptId: 'interrupt_user_question',
        reason: InterruptReason.UserQuestion,
        status: 'resolved',
        payload: {
          answers: [
            {
              question: '你希望采用哪种冒泡排序实现？',
              multiSelect: false,
              answer: [{ label: 'optimized', description: '提前终止优化版' }],
            },
          ],
        },
      },
    },
  }

  const handleInterruptResume = async (payload: Record<string, unknown>, interrupt: { id: string }) => {
    console.log('resume', interrupt.id, payload)
  }
</script>

# InterruptMessage 中断消息
## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/interrupt-message.vue`
- **能力域**：Agent 能力
- **能力说明**：渲染 human-in-the-loop 中断消息，分发工具审批，并按 `result.reason` 回显 resume 结果。



> **能力域**：Agent 能力

human-in-the-loop 中断消息渲染器（导出名 **`InterruptMessageRender`**）。对应 `MessageRole.Interrupt`，解析 `content.outcome` 渲染审批卡片或兜底提示。

> 通常由 [MessageRender](/components/message/message-render) 自动调用，无需业务侧直接引入。
> `UserQuestion` 的待回答卡片由 [ChatContainer](/components/setup/chat-container) 放在输入区上方，本组件在 `outcome.success` 时按 `result.reason` 回显审批单或用户回答。

## 渲染架构

```
InterruptMessageRender
├── content.message（可选）→ 顶部说明文案
└── content.outcome.type === 'interrupt'
      └── v-for interrupts
            ├── reason === aidev:tool_approval → ToolApprovalCard（透传 onInterruptResume，用于取消审批）
            ├── reason === aidev:user_question → 不在消息内渲染，交由 ChatContainer 输入区挂载
            └── 未注册 reason → 兜底块（item.message 或「暂不支持的中断消息」）

content.outcome.type === 'success'
└── resultRenderers[result.reason]
      ├── aidev:tool_approval → ToolApprovalCard（可交互回显，透传 onInterruptResume）
      └── aidev:user_question → UserQuestionAnsweredCard（支持 #answeredQuestion 透传 #answer）
```

| `InterruptReason`              | 子组件              |
| ------------------------------ | ------------------- |
| `aidev:tool_approval`（待审批） | `ToolApprovalCard`  |
| `aidev:tool_approval`（已处理） | `ToolApprovalCard`（可交互回显，仍可取消 / 刷新） |
| `aidev:user_question`（待回答） | 输入区 `UserQuestionCard`，本组件不渲染 |
| `aidev:user_question`（已回答） | `UserQuestionAnsweredCard` |
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

  const handleInterruptResume = async (payload, interrupt) => {
    // ToolApprovalCard 点击「取消审批」时，payload 为 ToolApprovalResume
    console.log(payload, interrupt?.id);
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

## UserQuestion 待回答

待回答的 `UserQuestion` 不在消息内渲染；`ChatContainer` 会找到最近一条待回答中断，并在 `ChatInput` 上方挂载 [UserQuestionCard](/components/agent/user-question-card)。

```vue
<InterruptMessageRender
  :content="userQuestionMessage.content"
  role="interrupt"
/>
```

**渲染效果**

<div class="demo">
  <InterruptMessageRender v-bind="userQuestionMessage" />
</div>

## AIDevToolApproval 已处理回显（outcome.success）

`outcome.type === 'success'` 且 `result.reason === InterruptReason.AIDevToolApproval` 时，会话内以可交互 `ToolApprovalCard` 回显审批单（`readonly: false`）：待审批态仍可取消 / 刷新，终态展示置灰的取消按钮。`result.payload.metadata` 需透传中断时的 `metadata`（含 `ticket`）：

```vue
<InterruptMessageRender
  :content="resumedMessage.content"
  role="interrupt"
/>
```

**渲染效果**

<div class="demo">
  <InterruptMessageRender v-bind="resumedMessage" />
</div>

## UserQuestion 已回答回显（outcome.success）

`outcome.type === 'success'` 且 `result.reason === InterruptReason.UserQuestion` 时，会话内回显用户回答。可通过 `#answeredQuestion` slot 自定义单题回显：

```vue
<InterruptMessageRender
  :content="userQuestionAnsweredMessage.content"
  role="interrupt"
>
  <template #answeredQuestion="{ item, index, status }">
    <MyCustomAnswerView :data="item" :index="index" :status="status" />
  </template>
</InterruptMessageRender>
```

**渲染效果**

<div class="demo">
  <InterruptMessageRender v-bind="userQuestionAnsweredMessage" />
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

### Slots

| 插槽名           | 参数                                              | 说明                                                                 |
| ---------------- | ------------------------------------------------- | -------------------------------------------------------------------- |
| answeredQuestion | `{ item, index, status }`                         | 自定义 UserQuestion 已回答内容回显，透传给 `UserQuestionAnsweredCard` 的 `#answer` |

slot 参数与 [UserQuestionAnsweredCard](/components/agent/user-question-answered-card) 的 `#answer` 一致。

### Events / Expose

无。

## 类型定义

```typescript
import type { Interrupt, InterruptMessage, OnInterruptResume } from '@blueking/chat-x';
```

详见 [中断类型 Interrupt](../../types/interrupt.md)。

## 关联组件

- [ToolApprovalCard](/components/agent/tool-approval-card) — AI Dev 审批单卡片
- [MessageRender](/components/message/message-render) — 按 `role` 派发
- [MessageContainer](/components/setup/message-container) — 列表容器与 `onInterruptResume` 透传
