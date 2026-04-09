---
name: UserMessage 用户消息
slug: user-message
category: molecular
description: 用户消息展示组件，右对齐显示用户发送的消息内容。支持纯文本、多媒体（图片/文件）、文本引用、结构化引用、快捷指令等多种内容形式，以及消息的内联编辑功能。
aiSummary: >
  UserMessage 渲染右对齐用户消息，支持文本、附件、文本/结构化引用、快捷指令与内联编辑。需处理 onAction、onInputConfirm、
  onShortcutConfirm 等回调；messageToolsStatus 控制工具栏。由 MessageRender 在 user 角色下使用，常与多选联动。
relatedComponents:
  - slug: message-render
    relation: 由 MessageRender 在 role 为 user 时创建
  - slug: message-tools
    relation: 消息工具栏交互与状态由 MessageTools 体系承载
  - slug: message-container
    relation: 嵌入列表时由 MessageContainer 管理分组与多选
sinceVersion: 1.0.0
domain: message
---

<script lang="ts" setup>
  import UserMessageComp from '../../../src/components/chat-message/user-message/user-message.vue'

  // 纯文本消息
  const textContent = '你好，请帮我分析以下这段 Python 代码的性能瓶颈。';

  // 数组格式：文本 + 二进制文件
  const mixedContent = [
    {
      type: 'binary',
      url: 'https://picsum.photos/400/300',
      mimeType: 'image/png',
      filename: 'screenshot.png',
    },
    {
      type: 'text',
      text: '请帮我分析这张架构图，指出其中的问题。',
    },
  ];

  // 文本引用（显示在气泡外）
  const textCiteProperty = {
    extra: {
      cite: '// 原始代码片段\nfor (let i = 0; i < arr.length; i++) {\n  fetch(`/api/${arr[i]}`)\n}',
    },
  };

  // 结构化引用（显示在气泡内）
  const kvCiteProperty = {
    extra: {
      cite: {
        title: '销售数据分析',
        data: [
          { key: '报表名称', value: '2024 年 Q4 销售报表' },
          { key: '时间范围', value: '2024年10月 - 12月' },
          { key: '数据量', value: '12,580 条' },
          { key: '负责人', value: '张三' },
        ],
      },
    },
  };

  // 快捷指令消息
  const shortcutProperty = {
    extra: {
      shortcut: {
        id: 'translate',
        name: '翻译',
        components: [
          {
            type: 'select',
            key: 'targetLang',
            name: '目标语言',
            default: 'en',
            options: [
              { label: '英文', value: 'en' },
              { label: '中文', value: 'zh' },
            ],
          },
          {
            type: 'textarea',
            key: 'content',
            name: '翻译内容',
            fillBack: true,
            default: '请帮我翻译这段文字',
          },
        ],
        formModel: {
          targetLang: 'en',
          content: '请帮我翻译这段文字',
        },
      },
    },
  };

  const handleAction = async (tool) => {
    console.log('消息操作:', tool.id);
  };

  const handleInputConfirm = async (content, docSchema) => {
    console.log('编辑确认:', content, docSchema);
  };

  const handleShortcutConfirm = async (formModel) => {
    console.log('快捷指令提交:', formModel);
  };
</script>

# UserMessage 用户消息

> **层级**：分子组件 · **功能域**：消息展示

用户消息展示组件，右对齐显示用户发送的消息内容。支持纯文本、多媒体（图片/文件）、文本引用、结构化引用、快捷指令等多种内容形式，以及消息的内联编辑功能。

## 组件结构

**正常模式**

```
.ai-user-message（align-items: flex-end，gap: 6px，font-size: 12px）
├── CiteContent（v-if：cite 为字符串）
│     紧凑条带（高 28px，灰色 #f5f7fa），引用图标 + 单行截断文本
│
├── [Binary 图片区] v-if binaryImageFiles.length
│     .ai-user-message-binary-files → FileContent（readonly=true，图片统一渲染，支持点击预览）
│
├── [Binary 非图片文件区] v-for binaryNonImageFiles
│     .ai-user-message-binary-files → FileContent（readonly=true，每个文件独立渲染）
│
├── .ai-user-message-content（气泡：bg #e1ecff，padding 8×12，border-radius 4px）
│     v-if: cite 为数组 → KeyValueContent（title + key/value 列表）
│     v-else-if: content  → MarkdownContent × N（每个 text 项一个实例）
│
└── MessageTools（.ai-user-message-tools）
      v-if: messageToolsStatus !== 'hidden'
      visibility: hidden（默认）→ visible（:hover 时）
      tools: [copy, cite, edit]，updateTools: []
```

