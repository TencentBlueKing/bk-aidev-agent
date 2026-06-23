# ToolApprovalCard 工具审批卡片

> 能力域：Agent 能力 ｜ 导入：`import { ToolApprovalCard } from '@blueking/chat-x'` ｜ since 1.0.0

渲染 AIDevToolApproval 中断的审批信息与取消操作；outcome.success 回显时以 readonly 只读展示。 源码位置：src/components/chat-message/interrupt-message/tool-approval-card.vue。

**关联**：interrupt-message（InterruptMessageRender 按 reason 派发渲染）

---

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
├── 标题栏：左侧色条 + 单据标题 + 复制图标 + 状态徽章（评审中/已通过/已拒绝/已撤销等）
├── 字段区：单据编号、提交时间
├── 处理人：当前处理人（overflow-tips 省略）
└── 操作区：查看单据详情（新窗口打开 url）、取消审批（仅 pending / draft 且非 readonly）
```

`readonly` 为 `true` 时用于 `outcome.success` 结果回显：隐藏「取消审批」按钮，不接受审批取消交互。通常由 [InterruptMessageRender](/components/agent/interrupt-message) 内部传入，业务侧无需手动设置。

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

## 只读回显（readonly）

`outcome.success` 时 [InterruptMessageRender](/components/agent/interrupt-message) 会将 `AIDevToolApprovalResume.payload.metadata` 还原为 `interrupt` 形态，并以 `readonly` 挂载本组件：

```vue
<ToolApprovalCard
  :interrupt="approvedInterrupt"
  readonly
/>
```

**渲染效果**（待审批态下 readonly 不展示「取消审批」）

## API

### Props

| 属性名            | 类型                         | 默认值 | 说明                                         |
| ----------------- | ---------------------------- | ------ | -------------------------------------------- |
| interrupt         | `AIDevToolApprovalInterrupt` | —      | **必填**，含 `metadata.ticket`               |
| onInterruptResume | `OnInterruptResume`          | —      | 取消审批时触发，签名为 `(payload, interrupt)`，payload 为 `{ operation: InterruptResumeOperation.ApprovalCancel, payload: { interrupt_id } }` |
| readonly          | `boolean`                    | —      | 只读回显态（`outcome.success` 结果回显）：隐藏取消审批按钮，不接受交互 |

### Events / Slots / Expose

无。打开链接、复制剪贴板在组件内部完成；取消审批通过 `onInterruptResume({ operation: InterruptResumeOperation.ApprovalCancel, payload: { interrupt_id: interrupt.id } }, interrupt)` 通知业务侧处理。

## 依赖

- `bkui-vue`：`Button`、`Loading`
- `useClipboard` — 复制单据
- `v-overflow-tips` — 处理人超长省略

## 关联组件

- [InterruptMessage 中断消息](/components/agent/interrupt-message)
- [中断类型 Interrupt](../../types/interrupt.md)
- [常量枚举 Constants](../../types/constants.md) — `APPROVAL_STATUS`、`APPROVAL_STATUS_MAP`
