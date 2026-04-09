---
name: ImagePreviewGroup 图片预览组
slug: image-preview-group
category: molecular
description: >-
  多图预览管理容器。通过 `provide/inject` + `Map<symbol>` 模式管理子级 `AiImage`
  的注册与预览状态，点击任意子图片时自动收集所有已注册图片并打开多图预览。
aiSummary: >
  ImagePreviewGroup 通过 provide/inject 与子级 symbol 注册表管理多个 AiImage，点击任一子图时聚合已注册图片并打开内置全屏预览。
  解决同屏多缩略图统一多图浏览与索引切换的需求。
relatedComponents:
  - slug: ai-image
    relation: 子级注册并参与多图预览集合
  - slug: image-preview
    relation: 内置实例承载多图切换与工具栏
sinceVersion: 1.0.0
domain: media
---

<script lang="ts" setup>
  import AiImage from '../../../src/components/image-preview/image.vue'
  import ImagePreviewGroup from '../../../src/components/image-preview/image-preview-group.vue'

  const landscapes = [
    'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&h=300&fit=crop',
  ];

  const detailedImages = [
    {
      src: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop',
      previewProps: {
        src: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1920',
        name: '湖泊风景.jpg',
        width: 1920,
        resolution: '1920×1080',
      },
    },
    {
      src: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=300&fit=crop',
      previewProps: {
        src: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=1920',
        name: '山谷日出.jpg',
        width: 1920,
        resolution: '1920×1280',
      },
    },
    {
      src: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&h=300&fit=crop',
      previewProps: {
        src: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=1920',
        name: '森林小径.jpg',
        width: 1920,
        resolution: '1920×1280',
      },
    },
  ];

  const handleDownload = (url) => {
    console.log('自定义下载:', url);
  };
</script>

# ImagePreviewGroup 图片预览组

> **层级**：分子组件 · **功能域**：文件与图片

多图预览管理容器。通过 `provide/inject` + `Map<symbol>` 模式管理子级 `AiImage` 的注册与预览状态，点击任意子图片时自动收集所有已注册图片并打开多图预览。

## 组件结构

```
.ai-image-preview-group
├── <slot />（放置多个 AiImage）
└── ImagePreview（内置，按需显示）
      v-model:visible="previewVisible"
      v-model:current="activeIndex"
      :images="previewImages"
```

## 工作原理

```
┌─ ImagePreviewGroup ──────────────────────────────────────┐
│  provide(IMAGE_PREVIEW_GROUP_KEY, { register, unregister, preview })  │
│                                                                       │
│  ┌─ AiImage ─┐  ┌─ AiImage ─┐  ┌─ AiImage ─┐                       │
│  │ uid: sym1 │  │ uid: sym2 │  │ uid: sym3 │                        │
│  │ onMounted → register(sym, getItem)                                 │
│  │ onClick  → groupContext.preview(sym)                               │
│  │ onUnmount → unregister(sym)                                        │
│  └────────────┘  └────────────┘  └────────────┘                       │
│                                                                       │
│  preview(uid) → 收集所有 registry 中的 ImageItem →                    │
│                  设置 activeIndex → 打开 ImagePreview                  │
└───────────────────────────────────────────────────────────────────────┘
```

## 基础用法

```vue
<template>
  <ImagePreviewGroup>
    <AiImage
      v-for="(src, i) in images"
      :key="i"
      :src="src"
      :width="160"
      :height="120"
    />
  </ImagePreviewGroup>
</template>

<script setup lang="ts">
  import { AiImage, ImagePreviewGroup } from '@blueking/chat-x';

  const images = [
    'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&h=300&fit=crop',
  ];
</script>
```

<div class="demo" style="display: flex; gap: 8px;">
  <ImagePreviewGroup>
    <AiImage
      v-for="(src, i) in landscapes"
      :key="i"
      :src="src"
      :width="160"
      :height="120"
    />
  </ImagePreviewGroup>
</div>

