---
name: ContentRender 内容渲染器
slug: content-render
kind: component
domain: rendering
description: 按 MessageContentType 分发 Markdown、文本、引用、键值、图片等内容。
aiSummary: >
  按 MessageContentType 分发 Markdown、文本、引用、键值、图片等内容。
  源码位置：src/components/chat-content/content-render/content-render.vue。
relatedComponents:
  - slug: markdown-content
    relation: 文本类 Markdown 正文的默认渲染实现
  - slug: reference-content
    relation: 引用文档数组类型的列表渲染
  - slug: assistant-message
    relation: AI 回复中默认通过本组件渲染正文
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import ContentRenderComp from '../../../src/components/chat-content/content-render/content-render.vue'

  const markdownDemo = `## 代码示例

\`\`\`javascript
const greeting = 'Hello, World!';
console.log(greeting);
\`\`\`

## 列表与任务

- 普通列表项
- [x] 已完成任务
- [ ] 待完成任务

## 表格

| 名称  | 描述   |
|-------|--------|
| Vue   | 前端框架 |
| React | 前端库  |`;

  const markdownExtDemo = `**加粗** 和 *斜体*

下划线：++新增内容++

标注：==高亮文字==

上标：E = mc^2^，下标：H~2~O

脚注：这里有一个脚注[^1]

[^1]: 这是脚注内容`;

  const latexDemo = `行内公式：$E = mc^2$

块级公式：

$$
\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}
$$`;

  const mermaidDemo = `\`\`\`mermaid
graph TD
    A[开始] --> B{判断}
    B -->|是| C[处理]
    B -->|否| D[结束]
    C --> D
\`\`\``;

  const refDocs = [
    { name: 'Vue 3 官方文档', url: 'https://vuejs.org', originFile: 'vue3-guide.md' },
    { name: 'Vite 官方文档', url: 'https://vitejs.dev', originFile: 'vite-guide.md' },
    { name: 'TypeScript 手册', url: 'https://www.typescriptlang.org', originFile: '' },
  ];

  const refDocsNoOrigin = [
    { name: 'Vue 3 官方文档', url: 'https://vuejs.org', originFile: '' },
    { name: 'Vite 官方文档', url: 'https://vitejs.dev', originFile: '' },
  ];
</script>

# ContentRender 内容渲染器
## 源码事实

- **源码位置**：`src/components/chat-content/content-render/content-render.vue`
- **能力域**：内容渲染
- **能力说明**：按 MessageContentType 分发 Markdown、文本、引用、键值、图片等内容。



> **能力域**：内容渲染

消息内容渲染分发组件，根据 `content` 的 JavaScript 类型自动选择渲染方式：字符串 → `MarkdownContent`（Markdown 渲染），数组 → `ReferenceContent`（引用列表）。

## 渲染管线

```
ContentRender
├── typeof content === 'string'  →  MarkdownContent（Markdown 渲染）
│   └── status === 'error'       →  CommonErrorContent（红色错误图标 + 文本）
├── Array.isArray(content)       →  ReferenceContent（引用文档列表）
└── 其他                         →  undefined（不渲染，可通过 slot 自定义）
```

> **注意**：渲染类型由 `content` 的 JavaScript 类型决定（字符串 vs 数组），`type` prop 仅当传入 `MessageContentType.Text` 时才强制走 `MarkdownContent`，通常不需要显式传递。

## 基础用法（Markdown 文本）

字符串内容自动渲染为 Markdown：

```vue
<template>
  <ContentRender
    :content="content"
    :status="status"
  />
</template>

<script setup lang="ts">
  import { ContentRender, MessageStatus } from '@blueking/chat-x';

  const content = '这是一段 **Markdown** 内容，支持 `代码`、**加粗**、*斜体* 等语法。';
  const status = MessageStatus.Complete;
</script>
```

**渲染效果**

<div class="demo">
  <ContentRenderComp
    content="这是一段 **Markdown** 内容，支持 `代码`、**加粗**、*斜体* 等语法。"
    status="complete"
  />
</div>

## Markdown 语法支持

`MarkdownContent` 内置了完整的 Markdown 解析能力，使用 `markdown-it` + 多个插件：

### 常用语法（代码、列表、表格）

