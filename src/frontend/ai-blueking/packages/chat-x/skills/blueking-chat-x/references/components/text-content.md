# TextContent 文本内容

> 能力域：内容渲染 ｜ 导入：`import { TextContent } from '@blueking/chat-x'` ｜ since 1.0.0

渲染纯文本内容。 源码位置：src/components/chat-content/text-content/text-content.vue。

**关联**：markdown-content（需要富文本时的替代方案）、user-message（用户消息中纯文本内容展示）

---

# TextContent 文本内容
## 源码事实

- **源码位置**：`src/components/chat-content/text-content/text-content.vue`
- **能力域**：内容渲染
- **能力说明**：渲染纯文本内容。

> **能力域**：内容渲染

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

## 长文本自动换行

`word-break: break-all` 确保无空格的长字符串（如 URL、哈希值）也能在容器内正常换行：

## XSS 安全

`content` 使用 `{{ }}` 文本插值渲染，HTML 标签会被转义，不会执行脚本：

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

- [MarkdownContent](/components/rendering/markdown-content) — 富文本替代
- [UserMessage](/components/message/user-message) — 用户消息气泡
