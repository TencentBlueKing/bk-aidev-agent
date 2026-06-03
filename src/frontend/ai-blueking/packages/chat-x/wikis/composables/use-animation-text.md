---
name: useAnimationText
slug: use-animation-text
category: composable
description: 文本淡入动画的组合式函数。将响应式文本按**增量**拆分为独立 chunk，每个新增 chunk 对应一次淡入动画，适用于 AI 流式输出的逐段渐显效果。
aiSummary: >
  useAnimationText 接收 MaybeRef<string> 与可选 AnimationConfig（fadeDuration、easing），返回 chunks 与 animationStyle。
  监听文本变化：前缀追加则增量拆分为新 chunk 并触发动画，否则重置为单 chunk，适合流式输出逐段淡入。
  全局样式已含 ai-markdown-fade-in。AnimationText 组件内部封装同一逻辑。
relatedComponents:
  - slug: animation-text
    relation: 封装 chunks 与样式渲染
  - slug: markdown-content
    relation: 流式 Markdown 文本展示场景可组合使用
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref, watch } from 'vue';

  // 公共动画样式（与 useAnimationText 返回值结构一致）
  const animStyle = {
    animation: 'ai-markdown-fade-in 200ms ease-in-out forwards',
    color: 'inherit',
  };
  const slowAnimStyle = {
    animation: 'ai-markdown-fade-in 600ms ease-out forwards',
    color: 'inherit',
  };

  // 按照 useAnimationText 内部分块逻辑处理 chunks
  function makeChunkWatcher(chunksRef) {
    return (newVal, oldVal) => {
      if (!oldVal || !newVal.startsWith(oldVal)) {
        chunksRef.value = [newVal];
      } else {
        const chunk = newVal.slice(oldVal.length);
        if (chunk) chunksRef.value = [...chunksRef.value, chunk];
      }
    };
  }

  // Demo 1：基础流式演示
  const text1 = ref('');
  const chunks1 = ref([]);
  const isStreaming1 = ref(false);
  watch(text1, makeChunkWatcher(chunks1));

  async function startStream1() {
    if (isStreaming1.value) return;
    isStreaming1.value = true;
    text1.value = '';
    chunks1.value = [];
    const sentence = '这是一段模拟 AI 流式输出的文本内容，每个字符逐步追加，最新的增量片段会触发淡入动画。';
    for (const char of sentence) {
      text1.value += char;
      await new Promise(r => setTimeout(r, 60));
    }
    isStreaming1.value = false;
  }

  // Demo 2：自定义配置演示（fadeDuration=600ms）
  const text2 = ref('');
  const chunks2 = ref([]);
  const isStreaming2 = ref(false);
  watch(text2, makeChunkWatcher(chunks2));

  async function startStream2() {
    if (isStreaming2.value) return;
    isStreaming2.value = true;
    text2.value = '';
    chunks2.value = [];
    const sentence = '自定义 fadeDuration=600ms、easing=ease-out，每个增量片段缓慢淡入。';
    for (const char of sentence) {
      text2.value += char;
      await new Promise(r => setTimeout(r, 60));
    }
    isStreaming2.value = false;
  }

  // Demo 3：重置行为演示
  const text3 = ref('');
  const chunks3 = ref([]);
  const isStreaming3 = ref(false);
  watch(text3, makeChunkWatcher(chunks3));

  async function startStream3() {
    if (isStreaming3.value) return;
    isStreaming3.value = true;
    const messages = [
      '第一条消息：你好！',
      '第二条消息：这是全新内容，text 被完全替换，chunks 会重置为单一片段。',
    ];
    for (const msg of messages) {
      text3.value = '';
      chunks3.value = [];
      await new Promise(r => setTimeout(r, 300));
      for (const char of msg) {
        text3.value += char;
        await new Promise(r => setTimeout(r, 60));
      }
      await new Promise(r => setTimeout(r, 800));
    }
    isStreaming3.value = false;
  }
</script>

# useAnimationText

> **分类**：composable

