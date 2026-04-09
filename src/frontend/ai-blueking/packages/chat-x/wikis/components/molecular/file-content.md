---
name: FileContent 文件内容展示
slug: file-content
category: molecular
description: >-
  文件列表展示组件，支持图片缩略图预览、点击图片全屏预览（`ImagePreview`）、文档卡片展示（文件名/扩展名/文件大小）、图片加载失败占位和删除操作。
aiSummary: >
  FileContent 展示消息或输入区附件列表：图片显示缩略图并可进入 ImagePreview，文档以卡片展示文件名、类型与大小。
  支持删除、图片加载失败占位及仅有远端文件名的降级展示。
relatedComponents:
  - slug: image-preview
    relation: 点击图片缩略图打开全屏预览
  - slug: user-message
    relation: 用户消息只读展示附件列表
sinceVersion: 1.0.0
domain: media
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import FileContentComp from '../../../src/components/chat-content/file-content/file-content.vue'

  // 文档文件（无 url，走文档卡片模式）
  const docFiles = ref([
    { file: new File(['report content'], 'report.pdf',  { type: 'application/pdf' }) },
    { file: new File(['data content'],   'data.xlsx',   { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }) },
    { file: new File(['readme'],         'README.md',   { type: 'text/markdown' }) },
  ]);

  // 图片文件（有 url → 显示缩略图）
  const imageFiles = ref([
    {
      url: 'https://picsum.photos/seed/cat/200/200',
      filename: 'cat.jpg',
      mimeType: 'image/jpeg',
      file: new File([''], 'cat.jpg', { type: 'image/jpeg' }),
    },
    {
      url: 'https://picsum.photos/seed/dog/200/200',
      filename: 'dog.png',
      mimeType: 'image/png',
      file: new File([''], 'dog.png', { type: 'image/png' }),
    },
  ]);

  // 图片加载失败
  const errorImageFiles = ref([
    {
      url: 'https://invalid-url.example.com/broken.png',
      filename: 'broken.png',
      mimeType: 'image/png',
      file: new File([''], 'broken.png', { type: 'image/png' }),
    },
  ]);

  // 混合文件（图片 + 文档）
  const mixedFiles = ref([
    {
      url: 'https://picsum.photos/seed/abc/200/200',
      filename: 'photo.jpg',
      mimeType: 'image/jpeg',
      file: new File([''], 'photo.jpg', { type: 'image/jpeg' }),
    },
    { file: new File(['content'], 'report.pdf', { type: 'application/pdf' }) },
    { file: new File(['data'],    'data.xlsx',  { type: 'application/vnd.ms-excel' }) },
  ]);

  // 只有 filename（无 File 对象，无法显示文件大小）
  const remoteFiles = ref([
    { filename: 'server-report.pdf', mimeType: 'application/pdf', url: undefined },
    { filename: 'config.json',       mimeType: 'application/json', url: undefined },
  ]);

  const handleDeleteFile = (file) => {
    docFiles.value    = docFiles.value.filter(f => f !== file);
    imageFiles.value  = imageFiles.value.filter(f => f !== file);
    mixedFiles.value  = mixedFiles.value.filter(f => f !== file);
  };
</script>

# FileContent 文件内容展示

> **层级**：分子组件 · **功能域**：文件与图片

文件列表展示组件，支持图片缩略图预览、点击图片全屏预览（`ImagePreview`）、文档卡片展示（文件名/扩展名/文件大小）、图片加载失败占位和删除操作。

## 渲染决策逻辑

每个文件按以下优先级决定渲染方式：

```
file.url 存在？
├── 是 → 图片模式（用 file.url 作为 <img src>，点击可全屏预览）
│        图片加载失败 → 错误占位（粉色背景 + 红色边框 + 灰色图标）
└── 否 → 检查 mimeType 或 file.file?.type
         ├── 以 'image/' 开头 → 图片模式（用 getFilePreviewUrl(file.file) 作为 src，点击可全屏预览）
         └── 其他            → 文档卡片模式（图标 + 文件名 + 扩展名 + 大小）
```

> **注意**：`file.url` 存在时**无论文件 MIME 类型是什么**都会走图片模式。若要将 PDF 等非图片文件显示为文档卡片，确保不设置 `url` 字段（或设为 `undefined`）。

## 基础用法（文档文件）

无 `url` 字段、MIME 类型非 `image/*` 的文件，渲染为文档卡片（文档图标 + 文件名 + 扩展名 + 大小）：

