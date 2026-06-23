# HighlightKeyword 关键词高亮

> 能力域：辅助能力 ｜ 导入：`import { HighlightKeyword } from '@blueking/chat-x'` ｜ since 1.0.0

根据注入关键词高亮文本片段。 源码位置：src/components/highlight-keyword/highlight-keyword.ts。

**关联**：toolcall-render（工具调用标题与状态文案高亮）、desc-panel（工具详情键值与描述文本高亮）、execution-summary（执行摘要搜索过滤与列表高亮）

---

# HighlightKeyword 关键词高亮
## 源码事实

- **源码位置**：`src/components/highlight-keyword/highlight-keyword.ts`
- **能力域**：辅助能力
- **能力说明**：根据注入关键词高亮文本片段。

> **能力域**：辅助能力

函数式组件，用于在文本中高亮匹配的搜索关键词。通过 `useKeywordInject` 从上层注入关键词，自动将匹配部分包裹在带高亮样式的 `<span>` 中。

主要配合 `ExecutionSummary` 的搜索功能使用，实现搜索结果的视觉高亮。

## 工作原理

```
props.text + inject(keyword)
        │
        ├── keyword 为空 → 直接渲染原文本
        │
        └── keyword 非空
            ├── 正则 split 文本为 parts[]
            ├── parts.length === 1 → 无匹配，渲染原文本
            └── parts.length > 1 → 匹配部分用 <span class="highlight"> 包裹
```

组件使用 `defineComponent` + `h()` 渲染函数实现，不依赖模板。

## 基础用法

```vue
<template>
  <HighlightKeyword :text="text" />
</template>

<script setup lang="ts">
  import { HighlightKeyword } from '@blueking/chat-x';

  const text = '这是一段包含 Vue 3 Composition API 的示例文本';
</script>
```

> **注意**：关键词通过 `useKeywordProvider` / `useKeywordInject`（`provide/inject`）注入，不通过 props 传入。上层需先调用 `useKeywordProvider()` 设置关键词。

**渲染效果**（在输入框中输入关键词，观察文本高亮变化）

## 关键词高亮示例

预设关键词为 `API`，文本中所有匹配部分会以高亮背景显示：

## 与 ExecutionSummary 配合

`ExecutionSummary` 内部通过 `useKeywordProvider` 提供搜索关键词，后代组件中的 `HighlightKeyword` 自动响应：

```
ExecutionSummary
├── useKeywordProvider(keyword)  ← Input 绑定
└── MessageRender
    └── AssistantMessage
        └── ToolcallRender
            └── HighlightKeyword(:text)  ← inject(keyword)
```

## 配套 Composables

### useKeywordProvider

在上层组件中创建关键词并 `provide`，后代组件通过 `useKeywordInject` 消费：

```typescript
import { useKeywordProvider } from '@blueking/chat-x';

const { keyword } = useKeywordProvider();
keyword.value = '搜索词';
```

### useKeywordInject

在后代组件中注入关键词，返回 `ComputedRef<string> | undefined`：

```typescript
import { useKeywordInject } from '@blueking/chat-x';

const keyword = useKeywordInject();
console.log(keyword?.value); // 当前搜索关键词
```

### useKeywordMatch

用于判断组件的可搜索文本是否与当前关键词匹配。内部调用 `useKeywordInject` 获取关键词，根据传入的文本提取函数判断是否命中：

```typescript
import { useKeywordMatch } from '@blueking/chat-x';

const { keywordMatched } = useKeywordMatch(() => [props.title, props.description, props.content]);

// keywordMatched.value === true 表示命中搜索
// keywordMatched.value === false 表示未命中（可据此隐藏组件）
// keyword 为空时始终返回 true
```

`useKeywordMatch` 的典型用途是在 `ExecutionSummary` 的搜索过滤中，让组件自行判断是否匹配搜索词，与 `HighlightKeyword` 配合实现搜索 + 高亮。

## API

### Props

| 属性名 | 类型     | 必填 | 说明       |
| ------ | -------- | ---- | ---------- |
| text   | `string` | ✓    | 待高亮文本 |

### 依赖注入

| 注入项  | 提供方               | 说明                   |
| ------- | -------------------- | ---------------------- |
| keyword | `useKeywordProvider` | 搜索关键词，响应式更新 |

### 配套 Composables

| 函数名               | 参数                                            | 返回值                                     | 说明                                          |
| -------------------- | ----------------------------------------------- | ------------------------------------------ | --------------------------------------------- |
| `useKeywordProvider` | —                                               | `{ keyword: ShallowRef<string> }`          | 创建并 `provide` 关键词，用于上层组件         |
| `useKeywordInject`   | —                                               | `ComputedRef<string> \| undefined`         | 注入关键词，用于后代组件                      |
| `useKeywordMatch`    | `getSearchTexts: () => (string \| undefined)[]` | `{ keywordMatched: ComputedRef<boolean> }` | 判断组件文本是否匹配关键词，空关键词返回 true |

### CSS 类名

| 类名                    | 说明                                |
| ----------------------- | ----------------------------------- |
| `.ai-highlight-keyword` | 匹配文本的高亮样式（背景色 + 圆角） |

## 关联组件

- [ToolcallRender](/components/agent/toolcall-render) — 工具调用头部高亮
- [DescPanel](/components/rendering/desc-panel) — 详情面板键值高亮
- [ExecutionSummary](/components/agent/execution-summary) — 执行摘要搜索
