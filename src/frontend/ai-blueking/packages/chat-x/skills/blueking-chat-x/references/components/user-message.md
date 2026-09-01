# UserMessage 用户消息

> 能力域：消息系统 ｜ 导入：`import { UserMessage } from '@blueking/chat-x'` ｜ since 0.0.20

渲染用户消息：纯文本（非 Markdown）、键值引用、二进制附件与编辑态 ChatInput / ShortcutRender； 工具栏含 copy / cite / edit / delete。源码位置：src/components/chat-message/user-message/user-message.vue。

**关联**：message-render（由 MessageRender 在 role 为 user 时创建）、message-tools（消息工具栏交互与状态由 MessageTools 体系承载）、message-time（createdAt 经工具栏 prepend 插槽展示）、message-container（嵌入列表时由 MessageContainer 管理分组与多选）、chat-input（编辑态普通消息使用 ChatInput）

---

# UserMessage 用户消息

## 源码事实

- **源码位置**：`src/components/chat-message/user-message/user-message.vue`
- **能力域**：消息系统
- **能力说明**：渲染用户消息：纯文本、键值引用、文件附件与编辑态输入（**不**渲染 Markdown）。

> **导出说明**：`UserMessage` **未**从 `@blueking/chat-x` 包入口导出（入口同名是 TS interface）。消费方请用 `MessageRender` / `MessageContainer`。下文 `UserMessageComp` 为文档站内部相对路径示例。

用户消息展示组件，右对齐。支持纯文本、多媒体（图片/文件）、文本引用、结构化引用、快捷指令，以及内联编辑。

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
│     v-else-if: content  → TextContent × N（textParts 中每个文本片段一个实例）
│
└── MessageTools（.ai-user-message-tools）
      v-if: messageToolsStatus !== 'hidden'
      visibility: hidden（默认）→ visible（:hover 时）
      tools: [copy, cite, edit, delete]，updateTools: []
      #prepend slot → MessageTime（createdAt，工具图标左侧）
```

> **时间随工具栏显隐**：时间位于工具栏内，与工具按钮共用 `visibility` 控制，因此同样在悬停消息时才可见。

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
      v-model: editContent（取 textParts[0]，即第一个文本片段）
      defaultUploadFiles: binaryFiles
      #send-icon slot → .user-edit-footer
            Button "取消" → isEdit=false
            Button primary "发送" → chatInputRef.triggerSendMessage() + isEdit=false
```

## 基础用法

`content` 为字符串时，通过 `TextContent` 以**纯文本**插值渲染（`{{ content }}`），**不**走 Markdown。

```vue
<template>
  <MessageRender
    :message="message"
    :on-action="handleAction"
  />
</template>

<script setup lang="ts">
  import { MessageRender, MessageRole, MessageStatus, type IToolBtn } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.User,
    content: '你好，请帮我分析以下这段 Python 代码的性能瓶颈。',
    status: MessageStatus.Complete,
  };

  const handleAction = async (tool: IToolBtn) => {
    // copy / edit 有内置行为；cite / delete 需业务侧处理
    console.log('工具操作:', tool.id);
  };
</script>
```

> **工具栏**：悬停时显示「复制」「引用」「编辑」「删除」（CSS `visibility`，始终占位）。

## 多媒体消息

`content` 为数组时，同时支持文本（`type: 'text'`）和二进制文件（`type: 'binary'`）。组件将 `binary` 项按图片和非图片分为两组：

- **图片文件**（`binaryImageFiles`）：判断 `url` 存在或 `mimeType` / `file.type` 以 `image/` 开头的文件，统一放入一个 `FileContent`（`readonly=true`）中渲染，支持点击缩略图全屏预览
- **非图片文件**（`binaryNonImageFiles`）：每个文件单独渲染在 `FileContent`（`readonly=true`）中

`text` 项经 `textParts` 计算属性统一为 `string[]`，按顺序各渲染一个 `TextContent`。

