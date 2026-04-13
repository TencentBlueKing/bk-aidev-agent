---
name: MarkdownContent Markdown 内容渲染
slug: markdown-content
category: atomic
description: >-
  AI 消息内容渲染的核心原子组件，集成代码高亮、LaTeX 公式、Mermaid 图表等能力，内置流式渲染优化（5ms throttle + 语法补全 +
  防闪烁）。
aiSummary: >
  MarkdownContent 将 Markdown 字符串解析为 token 并渲染，集成代码块、公式、Mermaid 等子渲染器。
  核心 props 为 content 与 status；内置流式节流、语法补全与 DOMPurify 安全策略。
  通常由 ContentRender、AssistantMessage 等间接使用，无需业务直接挂载。
relatedComponents:
  - slug: code-content
    relation: fence 代码块语法高亮与复制
  - slug: latex-content
    relation: 数学公式 token 的 KaTeX 渲染
  - slug: mermaid-content
    relation: mermaid 代码块的图表渲染
  - slug: content-render
    relation: 上层按类型分发到本组件渲染 Markdown 字符串
sinceVersion: 1.0.0
domain: content
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import MarkdownContent from '../../../src/components/chat-content/markdown-content/markdown-content.vue'
  import { MessageStatus } from '../../../src/ag-ui/types/constants'

  const basicContent = `# 标题示例

这是一段 **Markdown** 内容，支持 _斜体_、~~删除线~~、\`行内代码\` 等格式。

- 列表项 1
- 列表项 2

\`\`\`javascript
console.log('Hello, World!');
\`\`\`
`;

  const textFormatContent = `**粗体文本** _斜体文本_ ~~删除线文本~~ \`行内代码\`

带有 ++下划线++ 和 ==高亮== 的文本。

H~2~O 是水的化学式，2^10^ = 1024。
`;

  const listContent = `- 无序列表项 1
- 无序列表项 2
  - 嵌套列表项 2.1
  - 嵌套列表项 2.2

1. 有序列表项 1
2. 有序列表项 2

- [x] 已完成的任务
- [ ] 未完成的任务
`;

  const codeContent = `\`\`\`typescript
interface User {
  id: number;
  name: string;
}

function greet(user: User): string {
  return \`Hello, \${user.name}!\`;
}
\`\`\`
`;

  const tableContent = `| 组件 | 用途 | 状态 |
| --- | --- | --- |
| MarkdownContent | Markdown 渲染 | ✅ 稳定 |
| CodeContent | 代码高亮 | ✅ 稳定 |
| MermaidContent | 图表渲染 | ✅ 稳定 |
| LatexContent | 公式渲染 | ✅ 稳定 |
`;

  const latexContent = `行内公式：质能方程 $E = mc^2$，勾股定理 $a^2 + b^2 = c^2$

块级公式：

$$
\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}
$$

$$
\\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}
$$
`;

  const mermaidContent = `\`\`\`mermaid
graph TD
    A[用户输入] --> B{是否合法?}
    B -->|是| C[处理请求]
    B -->|否| D[返回错误]
    C --> E[返回结果]
\`\`\`
`;

  const alignContainerContent = `::: hljs-left
左对齐段落
:::

::: hljs-center
居中段落
:::

::: hljs-right
右对齐段落
:::
`;

  const errorContent = '请求失败，服务端返回了错误响应。';

  const streamingContent = ref('');
  const isStreaming = ref(false);

  const simulateStreaming = async () => {
    streamingContent.value = '';
    isStreaming.value = true;
    const content = `## 流式渲染演示

这是一段 **流式输出** 的内容，组件自动处理未闭合语法。

- 列表项 1
- 列表项 2

\`\`\`javascript
function hello() {
  console.log('Hello!');
}
\`\`\`

> 引用也支持流式渲染

行内公式 $E = mc^2$ 同样支持。
`;
    for (const char of content) {
      await new Promise(r => setTimeout(r, 25));
      streamingContent.value += char;
    }
    isStreaming.value = false;
  };
</script>

# MarkdownContent Markdown 内容渲染

> **层级**：原子组件 · **功能域**：内容渲染

AI 消息内容渲染的核心原子组件，集成代码高亮、LaTeX 公式、Mermaid 图表等能力，内置流式渲染优化（5ms throttle + 语法补全 + 防闪烁）。

由 `AssistantMessage`、`ReasoningMessage` 等分子组件内部自动使用，通常不需要手动引入。

## 组件结构与渲染流程

