# ExecutionSummary 执行摘要

> 能力域：Agent 能力 ｜ 导入：`import { ExecutionSummary } from '@blueking/chat-x'` ｜ since 1.0.0

按消息流提取执行摘要，支持关键词定位和消息渲染。 源码位置：src/components/execution-summary/execution-summary.vue。

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
execution-summary
├── execution-summary-header
│   └── Input（关键词搜索框，clearable）
└── execution-summary-content
    ├── 有数据时：
    │   └── content-item × N（时间线节点）
    │       ├── timeline-dot（时间节点圆点）
    │       ├── content-item-time（格式化时间）
    │       ├── content-item-locate（hover 显示定位按钮）
    │       ├── content-item-messages（MessageRender × N）
    │       └── timeline-line（连接线，最后一项不显示）
    └── 无数据时：
        └── Exception（空状态）+ 清空搜索按钮
```

## 空状态

当 `messageGroups` 为空数组时，显示空状态提示：

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