```vue
<template>
  <FileContent
    :files="files"
    @delete-file="handleDeleteFile"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { FileContent, type UploadFile } from '@blueking/chat-x';

  const files = ref<Partial<UploadFile>[]>([
    { file: new File(['content'], 'report.pdf', { type: 'application/pdf' }) },
    { file: new File(['content'], 'data.xlsx', { type: 'application/vnd.ms-excel' }) },
    { file: new File(['readme'], 'README.md', { type: 'text/markdown' }) },
  ]);

  const handleDeleteFile = (file: Partial<UploadFile>) => {
    files.value = files.value.filter(f => f !== file);
  };
</script>
```

**渲染效果**（悬停文件卡片，右上角出现删除按钮）

<div class="demo">
  <FileContentComp :files="docFiles" @delete-file="handleDeleteFile" />
</div>

## 图片文件预览

设置了 `url` 字段时，渲染为 48×48 的图片缩略图（`cursor: zoom-in`）。点击图片可打开全屏预览（内部集成 `ImagePreview` 组件），支持缩放、旋转、下载等操作：

```vue
<script setup lang="ts">
  import { ref } from 'vue';
  import { type UploadFile } from '@blueking/chat-x';

  const imageFiles = ref<Partial<UploadFile>[]>([
    {
      url: 'https://example.com/cat.jpg', // 有 url → 图片模式
      filename: 'cat.jpg',
      mimeType: 'image/jpeg',
      file: new File([''], 'cat.jpg', { type: 'image/jpeg' }),
    },
    {
      url: 'https://example.com/dog.png',
      filename: 'dog.png',
      mimeType: 'image/png',
      file: new File([''], 'dog.png', { type: 'image/png' }),
    },
  ]);
</script>
```

**渲染效果**

<div class="demo">
  <FileContentComp :files="imageFiles" @delete-file="handleDeleteFile" />
</div>

## 图片点击预览

图片模式下点击缩略图会打开全屏预览弹窗。多张图片时支持左右切换。加载失败的图片不会出现在预览列表中：

```vue
<template>
  <FileContent :files="imageFiles" />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { FileContent, type UploadFile } from '@blueking/chat-x';

  const imageFiles = ref<Partial<UploadFile>[]>([
    { url: 'https://example.com/cat.jpg', filename: 'cat.jpg', mimeType: 'image/jpeg' },
    { url: 'https://example.com/dog.png', filename: 'dog.png', mimeType: 'image/png' },
  ]);
</script>
```

<div class="demo">
  <FileContentComp :files="imageFiles" />
</div>

> **预览行为**：组件内部自动维护 `ImagePreview` 实例，无需外部管理预览状态。只有加载成功的图片才会进入预览列表，加载失败的图片被自动过滤。

## 图片加载失败

`<img>` 触发 `onerror` 时，切换为粉色背景 + 红色边框的错误占位：

<div class="demo">
  <FileContentComp :files="errorImageFiles" @delete-file="handleDeleteFile" />
</div>

## 混合文件（图片 + 文档）

同一列表中可同时包含图片和文档文件，横向 flex 布局、换行排列：

```vue
<script setup lang="ts">
  const files = [
    { url: 'https://example.com/photo.jpg', filename: 'photo.jpg', mimeType: 'image/jpeg' },
    { file: new File(['content'], 'report.pdf', { type: 'application/pdf' }) },
    { file: new File(['data'], 'data.xlsx', { type: 'application/vnd.ms-excel' }) },
  ];
</script>
```

**渲染效果**

<div class="demo">
  <FileContentComp :files="mixedFiles" @delete-file="handleDeleteFile" />
</div>

## 只读模式（readonly）

传入 `readonly` 时，隐藏删除按钮，适用于用户消息中展示已发送的文件：

```vue
<FileContent :files="files" :readonly="true" />
```

**渲染效果**（悬停无删除按钮）

<div class="demo">
  <FileContentComp :files="docFiles" :readonly="true" />
</div>

## 仅有 filename（无 File 对象）

从服务端恢复的历史文件没有 `File` 对象时，仍可渲染文档卡片，但**文件大小不显示**，扩展名从 `filename` 或 `mimeType` 推断：

```vue
<script setup lang="ts">
  const remoteFiles = [
    // 无 file 对象，文件大小显示为空
    { filename: 'server-report.pdf', mimeType: 'application/pdf' },
    { filename: 'config.json', mimeType: 'application/json' },
  ];
</script>
```

**渲染效果**（大小区域为空）

<div class="demo">
  <FileContentComp :files="remoteFiles" :readonly="true" />
</div>

## 在 ChatInput 中使用