<div class="demo">
  <ContentRenderComp :content="markdownDemo" status="complete" />
</div>

### 扩展语法

| 语法                  | 效果           | 插件                      |
| --------------------- | -------------- | ------------------------- |
| `++文字++`            | 下划线（新增） | markdown-it-ins           |
| `==文字==`            | 高亮标注       | markdown-it-mark          |
| `^上标^`              | 上标           | markdown-it-sup           |
| `~下标~`              | 下标           | markdown-it-sub           |
| `[^1]` / `[^1]: 内容` | 脚注           | markdown-it-footnote      |
| `- [x] 任务`          | 任务列表       | markdown-it-task-checkbox |

<div class="demo">
  <ContentRenderComp :content="markdownExtDemo" status="complete" />
</div>

### LaTeX 数学公式

行内公式 `$...$` 和块级公式 `$$...$$`，由 `katex` 渲染：

```vue
<ContentRender content="行内公式：$E = mc^2$" status="complete" />
```

<div class="demo">
  <ContentRenderComp :content="latexDemo" status="complete" />
</div>

### Mermaid 图表

代码块语言标识为 `mermaid` 时，由 `MermaidContent` 专门渲染：

<div class="demo">
  <ContentRenderComp :content="mermaidDemo" status="complete" />
</div>

## 消息状态

`status` 只传递给 `MarkdownContent`，对 `ReferenceContent` 无效。

| `status`    | 渲染行为                                                          |
| ----------- | ----------------------------------------------------------------- |
| `complete`  | 正常渲染完整 Markdown                                             |
| `streaming` | 自动补全未闭合的 Markdown 语法（代码块、列表等），节流解析（5ms） |
| `pending`   | 同 `complete`（按当前内容渲染）                                   |
| `error`     | 渲染为 `CommonErrorContent`（红色错误图标 + `content` 文本）      |
| `stop`      | 同 `complete`                                                     |

**错误状态示例**

<div class="demo">
  <ContentRenderComp
    content="抱歉，请求处理失败，服务暂时不可用，请稍后重试。"
    status="error"
  />
</div>

## 引用文档列表

`content` 传入 `ReferenceDocumentContent[]` 数组时，自动渲染为 `ReferenceContent`（引用文档列表）：

```vue
<template>
  <ContentRender :content="referenceContent" />
</template>

<script setup lang="ts">
  import { ContentRender, type ReferenceDocumentContent } from '@blueking/chat-x';

  const referenceContent: ReferenceDocumentContent[] = [
    {
      name: 'Vue 3 官方文档',
      url: 'https://vuejs.org',
      originFile: 'vue3-guide.md', // 有 originFile 时显示预览和跳转图标
    },
    {
      name: 'TypeScript 手册',
      url: 'https://www.typescriptlang.org',
      originFile: '', // 无 originFile 时不显示操作图标
    },
  ];
</script>
```

**渲染效果**（悬停条目查看图标，有 `originFile` 的条目显示预览和跳转图标）

<div class="demo">
  <ContentRenderComp :content="refDocs" />
</div>

### ReferenceContent 图标显示规则

| 条件                           | 显示图标                                     |
| ------------------------------ | -------------------------------------------- |
| 始终                           | 文档图标（红色）                             |
| `url` 和 `originFile` 均不为空 | 预览图标（悬停可见）                         |
| `url` 和 `originFile` 均不为空 | 跳转图标（悬停可见，打开 `originFile` 链接） |

无 `originFile` 时只显示文档图标（点击文档名跳转 `url`）：

<div class="demo">
  <ContentRenderComp :content="refDocsNoOrigin" />
</div>

## 自定义渲染（默认插槽）

默认插槽接收 `{ content }` 参数（原始 `content` prop 值），替换整个内容渲染：

```vue
<template>
  <ContentRender
    :content="content"
    :status="status"
  >
    <template #default="{ content }">
      <div class="custom-content">
        <h3>自定义渲染</h3>
        <pre>{{ JSON.stringify(content, null, 2) }}</pre>
      </div>
    </template>
  </ContentRender>
</template>

<script setup lang="ts">
  import { ContentRender } from '@blueking/chat-x';

  const content = '自定义内容，由 slot 接管渲染。';
  const status = 'complete';
</script>
```

**渲染效果**

