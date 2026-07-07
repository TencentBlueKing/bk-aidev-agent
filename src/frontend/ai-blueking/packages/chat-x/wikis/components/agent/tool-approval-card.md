---
name: ToolApprovalCard 工具审批卡片
slug: tool-approval-card
kind: component
domain: agent
description: 渲染 AIDevToolApproval 中断的审批信息与取消/刷新操作，支持只读回显态。
aiSummary: >
  渲染 AIDevToolApproval 中断的审批信息与取消/刷新操作；outcome.success 回显时以 readonly 只读展示。
  源码位置：src/components/chat-message/interrupt-message/tool-approval-card.vue。
relatedComponents:
  - slug: interrupt-message
    relation: InterruptMessageRender 按 reason 派发渲染
sinceVersion: 1.0.0
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

  const revokedInterrupt = {
    id: 'interrupt_revoked',
    reason: InterruptReason.AIDevToolApproval,
    toolCallId: 'tool_call_revoked',
    metadata: {
      ticket: {
        approvers: [],
        sn: 'REV-2026-04-24-004',
        status: APPROVAL_STATUS.REVOKED,
        submit_time: '2026-04-24 17:00:00',
        title: '算法方案评审单',
        url: 'https://example.com/review-tickets/REV-2026-04-24-004',
      },
    },
  }

  const handleInterruptResume = async (payload: Record<string, unknown>, interrupt: { id: string }) => {
    console.log('审批操作:', payload, interrupt.id)
  }
</script>

# ToolApprovalCard 审批卡片
## 源码事实

- **源码位置**：`src/components/chat-message/interrupt-message/tool-approval-card.vue`
- **能力域**：Agent 能力
- **能力说明**：渲染 AIDevToolApproval 中断的审批信息与取消操作；`readonly` 时用于 outcome.success 只读回显。



> **能力域**：Agent 能力

AI Dev 第三方工具审批（`InterruptReason.AIDevToolApproval`）专用卡片，由 [InterruptMessageRender](/components/agent/interrupt-message) 按 `reason` 动态挂载。

> **通常不需要单独引入**；仅在需要独立预览卡片样式时使用。

## 渲染结构

```
ToolApprovalCard
├── 标题栏：左侧色条 + 单据标题 + 复制图标 + 刷新图标（仅审批中）+ 状态徽章（审批中/已通过/已拒绝/已撤销等）
├── 字段区：单据编号、提交时间
├── 处理人：当前处理人（overflow-tips 省略）
└── 操作区：查看单据详情（新窗口打开 url）、取消审批（见下）
```

**标题栏刷新图标**（仅 `pending` / `draft` 且非 `readonly` 时展示，复制图标右侧）：取消审批为后端轮询、状态无法实时返回，用户可点击刷新图标主动拉取单据最新状态，`hover` 显示 tooltip「刷新单据状态」。刷新做 **2s 冷却节流**（冷却中图标置灰不可点）；点击「取消审批」也会触发一次 2s 冷却，即取消后需间隔 2s 才能继续刷新。分享只读渲染下刷新图标禁用。

操作区第二个按钮的形态随状态变化（`readonly` 时整体隐藏）：

- **待审批（`pending` / `draft`）**：展示「取消审批」按钮；点击后按钮进入 **loading** 并禁用防重复提交（同步 resume 无法获知结果）。
- **终态（`approved` / `rejected` / `cancelled` / `revoked` / `expired` / `abandoned`）**：保留「取消审批」按钮但**置灰禁用**，`hover` 显示当前状态无法取消的原因；`cancelled` / `revoked` 态按钮文案为「已取消审批」。

置灰按钮的 tooltip 文案映射：

| `ticket.status`       | 文案                       |
| --------------------- | -------------------------- |
| `approved`            | 该单据已通过，无法取消     |
| `rejected`            | 该单据已被拒绝，无法取消   |
| `cancelled`、`revoked` | 单据已取消，无需重复点击   |
| 其它终态（`expired`、`abandoned`） | 当前状态无法取消审批 |

`readonly` 为 `true` 时用于 `outcome.success` 结果回显：隐藏刷新图标与第二个操作按钮（取消 / 置灰取消均不展示），不接受交互。通常由 [InterruptMessageRender](/components/agent/interrupt-message) 内部传入，业务侧无需手动设置。

分享只读渲染模式（注入的 `RenderMode.Share`）下，操作按钮与刷新图标**保持可见但禁用**（区别于 `readonly` 的直接隐藏），避免在分享回显场景误触发。该渲染模式由 [ChatContainer](/components/setup/chat-container) 等容器通过 `useRenderModeProvider` 注入，组件内部经 `useRenderModeInject` 读取，业务侧无需手动设置。

