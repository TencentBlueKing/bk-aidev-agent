---
name: AiLoading AI 加载动画
slug: ai-loading
category: atomic
description: AI 加载动画原子组件。由两层 SVG 叠加构成：外层旋转光环（带渐变弧线）+ 内层脉冲星形图标，两者共用同一套蓝→紫→粉渐变色。
aiSummary: >
  AiLoading 使用纯 CSS/SVG 动画（旋转环与脉冲星形）展示加载中，不依赖 bkui Loading。
  多实例时需用 cloneVNode 等为渐变 id 加前缀避免冲突；支持 stopLoading 暂停动画。
relatedComponents:
  - slug: loading-message
    relation: 列表末尾加载占位
  - slug: reasoning-message
    relation: 推理进行中的加载指示
  - slug: activity-message
    relation: 活动消息加载态指示
sinceVersion: 1.0.0
domain: helper
---

<script lang="ts" setup>
  import { ref } from 'vue';
  import AiLoading from '../../../src/components/ai-loading/ai-loading.vue'

  const isPaused = ref(false);
</script>

# AiLoading AI 加载动画

> **层级**：原子组件 · **功能域**：辅助组件

AI 加载动画原子组件。由两层 SVG 叠加构成：外层旋转光环（带渐变弧线）+ 内层脉冲星形图标，两者共用同一套蓝→紫→粉渐变色。

## 组件结构

```
.ai-loading（inline-flex，position: relative，width/height 由 size prop 控制）
│   CSS 同时定义 width/height: 1em 兜底，inline style 优先
│
├── .ai-loading-ring（position: absolute，svg 100%×100%）
│     旋转弧线：ai-loading-rotate 0.8s linear infinite
│     渐变：#235DFA → #8A77EC → #EB8CEC（蓝 → 紫 → 粉）
│
└── .ai-loading-star（position: absolute，svg 100%×100%）
      脉冲星形：ai-loading-pulse 0.8s ease-in-out infinite
      关键帧：scale(0.5) → scale(1) → scale(0.5)（小→大→小）
      渐变：同上

stopLoading=true → 根元素加 .ai-loading-stopped
  → .ai-loading-stopped .ai-loading-ring { animation-play-state: paused }
  → .ai-loading-stopped .ai-loading-star { animation-play-state: paused }
```

## 基础用法

```vue
<template>
  <AiLoading />
</template>

<script setup lang="ts">
  import { AiLoading } from '@blueking/chat-x';
</script>
```

<div class="demo">
  <AiLoading />
</div>

## 自定义尺寸

通过 `size` 属性控制图标大小（单位 px），默认 `16`：

```vue
<template>
  <AiLoading />
  <!-- 16px（默认） -->
  <AiLoading :size="24" />
  <AiLoading :size="32" />
  <AiLoading :size="48" />
</template>
```

<div class="demo">
  <div style="display: flex; align-items: center; gap: 16px;">
    <AiLoading />
    <AiLoading :size="24" />
    <AiLoading :size="32" />
    <AiLoading :size="48" />
  </div>
</div>

## 暂停动画

`stopLoading` 为 `true` 时，组件根元素添加 `.ai-loading-stopped` class，两层动画同时进入 `paused` 状态（不移除元素，仅冻结帧）：

```vue
<template>
  <AiLoading :stop-loading="isPaused" />
  <button @click="isPaused = !isPaused">
    {{ isPaused ? '恢复' : '暂停' }}
  </button>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AiLoading } from '@blueking/chat-x';

  const isPaused = ref(false);
</script>
```

<div class="demo">
  <div style="display: flex; align-items: center; gap: 12px;">
    <AiLoading :stop-loading="isPaused" :size="24" />
    <button
      style="padding: 4px 12px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
      @click="isPaused = !isPaused"
    >
      {{ isPaused ? '恢复' : '暂停' }}
    </button>
  </div>
</div>

## 多实例渐变隔离

每个 `AiLoading` 实例通过**模块级 `uid` 计数器**生成唯一的 SVG 渐变 ID：

```
ai-loading-ring-{instanceId}
ai-loading-star-{instanceId}
```

同一页面挂载多个实例时，渐变互不影响。ring 和 star 的 `instanceId` 始终相同（同一组件内），SVG `<path fill="url(#...)" />` 正确引用各自实例的渐变定义。

<div class="demo">
  <div style="display: flex; gap: 12px;">
    <AiLoading :size="28" />
    <AiLoading :size="28" :stop-loading="true" />
    <AiLoading :size="28" />
  </div>
</div>

## 动画规格

| 层                 | 动画名              | 时长 | 缓动        | 关键帧                                  |
| ------------------ | ------------------- | ---- | ----------- | --------------------------------------- |
| `.ai-loading-ring` | `ai-loading-rotate` | 0.8s | linear      | `0deg → 360deg` 匀速旋转                |
| `.ai-loading-star` | `ai-loading-pulse`  | 0.8s | ease-in-out | `0%/100%: scale(0.5)` → `50%: scale(1)` |

脉冲动画节奏：以**半尺寸**起始 → 膨胀至**全尺寸**（0.4s）→ 收缩回**半尺寸**（0.4s），循环往复。

## API

### Props

| 属性名      | 类型      | 默认值  | 说明                                               |
| ----------- | --------- | ------- | -------------------------------------------------- |
| size        | `number`  | `16`    | 图标尺寸（px），应用为 inline style，覆盖 CSS 默认 |
| stopLoading | `boolean` | `false` | `true` 时两层动画均 `paused`，图标停在当前帧       |

## 使用场景

组件库内部以下场景自动使用 `AiLoading`：

| 使用方             | 触发时机                                       | 固定尺寸  |
| ------------------ | ---------------------------------------------- | --------- |
| `LoadingMessage`   | 等待 AI 首次响应（loading 消息占位）           | 18px      |
| `ReasoningMessage` | `status` 为 `pending`/`streaming` 时（思考中） | 默认 16px |
| `ActivityMessage`  | 活动消息加载状态                               | 默认 16px |

## 关联组件

- [LoadingMessage](../molecular/loading-message.md) — 对话加载消息
- [ReasoningMessage](../molecular/reasoning-message.md) — 推理加载态
- [ActivityMessage](../molecular/activity-message.md) — 活动加载态
