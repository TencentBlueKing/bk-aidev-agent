# useFlowNodeActions

> 未从包入口导出：内部实现 ｜ since 2.0.0

useFlowNodeActions 接收 onInterruptResume 与 openNodeDetail，返回 getNodeActions 与 isNodePending。 失败节点按 retryable/skippable 展示重试/跳过，详情恒在末尾；点击后进入 pending 防重复提交， 以 task_id:node_id:retry 为键自动收敛；点击 resume 时不传 interrupt。

**关联**：flow-agent-content（FlowAgentContent 内部消费，驱动节点行尾按钮组渲染）

---

# useFlowNodeActions 节点行尾操作

> **分类**：composable

将 FlowAgent 节点行尾的「详情（打开侧栏）」与「重试 / 跳过（回传 Agent resume）」聚合为统一的声明式操作列表。`FlowAgentContent` 只需遍历 `getNodeActions` 返回值渲染按钮，显隐与点击行为均收敛于此 composable。

源码：`src/components/chat-content/flow-agent-content/use-flow-node-actions.ts`

## 函数签名

```typescript
function useFlowNodeActions(options: {
  /** 隐藏重试 / 跳过等交互式 resume 操作（分享态只读，仅保留「详情」查看入口） */
  hideResumeActions?: Ref<boolean>;
  /** resume 回调（与第三方审批取消同一回调，按 payload.operation 分流） */
  onInterruptResume: Ref<OnInterruptResume | undefined>;
  /** 打开节点详情侧栏（复用 useFlowTab 的能力） */
  openNodeDetail: (task: BkFlowTask, node: BkFlowNode) => void;
}): {
  getNodeActions: (task: FlowTaskVM, node: FlowNodeVM) => FlowNodeActionVM[];
  /** 当前节点是否有进行中的 resume 操作（供视图层常驻显示按钮组） */
  isNodePending: (task: FlowTaskVM, node: FlowNodeVM) => boolean;
};
```

## 返回值：FlowNodeActionVM

```typescript
type FlowNodeActionId =
  | 'detail'
  | InterruptResumeOperation.FlowNodeRetry
  | InterruptResumeOperation.FlowNodeSkip;

interface FlowNodeActionVM {
  /** 是否禁用点击（任一 resume 操作进行中时，重试 / 跳过均禁用） */
  disabled: boolean;
  icon: Component;
  id: FlowNodeActionId;
  /** 国际化文案（进行中时切换为「重试中 / 跳过中」） */
  label: string;
  /** 是否处于进行中态：图标切换为 loading */
  loading: boolean;
  /** 因另一操作进行中而禁用时的 hover 提示 */
  tooltip?: string;
  run: () => void;
}
```

| 字段       | 说明                                                           |
| ---------- | -------------------------------------------------------------- |
| `disabled` | 禁用点击；resume 进行中时重试 / 跳过均为 `true`，详情恒为 `false` |
| `icon`     | 按钮图标组件（`loading` 时由上层切换为 Loading 组件）          |
| `id`       | 唯一标识，用于 `v-for` key                                     |
| `label`    | 国际化文案；进行中为「重试中 / 跳过中」                        |
| `loading`  | 本操作进行中时为 `true`                                        |
| `tooltip`  | 被另一操作阻塞时的 hover 提示（如「任务正在重试中，不可跳过」） |
| `run`      | 点击执行（详情或 resume）；进行中重复调用被内部忽略              |

## 操作显隐规则

| 操作 | `id`               | 显隐条件                                   | 点击行为                                      |
| ---- | ------------------ | ------------------------------------------ | --------------------------------------------- |
| 重试 | `flow_node_retry`  | `convergedState === 'failed'` 且 `retryable` | 调用 `onInterruptResume`，**不传** `interrupt` |
| 跳过 | `flow_node_skip`   | `convergedState === 'failed'` 且 `skippable` | 同上                                          |
| 详情 | `detail`           | 始终（含 Share 分享态）                     | 调用 `openNodeDetail(task.raw, node.raw)`     |

展示顺序：重试 → 跳过 → 详情。

> **分享态过滤**：传入 `hideResumeActions`（`Ref<boolean>`，如 `RenderMode.Share`）为 `true` 时，`getNodeActions` 直接过滤掉重试 / 跳过，仅返回「详情」查看入口；用于只读分享场景放开查看、禁止交互。

## pending 态与防重复提交

点击重试或跳过后：

1. 以 `task_id:node_id:retry` 为键写入 `pendingMap`，同一节点仅允许一个进行中的 resume 操作
2. 进行中按钮：`loading: true`、`disabled: true`、`label` 切换为「重试中 / 跳过中」
3. 另一 resume 按钮：`disabled: true`，`tooltip` 给出阻塞原因
4. 详情按钮：不受影响
5. `isNodePending(task, node)` 返回 `true`，供视图层添加 `is-pending` class 常驻显示按钮组
6. 后端推送新状态且 `node.retry` 变化时，pending 键自动失效，按钮恢复可用

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

const { getNodeActions, isNodePending } = useFlowNodeActions({
  // 分享态只读：过滤重试 / 跳过，仅保留详情
  hideResumeActions: computed(() => renderMode.value === RenderMode.Share),
  onInterruptResume: toRef(props, 'onInterruptResume'),
  openNodeDetail,
});

// 模板中
// :class="{ 'is-pending': isNodePending(task, node) }"
// v-for="action in getNodeActions(task, node)" :key="action.id"
// :class="{ 'is-disabled': action.disabled }"
// v-tippy="action.tooltip ? { content: action.tooltip } : { content: '' }"
// @click.stop="handleActionClick(action)"  // 禁用态拦截，避免重复提交
```

## 扩展新操作

在 `RESUME_ACTION_DEFS` 注册表中追加一项即可，需声明 `visible` 与 `operation` 枚举：

```typescript
const RESUME_ACTION_DEFS: FlowNodeResumeActionDef[] = [
  // 现有：重试、跳过
  {
    blockedTip: () => t('另一操作进行中的提示'),
    icon: MyIcon,
    id: InterruptResumeOperation.MyNewOp, // 需先在 InterruptResumeOperation 扩展
    label: () => t('新操作'),
    pendingLabel: () => t('新操作进行中'),
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
