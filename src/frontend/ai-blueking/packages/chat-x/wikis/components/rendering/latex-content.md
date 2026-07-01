---
name: LatexContent LaTeX 公式
slug: latex-content
kind: component
domain: rendering
description: 使用 KaTeX 渲染 LaTeX 公式内容。
aiSummary: >
  使用 KaTeX 渲染 LaTeX 公式内容。
  源码位置：src/components/markdown-token/latex-content/latex-content.vue。
relatedComponents:
  - slug: markdown-content
    relation: 插件解析 $...$ / $$...$$ 后生成数学 token 并挂载本组件
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import LatexContent from '../../../src/components/markdown-token/latex-content/latex-content.vue'

  const blockTokens = [
    { type: 'math_block', content: 'E = mc^2' },
  ];

  const inlineTokens = [
    { type: 'math_inline', content: 'a^2 + b^2 = c^2' },
  ];

  const integralTokens = [
    { type: 'math_block', content: '\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}' },
  ];

  const matrixTokens = [
    { type: 'math_block', content: '\\begin{pmatrix} a & b \\\\ c & d \\end{pmatrix}' },
  ];

  const alignedTokens = [
    { type: 'math_block', content: '\\begin{aligned} f(x) &= x^2 + 2x + 1 \\\\ &= (x+1)^2 \\end{aligned}' },
  ];

  const mixedTokens = [
    { type: 'inline', children: [
      { type: 'text', content: '勾股定理：' },
      { type: 'math_inline', content: 'a^2 + b^2 = c^2' },
      { type: 'text', content: '，质能方程：' },
      { type: 'math_inline', content: 'E = mc^2' },
    ]},
  ];

  const streamingTokens = ref([
    { type: 'math_block', content: '' },
  ]);
  const isStreaming = ref(false);
  const streamProgress = ref('');

  const simulateStreaming = async () => {
    const formula = '\\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}';
    streamingTokens.value = [{ type: 'math_block', content: '' }];
    streamProgress.value = '';
    isStreaming.value = true;
    let content = '';
    for (const char of formula) {
      await new Promise(r => setTimeout(r, 50));
      content += char;
      streamProgress.value = content;
      streamingTokens.value = [{ type: 'math_block', content }];
    }
    isStreaming.value = false;
  };
</script>

# LatexContent LaTeX 公式渲染
## 源码事实

- **源码位置**：`src/components/markdown-token/latex-content/latex-content.vue`
- **能力域**：内容渲染
- **能力说明**：使用 KaTeX 渲染 LaTeX 公式内容。



> **能力域**：内容渲染

Markdown Token 层的 LaTeX 公式渲染基础组件，基于 **KaTeX** 实现。被 `MarkdownContent` 在解析到数学公式 token 时自动调用，通常无需手动引入。

核心能力：**流式防抖渲染**（throttle 100ms）、**语法自动补全**（`completeLatexContent`）、**渐进式降级重试**（最多 5 次）、**错误静默**（错误文本白色不可见）。

## 组件结构与 Token 渲染路径

```
props.token（Token[]）
│
├─ token.type === 'math_block'（单块且 token.length ≤ 1）
│    wrapperTag = 'div'，wrapperClass = 'block-latex-content'
│    └─ <div class="block-latex-wrapper">
│          └─ renderLatexToken(token) → <span class="block-katex">KaTeX HTML</span>
│
├─ token.type === 'math_inline'（或混合 token 数组）
│    wrapperTag = 'span'，wrapperClass = 'inline-latex-content'
│    └─ renderLatexToken(token) → <span class="inline-katex">KaTeX HTML</span>
│
├─ token.type === 'inline'（含 children）
│    └─ renderInlineChildren(token.children)
│         ├─ math_inline  → renderLatexToken（递归）
│         ├─ text         → escapeHtml
│         ├─ softbreak    → '\n'
│         ├─ hardbreak    → '<br>'
│         ├─ code_inline  → '<code>...</code>'
│         ├─ strong_open/close → '<strong>' / '</strong>'
│         ├─ em_open/close    → '<em>' / '</em>'
│         ├─ s_open/close     → '<s>' / '</s>'
│         ├─ link_open/close  → '<a href="...">...</a>'
│         ├─ image            → '<img src="..." alt="...">'
│         └─ 未知类型         → escapeHtml(token.content)
│
├─ token.type === 'paragraph_open/close' → '<p>' / '</p>'
└─ token.type === 'text' / 其他         → escapeHtml(token.content)
```

