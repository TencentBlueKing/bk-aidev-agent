# FlowAgentContent FlowAgent 执行内容

> 能力域：Agent 能力 ｜ 导入：`import { FlowAgentContent } from '@blueking/chat-x'` ｜ since 1.0.0

渲染 FlowAgent 任务/节点执行状态、耗时、详情入口和自定义 Tab 联动。 源码位置：src/components/chat-content/flow-agent-content/flow-agent-content.vue。

**关联**：flow-agent-node-detail（详情入口点击后挂载到自定义 Tab 渲染）、activity-layout（提供可折叠的活动容器外壳）、chat-container（通过自定义 Tab 在侧栏展示节点详情）

---

# FlowAgentContent FlowAgent 执行内容

> **能力域**：Agent 能力

渲染 FlowAgent（标准运维 / 流程编排）执行过程的活动组件，以「任务 → 节点」两级结构展示执行状态、耗时统计与详情入口。组件内部消费 `useCustomTabConsumer`，点击节点「详情」会向侧栏的自定义 Tab 注入 `FlowAgentNodeDetail` 渲染节点输入输出。

通常不需要直接使用，`MessageRender` 会根据消息 `content.type === flow_agent` 自动渲染。

## 源码事实

- **源码位置**：`src/components/chat-content/flow-agent-content/flow-agent-content.vue`
- **能力说明**：渲染 FlowAgent 任务/节点执行状态、耗时、详情入口和自定义 Tab 联动。

## 核心能力

- **状态聚合统计**：汇总所有任务的 `statistics.state_counts`，在标题栏按「执行中 / 成功 / 失败 / 挂起 / 待执行」分类展示带颜色的计数（超过 99 显示 `99+`）
- **两级折叠**：任务整体由 `ActivityLayout` 折叠；每个任务节点列表可单独展开/收起
- **耗时格式化**：节点耗时与任务总耗时按 `d/h/m/s` 紧凑展示，小于 1 秒显示 `<1s`
- **节点行尾操作**：hover 失败节点行显示「重试 / 跳过 / 详情」按钮组（间距 12px）；成功 / 运行中等非失败节点仅显示「详情」。重试 / 跳过依赖节点 `retryable` / `skippable` 能力位，通过 `onInterruptResume` 回传 Agent
- **详情入口联动**：「详情」按钮点击后通过自定义 Tab 挂载 `FlowAgentNodeDetail`
- **分享态降级**：`RenderMode.Share` 下隐藏耗时与行尾操作按钮，仅保留只读的执行状态

## 状态映射

组件将后端原始 `state` / `task_state` 归一为 5 类收敛状态（`getConvergedState`），用于图标、颜色与统计分类：

| 收敛状态    | 颜色        | 原始状态                                                                          |
| ----------- | ----------- | --------------------------------------------------------------------------------- |
| `success`   | `#18B456`   | `FINISHED`                                                                        |
| `failed`    | `#EA3636`   | `FAILED`、`REVOKED`、`ROLL_BACK_FAILED`                                            |
| `suspended` | `#F59500`   | `SUSPENDED`                                                                       |
| `pending`   | `#4D4F56`   | `PENDING`                                                                         |
| `running`   | `#3A84FF`   | `CREATED`、`LOOP_READY`、`READY`、`RUNNING`、`BLOCKED`、`ROLLING_BACK`、`ROLL_BACK_SUCCESS` 及未知状态（兜底） |

## 基础用法

`content` 为任务数组 `BkFlowTask[]`；传入单个对象时组件会自动包装为单元素数组。

