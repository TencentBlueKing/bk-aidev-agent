---
name: FileUploadBtn 文件上传按钮
slug: file-upload-btn
kind: component
domain: input
description: 文件选择按钮，封装 input[type=file] 并输出选择事件。
aiSummary: >
  文件选择按钮，封装 input[type=file] 并输出选择事件。
  源码位置：src/components/ai-buttons/file-upload-btn/file-upload-btn.vue。
relatedComponents:
  - slug: chat-input
    relation: 输入区附件上传按钮常见挂载位置
  - slug: file-content
    relation: 选中文件常以列表形式展示待发送内容
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import FileUploadBtn from '../../../src/components/ai-buttons/file-upload-btn/file-upload-btn.vue'

  const handleUpload = (files) => {
    alert(`已选择 ${files.length} 个文件：${files.map(f => f.name).join(', ')}`);
  };
</script>

# FileUploadBtn 文件上传按钮
## 源码事实

- **源码位置**：`src/components/ai-buttons/file-upload-btn/file-upload-btn.vue`
- **能力域**：输入交互
- **能力说明**：文件选择按钮，封装 input[type=file] 并输出选择事件。



> **能力域**：输入交互

聊天输入框内置的文件上传触发按钮，点击后弹出系统文件选择框。内部包含隐藏的 `<input type="file">` 与可见的图标按钮；在按钮层对**单文件**做大小与空文件过滤，**已选文件个数上限**由上层（如 `ChatInput`）统一校验并提示，避免按钮与输入区各弹一条错误提示。

## 组件结构

```
.ai-file-upload-btn（display: flex，align-items: center）
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
  ├─ 遍历所选文件：size > 0 且 size < MAX_UPLOAD_FILE_SIZE（约 2.4MB）→ 加入 toEmit
  │       size 为 0 或 ≥ 上限 → sizeRejected += 1
  │
  ├─ sizeRejected > 0 → bkui-vue Message.error（formatUploadNotAddedMessage，说明可能超大或超出个数等）
  │
  ├─ toEmit.length > 0 → emit('upload', toEmit)
  │
  └─ target.value = ''（重置 input，允许再次选择同一文件）
```

**关键边界行为**：

| 场景                                                         | 结果                                                                 |
| ------------------------------------------------------------ | -------------------------------------------------------------------- |
| 一次多选超过上层允许个数（如 `ChatInput` 内已达 3 个）       | 由 **ChatInput** 侧 toast 并丢弃/不计入，不在本按钮内按个数提前拦截 |
| 部分文件因空文件或单文件超大被过滤                           | 弹出错误 toast；若仍有合法文件，**仍触发** `upload`（payload 为合法子集） |
| 全部被过滤（均为空或超大）                                   | 仅 toast，**不触发** `upload`                                        |
| `file.size === 0`                                          | 计入未添加提示，不进入 `upload` payload                              |
| `file.size >= MAX_UPLOAD_FILE_SIZE`（与全局常量一致，约 2.4MB） | 计入未添加提示，不进入 `upload` payload（比较为严格 `<`）           |
| 选择后取消                                                   | `files.length === 0`，不触发 `upload`                                |

> `multiple` prop 声明存在但当前模板中 `input` 的 `multiple` 属性为**硬编码**（非 `:multiple="multiple"` 绑定），始终允许多选，该 prop 暂时无实际效果。

> **`maxFiles` prop**：当前版本在按钮内**不参与截断或计数校验**，仅作类型与文档预留；列表最多几个文件由上层（如 `ChatInput` 的 `MAX_UPLOAD_FILES`）控制。详见 [ChatInput 文件上传](/components/input/chat-input#file-upload)。

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

| 属性名       | 类型           | 默认值      | 说明                                                                 |
| ------------ | -------------- | ----------- | -------------------------------------------------------------------- |
| accept       | `string`       | `'image/*'` | 文件选择框过滤类型，遵循 `<input accept>` 规范                       |
| maxFiles     | `number`       | `3`         | 预留字段，**当前不在按钮内生效**；个数上限见 `ChatInput` 与全局常量 |
| multiple     | `boolean`      | `true`      | 声明属性（当前版本未实际绑定到 input，始终多选）                     |
| tippyOptions | `AITippyProps` | —           | 扩展 tooltip 配置，会与内置配置合并                                |

### Events

| 事件名 | 参数              | 说明                                                                                      |
| ------ | ----------------- | ----------------------------------------------------------------------------------------- |
| upload | `(files: File[])` | 当存在至少一个合法文件时触发；`files` 为过滤掉空文件与单文件超大（`size >= MAX_UPLOAD_FILE_SIZE`，约 2.4MB）后的数组；个数截断不在此组件内完成 |

### Slots

| 插槽名  | 说明                                            |
| ------- | ----------------------------------------------- |
| default | 自定义按钮图标内容，默认为内置 `FileUploadIcon` |

## 使用场景

`FileUploadBtn` 由 `ChatInput` 组件内置，当 `ChatInput` 的 `supportUpload` prop 为 `true`（默认值）时自动渲染。一般不需要单独引入，除非构建完全自定义的输入区域。

## 类型定义

```typescript
import type { TippyOptions } from 'vue-tippy';

type AITippyProps = Partial<Pick<TippyOptions, 'appendTo' | 'placement' | 'zIndex'>>;
```

## 关联组件

- [ChatInput](/components/input/chat-input) — 默认内置上传入口
- [FileContent](/components/medias/file-content) — 选中文件列表展示
