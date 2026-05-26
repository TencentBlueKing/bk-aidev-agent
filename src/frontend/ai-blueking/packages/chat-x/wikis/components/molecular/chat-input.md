---
name: ChatInput 聊天输入框
slug: chat-input
category: molecular
description: 聊天消息输入框组件，支持快捷指令选择、资源 `@` 引用、Prompt `/` 模板、消息引用、文件上传（拖拽/粘贴/点击）等功能。
aiSummary: >
  ChatInput 是聊天主输入区，集成富文本编辑（/ 提示词模板、@ 资源引用）、消息引用、附件上传与快捷指令入口。
  通过 prompts、resources、shortcuts 等 props 配置能力，配合 messageStatus 控制发送、流式与停止。
  内部组合 ShortcutBtns、FileUploadBtn 等，与 ShortcutRender 联动完成含表单的快捷指令流程。
relatedComponents:
  - slug: shortcut-btns
    relation: 底部附件区默认展示的快捷指令列表
  - slug: shortcut-btn
    relation: 已选快捷指令以单按钮形式展示并可关闭
  - slug: shortcut-render
    relation: 快捷指令含 components 时由外层唤起表单渲染
  - slug: chat-container
    relation: 顶层聊天布局中作为输入区子组件
  - slug: cite-content
    relation: 消息引用区展示选中的上下文片段
sinceVersion: 1.0.0
domain: input
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import ChatInputComp from '../../../src/components/chat-input/chat-input.vue'

  const inputBasic = ref('');
  const inputCite = ref('');
  const inputPlaceholder = ref('');
  const inputStreaming = ref('');
  const inputComplete = ref('');
  const inputDisabled = ref('');
  const inputBlocked = ref('这条消息暂时不能发送');
  const inputShortcut = ref('');
  const inputUpload = ref('');
  const inputSlot = ref('');

  const citeContent = ref('Vue 3 的 Composition API 提供了更灵活的逻辑组织方式，能够更好地进行代码复用和类型推断。');
  const interruptTip = '当前会话有 1 个待审批单，如需继续，请先取消审批';

  const handleSendMessage = async (value, docSchema) => {
    console.log('发送消息:', value, docSchema);
  };

  const handleStopSending = async () => {
    console.log('停止发送');
  };

  const handleUploadDemo = async (file) => {
    return { download_url: URL.createObjectURL(file) };
  };

  const prompts = [
    '帮我写一篇关于 {topic} 的文章',
    '解释一下这段代码的作用',
    '请用简洁的语言总结以下内容',
    '将以下内容翻译成英文',
    '帮我优化这段代码',
  ];

  const resources = [
    { id: 'tool1', name: '天气查询', type: 'tool', icon: 'icon-tool' },
    { id: 'tool2', name: '代码执行', type: 'tool', icon: 'icon-tool' },
    { id: 'mcp1', name: 'database-server', type: 'mcp', icon: 'icon-mcp' },
    { id: 'doc1', name: 'API 接口文档', type: 'doc', icon: 'icon-doc' },
    { id: 'doc2', name: '开发规范手册', type: 'doc', icon: 'icon-doc' },
    { id: 'shortcut1', name: '翻译助手', type: 'shortcut', icon: 'icon-shortcut' },
  ];

  const shortcuts = [
    { id: 'translate', name: '翻译' },
    { id: 'explain', name: '解释代码' },
    { id: 'summarize', name: '总结' },
  ];
</script>

# ChatInput 聊天输入框

> **层级**：分子组件 · **功能域**：输入交互

聊天消息输入框组件，支持快捷指令选择、资源 `@` 引用、Prompt `/` 模板、消息引用、文件上传（拖拽/粘贴/点击）等功能。

## 组件结构

```
chat-input-container
├── slot#top（容器顶部，在输入框框体外侧）
├── slot#interrupt（容器顶部，在输入框框体外侧，通常展示中断/审批提示）
└── chat-input（框体，受 inputMaxHeight 控制）
    ├── slot#input-header（默认：cite 不为空时渲染引用区）
    ├── slot#files（默认：有上传文件时渲染文件预览区）
    ├── AiSlashInput（富文本编辑器，/ 触发 Prompt，@ 触发资源）
    └── InputAttachment（底部工具栏，高度固定 40px）
        ├── FileUploadBtn（仅当 supportUpload 为 true 时显示，在 slot#attachment 外部）
        ├── 分隔线（仅当 supportUpload 为 true 且有快捷指令时显示）
        ├── slot#attachment（默认：ShortcutBtns 或已选 ShortcutBtn + 关闭图标）
        └── slot#send-icon（默认：发送/停止图标，仅替换图标，按钮容器保留）
```

