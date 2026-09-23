---
name: HighlightKeyword 关键词高亮
slug: highlight-keyword
kind: component
domain: helper
description: 按传入关键词高亮文本片段。
aiSummary: >
  按 keyword prop 高亮文本片段。
  源码位置：src/components/highlight-keyword/highlight-keyword.ts。
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import HighlightKeywordComp from '../../../src/components/highlight-keyword/highlight-keyword'

  const keyword1 = ref('')
  const demoText1 = 'Vue 3 引入了 Composition API，开发者可以使用 ref、computed 和 watch 等函数来组织代码。'

  const keyword2 = ref('API')
  const demoText2 = 'Composition API 是 Vue 3 的核心特性之一，提供了更灵活的 API 来复用逻辑。'
</script>

# HighlightKeyword 关键词高亮

## 源码事实

- **源码位置**：`src/components/highlight-keyword/highlight-keyword.ts`
- **能力域**：辅助能力
- **能力说明**：按 `keyword` prop 高亮文本片段。

函数式组件，把 `text` 里匹配 `keyword` 的片段包进带高亮样式的 `<span>`。未传或空关键词时原样渲染文本。

## 基础用法

```vue
<template>
  <HighlightKeyword
    :keyword="keyword"
    :text="text"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import { HighlightKeyword } from '@blueking/chat-x';

  const keyword = ref('API');
  const text = '这是一段包含 Vue 3 Composition API 的示例文本';
</script>
```

**渲染效果**（在输入框中输入关键词，观察文本高亮变化）

<div class="demo">
  <div style="margin-bottom: 8px;">
    <input v-model="keyword1" placeholder="输入关键词搜索..." style="padding: 4px 8px; border: 1px solid #dcdee5; border-radius: 4px; width: 200px;" />
  </div>
  <HighlightKeywordComp
    :keyword="keyword1"
    :text="demoText1"
  />
</div>

## 关键词高亮示例

预设关键词为 `API`，文本中所有匹配部分会以高亮背景显示：

<div class="demo">
  <HighlightKeywordComp
    :keyword="keyword2"
    :text="demoText2"
  />
</div>

## API

### Props

| 属性名    | 类型     | 必填 | 说明                         |
| --------- | -------- | ---- | ---------------------------- |
| text      | `string` | ✓    | 待高亮文本                   |
| keyword   | `string` |      | 要高亮的关键词，缺省空字符串 |

### CSS 类名

| 类名                    | 说明                                |
| ----------------------- | ----------------------------------- |
| `.ai-is-keyword` | 匹配文本的高亮样式 |
