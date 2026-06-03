---
name: markdownItContainer
slug: markdown-container
category: plugin
description: "Markdown-it 自定义容器插件，支持 ::: name ... ::: 语法，用于对齐块等场景。"
aiSummary: >
  markdownItContainer 基于 markdown-it-container，支持字符串或正则匹配容器名；MarkdownContent 中用于 hljs-left/center/right 对齐。
  渲染为带 class 的 div，与 tokens-to-vnodes 及样式配合。
relatedComponents:
  - slug: markdown-content
    relation: 渲染管线中注册插件
sinceVersion: 1.0.0
---

# markdownItContainer 自定义容器插件

> **分类**：plugin

将 `::: 容器名` 开头的块解析为带 `class` 的块级容器，闭合行使用 `:::`。

## 语法示例

```markdown
::: hljs-left
左对齐内容
:::

::: hljs-center
居中内容
:::

::: hljs-right
右对齐内容
:::
```

## 在 MarkdownContent 中的注册方式

组件内使用正则同时注册左/中/右三种容器名：

```typescript
import MarkdownIt from 'markdown-it';
import { markdownItContainer } from '../../../src/plugins/markdown-container';

const md = new MarkdownIt({ html: true }).use(markdownItContainer, /^hljs-(left|center|right)$/);
```

## 配置说明

| 参数   | 类型                | 说明                                               |
| ------ | ------------------- | -------------------------------------------------- |
| `name` | `string \| RegExp`  | 容器标识；字符串为精确匹配，正则用于一类名称       |
| `opts` | `ContainerOptions?` | 可选 `marker`、`validate`、`render` 覆盖默认行为   |

更多行为见源码 `packages/chat-x/src/plugins/markdown-container.ts`。

## 关联

- [MarkdownContent](../components/rendering/markdown-content) — 实际接入与样式
