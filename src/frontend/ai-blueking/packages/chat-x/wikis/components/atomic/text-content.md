---
name: TextContent 文本内容
slug: text-content
category: atomic
description: 纯文本气泡组件，使用 Vue 文本插值渲染 `content`，天然防 XSS。
aiSummary: >
  TextContent 用 Vue 文本插值渲染纯文本气泡，不解析 HTML，适合简单提示与用户/助手纯文案。
  需要 Markdown、代码块或公式时应改用 MarkdownContent 等富文本组件。
relatedComponents:
  - slug: markdown-content
    relation: 需要富文本时的替代方案
  - slug: user-message
    relation: 用户消息中纯文本内容展示
sinceVersion: 1.0.0
domain: helper
---

<script lang="ts" setup>
  import TextContent from '../../../src/components/chat-content/text-content/text-content.vue';
</script>

# TextContent 文本内容

> **层级**：原子组件 · **功能域**：辅助组件

纯文本气泡组件，使用 Vue 文本插值渲染 `content`，天然防 XSS。

## 组件结构

```
div.text-content
  display: flex; width: fit-content
  padding: 8px 12px; border-radius: 4px
  background-color: #e1ecff（浅蓝色气泡）
  word-break: break-all（无空格长文本按字符换行）
  │
  └── {{ content }}（文本插值，HTML 标签不被解析）
```

> **换行说明**：组件无 `white-space: pre-wrap`，`\n` 不会渲染为视觉换行。如需保留换行，需在外层添加 `white-space: pre-wrap` 样式。

## 基础用法

```vue
<template>
  <TextContent content="这是一条纯文本消息" />
</template>

<script setup lang="ts">
  import { TextContent } from '@blueking/chat-x';
</script>
```

<div class="demo">
  <TextContent content="这是一条纯文本消息" />
</div>

## 长文本自动换行

`word-break: break-all` 确保无空格的长字符串（如 URL、哈希值）也能在容器内正常换行：

<div class="demo" style="max-width: 300px;">
  <TextContent content="这是一段很长的文字内容，会在容器边界处自动换行显示，不会撑破父容器的宽度。" />
</div>

## XSS 安全

`content` 使用 `{{ }}` 文本插值渲染，HTML 标签会被转义，不会执行脚本：

<div class="demo">
  <TextContent :content="`&lt;script&gt;alert('xss')&lt;/script&gt; 这段脚本不会执行`" />
</div>

## API

### Props

| 属性名  | 类型     | 必填 | 说明                                           |
| ------- | -------- | ---- | ---------------------------------------------- |
| content | `string` | 是   | 要显示的文本内容；空字符串时气泡仍渲染，无内容 |

## 使用场景

`TextContent` 为极简的文本气泡，适用于**不需要 Markdown 渲染**的纯文本展示场景。如需富文本，使用 `MarkdownContent` 组件。

| 场景                              | 推荐组件          |
| --------------------------------- | ----------------- |
| 纯文本气泡（用户消息、简单提示）  | `TextContent`     |
| 含 Markdown / 代码块 / 公式的内容 | `MarkdownContent` |
| 工具调用结果描述                  | `DescPanel`       |

## 关联组件

- [MarkdownContent](./markdown-content.md) — 富文本替代
- [UserMessage](../molecular/user-message.md) — 用户消息气泡
