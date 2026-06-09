---
name: useFlowNodeActions
slug: use-flow-node-actions
category: composable
description: >-
  聚合 FlowAgent 节点行尾操作（详情 / 重试 / 跳过）为声明式视图模型列表，显隐与 resume 回调收敛于此。
aiSummary: >
  useFlowNodeActions 接收 onInterruptResume 与 openNodeDetail，返回 getNodeActions(task, node)。
  失败节点按 retryable/skippable 展示重试/跳过，详情恒在末尾；点击 resume 时不传 interrupt。
relatedComponents:
  - slug: flow-agent-content
    relation: FlowAgentContent 内部消费，驱动节点行尾按钮组渲染
sinceVersion: 2.0.0
---

# useFlowNodeActions 节点行尾操作

> **分类**：composable

将 FlowAgent 节点行尾的「详情（打开侧栏）」与「重试 / 跳过（回传 Agent resume）」聚合为统一的声明式操作列表。`FlowAgentContent` 只需遍历 `getNodeActions` 返回值渲染按钮，显隐与点击行为均收敛于此 composable。

源码：`src/components/chat-content/flow-agent-content/use-flow-node-actions.ts`

## 函数签名

```typescript
function useFlowNodeActions(options: {
  /** resume 回调（与第三方审批取消同一回调，按 payload.operation 分流） */
  onInterruptResume: Ref<OnInterruptResume | undefined>;
  /** 打开节点详情侧栏（复用 useFlowTab 的能力） */
  openNodeDetail: (task: BkFlowTask, node: BkFlowNode) => void;
}): {
  getNodeActions: (task: FlowTaskVM, node: FlowNodeVM) => FlowNodeActionVM[];
};
```

## 返回值：FlowNodeActionVM

```typescript
type FlowNodeActionId =
  | 'detail'
  | InterruptResumeOperation.FlowNodeRetry
  | InterruptResumeOperation.FlowNodeSkip;

interface FlowNodeActionVM {
  icon: Component;
  id: FlowNodeActionId;
  label: string;
  run: () => void;
}
```

| 字段    | 说明                           |
| ------- | ------------------------------ |
| `icon`  | 按钮图标组件                   |
| `id`    | 唯一标识，用于 `v-for` key     |
| `label` | 国际化文案                     |
| `run`   | 点击执行（详情或 resume）      |

## 操作显隐规则

| 操作 | `id`               | 显隐条件                                   | 点击行为                                      |
| ---- | ------------------ | ------------------------------------------ | --------------------------------------------- |
| 重试 | `flow_node_retry`  | `convergedState === 'failed'` 且 `retryable` | 调用 `onInterruptResume`，**不传** `interrupt` |
| 跳过 | `flow_node_skip`   | `convergedState === 'failed'` 且 `skippable` | 同上                                          |
| 详情 | `detail`           | 始终（Share 模式由上层组件隐藏整组）       | 调用 `openNodeDetail(task.raw, node.raw)`     |

展示顺序：重试 → 跳过 → 详情。

## resume 负载格式

```typescript
// 重试
onInterruptResume?.({
  operation: InterruptResumeOperation.FlowNodeRetry,
  payload: { node_id: node.id, task_id: task.task_id },
});

// 跳过
onInterruptResume?.({
  operation: InterruptResumeOperation.FlowNodeSkip,
  payload: { node_id: node.id, task_id: task.task_id },
});
```

## 使用示例

`FlowAgentContent` 内部用法（业务侧通常通过 `MessageRender` 传入 `onInterruptResume`，无需直接调用本 composable）：

```typescript
import { toRef } from 'vue';
import { useFlowNodeActions } from '@blueking/chat-x';
// 或相对路径：'./use-flow-node-actions'

const { getNodeActions } = useFlowNodeActions({
  onInterruptResume: toRef(props, 'onInterruptResume'),
  openNodeDetail,
});

// 模板中
// v-for="action in getNodeActions(task, node)" :key="action.id"
// @click.stop="action.run()"
```

## 扩展新操作

在 `RESUME_ACTION_DEFS` 注册表中追加一项即可，需声明 `visible` 与 `operation` 枚举：

```typescript
const RESUME_ACTION_DEFS: FlowNodeResumeActionDef[] = [
  // 现有：重试、跳过
  {
    icon: MyIcon,
    id: InterruptResumeOperation.MyNewOp, // 需先在 InterruptResumeOperation 扩展
    label: () => t('新操作'),
    visible: node => /* 自定义显隐 */,
  },
];
```

同时在 `interrupt.ts` 扩展 `InterruptResumeOperation` 与 `FlowNodeResume` 联合类型。

## 关联文档

- [FlowAgentContent 执行内容](/components/agent/flow-agent-content) — 消费方组件
- [中断类型 Interrupt](/types/interrupt) — `InterruptResumeOperation`、`FlowNodeResume`、`OnInterruptResume`
- [ActivityMessage 活动消息](/components/message/activity-message) — `onInterruptResume` 透传链路
- [MessageRender 消息渲染器](/components/message/message-render) — 顶层透传入口
