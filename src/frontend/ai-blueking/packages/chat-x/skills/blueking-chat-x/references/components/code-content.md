# CodeContent 代码块

> 能力域：内容渲染 ｜ 导入：`import { CodeContent } from '@blueking/chat-x'` ｜ since 1.0.0

渲染 Markdown 代码块，支持高亮、复制和 header 插槽。 源码位置：src/components/markdown-token/code-content/code-content.vue。

**关联**：markdown-content（解析 Markdown 后生成 fence token 并渲染本组件）

---

# CodeContent 代码块渲染
## 源码事实

- **源码位置**：`src/components/markdown-token/code-content/code-content.vue`
- **能力域**：内容渲染
- **能力说明**：渲染 Markdown 代码块，支持高亮、复制和 header 插槽。

> **能力域**：内容渲染

代码块渲染基础组件，专为 **Markdown 流式输出**设计。接收 `markdown-it` token 数组，基于 `highlight.js`（github-dark 主题）实现逐行语法高亮，顶部固定深色头部展示语言名和复制按钮。

## 组件结构

根类名为 **`.code-content-wrapper`**：外层宽度、下边距以及 **`.code-content-header`**（深色顶栏）在任意父级下均生效。**代码区** `.hljs-pre`、行内高亮等样式选择器为 **`.ai-message-container .code-content-wrapper`**，仅在消息列表（`MessageContainer` 根上的 `ai-message-container`）内与对话区一致。Wiki 与业务中若要完整还原代码区外观，请将 `CodeContent` 包在带 `ai-message-container` 类名的父节点内。

```
.code-content-wrapper
├── .code-content-header（深色顶栏；不依赖 .ai-message-container）
│     ├── .code-header-language（token.info）
│     ├── slot#header（{ language, token }）
│     └── ToolBtn id="copy"
│
└── .hljs-pre（完整 padding / 背景 / code 字体：需父级为 .ai-message-container .code-content-wrapper）
      └── <code class="hljs language-{raw-info}">
            ├── v-for completedLines → <span class="code-line" />
            └── v-if currentLineText → <span class="code-line current-line" />
```

## 基础用法

`token` 接收 `markdown-it` 解析生成的 token 数组，组件从中提取第一个 `fence` 或 `code_block` token 渲染：

```vue
<template>
  <!-- 代码区 .hljs-pre 的完整样式依赖父级 .ai-message-container（与对话消息区一致）；顶栏单独也可用 -->
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

**Python**

**SQL**

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

### 无语言标识

`info` 为空字符串时，语言区域留空，内容同样走 HTML 转义路径：

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

- [MarkdownContent](/components/rendering/markdown-content) — 解析并传入 code fence token
