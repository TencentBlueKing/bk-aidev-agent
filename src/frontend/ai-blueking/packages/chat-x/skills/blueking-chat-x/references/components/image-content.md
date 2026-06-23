# ImageContent 图片内容

> 能力域：媒体文件 ｜ 导入：`import { ImageContent } from '@blueking/chat-x'` ｜ since 1.0.0

渲染 Markdown 图片 token。 源码位置：src/components/markdown-token/image-content/image-content.vue。

**关联**：markdown-content（解析图片 token 后挂载本组件）

---

# ImageContent 图片渲染
## 源码事实

- **源码位置**：`src/components/markdown-token/image-content/image-content.vue`
- **能力域**：媒体文件
- **能力说明**：渲染 Markdown 图片 token。

> **能力域**：媒体文件

Markdown Token 层的图片渲染基础组件，被 `MarkdownContent` 在解析到图片 token 时自动调用，通常无需手动引入。

核心能力：**流式 URL 防闪烁**（debounce 稳定判断 + throttle 预加载）、**全局缓存**（模块级 `Set` 跨实例共享）、**三态渲染**（加载中 / 成功 / 失败）。

## 组件结构

```
span.md-image-wrapper（inline-block，vertical-align: middle）
├── [showLoading] span.md-image-loading（inline-flex，gap: 6px，padding: 4px 8px，bg: #f5f7fa）
│     ├── bkui-vue Loading（spin，mini，primary）
│     └── "图片加载中..."
├── [showError]  span.md-image-error（同上，color: #ea3636，bg: #fee）
│     ├── span.md-image-error-icon  →  ⚠️（font-size: 14px）
│     └── span.md-image-error-text  →  alt || "图片加载失败"
└── [else]       img.md-image（max-width: 100%，height: auto，loading="lazy"）
                   :src="src"  :alt="alt"
```

> **错误文本**：优先显示 `alt`，未传 `alt` 时才显示 "图片加载失败"。

## 状态机

组件内部维护三个 `shallowRef`：`isLoading`、`hasError`、`isUrlStable`，以及两个 computed 控制显示：

```
showLoading 为 true 的条件（按优先级）：
  1. isCached（全局缓存命中）→ false，直接显示图片
  2. !isValidUrl              → true（URL 无效或正在输入中）
  3. isLoading               → true（正在预加载）
  4. !isUrlStable && hasError → true（URL 仍在变化，忽略旧错误）

showError 为 true 的条件（需全部满足）：
  isUrlStable && hasError && !isLoading
```

### URL 有效性（isValidUrl）

```
src 被判定为无效的情况（显示 Loading）：
  · 空字符串 / '#' / '#)'
  · 以 '#' 或 '#)' 结尾（Markdown 语法补全占位符）
  · 无协议且不是相对路径/带图片扩展名的路径
  · https?:// 开头但域名中无 '.' 且不是 localhost

合法 URL 格式：
  · https?://、//          → 协议 URL（域名需含 '.' 或为 localhost）
  · data:、blob:           → Data URL / Blob URL
  · /path 或 ./path       → 绝对/相对路径
  · image.png、a.jpg?v=1  → 带图片扩展名的文件名
```

### 流式防抖与节流

| 机制                        | 参数                      | 作用                                                             |
| --------------------------- | ------------------------- | ---------------------------------------------------------------- |
| `markUrlStable`（debounce） | 500ms                     | URL 停止变化 500ms 后置 `isUrlStable = true`，此后才允许显示错误 |
| `preloadImage`（throttle）  | 100ms，leading + trailing | 限制 `new Image()` 预加载频率，流式输入时不会每个字符都发请求    |

### 全局缓存

`loadedImageCache` 是**模块级 `Set<string>`**，所有 `ImageContent` 实例共享：

- 图片加载成功后 → `loadedImageCache.add(url)`
- 组件初始化时若命中缓存 → `isLoading = false`，`isUrlStable = true`，跳过所有预加载逻辑，直接渲染 `<img>`
- 页面刷新后缓存清空（仅内存缓存）

## 基础用法

```vue
<template>
  <ImageContent
    src="https://picsum.photos/seed/demo/400/200"
    alt="示例图片"
  />
</template>

<script setup lang="ts">
  import { ImageContent } from '@blueking/chat-x';
</script>
```

## 加载失败

URL 稳定后（500ms 无变化）加载失败，显示 `⚠️ + alt文本`（无 alt 时显示"图片加载失败"）：

## Data URL

支持 Base64 / SVG Data URL，不经过 `isValidUrl` 的网络检测，直接进入预加载：

```vue
<template>
  <ImageContent
    src="data:image/svg+xml,..."
    alt="内联 SVG"
  />
</template>
```

## 流式输入防闪烁

流式 Markdown 渲染时 URL 逐字符拼接，组件通过 debounce + throttle 避免频繁请求和闪烁：

```vue
<template>
  <button
    @click="simulateStreaming"
    :disabled="isStreaming"
  >
    {{ isStreaming ? '输入中...' : '模拟流式输入' }}
  </button>
  <ImageContent
    :src="streamingUrl"
    alt="流式图片"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ImageContent } from '@blueking/chat-x';

  const streamingUrl = ref('');
  const isStreaming = ref(false);

  const simulateStreaming = async () => {
    const url = 'https://picsum.photos/seed/chat-x-stream/400/200';
    streamingUrl.value = '';
    isStreaming.value = true;
    for (let i = 0; i <= url.length; i++) {
      await new Promise(r => setTimeout(r, 60));
      streamingUrl.value = url.slice(0, i);
    }
    isStreaming.value = false;
  };
</script>
```

**流式过程中的状态变化**：

```
URL = ''             → isValidUrl=false  → showLoading=true（Loading）
URL = 'https://'    → isValidUrl=false  → showLoading=true（域名不完整）
URL = 'https://p…'  → isValidUrl=false  → showLoading=true（域名无 '.'）
URL = 完整 URL       → isValidUrl=true   → throttle 触发 preloadImage
                                           debounce 500ms → isUrlStable=true
                                           onload → cache → showLoading=false → 显示图片
```

## API

### Props

| 属性名 | 类型     | 必填 | 说明                                                                         |
| ------ | -------- | ---- | ---------------------------------------------------------------------------- |
| src    | `string` | ✓    | 图片 URL，支持 https / http / // / data: / blob: / 相对路径 / 带扩展名文件名 |
| alt    | `string` | —    | 替代文本；加载失败时优先显示此文本，未传时显示"图片加载失败"                 |

## 使用场景

`ImageContent` 由 `MarkdownContent` 在渲染 `image` token 时自动调用，通常不需要手动引入。如需在 Markdown 以外的场景渲染带流式防抖保护的图片，可单独使用。

## 关联组件

- [MarkdownContent](/components/rendering/markdown-content) — 图片 token 渲染入口
