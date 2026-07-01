---
name: AiImage 图片展示
slug: ai-image
kind: component
domain: medias
description: 图片展示组件，组合加载、错误、预览和 extra 插槽。
aiSummary: >
  图片展示组件，组合加载、错误、预览和 extra 插槽。
  源码位置：src/components/image-preview/image.vue。
relatedComponents:
  - slug: image-preview
    relation: 独立模式下内嵌全屏预览，单图预览入口
  - slug: image-preview-group
    relation: 组内注册子图并统一打开多图预览
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import AiImage from '../../../src/components/image-preview/image.vue'
  import ImagePreviewGroup from '../../../src/components/image-preview/image-preview-group.vue'

  const handleLoad = (ev) => {
    console.log('图片加载成功', ev);
  };

  const handleError = (ev) => {
    console.log('图片加载失败', ev);
  };

  const handlePreview = () => {
    console.log('触发预览');
  };

  const handleDownload = (url) => {
    console.log('自定义下载:', url);
  };

  const images = [
    'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=300&fit=crop',
    'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&h=300&fit=crop',
  ];
</script>

# AiImage 图片展示
## 源码事实

- **源码位置**：`src/components/image-preview/image.vue`
- **能力域**：媒体文件
- **能力说明**：图片展示组件，组合加载、错误、预览和 extra 插槽。



> **能力域**：媒体文件

图片展示组件，支持加载状态、加载失败重试、懒加载、点击预览等功能。可独立使用（单图预览），也可配合 `ImagePreviewGroup` 实现多图预览。

## 组件结构

```
.ai-image（display: inline-block，border-radius: 4px）
├── <img>（v-if status !== 'error' && actualSrc，object-fit: cover）
├── .ai-image-error（v-if status === 'error'）
│     └── ImageErrorIcon（24×24，color: #c4c6cc）
├── .ai-image-error-overlay（v-if status === 'error'，hover 时显示）
│     ├── ReloadIcon（16×16）
│     └── <span>"重新加载"</span>
├── <slot />
└── ImagePreview（v-if !groupContext && preview && previewVisible）
      独立模式下的内置全屏预览
```

## 基础用法

```vue
<template>
  <AiImage
    src="https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    alt="风景图"
    @load="handleLoad"
    @error="handleError"
    @preview="handlePreview"
  />
</template>

<script setup lang="ts">
  import { AiImage } from '@blueking/chat-x';

  const handleLoad = (ev: Event) => {
    console.log('图片加载成功', ev);
  };

  const handleError = (ev: Event) => {
    console.log('图片加载失败', ev);
  };

  const handlePreview = () => {
    console.log('触发预览');
  };
</script>
```

<div class="demo">
  <AiImage
    src="https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    alt="风景图"
    @load="handleLoad"
    @error="handleError"
    @preview="handlePreview"
  />
</div>

## 加载失败与重新加载

当图片加载失败时，显示错误占位图标，鼠标悬停后出现"重新加载"遮罩，点击可重新加载（内部通过追加时间戳参数实现缓存破坏）：

```vue
<template>
  <AiImage
    src="https://invalid-url.example.com/not-exist.png"
    :width="200"
    :height="150"
  />
</template>
```

<div class="demo">
  <AiImage
    src="https://invalid-url.example.com/not-exist.png"
    :width="200"
    :height="150"
  />
</div>

## 禁用预览

将 `preview` 设为 `false` 可禁用点击预览功能，此时图片不显示 `zoom-in` 光标：

```vue
<template>
  <AiImage
    src="https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    :preview="false"
  />
</template>
```

<div class="demo">
  <AiImage
    src="https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    :preview="false"
  />
</div>

## 预览属性配置

通过 `previewProps` 可为预览弹窗配置不同的图片源（如高清原图）、名称、尺寸信息等：

```vue
<template>
  <AiImage
    src="https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    :preview-props="{
      src: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=1920',
      name: '森林.jpg',
      width: 1920,
      resolution: '1920×1080',
    }"
    :show-info="true"
  />
</template>
```

<div class="demo">
  <AiImage
    src="https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    :preview-props="{
      src: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=1920',
      name: '森林.jpg',
      width: 1920,
      resolution: '1920×1080',
    }"
    :show-info="true"
  />
</div>

## 多图预览（配合 ImagePreviewGroup）

将多个 `AiImage` 放在 `ImagePreviewGroup` 中，点击任意图片会打开多图预览模式，支持左右切换：

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
      v-for="(src, i) in images"
      :key="i"
      :src="src"
      :width="160"
      :height="120"
    />
  </ImagePreviewGroup>
</div>

## 自定义下载

通过 `onDownload` 自定义下载行为（例如调用后端接口），不传时使用默认的 `<a>` 标签下载：

```vue
<template>
  <AiImage
    src="https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    :on-download="handleDownload"
  />
</template>

<script setup lang="ts">
  import { AiImage } from '@blueking/chat-x';

  const handleDownload = (url: string) => {
    console.log('自定义下载:', url);
  };
</script>
```

<div class="demo">
  <AiImage
    src="https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop"
    :width="200"
    :height="150"
    :on-download="handleDownload"
  />
</div>

## API

### Props

| 属性名       | 类型                    | 默认值  | 说明                                                            |
| ------------ | ----------------------- | ------- | --------------------------------------------------------------- |
| src          | `string`                | —       | **必填**，图片地址                                              |
| alt          | `string`                | `''`    | 图片 alt 属性                                                   |
| width        | `number \| string`      | —       | 容器宽度，数字时单位为 px                                       |
| height       | `number \| string`      | —       | 容器高度，数字时单位为 px                                       |
| lazy         | `boolean`               | `false` | 是否懒加载（IntersectionObserver，rootMargin: 200px）           |
| preview      | `boolean`               | `true`  | 是否启用点击预览；为 `true` 且图片加载成功时显示 `zoom-in` 光标 |
| previewProps | `ImagePreviewConfig`    | —       | 预览弹窗配置（可指定高清源、名称、尺寸等）                      |
| showInfo     | `boolean`               | `false` | 预览工具栏是否显示图片尺寸信息                                  |
| onDownload   | `(url: string) => void` | —       | 自定义下载回调；不传时使用默认 `<a>` 标签下载                   |

### Events

| 事件名  | 参数          | 说明               |
| ------- | ------------- | ------------------ |
| load    | `(ev: Event)` | 图片加载成功时触发 |
| error   | `(ev: Event)` | 图片加载失败时触发 |
| preview | —             | 点击触发预览时触发 |

### Slots

| 插槽名  | 说明                                            |
| ------- | ----------------------------------------------- |
| default | 覆盖在图片上方的自定义内容                      |
| extra   | 预览工具栏的额外操作区域（透传给 ImagePreview） |

### Expose

| 属性名         | 类型           | 说明                             |
| -------------- | -------------- | -------------------------------- |
| previewVisible | `Ref<boolean>` | 当前预览弹窗是否可见（独立模式） |

## 类型定义

```typescript
interface ImagePreviewConfig {
  src?: string;
  name?: string;
  width?: number;
  height?: number;
  resolution?: string;
  downloadUrl?: string;
}
```

## 使用场景

- AI 对话中的图片消息展示
- 需要点击放大查看的缩略图
- 多图浏览场景（配合 `ImagePreviewGroup`）
- 懒加载长列表中的图片

## 关联组件

- [ImagePreview](/components/medias/image-preview) — 独立模式下的全屏预览
- [ImagePreviewGroup](/components/medias/image-preview-group) — 多图注册与预览上下文