**编辑模式**（点击 `edit` 按钮后 `isEdit=true`）

```
.ai-user-message
├── CiteContent（同上，不受编辑模式影响）
│
├── ShortcutRender（v-if: shortcut 有值）
│     @close → isEdit=false
│     @submit(formModel) → onShortcutConfirm(formModel) + isEdit=false
│
└── ChatInput（v-else，带自定义 #send-icon slot）
      v-model: editContent（仅含文本内容，数组时取第一个 text 项）
      defaultUploadFiles: binaryFiles
      #send-icon slot → .user-edit-footer
            Button "取消" → isEdit=false
            Button primary "发送" → chatInputRef.triggerSendMessage() + isEdit=false
```

## 基础用法

`content` 为字符串时，通过 `MarkdownContent` 渲染（支持 Markdown 语法）。

```vue
<template>
  <UserMessage
    :content="content"
    :on-action="handleAction"
  />
</template>

<script setup lang="ts">
  import { UserMessage, type IToolBtn } from '@blueking/chat-x';

  const content = '你好，请帮我分析以下这段 Python 代码的性能瓶颈。';

  const handleAction = async (tool: IToolBtn) => {
    console.log('工具操作:', tool.id);
  };
</script>
```

<div class="demo">
  <UserMessageComp :content="textContent" :on-action="handleAction" />
</div>

> **工具栏**：鼠标悬停时，消息下方出现「复制」「引用」「编辑」三个操作按钮（CSS `visibility` 切换，始终占位）。

## 多媒体消息

`content` 为数组时，同时支持文本（`type: 'text'`）和二进制文件（`type: 'binary'`）。组件将 `binary` 项按图片和非图片分为两组：

- **图片文件**（`binaryImageFiles`）：判断 `url` 存在或 `mimeType` / `file.type` 以 `image/` 开头的文件，统一放入一个 `FileContent`（`readonly=true`）中渲染，支持点击缩略图全屏预览
- **非图片文件**（`binaryNonImageFiles`）：每个文件单独渲染在 `FileContent`（`readonly=true`）中

`text` 项按顺序各渲染一个 `MarkdownContent`。

```vue
<script setup lang="ts">
  import { UserMessage, MessageContentType } from '@blueking/chat-x';

  const content = [
    {
      type: MessageContentType.Binary, // 'binary'
      url: 'https://example.com/screenshot.png',
      mimeType: 'image/png',
      filename: 'screenshot.png',
    },
    {
      type: MessageContentType.Text, // 'text'
      text: '请帮我分析这张架构图，指出其中的问题。',
    },
  ];
</script>
```

<div class="demo">
  <UserMessageComp :content="mixedContent" :on-action="handleAction" />
</div>

## 带引用的消息

通过 `property.extra.cite` 传入引用内容，支持两种格式，渲染位置不同：

| `cite` 类型               | 渲染组件                                         | 渲染位置         |
| ------------------------- | ------------------------------------------------ | ---------------- |
| `string`                  | `CiteContent`（紧凑条带，高 28px，文本单行截断） | 气泡**外部上方** |
| `{ title?, data[] }` 对象 | `KeyValueContent`（键值对列表）                  | 气泡**内部**     |

### 文本引用

`cite` 为字符串时，在气泡上方显示一个带引用图标的灰色条带（`#f5f7fa`），文本过长时截断。

```vue
<script setup lang="ts">
  import { UserMessage } from '@blueking/chat-x';

  const content = '这段代码每次循环都发起请求，应该如何优化？';
  const property = {
    extra: {
      cite: '// 原始代码\nfor (let i = 0; i < arr.length; i++) {\n  fetch(`/api/${arr[i]}`)\n}',
    },
  };
</script>
```

