---
name: ImagePreview 图片预览
slug: image-preview
category: molecular
description: >-
  全屏图片预览组件，通过 `Teleport` 渲染到 `body`，支持缩放、旋转、拖拽、下载、键盘导航等功能。`images` 支持传入 URL
  字符串、`ImageItem` 对象或 `File` 对象，File 对象会自动通过 `URL.createObjectURL`
  生成预览并在关闭/卸载时回收。通常不直接使用，而是配合 `AiImage`、`ImagePreviewGroup` 或 `FileContent`
  自动触发。
aiSummary: >
  ImagePreview 通过 Teleport 提供全屏图片预览，支持缩放、旋转、拖拽、下载、键盘与多图切换。
  数据源可为 URL 字符串、ImageItem 或 File（自动 ObjectURL 并在关闭时回收）。
  通常由 AiImage、ImagePreviewGroup、FileContent 等触发，业务较少直接单独挂载。
relatedComponents:
  - slug: ai-image
    relation: 独立模式下由 AiImage 打开预览
  - slug: image-preview-group
    relation: 组内容器内持有一个实例做多图切换
  - slug: file-content
    relation: 文件列表点击缩略图触发预览
sinceVersion: 1.0.0
domain: media
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import ImagePreview from '../../../src/components/image-preview/image-preview.vue'

  const visible = ref(false);
  const visibleMulti = ref(false);
  const currentIndex = ref(0);

  const singleImages = [
    'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1920',
  ];

  const multiImages = [
    {
      url: 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1920',
      name: '湖泊风景.jpg',
      width: 1920,
      resolution: '1920×1080',
    },
    {
      url: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=1920',
      name: '山谷日出.jpg',
      width: 1920,
      resolution: '1920×1280',
    },
    {
      url: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=1920',
      name: '森林小径.jpg',
      width: 1920,
      resolution: '1920×1280',
    },
  ];

  const handleDownload = (url) => {
    console.log('自定义下载:', url);
  };

  // File 对象预览示例
  const visibleFile = ref(false);
  const fileImages = [
    new File(['fake-png-data'], 'screenshot.png', { type: 'image/png' }),
    new File(['fake-jpg-data'], 'photo.jpg', { type: 'image/jpeg' }),
  ];
</script>

# ImagePreview 图片预览

> **层级**：分子组件 · **功能域**：文件与图片

全屏图片预览组件，通过 `Teleport` 渲染到 `body`，支持缩放、旋转、拖拽、下载、键盘导航等功能。`images` 支持传入 URL 字符串、`ImageItem` 对象或 `File` 对象，File 对象会自动通过 `URL.createObjectURL` 生成预览并在关闭/卸载时回收。通常不直接使用，而是配合 `AiImage`、`ImagePreviewGroup` 或 `FileContent` 自动触发。

## 组件结构

```
Teleport(to="body")
└── .ai-image-preview（fixed，z-index: 10000，background: rgba(0,0,0,0.6)）
    ├── .ai-image-preview-close（右上角关闭按钮）
    ├── .ai-image-preview-arrow-left（左切换箭头，多图时显示）
    ├── .ai-image-preview-arrow-right（右切换箭头，多图时显示）
    ├── .ai-image-preview-body（图片主体区域，支持拖拽/滚轮缩放）
    │   ├── <img>（currentStatus !== 'error' 时）
    │   ├── .ai-image-preview-error（加载失败时）
    │   └── .ai-image-preview-loading（加载中，支持模糊缩略图）
    └── PreviewToolbar（底部工具栏）
        ├── 页码（多图时: 1/3）
        ├── 缩小 / 放大 / 旋转 / 重置 / 下载
        ├── slot#extra（额外操作区域）
        └── 图片信息（showInfo 时显示宽度/分辨率）
```

## 内部子组件

### PreviewToolbar

底部圆角工具栏，包含以下按钮：

| 按钮 | 功能                           | tooltip |
| ---- | ------------------------------ | ------- |
| 缩小 | 按 15% 步进缩小（最小 0.1 倍） | 缩小    |
| 放大 | 按 15% 步进放大（最大 10 倍）  | 放大    |
| 旋转 | 顺时针旋转 90°                 | 旋转    |
| 重置 | 重置缩放/旋转/位移             | 重置    |
| 下载 | 触发下载                       | 下载    |

多图模式下还显示页码（如 "1 / 3"）和分隔线。

### useImageTransform

图片变换 Composable，管理缩放/旋转/平移状态：

- `scale`：缩放比例（0.1 ~ 10，步进 15%）
- `rotate`：旋转角度（每次 +90°，累加不取模）
- `translateX / translateY`：拖拽偏移量
- 支持鼠标滚轮缩放和拖拽平移
- `resetTransform` 重置时跳过过渡动画（`skipTransition`），避免视觉闪烁

### usePreviewKeyboard

键盘导航 Composable：

| 按键  | 功能               |
| ----- | ------------------ |
| `Esc` | 关闭预览           |
| `←`   | 上一张（多图模式） |
| `→`   | 下一张（多图模式） |

预览打开时自动锁定 `body` 滚动（`overflow: hidden`），关闭时恢复。

## 基础用法（单图）

```vue
<template>
  <button @click="visible = true">预览图片</button>
  <ImagePreview
    v-model:visible="visible"
    :images="images"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ImagePreview } from '@blueking/chat-x';

  const visible = ref(false);
  const images = ['https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1920'];
</script>
```

<div class="demo">
  <button @click="visible = true" style="padding: 4px 16px; border: 1px solid #3a84ff; border-radius: 4px; background: #3a84ff; color: #fff; cursor: pointer; font-size: 12px; line-height: 24px;">
    预览单张图片
  </button>
  <ImagePreview
    v-model:visible="visible"
    :images="singleImages"
  />
