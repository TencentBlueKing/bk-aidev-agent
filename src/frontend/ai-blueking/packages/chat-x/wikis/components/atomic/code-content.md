---
name: CodeContent 代码块渲染
slug: code-content
category: atomic
description: >-
  代码块渲染原子组件，专为 **Markdown 流式输出**设计。接收 `markdown-it` token 数组，基于
  `highlight.js`（github-dark 主题）实现逐行语法高亮，顶部固定深色头部展示语言名和复制按钮。
aiSummary: >
  CodeContent 接收 markdown-it 的 fence/code_block token，按行 highlight.js 高亮并带语言标签与复制。
  必填 props 为 token 数组；mounted 事件用于滚动联动等。
  由 MarkdownContent 在解析代码块时挂载，面向流式增量更新。
relatedComponents:
  - slug: markdown-content
    relation: 解析 Markdown 后生成 fence token 并渲染本组件
sinceVersion: 1.0.0
domain: content
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import CodeContent from '../../../src/components/markdown-token/code-content/code-content.vue'

  const tsTokens = [
    {
      type: 'fence',
      tag: 'code',
      info: 'typescript',
      content: `interface User {
  id: number;
  name: string;
  email: string;
}

function greet(user: User): string {
  return \`Hello, \${user.name}!\`;
}

const user: User = { id: 1, name: 'Alice', email: 'alice@example.com' };
console.log(greet(user));`,
    },
  ];

  const pythonTokens = [
    {
      type: 'fence',
      tag: 'code',
      info: 'python',
      content: `from dataclasses import dataclass
from typing import List

@dataclass
class Task:
    title: str
    completed: bool = False

def filter_pending(tasks: List[Task]) -> List[Task]:
    return [t for t in tasks if not t.completed]

tasks = [Task("写文档", True), Task("写测试"), Task("代码审查")]
print(filter_pending(tasks))`,
    },
  ];

  const sqlTokens = [
    {
      type: 'fence',
      tag: 'code',
      info: 'sql',
      content: `SELECT u.name, u.email,
  COUNT(o.id) AS order_count,
  SUM(o.total)  AS total_spent
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at >= '2024-01-01'
GROUP BY u.id, u.name, u.email
HAVING COUNT(o.id) > 0
ORDER BY total_spent DESC
LIMIT 10;`,
    },
  ];

  const unknownTokens = [
    {
      type: 'fence',
      tag: 'code',
      info: 'myDSL',
      content: `RULE "订单折扣"
  WHEN order.amount > 1000
  THEN discount = 0.1
END`,
    },
  ];

  const noLangTokens = [
    {
      type: 'fence',
      tag: 'code',
      info: '',
      content: `plain text block
no language specified
< & > characters are escaped`,
    },
  ];

  // 流式渲染演示
  const streamingTokens = ref([
    {
      type: 'fence',
      tag: 'code',
      info: 'typescript',
      content: '',
    },
  ]);
  const isStreaming = ref(false);

  const simulateStreaming = async () => {
    const code = `import { ref, computed } from 'vue';

export function useCounter(initial = 0) {
  const count = ref(initial);
  const doubled = computed(() => count.value * 2);
  const increment = () => count.value++;
  const decrement = () => count.value--;
  return { count, doubled, increment, decrement };
}`;
    streamingTokens.value = [{ type: 'fence', tag: 'code', info: 'typescript', content: '' }];
    isStreaming.value = true;
    let content = '';
    for (const char of code) {
      await new Promise(r => setTimeout(r, 18));
      content += char;
      streamingTokens.value = [{ type: 'fence', tag: 'code', info: 'typescript', content }];
    }
    isStreaming.value = false;
  };
</script>

# CodeContent 代码块渲染

> **层级**：原子组件 · **功能域**：内容渲染

代码块渲染原子组件，专为 **Markdown 流式输出**设计。接收 `markdown-it` token 数组，基于 `highlight.js`（github-dark 主题）实现逐行语法高亮，顶部固定深色头部展示语言名和复制按钮。

## 组件结构

样式根选择器为 **`.ai-message-container .code-content-wrapper`**：代码块头部与 `pre` 区样式仅在消息容器（如 `MessageContainer` 根上的 `ai-message-container`）下生效。Wiki 与业务中独立演示时，请将 `CodeContent` 包在带 `ai-message-container` 类名的父节点内。