> **注意**：`slot#attachment` 只替换快捷指令区，`FileUploadBtn` 在其外部，使用该 slot 不会移除上传按钮。`slot#send-icon` 只替换图标，按钮的点击处理和样式仍由组件控制。

### AiSlashInput 与 modelValue 同步

内部编辑器 `AiSlashInput` 在 **`modelValue` 由外部异步更新**（例如从历史会话回填、父组件重置）且与当前文档不一致时，会通过 `useCommandSelection` 提供的 `GetDocSnapshot` 读取编辑器快照，与 `docToString(modelValue)` 比对后，必要时执行 `ReplaceAll` 将编辑器内容同步为新的 `modelValue`，避免内外状态脱节。

## 基础用法

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type TagSchema } from '@blueking/chat-x';

  const inputValue = ref('');
  const messageStatus = ref(MessageStatus.Complete);

  const handleSendMessage = async (content: string, docSchema: TagSchema) => {
    // content：纯文本字符串（无文件时）或 InputContent[] 数组（有文件时）
    messageStatus.value = MessageStatus.Streaming;
    // ... 发送 AI 请求
    messageStatus.value = MessageStatus.Complete;
  };

  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
  };
</script>
```

**渲染效果**（输入 `/` 唤出 Prompt，输入 `@` 唤出资源菜单）

<div class="demo">
  <ChatInputComp
    v-model="inputBasic"
    message-status="complete"
    :prompts="prompts"
    :resources="resources"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</div>

## 发送状态（messageStatus）

`messageStatus` 控制底部工具栏的按钮渲染，但**输入框为空时始终自动置灰禁用**，无论 `messageStatus` 传入什么值。

| `messageStatus`               | 输入框有内容时按钮表现                                 | 输入框空时               |
| ----------------------------- | ------------------------------------------------------ | ------------------------ |
| `complete` / `stop` / `error` | 蓝色发送按钮，点击触发 `onSendMessage`                 | 灰色禁用                 |
| `streaming` / `pending` / `fetching` | 蓝色停止按钮（Loading 图标），点击触发 `onStopSending` | 蓝色停止按钮（仍可点击） |
| `disabled`                    | 灰色禁用，点击无效                                     | 灰色禁用                 |

> **实现细节**：组件内部用 `messageState` 计算属性决定实际按钮状态：当 `messageStatus` 为 `pending`、`streaming` 或 `fetching` 时直接使用该状态（确保停止按钮始终可用）；否则当输入为空或仅含空白字符时强制为 `disabled`，其余情况使用 `messageStatus` 的值。`fetching` 时按 Enter **不会**触发发送（避免请求中与 Loading 占位阶段重复提交）。

### sendDisabledTip（业务阻塞发送）

当业务侧需要临时阻止发送但仍允许用户输入时，可传入 `sendDisabledTip`。组件会置灰发送按钮，按钮 tooltip 展示该文案，并拦截点击发送、按 Enter 发送和 `triggerSendMessage()`：

```vue
<template>
  <ChatInput
    v-model="inputValue"
    message-status="complete"
    :send-disabled-tip="interruptTip"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  >
    <template #interrupt>
      <div class="input-alert">{{ interruptTip }}</div>
    </template>
  </ChatInput>
