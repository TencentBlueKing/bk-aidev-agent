# ExecutionSummary 执行摘要

> 能力域：Agent 能力 ｜ 导入：`import { ExecutionSummary } from '@blueking/chat-x'` ｜ since 1.0.0

按消息流提取执行摘要，支持关键词定位和消息渲染。 通过 useExecutionPanelProvider 提供 EXECUTION_PANEL_TOKEN，面板内消息按只读呈现， FlowAgent 失败节点在面板内不展示重试/跳过，只保留详情。 源码位置：src/components/execution-summary/execution-summary.vue。

**关联**：message-render（摘要列表内渲染消息内容）、highlight-keyword（搜索关键词注入与高亮）、chat-container（常与侧栏「执行情况」Tab 组合）

---

# ExecutionSummary 执行摘要
## 源码事实

- **源码位置**：`src/components/execution-summary/execution-summary.vue`
- **能力域**：Agent 能力
- **能力说明**：按消息流提取执行摘要，支持关键词定位和消息渲染。

> **能力域**：Agent 能力

执行摘要面板组件，以时间线形式展示对话中的工具调用和 FlowAgent 活动记录。支持关键词搜索过滤和点击定位到对话中的消息位置。

通常不需要直接使用，`ChatContainer` 会在侧边栏的「执行情况」Tab 中自动渲染。

## 核心能力

- **时间线布局**：每组消息按时间节点排列，带连接线
- **关键词搜索**：实时过滤匹配的执行记录
- **对话定位**：hover 显示「在对话中定位」按钮，点击滚动到对应消息
- **空状态处理**：无数据或搜索无结果时显示空状态提示
- **面板上下文（只读呈现）**：组件 setup 时通过 `useExecutionPanelProvider()` 提供 `EXECUTION_PANEL_TOKEN`，供内部消息组件识别「当前处于侧栏面板内」并隐藏交互操作。目前 `FlowAgentContent` 据此不展示节点「重试 / 跳过」，只保留「详情」

## 基础用法

```vue
<template>
  <ExecutionSummary
    :message-groups="executionGroups"
    @locate-message-group="handleLocate"
    @update-keyword="handleUpdateKeyword"
  />
</template>

<script setup lang="ts">
  import { ExecutionSummary, type MessageGroup } from '@blueking/chat-x';

  const handleLocate = (uid: string, group: MessageGroup) => {
    const dom = document.getElementById(uid);
    dom?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleUpdateKeyword = (keyword: string) => {
    console.log('搜索关键词:', keyword);
  };
</script>
```

**渲染效果**（包含搜索过滤和定位功能，hover 消息组可看到「在对话中定位」按钮）

## 组件结构

```
ai-execution-summary
├── ai-execution-summary-header（仅 messageGroups 非空时渲染）
│   └── Input（关键词搜索框，clearable）
└── ai-execution-summary-content
    ├── 有数据时：
    │   └── content-item × N（时间线节点）
    │       ├── timeline-dot（时间节点圆点）
    │       ├── content-item-time（格式化时间）
    │       ├── content-item-locate（hover 显示定位按钮）
    │       ├── content-item-messages（MessageRender × N）
    │       └── timeline-line（连接线，最后一项不显示）
    └── 无数据时：
        └── Exception（scene="part"）+「暂无数据」/「搜索结果为空」文案（有关键词时附带「清空搜索」）
```

## 空状态

当 `messageGroups` 为空数组时，**不渲染搜索 header**，内容区整块展示空态（bkui `Exception` +「暂无数据」；若仍有搜索关键词则为「搜索结果为空」并提供「清空搜索」）：

## 与 ChatContainer 配合

`ChatContainer` 通过 `useMessageGroup` 计算 `executionGroups`（仅包含工具调用和 FlowAgent 消息），并传给 `ExecutionSummary`：

```vue
<!-- ChatContainer 内部 -->
<ExecutionSummary
  :message-groups="executionGroups"
  @locate-message-group="handleLocateMessageGroup"
  @update-keyword="handleUpdateKeyword"
/>
```

## 面板内的消息按只读呈现

面板与对话流复用同一套渲染链路（`MessageRender` → `ContentRender` → 具体内容组件），但面板定位是「回看执行过程」，不承载操作。为此组件在 setup 阶段 provide 面板上下文：

```typescript
// 源码：src/composables/use-common.ts（内部上下文，未从包入口导出）
import { useExecutionPanelProvider } from '../../composables/use-common';

// 面板身份在组件树中恒定，provide 常量 true 即可，无需响应式
useExecutionPanelProvider();
```

内容组件用 `useExecutionPanelInject()` 读取（缺省 `false`，即对话流内）。当前的差异：

| 内容 | 对话流内 | 侧栏「执行情况」面板内 |
| ---- | -------- | ---------------------- |
| FlowAgent 失败节点「重试 / 跳过」 | 展示（依赖 `retryable` / `skippable`） | **不展示** |
| FlowAgent 节点「详情」 | 展示 | 展示 |

新增内容组件若也需要区分这两种场景，同样注入 `useExecutionPanelInject()` 即可，不必扩展 props。`EXECUTION_PANEL_TOKEN` 与这两个函数同属 `use-common.ts` 的内部上下文，未从 `@blueking/chat-x` 包入口导出，仅供库内组件使用。详见 [FlowAgentContent](/components/agent/flow-agent-content)。

## API

### Props

| 属性名        | 类型             | 必填 | 说明             |
| ------------- | ---------------- | ---- | ---------------- |
| messageGroups | `MessageGroup[]` | ✓    | 执行摘要消息分组 |

### Events

| 事件名             | 参数                                  | 说明                     |
| ------------------ | ------------------------------------- | ------------------------ |
| locateMessageGroup | `(uid: string, group: MessageGroup)` | 点击「在对话中定位」按钮，参数为消息组 `MessageGroup.uid` |
| updateKeyword      | `(keyword: string)`                   | 搜索关键词变更           |

## 类型定义

```typescript
import { type MessageGroup } from '@blueking/chat-x';

interface MessageGroup {
  uid: string;
  type: MessageRole;
  messages: Message[];
  checked: boolean;
  isHover: boolean;
  pause?: boolean;
  startTime?: number;
}
```

## 关联组件

- [MessageRender](/components/message/message-render) — 摘要内消息渲染
- [HighlightKeyword](/components/helper/highlight-keyword) — 搜索高亮
- [ChatContainer](/components/setup/chat-container) — 侧栏挂载场景
