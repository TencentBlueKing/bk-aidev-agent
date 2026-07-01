---
name: markdownItLatex
slug: markdown-latex
category: plugin
description: Markdown-it LaTeX 解析插件，用于解析 LaTeX 数学公式语法。
aiSummary: >
  markdownItLatex 为 markdown-it 插件，解析 $...$、$$...$$、\\(...\\)、\\[...\\] 为 math_inline / math_block token，可选 LatexOption.replaceAlignStart。
  不负责渲染，KaTeX 在 LatexContent 中异步渲染。与 Markdown 管道、ContentRender 中的公式展示链路配合。
relatedComponents:
  - slug: latex-content
    relation: 消费 math token 并 KaTeX 渲染
  - slug: markdown-content
    relation: Markdown 渲染管线
  - slug: content-render
    relation: 消息内容统一渲染入口
sinceVersion: 1.0.0
---

# markdownItLatex LaTeX 解析插件

> **分类**：plugin

Markdown-it LaTeX 解析插件，用于解析 LaTeX 数学公式语法。

## 功能说明

此插件只负责解析 LaTeX 语法，将其转换为 `math_inline` 和 `math_block` token。实际的 KaTeX 渲染在 `LatexContent` 组件中完成。

## 支持的语法

| 语法      | 类型     | 示例                   |
| --------- | -------- | ---------------------- |
| `$...$`   | 行内公式 | `$E = mc^2$`           |
| `$$...$$` | 块级公式 | `$$\sum_{i=1}^{n} i$$` |
| `\(...\)` | 行内公式 | `\(E = mc^2\)`         |
| `\[...\]` | 块级公式 | `\[\sum_{i=1}^{n} i\]` |

## 基础用法

```typescript
import MarkdownIt from 'markdown-it';
import { markdownItLatex } from '@blueking/chat-x';

const md = new MarkdownIt().use(markdownItLatex);

// 解析包含 LaTeX 的 Markdown
const tokens = md.parse(`
行内公式：$E = mc^2$

块级公式：

$$
\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}
$$
`);
```

## 配置选项

```typescript
import MarkdownIt from 'markdown-it';
import { markdownItLatex, type LatexOption } from '@blueking/chat-x';

const options: LatexOption = {
  replaceAlignStart: true, // 将 align* 替换为 aligned（KaTeX 不支持 align*）
};

const md = new MarkdownIt().use(markdownItLatex, options);
```

### 配置项

| 属性名            | 类型      | 默认值 | 说明                             |
| ----------------- | --------- | ------ | -------------------------------- |
| replaceAlignStart | `boolean` | `true` | 是否将 `align*` 替换为 `aligned` |

## Token 类型

插件会生成以下两种 token：

### math_inline

行内数学公式 token：

```typescript
{
  type: 'math_inline',
  tag: 'math',
  content: 'E = mc^2',
  markup: '$',
  meta: { displayMode: false }
}
```

### math_block

块级数学公式 token：

```typescript
{
  type: 'math_block',
  tag: 'math',
  content: '\\sum_{i=1}^{n} i = \\frac{n(n+1)}{2}',
  markup: '$$',
  block: true,
  map: [startLine, endLine]
}
```

## 公式示例

### 基础公式

```markdown
行内公式：$E = mc^2$

块级公式：

$$
E = mc^2
$$
```

### 复杂公式

```markdown
$$
\\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}
$$
```

### 矩阵

```markdown
$$
\\begin{pmatrix}
a & b \\\\
c & d
\\end{pmatrix}
$$
```

### 多行公式

```markdown
$$
\\begin{aligned}
f(x) &= x^2 + 2x + 1 \\\\
     &= (x + 1)^2
\\end{aligned}
$$
```

## 转义处理

插件会正确处理转义的分隔符：

```markdown
这不是公式：\$100

这是公式：$x = 100$
```

## 与 KaTeX 配合

渲染由 `LatexContent` 组件完成，使用 KaTeX 库：

```vue
<template>
  <LatexContent :token="latexTokens" />
</template>

<script setup lang="ts">
  import { LatexContent } from '@blueking/chat-x';

  // latexTokens 是包含 math_inline 或 math_block 的 token 数组
</script>
```

## KaTeX 支持说明

KaTeX 支持的功能：

- 大多数 LaTeX 数学符号
- 分数、根号、指数
- 矩阵和数组
- 括号和分隔符
- 希腊字母和运算符
- 上下标和大型运算符

KaTeX 限制：

- 不支持 `align*` 环境（插件会自动替换为 `aligned`）
- 部分 LaTeX 宏不支持

## 使用场景

- AI 数学问答
- 技术文档展示
- 教育类应用
- 科学计算结果展示

## 注意事项

1. **双反斜杠**：在 JavaScript 字符串中，`\` 需要写成 `\\`
2. **环境支持**：建议使用 `aligned` 替代 `align*`
3. **性能考虑**：KaTeX 渲染在组件中异步进行，避免阻塞主线程

## 关联组件

- [LatexContent](../components/rendering/latex-content) — KaTeX 渲染
- [MarkdownContent](../components/rendering/markdown-content) — Markdown 内容
- [ContentRender](../components/rendering/content-render) — 内容渲染