`FileContent` 由 `ChatInput` 内部自动渲染在文件预览区（`slot#files` 的默认内容），通常不需要手动引入。当 `ChatInput` 收到上传文件时，自动更新 `uploadFiles` 并渲染：

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :on-send-message="handleSendMessage"
    :on-upload="handleUpload"
  />
</template>
```

若需自定义文件展示，通过 `slot#files` 替换默认 `FileContent`：

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :on-upload="handleUpload"
  >
    <template #files="{ files }">
      <!-- 自定义文件列表 UI -->
      <FileContent
        :files="files"
        readonly
      />
    </template>
  </ChatInput>
</template>
```

## API

### Props

| 属性名   | 类型                    | 默认值  | 必填 | 说明                            |
| -------- | ----------------------- | ------- | ---- | ------------------------------- |
| files    | `Partial<UploadFile>[]` | -       | ✅   | 文件列表                        |
| readonly | `boolean`               | `false` | -    | 只读模式，`true` 时隐藏删除按钮 |

### Events

| 事件名     | 参数                          | 触发时机           |
| ---------- | ----------------------------- | ------------------ |
| deleteFile | `(file: Partial<UploadFile>)` | 点击删除按钮时触发 |

## 渲染模式详解

### 图片模式

| 条件                               | 图片 src                         | 点击行为       |
| ---------------------------------- | -------------------------------- | -------------- |
| `file.url` 有值（优先）            | `file.url`                       | 打开全屏预览   |
| MIME 以 `image/` 开头（无 url 时） | `URL.createObjectURL(file.file)` | 打开全屏预览   |
| 图片加载失败                       | 错误占位                         | 不进入预览列表 |

### 文档卡片模式

| 字段     | 取值优先级                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------ |
| 文件名   | `file.filename` → `file.file?.name`                                                                          |
| 扩展名   | 有 `file.file`：取文件名最后一段 `.xxx` 或 MIME 后缀<br>无 `file.file`：取 `filename` 后缀 → `mimeType` 后缀 |
| 文件大小 | 仅当有 `file.file`（`File` 对象）时显示，否则为空                                                            |

## 类型定义

```typescript
import type { UploadFile, BinaryInputContent } from '@blueking/chat-x';

// 上传状态（ChatInput 内部使用，FileContent 不使用此字段）
enum UploadStatus {
  Pending = 'pending', // 上传中
  Success = 'success', // 上传成功
  Error = 'error', // 上传失败
}

// 上传文件（FileContent 的 files 数组中每一项）
type UploadFile = BinaryInputContent & {
  file?: File; // 原始 File 对象，无则文件大小不显示
  status?: UploadStatus; // 上传状态（ChatInput 使用，FileContent 不消费）
};

// 二进制内容基础类型
interface BinaryInputContent {
  type: 'binary';
  url?: string; // 文件访问地址，存在时强制走图片模式
  filename?: string; // 文件名（用于文档卡片）
  mimeType?: string; // MIME 类型（用于图片判断和扩展名推断）
}
```

## 工具函数（内部使用）

```typescript
// 判断是否走图片模式
// ⚠️ file.url 存在时直接返回 true，不判断 MIME 类型
const isImage = (file: Partial<UploadFile>): boolean => {
  if (file.url) return true;
  return isImageFile(file.mimeType || file.file?.type);
};

// 判断 MIME 类型是否为图片
const isImageFile = (mimeType?: string): boolean => {
  if (!mimeType) return false;
  return mimeType.startsWith('image/');
};

// 获取 File 对象的临时预览 URL（无 url 时的图片模式备选）
const getFilePreviewUrl = (file?: File): string => {
  if (!file) return '';
  return URL.createObjectURL(file);
};

// 获取文件扩展名
const getFileExtension = (file?: File): string => {
  if (!file) return '';
  return file.name.split('.').pop() || file.type?.split('/').pop() || '';
};

// 格式化文件大小（需要 File 对象）
const formatFileSize = (file?: File): string => {
  if (!file) return '';
  const size = file.size;
  const units = ['B', 'KB', 'M', 'GB'];
  const index = Math.floor(Math.log2(size || 1) / 10);
  return `${(size / Math.pow(1024, index)).toFixed(2)} ${units[index]}`;
};
```

## 使用场景

- **ChatInput 文件预览区**：上传文件后在编辑器上方展示待发送的文件列表（可删除）
- **用户消息展示**：`UserMessage` 内部以 `readonly` 模式展示已发送的图片和附件
- **历史消息回放**：服务端返回的文件信息（无 `File` 对象）也能正常渲染文档卡片

## 关联组件

- [ImagePreview](./image-preview.md) — 图片全屏预览
- [UserMessage](./user-message.md) — 用户消息内附件展示
