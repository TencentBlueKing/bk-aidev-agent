# ActivityLayout 活动布局

> 能力域：辅助能力 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

活动消息的折叠布局容器，提供 title/default 插槽。 源码位置：src/components/chat-content/activity-layout/activity-layout.vue。

**关联**：activity-message（活动消息通过本组件承载标题栏与内容区）、knowledge-rag-content（知识召回活动复用本组件展示加载标题与正文）、reference-doc-content（引用文档活动复用本组件展示文档数量与引用列表）、flow-agent-content（FlowAgent 活动复用本组件，但隐藏默认折叠箭头）

---

# ActivityLayout 活动布局

> **能力域**：辅助能力

`ActivityLayout` 是活动消息的通用折叠布局容器，负责渲染标题栏、折叠箭头和内容区域。它不关心活动内容类型本身，标题和正文均通过插槽传入，因此常被 `KnowledgeRagContent`、`ReferenceDocContent`、`FlowAgentContent` 等活动组件复用。

通常不需要业务侧直接使用；如果要新增一种活动消息内容，可以用它作为标题/内容外壳。

## 源码事实

- **源码位置**：`src/components/chat-content/activity-layout/activity-layout.vue`
- **能力说明**：活动消息的折叠布局容器，提供 `title` / `default` 插槽。

## 核心能力

- **标题栏点击折叠**：点击标题栏切换 `collapsed`，内容区通过 `v-show="!collapsed"` 显示或隐藏
- **双向绑定**：通过 `v-model:collapsed` 让父组件控制展开/收起状态，默认展开
- **标题插槽透传状态**：`title` 插槽会收到 `{ collapsed }`，可根据折叠状态调整标题内容
- **默认折叠箭头**：非 FlowAgent 活动自动在标题右侧显示折叠箭头
- **FlowAgent 特例**：`activityType === MessageContentType.FlowAgent` 时隐藏默认折叠箭头，由 FlowAgent 自己渲染标题交互

## 基础用法

```vue
<template>
  <ActivityLayout v-model:collapsed="collapsed">
    <template #title="{ collapsed }">
      <span class="ai-activity-message-title-icon">
        <DocumentIcon style="font-size: 12px" />
      </span>
      <span class="ai-activity-message-title-text">
        {{ collapsed ? '已折叠' : '引用 2 篇资料作为参考' }}
      </span>
    </template>

    <div style="padding: 0 14px;">
      活动内容
    </div>
  </ActivityLayout>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import ActivityLayout from '@blueking/chat-x/src/components/chat-content/activity-layout/activity-layout.vue';
  import { DocumentIcon } from '@blueking/chat-x/src/icons/content';

  const collapsed = ref(false);
</script>
```

**渲染效果**

## 折叠状态

`collapsed` 默认为 `false`。设置为 `true` 时只展示标题栏，正文内容保留在 DOM 中但通过 `v-show` 隐藏。

## FlowAgent 活动

传入 `activityType="flow_agent"` 时，`ActivityLayout` 不渲染右侧默认折叠箭头。该场景下标题栏通常由 `FlowAgentContent` 自己展示状态统计、加载图标和展开箭头。

```vue
<ActivityLayout
  v-model:collapsed="collapsed"
  :activity-type="MessageContentType.FlowAgent"
>
  <template #title>
    <span>执行情况: 成功 2 / 失败 1</span>
  </template>
  <div>FlowAgent 节点列表</div>
</ActivityLayout>
```

## 组件结构

```
.ai-activity-message
├── .ai-activity-message-title（点击切换 collapsed）
│   ├── title slot（slot props: { collapsed }）
│   └── CollapsedIcon（activityType !== flow_agent 时显示）
└── .ai-activity-message-content（v-show="!collapsed"）
    └── default slot
```

## API

### Props

| 属性名       | 类型                 | 必填 | 默认值 | 说明                                          |
| ------------ | -------------------- | ---- | ------ | --------------------------------------------- |
| activityType | `MessageContentType` | 否   | —      | 活动类型；为 `flow_agent` 时隐藏默认折叠箭头 |

### Models

| 名称      | 类型      | 默认值  | 说明             |
| --------- | --------- | ------- | ---------------- |
| collapsed | `boolean` | `false` | 活动内容是否折叠 |

### Emits

- 无显式 emits；`v-model:collapsed` 会产生 `update:collapsed`。

### Slots

| 插槽名  | 参数                    | 说明       |
| ------- | ----------------------- | ---------- |
| title   | `{ collapsed: boolean }` | 标题栏内容 |
| default | —                       | 活动正文   |

### Expose

- 无。

## 使用建议

- 适合作为活动消息内部布局外壳，不建议替代通用卡片、面板或页面 Section。
- 标题栏点击区域会整体触发折叠，标题插槽内如有按钮或链接，需要自行处理事件冒泡。
- `default` 内容使用 `v-show` 控制可见性，折叠时不会卸载内部组件。

## 关联组件

- [ActivityMessage](../message/activity-message.md) — 活动消息分发入口。
- [KnowledgeRagContent](../agent/knowledge-rag-content.md) — 知识召回活动。
- [ReferenceDocContent](../agent/reference-doc-content.md) — 引用文档活动。
- [FlowAgentContent](../agent/flow-agent-content.md) — FlowAgent 执行活动。