文本淡入动画的组合式函数。将响应式文本按**增量**拆分为独立 chunk，每个新增 chunk 对应一次淡入动画，适用于 AI 流式输出的逐段渐显效果。

## 工作原理

每当 `text` 发生变化时，composable 通过比较新旧文本决定如何更新 chunks：

| 变化情况                            | 处理方式                  |
| ----------------------------------- | ------------------------- |
| 新文本以旧文本为前缀（追加）        | 将增量部分追加为新 chunk  |
| 新文本与旧文本完全不同（替换/重置） | chunks 重置为 `[newText]` |
| 文本未变化                          | 无操作                    |

每个 chunk 对应一个独立的 DOM 节点，节点加入 DOM 时自动触发 `ai-markdown-fade-in` 淡入动画。

> `@keyframes ai-markdown-fade-in` 已内置于 `@blueking/chat-x` 全局样式，**无需手动定义**。

## 基础用法

将 `Ref<string>` 传入 composable，配合 `v-for` + `:style` 渲染各 chunk。

```vue
<template>
  <div>
    <span
      v-for="(chunk, index) in chunks"
      :key="index"
      :style="animationStyle"
      >{{ chunk }}</span
    >
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { useAnimationText } from '@blueking/chat-x';

  const text = ref('');
  const { chunks, animationStyle } = useAnimationText(text);

  // 模拟流式追加
  async function startStreaming() {
    const fullText = '这是一段模拟 AI 流式输出的文本内容...';
    for (const char of fullText) {
      text.value += char;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  }

  startStreaming();
</script>
```

**渲染效果**

<div class="demo">
  <div style="min-height:48px;line-height:1.8;font-size:14px;">
    <span v-for="(chunk, index) in chunks1" :key="index" :style="animStyle">{{ chunk }}</span>
    <span v-if="!chunks1.length" style="color:#c4c6cc;">点击按钮开始演示...</span>
  </div>
  <button
    style="margin-top:10px;padding:4px 14px;border:1px solid #3a84ff;border-radius:3px;color:#3a84ff;background:#fff;cursor:pointer;"
    :disabled="isStreaming1"
    @click="startStream1"
  >
    {{ isStreaming1 ? '输出中...' : '开始流式输出' }}
  </button>
</div>

## 自定义动画配置

通过 `options` 调整淡入动画的持续时间和缓动函数。

```vue
<script setup lang="ts">
  import { ref } from 'vue';
  import { useAnimationText } from '@blueking/chat-x';

  const text = ref('');
  const { chunks, animationStyle } = useAnimationText(text, {
    fadeDuration: 600, // 淡入持续时间，默认 200ms
    easing: 'ease-out', // CSS 缓动函数，默认 'ease-in-out'
  });
</script>
```

**渲染效果**（fadeDuration=600ms）

<div class="demo">
  <div style="min-height:48px;line-height:1.8;font-size:14px;">
    <span v-for="(chunk, index) in chunks2" :key="index" :style="slowAnimStyle">{{ chunk }}</span>
    <span v-if="!chunks2.length" style="color:#c4c6cc;">点击按钮开始演示...</span>
  </div>
  <button
    style="margin-top:10px;padding:4px 14px;border:1px solid #3a84ff;border-radius:3px;color:#3a84ff;background:#fff;cursor:pointer;"
    :disabled="isStreaming2"
    @click="startStream2"
  >
    {{ isStreaming2 ? '输出中...' : '开始流式输出' }}
  </button>
</div>

## 文本重置行为

当 `text` 被完全替换（新值不以旧值为前缀）时，chunks 会重置为单一片段，之前积累的 chunks 清空。这适用于多轮对话中切换消息的场景。

```vue
<script setup lang="ts">
  import { ref } from 'vue';
  import { useAnimationText } from '@blueking/chat-x';

  const text = ref('');
  const { chunks, animationStyle } = useAnimationText(text);

  async function nextMessage(newContent: string) {
    // 直接替换整个 text，chunks 自动重置
    text.value = '';
    for (const char of newContent) {
      text.value += char;
      await new Promise(r => setTimeout(r, 50));
    }
  }
</script>
```

