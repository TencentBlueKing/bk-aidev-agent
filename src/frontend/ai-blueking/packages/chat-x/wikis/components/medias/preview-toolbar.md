---
name: PreviewToolbar 图片预览工具栏
slug: preview-toolbar
kind: component
domain: medias
description: 图片预览的缩放、旋转、下载等工具按钮。
aiSummary: >
  图片预览的缩放、旋转、下载等工具按钮。
  源码位置：src/components/image-preview/preview-toolbar.vue。
relatedComponents: []
sinceVersion: 1.0.0
exportStatus: internal
---

# PreviewToolbar 图片预览工具栏

> **导出状态**：内部实现，未从 `@blueking/chat-x` 包入口导出。
> 业务请通过 [ImagePreview](/components/medias/image-preview) 使用。
> 文档站 demo 使用相对路径引入源码；不要写 `import { PreviewToolbar } from '@blueking/chat-x'`。

> **能力域**：媒体文件

## 源码事实

- **源码位置**：`src/components/image-preview/preview-toolbar.vue`
- **能力说明**：图片预览的缩放、旋转、下载等工具按钮。

## API 摘要

### Props

- `{ activeIndex: number; currentImageInfo?: null | { resolution?: string; width?: number }; isMultiple: boolean; showInfo: boolean; total: number; }`

### Emits

- `{ (e: 'zoomIn'): void; (e: 'zoomOut'): void; (e: 'rotate'): void; (e: 'reset'): void; (e: 'download'): void; }`

### Slots

- `extra`

### Expose

- 无。

## 组件依赖

- 无组件依赖或仅依赖基础库。

## 使用建议

- 优先通过上层组合组件使用；直接使用前请确认 props 数据结构来自对应类型定义。
