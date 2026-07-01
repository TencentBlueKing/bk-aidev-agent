---
name: ScrollBtn 滚动按钮
slug: scroll-btn
kind: component
domain: feedback
description: 停止生成或返回底部等滚动/状态按钮。
aiSummary: >
  停止生成或返回底部等滚动/状态按钮。
  源码位置：src/components/ai-buttons/scroll-btn/scroll-btn.vue。
relatedComponents:
  - slug: message-container
    relation: 消息列表底部固定区挂载滚动与停止按钮
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import ScrollBtn from '../../../src/components/ai-buttons/scroll-btn/scroll-btn.vue'
  import { ArrowDownIcon } from '../../../src/icons/messages'
  import { CloseCircleIcon } from '../../../src/icons/input'

  const handleScrollBottom = () => alert('滚动到底部');
  const handleStopStreaming = () => alert('停止生成');
</script>

# ScrollBtn 滚动按钮
## 源码事实

- **源码位置**：`src/components/ai-buttons/scroll-btn/scroll-btn.vue`
- **能力域**：工具与反馈
- **能力说明**：停止生成或返回底部等滚动/状态按钮。



> **能力域**：工具与反馈

聊天容器底部浮动操作按钮的外壳组件，提供统一的胶囊样式（圆角 26px、高 24px、阴影），内容完全由插槽定制。

由 `MessageContainer` 内部管理"停止生成"和"返回底部"两个按钮的显示逻辑，通常不需要手动引入。

## 组件结构

```
div.ai-scroll-btn（flex，gap: 4px，width: fit-content，min-width: 84px，height: 24px）
  .is-loading / .is-disabled → cursor: not-allowed，opacity: 0.65
  border: 1px solid #dcdee5，border-radius: 26px
  box-shadow: 0 -2px 6px 0 #0000001a
  hover → border: #c4c6cc，box-shadow 加深，cursor: pointer
  │
  ├── Loading（loading=true 时显示旋转加载图标）
  ├── <slot name="icon">（loading=false 时显示，无默认内容）
  │     子图标自动继承 .ai-common-icon 样式：14×14px，font-size: 14px
  │
  └── <slot name="title">（默认内容：{{ title }}，XSS 安全）
        传入 title slot 时完全替换 title prop 的文本
```

> **`loading` / `disabled` prop**：`loading` 为 `true` 时显示旋转加载图标替代 icon slot，且点击无效；`disabled` 为 `true` 时点击同样无效。两者均添加 `not-allowed` 光标和 `0.65` 透明度。
>
> **`@click` 事件**：通过内部 `handleClick` 处理，`loading` 或 `disabled` 时不触发。

## 基础用法：返回底部

```vue
<template>
  <ScrollBtn
    title="返回底部"
    @click="toScrollBottom"
  >
    <template #icon>
      <ArrowDownIcon />
    </template>
  </ScrollBtn>
</template>

<script setup lang="ts">
  import { ScrollBtn } from '@blueking/chat-x';
  import { ArrowDownIcon } from '@blueking/chat-x';

  const toScrollBottom = () => {
    /* 滚动逻辑 */
  };
</script>
```

<div class="demo">
  <ScrollBtn title="返回底部" @click="handleScrollBottom">
    <template #icon>
      <ArrowDownIcon />
    </template>
  </ScrollBtn>
</div>

## 停止生成

```vue
<template>
  <ScrollBtn
    title="停止生成"
    @click="stopStreaming"
  >
    <template #icon>
      <CloseCircleIcon />
    </template>
  </ScrollBtn>
</template>
```

<div class="demo">
  <ScrollBtn title="停止生成" @click="handleStopStreaming">
    <template #icon>
      <CloseCircleIcon />
    </template>
  </ScrollBtn>
</div>

## 仅图标（不传 title）

不传 `title` prop 时，`title` slot 渲染空文本，按钮收缩至 `min-width: 84px`：

<div class="demo" style="display: flex; gap: 12px;">
  <ScrollBtn @click="handleScrollBottom">
    <template #icon>
      <ArrowDownIcon />
    </template>
  </ScrollBtn>
  <ScrollBtn @click="handleStopStreaming">
    <template #icon>
      <CloseCircleIcon />
    </template>
  </ScrollBtn>
</div>

## 自定义 title slot

传入 `#title` 插槽时，完全覆盖 `title` prop 的文本渲染：

```vue
<template>
  <ScrollBtn
    title="此文本被覆盖"
    @click="handleClick"
  >
    <template #icon>
      <ArrowDownIcon />
    </template>
    <template #title>
      <span style="color: #3a84ff; font-weight: 600;">新消息 ↓</span>
    </template>
  </ScrollBtn>
</template>
```

<div class="demo">
  <ScrollBtn title="此文本被覆盖" @click="handleScrollBottom">
    <template #icon>
      <ArrowDownIcon />
    </template>
    <template #title>
      <span style="color: #3a84ff; font-weight: 600;">新消息 ↓</span>
    </template>
  </ScrollBtn>
</div>

## API

### Props

| 属性名   | 类型      | 必填 | 说明                                                                      |
| -------- | --------- | ---- | ------------------------------------------------------------------------- |
| title    | `string`  | —    | 按钮文本；被 `#title` 插槽覆盖时无效；XSS 安全（文本插值）                |
| loading  | `boolean` | —    | 加载状态；为 `true` 时显示旋转 Loading 图标替代 icon slot，点击不触发事件 |
| disabled | `boolean` | —    | 禁用状态；为 `true` 时点击不触发事件                                      |

### Events

| 事件名 | 参数                  | 说明                                             |
| ------ | --------------------- | ------------------------------------------------ |
| click  | `(event: MouseEvent)` | 点击按钮时触发；`loading` 或 `disabled` 时不触发 |

### Slots

| 插槽名 | 说明                                                                      |
| ------ | ------------------------------------------------------------------------- |
| icon   | 图标区域，无默认内容；放置 `@blueking/chat-x` 图标时自动应用 14×14px 样式 |
| title  | 文本区域，默认渲染 `title` prop；传入后**完全替换** prop 文本             |

## 在 MessageContainer 中的使用

`ScrollBtn` 由 `MessageContainer` 内置，根据状态自动控制显隐，无需手动管理：

```html
<!-- 停止生成：仅在流式输出时显示 -->
<ScrollBtn
  v-show="messageStatus === MessageStatus.Streaming"
  :title="t('停止生成')"
  @click="$emit('stopStreaming')"
>
  <template #icon><CloseCircleIcon /></template>
</ScrollBtn>

<!-- 返回底部：距底部超过 100px 且不在底部时显示 -->
<ScrollBtn
  v-show="!isScrollBottom && scrollBottomHeight > 100"
  :title="t('返回底部')"
  @click="toScrollBottom"
>
  <template #icon><ArrowDownIcon /></template>
</ScrollBtn>
```

两个按钮都渲染在 `div.ai-message-fixed-bottom` 容器内，由父布局定位到消息列表底部中央。

## 关联组件

- [MessageContainer](/components/setup/message-container) — 底部固定区集成
