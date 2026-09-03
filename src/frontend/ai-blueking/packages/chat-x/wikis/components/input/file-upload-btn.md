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
  - slug: add-menu-btn
    relation: ChatInput 内部已改用 + 号聚合菜单承载上传入口
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

::: warning ChatInput 已不再使用本按钮
输入区重构后，`ChatInput` 的上传入口改为左下角 [AddMenuBtn](/components/input/add-menu-btn) 聚合菜单里的「文件」项（内部走自持的隐藏 `input[type=file]`）。本组件仍保留在源码中并可用于自建输入区，但**不会**出现在 `ChatInput` 的默认布局里，也**未从包入口导出**——文档站示例经相对路径引入。
:::

文件上传触发按钮，点击后弹出系统文件选择框。内部包含隐藏的 `<input type="file">` 与可见的图标按钮；**不限制文件类型**，在按钮层只对**单文件**做大小与空文件过滤，**已选文件个数上限**由上层统一校验并提示，避免按钮与输入区各弹一条错误提示。

## 组件结构

```
.ai-file-upload-btn（display: flex，align-items: center）
├── input[type="file"]（.file-upload-btn-input，display: none，multiple，:accept）
│     accept 缺省时不下发该属性，系统选择框不过滤任何类型
│     触发后走 handleFileInputChange → 校验 → emit upload → target.value = ''
└── span.ai-shortcut-btn.file-upload-btn-icon（热区 32×32px / 圆角 8px；图标字号跟随 --ai-icon-size-sm：small=16px、normal=18px；color: #979ba5；hover: #f0f1f5）
      v-tippy: "上传文件，最多支持 {count} 个，单个最大 {size}MB"
        （{count} / {size} 由 MAX_UPLOAD_FILES 与 MAX_UPLOAD_FILE_SIZE 运行时填充，theme: ai-chat-box，offset: [0, 16]，可通过 tippyOptions 扩展）
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
| 一次多选超过上层允许个数                                     | 由**上层**（如输入区）toast 并丢弃 / 不计入，不在本按钮内按个数提前拦截 |
| 部分文件因空文件或单文件超大被过滤                           | 弹出错误 toast；若仍有合法文件，**仍触发** `upload`（payload 为合法子集） |
| 全部被过滤（均为空或超大）                                   | 仅 toast，**不触发** `upload`                                        |
| `file.size === 0`                                          | 计入未添加提示，不进入 `upload` payload                              |
| `file.size >= MAX_UPLOAD_FILE_SIZE`（与全局常量一致，约 2.4MB） | 计入未添加提示，不进入 `upload` payload（比较为严格 `<`）           |
| 选择后取消                                                   | `files.length === 0`，不触发 `upload`                                |

> `multiple` prop 声明存在但当前模板中 `input` 的 `multiple` 属性为**硬编码**（非 `:multiple="multiple"` 绑定），始终允许多选，该 prop 暂时无实际效果。

> **文件类型不做限制**：组件不再默认 `accept="image/*"`，任意类型文件都可选择。若业务需要收窄，显式传入 `accept`。个数上限由上层控制（`MAX_UPLOAD_FILES`），详见 [ChatInput 文件上传](/components/input/chat-input#file-upload)。

## 基础用法

```vue
<template>
  <FileUploadBtn @upload="handleUpload" />
</template>

<script setup lang="ts">
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

默认**不限制**文件类型。需要收窄时通过 `accept` 属性控制系统文件选择框的过滤条件，遵循 `<input type="file">` 的 `accept` 规范：

```vue
<template>
  <!-- 不限制类型（默认，不下发 accept） -->
  <FileUploadBtn @upload="handleUpload" />

  <!-- 仅图片 -->
  <FileUploadBtn
    accept="image/*"
    @upload="handleUpload"
  />

  <!-- 文档类型 -->
  <FileUploadBtn
    accept=".pdf,.doc,.docx,.xlsx,.pptx"
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

| 属性名       | 类型           | 默认值 | 说明                                                                       |
| ------------ | -------------- | ------ | -------------------------------------------------------------------------- |
| accept       | `string`       | —      | 文件选择框过滤类型，遵循 `<input accept>` 规范；缺省时不下发，不限制类型 |
| multiple     | `boolean`      | `true` | 声明属性（当前版本未实际绑定到 input，始终多选）                           |
| tippyOptions | `AITippyProps` | —      | 扩展 tooltip 配置，会与内置配置合并                                        |

### Events

| 事件名 | 参数              | 说明                                                                                      |
| ------ | ----------------- | ----------------------------------------------------------------------------------------- |
| upload | `(files: File[])` | 当存在至少一个合法文件时触发；`files` 为过滤掉空文件与单文件超大（`size >= MAX_UPLOAD_FILE_SIZE`，约 2.4MB）后的数组；个数截断不在此组件内完成 |

### Slots

| 插槽名  | 说明                                            |
| ------- | ----------------------------------------------- |
| default | 自定义按钮图标内容，默认为内置 `FileUploadIcon` |

## 使用场景

仅在**自建输入区**时使用。若使用 `ChatInput`，上传能力由 `supportUpload`（默认 `true`）开启，入口是 + 号菜单里的「文件」项、拖拽与粘贴，无需再挂本按钮。

## 类型定义

```typescript
import type { TippyOptions } from 'vue-tippy';

type AITippyProps = Partial<Pick<TippyOptions, 'appendTo' | 'placement' | 'zIndex'>>;
```

## 关联组件

- [AddMenuBtn](/components/input/add-menu-btn) — `ChatInput` 现行的上传 / 资源入口
- [ChatInput](/components/input/chat-input) — 上传能力与校验规则
- [FileContent](/components/medias/file-content) — 选中文件列表展示