</template>
```

**渲染效果**

<div class="demo">
  <ChatInputComp
    v-model="inputBlocked"
    message-status="complete"
    :send-disabled-tip="interruptTip"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  >
    <template #interrupt>
      <div style="width: 100%; max-width: 1000px; padding: 6px 8px; margin-bottom: 6px; font-size: 12px; line-height: 20px; color: #4d4f56; background: #f0f5ff; border: 1px solid #a3c5fd; border-radius: 4px;">
        {{ interruptTip }}
      </div>
    </template>
  </ChatInputComp>
</div>

### Complete（可发送）

<div class="demo">
  <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">messageStatus = "complete"，输入内容后发送按钮可点击</p>
  <ChatInputComp
    v-model="inputComplete"
    message-status="complete"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</div>

### Streaming（流式输出中，显示停止按钮）

<div class="demo">
  <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">messageStatus = "streaming"，显示停止按钮（无论输入框是否为空）</p>
  <ChatInputComp
    v-model="inputStreaming"
    message-status="streaming"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</div>

### Disabled（禁用）

<div class="demo">
  <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">messageStatus = "disabled"，发送按钮始终禁用</p>
  <ChatInputComp
    v-model="inputDisabled"
    message-status="disabled"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</div>

## 引用消息（v-model:cite）

通过 `v-model:cite` 绑定引用内容，引用区域显示在编辑器上方，用户可点击关闭按钮取消引用。发送时通过 `onSendMessage` 的第一个参数获取输入内容，引用内容需自行通过 `cite` 变量读取：

```vue
<template>
  <ChatInput
    v-model="inputValue"
    v-model:cite="citeContent"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type TagSchema } from '@blueking/chat-x';

  const inputValue = ref('');
  const citeContent = ref('被引用的消息内容...');
  const messageStatus = ref(MessageStatus.Complete);

  const handleSendMessage = async (content: string, docSchema: TagSchema) => {
    console.log('输入内容:', content);
    console.log('引用内容:', citeContent.value); // 自行读取引用内容
    citeContent.value = ''; // 发送后清空引用
  };

  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
  };
</script>
```

**渲染效果**（顶部引用区，点击右侧 × 关闭引用）

<div class="demo">
  <ChatInputComp
    v-model="inputCite"
    v-model:cite="citeContent"
    message-status="complete"
    :prompts="prompts"
    :resources="resources"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</div>

## Prompt 模板（`/` 触发）

通过 `prompts` 传入字符串数组，用户在编辑器中输入 `/` 唤出 Prompt 菜单，支持模糊搜索，选择后自动填入编辑器：

```vue
<script setup lang="ts">
  const prompts = [
    '帮我写一篇关于 {topic} 的文章',
    '解释一下这段代码的作用',
    '请用简洁的语言总结以下内容',
    '将以下内容翻译成英文',
    '帮我优化这段代码',
  ];
</script>
```

## 资源 `@` 引用（`@` 触发）

通过 `resources` 传入资源列表，用户输入 `@` 唤出资源选择菜单。资源按 `type` 分组展示，选中后以 Tag 标签形式嵌入编辑器。已选中的资源不会再出现在下拉菜单中（自动去重）。

通过监听 `@update:model-value` 事件的第二个参数 `selectedResourceList` 可以获取当前编辑器中已选中的资源列表：

```vue
<template>
  <ChatInput
    :model-value="inputValue"
    :message-status="messageStatus"
    :prompts="prompts"
    :resources="resources"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
    @update:model-value="handleModelValueUpdate"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type TagSchema, type IAiSlashMenuItem } from '@blueking/chat-x';

  const inputValue = ref('');
  const messageStatus = ref(MessageStatus.Complete);

  const resources: IAiSlashMenuItem[] = [
    { id: 'tool1', name: '天气查询', type: 'tool', icon: 'icon-tool' },
    { id: 'tool2', name: '代码执行', type: 'tool', icon: 'icon-tool' },
    { id: 'mcp1', name: 'db-server', type: 'mcp', icon: 'icon-mcp' },
    { id: 'doc1', name: 'API 文档', type: 'doc', icon: 'icon-doc' },
    { id: 'sc1', name: '翻译助手', type: 'shortcut', icon: 'icon-shortcut' },
  ];

  const handleModelValueUpdate = (value: string | TagSchema, selectedResourceList: IAiSlashMenuItem[]) => {
    inputValue.value = value;
    // selectedResourceList 为当前编辑器中已选中的 @ 资源列表
    console.log('已选资源:', selectedResourceList);
  };

  const handleSendMessage = async (content: string, docSchema: TagSchema) => {
    console.log('发送内容（含 @ 引用）:', docSchema);
  };

  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
  };