```vue
<template>
  <FlowAgentContent
    :content="flowContent"
    :message-uid="messageUid"
    :on-interrupt-resume="handleInterruptResume"
    :status="status"
  />
</template>

<script setup lang="ts">
  import { FlowAgentContent } from '@blueking/chat-x';
  import type { BkFlowMessageContent, OnInterruptResume } from '@blueking/chat-x';

  const messageUid = 'flow-msg-1';
  const status = 'success';
  const handleInterruptResume: OnInterruptResume = async payload => {
    console.log('flow node resume:', payload);
  };
  const flowContent: BkFlowMessageContent = [
    {
      task_id: 100,
      task_name: '主机巡检流程',
      task_state: 'FINISHED',
      task_outputs: { result: 'ok' },
      statistics: { state_counts: { FINISHED: 2, FAILED: 1 }, total: 3 },
      nodes: {
        n1: { id: 'n1', name: '采集主机指标', state: 'FINISHED', elapsed_time: 12, type: 'task', loop: 0, retry: 0, skip: false, start_time: '', finish_time: '' },
        n2: { id: 'n2', name: '分析异常项', state: 'FINISHED', elapsed_time: 65, type: 'task', loop: 0, retry: 0, skip: false, start_time: '', finish_time: '' },
        n3: { id: 'n3', name: '推送告警', state: 'FAILED', elapsed_time: 3, type: 'task', loop: 0, retry: 1, skip: false, retryable: true, skippable: true, start_time: '', finish_time: '' },
      },
    },
  ];
</script>
```

**渲染效果**（hover 失败节点行可看到「重试 / 跳过 / 详情」按钮组；点击「详情」会向侧栏自定义 Tab 注入节点详情）

## 执行中状态

`status` 为 `pending` / `streaming` 时，标题栏图标显示为加载动画；运行中的节点显示旋转 Loading，待执行 / 挂起节点显示对应颜色的状态点。

## 失败节点重试 / 跳过

失败节点（`convergedState === 'failed'`）且具备对应能力位时，hover 行尾展示「重试」或「跳过」按钮。点击后调用 `onInterruptResume`，**不传** `interrupt` 参数：

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

| 按钮 | 显隐条件                              | `operation`          |
| ---- | ------------------------------------- | ---------------------- |
| 重试 | 失败态且 `node.retryable === true`    | `flow_node_retry`      |
| 跳过 | 失败态且 `node.skippable === true`    | `flow_node_skip`       |
| 详情 | 始终展示（Share 模式除外）            | —（打开侧栏 Tab，不走 resume） |

行尾操作由内部 composable [`useFlowNodeActions`](/composables/use-flow-node-actions) 聚合为声明式列表，组件层仅遍历渲染。

## 节点详情联动

点击节点「详情」按钮时，组件调用 `addCustomTab` 注入一个以 `${task_id}|${node.id}|${node.name}` 为唯一 `name` 的 Tab，渲染组件为 `FlowAgentNodeDetail`：

```ts
addCustomTab?.({
  label: node.name,
  name: `${task.task_id}|${node.id}|${node.name}`,
  data: {
    component: BkFlowNodeDetail,
    messageUid: props.messageUid,
    props: {
      loading: true,
      node_id: node.id,
      node_name: node.name,
      task_id: task.task_id,
      task_name: task.task_name,
      data: {},
    },
  },
});
```

> 实际节点详情数据由应用层在 `ChatContainer` 的 `onCustomTabChange` 中异步拉取后回填，组件本身只负责挂载占位与传参。组件卸载时（在消息容器滚动上下文中）会自动调用 `removeCustomTab` 清理对应 Tab。

## 组件结构

```
ActivityLayout（activity-type=flow_agent，v-model:collapsed）
├── #title（执行情况统计栏）
│   ├── AiLoading / ArrowRightIcon（加载态 / 折叠箭头）
│   └── flow-agent-stat-item × N（按收敛状态分类的计数）
└── flow-agent-task-group × N（任务）
    ├── flow-agent-task-header（点击折叠当前任务）
    │   ├── task-arrow（任务展开箭头）
    │   ├── task-state-icon（Loading / 状态图标）
    │   ├── task-name（HighlightKeyword + 溢出提示）
    │   └── task-time（任务总耗时 = 各节点耗时累加）
    └── flow-agent-task-nodes（v-show 折叠）
        └── flow-agent-node-item × N（节点）
            ├── node-status（Loading / 状态圆点）
            ├── node-name（HighlightKeyword + 溢出提示）
            └── node-trailing（非 Share 态）
                ├── node-time（节点耗时，hover 时隐藏）
                └── node-actions（hover 时显示按钮组，间距 12px）
                    ├── node-action-btn「重试」（失败 + retryable）
                    ├── node-action-btn「跳过」（失败 + skippable）
                    └── node-action-btn「详情」（始终，点击挂载详情 Tab）
```

## API

### Props