<div class="demo">
  <UserMessageComp
    content="这段代码每次循环都发起请求，应该如何优化？"
    :property="textCiteProperty"
    :on-action="handleAction"
  />
</div>

### 结构化引用（键值对）

`cite` 为对象 `{ title?, data: { key, value }[] }` 时，引用内容渲染在气泡**内部**（`KeyValueContent` 组件）：

```vue
<script setup lang="ts">
  import { UserMessage } from '@blueking/chat-x';

  const content = '请帮我分析这份报表的数据趋势。';
  const property = {
    extra: {
      cite: {
        title: '销售数据分析',
        data: [
          { key: '报表名称', value: '2024 年 Q4 销售报表' },
          { key: '时间范围', value: '2024年10月 - 12月' },
          { key: '数据量', value: '12,580 条' },
        ],
      },
    },
  };
</script>
```

<div class="demo">
  <UserMessageComp
    content="请帮我分析这份报表的数据趋势。"
    :property="kvCiteProperty"
    :on-action="handleAction"
  />
</div>

## 快捷指令消息

当消息来自快捷指令时，`property.extra.shortcut` 中携带快捷指令对象。在**编辑模式**下，组件渲染 `ShortcutRender` 代替普通 `ChatInput`。

`shortcut` computed 支持两条来源路径：

```
1. property.extra.shortcut 有值 → 直接使用
2. property.extra.cite 为对象 + property.extra.context 有值
     → 从 cite.data 和 context 动态构建 ShortcutComponent[] 数组
```

```vue
<script setup lang="ts">
  import { UserMessage } from '@blueking/chat-x';

  const content = '请帮我翻译这段文字';
  const property = {
    extra: {
      shortcut: {
        id: 'translate',
        name: '翻译',
        components: [
          {
            type: 'select',
            key: 'targetLang',
            name: '目标语言',
            default: 'en',
            options: [
              { label: '英文', value: 'en' },
              { label: '中文', value: 'zh' },
            ],
          },
          {
            type: 'textarea',
            key: 'content',
            name: '翻译内容',
            fillBack: true,
            default: '请帮我翻译这段文字',
          },
        ],
        formModel: { targetLang: 'en', content: '请帮我翻译这段文字' },
      },
    },
  };
</script>
```

<div class="demo">
  <UserMessageComp
    :content="'请帮我翻译这段文字'"
    :property="shortcutProperty"
    :on-action="handleAction"
    :on-shortcut-confirm="handleShortcutConfirm"
  />
</div>

## 消息编辑

点击「编辑」按钮后进入编辑模式，根据消息类型呈现不同界面：

| 消息类型                                     | 编辑界面                                              | 确认回调            |
| -------------------------------------------- | ----------------------------------------------------- | ------------------- |
| 普通文本 / 含文件消息                        | `ChatInput`（自定义 `#send-icon`，含"取消/发送"按钮） | `onInputConfirm`    |
| 含 `property.extra.shortcut` 或 cite+context | `ShortcutRender`                                      | `onShortcutConfirm` |

**`editContent` 的初始化逻辑**（仅文本部分，二进制文件通过 `defaultUploadFiles` 恢复）：

```
content 为 string     → editContent = content
textContent 为 string → editContent = textContent
textContent 为 array  → editContent = textContent[0]?.text（取第一个文本项）
binaryFiles 有值      → 进入编辑模式（editContent 可为空）
```

```vue
<template>
  <UserMessage
    :content="content"
    :on-action="handleAction"
    :on-input-confirm="handleInputConfirm"
    :on-shortcut-confirm="handleShortcutConfirm"
  />
</template>

<script setup lang="ts">
  import { UserMessage, type IToolBtn, type TagSchema } from '@blueking/chat-x';

  const content = '请帮我优化这段代码';

  const handleAction = async (tool: IToolBtn) => {
    // tool.id === 'edit'  → 组件内部自动切换编辑模式
    // tool.id === 'copy'  → 自动复制（字符串直接复制，数组 JSON.stringify 后复制）
    // tool.id === 'cite'  → 由外部 onAction 处理（组件内无内置行为）
    console.log('工具:', tool.id);
  };

  const handleInputConfirm = async (content: string | InputContent[], docSchema: TagSchema) => {
    console.log('编辑后内容:', content);
    // 重新发送消息
  };

  const handleShortcutConfirm = async (formModel: Record<string, unknown>) => {
    console.log('快捷指令表单:', formModel);
    // 重新发送快捷指令
  };
</script>
```