```
.ai-message-container .code-content-wrapper（width: 100%，margin-bottom: 12px）
├── .code-content-header（height: 40px，bg: #2f333d，border: 1px solid #1a1a1a）
│     ├── .code-header-language（color: #999，显示 token.info 原始字符串）
│     ├── slot#header（{ language, token }）— 自定义头部操作按钮区域
│     └── ToolBtn id="copy"（点击复制 codeRef.innerText）
│
└── .hljs-pre（bg: #282c34，padding: 8×16，overflow-x: auto）
      └── <code class="hljs language-{raw-info}">
            ├── v-for completedLines
            │     <span class="code-line" v-html="line.html" /> + '\n'
            │     （已完成行，经过 hljs.highlight 高亮）
            └── v-if currentLineText
                  <span class="code-line current-line" v-html="currentLineHtml" />
                  （最后一行，也经过 highlightLine，用 .current-line 标识正在输入）
```

## 基础用法

`token` 接收 `markdown-it` 解析生成的 token 数组，组件从中提取第一个 `fence` 或 `code_block` token 渲染：

```vue
<template>
  <!-- 完整深色头部与 pre 样式依赖父级 .ai-message-container（与对话消息区一致） -->
  <div class="ai-message-container">
    <CodeContent
      :token="codeTokens"
      @mounted="handleMounted"
    />
  </div>
</template>

<script setup lang="ts">
  import { CodeContent } from '@blueking/chat-x';
  import type { Token } from 'markdown-it';

  const codeTokens: Token[] = [
    {
      type: 'fence',
      tag: 'code',
      info: 'typescript',
      content: 'const greeting = "Hello, World!";\nconsole.log(greeting);',
    },
  ];

  const handleMounted = ({ el }: { el: HTMLElement | null }) => {
    // el 是 <code> 元素的 DOM 引用（通过懒加载 getter 访问）
    console.log('代码块已渲染:', el);
  };
</script>
```

**TypeScript**

<div class="demo">
  <div class="ai-message-container">
    <CodeContent :token="tsTokens" />
  </div>
</div>

**Python**

<div class="demo">
  <div class="ai-message-container">
    <CodeContent :token="pythonTokens" />
  </div>
</div>

**SQL**

<div class="demo">
  <div class="ai-message-container">
    <CodeContent :token="sqlTokens" />
  </div>
</div>

## 流式渲染

组件的核心设计场景。流式输入时，每次 `token[].content` 追加新内容，只更新最后一行，已完成的行通过**内容比较复用缓存**，无需重新高亮：

```
content 变化 → watch(immediate: true, deep: true) → processContent()
  → split('\n')
  → 除最后一行：与 completedLines 对比，内容未变则复用，否则重新 highlightLine
  → 最后一行：highlightLine 并赋值给 currentLineHtml（v-html 渲染）
```

**注意**：当 content 以 `\n` 结尾时，`split('\n')` 末尾为 `''`，`currentLineText = ''`，`.current-line` 元素不渲染（`v-if="currentLineText"`）。

```vue
<script setup lang="ts">
  import { ref } from 'vue';
  import { CodeContent } from '@blueking/chat-x';

  const streamingTokens = ref([{ type: 'fence', tag: 'code', info: 'typescript', content: '' }]);

  async function simulateStream() {
    let content = '';
    for (const char of fullCode) {
      await new Promise(r => setTimeout(r, 20));
      content += char;
      // 每次只更新 content，token 数组引用可保持同一个对象（deep watch）
      streamingTokens.value = [{ type: 'fence', tag: 'code', info: 'typescript', content }];
    }
  }
</script>
```

<div class="demo">
  <div style="display: flex; flex-direction: column; gap: 12px;">
    <button
      style="width: fit-content; padding: 4px 12px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
      :disabled="isStreaming"
      @click="simulateStreaming"
    >
      {{ isStreaming ? '输出中...' : '模拟流式输入' }}
    </button>
    <div class="ai-message-container">
      <CodeContent :token="streamingTokens" />
    </div>
  </div>
</div>

## 语言识别

### 内置别名映射

组件在 `MarkdownLanguageMap` 中维护了 3 个常用别名，`info` 字段使用别名时自动映射：

| `info` 值 | 映射后       | 说明 |
| --------- | ------------ | ---- |
| `js`      | `javascript` | —    |
| `ts`      | `typescript` | —    |
| `py`      | `python`     | —    |