</div>

## 多图预览

传入多张图片时，左右箭头和页码自动显示，支持循环切换：

```vue
<template>
  <button @click="visibleMulti = true">预览多张图片</button>
  <ImagePreview
    v-model:visible="visibleMulti"
    v-model:current="currentIndex"
    :images="images"
    :show-info="true"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ImagePreview, type ImageItem } from '@blueking/chat-x';

  const visibleMulti = ref(false);
  const currentIndex = ref(0);
  const images: ImageItem[] = [
    { url: '...', name: '湖泊风景.jpg', width: 1920, resolution: '1920×1080' },
    { url: '...', name: '山谷日出.jpg', width: 1920, resolution: '1920×1280' },
    { url: '...', name: '森林小径.jpg', width: 1920, resolution: '1920×1280' },
  ];
</script>
```

<div class="demo">
  <button @click="visibleMulti = true" style="padding: 4px 16px; border: 1px solid #3a84ff; border-radius: 4px; background: #3a84ff; color: #fff; cursor: pointer; font-size: 12px; line-height: 24px;">
    预览多张图片（带信息栏）
  </button>
  <ImagePreview
    v-model:visible="visibleMulti"
    v-model:current="currentIndex"
    :images="multiImages"
    :show-info="true"
  />
</div>

## File 对象预览

`images` 数组中可直接传入 `File` 对象，组件会自动通过 `URL.createObjectURL` 生成预览 URL，并在预览关闭或组件卸载时自动调用 `URL.revokeObjectURL` 释放内存：

```vue
<template>
  <button @click="visibleFile = true">预览 File 对象</button>
  <ImagePreview
    v-model:visible="visibleFile"
    :images="fileImages"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ImagePreview } from '@blueking/chat-x';

  const visibleFile = ref(false);
  const fileImages = [
    new File(['png-data'], 'screenshot.png', { type: 'image/png' }),
    new File(['jpg-data'], 'photo.jpg', { type: 'image/jpeg' }),
  ];
</script>
```

<div class="demo">
  <button @click="visibleFile = true" style="padding: 4px 16px; border: 1px solid #3a84ff; border-radius: 4px; background: #3a84ff; color: #fff; cursor: pointer; font-size: 12px; line-height: 24px;">
    预览 File 对象
  </button>
  <ImagePreview
    v-model:visible="visibleFile"
    :images="fileImages"
  />
</div>

> **ObjectURL 生命周期管理**：组件内部维护 `objectUrls` 数组，在以下时机自动回收：
>
> - `normalizedImages` 计算属性重算时（会先 `revokeObjectUrls`，再按当前 `images` 与 `visible` 生成新列表）
> - **`visible` 为 `false` 时**：计算属性直接清空并 `revokeObjectURL`，避免仅依赖 `props.images` 时 computed 仍缓存**已失效**的 blob URL，导致关闭预览后再次打开加载失败
> - 组件 `onBeforeUnmount` 时

## API

### Props

| 属性名       | 类型                              | 默认值  | 说明                                                        |
| ------------ | --------------------------------- | ------- | ----------------------------------------------------------- |
| images       | `(File \| ImageItem \| string)[]` | `[]`    | 图片列表；字符串自动转为 `{ url }`，File 自动转为 ObjectURL |
| maskClosable | `boolean`                         | `true`  | 点击遮罩层是否关闭预览                                      |
| showInfo     | `boolean`                         | `false` | 工具栏是否显示图片尺寸信息（width / resolution）            |
| onDownload   | `(url: string) => void`           | —       | 自定义下载回调；不传时使用默认 `<a>` 标签下载               |

### v-model

| 属性名  | 类型      | 必填 | 说明                    |
| ------- | --------- | ---- | ----------------------- |
| visible | `boolean` | ✅   | 控制预览弹窗的显示/隐藏 |
| current | `number`  | —    | 当前展示的图片索引      |

### Slots

| 插槽名 | 说明                                   |
| ------ | -------------------------------------- |
| extra  | 工具栏额外操作区域，渲染在下载按钮右侧 |

## 类型定义

```typescript
interface ImageItem {
  url: string;
  thumbnailUrl?: string;
  name?: string;
  file?: File;
  width?: number;
  height?: number;
  resolution?: string;
  downloadUrl?: string;
}

type ImageLoadingStatus = 'loading' | 'loaded' | 'error';
```

## 交互说明

| 操作          | 效果                                    |
| ------------- | --------------------------------------- |
| 滚轮向上      | 放大图片（15% 步进）                    |
| 滚轮向下      | 缩小图片（15% 步进）                    |
| 鼠标左键拖拽  | 平移图片                                |
| 点击遮罩      | 关闭预览（`maskClosable` 为 `true` 时） |
| 点击关闭按钮  | 关闭预览                                |
| 左/右箭头按钮 | 切换上/下一张（多图，循环切换）         |
| `Esc` 键      | 关闭预览                                |
| `←` / `→` 键  | 切换上/下一张（多图）                   |

## 使用场景

- 单张或多张图片的全屏预览
- AI 对话中点击图片放大查看（由 `AiImage` 自动触发）
- 文件列表中点击图片缩略图预览（由 `FileContent` 内部集成）
- 用户消息中点击附件图片预览（由 `UserMessage` → `FileContent` 自动触发）
- 需要旋转/缩放/下载操作的图片查看
- 传入 `File` 对象直接预览（无需手动管理 ObjectURL）

## 关联组件

- [AiImage](../atomic/ai-image.md) — 独立模式触发预览
- [ImagePreviewGroup](./image-preview-group.md) — 多图预览容器
- [FileContent](./file-content.md) — 附件列表点击预览
