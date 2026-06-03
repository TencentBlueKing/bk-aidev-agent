---
name: AnimationText 动画文本
slug: animation-text
kind: component
domain: rendering
description: 按文本增量播放流式动画。
aiSummary: >
  按文本增量播放流式动画。
  源码位置：src/components/animation-text/animation-text.vue。
relatedComponents:
  - slug: use-animation-text
    relation: 提供 chunk 拆分与 animationStyle 的 composable
  - slug: markdown-content
    relation: 流式 Markdown 中可与渐显策略配合
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref, watch } from 'vue';
  import AnimationText from '../../../src/components/animation-text/animation-text.vue'

  // 流式 demo：直接 watch Ref（不能用 () => ref 形式，否则 Vue 追踪不到）
  const streamText = ref('');
  const streamChunks = ref([]);
  const isStreaming = ref(false);
  const streamAnimStyle = {
    animation: 'ai-markdown-fade-in 200ms ease-in-out forwards',
    color: 'inherit',
  };

  watch(streamText, (newVal, oldVal) => {
    if (!oldVal || !newVal.startsWith(oldVal)) {
      streamChunks.value = [newVal];
    } else {
      const chunk = newVal.slice(oldVal.length);
      if (chunk) streamChunks.value = [...streamChunks.value, chunk];
    }
  });

  const sentence = '这是一段模拟流式输出的文本内容，每隔一段时间追加新的字符。';

  async function startStream() {
    if (isStreaming.value) return;
    isStreaming.value = true;
    streamText.value = '';
    streamChunks.value = [];
    for (const char of sentence) {
      streamText.value += char;
      await new Promise(r => setTimeout(r, 80));
    }
    isStreaming.value = false;
  }
</script>

# AnimationText 动画文本
## 源码事实

- **源码位置**：`src/components/animation-text/animation-text.vue`
- **能力域**：内容渲染
- **能力说明**：按文本增量播放流式动画。



> **能力域**：内容渲染

动画文本基础组件，将文本以**淡入（fade-in）**方式渐显。内部由 `useAnimationText` composable 驱动，核心能力是将增量文本拆分为独立 chunk，每个 chunk 单独触发一次淡入动画，适用于流式文本的逐段渐显效果。

## 组件结构

```
AnimationText
└── <span v-for="chunk in chunks" :style="animationStyle">
       {{ chunk }}
    </span>

animationStyle = {
  animation: `ai-markdown-fade-in {fadeDuration}ms {easing} forwards`,
  color: 'inherit',
}

@keyframes ai-markdown-fade-in {
  0%   { opacity: 0; }
  100% { opacity: 1; }
}
```

> **注意**：`AnimationText` 组件将 `props.text`（字符串原始值）传给 `useAnimationText`，watch 只触发一次（挂载时），**prop 变化后不会触发新动画**。若需响应式流式效果，请直接使用 `useAnimationText` composable，并传入 `Ref<string>`。

## 基础用法

挂载时文本以淡入方式显示，适合一次性展示的短文本动画：

```vue
<template>
  <AnimationText text="这是一段带动画效果的文本" />
</template>

<script setup lang="ts">
  import { AnimationText } from '@blueking/chat-x';
</script>
```

<div class="demo">
  <AnimationText text="这是一段带动画效果的文本" />
</div>

## 流式文本（推荐使用 composable）

对于流式输出场景，需直接使用 `useAnimationText` 并传入响应式 `Ref<string>`：

```vue
<template>
  <span
    v-for="(chunk, index) in streamChunks"
    :key="index"
    :style="streamAnimStyle"
    >{{ chunk }}</span
  >
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';

  const streamText = ref('');
  const streamChunks = ref<string[]>([]);
  const streamAnimStyle = {
    animation: 'ai-markdown-fade-in 200ms ease-in-out forwards',
    color: 'inherit',
  };

  // 直接 watch Ref（Vue 自动追踪 .value 变化）
  // ⚠️ 不能写成 watch(() => streamText, ...)，那样 getter 每次返回同一个 Ref 引用，永远不触发
  watch(streamText, (newVal, oldVal) => {
    if (!oldVal || !newVal.startsWith(oldVal)) {
      streamChunks.value = [newVal]; // 内容替换 → 整体重置
    } else {
      const chunk = newVal.slice(oldVal.length);
      if (chunk) streamChunks.value = [...streamChunks.value, chunk]; // 追加 → 新 chunk 淡入
    }
  });

  // 模拟流式追加
  async function receiveStream() {
    streamText.value = '';
    streamChunks.value = [];
    for (const char of '来自 AI 的流式回复内容...') {
      streamText.value += char;
      await new Promise(r => setTimeout(r, 80));
    }
  }
</script>
```

**效果演示**（点击按钮触发流式输出）

