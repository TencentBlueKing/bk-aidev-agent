# FileContent 文件内容

> 能力域：媒体文件 ｜ 导入：`import { FileContent } from '@blueking/chat-x'` ｜ since 1.0.0

渲染文件附件，支持图片预览、上传中/失败态和下载事件。 源码位置：src/components/chat-content/file-content/file-content.vue。

**关联**：image-preview（点击图片缩略图打开全屏预览）、user-message（用户消息只读展示附件列表）

---

# FileContent 文件内容展示
## 源码事实

- **源码位置**：`src/components/chat-content/file-content/file-content.vue`
- **能力域**：媒体文件
- **能力说明**：渲染文件附件，支持图片预览、上传中/失败态和下载事件。

> **能力域**：媒体文件

文件列表展示组件，支持图片缩略图预览、点击图片全屏预览（`ImagePreview`）、文件卡片展示（类型图标 / 文件名 / 文件大小）、上传中/失败态、图片加载失败占位和删除操作。

内部由三个子组件承载单项渲染：

| 子组件             | 源码位置                                                            | 职责                                          |
| ------------------ | ------------------------------------------------------------------- | --------------------------------------------- |
| `UploadImageItem`  | `src/components/chat-content/file-content/upload-image-item.vue`  | 图片缩略图、上传中遮罩、失败占位、hover 删除徽标 |
| `UploadFileItem`   | `src/components/chat-content/file-content/upload-file-item.vue`   | 180px 文件卡片（`FileIcon` + 文件名 + 大小 / 失败文案） |
| `UploadSpinner`    | `src/components/chat-content/file-content/upload-spinner.vue`     | 16px 白色环形 loading，文件与图片共用         |

## 渲染决策逻辑

先分组、再渲染。设计稿要求**图片始终排在文件前方**，两类各自成行：

```
splitUploadFiles(files)  // 单次遍历
├── 图片组（.ai-files-content-row.is-images）
│     判定依据：mimeType 或 file.file?.type 以 'image/' 开头
│     src：file.url 优先，否则用本地 File 的 blob URL（按 key 缓存，移除 / 卸载时 revoke）
│     加载失败或 status=error → 错误占位（粉色背景 + 红色边框 + 灰色图标），且不进入预览列表
│     status=pending → 半透明遮罩 + 16px 环形 loading，禁止点击预览
└── 文件组（.ai-files-content-row.is-files）
      文件卡片：类型图标（FileIcon，按文件名解析扩展名）+ 文件名 + 文件大小
      status=pending → 半透明遮罩 + 16px 环形 loading
      status=error → 浅红底 + 红边框，第二行展示「上传失败」
```

> **是否为图片只看 MIME，不看 `url`。** 解除上传类型限制后，任意文件上传成功都会拿到 `url`，若按 `url` 判断会把 PDF / DOC 渲染成破图。因此 `url` 只决定 `<img src>` 从哪里来，不参与图片判定。

## 基础用法（文件卡片）

MIME 类型非 `image/*` 的文件，渲染为固定宽 180px 的文件卡片（类型图标 + 文件名 + 大小）。类型图标与文件产物侧栏共用 `FileIcon` 的扩展名映射，`pdf` / `py` / `docx` 等各有专属图标，未登记的扩展名回退兜底图标：

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

**渲染效果**（悬停文件卡片，底色加深并在右上角出现删除徽标）

## 图片文件预览

MIME 为 `image/*` 时渲染为图片缩略图（`cursor: zoom-in`）。点击图片可打开全屏预览（内部集成 `ImagePreview` 组件），支持缩放、旋转、下载等操作：

