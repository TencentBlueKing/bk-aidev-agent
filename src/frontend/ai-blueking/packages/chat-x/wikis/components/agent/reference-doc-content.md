---
name: ReferenceDocContent 引用文档活动
slug: reference-doc-content
kind: component
domain: agent
description: 渲染引用文档类活动内容，复用 ActivityLayout 与 ReferenceContent。
aiSummary: >
  渲染引用文档类活动内容，复用 ActivityLayout 与 ReferenceContent。
  源码位置：src/components/chat-content/reference-doc-content/reference-doc-content.vue。
relatedComponents:
  - slug: activity-message
    relation: 非 knowledge_rag / flow_agent 活动默认可分发为引用文档活动
  - slug: activity-layout
    relation: 提供可折叠的活动容器外壳
  - slug: reference-content
    relation: 渲染引用文档列表
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import ReferenceDocContentComp from '../../../src/components/chat-content/reference-doc-content/reference-doc-content.vue';

  const docs = [
    { name: '蓝鲸 Agent 接入指南', url: 'https://example.com/agent', originFile: 'https://example.com/docs/agent' },
    { name: '主机巡检操作手册', url: 'https://example.com/host-check', originFile: 'https://example.com/docs/host-check' },
    { name: '告警策略最佳实践', url: 'https://example.com/alarm-policy', originFile: '' },
  ];

  const emptyDocs = [];
  const collapsed = ref(false);
  const collapsedState = ref(true);
</script>

# ReferenceDocContent 引用文档活动

> **能力域**：Agent 能力

`ReferenceDocContent` 用于渲染“引用 N 篇资料作为参考”这类活动消息。组件基于 `ActivityLayout` 提供折叠外壳，并将文档数组交给 `ReferenceContent` 展示。

通常不需要直接使用，`ActivityMessage` 会在引用文档活动场景中分发到本组件。

## 源码事实

- **源码位置**：`src/components/chat-content/reference-doc-content/reference-doc-content.vue`
- **能力说明**：渲染引用文档类活动内容，复用 ActivityLayout 与 ReferenceContent。

## 核心能力

- **数量标题**：根据 `content.length` 生成标题，中文为“引用 N 篇资料作为参考”
- **文档图标**：标题区域固定展示文档图标，不随消息状态变化
- **可折叠内容**：通过 `v-model:collapsed` 控制引用列表展开/收起，默认展开
- **引用列表复用**：文档展示、hover 操作图标、链接打开规则均由 `ReferenceContent` 负责

## 基础用法

```vue
<template>
  <ReferenceDocContent
    v-model:collapsed="collapsed"
    :content="docs"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import ReferenceDocContent from '@blueking/chat-x/src/components/chat-content/reference-doc-content/reference-doc-content.vue';
  import type { ReferenceDocumentContent } from '@blueking/chat-x';

  const collapsed = ref(false);

  const docs: ReferenceDocumentContent[] = [
    { name: '蓝鲸 Agent 接入指南', url: 'https://example.com/agent', originFile: 'https://example.com/docs/agent' },
    { name: '主机巡检操作手册', url: 'https://example.com/host-check', originFile: 'https://example.com/docs/host-check' },
  ];
</script>
```

**渲染效果**

<div class="demo">
  <ReferenceDocContentComp
    v-model:collapsed="collapsed"
    :content="docs"
  />
</div>

## 空引用

当 `content` 为空或未传入时，标题数量显示为 `0`，引用列表为空。

<div class="demo">
  <ReferenceDocContentComp :content="emptyDocs" />
</div>

## 折叠状态

<div class="demo">
  <ReferenceDocContentComp
    v-model:collapsed="collapsedState"
    :content="docs"
  />
</div>

## API

### Props

| 属性名     | 类型                         | 必填 | 默认值 | 说明                                   |
| ---------- | ---------------------------- | ---- | ------ | -------------------------------------- |
| content    | `ReferenceDocumentContent[]` | 否   | —      | 引用文档列表                           |
| messageUid | `string`                     | 否   | —      | 所属消息唯一标识，当前组件暂未直接使用 |

### Models

| 名称      | 类型      | 默认值  | 说明             |
| --------- | --------- | ------- | ---------------- |
| collapsed | `boolean` | `false` | 活动内容是否折叠 |

### Emits

- 无显式 emits；`v-model:collapsed` 会产生 `update:collapsed`。

### Slots

- 无。

### Expose

- 无。

## 类型定义

```typescript
export type ReferenceDocumentContent = {
  name: string;       // 文档标题
  originFile: string; // 原始文件链接，存在时 ReferenceContent 显示跳转操作
  url: string;        // 预览链接或标题点击链接
};
```

## 使用建议

- 只负责引用文档活动外壳；如果只需要纯引用列表，请直接使用 [ReferenceContent](../rendering/reference-content.md)。
- 文档条目的过滤与操作图标规则以 `ReferenceContent` 为准，`ReferenceDocContent` 不重复处理。

## 关联组件

- [ActivityMessage](../message/activity-message.md) — 活动消息分发入口。
- [ActivityLayout](../helper/activity-layout.md) — 折叠活动外壳。
- [ReferenceContent](../rendering/reference-content.md) — 引用来源列表。