</script>
```

> 基础用法 demo 已集成 Prompt 和资源功能，可在上方输入框中体验 `/` 和 `@` 操作。
>
> **注意**：`v-model` 仍可使用（Vue 自动取第一个参数绑定），但如需获取 `selectedResourceList`，应使用 `@update:model-value` 显式监听。

## 快捷指令

通过 `shortcuts` 传入快捷指令列表，底部工具栏展示快捷指令按钮；通过 `shortcutId` + `shortcuts` 配合控制选中状态：

- `shortcutId` 为空 → 显示所有快捷指令按钮列表
- `shortcutId` 匹配某个 `shortcut.id` → 隐藏列表，显示已选指令 + 关闭图标

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :message-status="messageStatus"
    :shortcuts="shortcuts"
    :shortcut-id="selectedShortcutId"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
    @select-shortcut="selectedShortcutId = $event.id"
    @delete-shortcut="selectedShortcutId = ''"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type TagSchema, type Shortcut } from '@blueking/chat-x';

  const inputValue = ref('');
  const messageStatus = ref(MessageStatus.Complete);
  const selectedShortcutId = ref('');

  const shortcuts: Shortcut[] = [
    { id: 'translate', name: '翻译' },
    { id: 'explain', name: '解释代码' },
    { id: 'summarize', name: '总结' },
  ];

  const handleSendMessage = async (content: string, docSchema: TagSchema) => {
    console.log('发送内容:', content, '当前快捷指令:', selectedShortcutId.value);
  };

  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
  };
</script>
```

**渲染效果**（底部显示快捷指令按钮，点击选中后按钮变为已选状态）

<div class="demo">
  <ChatInputComp
    v-model="inputShortcut"
    message-status="complete"
    :prompts="prompts"
    :resources="resources"
    :shortcuts="shortcuts"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</div>

## 文件上传 {#file-upload}

`supportUpload` 默认为 `true`，底部工具栏自动显示文件上传按钮。传入 `onUpload` 回调后即可处理文件上传：

- 底部工具栏出现文件上传按钮（在快捷指令左侧）
- 支持**点击选择**、**拖拽上传**、**粘贴上传**（Ctrl+V）
- `onUpload` 每次传入**单个** `File`，返回 `{ download_url?: string }`
- 文件自动去重（基于 `name + size + lastModified` 复合键），不会重复上传
- 发送成功后，`uploadFiles` 自动清空

**个数与大小校验（与 `FileUploadBtn` 分工）**：

- 列表最多保留 **`MAX_UPLOAD_FILES`（3）** 个待发送附件；已满时再次选择/拖入/粘贴文件会弹出 **bkui-vue `Message` 错误提示**（`formatUploadNotAddedMessage`），且不会继续入队。
- 在未满的前提下：空文件、单文件大小 **`>= MAX_UPLOAD_FILE_SIZE`（约 2.4MB）**、或与已有文件重复的项会被跳过；若本轮有任意文件因此未加入列表，会在处理结束后弹出**同一条文案风格**的错误提示，汇总未成功添加的数量。
- `FileUploadBtn` 仅在按钮层过滤**空文件与单文件超大**，把合法文件以数组形式 `upload` 上来；**个数上限与重复校验**在 `ChatInput` 的 `handleUpload` 中统一处理，避免与按钮层各弹一条提示。

**发送内容格式**（有文件时）：

```typescript
// onSendMessage 的 content 参数变为数组：
[
  { type: 'binary', url: '...', mimeType: 'image/png', filename: 'a.png' },
  { type: 'binary', url: '...', mimeType: 'application/pdf', filename: 'b.pdf' },
  // 若输入框也有文字，则最后追加：
  { type: 'text', text: '请帮我分析这两个文件' },
];
```

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
    :on-upload="handleUpload"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type UserMessage, type TagSchema } from '@blueking/chat-x';

  const inputValue = ref('');
  const messageStatus = ref(MessageStatus.Complete);

  const handleSendMessage = async (content: UserMessage['content'], docSchema: TagSchema) => {
    if (Array.isArray(content)) {
      // 有文件时 content 为数组
      content.forEach(item => {
        if (item.type === 'binary') console.log('文件:', item.filename, item.url);
        if (item.type === 'text') console.log('文字:', item.text);
      });
    } else {
      // 无文件时 content 为纯字符串
      console.log('文字:', content);
    }
  };

  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
  };

  // 每次传入单个 File，需返回 { download_url: string }
  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    return res.json(); // { download_url: '...' }
  };
