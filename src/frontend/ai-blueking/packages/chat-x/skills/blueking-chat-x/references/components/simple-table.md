# SimpleTable 简易表格

> 能力域：Agent 能力 ｜ 未从包入口导出：内部组件，请通过上层组件使用 ｜ since 1.0.0

FlowAgent 节点详情中的轻量表格展示组件。 源码位置：src/components/chat-content/flow-agent-content/simple-table.vue。

**关联**：flow-agent-node-detail（节点详情中用于展示输入参数、插件输出定义和结构化输出）、detail-section（通常放在详情分段容器内使用）

---

# SimpleTable 简易表格

> **能力域**：Agent 能力

`SimpleTable` 是 FlowAgent 节点详情中的轻量只读表格，用于展示参数名、参数值、插件输出定义等结构化信息。组件只根据 `columns` 和 `data` 渲染表格，不提供排序、筛选、分页或编辑能力。

通常不需要单独使用，主要由 `FlowAgentNodeDetail` 内部组合。

## 源码事实

- **源码位置**：`src/components/chat-content/flow-agent-content/simple-table.vue`
- **能力说明**：FlowAgent 节点详情中的轻量表格展示组件。

## 核心能力

- **列驱动渲染**：通过 `columns` 决定表头、字段读取 key 和单元格换行策略
- **空值兜底**：单元格值为 `null` 或 `undefined` 时显示 `--`，`0` 会正常显示为 `0`
- **空数据占位**：`data` 为空数组时渲染一行 `--`，`colspan` 等于列数
- **长文本换行**：列配置 `breakAll: true` 后，该列单元格添加 `is-break-all` 样式，适合展示 JSON 或长字符串

## 基础用法

```vue
<template>
  <SimpleTable
    :columns="columns"
    :data="data"
  />
</template>

<script setup lang="ts">
  import SimpleTable from '@blueking/chat-x/src/components/chat-content/flow-agent-content/simple-table.vue';

  const columns = [
    { key: 'key', label: '参数名' },
    { breakAll: true, key: 'value', label: '参数值' },
  ];

  const data = [
    { key: 'bk_host_id', value: '10001' },
    { key: 'metadata', value: '{"source":"cmdb","scope":"production"}' },
  ];
</script>
```

**渲染效果**

## 空数据

当 `data.length === 0` 时，组件渲染一行居中的 `--`，用于表示当前分段没有可展示数据。

## API

### Props

| 属性名  | 类型                     | 必填 | 默认值 | 说明                         |
| ------- | ------------------------ | ---- | ------ | ---------------------------- |
| columns | `SimpleTableColumn[]`    | 是   | —      | 表格列配置                   |
| data    | `Record<string, unknown>[]` | 是 | —      | 表格行数据，按列 `key` 取值 |

### Emits

- 无。

### Slots

- 无。

### Expose

- 无。

## 类型定义

```typescript
export interface SimpleTableColumn {
  breakAll?: boolean; // 是否对该列单元格启用 word-break: break-all
  key: string;        // 从 data 行对象中读取的字段名
  label: string;      // 表头文案
}
```

## 使用建议

- 适合详情面板中的短表格，不适合承载复杂数据表能力。
- 需要展示对象值时，建议在传入前先序列化为字符串；`FlowAgentNodeDetail` 内部会对对象值执行 `JSON.stringify`。

## 关联组件

- [FlowAgentNodeDetail](./flow-agent-node-detail.md) — 节点详情主体。
- [DetailSection](./detail-section.md) — 表格常放置在详情分段内。
