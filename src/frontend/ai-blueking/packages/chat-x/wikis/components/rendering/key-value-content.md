---
name: KeyValueContent 键值内容
slug: key-value-content
kind: component
domain: rendering
description: 以键值列表展示结构化内容。
aiSummary: >
  以键值列表展示结构化内容。
  源码位置：src/components/chat-content/key-value-content/key-value-content.vue。
relatedComponents:
  - slug: user-message
    relation: 用户消息内展示结构化附加信息
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import KeyValueContent from '../../../src/components/chat-content/key-value-content/key-value-content.vue'

  const basicData = [
    { key: '名称', value: '蓝鲸智云' },
    { key: '版本', value: 'v3.0' },
    { key: '状态', value: '运行中' },
  ];

  const paramData = [
    { key: '模型', value: 'GPT-4' },
    { key: '温度', value: '0.7' },
    { key: '最大 Token', value: '2048' },
    { key: '频率惩罚', value: '0.5' },
  ];

  const longValueData = [
    { key: '路径', value: '/usr/local/bk-paas/apps/saas/api/v3/resource/query?env=prod&region=sz&cluster=default' },
    { key: '描述', value: '这是一条很长的描述文字，用于演示超出容器宽度时自动截断为省略号的效果' },
  ];
</script>

# KeyValueContent 键值对内容
## 源码事实

- **源码位置**：`src/components/chat-content/key-value-content/key-value-content.vue`
- **能力域**：内容渲染
- **能力说明**：以键值列表展示结构化内容。



> **能力域**：内容渲染

键值对列表展示基础组件，每行以 `key : value` 格式渲染一条数据，支持可选标题栏（带 `ThinkingIcon`）。

主要被 `UserMessage` 内部用于渲染结构化引用内容（`property.extra.cite.data`），通常不需要手动引入。

## 组件结构

```
div.ai-key-value-content（flex column，gap: 8px，font-size: 12px，color: #4d4f56）
├── [v-if="title"] div.ai-key-value-title（flex，gap: 4px，font-size: 12px，font-weight: 700，color: #3a84ff）
│     ├── ThinkingIcon（14×14px）
│     └── {{ title }}
└── div.ai-key-value-content（flex column，无 gap）   ← 与外层同名嵌套
      └── div.key-value-item × N（flex row，gap: 3px，min-height: 20px）
            ├── div.item-key   → {{ item.key }}（flex: 0 0 auto，font-weight: bold，color: #333）
            ├── "："            → 硬编码文本节点，冒号不属于任何 div
            └── div.item-value → {{ item.value }}（overflow hidden，ellipsis，`word-break: break-all` 允许多行换行）
```

> **注意**：内层也是 `.ai-key-value-content` 类（与外层同名），仅用于布局，无额外样式差异。  
> **注意**：`v-for` 使用 `item.key` 作为 `:key`，`content` 中的 `key` 字段必须唯一，否则触发 Vue 重复 key 警告。  
> **注意**：`item.value` 在单行方向仍可能因 `text-overflow: ellipsis` 显示省略，但配合 `word-break: break-all` 长串会优先换行展示，**无 tooltip**（与 `DescPanel` 不同）。

## 基础用法

```vue
<template>
  <KeyValueContent :content="data" />
</template>

<script setup lang="ts">
  import { KeyValueContent } from '@blueking/chat-x';

  const data = [
    { key: '名称', value: '蓝鲸智云' },
    { key: '版本', value: 'v3.0' },
    { key: '状态', value: '运行中' },
  ];
</script>
```

<div class="demo">
  <KeyValueContent :content="basicData" />
</div>

## 带标题

传入 `title` 时，顶部显示 `ThinkingIcon` + 标题文本（蓝色加粗）：

```vue
<template>
  <KeyValueContent
    title="模型参数"
    :content="[
      { key: '模型', value: 'GPT-4' },
      { key: '温度', value: '0.7' },
      { key: '最大 Token', value: '2048' },
      { key: '频率惩罚', value: '0.5' },
    ]"
  />
</template>
```

<div class="demo">
  <KeyValueContent title="模型参数" :content="paramData" />
</div>

## 超长 value 换行

`.item-value` 使用 `word-break: break-all`，长 URL 或长文本会在容器内换行；仍保留 `overflow: hidden` 与 `text-overflow: ellipsis` 以约束极端情况，**悬停无 tooltip**：

<div class="demo">
  <KeyValueContent title="请求信息" :content="longValueData" />
</div>

## API

### Props

| 属性名  | 类型                                | 必填 | 说明                                                              |
| ------- | ----------------------------------- | ---- | ----------------------------------------------------------------- |
| content | `{ key: string; value: string; }[]` | ✓    | 键值对数组；`key` 同时作为 `v-for` 的 `:key`，需保证唯一          |
| title   | `string`                            | —    | 标题文本；传入后在列表上方渲染 `ThinkingIcon + title`（蓝色加粗） |

## 使用场景

`KeyValueContent` 由 `UserMessage` 内部使用，渲染结构化引用内容（`property.extra.cite` 为对象类型时）：

```typescript
// UserMessage 内部逻辑（简化）
const citeTitle = computed(() => {
  const cite = props.property?.extra?.cite;
  return cite && typeof cite !== 'string' ? cite.title : undefined;
});

const citeContent = computed(() => {
  const cite = props.property?.extra?.cite;
  return cite && typeof cite !== 'string' ? cite.data : cite;
});
// citeContent 为数组时 → <KeyValueContent :content="citeContent" :title="citeTitle" />
// citeContent 为字符串时 → <CiteContent :content="citeContent" />
```

如需在用户消息中展示结构化引用，将 `property.extra.cite` 设置为以下格式即可：

```typescript
const message = {
  // ...
  property: {
    extra: {
      cite: {
        title: '引用标题',
        data: [{ key: '字段名', value: '字段值' }],
      },
    },
  },
};
```

## 关联组件

- [UserMessage](/components/message/user-message) — 键值气泡展示