### displayMode 判断规则

```typescript
// renderLatexToken 内部
const displayMode = token.type === 'math_block' || token.meta?.displayMode === true;
// math_inline 也可通过 meta.displayMode=true 强制块级渲染
```

## 基础用法：块级公式

```vue
<template>
  <LatexContent :token="token" />
</template>

<script setup lang="ts">
  import { LatexContent } from '@blueking/chat-x';
  import type { Token } from 'markdown-it';

  const token: Token[] = [{ type: 'math_block', content: 'E = mc^2' } as Token];
</script>
```

<div class="demo">
  <LatexContent :token="blockTokens" />
</div>

## 行内公式

`math_inline` 类型，包装为 `span.inline-latex-content`，嵌入文字流中渲染：

```vue
<template>
  <!-- 行内公式 -->
  <LatexContent :token="[{ type: 'math_inline', content: 'a^2 + b^2 = c^2' }]" />
</template>
```

<div class="demo">
  行内公式：<LatexContent :token="inlineTokens" />，可嵌入正文。
</div>

## 混合 inline token（文字 + 公式）

传入 `inline` token 并带 `children` 时，`renderInlineChildren` 逐一处理文本、公式、标记：

<div class="demo">
  <LatexContent :token="mixedTokens" />
</div>

## 积分与根号

<div class="demo">
  <LatexContent :token="integralTokens" />
</div>

## 矩阵

<div class="demo">
  <LatexContent :token="matrixTokens" />
</div>

## 对齐环境

<div class="demo">
  <LatexContent :token="alignedTokens" />
</div>

## 流式渲染防闪烁

组件针对流式 Markdown 输入进行了优化：**100ms throttle**（leading + trailing）避免每字符重渲染，**`completeLatexContent`** 在每次渲染前自动补全不完整语法：

```vue
<template>
  <LatexContent :token="streamingTokens" />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { LatexContent } from '@blueking/chat-x';

  const streamingTokens = ref([{ type: 'math_block', content: '' }]);

  const simulate = async () => {
    const formula = '\\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}';
    let content = '';
    for (const char of formula) {
      await new Promise(r => setTimeout(r, 50));
      content += char;
      streamingTokens.value = [{ type: 'math_block', content }];
    }
  };
</script>
```

<div class="demo">
  <div>
    <button
      @click="simulateStreaming"
      :disabled="isStreaming"
      style="margin-bottom: 12px; padding: 4px 12px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
    >
      {{ isStreaming ? '渲染中...' : '模拟流式输入' }}
    </button>
    <div style="font-size: 12px; color: #979ba5; margin-bottom: 8px; word-break: break-all;">
      当前输入：<code>{{ streamProgress || '(空)' }}</code>
    </div>
    <LatexContent :token="streamingTokens" />
  </div>
</div>

## 语法自动补全（completeLatexContent）

在每次调用 KaTeX 前，组件先通过 `completeLatexContent` 修复不完整语法，处理顺序为：