```
props.content → completeMarkdownSyntax → md.parse → groupTokens → groupedTokens
                                                                          │
                          div.ai-markdown-content（contain: layout style）
                                        │
                        status === 'error' → CommonErrorContent（:content）
                                        │
                        else → div.ai-markdown-body[data-theme]（contain: content）
                                  │
                            v-for groupedToken
                                  │
                    ┌─────────────┼────────────────────┬───────────────┐
                    │             │                    │               │
              hasMermaid?   hasLatex?           hasCode?         else
                    ↓             ↓                    ↓               ↓
           MermaidContent  LatexContent        CodeContent    VNodeRenderer
           @mounted         @mounted           @mounted       @vue:mounted
                    │
                    └──── handleTokenMounted（throttle 100ms）→ containerScroll.toScrollBottom()
```

### Token 分组（groupTokens）

`groupTokens` 使用栈将扁平 Token 数组转为分组数组，每组对应一个顶层 DOM 节点（段落、标题、列表、代码块等）：

- `nesting === 1`（open）→ 入栈，建立新 group；顶层 group 立刻加入结果
- `nesting === -1`（close）→ 出栈，完成该 group；嵌套 group 合并到父 group
- `nesting === 0`（自闭合/inline）→ 无栈时独立成组，有栈时追加到当前 group

每组第一个 token 的 `attrs` 追加 `class="ai-blueking-markdown-fade-in"`，触发渐显动画。

### 子组件优先级

对每个 token 组按以下顺序判断：

| 优先级 | 检测逻辑                                                             | 使用组件                                  |
| ------ | -------------------------------------------------------------------- | ----------------------------------------- |
| 1      | `fence` token 且 `info === 'mermaid'`                                | `MermaidContent`                          |
| 2      | `math_inline` / `math_block`，或 children 中递归含有（inline token） | `LatexContent`                            |
| 3      | `fence`（非 mermaid）或 `code_block`                                 | `CodeContent`                             |
| 4      | 其余                                                                 | `VNodeRenderer`（HTML 由 DOMPurify 过滤） |

## 基础用法

```vue
<template>
  <MarkdownContent
    :content="markdownText"
    :status="MessageStatus.Complete"
  />
</template>

<script setup lang="ts">
  import { MarkdownContent, MessageStatus } from '@blueking/chat-x';

  const markdownText = `# 标题\n\n这是一段 **Markdown** 内容。`;
