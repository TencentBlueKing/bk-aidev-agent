# CommonErrorContent 错误内容

> 能力域：内容渲染 ｜ 导入：`import { CommonErrorContent } from '@blueking/chat-x'` ｜ since 1.0.0

展示统一错误提示内容。 源码位置：src/components/chat-content/common-error-content/common-error-content.vue。

**关联**：markdown-content（Markdown 渲染错误态展示）、reasoning-message（推理消息错误态展示）

---

# CommonErrorContent 通用错误内容
## 源码事实

- **源码位置**：`src/components/chat-content/common-error-content/common-error-content.vue`
- **能力域**：内容渲染
- **能力说明**：展示统一错误提示内容。

> **能力域**：内容渲染

错误状态消息渲染基础组件。红色 `ErrorIcon`（14×14px，绝对定位）+ 文本区域，`display: flex` 水平排列。

通常由上层组件在 `status === 'error'` 时自动渲染，无需手动使用。

## 组件结构

```
.ai-error-content（position: relative，display: flex，align-items: center）
├── ErrorIcon（position: absolute，top: 2px，left: 0，flex: 0 0 14px，14×14px，color: #ea3636）
└── .ai-error-content-text（flex: 1，margin-left: 20px，font-size: 12px，line-height: 20px，color: #4d4f56）
      └── {{ content }}（Vue 文本插值，XSS 安全；content 为 undefined 时渲染空文本）
```

## 基础用法

```vue
<template>
  <CommonErrorContent content="请求失败，请稍后重试" />
</template>

<script setup lang="ts">
  import { CommonErrorContent } from '@blueking/chat-x';
</script>
```

## 典型错误场景

## 不传 content

`content` 为可选，缺省时只渲染 `ErrorIcon`：

## 使用场景

组件库内部有两处自动使用：

| 使用方             | 触发条件             | 传入内容                                      |
| ------------------ | -------------------- | --------------------------------------------- |
| `MarkdownContent`  | `status === 'error'` | `content`（字符串）                           |
| `ReasoningMessage` | `status === 'error'` | `content?.join('\n') \|\| ''`（数组转字符串） |

即 `AssistantMessage` / `ReasoningMessage` 在错误状态时，内容区域会自动替换为此组件，无需手动引入。

## API

### Props

| 属性名  | 类型     | 必填 | 说明                                                            |
| ------- | -------- | ---- | --------------------------------------------------------------- |
| content | `string` | —    | 错误提示文本；使用 Vue 文本插值渲染，XSS 安全；缺省时仅显示图标 |

## 关联组件

- [MarkdownContent](/components/rendering/markdown-content) — Markdown 错误态
- [ReasoningMessage](/components/message/reasoning-message) — 推理错误态
