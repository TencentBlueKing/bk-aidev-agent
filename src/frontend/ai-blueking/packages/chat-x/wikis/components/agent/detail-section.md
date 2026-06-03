---
name: DetailSection 详情分段
slug: detail-section
kind: component
domain: agent
description: FlowAgent 节点详情中的标题/内容分段容器。
aiSummary: >
  FlowAgent 节点详情中的标题/内容分段容器。
  源码位置：src/components/chat-content/flow-agent-content/detail-section.vue。
relatedComponents:
  - slug: flow-agent-node-detail
    relation: 节点详情中用于承载基础信息、输入参数、输出参数等区块
  - slug: simple-table
    relation: 常作为分段内容展示结构化参数表格
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import DetailSectionComp from '../../../src/components/chat-content/flow-agent-content/detail-section.vue';
  import SimpleTableComp from '../../../src/components/chat-content/flow-agent-content/simple-table.vue';

  const infoColumns = [
    { key: 'label', label: '字段' },
    { key: 'value', label: '内容' },
  ];

  const infoData = [
    { label: '流程模板', value: '主机巡检流程' },
    { label: '节点名称', value: '采集主机指标' },
    { label: '步骤名称', value: '巡检准备' },
  ];
</script>

# DetailSection 详情分段

> **能力域**：Agent 能力

`DetailSection` 是 FlowAgent 节点详情页中的轻量分段容器，用于给一组相关信息提供统一标题样式。组件自身只负责渲染标题和默认插槽，不处理数据格式、折叠、空态或表格逻辑。

通常不需要单独接入，主要由 `FlowAgentNodeDetail` 内部组合使用。

## 源码事实

- **源码位置**：`src/components/chat-content/flow-agent-content/detail-section.vue`
- **能力说明**：FlowAgent 节点详情中的标题/内容分段容器。

## 核心能力

- **统一标题样式**：标题前带蓝色竖条，标题文本使用详情页统一字号与字重
- **内容完全透传**：通过默认插槽承载任意内容，如基础信息表单、`SimpleTable` 或自定义说明
- **无内部状态**：不维护折叠、加载、选择等状态，适合作为详情页布局基础块

## 基础用法

```vue
<template>
  <DetailSection title="基础信息">
    <div class="info-row">节点名称：采集主机指标</div>
  </DetailSection>
</template>

<script setup lang="ts">
  import DetailSection from '@blueking/chat-x/src/components/chat-content/flow-agent-content/detail-section.vue';
</script>
```

**渲染效果**

<div class="demo">
  <DetailSectionComp title="基础信息">
    <div style="display: grid; gap: 8px; font-size: 12px; color: #4d4f56;">
      <div>流程模板：主机巡检流程</div>
      <div>节点名称：采集主机指标</div>
      <div>步骤名称：巡检准备</div>
    </div>
  </DetailSectionComp>
</div>

## 搭配 SimpleTable

`DetailSection` 最常见的用法是包裹结构化内容，由外层负责分段标题，内部组件负责数据展示。

```vue
<template>
  <DetailSection title="输入参数">
    <SimpleTable
      :columns="columns"
      :data="data"
    />
  </DetailSection>
</template>
```

<div class="demo">
  <DetailSectionComp title="输入参数">
    <SimpleTableComp
      :columns="infoColumns"
      :data="infoData"
    />
  </DetailSectionComp>
</div>

## API

### Props

| 属性名 | 类型     | 必填 | 默认值 | 说明     |
| ------ | -------- | ---- | ------ | -------- |
| title  | `string` | 是   | —      | 分段标题 |

### Emits

- 无。

### Slots

| 插槽名  | 说明             |
| ------- | ---------------- |
| default | 分段主体展示内容 |

### Expose

- 无。

## 使用建议

- 用于详情页内部的短分段，不建议作为通用卡片或页面 Section 使用。
- 内容空态应由插槽内组件自行处理，`DetailSection` 不会主动显示空态。

## 关联组件

- [FlowAgentNodeDetail](./flow-agent-node-detail.md) — 节点详情主体。
- [SimpleTable](./simple-table.md) — 分段内常用的轻量表格。
