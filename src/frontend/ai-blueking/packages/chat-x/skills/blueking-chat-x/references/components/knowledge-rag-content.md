# KnowledgeRagContent 知识召回内容

> 能力域：Agent 能力 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

渲染知识召回活动，包含加载态、Markdown 内容与引用来源。 源码位置：src/components/chat-content/knowledge-rag-content/knowledge-rag-content.vue。

**关联**：activity-message（activityType 为 knowledge_rag 时分发到本组件）、activity-layout（提供可折叠的活动容器外壳）、markdown-content（渲染知识召回摘要正文）、reference-content（渲染召回引用来源列表）

---

# KnowledgeRagContent 知识召回内容

> **能力域**：Agent 能力

`KnowledgeRagContent` 用于渲染知识召回活动内容，包含活动标题、加载态、Markdown 摘要和引用来源列表。它是 `ActivityMessage` 在 `activityType === 'knowledge_rag'` 时使用的具体内容组件。

通常不需要直接使用，`MessageRender -> ActivityMessage` 会根据消息类型自动分发到本组件。

## 源码事实

- **源码位置**：`src/components/chat-content/knowledge-rag-content/knowledge-rag-content.vue`
- **能力说明**：渲染知识召回活动，包含加载态、Markdown 内容与引用来源。

## 核心能力

- **活动外壳**：基于 `ActivityLayout` 渲染可折叠活动区域，默认展开
- **状态标题**：`status` 为 `pending` / `streaming` 时标题显示“检索中”并展示 Loading；其他状态显示“检索完成”
- **Markdown 摘要**：使用 `MarkdownContent` 渲染 `content.content`
- **引用来源**：使用 `ReferenceContent` 渲染 `content.referenceDocument`
- **空值兜底**：正文缺失时传入空字符串，引用缺失时传入空数组

## 基础用法

```vue
<template>
  <KnowledgeRagContent
    v-model:collapsed="collapsed"
    :content="content"
    status="complete"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import KnowledgeRagContent from '@blueking/chat-x/src/components/chat-content/knowledge-rag-content/knowledge-rag-content.vue';
  import type { KnowledgeRagMessageContent } from '@blueking/chat-x';

  const collapsed = ref(false);

  const content: KnowledgeRagMessageContent = {
    content: '根据知识库检索，**蓝鲸智云** 常见 Agent 接入流程包括...',
    referenceDocument: [
      { name: 'Agent 接入指南', url: 'https://example.com/agent-guide', originFile: 'https://example.com/docs/agent-guide' },
    ],
  };
</script>
```

**渲染效果**

## 检索中状态

当消息状态为 `pending` 或 `streaming` 时，标题区域显示 Loading，标题文案为“检索中”。

## 折叠状态

`collapsed` 通过 `v-model:collapsed` 与 `ActivityLayout` 双向绑定，适合由父级活动消息统一控制展开/收起。

## API

### Props

| 属性名     | 类型                         | 必填 | 默认值 | 说明                                     |
| ---------- | ---------------------------- | ---- | ------ | ---------------------------------------- |
| content    | `KnowledgeRagMessageContent` | 否   | —      | 知识召回摘要与引用来源                   |
| messageUid | `string`                     | 否   | —      | 所属消息唯一标识，当前组件暂未直接使用   |
| status     | `MessageStatus`              | 否   | —      | 消息状态，影响标题文案与 Loading 显示    |

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
export type KnowledgeRagMessageContent = {
  content: string;
  referenceDocument: ReferenceDocumentContent[];
};

export type ReferenceDocumentContent = {
  name: string;
  originFile: string;
  url: string;
};
```

## 使用建议

- 业务接入时优先通过 [ActivityMessage](../message/activity-message.md) 或完整消息链路使用，避免重复判断 `activityType`。
- `referenceDocument` 为空时组件仍会渲染正文区域，引用列表由 `ReferenceContent` 处理空数组。

## 关联组件

- [ActivityMessage](../message/activity-message.md) — 活动消息分发入口。
- [ActivityLayout](../helper/activity-layout.md) — 折叠活动外壳。
- [MarkdownContent](../rendering/markdown-content.md) — Markdown 摘要渲染。
- [ReferenceContent](../rendering/reference-content.md) — 引用来源列表。
