---
name: ExecutionSummary 执行摘要
slug: execution-summary
kind: component
domain: agent
description: 按消息流提取执行摘要，支持关键词定位和消息渲染。
aiSummary: >
  按消息流提取执行摘要，支持关键词定位和消息渲染。
  源码位置：src/components/execution-summary/execution-summary.vue。
relatedComponents:
  - slug: message-render
    relation: 摘要列表内渲染消息内容
  - slug: highlight-keyword
    relation: 搜索关键词注入与高亮
  - slug: chat-container
    relation: 常与侧栏「执行情况」Tab 组合
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import ExecutionSummaryComp from '../../../src/components/execution-summary/execution-summary.vue'

  const locateInfo = ref('');

  const mockGroups = [
    {
      uid: 'group-1',
      type: 'assistant',
      checked: false,
      isHover: false,
      startTime: Date.now() - 120000,
      messages: [
        {
          id: 'msg-1',
          role: 'assistant',
          status: 'complete',
          content: '正在查询数据库中的用户信息...',
          toolCalls: [
            {
              id: 'tc-1',
              type: 'function',
              function: { name: 'query_database', arguments: '{"table": "users", "limit": 10}' },
              status: 'complete',
              toolMessage: {
                id: 'tm-1',
                role: 'tool',
                content: '查询成功，返回 10 条记录',
                toolCallId: 'tc-1',
                duration: 1200,
              },
            },
          ],
        },
      ],
    },
    {
      uid: 'group-2',
      type: 'assistant',
      checked: false,
      isHover: false,
      startTime: Date.now() - 60000,
      messages: [
        {
          id: 'msg-2',
          role: 'assistant',
          status: 'complete',
          content: '正在分析用户行为数据...',
          toolCalls: [
            {
              id: 'tc-2',
              type: 'function',
              function: { name: 'analyze_behavior', arguments: '{"metric": "active_users"}' },
              status: 'complete',
              toolMessage: {
                id: 'tm-2',
                role: 'tool',
                content: '分析完成：日活用户 1,234 人',
                toolCallId: 'tc-2',
                duration: 3500,
              },
            },
          ],
        },
      ],
    },
  ];

  const handleLocate = (uid, group) => {
    locateInfo.value = `定位到消息组: ${uid}（${new Date(group.startTime).toLocaleTimeString()}）`;
  };

  const handleUpdateKeyword = (keyword) => {
    console.log('搜索关键词:', keyword);
  };
</script>

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

<div class="demo">
  <div style="height: 400px; border: 1px solid #dcdee5; border-radius: 8px; overflow: hidden;">
    <ExecutionSummaryComp
      :message-groups="mockGroups"
      @locate-message-group="handleLocate"
      @update-keyword="handleUpdateKeyword"
    />
  </div>
  <div v-if="locateInfo" style="margin-top: 8px; padding: 8px 12px; background: #e1ecff; border-radius: 4px; font-size: 13px;">
    {{ locateInfo }}
  </div>
</div>

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

<div class="demo">
  <div style="height: 300px; border: 1px solid #dcdee5; border-radius: 8px; overflow: hidden;">
    <ExecutionSummaryComp :message-groups="[]" />
  </div>
</div>

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