**渲染效果**（两条消息依次播放，第二条时 chunks 重置）

<div class="demo">
  <div style="min-height:48px;line-height:1.8;font-size:14px;">
    <span v-for="(chunk, index) in chunks3" :key="index" :style="animStyle">{{ chunk }}</span>
    <span v-if="!chunks3.length" style="color:#c4c6cc;">点击按钮开始演示...</span>
  </div>
  <button
    style="margin-top:10px;padding:4px 14px;border:1px solid #3a84ff;border-radius:3px;color:#3a84ff;background:#fff;cursor:pointer;"
    :disabled="isStreaming3"
    @click="startStream3"
  >
    {{ isStreaming3 ? '输出中...' : '播放两条消息' }}
  </button>
</div>

## 使用 AnimationText 组件

如无需定制渲染逻辑，可直接使用封装好的 `AnimationText` 组件，内部已集成 `useAnimationText`：

```vue
<template>
  <AnimationText :text="text" />
</template>

<script setup lang="ts">
  import { AnimationText } from '@blueking/chat-x';
</script>
```

> 详见 [AnimationText 组件文档](/components/rendering/animation-text)。

## API

### 函数签名

```typescript
function useAnimationText(
  text: MaybeRef<string>,
  options?: AnimationConfig,
): {
  chunks: Ref<string[]>;
  animationStyle: ComputedRef<CSSProperties>;
};
```

### 参数

| 参数      | 类型               | 必填 | 说明                                      |
| --------- | ------------------ | ---- | ----------------------------------------- |
| `text`    | `MaybeRef<string>` | 是   | 响应式文本，传入 `Ref<string>` 可追踪变化 |
| `options` | `AnimationConfig`  | 否   | 动画配置                                  |

### AnimationConfig

| 属性           | 类型     | 默认值          | 说明                   |
| -------------- | -------- | --------------- | ---------------------- |
| `fadeDuration` | `number` | `200`           | 淡入动画持续时间（ms） |
| `easing`       | `string` | `'ease-in-out'` | CSS 缓动函数           |

### 返回值

| 属性             | 类型                         | 说明                                       |
| ---------------- | ---------------------------- | ------------------------------------------ |
| `chunks`         | `Ref<string[]>`              | 拆分后的文本片段数组，每个片段对应一次动画 |
| `animationStyle` | `ComputedRef<CSSProperties>` | 所有 chunk 共用的动画样式对象              |

## 类型定义

```typescript
import type { MaybeRef, Ref, ComputedRef, CSSProperties } from 'vue';

interface AnimationConfig {
  fadeDuration?: number;
  easing?: string;
}

function useAnimationText(
  text: MaybeRef<string>,
  options?: AnimationConfig,
): {
  chunks: Ref<string[]>;
  animationStyle: ComputedRef<CSSProperties>;
};
```

## 注意事项

1. **在组件 `setup` 中通过 `watch(text, ...)` 直接监听 Ref**：composable 内部使用 `watch(() => text, ...)` 的 getter 形式，当 `text` 是 `Ref` 时，getter 每次返回同一个 Ref 对象，Vue 判断为"值未变化"，**watch 不会触发**。在自定义 setup 中如需直接响应文本变化，请用 `watch(text, handler)` 而非 `watch(() => text, handler)`。

2. **`animationStyle` 为所有 chunk 共享的同一个对象**：动画效果来自每个 chunk 对应的 DOM 节点被创建时触发，而非样式本身的差异。

3. **内置 CSS 关键帧**：引入 `@blueking/chat-x` 的全局样式后，`@keyframes ai-markdown-fade-in` 自动可用，无需手动定义。

4. **性能**：长时间流式输出会积累大量 chunk 节点，动画完成后（`forwards`）这些节点保持 `opacity: 1`，对性能影响可接受；如有需要可在流式结束后将 `text` 合并为单次赋值以归并 chunk

## 关联组件

- [AnimationText](../components/rendering/animation-text) — 默认封装组件
- [MarkdownContent](../components/rendering/markdown-content) — 富文本流式展示场景。
