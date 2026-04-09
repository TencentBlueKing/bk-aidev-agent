---
name: FileUploadBtn 文件上传按钮
slug: file-upload-btn
category: atomic
description: >-
  聊天输入框内置的文件上传触发按钮，点击后弹出系统文件选择框。内部包含隐藏的 `<input type="file">`
  与可见的图标按钮，并内置文件数量及大小校验逻辑。
aiSummary: >
  FileUploadBtn 提供隐藏 file input 与图标按钮，选择文件后 emit upload，并内置数量与单文件大小上限校验。
  常用于 ChatInput 工具条；与 FileContent 等展示列表配合形成「选择 → 展示 → 发送」链路。
relatedComponents:
  - slug: chat-input
    relation: 输入区附件上传按钮常见挂载位置
  - slug: file-content
    relation: 选中文件常以列表形式展示待发送内容
sinceVersion: 1.0.0
domain: media
---

<script lang="ts" setup>
  import FileUploadBtn from '../../../src/components/ai-buttons/file-upload-btn/file-upload-btn.vue'

  const handleUpload = (files) => {
    alert(`已选择 ${files.length} 个文件：${files.map(f => f.name).join(', ')}`);
  };
</script>

# FileUploadBtn 文件上传按钮

> **层级**：原子组件 · **功能域**：文件与图片

聊天输入框内置的文件上传触发按钮，点击后弹出系统文件选择框。内部包含隐藏的 `<input type="file">` 与可见的图标按钮，并内置文件数量及大小校验逻辑。

## 组件结构

```
.file-upload-btn（display: flex，align-items: center）
├── input[type="file"]（.file-upload-btn-input，display: none，multiple，:accept）
│     触发后走 handleFileInputChange → 校验 → emit upload → target.value = ''
└── span.ai-shortcut-btn.file-upload-btn-icon（24×24px，color: #979ba5，hover: cursor: pointer）
      v-tippy: "上传图片, 最多支持上传 3 个, 最大支持 2.4MB"（theme: ai-chat-box，offset: [0, 16]，可通过 tippyOptions 扩展）
      @click → fileInputRef.click()
      └── <slot> 默认：FileUploadIcon
```

## 文件校验逻辑

```
用户选择文件
  │
  ├─ files.length > Math.max(maxFiles, MAX_UPLOAD_FILES[3])
  │       ↓ true → bkui-vue Message.error("最多上传 N 个文件")，终止，不 emit
  │
  └─ emit('upload', files.filter(f => f.size > 0 && f.size < MAX_UPLOAD_FILE_SIZE[2.5MB]))
        ↓
      target.value = ''（重置 input，允许再次选择同一文件）
```

**关键边界行为**：

| 场景                                      | 结果                                                        |
| ----------------------------------------- | ----------------------------------------------------------- |
| 文件数超过 `Math.max(maxFiles, 3)`        | 弹出错误 toast，**不触发** `upload`                         |
| 文件数未超限，但部分文件被大小过滤        | **仍触发** `upload`，payload 为过滤后的数组（可能为空数组） |
| `file.size === 0`                         | 被过滤（空文件）                                            |
| `file.size >= 2.5MB`（即 `2621440` 字节） | 被过滤（使用严格小于 `<`，等于 2.5MB 也会被过滤）           |
| `maxFiles` 设为小于 3 的值（如 `1`）      | 实际限制取 `Math.max(1, 3) = 3`，不低于全局下限             |
| 选择后取消                                | `files.length === 0`，不触发 `upload`                       |

> `multiple` prop 声明存在但当前模板中 `input` 的 `multiple` 属性为**硬编码**（非 `:multiple="multiple"` 绑定），始终允许多选，该 prop 暂时无实际效果。

## 基础用法

```vue
<template>
  <FileUploadBtn @upload="handleUpload" />
</template>

<script setup lang="ts">
  import { FileUploadBtn } from '@blueking/chat-x';

  const handleUpload = (files: File[]) => {
    console.log(
      '选中文件:',
      files.map(f => `${f.name}(${f.size}B)`),
    );
  };
</script>
```

<div class="demo">
  <FileUploadBtn @upload="handleUpload" />