### 解析优先级

```
1. MarkdownLanguageMap[info] → 尝试别名映射
2. hljs.getLanguage(mappedLang) → 检查 hljs 是否支持
3. 提取文件扩展名（如 "index.ts" → "ts"）→ 再次查询 hljs
4. 均不匹配 → resolveLanguage 返回 null → 对内容进行 HTML 转义（非高亮）
```

> **注意**：`code` 元素的 class 使用原始 `token.info`（`language-{info}`），不是解析后的语言名。即 `info: 'js'` → `class="language-js"`，但高亮时用 `javascript`。

### 未知语言（HTML 转义）

当语言无法识别时，内容经过 HTML 转义（`&lt;` `&gt;` `&amp;` `&quot;`）后直接渲染，不进行语法高亮：

<div class="demo">
  <div class="ai-message-container">
    <CodeContent :token="unknownTokens" />
  </div>
</div>

### 无语言标识

`info` 为空字符串时，语言区域留空，内容同样走 HTML 转义路径：

<div class="demo">
  <div class="ai-message-container">
    <CodeContent :token="noLangTokens" />
  </div>
</div>

## 高亮缓存

每行代码的高亮结果缓存在组件实例内部的 `Map<string, string>` 中（key 为 `"${lang}:${lineContent}"`），最大容量 500 条；超限后清除前 250 条（LRU 近似）：

```typescript
const lineHighlightCache = new Map<string, string>();
const MAX_CACHE_SIZE = 500;

// 超限时清理前半部分
if (lineHighlightCache.size > MAX_CACHE_SIZE) {
  const keys = Array.from(lineHighlightCache.keys()).slice(0, MAX_CACHE_SIZE / 2);
  keys.forEach(k => lineHighlightCache.delete(k));
}
```

## API

### Props

| 属性名 | 类型      | 必填 | 说明                                                                     |
| ------ | --------- | ---- | ------------------------------------------------------------------------ |
| token  | `Token[]` | ✓    | markdown-it token 数组；组件提取其中第一个 `fence` 或 `code_block` token |

### Events

| 事件名  | 参数类型                      | 触发时机                                                                          |
| ------- | ----------------------------- | --------------------------------------------------------------------------------- |
| mounted | `{ el: HTMLElement \| null }` | 每次 `token` 变化后 `nextTick` 完成时；`el` 为 `<code>` 元素引用（懒加载 getter） |

### Slots

| 插槽名 | 参数                                   | 说明                                                                                       |
| ------ | -------------------------------------- | ------------------------------------------------------------------------------------------ |
| header | `{ language: string; token: Token[] }` | 代码块头部自定义内容区域，渲染在语言标签和复制按钮之间，可用于添加"插入"、"应用"等操作按钮 |

> **`mounted` 频率**：由于 `watch` 设置了 `immediate: true` 和 `deep: true`，每次 `token` 内容变化（包括初始化）都会触发 `mounted` 事件。

## Token 结构

组件从 token 数组中提取第一个匹配的 token：

```typescript
// 组件接受的 token 格式（只使用这 3 个字段）
interface CodeToken {
  type: 'fence' | 'code_block'; // 触发提取的条件
  info: string; // 语言标识（如 'typescript'），显示在头部
  content: string; // 代码内容（换行符 '\n' 分隔多行）
}
```

完整 Token 类型从 `markdown-it` 包引入：

```typescript
import type { Token } from 'markdown-it';
```

## 样式说明

| 区域                    | 关键样式                                                                             |
| ----------------------- | ------------------------------------------------------------------------------------ |
| `.code-content-header`  | `height: 40px`，`background: #2f333d`，`border: 1px solid #1a1a1a`，圆角仅顶部 `6px` |
| `.code-header-language` | `color: #999`，`font-size: 12px`，`margin-right: auto`（推复制按钮到右侧）           |
| `.hljs-pre`             | `background: #282c34`，`padding: 8px 16px`，`overflow-x: auto`，圆角仅底部 `6px`     |
| `code`                  | `color: #abb2bf`，`font-size: 13px`，`line-height: 1.5`，等宽字体栈                  |
| `.code-line`            | `display: inline`（保持行内流式拼接）                                                |

## 关联组件

- [MarkdownContent](./markdown-content.md) — 解析并传入 code fence token