```vue
<script setup lang="ts">
  import { MessageRender, MessageContentType, MessageRole, MessageStatus } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.User,
    status: MessageStatus.Complete,
    content: [
      {
        type: MessageContentType.Binary,
        url: 'https://example.com/screenshot.png',
        mimeType: 'image/png',
        filename: 'screenshot.png',
      },
      {
        type: MessageContentType.Text,
        text: '请帮我分析这张架构图，指出其中的问题。',
      },
    ],
  };
</script>
```

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
  // 消费方将 property 挂在 message 上，经 MessageRender 透传
  const message = {
    role: 'user',
    content: '这段代码每次循环都发起请求，应该如何优化？',
    property: {
      extra: {
        cite: '// 原始代码\nfor (let i = 0; i < arr.length; i++) {\n  fetch(`/api/${arr[i]}`)\n}',
      },
    },
  };
</script>
```

### 结构化引用（键值对）

`cite` 为对象 `{ title?, data: { key, value }[] }` 时，引用内容渲染在气泡**内部**（`KeyValueContent` 组件）：

```vue
<script setup lang="ts">
  const message = {
    role: 'user',
    content: '请帮我分析这份报表的数据趋势。',
    property: {
      extra: {
        cite: {
          title: '销售数据分析',
          type: 'structured',
          data: [
            { key: '报表名称', value: '2024 年 Q4 销售报表' },
            { key: '时间范围', value: '2024年10月 - 12月' },
            { key: '数据量', value: '12,580 条' },
          ],
        },
      },
    },
  };
</script>
```

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
  const message = {
    role: 'user',
    content: '请帮我翻译这段文字',
    property: {
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
    },
  };
</script>
```

## 消息编辑

点击「编辑」按钮后进入编辑模式，根据消息类型呈现不同界面：

| 消息类型                                     | 编辑界面                                              | 确认回调            |
| -------------------------------------------- | ----------------------------------------------------- | ------------------- |
| 普通文本 / 含文件消息                        | `ChatInput`（自定义 `#send-icon`，含"取消/发送"按钮） | `onInputConfirm`    |
| 含 `property.extra.shortcut` 或 cite+context | `ShortcutRender`                                      | `onShortcutConfirm` |

**`editContent` 的初始化逻辑**（仅文本部分，二进制文件通过 `defaultUploadFiles` 恢复）：

```
textParts 有值  → editContent = textParts[0]（取第一个文本片段）
binaryFiles 有值 → 进入编辑模式（editContent 可为空）
```

`textParts` 由 `content` 统一计算：`string` 转为单元素数组，`InputContent[]` 则过滤出 `type: 'text'` 且非空的项并映射为 `string[]`。

```vue
<template>
  <MessageRender
    :message="message"
    :on-action="handleAction"
    :on-input-confirm="handleInputConfirm"
    :on-shortcut-confirm="handleShortcutConfirm"
  />
</template>

<script setup lang="ts">
  import {
    MessageRender,
    MessageRole,
    MessageStatus,
    type IToolBtn,
    type TagSchema,
    type UserMessage,
  } from '@blueking/chat-x';

  const message = {
    id: '1',
    messageId: '1',
    role: MessageRole.User,
    content: '请帮我优化这段代码',
    status: MessageStatus.Complete,
  };

  const handleAction = async (tool: IToolBtn) => {
    // edit → 组件内切编辑态；copy → 组件内复制
    // cite / delete → 无内置行为，业务侧处理（如删除会话消息）
    console.log('工具:', tool.id);
  };

  const handleInputConfirm = async (content: UserMessage['content'], docSchema: TagSchema) => {
    console.log('编辑后内容:', content, docSchema);
  };

  const handleShortcutConfirm = async (formModel: Record<string, unknown>) => {
    console.log('快捷指令表单:', formModel);
  };
</script>
```

## 工具按钮

工具栏使用 CSS `visibility` 控制可见性（非 `display`），始终占位，hover 时显示：

**内置工具列表（`CONST_USER_MESSAGE_TOOLS`）**

| 工具 ID  | 名称 | 内置行为                                     |
| -------- | ---- | -------------------------------------------- |
| `copy`   | 复制 | 字符串直接复制；数组 `JSON.stringify` 后复制 |
| `cite`   | 引用 | 无内置行为，需通过 `onAction` 外部处理       |
| `edit`   | 编辑 | 切换 `isEdit=true`，进入编辑模式             |
| `delete` | 删除 | 无内置行为，需通过 `onAction` 外部处理       |

可通过 `messageTools` 按 id 覆盖/追加，`{ id: 'edit', hidden: true }` 可隐藏内置项。

