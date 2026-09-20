# 插件

`@blueking/chat-x` 提供一些 Markdown-it 插件，用于扩展 Markdown 的解析能力。包入口导出以 `src/plugins/index.ts` 为准。

## 公开插件（可从包入口引入）

| 插件名 | 说明 | 文档 |
| --- | --- | --- |
| `markdownItLatex` | LaTeX 公式解析 | [查看](./markdown-latex.md) |
| `markdownItMermaid` | Mermaid 图表解析 | [查看](./markdown-mermaid.md) |
| `markdownItBkInlineStyle` | 蓝鲸行内富文本 | 源码 `src/plugins/markdown-bk-inline-style.ts` |
| `markdownAnimationAttrs` | 流式动画属性 | 源码 `src/plugins/markdown-animation-attrs.ts` |

```typescript
import {
  markdownItLatex,
  markdownItMermaid,
  markdownItBkInlineStyle,
  markdownAnimationAttrs,
} from '@blueking/chat-x';
```

## 使用示例

```typescript
import MarkdownIt from 'markdown-it';
import { markdownItLatex, markdownItMermaid } from '@blueking/chat-x';

const md = new MarkdownIt().use(markdownItLatex, { replaceAlignStart: true }).use(markdownItMermaid);

const html = md.render(`
# 数学公式

行内公式：$E = mc^2$
`);
```

## 内部插件（未从包入口导出）

| 插件名 | 说明 | 文档 |
| --- | --- | --- |
| `markdownItContainer` | 自定义 `:::` 容器，供 MarkdownContent 对齐块使用 | [查看](./markdown-container.md) |

## 注意事项

1. **渲染分离**：插件只负责解析，实际渲染由对应的 Vue 组件完成
2. **内置使用**：`MarkdownContent` 已内置公开插件与内部 container
3. **自定义场景**：如需自定义 Markdown 渲染，可单独引入**公开**插件
