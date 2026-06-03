---
name: MessageLoading 品牌加载
slug: message-loading
kind: component
domain: helper
description: 带品牌图标和逐字渐变动画的加载组件。
aiSummary: >
  带品牌图标和逐字渐变动画的加载组件。
  源码位置：src/components/message-loading/message-loading.vue。
relatedComponents:
  - slug: loading-message
    relation: 消息列表加载占位可选择使用品牌加载动效
  - slug: ai-loading
    relation: 更轻量的三点加载动画
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import MessageLoadingComp from '../../../src/components/message-loading/message-loading.vue';
</script>

# MessageLoading 品牌加载

> **能力域**：辅助能力

`MessageLoading` 是带蓝鲸品牌图标和逐字渐变动画的加载组件，用于展示 AI 正在思考、生成或执行任务的等待状态。组件默认显示品牌图标和“加载中...”文案，也支持通过插槽替换图标或文本。

与 [AiLoading](./ai-loading.md) 相比，它更偏品牌化、文案化；适合较明显的等待区域，不适合嵌入很紧凑的按钮或状态点。

## 源码事实

- **源码位置**：`src/components/message-loading/message-loading.vue`
- **能力说明**：带品牌图标和逐字渐变动画的加载组件。

## 核心能力

- **品牌图标动画**：默认使用 `AIBluekingIcon`，图标随 `duration` 做透明度和滤镜动画
- **逐字渐变文本**：未传 `#text` 插槽时，将 `text` 拆成字符逐个渲染，并按 `stagger` 延迟播放
- **可调尺寸和节奏**：通过 `iconSize`、`gap`、`duration`、`stagger` 控制图标尺寸、间距和动画速度
- **插槽覆盖**：`#icon` 可替换图标，`#text` 可替换整段文本渲染
- **无障碍降级**：遵循 `prefers-reduced-motion: reduce`，减少动画效果

## 基础用法

```vue
<template>
  <MessageLoading />
</template>

<script setup lang="ts">
  import { MessageLoading } from '@blueking/chat-x';
</script>
```

**渲染效果**

<div class="demo">
  <MessageLoadingComp />
</div>

## 自定义文案和尺寸

```vue
<template>
  <MessageLoading
    text="正在思考中..."
    :icon-size="28"
    :gap="10"
    :duration="2"
    :stagger="0.12"
  />
</template>
```

<div class="demo">
  <MessageLoadingComp
    text="正在思考中..."
    :icon-size="28"
    :gap="10"
    :duration="2"
    :stagger="0.12"
  />
</div>

## 自定义插槽

传入 `#text` 后，组件不再按字符拆分 `text` prop，而是直接渲染插槽内容；传入 `#icon` 可替换默认品牌图标。

```vue
<template>
  <MessageLoading>
    <template #icon>
      <span class="custom-icon">AI</span>
    </template>
    <template #text>
      正在生成巡检结论
    </template>
  </MessageLoading>
</template>
```

<div class="demo">
  <MessageLoadingComp>
    <template #icon>
      <span style="display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; font-size: 12px; font-weight: 600; color: #3a84ff; border: 1px solid #a3c5fd; border-radius: 50%;">
        AI
      </span>
    </template>
    <template #text>
      正在生成巡检结论
    </template>
  </MessageLoadingComp>
</div>

## API

### Props

| 属性名   | 类型     | 必填 | 默认值      | 说明                               |
| -------- | -------- | ---- | ----------- | ---------------------------------- |
| text     | `string` | 否   | `'加载中...'` | 逐字动画文案；使用 `#text` 时可不传 |
| iconSize | `number` | 否   | `32`        | 默认图标边长，单位 px              |
| gap      | `number` | 否   | `8`         | 图标与文字间距，单位 px            |
| duration | `number` | 否   | `1.8`       | 单次动画循环时长，单位秒           |
| stagger  | `number` | 否   | `0.135`     | 相邻字符动画延迟，单位秒           |

### Emits

- 无。

### Slots

| 插槽名 | 说明                     |
| ------ | ------------------------ |
| icon   | 自定义图标区域           |
| text   | 自定义文本区域，覆盖逐字渲染 |

### Expose

- 无。

## 样式与 attrs

- 组件设置 `inheritAttrs: false`，会将外部 `class` 合并到根节点，并将除 `class` / `style` 外的 attrs 透传到根节点。
- 外部对象形式的 `style` 会与 CSS 变量合并；字符串形式 `style` 不会参与合并。
- 根节点使用 CSS 变量控制动画：`--ai-message-loading-duration`、`--ai-message-loading-stagger`、`--ai-message-loading-gap`。

## 使用建议

- 页面级或消息级等待态优先使用 `MessageLoading`；紧凑状态点优先使用 [AiLoading](./ai-loading.md)。
- 需要自定义文本样式时优先使用 `#text` 插槽，避免只依赖全局覆盖内部 class。

## 关联组件

- [LoadingMessage](../message/loading-message.md) — 消息列表中的加载占位。
- [AiLoading](./ai-loading.md) — 三点加载动画。
