---
name: DescPanel 描述面板
slug: desc-panel
category: atomic
description: 工具调用（ToolCall）详情面板的描述区域组件，主要用于 `ToolcallRender` 内部的折叠面板中。
aiSummary: >
  DescPanel 将描述字符串尝试 JSON 解析为键值列表展示，否则按纯文本输出，用于工具调用详情折叠区。
  内部对键与值使用 HighlightKeyword 支持搜索高亮。
relatedComponents:
  - slug: toolcall-render
    relation: 工具调用详情中渲染描述与参数
  - slug: highlight-keyword
    relation: 键值与文本匹配关键词高亮
sinceVersion: 1.0.0
domain: helper
---

<script lang="ts" setup>
  import DescPanel from '../../../src/components/tool-call/desc-panel/desc-panel.vue'
</script>

# DescPanel 描述面板

> **层级**：原子组件 · **功能域**：辅助组件

工具调用（ToolCall）详情面板的描述区域组件，主要用于 `ToolcallRender` 内部的折叠面板中。

将 `desc` 字符串尝试解析为 JSON，解析成功且结果为对象/数组时以键值对列表渲染，否则作为纯文本展示。

## 组件结构

```
.toolcall-desc（flex column，gap: 4px，padding: 12px，background: #f5f7fa）
├── .desc-title（font-size: 12px，font-weight: bold，color: #313238，margin-bottom: 6px）
│     └── {{ title }}
└── .desc-panel（flex column，gap: 4px）
      ├── [JSON 对象/数组] v-for 逐项渲染 .desc-panel-item
      │     ├── .desc-label  → "{{ key }}:"
      │     └── .desc-value（overflow hidden，ellipsis，nowrap）
      │           └── v-overflow-tips → hover 时显示完整内容
      │               · value 为对象/数组时，tooltip 显示 JSON.stringify(value)
      │               · value 为原始值时，tooltip 显示原始值
      └── [非 JSON / 解析失败] 直接渲染 {{ data }}（纯文本）
```

## desc 解析规则

`data` 是一个 computed，逻辑如下：

```typescript
const data = computed(() => {
  try {
    return JSON.parse(props.desc || ''); // desc 为 undefined/''/null 时 parse('') 会抛出
  } catch {
    return props.desc; // 解析失败，原样返回字符串
  }
});
```

模板通过 `typeof data === 'object'` 分支渲染：

| desc 值            | JSON.parse 结果 | typeof 结果 | 渲染方式                 |
| ------------------ | --------------- | ----------- | ------------------------ |
| `'{"a":1}'`        | `{ a: 1 }`      | `'object'`  | 键值对列表               |
| `'[1,2,3]'`        | `[1, 2, 3]`     | `'object'`  | 索引键值对（0:、1:、2:） |
| `'{}'`             | `{}`            | `'object'`  | 键值对列表（0 行）       |
| `'"hello"'`        | `"hello"`       | `'string'`  | 纯文本                   |
| `'42'`             | `42`            | `'number'`  | 纯文本                   |
| `'普通文本'`       | 解析抛出        | —           | 纯文本（原始字符串）     |
| `''` / `undefined` | 解析抛出        | —           | 纯文本（空白）           |

> **嵌套对象**：值本身是对象时，`{{ value }}` 渲染为 `[object Object]`，但 `v-overflow-tips` 的 tooltip 会显示 `JSON.stringify(value)` 的完整内容，方便查看原始结构。

## 基础用法：JSON 参数

```vue
<template>
  <DescPanel
    title="工具调用参数"
    desc='{"query": "天气查询", "city": "北京", "unit": "celsius"}'
  />
</template>

<script setup lang="ts">
  import { DescPanel } from '@blueking/chat-x';
</script>
```

<div class="demo">
  <DescPanel
    title="工具调用参数"
    desc='{"query": "天气查询", "city": "北京", "unit": "celsius"}'
  />
</div>

## 纯文本描述

`desc` 不是合法 JSON 时作为纯文本渲染：

```vue
<template>
  <DescPanel
    title="执行说明"
    desc="正在查询北京的实时天气，请稍候..."
  />
</template>
```

<div class="demo">
  <DescPanel
    title="执行说明"
    desc="正在查询北京的实时天气，请稍候..."
  />
</div>

## JSON 数组

JSON 数组同样被视为 `object`，以数组索引（`0:`、`1:`…）作为键渲染：

```vue
<template>
  <DescPanel
    title="文件列表"
    desc='["report.pdf", "data.csv", "readme.md"]'
  />
</template>
```

<div class="demo">
  <DescPanel
    title="文件列表"
    desc='["report.pdf", "data.csv", "readme.md"]'
  />
</div>

## 嵌套 JSON

嵌套对象的值通过 `v-overflow-tips` 悬停后显示 JSON.stringify 结果，文本区域显示 `[object Object]`：

```vue
<template>
  <DescPanel
    title="API 配置"
    desc='{"endpoint": "/api/search", "headers": {"Authorization": "Bearer xxx", "Content-Type": "application/json"}, "timeout": 5000}'
  />
</template>
```

<div class="demo">
  <DescPanel
    title="API 配置"
    desc='{"endpoint": "/api/search", "headers": {"Authorization": "Bearer xxx", "Content-Type": "application/json"}, "timeout": 5000}'
  />
</div>

## 无 desc

`desc` 为可选，不传时面板仅显示标题，内容区域为空：

<div class="demo">
  <DescPanel title="暂无调用参数" />
</div>

## API

### Props

| 属性名 | 类型     | 必填 | 说明                                                                                |
| ------ | -------- | ---- | ----------------------------------------------------------------------------------- |
| title  | `string` | ✓    | 面板标题，始终渲染在顶部                                                            |
| desc   | `string` | —    | 描述内容；尝试 `JSON.parse`，成功且为 `object` 类型时渲染键值对列表，否则渲染纯文本 |

## 使用场景

`DescPanel` 由 `ToolcallRender` 内部在折叠面板中使用，分别用于渲染工具调用的 **输入参数**（`arguments`）和 **输出结果**（`toolMessage.description`）。通常不需要手动引入，如需独立使用，直接传入 `title` 和 `desc` 即可。

## 关联组件

- [ToolcallRender](../molecular/toolcall-render.md) — 主要使用场景
- [HighlightKeyword](./highlight-keyword.md) — 键值高亮