</script>
```

**渲染效果**（底部出现文件上传按钮，支持点击、拖拽、粘贴上传）

<div class="demo">
  <ChatInputComp
    v-model="inputUpload"
    message-status="complete"
    :prompts="prompts"
    :resources="resources"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
    :on-upload="handleUploadDemo"
  />
</div>

## 预设上传文件（defaultUploadFiles）

通过 `defaultUploadFiles` 设置初始已上传的文件列表，文件出现在文件预览区，随下次发送一起携带：

```vue
<script setup lang="ts">
  import { type UploadFile, UploadStatus } from '@blueking/chat-x';

  const defaultFiles: UploadFile[] = [
    {
      type: 'binary',
      url: 'https://example.com/report.pdf',
      filename: 'report.pdf',
      mimeType: 'application/pdf',
      status: UploadStatus.Success,
    },
  ];
</script>
```

## 自定义占位符

通过 `placeholder` 自定义占位符文案，支持多行（换行用 `\n`）：

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :message-status="messageStatus"
    :placeholder="placeholder"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</template>

<script setup lang="ts">
  // 多行占位符
  const placeholder = `你好，我是 AI 小鲸！
输入 "/" 唤出 Prompt
输入 "@" 唤出工具
按 Shift + Enter 换行`;
</script>
```

**渲染效果**

<div class="demo">
  <ChatInputComp
    v-model="inputPlaceholder"
    message-status="complete"
    placeholder="你好，我是 AI 小鲸！&#10;输入 / 唤出 Prompt&#10;输入 @ 唤出工具&#10;按 Shift + Enter 换行"
    :prompts="prompts"
    :resources="resources"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</div>

## 自定义插槽

组件提供 6 个插槽用于自定义各区域内容：

| 插槽名         | 位置                                       | 默认行为                                   |
| -------------- | ------------------------------------------ | ------------------------------------------ |
| `top`          | 框体外部顶部（`.chat-input` 上方）         | 无                                         |
| `interrupt`    | 框体外部顶部，位于 `top` 之后              | 无，通常用于展示审批/中断提示              |
| `input-header` | 框体内部顶部（编辑器上方）                 | `cite` 不为空时渲染引用区（`CiteContent`） |
| `files`        | 文件预览区                                 | 有上传文件时渲染 `FileContent`             |
| `attachment`   | 底部工具栏快捷指令区（FileUploadBtn 右侧） | 快捷指令按钮列表 / 已选快捷指令            |
| `send-icon`    | 发送按钮内的图标                           | 发送图标 / 停止图标（按钮容器由组件控制）  |

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  >
    <!-- 框体外顶部，适合展示模型信息、Token 消耗等 -->
    <template #top>
      <div class="input-tips">当前模型: GPT-4 · 剩余 Token: 12,800</div>
    </template>

    <!-- 框体外顶部，适合展示中断、审批等业务提示 -->
    <template #interrupt>
      <div class="input-alert">当前会话有待审批单，暂时不能继续发送</div>
    </template>

    <!-- 替换引用区，可自定义引用样式 -->
    <template #input-header>
      <div class="custom-header">自定义头部内容</div>
    </template>

    <!-- 替换文件预览区，接收 files 参数 -->
    <template #files="{ files }">
      <div class="custom-files">
        <span
          v-for="file in files"
          :key="file.filename"
          >{{ file.filename }}</span
        >
      </div>
    </template>

    <!-- 替换快捷指令区（FileUploadBtn 仍在左侧） -->
    <template #attachment>
      <button @click="handleCustomAction">🎯 自定义操作</button>
    </template>

    <!-- 替换发送按钮图标（点击逻辑不变） -->
    <template #send-icon>
      <span>🚀</span>
    </template>
  </ChatInput>
</template>
```

**渲染效果**（顶部自定义模型信息与中断提示）

<div class="demo">
  <ChatInputComp
    v-model="inputSlot"
    message-status="complete"
    :prompts="prompts"
    :resources="resources"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  >
    <template #top>
      <div style="padding: 6px 12px; font-size: 12px; color: #979ba5; text-align: center; background: #f5f7fa; border-radius: 4px 4px 0 0;">当前模型: GPT-4 · 剩余 Token: 12,800</div>
    </template>
    <template #interrupt>
      <div style="width: 100%; max-width: 1000px; padding: 6px 8px; margin-bottom: 6px; font-size: 12px; line-height: 20px; color: #4d4f56; background: #f0f5ff; border: 1px solid #a3c5fd; border-radius: 4px;">
        当前会话有待审批单，暂时不能继续发送
      </div>
    </template>
  </ChatInputComp>
</div>

## Expose（模板引用）

通过 `ref` 获取组件实例后可调用以下方法：

```vue
<template>
  <ChatInput
    ref="chatInputRef"
    v-model="inputValue"
    :on-send-message="handleSendMessage"
  />
  <button @click="chatInputRef?.focus()">聚焦输入框</button>
  <button @click="chatInputRef?.triggerSendMessage()">手动发送</button>
