# 插件

`@blueking/chat-x` 提供了一些 Markdown-it 插件，用于扩展 Markdown 的解析能力。

---

# 插件

`@blueking/chat-x` 提供了一些 Markdown-it 插件，用于扩展 Markdown 的解析能力。

## 插件列表

| 插件名            | 说明             | 文档                          |
| ----------------- | ---------------- | ----------------------------- |
| markdownItLatex   | LaTeX 公式解析   | [查看](./markdown-latex.md)   |
| markdownItMermaid | Mermaid 图表解析 | [查看](./markdown-mermaid.md) |

## 引入方式

```typescript
import { markdownItLatex, markdownItMermaid } from '@blueking/chat-x';
```

## 使用示例

```typescript
import MarkdownIt from 'markdown-it';
import { markdownItLatex, markdownItMermaid } from '@blueking/chat-x';

const md = new MarkdownIt().use(markdownItLatex, { replaceAlignStart: true }).use(markdownItMermaid);

const html = md.render(`
# 数学公式

行内公式：$E = mc^2$

块级公式：

$$
\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}
$$

# 流程图

\`\`\`mermaid
graph TD
    A[开始] --> B[结束]
\`\`\`
`);
```

## 注意事项

1. **渲染分离**：插件只负责解析，实际渲染由对应的 Vue 组件完成
2. **内置使用**：`ContentRender` 和 `MarkdownContent` 组件已内置这些插件
3. **自定义场景**：如需自定义 Markdown 渲染，可单独引入插件使用