| 步骤 | 处理内容                                                              | 示例                                          |
| ---- | --------------------------------------------------------------------- | --------------------------------------------- |
| 0    | 不完整 `\begin{env` → 猜测环境名补全 `\begin{env}\end{env}`           | `\begin{pma` → `\begin{pmatrix}\end{pmatrix}` |
| 0.1  | 不完整 `\end{env` → 猜测环境名补全                                    | `\end{alig` → `\end{aligned}`                 |
| 0.2  | 末尾不完整命令 `\begi` → 若匹配已知命令前缀则移除，完整命令则补全参数 | `\frac` → `\frac{}{}`                         |
| 1    | 未闭合 `{}` → 补全缺失的 `}`                                          | `\frac{a}{b` → `\frac{a}{b}`                  |
| 2    | 未闭合 `[]` → 补全缺失的 `]`                                          | `\sqrt[3` → `\sqrt[3]`                        |
| 3    | 双参数命令缺第二个参数 → 追加 `{}`                                    | `\frac{a}` → `\frac{a}{}`                     |
| 4    | `\begin{env}` 无对应 `\end{env}` → 追加 `\end{env}`                   | `\begin{matrix}...` → `...\end{matrix}`       |

**可猜测的环境名**（`COMMON_ENVS`）：`aligned`、`align`、`equation`、`gather`、`matrix`、`pmatrix`、`bmatrix`、`vmatrix`、`cases`、`array`、`split`、`multline`

**双参数命令**（`TWO_ARG_COMMANDS`）：`frac`、`dfrac`、`tfrac`、`binom`、`cfrac`、`overset`、`underset` 等

**单参数命令**（`ONE_ARG_COMMANDS`）：`sqrt`、`text`、`mathbf`、`hat`、`vec`、`overline`、`boxed` 等

## 渐进式降级重试（tryRenderKatex）

补全后仍渲染失败时，最多重试 5 次，每次尝试两种裁剪策略：

```
尝试 completeLatexContent(content) → KaTeX 渲染
  失败 →
    策略 1：移除末尾不完整命令（正则 /\\[a-zA-Z]+(\{[^{}]*\})*\s*$/）
    策略 2：移除未闭合 {（正则 /\{[^{}]*$/）
  若仍失败 → 返回 null
    → 渲染 <span class="katex-loading" style="color: #666; font-style: italic;">原始文本（HTML 转义）</span>
```

> **错误静默**：KaTeX 以 `errorColor: '#fff'`（白色）渲染错误文本，错误不可见。若检测到 HTML 中含 `katex-error` 类或 `color:#cc0000`，也视为渲染失败，降级为 `katex-loading` 显示原始文本。

## API

### Props

| 属性名 | 类型      | 必填 | 说明                                                                                                                     |
| ------ | --------- | ---- | ------------------------------------------------------------------------------------------------------------------------ |
| token  | `Token[]` | ✓    | markdown-it Token 数组；支持 `math_block`、`math_inline`、`inline`（含 children）、`paragraph_open/close`、`text` 等类型 |

### Token 结构

```typescript
// math_block / math_inline
{
  type: 'math_block' | 'math_inline';
  content: string;              // LaTeX 公式字符串
  meta?: { displayMode?: boolean }; // true → 块级渲染（math_inline 可用此强制块级）
}

// inline（含行内标记 + 公式混排）
{
  type: 'inline';
  children: Token[];            // 子 token 列表
}
```

## 样式说明

| 类名                    | 标签   | 作用                                                                                        |
| ----------------------- | ------ | ------------------------------------------------------------------------------------------- |
| `.block-latex-content`  | `div`  | 单一 `math_block` 时的外层，`text-align: center`，`overflow: auto hidden`，`margin: 16px 0` |
| `.inline-latex-content` | `span` | 混合/行内时的外层，`display: inline`，`vertical-align: baseline`                            |
| `.block-latex-wrapper`  | `div`  | 每个 `math_block` token 的包装，`text-align: center`，`margin: 16px 0`                      |
| `.block-katex`          | `span` | 块级 KaTeX 输出                                                                             |
| `.inline-katex`         | `span` | 行内 KaTeX 输出                                                                             |
| `.katex-loading`        | `span` | 渲染失败降级态，斜体灰色显示原始 LaTeX 文本                                                 |

## 关联组件

- [MarkdownContent](/components/rendering/markdown-content) — 数学公式 token 的来源与挂载