</template>

<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { ChatInput } from '@blueking/chat-x';

  const chatInputRef = useTemplateRef<InstanceType<typeof ChatInput>>('chatInputRef');
  const inputValue = ref('');
  const handleSendMessage = async (content: string) => {
    /* ... */
  };
</script>
```

## API

### Props

| 属性名             | 类型                                                                       | 默认值   | 必填 | 说明                                                    |
| ------------------ | -------------------------------------------------------------------------- | -------- | ---- | ------------------------------------------------------- |
| modelValue         | `string \| TagSchema`                                                      | -        | ✅   | 编辑器的值，支持 `v-model`                              |
| messageStatus      | `MessageStatus`                                                            | -        | -    | 消息状态，控制按钮；输入为空时内部强制 `disabled`       |
| cite               | `string`                                                                   | `''`     | -    | 引用内容，支持 `v-model:cite`，不为空时显示引用区       |
| prompts            | `string[]`                                                                 | `[]`     | -    | Prompt 模板列表，输入 `/` 触发                          |
| resources          | `IAiSlashMenuItem[]`                                                       | `[]`     | -    | 资源列表，输入 `@` 触发，按 `type` 分组展示             |
| shortcuts          | `Shortcut[]`                                                               | -        | -    | 快捷指令列表，显示在底部工具栏                          |
| shortcutId         | `string`                                                                   | -        | -    | 当前选中的快捷指令 ID，匹配时列表收起为已选样式         |
| placeholder        | `string`                                                                   | 见默认值 | -    | 编辑器占位符，支持多行                                  |
| inputMaxHeight     | `number`                                                                   | `200`    | -    | 框体最大高度（px），有文件时自动加上文件预览区高度      |
| defaultUploadFiles | `UploadFile[]`                                                             | -        | -    | 预设已上传的文件列表                                    |
| sendDisabledTip    | `string`                                                                   | -        | -    | 业务阻塞发送时的 tooltip 提示；传入后发送按钮置灰，点击、Enter 与 `triggerSendMessage()` 均不会发送 |
| supportUpload      | `boolean`                                                                  | `true`   | -    | 是否显示文件上传按钮                                    |
| tippyOptions       | `AITippyProps`                                                             | —        | -    | 透传给 FileUploadBtn 和 InputAttachment 的 tooltip 配置 |
| onSendMessage      | `(content: UserMessage['content'], docSchema: TagSchema) => Promise<void>` | -        | -    | 发送消息回调，无文件时 content 为字符串，有文件时为数组 |
| onStopSending      | `() => Promise<void>`                                                      | -        | -    | 停止发送回调，点击停止按钮时触发                        |
| onUpload           | `(file: File) => Promise<{ download_url?: string }>`                       | -        | -    | 文件上传回调（每次单文件）                              |

### 默认占位符

```
输入 "/"唤出 Prompt
输入"@"唤出工具
通过 Shift + Enter 进行换行输入
```

### Events

| 事件名            | 参数                                                                     | 触发时机                                                  |
| ----------------- | ------------------------------------------------------------------------ | --------------------------------------------------------- |
| update:modelValue | `(value: string \| TagSchema, selectedResourceList: IAiSlashMenuItem[])` | 编辑器值变化时触发；第二个参数为当前已选中的 `@` 资源列表 |
| selectShortcut    | `(shortcut: Shortcut)`                                                   | 点击底部快捷指令按钮                                      |
| deleteShortcut    | -                                                                        | 点击已选快捷指令旁的关闭按钮                              |

### Slots

| 插槽名       | 参数                               | 说明                                                       |
| ------------ | ---------------------------------- | ---------------------------------------------------------- |
| top          | -                                  | 框体（`.chat-input`）外部顶部，适合展示模型/Token 信息     |
| interrupt    | -                                  | 框体外部顶部，位于 `top` 后，适合展示审批/中断提示         |
| input-header | -                                  | 框体内顶部，替换引用区（`CiteContent`）                    |
| files        | `{ files: Partial<UploadFile>[] }` | 文件预览区                                                 |
| attachment   | -                                  | 底部快捷指令区，`FileUploadBtn` 在其左侧，不受此 slot 影响 |
| send-icon    | -                                  | 发送按钮内图标，按钮的点击逻辑和样式仍由组件控制           |

### Expose

| 方法名             | 类型         | 说明             |
| ------------------ | ------------ | ---------------- |
| focus              | `() => void` | 聚焦编辑器       |
| triggerSendMessage | `() => void` | 手动触发发送逻辑 |

## 键盘快捷键

| 快捷键          | 说明                                     |
| --------------- | ---------------------------------------- |
| `Enter`         | 发送消息（输入为空或仅空白字符时不触发） |
| `Shift + Enter` | 换行                                     |
| `/`             | 唤出 Prompt 列表                         |
| `@`             | 唤出资源列表                             |
| `↑` / `↓`       | 在 Prompt / 资源菜单中导航               |
| `Esc`           | 关闭 Prompt / 资源菜单                   |

## 类型定义

```typescript
import type { UserMessage } from '@blueking/chat-x';