| 属性名     | 类型                     | 必填 | 默认值      | 说明                                                                       |
| ---------- | ------------------------ | ---- | ----------- | -------------------------------------------------------------------------- |
| content    | `BkFlowMessageContent`   | 否   | `[{}]`      | 任务数组；传入单个 `BkFlowTask` 时自动包装为单元素数组                       |
| messageUid | `string`                 | 否   | —           | 所属消息唯一标识，注入到节点详情 Tab 的 `data.messageUid`，用于异步回填数据 |
| onInterruptResume | `OnInterruptResume` | 否   | —           | 节点「重试 / 跳过」与第三方审批取消复用同一回调，按 `payload.operation` 分流；流程节点操作时不传 `interrupt` |
| status     | `MessageStatus`          | 否   | —           | 消息状态；`pending` / `streaming` 时标题栏显示加载动画                       |

### Emits

- 无。

### Slots

- 无。

### Expose

- 无。

## 类型定义

```typescript
// 来自 @blueking/chat-x 导出
type BkFlowMessageContent = BkFlowTask[];

interface BkFlowTask {
  task_id: number;
  task_name: string;
  task_state: string;          // 原始任务状态，经 getConvergedState 归一
  task_outputs: unknown;       // 任务输出（当前展示区块已注释，不渲染）
  statistics: {
    state_counts: Record<string, number>; // 原始状态 → 数量，用于标题统计聚合
    total: number;
  };
  nodes: Record<string, BkFlowNode>;       // key 为节点 id
}

interface BkFlowNode {
  id: string;
  name: string;
  state: string;        // 原始节点状态
  elapsed_time: number; // 耗时（秒）
  type: string;
  loop: number;
  retry: number;
  retryable?: boolean; // 是否可重试（失败节点「重试」按钮显隐）
  skip: boolean;
  skippable?: boolean; // 是否可跳过（失败节点「跳过」按钮显隐）
  start_time: string;
  finish_time: string;
}
```

## 组件依赖

- `AiLoading` — 标题栏流式加载动画
- `ActivityLayout` — 可折叠活动容器外壳
- `BkFlowNodeDetail` — 节点详情面板（经自定义 Tab 挂载）
- `Loading`（bkui-vue） — 运行中状态的旋转指示
- `HighlightKeyword` — 任务 / 节点名称的搜索关键词高亮

## 注意事项

1. **依赖自定义 Tab 上下文**：组件内部使用 `useCustomTabConsumer()!`，必须存在 `useCustomTabProvider` 提供者（`ChatContainer` 已内置）。脱离上下文直接使用需自行提供，否则详情入口会报错。
2. **统计来自 `statistics.state_counts` 而非节点遍历**：标题栏计数直接读取后端下发的统计，不会实时统计 `nodes`；两者不一致时以 `state_counts` 为准。
3. **任务总耗时为节点累加**：`task-time` 由各节点 `elapsed_time` 求和得到，并非任务级独立字段。
4. **`task_outputs` 暂不渲染**：模板中任务输出展示区块已注释，传入也不会显示。
5. **未知状态兜底为 `running`**：`getConvergedState` 对未识别的原始状态统一归为运行中。
6. **Share 模式降级**：`RenderMode.Share` 下不渲染节点耗时与行尾操作按钮（重试 / 跳过 / 详情），仅保留只读执行状态。
7. **`onInterruptResume` 透传链路**：`MessageRender` → `ActivityMessage` → `FlowAgentContent`；未传入时重试 / 跳过按钮仍展示但点击无回调。

## 关联组件

- [FlowAgentNodeDetail](/components/agent/flow-agent-node-detail) — 节点详情面板
- [ActivityLayout](/components/helper/activity-layout) — 可折叠活动容器
- [ChatContainer](/components/setup/chat-container) — 侧栏自定义 Tab 挂载场景
- [useFlowNodeActions](/composables/use-flow-node-actions) — 节点行尾操作聚合 composable
- [中断类型 Interrupt](/types/interrupt) — `InterruptResumeOperation`、`FlowNodeResume`、`OnInterruptResume`
- [使用建议] 优先通过上层组合组件（`MessageRender`）使用；直接使用前请确认 `content` 数据结构来自对应类型定义。