## 带图片信息

配合 `showInfo` 和 `AiImage` 的 `previewProps`，在预览工具栏显示图片尺寸信息：

```vue
<template>
  <ImagePreviewGroup :show-info="true">
    <AiImage
      v-for="(img, i) in images"
      :key="i"
      :src="img.src"
      :preview-props="img.previewProps"
      :width="160"
      :height="120"
    />
  </ImagePreviewGroup>
</template>

<script setup lang="ts">
  import { AiImage, ImagePreviewGroup, type ImagePreviewConfig } from '@blueking/chat-x';

  const images = [
    {
      src: '...缩略图地址...',
      previewProps: {
        src: '...高清原图地址...',
        name: '湖泊风景.jpg',
        width: 1920,
        resolution: '1920×1080',
      } as ImagePreviewConfig,
    },
    // ...更多图片
  ];
</script>
```

<div class="demo" style="display: flex; gap: 8px;">
  <ImagePreviewGroup :show-info="true">
    <AiImage
      v-for="(img, i) in detailedImages"
      :key="i"
      :src="img.src"
      :preview-props="img.previewProps"
      :width="160"
      :height="120"
    />
  </ImagePreviewGroup>
</div>

## 自定义下载

通过 `onDownload` 统一控制所有子图片的下载行为：

```vue
<template>
  <ImagePreviewGroup :on-download="handleDownload">
    <AiImage
      v-for="(src, i) in images"
      :key="i"
      :src="src"
      :width="160"
      :height="120"
    />
  </ImagePreviewGroup>
</template>

<script setup lang="ts">
  import { AiImage, ImagePreviewGroup } from '@blueking/chat-x';

  const handleDownload = (url: string) => {
    window.open(`/api/download?url=${encodeURIComponent(url)}`);
  };
</script>
```

<div class="demo" style="display: flex; gap: 8px;">
  <ImagePreviewGroup :on-download="handleDownload">
    <AiImage
      v-for="(src, i) in landscapes"
      :key="i"
      :src="src"
      :width="160"
      :height="120"
    />
  </ImagePreviewGroup>
</div>

## API

### Props

| 属性名       | 类型                    | 默认值  | 说明                                          |
| ------------ | ----------------------- | ------- | --------------------------------------------- |
| maskClosable | `boolean`               | `true`  | 点击遮罩层是否关闭预览                        |
| showInfo     | `boolean`               | `false` | 预览工具栏是否显示图片尺寸信息                |
| onDownload   | `(url: string) => void` | —       | 自定义下载回调；不传时使用默认 `<a>` 标签下载 |

### Slots

| 插槽名  | 说明                                            |
| ------- | ----------------------------------------------- |
| default | 放置子级 `AiImage` 组件                         |
| extra   | 预览工具栏的额外操作区域（透传给 ImagePreview） |

## 类型定义

```typescript
interface ImagePreviewGroupContext {
  register: (uid: symbol, getItem: () => ImageItem) => void;
  unregister: (uid: symbol) => void;
  preview: (uid: symbol) => void;
}

const IMAGE_PREVIEW_GROUP_KEY: InjectionKey<ImagePreviewGroupContext>;
```

## 与 AiImage 的协作关系

| AiImage 场景  | 行为                                                                                     |
| ------------- | ---------------------------------------------------------------------------------------- |
| 未在 Group 内 | `inject` 返回 `null`，AiImage 内部自行渲染 `ImagePreview`（独立模式）                    |
| 在 Group 内   | `inject` 获取 Group 上下文；`onMounted` 注册自身；点击时调用 `groupContext.preview(uid)` |

## 使用场景

- AI 对话中一条消息包含多张图片，需要统一预览
- 图片画廊场景
- 任何需要"点击缩略图 → 多图预览切换"的场景

## 关联组件

- [AiImage](../atomic/ai-image.md) — 子级缩略图与注册
- [ImagePreview](./image-preview.md) — 内置全屏预览
