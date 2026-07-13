---
name: DescPanel 描述面板
slug: desc-panel
kind: component
domain: rendering
description: 将文本或 JSON 内容降级为可读描述面板。
aiSummary: >
  将文本或 JSON 内容降级为可读描述面板。
  源码位置：src/components/tool-call/desc-panel/desc-panel.vue。
relatedComponents:
  - slug: toolcall-render
    relation: 工具调用详情中渲染描述与参数
  - slug: highlight-keyword
    relation: 键值与文本匹配关键词高亮
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import DescPanel from '../../../src/components/tool-call/desc-panel/desc-panel.vue'
</script>

# DescPanel 描述面板
## 源码事实

- **源码位置**：`src/components/tool-call/desc-panel/desc-panel.vue`
- **能力域**：内容渲染
- **能力说明**：将文本或 JSON 内容降级为可读描述面板。



> **能力域**：内容渲染

工具调用（ToolCall）详情面板的描述区域组件，主要用于 `ToolcallRender` 内部的折叠面板中。

将 `desc` 字符串尝试解析为 JSON，解析成功且结果为对象/数组时以键值对列表渲染，否则作为纯文本展示。

## 组件结构

```
.ai-toolcall-desc（flex column，gap: 4px，padding: 12px，background: #f5f7fa）
├── .desc-title（font-size: 12px，font-weight: bold，color: #313238，margin-bottom: 6px）
│     └── {{ title }}
└── .desc-panel（flex column，gap: 4px）
      ├── [JSON 对象/数组] v-for 逐项渲染 .desc-panel-item
      │     ├── .desc-label  → HighlightKeyword(key)
      │     └── .desc-value → HighlightKeyword(值的文本或 JSON 字符串)，`word-break: break-all`
      └── [非 JSON / 解析失败] HighlightKeyword(data)，`word-break: break-all`
```

> **说明**：键值与纯文本均通过 `HighlightKeyword` 展示，长内容依赖换行与面板宽度展示，**不再**使用 `v-overflow-tips` 悬停气泡。

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

> **嵌套对象**：值本身是对象时，文本区域通过 `JSON.stringify(value)` 展示完整 JSON（`HighlightKeyword` + `word-break: break-all`），不再使用悬停 tooltip。

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

嵌套对象的值在文本区域直接渲染为 `JSON.stringify(value)` 字符串，便于在面板内换行阅读：

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

- [ToolcallRender](/components/agent/toolcall-render) — 主要使用场景
- [HighlightKeyword](/components/helper/highlight-keyword) — 键值高亮
