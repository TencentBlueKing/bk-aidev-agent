---
name: VNodeRenderer VNode 渲染器
slug: vnode-renderer
kind: component
domain: helper
description: 将 Markdown token 转成 VNode 的内部渲染桥。
aiSummary: >
  将 Markdown token 转成 VNode 的内部渲染桥。
  源码位置：src/components/chat-content/vnode-renderer.ts。
relatedComponents:
  - slug: markdown-content
    relation: MarkdownContent 对普通 token 分组使用本组件渲染
  - slug: code-content
    relation: fence/code_block 代码块通常会被 MarkdownContent 提前分流到 CodeContent
  - slug: mermaid-content
    relation: mermaid 代码块通常会被 MarkdownContent 提前分流到 MermaidContent
  - slug: image-content
    relation: 图片 token 由 tokensToVNodes 转为 ImageContent
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import VNodeRendererComp from '../../../src/components/chat-content/vnode-renderer';
  import MarkdownIt from '../../../src/markdown-it/index';

  const md = new MarkdownIt();
  const tokens = md.parse('这是一段 **加粗文本**，包含 [外部链接](https://example.com)。', {});
  const emptyTokens = [];
</script>

# VNodeRenderer VNode 渲染器

> **能力域**：辅助能力

`VNodeRenderer` 是 Markdown 渲染链路里的内部桥接组件。它接收 markdown-it 解析出的 `Token[]`，调用 `tokensToVNodes` 转成 Vue VNode，并返回渲染函数结果。

通常不需要业务侧直接使用。完整 Markdown 内容请优先使用 [MarkdownContent](../rendering/markdown-content.md)，它会先识别 Mermaid、LaTeX、代码块等特殊 token，再把普通 token 分组交给 `VNodeRenderer`。

## 源码事实

- **源码位置**：`src/components/chat-content/vnode-renderer.ts`
- **能力说明**：将 Markdown token 转成 VNode 的内部渲染桥。

## 核心能力

- **Token 到 VNode**：将 markdown-it 的 block、inline、text、link、image、html 等 token 转为 Vue VNode
- **稳定 key**：`tokensToVNodes` 基于 token 类型、标签和内容 hash 生成 key，降低流式渲染时 DOM 误复用风险
- **HTML 安全入口**：`options.html` 开启时可渲染 HTML token，实际安全过滤依赖 `options.sanitize`
- **渲染规则复用**：支持传入 markdown-it `renderer` 与 `mditOptions`，复用自定义 renderer rule
- **特殊 token 兜底**：图片 token 转成 `ImageContent`，链接自动补充 `target="_blank"` 与 `rel="noopener noreferrer"`

## 基础用法

```vue
<template>
  <VNodeRenderer :tokens="tokens" />
</template>

<script setup lang="ts">
  import MarkdownIt from '@blueking/chat-x/src/markdown-it/index';
  import VNodeRenderer from '@blueking/chat-x/src/components/chat-content/vnode-renderer';

  const md = new MarkdownIt();
  const tokens = md.parse('这是一段 **加粗文本**。', {});
</script>
```

**渲染效果**

<div class="demo">
  <VNodeRendererComp :tokens="tokens" />
</div>

## 空 Tokens

`tokens` 为空数组时，`tokensToVNodes` 返回空数组，不渲染任何内容。

<div class="demo">
  <VNodeRendererComp :tokens="emptyTokens" />
</div>

## 与 MarkdownContent 的关系

`MarkdownContent` 会先按 token 类型分流，再将普通 token 交给 `VNodeRenderer`：

```vue
<template v-else>
  <VNodeRenderer
    :options="vnodeOptions"
    :tokens="groupedToken"
  />
</template>
```

其中 `vnodeOptions` 会携带 HTML 净化函数、markdown-it renderer 和 parser options：

```typescript
const vnodeOptions = {
  html: true,
  mditOptions: md.options,
  renderer: md.renderer,
  sanitize: (html: string) => dompurify.sanitize(html, domPurifyConfig),
};
```

## API

### Props

| 属性名  | 类型                  | 必填 | 默认值 | 说明                         |
| ------- | --------------------- | ---- | ------ | ---------------------------- |
| tokens  | `Token[]`             | 是   | —      | markdown-it token 数组       |
| options | `TokenToVNodeOptions` | 否   | `{}`   | token 转 VNode 的渲染选项    |

### Emits

- 无。

### Slots

- 无。

### Expose

- 无。

## 类型定义

```typescript
export interface TokenToVNodeOptions {
  highlight?: ((str: string, lang: string, attrs?: unknown) => string) | null;
  html?: boolean;
  mditOptions?: Options;
  renderer?: Renderer;
  sanitize?: (html: string) => string;
}
```

## 使用建议

- 业务侧不要绕过 `MarkdownContent` 直接渲染完整 Markdown 字符串；`VNodeRenderer` 只接收已经解析好的 token。
- 如果启用 `options.html`，必须同步传入 `sanitize`，否则 HTML token 会直接进入 `innerHTML`。
- 特殊内容如代码块、Mermaid、LaTeX 推荐继续走 `MarkdownContent` 的分流逻辑。

## 关联组件

- [MarkdownContent](../rendering/markdown-content.md) — Markdown 主渲染器。
- [CodeContent](../rendering/code-content.md) — 代码块渲染。
- [MermaidContent](../rendering/mermaid-content.md) — Mermaid 图表渲染。
- [ImageContent](../media/image-content.md) — 图片 token 渲染。