<div class="demo">
  <div style="display: flex; flex-direction: column; gap: 12px;">
    <div style="min-height: 24px; font-size: 14px; color: #313238;">
      <span
        v-for="(chunk, index) in streamChunks"
        :key="index"
        :style="streamAnimStyle"
      >{{ chunk }}</span>
      <span v-if="!streamText && !isStreaming" style="color: #c4c6cc;">（等待输出...）</span>
    </div>
    <button
      style="width: fit-content; padding: 4px 16px; font-size: 12px; border: 1px solid #dcdee5; border-radius: 4px; cursor: pointer; background: #fff;"
      :disabled="isStreaming"
      @click="startStream"
    >
      {{ isStreaming ? '输出中...' : '开始流式输出' }}
    </button>
  </div>
</div>

## chunk 增量算法

`useAnimationText` 内部通过**前缀检测**将文本变化拆分为增量 chunk：

```
新文本以旧文本为前缀（即纯追加）→ 截取增量部分 → 追加新 chunk（触发新动画）
新文本与旧文本无前缀关系（内容替换）→ 清空所有 chunk → 用完整新文本创建单一 chunk
```

```typescript
// watch 内部逻辑（简化）
if (newText === prevText) return; // 无变化，跳过

if (prevText && newText.startsWith(prevText)) {
  // 追加模式：只有新增部分触发淡入
  const newChunk = newText.slice(prevText.length);
  chunks.value = [...chunks.value, newChunk];
} else {
  // 重置模式：内容替换，整体重新淡入
  chunks.value = [newText];
}
prevText = newText;
```

| 场景            | 示例                                       | 行为                           |
| --------------- | ------------------------------------------ | ------------------------------ |
| 流式追加（SSE） | `"Hello"` → `"Hello Wo"` → `"Hello World"` | 每次增量部分单独淡入           |
| 内容完全替换    | `"旧文本"` → `"新文本"`                    | 清空所有 chunk，新文本整体淡入 |
| 相同内容        | `"文本"` → `"文本"`                        | 不做任何处理，跳过             |

## 自定义动画参数

`useAnimationText` 支持通过第二个参数自定义动画时长和缓动：

```typescript
import { ref } from 'vue';
import { useAnimationText } from '@blueking/chat-x';

const text = ref('');
const { chunks, animationStyle } = useAnimationText(text, {
  fadeDuration: 400, // 动画时长（ms），默认 200
  easing: 'ease-out', // CSS easing，默认 'ease-in-out'
});
```

生成的 `animationStyle`：

```typescript
// animationStyle 是 computed，格式为：
{
  animation: `ai-markdown-fade-in ${fadeDuration}ms ${easing} forwards`,
  color: 'inherit',
}
```

> **关键帧**：`ai-markdown-fade-in` 定义在库的全局样式中，仅做透明度变化（`opacity: 0 → 1`），无位移或缩放。

## API

### AnimationText Props

| 属性名 | 类型     | 必填 | 说明                                            |
| ------ | -------- | ---- | ----------------------------------------------- |
| text   | `string` | ✓    | 要显示的文本；仅挂载时触发动画，prop 更新后无效 |

### useAnimationText

```typescript
function useAnimationText(
  text: MaybeRef<string>, // 字符串或 Ref<string>，传 Ref 才能响应变化
  options?: AnimationConfig,
): {
  chunks: Ref<string[]>; // 分割后的文本块数组，v-for 遍历渲染
  animationStyle: ComputedRef<{
    // 应用到每个 <span> 的 inline style
    animation: string;
    color: 'inherit';
  }>;
};

interface AnimationConfig {
  fadeDuration?: number; // 动画时长（ms），默认 200
  easing?: string; // CSS easing，默认 'ease-in-out'
}
```

## 注意事项

1. **`AnimationText` 不响应 prop 更新**：组件内部传的是字符串原始值，若需动态响应，直接用 `watch(myRef, ...)` 手动实现 chunk 逻辑
2. **流式场景不要使用 `useAnimationText`**：该 composable 内部使用 `watch(() => text, ...)` 的 getter 形式，当传入 `Ref<string>` 时，getter 每次返回同一个 Ref 引用，Vue 无法检测到 `.value` 变化，watch 只触发一次（immediate）。正确做法是直接 `watch(streamText, callback)` 绑定 Ref
3. **动画 keyframe 依赖全局样式**：使用 `@blueking/chat-x` 时会自动引入；独立使用时需确保 `ai-markdown-fade-in` 已定义
4. **chunks 只增不减**（追加模式下）：流式结束后 chunks 保留所有历史分段，若需复用，手动清空 `chunks.value = []` 再重置文本即可

## 关联组件

- [useAnimationText](../../composables/use-animation-text.md) — chunk 与动画样式逻辑
- [MarkdownContent](/components/rendering/markdown-content) — 流式正文渲染时可配合渐显