```vue
<script setup lang="ts">
  import { ref } from 'vue';
  import { type UploadFile } from '@blueking/chat-x';

  const imageFiles = ref<Partial<UploadFile>[]>([
    {
      url: 'https://example.com/cat.jpg',
      filename: 'cat.jpg',
      mimeType: 'image/jpeg', // 图片判定依据
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

> **预览行为**：组件内部自动维护 `ImagePreview` 实例，无需外部管理预览状态。只有加载成功的图片才会进入预览列表，加载失败与上传中/失败的图片被自动过滤。

## 上传中 / 上传失败

`FileContent` 消费每项的 `status`（`UploadStatus`）。尺寸不变：文件卡片仍是 180×48，图片仍是定高 48、宽 48~120。loading 用共享的 `UploadSpinner`（16px 白环），不要用 `AiLoading`。删除徽标始终叠在遮罩之上。

| status    | 文件卡片 | 图片缩略图 |
| --------- | -------- | ---------- |
| `pending` | `rgba(0,0,0,0.3)` 遮罩 + spinner | 保留预览图 + `rgba(0,0,0,0.5)` 遮罩 + spinner，点击不打开预览 |
| `error`   | 背景 `#fff0f0`、边框 `#ea3636`，第二行「上传失败」 | 与加载失败相同的破图占位（18px `ImageErrorIcon`） |
| `success` / 未设置 | 正常卡片 | 正常缩略图，可预览 |

上传中与上传失败的图片都不会进入 `ImagePreview` 列表。`ChatInput` 在存在 `pending` / `error` 附件时会拦截发送。

## 图片加载失败

`<img>` 触发 `onerror` 时，切换为粉色背景 + 红色边框的错误占位（与 `status=error` 同一套 UI）：

## 混合文件（图片 + 文件）

同一列表可同时包含图片和其他文件，组件内部自动把图片排在前一行、文件排在后一行，各行内部横向排列并按需换行：

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

## 只读模式（readonly）

传入 `readonly` 时，隐藏删除按钮，适用于用户消息中展示已发送的文件：

```vue
<FileContent :files="files" :readonly="true" />
```

**渲染效果**（悬停无删除按钮）

## 仅有 filename（无 File 对象）

从服务端恢复的历史文件没有 `File` 对象时仍可渲染文件卡片，类型图标从 `filename` 推断。文件大小取 `size` 字段；未下发 `size` 时大小节点不渲染：

```vue
<script setup lang="ts">
  const remoteFiles = [
    // 无 file 对象，未带 size，文件大小不渲染
    { filename: 'server-report.pdf', mimeType: 'application/pdf' },
    // 带 size 时正常显示「1.00M」
    { filename: 'config.json', mimeType: 'application/json', size: 1024 * 1024 },
  ];
</script>
```

**渲染效果**（未带 `size` 的项无大小行）

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

| 属性名   | 类型                    | 默认值    | 必填 | 说明                                        |
| -------- | ----------------------- | --------- | ---- | ------------------------------------------- |
| files    | `Partial<UploadFile>[]` | -         | ✅   | 文件列表                                    |
| readonly | `boolean`               | `false`   | -    | 只读模式，`true` 时隐藏删除徽标与 hover 态 |
| variant  | `'input' \| 'message'`  | `'input'` | -    | 展示形态，见下方「展示形态」                |

### 展示形态（variant）

只影响图片缩略图的圆角描边与整体对齐，文件卡片两种形态一致。图片尺寸规则两种形态相同：**定高 48px，宽度按原图比例，并在 48~120px 之间夹取**（竖图不至于过窄，长图不会撑破容器），超出部分由 `object-fit: cover` 裁切。

| variant     | 使用场景           | 图片圆角 / 描边 | 对齐   |
| ----------- | ------------------ | --------------- | ------ |
| `'input'`   | 输入框内待发送态   | 8px / `#f0f1f5` | 左对齐 |
| `'message'` | 用户消息内已发送态 | 4px / `#eaebf0` | 右对齐 |

### Events

| 事件名     | 参数                          | 触发时机           |
| ---------- | ----------------------------- | ------------------ |
| deleteFile | `(file: Partial<UploadFile>)` | 点击删除按钮时触发 |