取消审批与刷新均为同步 `onInterruptResume`，组件无法在回调内获知请求结果：取消点击后按钮立即进入 loading 防止重复取消；刷新做 2s 冷却节流供用户轮询最新状态；待后台刷新使卡片卸载/重建后交互态随实例销毁。

状态徽章样式：

| `ticket.status`                         | 视觉     |
| --------------------------------------- | -------- |
| `pending`、`draft`                      | 蓝色评审中 |
| `approved`                              | 绿色通过 |
| `rejected`、`cancelled`、`expired`、`abandoned` | 红色终态 |
| `revoked`                               | 橙色已撤销 |

## 基础用法（待审批）

> `ToolApprovalCard` 为 `InterruptMessageRender` 内部子组件，**未从 `@blueking/chat-x` 包入口导出**。业务侧通过构造 `InterruptMessage` 触发渲染即可；下方为类型与数据结构参考。

```vue
<template>
  <!-- 业务侧推荐：由 MessageRender / MessageContainer 自动渲染 -->
  <InterruptMessageRender
    :content="interruptMessage.content"
    role="interrupt"
    :status="interruptMessage.status"
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

  const handleInterruptResume = async (payload, interrupt) => {
    console.log(payload, interrupt.id);
  };
</script>
```

**渲染效果**（文档站直接挂载 `ToolApprovalCard` 预览卡片 UI）

<div class="demo">
  <ToolApprovalCard
    :interrupt="pendingInterrupt"
    :on-interrupt-resume="handleInterruptResume"
  />
</div>

## 已通过 / 已拒绝 / 已撤销

```vue
<div>
  <InterruptMessageRender
    :content="{ outcome: { type: 'interrupt', interrupts: [approvedInterrupt] } }"
    role="interrupt"
  />
  <InterruptMessageRender
    :content="{ outcome: { type: 'interrupt', interrupts: [rejectedInterrupt] } }"
    role="interrupt"
  />
  <InterruptMessageRender
    :content="{ outcome: { type: 'interrupt', interrupts: [revokedInterrupt] } }"
    role="interrupt"
  />
</div>
```

**渲染效果**

<div class="demo" style="display: flex; flex-direction: column; gap: 12px;">
  <ToolApprovalCard :interrupt="approvedInterrupt" />
  <ToolApprovalCard :interrupt="rejectedInterrupt" />
  <ToolApprovalCard :interrupt="revokedInterrupt" />
</div>

## 只读回显（readonly）

`outcome.success` 时 [InterruptMessageRender](/components/agent/interrupt-message) 会将 `AIDevToolApprovalResume.payload.metadata` 还原为 `interrupt` 形态，并以 `readonly` 挂载本组件：

```vue
<ToolApprovalCard
  :interrupt="approvedInterrupt"
  readonly
/>
```

**渲染效果**（待审批态下 readonly 不展示刷新图标与「取消审批」按钮）

<div class="demo">
  <ToolApprovalCard
    :interrupt="pendingInterrupt"
    readonly
  />
</div>

## API

### Props

| 属性名            | 类型                         | 默认值 | 说明                                         |
| ----------------- | ---------------------------- | ------ | -------------------------------------------- |
| interrupt         | `AIDevToolApprovalInterrupt` | —      | **必填**，含 `metadata.ticket`               |
| onInterruptResume | `OnInterruptResume`          | —      | 取消审批 / 刷新时触发，签名为 `(payload, interrupt)`，payload 为 `{ operation, payload: { interrupt_id } }`，`operation` 取 `InterruptResumeOperation.ApprovalCancel`（取消）或 `InterruptResumeOperation.ApprovalRefresh`（刷新），两者 payload 结构一致 |
| readonly          | `boolean`                    | —      | 只读回显态（`outcome.success` 结果回显）：隐藏取消 / 刷新按钮，不接受交互 |

### Events / Slots / Expose

无。打开链接、复制剪贴板在组件内部完成；取消审批通过 `onInterruptResume({ operation: InterruptResumeOperation.ApprovalCancel, payload: { interrupt_id: interrupt.id } }, interrupt)`、刷新单据通过 `onInterruptResume({ operation: InterruptResumeOperation.ApprovalRefresh, payload: { interrupt_id: interrupt.id } }, interrupt)` 通知业务侧处理。

## 依赖

- `bkui-vue`：`Button`、`Loading`
- `useClipboard` — 复制单据
- `v-overflow-tips` — 处理人超长省略

## 关联组件

- [InterruptMessage 中断消息](/components/agent/interrupt-message)
- [中断类型 Interrupt](../../types/interrupt.md)
- [常量枚举 Constants](../../types/constants.md) — `APPROVAL_STATUS`、`APPROVAL_STATUS_MAP`
