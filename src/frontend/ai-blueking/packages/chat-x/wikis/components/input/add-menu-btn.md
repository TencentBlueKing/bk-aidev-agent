---
name: AddMenuBtn 添加菜单按钮
slug: add-menu-btn
kind: component
domain: input
description: 输入框左下角的 + 号按钮，唤起聚合菜单，展开态高亮。
aiSummary: >
  AddMenuBtn 是输入框底部工具栏最左侧的 + 号：只负责展示与 toggle 事件，菜单开合由上层控制；
  active 为 true 时保持 hover 底色；mousedown 已 preventDefault，点击不会抢走编辑器焦点。
  源码位置：src/components/ai-buttons/add-menu-btn/add-menu-btn.vue。
relatedComponents:
  - slug: chat-input
    relation: 输入框底部工具栏渲染该按钮并处理 toggle
  - slug: input-menu-panel
    relation: 点击后唤起 plus 触发的聚合菜单
  - slug: file-upload-btn
    relation: 被本按钮取代的旧上传入口
sinceVersion: 0.0.51
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import AddMenuBtnComp from '../../../src/components/ai-buttons/add-menu-btn/add-menu-btn.vue';

  const active = ref(false);
</script>

# AddMenuBtn 添加菜单按钮

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/ai-buttons/add-menu-btn/add-menu-btn.vue`
- **能力说明**：输入框底部工具栏最左侧的 + 号，点击 emit `toggle`，由上层决定唤起或收起聚合菜单。
- **文案**：tooltip 固定为 `t('添加')`，theme 为 `ai-chat-box`，偏移 `[0, 16]`。

## 关键行为

- **不持有菜单状态**：`active` 由上层传入（[ChatInput](/components/input/chat-input) 传 `menuTrigger === 'plus'`），组件自身只做样式切换。
- **不抢焦点**：`@mousedown.prevent` 阻止默认行为，点击时编辑器光标位置保持不变，聚合菜单的关键字锚点才能落在原处。
- **展开态与 hover 同色**：`.is-active` 与 `:hover` 共用 `$color-bg-tab` 语义底色，圆形按钮 32×32。
- **默认插槽**：默认渲染内置 `AddIcon`（该图标从包入口导出，可单独使用）。

::: info 内部组件
本组件不在包入口导出，通常经 [ChatInput](/components/input/chat-input) 使用。以下用法用于说明组件契约。
:::

## 用法

```vue
<template>
  <AddMenuBtn
    :active="isMenuOpen"
    :tippy-options="tippyOptions"
    @toggle="handleToggle"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  const isMenuOpen = ref(false);
  const handleToggle = () => {
    isMenuOpen.value = !isMenuOpen.value;
  };
</script>
```

**渲染效果**（点击切换展开态高亮）

<div class="demo" style="display: flex; gap: 16px; align-items: center;">
  <AddMenuBtnComp
    :active="active"
    @toggle="active = !active"
  />
  <span style="font-size: 12px; color: #979ba5;">active = {{ active }}</span>
</div>

## API

### Props

| 属性名       | 类型            | 默认值      | 必填 | 说明                       |
| ------------ | --------------- | ----------- | ---- | -------------------------- |
| active       | `boolean`       | `undefined` | -    | 聚合菜单是否处于展开态     |
| tippyOptions | `AITippyProps`  | `undefined` | -    | tooltip 配置，会与内置配置合并 |

### Emits

| 事件名 | 参数 | 触发时机 |
| ------ | ---- | -------- |
| toggle | `()` | 点击按钮 |

### Slots

| 插槽名  | 说明                       |
| ------- | -------------------------- |
| default | 替换按钮内图标，默认 `AddIcon` |

## 与 FileUploadBtn 的关系

`ChatInput` 内部的上传入口已从 [FileUploadBtn](/components/input/file-upload-btn) 改为 + 号聚合菜单里的「文件」项：

- 上传能力开启（`supportUpload`）时，组件在菜单「添加」分组注入一条内置的 `type: 'file'` 条目，选中后唤起隐藏的原生 `input[type=file]`
- `FileUploadBtn` 组件仍然保留并可独立使用，但不再出现在 `ChatInput` 的默认布局中

## 关联组件

- [ChatInput](/components/input/chat-input) — 按钮的宿主与 `toggle` 处理方
- [InputMenuPanel](/components/input/input-menu-panel) — 被唤起的聚合菜单
- [FileUploadBtn](/components/input/file-upload-btn) — 独立上传按钮
