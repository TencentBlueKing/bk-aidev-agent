---
name: ToolApprovalCard 审批卡片
slug: tool-approval-card
category: molecular
description: AI Dev 工具审批中断专用卡片，展示评审单状态、处理人与详情/复制操作。
aiSummary: >
  接收 AIDevToolApprovalInterrupt，从 metadata.ticket 渲染标题、状态徽章、单据编号、提交时间、当前处理人；
  支持打开详情链接与复制 url/sn。由 InterruptMessageRender 在 reason 为 aidev:tool_approval 时挂载。
relatedComponents:
  - slug: interrupt-message
    relation: InterruptMessageRender 按 reason 派发渲染
sinceVersion: 2.0.0
domain: message
---

<script lang="ts" setup>
  import ToolApprovalCard from '../../../src/components/chat-message/interrupt-message/tool-approval-card.vue'
  import { APPROVAL_STATUS, InterruptReason } from '../../../src/ag-ui/types/constants'

  const pendingInterrupt = {
    id: 'interrupt_pending',
    reason: InterruptReason.AIDevToolApproval,
    toolCallId: 'tool_call_pending',
    metadata: {
      ticket: {
        approvers: ['张三', '李四', '王五'],
        sn: 'REV-2026-04-24-001',
        status: APPROVAL_STATUS.PENDING,
        submit_time: '2026-04-24 14:30:15',
        title: '算法方案评审单',
        url: 'https://example.com/review-tickets/REV-2026-04-24-001',
      },
    },
  }

  const approvedInterrupt = {
    id: 'interrupt_approved',
    reason: InterruptReason.AIDevToolApproval,
    toolCallId: 'tool_call_approved',
    metadata: {
      ticket: {
        approvers: ['张三'],
        sn: 'REV-2026-04-24-002',
        status: APPROVAL_STATUS.APPROVED,
        submit_time: '2026-04-24 15:00:00',
        title: '算法方案评审单',
        url: 'https://example.com/review-tickets/REV-2026-04-24-002',
      },
    },
  }

  const rejectedInterrupt = {
    id: 'interrupt_rejected',
    reason: InterruptReason.AIDevToolApproval,
    toolCallId: 'tool_call_rejected',
    metadata: {
      ticket: {
        approvers: ['李四'],
        sn: 'REV-2026-04-24-003',
        status: APPROVAL_STATUS.REJECTED,
        submit_time: '2026-04-24 16:00:00',
        title: '算法方案评审单',
        url: 'https://example.com/review-tickets/REV-2026-04-24-003',
      },
    },
  }
</script>

# ToolApprovalCard 审批卡片

> **层级**：分子组件 · **功能域**：消息展示

AI Dev 第三方工具审批（`InterruptReason.AIDevToolApproval`）专用卡片，由 [InterruptMessageRender](./interrupt-message.md) 按 `reason` 动态挂载。

> **通常不需要单独引入**；仅在需要独立预览卡片样式时使用。

## 渲染结构

```
ToolApprovalCard
├── 标题栏：左侧色条 + 单据标题 + 状态徽章（待审批/已审批/已拒绝等）
├── 字段区：单据编号、提交时间
├── 处理人：当前处理人（overflow-tips 省略）
└── 操作区：查看单据详情（新窗口打开 url）、复制单据（url 或 sn）
```

状态徽章样式：

| `ticket.status`                         | 视觉     |
| --------------------------------------- | -------- |
| `pending`、`draft`                      | 橙色待办 |
| `approved`                              | 绿色通过 |
| `rejected`、`cancelled`、`expired`、`abandoned` | 红色终态 |

## 基础用法（待审批）

> `ToolApprovalCard` 为 `InterruptMessageRender` 内部子组件，**未从 `@blueking/chat-x` 包入口导出**。业务侧通过构造 `InterruptMessage` 触发渲染即可；下方为类型与数据结构参考。

```vue
<template>
  <!-- 业务侧推荐：由 MessageRender / MessageContainer 自动渲染 -->
  <InterruptMessageRender
    :content="interruptMessage.content"
    role="interrupt"
    :status="interruptMessage.status"
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
    type AIDevToolApprovalInterrupt,
  } from '@blueking/chat-x';

  const interrupt: AIDevToolApprovalInterrupt = {
    id: 'interrupt_1',
    reason: InterruptReason.AIDevToolApproval,
    toolCallId: 'tool_call_1',
    metadata: {
      ticket: {
        approvers: ['张三', '李四'],
        sn: 'REV-2026-04-24-001',
        status: APPROVAL_STATUS.PENDING,
        submit_time: '2026-04-24 14:30:15',
        title: '算法方案评审单',
        url: 'https://example.com/tickets/001',
      },
    },
  };

  const interruptMessage: InterruptMessage = {
    id: 'msg_1',
    messageId: 'msg_1',
    role: MessageRole.Interrupt,
    status: MessageStatus.Pending,
    content: {
      outcome: { type: 'interrupt', interrupts: [interrupt] },
    },
  };
</script>
```

**渲染效果**（文档站直接挂载 `ToolApprovalCard` 预览卡片 UI）

<div class="demo">
  <ToolApprovalCard :interrupt="pendingInterrupt" />
</div>

## 已审批 / 已拒绝

```vue
<InterruptMessageRender
  :content="{ outcome: { type: 'interrupt', interrupts: [approvedInterrupt] } }"
  role="interrupt"
/>
```

**渲染效果**

<div class="demo" style="display: flex; flex-direction: column; gap: 12px;">
  <ToolApprovalCard :interrupt="approvedInterrupt" />
  <ToolApprovalCard :interrupt="rejectedInterrupt" />
</div>

## API

### Props

| 属性名    | 类型                         | 默认值 | 说明                           |
| --------- | ---------------------------- | ------ | ------------------------------ |
| interrupt | `AIDevToolApprovalInterrupt` | —      | **必填**，含 `metadata.ticket` |

### Events / Slots / Expose

无。交互通过按钮点击在组件内部完成（打开链接、复制剪贴板）。

## 依赖

- `bkui-vue`：`Button`、`Loading`
- `useClipboard` — 复制单据
- `v-overflow-tips` — 处理人超长省略

## 关联组件

- [InterruptMessage 中断消息](./interrupt-message.md)
- [中断类型 Interrupt](../../types/interrupt.md)
- [常量枚举 Constants](../../types/constants.md) — `APPROVAL_STATUS`、`APPROVAL_STATUS_MAP`