<div class="demo">
  <ContentRenderComp
    content="自定义内容，由 slot 接管渲染。ContentRender 仅负责传递原始数据。"
    status="complete"
  >
    <template #default="{ content }">
      <div style="padding: 12px; background: #f0f9ff; border-left: 3px solid #3a84ff; border-radius: 4px; font-size: 12px;">
        🎨 {{ content }}
      </div>
    </template>
  </ContentRenderComp>
</div>

## API

### Props

| 属性名  | 类型                                   | 必填 | 说明                                                                                      |
| ------- | -------------------------------------- | ---- | ----------------------------------------------------------------------------------------- |
| content | `string \| ReferenceDocumentContent[]` | ✅   | 内容数据，字符串走 Markdown 渲染，数组走引用文档列表渲染                                  |
| status  | `MessageStatus`                        | -    | 消息状态，只影响 Markdown 渲染（`error` 时渲染错误样式，`streaming` 时补全语法）          |
| type    | `ContentType`                          | -    | 内容类型提示，传入 `MessageContentType.Text` 可强制走 MarkdownContent；通常不需要显式传递 |

### Slots

| 插槽名     | 参数                                   | 说明                                                                          |
| ---------- | -------------------------------------- | ----------------------------------------------------------------------------- |
| codeHeader | `{ language: string; token: Token[] }` | 代码块头部自定义操作区域，透传给 MarkdownContent → CodeContent 的 header 插槽 |
| default    | `{ content: ContentMap[T] }`           | 自定义渲染，接收原始 content prop 值，替换全部默认逻辑                        |

## 流式渲染机制

`streaming` 状态下，`MarkdownContent` 有以下优化：

1. **语法自动补全**：`completeMarkdownSyntax` 在解析前补全未闭合的代码块、列表等，避免渲染异常
2. **节流解析**：`parseMarkdownContent` 节流 5ms（leading + trailing），大幅降低流式输入时的解析开销
3. **不完整状态保护**：当正在输入 LaTeX 命令（如 `$\fra...`）时保持之前的渲染结果，避免闪烁
4. **CSS contain 性能隔离**：`.ai-markdown-content` 使用 `contain: layout style`，`.ai-markdown-body` 使用 `contain: content`，减少重排影响范围
5. **自动滚动**：每个 token 挂载后触发 `toScrollBottom()`（节流 100ms），与 `MessageContainer` 配合实现流式自动滚动

## 类型定义

```typescript
import { MessageContentType, MessageStatus } from '@blueking/chat-x';

// 引用文档内容
type ReferenceDocumentContent = {
  name: string; // 显示名称（为空时该条目被过滤，不渲染）
  url: string; // 文档访问地址（点击文档名跳转）
  originFile: string; // 原始文件地址（非空时显示预览和跳转图标）
};

// 内容类型（ContentType = keyof ContentMap）
enum MessageContentType {
  Text = 'text', // 字符串，Markdown 渲染
  ReferenceDocument = 'reference_document', // ReferenceDocumentContent[]，引用列表
  Binary = 'binary',
  Function = 'function',
  KeyValue = 'key_value',
  KnowledgeRag = 'knowledge_rag',
  Other = 'other',
}
```

> `MessageStatus` 完整取值见 [常量枚举](../../types/constants)；本组件主要关心 `error`（错误内容）与流式相关状态。

## 使用场景

- **AI 文本回复渲染**：`AssistantMessage` 内部用 `ContentRender` 渲染 AI 回复内容，`status` 配合流式响应
- **知识库引用展示**：`ActivityMessage` 内部用 `ContentRender` 渲染引用文档列表
- **代码展示**：Markdown 代码块由 `CodeContent` 自动高亮（Atom One Dark 主题，支持 180+ 语言）
- **数学公式**：行内 `$...$` 和块级 `$$...$$`，由 KaTeX 渲染
- **流程图**：Mermaid 代码块自动渲染为 SVG 图表
- **自定义渲染**：通过 slot 接管渲染，实现表格、图表等自定义内容展示

## 关联组件

- [MarkdownContent](/components/rendering/markdown-content) — 字符串 Markdown 正文
- [ReferenceContent](/components/rendering/reference-content) — 引用文档数组
- [AssistantMessage](/components/message/assistant-message) — assistant 消息中默认使用
