# MarkdownContent Markdown 内容渲染

> 能力域：内容渲染 ｜ 导入：`import { MarkdownContent } from '@blueking/chat-x'` ｜ since 1.0.0

Markdown 主渲染器，集成代码块、公式、错误降级和 codeHeader 插槽。 源码位置：src/components/chat-content/markdown-content/markdown-content.vue。

**关联**：code-content（fence 代码块语法高亮与复制）、latex-content（数学公式 token 的 KaTeX 渲染）、mermaid-content（mermaid 代码块的图表渲染）、content-render（上层按类型分发到本组件渲染 Markdown 字符串）

---

# MarkdownContent Markdown 内容渲染
## 源码事实

- **源码位置**：`src/components/chat-content/markdown-content/markdown-content.vue`
- **能力域**：内容渲染
- **能力说明**：Markdown 主渲染器，集成代码块、公式、错误降级和 codeHeader 插槽。

> **能力域**：内容渲染

AI 消息内容渲染的核心基础组件，集成代码高亮、LaTeX 公式、Mermaid 图表等能力，内置流式渲染优化（5ms throttle + 语法补全 + 防闪烁）。

由 `AssistantMessage`、`ReasoningMessage` 等组合组件内部自动使用，通常不需要手动引入。

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

`VNodeRenderer` 的 `options` 中包含与当前 `MarkdownIt` 实例一致的 `mditOptions`（即 `md.options`），以便 `tokensToVNodes` 调用 `renderer.rules` 时第三参与 markdown-it 原生规则签名一致。

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

## 扩展文本格式

支持标准 Markdown + 扩展插件：`++下划线++`（markdown-it-ins）、`==高亮==`（markdown-it-mark）、`~下标~`（markdown-it-sub）、`^上标^`（markdown-it-sup）：

## 列表与任务清单

## 代码块

代码块由 `CodeContent` 渲染，支持 highlight.js 语法高亮、语言标签、一键复制。语法高亮主题样式由 `CodeContent` 侧引入（`github-dark`），`MarkdownContent` **不再**全局引入 `highlight.js` 主题 CSS，避免与代码块组件重复加载、并保持与消息区样式一致。

## 表格

## 对齐容器（markdown-it-container）

支持 `::: hljs-left` / `::: hljs-center` / `::: hljs-right` 自定义容器，内容渲染在带对应 class 的块级容器中，由内置样式控制 `text-align`：

## LaTeX 公式

公式由 `LatexContent`（KaTeX）渲染，支持行内 `$...$` 和块级 `$$...$$`：

## Mermaid 图表

## 错误状态

`status === MessageStatus.Error` 时渲染 `CommonErrorContent`，将 `content` 作为错误文本显示：

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
| `markdownItBkInlineStyle`   | 见下文「蓝鲸行内样式」 | 安全行内颜色/字号/粗斜体（非 HTML） |
| `markdown-it-footnote`      | `[^1]`              | 脚注                 |
| `markdown-it-ins`           | `++text++`          | 下划线               |
| `markdown-it-mark`          | `==text==`          | 高亮                 |
| `markdown-it-sub`           | `~text~`            | 下标                 |
| `markdown-it-sup`           | `^text^`            | 上标                 |
| `markdown-it-task-checkbox` | `- [x]`             | 任务列表             |
| `markdownItMermaid`         | ` ```mermaid `      | Mermaid 图表 token   |
| `markdownItLatex`           | `$...$` / `$$...$$` | KaTeX 数学公式 token |
| `markdownItContainer`       | `::: hljs-left` 等  | 自定义对齐容器（class 与 highlight.js 命名对齐） |

### 蓝鲸行内样式（`markdownItBkInlineStyle`）

不开启 `html: true`，由专用语法生成带白名单 `style` 的 `<span class="bk-md-inline-style">`。

**语法**：`::bk{` *属性* `}` *正文* `:/bk::`

- 属性写在 `{}` 内，使用 `;` 分隔；每项为 `键=值` 或 `键:值`。
- 正文支持行内 Markdown（如 `**粗体**`）。
- 结束标记必须为字面量 `:/bk::`，请勿在正文中出现该序列。

**支持的键**：`color` / `c`、`background-color`、`font-size`、`bold`、`italic`（详见 `plugins/markdown-bk-inline-style.ts` 内注释）。

**示例**：

```markdown
::bk{color:#c00;font-size:18px}**重要**:/bk::
::bk{background-color:yellow}高亮:/bk::
::bk{bold;italic}强调:/bk::
```

### 安全性

`MarkdownIt` **不**开启 `html: true`，用户无法插入任意 HTML 标签；行内彩色/字号等请使用上文「蓝鲸行内样式」扩展。

`VNodeRenderer` 渲染的 HTML 统一经过 DOMPurify 过滤，并额外允许 KaTeX 所需标签：

```typescript
const domPurifyConfig = {
  ADD_TAGS: ['semantics', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac', 'mtext', 'annotation'],
  ADD_ATTR: ['xmlns', 'mathvariant', 'encoding', 'style'],
};
```

> `CodeContent`、`MermaidContent`、`LatexContent` 各自内部处理安全性（KaTeX `errorColor`、highlight.js 转义等），不经过 DOMPurify。

## 关联组件

- [CodeContent](/components/rendering/code-content) — 代码 fence 高亮
- [LatexContent](/components/rendering/latex-content) — 公式渲染
- [MermaidContent](/components/rendering/mermaid-content) — Mermaid 图表
- [ContentRender](/components/rendering/content-render) — 内容类型分发入口
