---
name: SelectionFooter 多选操作栏
slug: selection-footer
kind: component
domain: input
description: 消息多选/分享模式下的底部操作栏。
aiSummary: >
  消息多选/分享模式下的底部操作栏。
  源码位置：src/components/selection-footer/selection-footer.vue。
relatedComponents:
  - slug: chat-container
    relation: 多选/分享模式由容器渲染底部栏
  - slug: message-container
    relation: 与消息列表勾选状态联动
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import SelectionFooterComp from '../../../src/components/selection-footer/selection-footer.vue'

  const isAllSelected = ref(false)
  const selectedCount = ref(2)

  const handleToggleAll = (checked) => {
    isAllSelected.value = checked
    selectedCount.value = checked ? 5 : 0
  }
  const handleCancel = () => {
    isAllSelected.value = false
    selectedCount.value = 0
    alert('取消选择')
  }
  const handleConfirm = () => {
    alert(`确认选择 ${selectedCount.value} 条消息`)
  }
</script>

# SelectionFooter 选择操作栏
## 源码事实

- **源码位置**：`src/components/selection-footer/selection-footer.vue`
- **能力域**：输入交互
- **能力说明**：消息多选/分享模式下的底部操作栏。



> **能力域**：输入交互

消息多选模式下的底部操作栏，提供全选、取消和确认操作。由 `ChatContainer` 在分享模式下自动渲染，通常不需要单独使用。

## 基础用法

```vue
<template>
  <SelectionFooter
    :is-all-selected="isAllSelected"
    :selected-count="selectedCount"
    :loading="false"
    @toggle-all="handleToggleAll"
    @cancel="handleCancel"
    @confirm="handleConfirm"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { SelectionFooter } from '@blueking/chat-x';

  const isAllSelected = ref(false);
  const selectedCount = ref(0);

  const handleToggleAll = (checked: boolean) => {
    isAllSelected.value = checked;
  };
  const handleCancel = () => {
    console.log('取消');
  };
  const handleConfirm = () => {
    console.log('确认');
  };
</script>
```

**渲染效果**

<div class="demo">
  <SelectionFooterComp
    :is-all-selected="isAllSelected"
    :selected-count="selectedCount"
    @toggle-all="handleToggleAll"
    @cancel="handleCancel"
    @confirm="handleConfirm"
  />
</div>

## API

### Props

| 属性名        | 类型      | 必填 | 默认值  | 说明                          |
| ------------- | --------- | ---- | ------- | ----------------------------- |
| isAllSelected | `boolean` | ✓    | —       | 是否全选                      |
| selectedCount | `number`  | ✓    | —       | 已选数量，为 0 时确认按钮禁用 |
| loading       | `boolean` | —    | `false` | 确认按钮加载状态              |

### Events

| 事件名     | 参数                 | 说明         |
| ---------- | -------------------- | ------------ |
| toggle-all | `(checked: boolean)` | 切换全选状态 |
| cancel     | —                    | 点击取消按钮 |
| confirm    | —                    | 点击确认按钮 |

## 关联组件

- [ChatContainer](/components/setup/chat-container) — 分享模式挂载
- [MessageContainer](/components/setup/message-container) — 多选与消息列表