## 渲染模式详解

### 图片模式

| 条件                | 图片 src                                          | 点击行为       |
| ------------------- | ------------------------------------------------- | -------------- |
| `file.url` 有值     | `file.url`                                        | 打开全屏预览   |
| 无 url、有 `File`   | `URL.createObjectURL(file.file)`（按 key 缓存）  | 打开全屏预览   |
| 图片加载失败        | 错误占位                                          | 不进入预览列表 |
| `status` 为 pending / error | 遮罩 loading 或错误占位                    | 不进入预览列表 |

blob URL 按附件 key 缓存，同一文件重复渲染不会重复创建；文件被移除或组件卸载时统一 `revokeObjectURL`。

### 文件卡片模式

| 字段     | 取值优先级                                    |
| -------- | --------------------------------------------- |
| 文件名   | `file.filename` → `file.file?.name`           |
| 类型图标 | 由文件名解析扩展名，交给 `FileIcon` 映射      |
| 文件大小 | `file.file?.size` → `file.size`；都没有则不渲染 |

## 类型定义

```typescript
import type { UploadFile, BinaryInputContent } from '@blueking/chat-x';

// 上传状态：ChatInput 写入，FileContent 消费以渲染 pending / error
enum UploadStatus {
  Pending = 'pending', // 上传中
  Success = 'success', // 上传成功
  Error = 'error', // 上传失败
}

// 上传文件（FileContent 的 files 数组中每一项）
type UploadFile = BinaryInputContent & {
  file?: File; // 原始 File 对象，无则文件大小不显示
  status?: UploadStatus; // 上传状态（pending 遮罩 loading，error 失败样式）
};

// 二进制内容基础类型
interface BinaryInputContent {
  type: 'binary';
  url?: string; // 文件访问地址，只决定 <img src> 来源，不参与图片判定
  filename?: string; // 文件名（文件卡片展示 + 类型图标解析）
  mimeType?: string; // MIME 类型（图片判定依据）
  size?: number; // 文件字节数，发送时由原始 File 写入
}
```

## 工具函数（`src/utils/upload-file.ts`）

组件内的取值与分组逻辑都收敛在这里，`ChatInput`、`UserMessage` 共用同一套判定：

```typescript
import {
  getFileIdentity,
  getUploadFileKey,
  getUploadFileName,
  getUploadFileSize,
  isUploadImageFile,
  splitUploadFiles,
} from '@blueking/chat-x';

// File 身份：文件名 + 大小 + 修改时间，用于去重与列表 key
getFileIdentity(file); // 'report.pdf_2048_1700000000000'

// 附件稳定 key：待发送态用 File 身份（上传成功回填 url 后不变），已发送态退回 url / 文件名
getUploadFileKey({ file }); // 'report.pdf_2048_1700000000000'
getUploadFileKey({ url: 'https://x/a.pdf' }); // 'https://x/a.pdf'

// 是否按图片渲染：只看 MIME，有 url 也不例外
isUploadImageFile({ mimeType: 'application/pdf', url: 'https://x/a.pdf' }); // false

// 文件名 / 字节数取值优先级
getUploadFileName({ filename: 'remote.pdf', file }); // 'remote.pdf'
getUploadFileSize({ size: 2048 }); // 2048

// 单次遍历分出图片组与其他文件组（图片在前）
splitUploadFiles(files); // { imageFiles, otherFiles }
```

## 使用场景

- **ChatInput 文件预览区**：上传文件后在编辑器上方展示待发送的文件列表（可删除）
- **用户消息展示**：`UserMessage` 内部以 `readonly` 模式展示已发送的图片和附件
- **历史消息回放**：服务端返回的文件信息（无 `File` 对象）也能正常渲染文档卡片

## 关联组件

- [ImagePreview](/components/medias/image-preview) — 图片全屏预览
- [UserMessage](/components/message/user-message) — 用户消息内附件展示
