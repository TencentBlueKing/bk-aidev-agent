# HighlightKeyword 关键词高亮

> 能力域：辅助能力 ｜ 导入：`import { HighlightKeyword } from '@blueking/chat-x'` ｜ since 1.0.0

按 `keyword` prop 高亮文本片段。源码位置：`src/components/highlight-keyword/highlight-keyword.ts`。

```vue
<HighlightKeyword
  :keyword="keyword"
  :text="text"
/>
```

| 属性名  | 类型     | 必填 | 说明                         |
| ------- | -------- | ---- | ---------------------------- |
| text    | `string` | ✓    | 待高亮文本                   |
| keyword | `string` |      | 要高亮的关键词，缺省空字符串 |

匹配片段使用 `.ai-is-keyword`。未传或空关键词时原样渲染 `text`。