</div>

## 限制文件类型

通过 `accept` 属性控制系统文件选择框的过滤条件，遵循 `<input type="file">` 的 `accept` 规范：

```vue
<template>
  <!-- 仅图片（默认） -->
  <FileUploadBtn
    accept="image/*"
    @upload="handleUpload"
  />

  <!-- 文档类型 -->
  <FileUploadBtn
    accept=".pdf,.doc,.docx,.xlsx,.pptx"
    @upload="handleUpload"
  />

  <!-- 不限制类型 -->
  <FileUploadBtn
    accept="*/*"
    @upload="handleUpload"
  />
</template>
```

<div class="demo" style="display: flex; gap: 12px;">
  <FileUploadBtn accept="image/*" @upload="handleUpload" />
  <FileUploadBtn accept=".pdf,.doc,.docx,.xlsx,.pptx" @upload="handleUpload" />
  <FileUploadBtn accept="*/*" @upload="handleUpload" />
</div>

> `accept` 仅影响文件选择框的过滤 UI，不做服务端验证，请在 `upload` 回调中自行校验 MIME 类型。

## 限制上传数量

`maxFiles` 限制单次选择的文件上传上限，实际生效值为 `Math.max(maxFiles, 3)`，不会低于全局下限 3：

```vue
<template>
  <!-- maxFiles=5：可一次选 5 个文件 -->
  <FileUploadBtn
    :max-files="5"
    @upload="handleUpload"
  />

  <!-- maxFiles=1：实际等效 maxFiles=3（取 Math.max(1,3)） -->
  <FileUploadBtn
    :max-files="1"
    @upload="handleUpload"
  />
</template>
```

<div class="demo" style="display: flex; gap: 12px;">
  <FileUploadBtn :max-files="5" @upload="handleUpload" />
  <FileUploadBtn :max-files="1" @upload="handleUpload" />
</div>

## 自定义图标

通过默认插槽替换上传图标：

```vue
<template>
  <FileUploadBtn @upload="handleUpload">
    <span style="font-size: 16px; line-height: 1;">📎</span>
  </FileUploadBtn>
</template>
```

<div class="demo">
  <FileUploadBtn @upload="handleUpload">
    <span style="font-size: 16px; line-height: 1;">📎</span>
  </FileUploadBtn>
</div>

## API

### Props

| 属性名       | 类型           | 默认值      | 说明                                                   |
| ------------ | -------------- | ----------- | ------------------------------------------------------ |
| accept       | `string`       | `'image/*'` | 文件选择框过滤类型，遵循 `<input accept>` 规范         |
| maxFiles     | `number`       | `3`         | 单次选择文件数上限；实际限制为 `Math.max(maxFiles, 3)` |
| multiple     | `boolean`      | `true`      | 声明属性（当前版本未实际绑定到 input，始终多选）       |
| tippyOptions | `AITippyProps` | —           | 扩展 tooltip 配置，会与内置配置合并                    |

### Events

| 事件名 | 参数              | 说明                                                                                      |
| ------ | ----------------- | ----------------------------------------------------------------------------------------- |
| upload | `(files: File[])` | 校验通过后触发；`files` 为过滤掉空文件和超大文件（≥ 2.5MB）后的数组；超出数量限制时不触发 |

### Slots

| 插槽名  | 说明                                            |
| ------- | ----------------------------------------------- |
| default | 自定义按钮图标内容，默认为内置 `FileUploadIcon` |

## 使用场景

`FileUploadBtn` 由 `ChatInput` 组件内置，当 `ChatInput` 的 `supportUpload` prop 为 `true`（默认值）时自动渲染。一般不需要单独引入，除非构建完全自定义的输入区域。

## 类型定义

```typescript
import type { TippyOptions } from 'vue-tippy';

type AITippyProps = Partial<Omit<TippyOptions, 'content' | 'getReferenceClientRect' | 'theme' | 'triggerTarget'>>;
```

## 关联组件

- [ChatInput](../molecular/chat-input.md) — 默认内置上传入口
- [FileContent](../molecular/file-content.md) — 选中文件列表展示