```vue
<!-- 经 MessageRender 控制工具栏状态 -->
<MessageRender
  :message="message"
  message-tools-status="hidden"
/>
<MessageRender
  :message="message"
  message-tools-status="disabled"
/>
```

## supportUpload 透传

编辑态 `ChatInput` 的上传能力来自 `injectGlobalConfig().supportUpload`（通常由 `ChatContainer` 的 `supportUpload` prop 注册）。自定义 `#message` 插槽时须把同一配置链路保留，否则编辑态会与主输入区不一致。

```vue
<template>
  <ChatContainer
    :messages="messages"
    :support-upload="true"
    :on-agent-action="handleAgentAction"
    :on-user-action="handleUserAction"
  >
    <template #message="{ message, messageToolsStatus, onInterruptResume }">
      <MessageRender
        :message="message"
        :message-tools-status="messageToolsStatus"
        :on-action="handleUserAction"
        :on-input-confirm="(content, docSchema) => handleUserInputConfirm(message, content, docSchema)"
        :on-shortcut-confirm="formModel => handleUserShortcutConfirm(message, formModel)"
        :on-interrupt-resume="onInterruptResume"
      />
    </template>
  </ChatContainer>
</template>
```

## API

### Props

| 属性名             | 类型                                                                                       | 说明                                                                      |
| ------------------ | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------- |
| content            | `string \| InputContent[]`                                                                 | 消息内容，字符串或含 text/binary 的数组                                   |
| createdAt          | `number \| string`                                                                         | 消息创建时间，经 `MessageTools` 的 `#prepend` 插槽交给 `MessageTime` 渲染在工具图标左侧；无值时不展示 |
| property           | `{ extra?: MessageExtra; artifacts?: AIFileInfo[] }`                                       | 附加属性；本组件消费 `extra.cite` / `shortcut` / `context`                |
| messageTools       | `IToolBtn[]`                                                                               | 自定义用户消息工具组；按 id 与 `CONST_USER_MESSAGE_TOOLS` 合并，`{ id, hidden: true }` 可隐藏 |
| messageToolsStatus | `MessageToolsStatus`                                                                       | 工具按钮状态，`disabled` 禁用、`hidden` 从 DOM 移除                       |
| onAction           | `MessageToolsProps['onAction']`                                                            | 工具回调；`copy`/`edit` 有内置行为，`cite`/`delete` 需外部处理            |
| onInputConfirm     | `(content: UserMessage['content'], docSchema: TagSchema) => Promise<void>`                 | 普通消息编辑确认回调                                                      |
| onShortcutConfirm  | `(formModel: Record<string, unknown>) => Promise<void>`                                    | 快捷指令消息编辑确认回调                                                  |
| tippyOptions       | `Partial<Omit<TippyOptions, 'getReferenceClientRect' \| 'triggerTarget'>>`                 | 自定义工具栏 Tippy 配置，透传给内部 `MessageTools`                        |

### Events / Slots / Expose

无。

### 全局配置依赖

编辑态 `ChatInput` 通过 `injectGlobalConfig()` 读取 `supportUpload`。祖先需已 `useGlobalConfig()`（通常由 `ChatContainer` 注册）。

## 类型定义

```typescript
// 文本内容项
interface TextInputContent {
  type: 'text';
  text: string;
}

// 二进制内容项（图片、文件）
interface BinaryContent {
  type: 'binary';
  url?: string;
  mimeType?: string;
  filename?: string;
}

type InputContent = TextInputContent | BinaryContent;

// property.extra（与源码 BaseMessage.property.extra 对齐）
type MessageExtra = {
  // 文本引用 或 结构化引用（互斥 union，不是两个同名字段）
  cite?:
    | string
    | {
        title: string;
        type: 'structured';
        data: Array<{ key: string; value: string }>;
      };
  command?: string;
  pause?: boolean;
  shortcut?: Partial<Shortcut>;
  context?: Array<{
    __key: string;
    __label: string;
    __value: string;
    fillBack?: boolean;
    context_type?: string;
  }>;
};
```

## 关联组件

- [MessageRender](/components/message/message-render) — user 角色由其实例化
- [MessageTools](/components/feedback/message-tools) — 工具栏交互
- [MessageTime](/components/feedback/message-time) — 工具栏左侧的消息时间
- [MessageContainer](/components/setup/message-container) — 列表与多选容器