## 工具按钮

工具栏使用 CSS `visibility` 控制可见性（非 `display`），始终占位，hover 时显示：

**内置工具列表（`CONST_USER_MESSAGE_TOOLS`）**

| 工具 ID | 名称 | 内置行为                                     |
| ------- | ---- | -------------------------------------------- |
| `copy`  | 复制 | 字符串直接复制；数组 `JSON.stringify` 后复制 |
| `cite`  | 引用 | 无内置行为，需通过 `onAction` 外部处理       |
| `edit`  | 编辑 | 切换 `isEdit=true`，进入编辑模式             |

```vue
<!-- 隐藏工具按钮（从 DOM 移除，不占位） -->
<UserMessage :content="content" message-tools-status="hidden" />

<!-- 禁用工具按钮（保留占位，不可点击，无 hover 效果） -->
<UserMessage :content="content" message-tools-status="disabled" />
```

## API

### Props

| 属性名             | 类型                                                                         | 说明                                                      |
| ------------------ | ---------------------------------------------------------------------------- | --------------------------------------------------------- |
| content            | `string \| InputContent[]`                                                   | 消息内容，字符串或含 text/binary 的数组                   |
| property           | `{ extra?: MessageExtra }`                                                   | 消息附加属性，包含引用、快捷指令、context 等信息          |
| messageToolsStatus | `MessageToolsStatus`                                                         | 工具按钮状态，`disabled` 禁用、`hidden` 从 DOM 移除       |
| onAction           | `(tool: IToolBtn) => Promise<void>`                                          | 工具按钮回调；`copy`/`edit` 有内置行为，`cite` 需外部处理 |
| onInputConfirm     | `(content: string \| InputContent[], docSchema: TagSchema) => Promise<void>` | 普通消息编辑确认回调                                      |
| onShortcutConfirm  | `(formModel: Record<string, unknown>) => Promise<void>`                      | 快捷指令消息编辑确认回调                                  |
| tippyOptions       | `Partial<Omit<TippyOptions, 'getReferenceClientRect' \| 'triggerTarget'>>`   | 自定义工具栏 Tippy 配置，透传给内部 `MessageTools` 组件   |

### 全局配置依赖

编辑模式下的 `ChatInput` 会通过 `injectGlobalConfig()` 获取全局配置中的 `supportUpload` 值。需要确保祖先组件（通常是 `ChatContainer`）已调用 `useGlobalConfig()` 注册配置。

## 类型定义

```typescript
// 文本内容项
interface TextInputContent {
  type: 'text'; // MessageContentType.Text
  text: string;
}

// 二进制内容项（图片、文件）
interface BinaryContent {
  type: 'binary'; // MessageContentType.Binary
  url?: string;
  mimeType?: string;
  filename?: string;
}

type InputContent = TextInputContent | BinaryContent;

// 消息附加属性
interface MessageExtra {
  // 文本引用（字符串）：渲染在气泡外 CiteContent
  cite?: string;

  // 结构化引用（对象）：渲染在气泡内 KeyValueContent；与 context 配合可重建 ShortcutRender
  cite?: {
    title?: string;
    data: Array<{ key: string; value: string }>;
  };

  // 快捷指令：编辑时渲染 ShortcutRender（优先于 cite+context 路径）
  shortcut?: Shortcut;

  // 上下文变量：与结构化 cite 配合，在编辑模式下动态构建 ShortcutComponent[]
  context?: Array<{
    __key: string;
    __label: string;
    __value: string;
    fillBack?: boolean;
  }>;
}
```

## 关联组件

- [MessageRender](./message-render.md) — user 角色由其实例化
- [MessageTools](./message-tools.md) — 工具栏交互
- [MessageContainer](./message-container.md) — 列表与多选容器