// 消息状态
enum MessageStatus {
  Pending = 'pending', // 等待中（显示停止按钮）
  Streaming = 'streaming', // 流式输出中（显示停止按钮）
  Complete = 'complete', // 完成（显示发送按钮）
  Error = 'error', // 错误（显示发送按钮）
  Stop = 'stop', // 已停止（显示发送按钮）
  Disabled = 'disabled', // 禁用（发送按钮置灰）
}

// 上传状态
enum UploadStatus {
  Pending = 'pending', // 上传中
  Success = 'success', // 上传成功
  Error = 'error', // 上传失败
}

// 上传文件
type UploadFile = {
  type: 'binary';
  url?: string; // 上传成功后的下载地址
  filename?: string; // 文件名
  mimeType?: string; // MIME 类型
  file?: File; // 原始 File 对象
  status?: UploadStatus; // 上传状态
};

// 资源菜单项（@ 触发）
interface IAiSlashMenuItem {
  id: string;
  name: string;
  icon: string;
  type: 'tool' | 'mcp' | 'doc' | 'shortcut'; // 分组类型
}

// onSendMessage 的 content 参数
type SendContent =
  | string // 无文件时：纯文本
  | Array<
      // 有文件时：数组
      { type: 'binary'; url?: string; mimeType: string; filename: string } | { type: 'text'; text: string }
    >;
```

## 完整集成示例

```vue
<template>
  <ChatInput
    v-model="inputValue"
    v-model:cite="citeContent"
    :message-status="messageStatus"
    :prompts="prompts"
    :resources="resources"
    :shortcuts="shortcuts"
    :shortcut-id="shortcutId"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
    :on-upload="handleUpload"
    @select-shortcut="shortcutId = $event.id"
    @delete-shortcut="shortcutId = ''"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type TagSchema, type Shortcut } from '@blueking/chat-x';

  const inputValue = ref('');
  const citeContent = ref('');
  const messageStatus = ref(MessageStatus.Complete);
  const shortcutId = ref('');

  const prompts = ['帮我写一篇关于 {topic} 的文章', '解释一下这段代码'];
  const resources = [{ id: 'tool1', name: '天气查询', type: 'tool', icon: '' }];
  const shortcuts: Shortcut[] = [
    { id: 'translate', name: '翻译' },
    { id: 'explain', name: '解释' },
  ];

  const handleSendMessage = async (content, docSchema: TagSchema) => {
    messageStatus.value = MessageStatus.Streaming;
    try {
      await callAI(content, { cite: citeContent.value, shortcut: shortcutId.value });
    } finally {
      messageStatus.value = MessageStatus.Complete;
      citeContent.value = '';
    }
  };

  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
    abortAICall();
  };

  const handleUpload = async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    return res.json(); // { download_url: '...' }
  };
</script>
```

## 关联组件

- [ShortcutBtns](../atomic/shortcut-btns.md) — 底部附件区默认快捷指令列表
- [ShortcutBtn](../atomic/shortcut-btn.md) — 已选快捷指令单按钮展示
- [ShortcutRender](./shortcut-render.md) — 含表单的快捷指令表单渲染
- [ChatContainer](./chat-container.md) — 顶层布局中包裹输入区
- [CiteContent](../atomic/cite-content.md) — 消息引用区内容展示
