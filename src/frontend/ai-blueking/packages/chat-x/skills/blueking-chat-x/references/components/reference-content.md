# ReferenceContent 引用来源

> 能力域：内容渲染 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

渲染引用文档/来源列表。 源码位置：src/components/chat-content/reference-content/reference-content.vue。

**关联**：content-render（ReferenceDocument 类型内容路由到本组件）、activity-message（知识库等活动场景内嵌引用列表）

---

# ReferenceContent 引用文档内容
## 源码事实

- **源码位置**：`src/components/chat-content/reference-content/reference-content.vue`
- **能力域**：内容渲染
- **能力说明**：渲染引用文档/来源列表。

> **能力域**：内容渲染

引用文档列表渲染基础组件，用于展示 AI 回复中引用的参考文档，每项包含文档图标、标题、预览与跳转操作。

主要由 `ActivityMessage`（知识库问答场景）和 `ContentRender`（`reference_document` 类型内容）内部使用。

## 组件结构

```
<template>（无根元素，Fragment 模式）
  v-for item in links（过滤 name 为空 → 映射为 { title, url, originFileUrl }）
    │
    div.ai-reference-item（flex，height: 28px，padding: 0 12px，color: #3a84ff）
      ├── DocLinkIcon（color="#D66F6B"，.ai-doc-link-icon，始终可见）
      ├── span.ai-reference-item-title（flex: 1，ellipsis，font-size: 12px）
      │     @click → url && gotoLink(url, event)
      │     （XSS 安全：{{ item.title }} 文本插值）
      ├── [v-if url && originFileUrl] PreviewIcon（.ai-common-icon）
      │     v-tippy: "预览内容"
      │     @click → gotoLink(url, event)
      │     默认 display: none，hover 父容器后 display: flex
      └── [v-if url && originFileUrl] TargetIcon（.ai-common-icon）
            v-tippy: "跳转详情"
            @click → gotoLink(originFileUrl, event)
            默认 display: none，hover 父容器后 display: flex

gotoLink(url, event):
  event.stopPropagation() + event.preventDefault()
  window.open(url, '_blank', 'noopener,noreferrer')
```

> **`v-for` key**：使用 `item.title`（即 `name`）作为 `:key`，同一组 `content` 中 `name` 须唯一，否则触发 Vue 重复 key 警告。

## 图标可见性规则

| 图标                      | 始终显示 | 显示条件（数据层）                | 显示条件（交互层） |
| ------------------------- | -------- | --------------------------------- | ------------------ |
| `DocLinkIcon`（红色书签） | ✓        | 无条件                            | 无条件             |
| `PreviewIcon`（预览）     | —        | `url` 与 `originFileUrl` 均为真值 | 仅在 hover 时出现  |
| `TargetIcon`（跳转）      | —        | `url` 与 `originFileUrl` 均为真值 | 仅在 hover 时出现  |

即：只有 `url` 没有 `originFileUrl`（或反之），两个操作图标均不渲染。

## 基础用法

```vue
<template>
  <ReferenceContent :content="references" />
</template>

<script setup lang="ts">
  import { ReferenceContent } from '@blueking/chat-x';
  import type { ReferenceDocumentContent } from '@blueking/chat-x';

  const references: ReferenceDocumentContent[] = [
    { name: '蓝鲸 PaaS 平台文档', url: 'https://bk.tencent.com', originFile: '' },
    { name: '组件库使用指南', url: 'https://bk.tencent.com/docs', originFile: '' },
  ];
</script>
```

## 含预览与跳转（url + originFile）

同时提供 `url` 和 `originFile` 时，hover 后出现预览图标和跳转图标：

## 混合场景：过滤与图标差异

`name` 为空的项被过滤不渲染；`originFile` 为空时不显示 `PreviewIcon` / `TargetIcon`：

```typescript
const refs = [
  { name: '有预览和跳转', url: 'https://…/preview', originFile: 'https://…/origin' }, // 两图标
  { name: '仅有 url', url: 'https://…/only', originFile: '' }, // 无图标
  { name: '', url: 'https://…/filtered', originFile: '' }, // 被过滤
];
// 实际渲染 2 条，第 3 条因 name='' 被过滤
```

## API

### Props

| 属性名  | 类型                         | 必填 | 说明                                          |
| ------- | ---------------------------- | ---- | --------------------------------------------- |
| content | `ReferenceDocumentContent[]` | ✓    | 引用文档列表；`name` 为空的项会被过滤，不渲染 |

### 类型定义

```typescript
export type ReferenceDocumentContent = {
  name: string; // 文档标题（用作列表展示文本，也作为 v-for :key）
  url: string; // 预览链接：标题点击、PreviewIcon 点击时打开
  originFile: string; // 原始文件链接：TargetIcon 点击时打开；为空则不渲染两个操作图标
};
```

## 使用场景

`ReferenceContent` 在两处被内部使用：

**1. `ActivityMessage`（知识库问答）**

```typescript
// content 为 ReferenceDocumentContent[] 数组时直接传入
<ReferenceContent :content="Array.isArray(content) ? content : content?.referenceDocument || []" />
```

**2. `ContentRender`（content 类型路由）**

```typescript
// type === MessageContentType.ReferenceDocument 且 content 为数组时
h(ReferenceContent, { content: props.content as ReferenceDocumentContent[] });
```

## 关联组件

- [ContentRender](/components/rendering/content-render) — 内容类型分发
- [ActivityMessage](/components/message/activity-message) — 活动消息内引用