</script>
```

<div class="demo">
  <MarkdownContent :content="basicContent" :status="MessageStatus.Complete" />
</div>

## 扩展文本格式

支持标准 Markdown + 扩展插件：`++下划线++`（markdown-it-ins）、`==高亮==`（markdown-it-mark）、`~下标~`（markdown-it-sub）、`^上标^`（markdown-it-sup）：

<div class="demo">
  <MarkdownContent :content="textFormatContent" :status="MessageStatus.Complete" />
</div>

## 列表与任务清单

<div class="demo">
  <MarkdownContent :content="listContent" :status="MessageStatus.Complete" />
</div>

## 代码块

代码块由 `CodeContent` 渲染，支持 highlight.js 语法高亮、语言标签、一键复制：

<div class="demo">
  <MarkdownContent :content="codeContent" :status="MessageStatus.Complete" />
</div>

## 表格

<div class="demo">
  <MarkdownContent :content="tableContent" :status="MessageStatus.Complete" />
</div>

## 对齐容器（markdown-it-container）

支持 `::: hljs-left` / `::: hljs-center` / `::: hljs-right` 自定义容器，内容渲染在带对应 class 的块级容器中，由内置样式控制 `text-align`：

<div class="demo">
  <MarkdownContent :content="alignContainerContent" :status="MessageStatus.Complete" />
</div>

## LaTeX 公式

公式由 `LatexContent`（KaTeX）渲染，支持行内 `$...$` 和块级 `$$...$$`：

<div class="demo">
  <MarkdownContent :content="latexContent" :status="MessageStatus.Complete" />
</div>

## Mermaid 图表

<div class="demo">
  <MarkdownContent :content="mermaidContent" :status="MessageStatus.Complete" />
</div>

## 错误状态

`status === MessageStatus.Error` 时渲染 `CommonErrorContent`，将 `content` 作为错误文本显示：

<div class="demo">
  <MarkdownContent :content="errorContent" :status="MessageStatus.Error" />
</div>

## 流式渲染

````vue
<template>
  <MarkdownContent
    :content="streamingContent"
    :status="isStreaming ? MessageStatus.Streaming : MessageStatus.Complete"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MarkdownContent, MessageStatus } from '@blueking/chat-x';

  const streamingContent = ref('');
  const isStreaming = ref(false);

  const simulate = async () => {
    const fullText = '## Hello\n\n**流式输出**演示。\n\n```js\nconsole.log(1);\n```';
    isStreaming.value = true;
    for (const char of fullText) {
      await new Promise(r => setTimeout(r, 30));
      streamingContent.value += char;
    }
    isStreaming.value = false;
  };
</script>
````

<div class="demo">
  <div>
    <button
      @click="simulateStreaming"
      :disabled="isStreaming"
      style="margin-bottom: 12px; padding: 4px 12px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
    >
      {{ isStreaming ? '输出中...' : '模拟流式输入' }}
    </button>
    <MarkdownContent
      :content="streamingContent"
      :status="isStreaming ? MessageStatus.Streaming : MessageStatus.Complete"
    />
  </div>
</div>

### 流式优化机制

| 机制              | 实现                                                                                         | 作用                                                       |
| ----------------- | -------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| 极速节流          | `parseMarkdownContent` throttle **5ms**，leading + trailing                                  | 每 5ms 最多解析一次，兼顾实时性与性能                      |
| Markdown 语法补全 | `completeMarkdownSyntax(content)`                                                            | 自动闭合代码块、行内代码、粗斜体、删除线、链接等未完成语法 |
| LaTeX 防闪烁      | `isIncomplete=true` 且已有渲染结果 → **跳过本次更新**                                        | 正在输入 LaTeX 命令时保持上一帧，避免闪白                  |
| 子组件 throttle   | `handleTokenMounted` throttle 100ms                                                          | 限制子组件挂载后触发的滚动到底部频率                       |
| CSS contain       | `.ai-markdown-content { contain: layout style }`<br>`.ai-markdown-body { contain: content }` | 限制重排/重绘范围，减少流式渲染的布局开销                  |
| 渐显动画          | 每组首 token 追加 `.ai-blueking-markdown-fade-in`                                            | 新内容块淡入，减少视觉跳跃感                               |

## 主题支持

组件通过 `data-theme` 属性和本地 `markdown-content.css`（由 GitHub Markdown 样式 vendoring 而来，类前缀为 `ai-markdown-body`）控制主题，默认为 `light`，避免受宿主页面 `@media (prefers-color-scheme)` 影响。

- **Light 模式**（默认）：`.ai-markdown-body[data-theme="light"]`，light 变量 + `color-scheme: light`
- **Dark 模式**：`.ai-markdown-body[data-theme="dark"]`，dark 变量 + `color-scheme: dark`

> 外层包裹类名为 `.ai-markdown-content`，内层正文区为 `.ai-markdown-body`，避免与宿主或其他库的 `.markdown-body` 全局样式冲突。

## API

### Props

| 属性名  | 类型            | 必填 | 说明                                                      |
| ------- | --------------- | ---- | --------------------------------------------------------- |
| content | `string`        | —    | Markdown 文本；为空时清空渲染结果                         |
| status  | `MessageStatus` | —    | `'error'` 时显示 `CommonErrorContent`，其余状态均正常渲染 |

### Slots

| 插槽名     | 参数                                   | 说明                                                                                    |
| ---------- | -------------------------------------- | --------------------------------------------------------------------------------------- |
| codeHeader | `{ language: string; token: Token[] }` | 代码块头部自定义操作区域，透传给 CodeContent 的 header 插槽，可添加"插入"、"应用"等按钮 |

### 内置插件

| 插件                        | 语法                | 功能                 |
| --------------------------- | ------------------- | -------------------- |
| `markdown-it-footnote`      | `[^1]`              | 脚注                 |
| `markdown-it-ins`           | `++text++`          | 下划线               |
| `markdown-it-mark`          | `==text==`          | 高亮                 |
| `markdown-it-sub`           | `~text~`            | 下标                 |
| `markdown-it-sup`           | `^text^`            | 上标                 |
| `markdown-it-task-checkbox` | `- [x]`             | 任务列表             |
| `markdownItMermaid`         | ` ```mermaid `      | Mermaid 图表 token   |
| `markdownItLatex`           | `$...$` / `$$...$$` | KaTeX 数学公式 token |
| `markdownItContainer`       | `::: hljs-left` 等  | 自定义对齐容器（class 与 highlight.js 命名对齐） |

### 安全性

`VNodeRenderer` 渲染的 HTML 统一经过 DOMPurify 过滤，并额外允许 KaTeX 所需标签：

```typescript
const domPurifyConfig = {
  ADD_TAGS: ['semantics', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac', 'mtext', 'annotation'],
  ADD_ATTR: ['xmlns', 'mathvariant', 'encoding', 'style'],
};
```

> `CodeContent`、`MermaidContent`、`LatexContent` 各自内部处理安全性（KaTeX `errorColor`、highlight.js 转义等），不经过 DOMPurify。

## 关联组件

- [CodeContent](./code-content.md) — 代码 fence 高亮
- [LatexContent](./latex-content.md) — 公式渲染
- [MermaidContent](./mermaid-content.md) — Mermaid 图表
- [ContentRender](../molecular/content-render.md) — 内容类型分发入口
