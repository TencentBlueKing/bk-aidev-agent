# ChatInput 聊天输入框

> 能力域：输入交互 ｜ 导入：`import { ChatInput } from '@blueking/chat-x'` ｜ since 1.0.0

聊天输入区，组合富文本输入、统一菜单、快捷指令、附件、引用、发送/停止等交互。 菜单数据由单一 menuSources 提供，按 type 分发到 `/` `@` `\` 与左下角 + 号四种触发方式。 源码位置：src/components/chat-input/chat-input.vue。

**关联**：ai-slash-input（内部富文本编辑区，负责触发符识别与标签插入）、input-menu-panel（输入框正上方的统一菜单面板）、add-menu-btn（左下角 + 号，唤起聚合菜单）、mention-tag（菜单选中的资源以标签形式嵌入编辑器）、model-selector（传入 models 后在发送按钮左侧默认展示模型选择器）、shortcut-btns（底部附件区默认展示的快捷指令列表）、cite-content（消息引用区展示选中的上下文片段）、chat-container（顶层聊天布局中作为输入区子组件）

---

# ChatInput 聊天输入框

> **能力域**：输入交互

## 源码事实

- **源码位置**：`src/components/chat-input/chat-input.vue`
- **能力说明**：聊天输入区，组合富文本输入、统一菜单、快捷指令、附件、引用、发送/停止等交互。
- **菜单数据源唯一**：`menuSources` 一份数组按 `type` 分发到 `/`、`@`、`\` 三个触发符与左下角 + 号，组件内部不再区分 `skills` / `prompts` / `resources`。

## 组件结构

```
ai-chat-input-container（padding: 0 16px 16px）
├── slot#top（框体外顶部）
├── slot#interrupt（框体外顶部，位于 top 之后）
└── chat-input-wrapper（相对定位；宽度 168px ~ 1000px）
    ├── InputMenuPanel（绝对定位于框体上方 8px、与框体等宽，菜单激活且有条目时渲染）
    └── chat-input（框体，min-height 110px，max-height 由 inputMaxHeight 控制）
        ├── slot#input-header（默认：cite 非空时渲染 CiteContent）
        ├── slot#files（默认：有上传文件时渲染 FileContent）
        ├── AiSlashInput（富文本编辑区，默认保持 4 行高度）
        └── InputAttachment（底部工具栏，固定 32px 高）
            ├── slot#default → 隐藏 file input + AddMenuBtn（+ 号）+ 分隔线 + slot#attachment
            ├── slot#before-send → slot#model-selector（默认 ModelSelector）
            └── slot#send-icon（默认：发送 / 停止图标）
```

> `slot#attachment` 只替换快捷指令区，`AddMenuBtn` 在其外部，使用该插槽不会移除 + 号。`slot#send-icon` 只替换图标，点击逻辑与按钮样式仍由组件控制。

## 基础用法

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :menu-sources="menuSources"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type IInputMenuItem, type TagSchema } from '@blueking/chat-x';

  const inputValue = ref('');
  const messageStatus = ref(MessageStatus.Complete);

  const menuSources: IInputMenuItem[] = [
    { id: 'translate', type: 'skill', name: '翻译', description: '把选中的文本翻译成目标语言' },
    { id: 'database-server', type: 'mcp', name: 'database-server' },
    { id: 'weather', type: 'tool', name: '天气查询' },
    { id: 'kb-api', type: 'knowledgebase', name: 'API 接口文档' },
    { id: 'prompt-article', type: 'prompt', name: '写文章', content: '帮我写一篇关于 {topic} 的文章' },
  ];

  const handleSendMessage = async (content: string, docSchema: TagSchema) => {
    // content：纯文本字符串（无文件时）或 InputContent[] 数组（有文件时）
    // docSchema：当前编辑器文档，含标签结构，可持久化用于回显
    messageStatus.value = MessageStatus.Streaming;
    // ... 发送 AI 请求
    messageStatus.value = MessageStatus.Complete;
  };

  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
  };
</script>
```

**渲染效果**（输入 `/` `@` `\` 或点击左下角 + 号唤出菜单）

## 统一菜单（menuSources）

### 触发方式与分组

菜单面板固定展示在输入框**正上方**并与输入框等宽（不跟随光标），最大高度 400px，超出滚动。四种触发方式共用同一份 `menuSources`，各自展示的分组不同：

| 触发方式         | 分组顺序                                                       | 说明                                       |
| ---------------- | -------------------------------------------------------------- | ------------------------------------------ |
| `/`              | Skill、MCP、工具                                               | 智能体能力                                 |
| `@`              | 知识库、会话产物                                               | 可引用的上下文资源                         |
| `\`              | Prompt                                                         | 提示词模板                                 |
| + 号（`plus`）   | 添加、Skill、MCP、工具、知识库、会话产物、Prompt               | 聚合全部分组，「添加」组下方有分隔线       |

分组与 `type` 的对应关系：

| 分组标题   | 覆盖的 `type`              | 备注                                             |
| ---------- | -------------------------- | ------------------------------------------------ |
| 添加       | `file`                     | 组件内置项，只出现在 + 号菜单                    |
| Skill      | `skill`                    | 插入后序列化为 `/<id>`                           |
| MCP        | `mcp`                      |                                                  |
| 工具       | `tool`                     |                                                  |
| 知识库     | `knowledgebase`、`doc`     | 后端两种历史命名合并为一个分组                   |
| 会话产物   | `artifact`                 | 无数据时仍展示分组并显示「暂无数据」             |
| Prompt     | `prompt`                   | 选中后整体替换输入框内容                         |

### 关键行为

- **过滤**：触发符之后输入的文本作为关键字，按 `name` 不区分大小写包含匹配。+ 号菜单的关键字取「唤起时光标位置 → 当前光标」之间的文本。
- **折叠**：每个分组默认展示 `menuGroupItemLimit`（默认 4）条，超出折叠为「更多 +N」，点击展开；关键字或触发方式变化后折叠状态重置。
- **去重**：已插入编辑器的标签按 `type:id` 从候选中剔除，不会重复出现。
- **空面板不弹出**：只有「会话产物」这类保留分组、没有任何真实条目时，面板不会展示。
- **内置「文件」项**：`supportUpload` 为 `true` 时，组件在「添加」分组注入一条 `type: 'file'` 的内置项，选中即唤起系统文件选择器，不需要业务方在 `menuSources` 里提供。
- **+ 号显隐**：`supportUpload` 为 `false` 且 `menuSources` 为空时不渲染 + 号。
- **选中动作**：`prompt` 整体替换输入框内容（取 `content`，缺省取 `name`）；`file` 唤起文件选择器；其余类型插入资源标签并补一个空格。

```vue
<template>
  <ChatInput
    :model-value="inputValue"
    :menu-sources="menuSources"
    :menu-group-item-limit="6"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    @update:model-value="handleModelValueUpdate"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatInput, MessageStatus, type IInputMenuItem, type TagSchema } from '@blueking/chat-x';

  const inputValue = ref<string | TagSchema>('');

  const handleModelValueUpdate = (value: string | TagSchema, selectedResourceList: IInputMenuItem[]) => {
    inputValue.value = value;
    // selectedResourceList 为当前编辑器内已插入的菜单条目（能在 menuSources 中反查到的部分）
    console.log('已选资源:', selectedResourceList);
  };
</script>
```

> `v-model` 仍可用（Vue 自动绑定第一个参数）；需要 `selectedResourceList` 时改用 `@update:model-value` 显式监听。

### 图标

条目的 `icon` 支持图片 URL 字符串或 Vue 组件，缺省时由 [ResourceIcon](/components/helper/resource-icon) 按 `type` 兜底（`artifact` 按文件名后缀推导）。

::: warning 组件形式的图标不会随标签保留
插入编辑器后，标签会把图标序列化到 DOM 属性上（这样文档可以脱离 `menuSources` 独立还原），因此只有字符串 URL 能被保留；传 Vue 组件时标签内会回退为类型默认图标。
:::

### 发送后的文本形态

标签在发送文本中按类型序列化：`skill` 输出 `/<id>`，其余类型输出 `@<name>`。因此 `skill` 的 `id` 需要是后端可识别的编码。

## 从 skills / prompts / resources 迁移

旧版三个数据源与 `AiSkillList` / `AiPromptList` / `AiSlashMenu` 三个菜单组件已移除，统一为 `menuSources`：

| 旧 API                                   | 新写法                                                                              |
| ---------------------------------------- | ----------------------------------------------------------------------------------- |
| `skills: ISkillListItem[]`               | `menuSources` 中 `type: 'skill'`；`skill_code` → `id`，`skill_name` → `name`         |
| `prompts: string[]`                      | `type: 'prompt'`；`name` 为菜单展示名，`content` 为插入正文                          |
| `resources: IAiSlashMenuItem[]`          | `type` 取 `tool` / `mcp` / `knowledgebase` / `doc` / `artifact`                      |
| `resources` 中的 `type: 'shortcut'`      | 不再进入菜单，快捷指令走 `shortcuts` + `shortcutId`                                  |
| `ISkillListItem` / `IAiSlashMenuItem`    | 统一为 `IInputMenuItem`（`resourceTypeMap`、`ResourceType` 一并移除）                |
| `\` 唤出 Prompt、`/` 唤出 Skill          | 触发符不变，`@` 新增「会话产物」分组，并新增 + 号聚合菜单                            |

```typescript
// 旧
const skills = [{ skill_code: 'translate', skill_name: '翻译', description: '翻译文本', icon: '' }];
const prompts = ['帮我写一篇关于 {topic} 的文章'];
const resources = [{ id: 'tool1', name: '天气查询', type: 'tool', icon: '' }];

// 新
const menuSources: IInputMenuItem[] = [
  { id: 'translate', type: 'skill', name: '翻译', description: '翻译文本' },
  { id: 'prompt-article', type: 'prompt', name: '写文章', content: '帮我写一篇关于 {topic} 的文章' },
  { id: 'tool1', type: 'tool', name: '天气查询' },
];
```

## 占位符

未传 `placeholder` 时，按 `menuSources` 中**实际存在的类型**动态拼接提示行（没有对应资源就不显示该行），最后一行始终保留：

```
输入 "/" 唤出 Skill，工具，MCP        // menuSources 含 skill / tool / mcp 任一
输入 "@" 唤出会话产物，知识库          // 含 knowledgebase / doc / artifact 任一
输入 "\" 唤出 Prompt                  // 含 prompt
通过 Shift + Enter 进行换行输入        // 始终显示
```

显式传入 `placeholder`（含空字符串）时完全覆盖上述文案，支持用 `\n` 换行。

## 发送状态（messageStatus）

`messageStatus` 控制底部按钮渲染，但**输入框为空且没有附件时始终置灰禁用**，无论传入什么值。

| `messageStatus`                      | 有内容或已有附件                                       | 空且无附件               |
| ------------------------------------ | ------------------------------------------------------ | ------------------------ |
| `complete` / `stop` / `error`        | 蓝色发送按钮，点击触发 `onSendMessage`                 | 灰色禁用                 |
| `streaming` / `pending` / `fetching` | 蓝色停止按钮（Loading 图标），点击触发 `onStopSending` | 蓝色停止按钮（仍可点击） |
| `disabled`                           | 灰色禁用，点击无效                                     | 灰色禁用                 |

内部由 `messageState` 计算：`pending` / `streaming` / `fetching` 直接沿用传入状态（保证停止按钮始终可用）；否则**已有上传附件即视为可发送**（纯附件消息无需文字）；再否则输入为空或仅空白字符时强制为 `disabled`。`fetching` 时按 Enter **不会**触发发送，避免请求中重复提交。

### onSendMessage 第三参数 options（UserQuestion 上下文）

`ChatInput` 自身调用 `onSendMessage` 时只传前两个参数。当组件被 [ChatContainer](/components/setup/chat-container) 包裹且存在待回答 `UserQuestion` 中断时，容器会在用户点击发送时注入第三个参数：

| 字段        | 类型              | 说明                                                             |
| ----------- | ----------------- | ---------------------------------------------------------------- |
| `interrupt` | `Interrupt`       | 当前激活的 `UserQuestionInterrupt`                               |
| `payload`   | `InterruptResume` | skip resume（`status: 'cancelled'`，`payload.answers` 为空数组） |

此场景下容器**不会**自动清空 `modelValue`，业务侧需在 `onSendMessage` 内自行处理消息发送与 `resumeAgent` 的先后顺序。结构化作答仍通过 `UserQuestionCard` → `onInterruptResume` 完成。

```typescript
const handleSendMessage = async (
  content: UserMessage['content'],
  docSchema: TagSchema,
  options?: { interrupt?: Interrupt; payload?: InterruptResume },
) => {
  if (options?.interrupt && options?.payload) {
    await resumeAgent({ interruptId: options.interrupt.id, resume: options.payload });
    return;
  }
  await sendMessage(content, docSchema);
};
```

### sendDisabledTip（业务阻塞发送）

需要临时阻止发送但仍允许输入时传入 `sendDisabledTip`：置灰发送按钮、按钮 tooltip 展示该文案，并拦截点击发送、Enter 发送与 `triggerSendMessage()`。

## 引用消息（v-model:cite）

通过 `v-model:cite` 绑定引用内容，引用区显示在编辑器上方，用户可点击关闭取消引用。发送时引用内容需自行读取 `cite` 变量，`onSendMessage` 的 `content` 不包含它。

```vue
<template>
  <ChatInput
    v-model="inputValue"
    v-model:cite="citeContent"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
  />
</template>

<script setup lang="ts">
  const handleSendMessage = async (content: string) => {
    console.log('引用内容:', citeContent.value);
    citeContent.value = ''; // 发送后自行清空
  };
</script>
```

## 快捷指令

`shortcuts` 传入列表，底部工具栏展示快捷指令按钮；`shortcutId` 控制选中态：

- `shortcutId` 为空 → 显示全部快捷指令按钮
- `shortcutId` 命中某个 `shortcut.id` → 收起列表，显示已选指令 + 关闭图标

```vue
<template>
  <ChatInput
    v-model="inputValue"
    :shortcuts="shortcuts"
    :shortcut-id="selectedShortcutId"
    :on-send-message="handleSendMessage"
    @select-shortcut="selectedShortcutId = $event.id"
    @delete-shortcut="selectedShortcutId = ''"
  />
</template>
```

## 文件上传 {#file-upload}

`supportUpload` 默认 `true`。文件入口有三条路径：**+ 号菜单的「文件」项**、**拖拽到输入框**、**粘贴（Ctrl+V）**。

- `onUpload` 一次选择传入**全部** `File[]`，返回同序的结果数组（也可对单文件返回单个对象）；元素为 `{ download_url?: string; id?: string; status?: 'failed' | 'success' }`
- 文件自动去重（基于 `name + size + lastModified` 复合键），不会重复上传
- **上传中或存在失败附件时禁止发送**（点击、Enter、`triggerSendMessage` 均拦截）。失败附件需用户删除后才能再发；不要把附件 Pending 映射成 `MessageStatus.Pending`
- 拖拽只响应从系统拖入的文件（编辑器内部标签拖动不会误触发），悬停时框体切换为蓝色描边 + 浅蓝底
- 发送成功后待发送列表自动清空；文件加入列表后光标自动回到输入区

**个数与大小校验**：

- 列表最多保留 **`MAX_UPLOAD_FILES`（9）** 个待发送附件；已满时再次选择/拖入/粘贴文件会弹出 **bkui-vue `Message` 错误提示**（`formatUploadNotAddedMessage`），且不会继续入队。
- 在未满的前提下：空文件、单文件大小 **`>= MAX_UPLOAD_FILE_SIZE`（约 2.4MB）** 会被跳过并弹出超大小/个数提示。与已有文件重复的项只去重、不弹这条误导文案。
- 个数上限、重复与大小校验都在 `ChatInput` 的 `handleUpload` 中统一处理（含 + 号菜单唤起的系统文件选择器、拖拽和粘贴）。

**发送内容格式**（有文件时 `content` 变为数组）：

```typescript
[
  { type: 'binary', url: '...', mimeType: 'image/png', filename: 'a.png', size: 10240 },
  { type: 'binary', url: '...', mimeType: 'application/pdf', filename: 'b.pdf', size: 20480 },
  // 输入框有实际文字时才追加文本段，纯附件消息不带空文本
  { type: 'text', text: '请帮我分析这两个文件' },
];
```

```vue
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

  // 一次选择多个文件只回调一次，按文件顺序返回结果
  const handleUpload = async (files: File[]) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    return res.json(); // ChatInputUploadResult[]
  };
</script>
```

### 预设上传文件（defaultUploadFiles）

设置初始已上传文件，出现在文件预览区并随下次发送一起携带：

```typescript
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
```

## 模型选择

传入 `models` 后在发送按钮左侧展示 [ModelSelector](/components/input/model-selector)。选中值（模型的 `llm_name`）通过 `v-model:selected-model` 双向绑定，`@model-change` 可获取完整模型对象，能力标签由组件依据 `property` 自动派生。

```vue
<template>
  <ChatInput
    v-model="inputValue"
    v-model:selected-model="selectedModel"
    :models="models"
    :on-send-message="handleSendMessage"
    @model-change="handleModelChange"
  />
</template>
```

也可通过 `#model-selector` 插槽完全自定义，插槽参数为 `{ models, selectedModel }`：

```vue
<template>
  <ChatInput v-model="inputValue" :models="models">
    <template #model-selector="{ models, selectedModel }">
      <span>当前：{{ selectedModel || '未选择' }}（共 {{ models.length }} 个）</span>
    </template>
  </ChatInput>
</template>
```

## 自定义插槽

```vue
<template>
  <ChatInput v-model="inputValue" :on-send-message="handleSendMessage">
    <!-- 框体外顶部，适合展示模型信息、Token 消耗 -->
    <template #top>
      <div class="input-tips">当前模型: GPT-4 · 剩余 Token: 12,800</div>
    </template>

    <!-- 框体外顶部，适合展示中断、审批提示 -->
    <template #interrupt>
      <div class="input-alert">当前会话有待审批单，暂时不能继续发送</div>
    </template>

    <!-- 替换引用区 -->
    <template #input-header>
      <div class="custom-header">自定义头部内容</div>
    </template>

    <!-- 替换文件预览区，接收 files 参数 -->
    <template #files="{ files }">
      <span v-for="file in files" :key="file.filename">{{ file.filename }}</span>
    </template>

    <!-- 替换快捷指令区（+ 号仍在左侧） -->
    <template #attachment>
      <button @click="handleCustomAction">自定义操作</button>
    </template>

    <!-- 替换发送按钮图标（点击逻辑不变） -->
    <template #send-icon>
      <span>🚀</span>
    </template>
  </ChatInput>
</template>
```

## Expose（模板引用）

```vue
<template>
  <ChatInput ref="chatInputRef" v-model="inputValue" :on-send-message="handleSendMessage" />
  <button @click="chatInputRef?.focus()">聚焦输入框</button>
  <button @click="chatInputRef?.insertMention({ id: 'output-1', type: 'artifact', name: '巡检报告.pdf' })">
    引用产物
  </button>
</template>

<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { ChatInput } from '@blueking/chat-x';

  const chatInputRef = useTemplateRef<InstanceType<typeof ChatInput>>('chatInputRef');
</script>
```

> 在 [ChatContainer](/components/setup/chat-container) 内部时，消息区与侧栏可以直接用 [useInputMention](/composables/use-input-mention) 把资源「@ 进输入框」，无需自行持有 `ChatInput` 实例。

## API

### Props

| 属性名             | 类型                                                 | 默认值   | 必填 | 说明                                                                 |
| ------------------ | ---------------------------------------------------- | -------- | ---- | -------------------------------------------------------------------- |
| modelValue         | `string \| TagSchema`                                | -        | ✅   | 编辑器的值，支持 `v-model`                                           |
| menuSources        | `IInputMenuItem[]`                                   | `[]`     | -    | 统一菜单数据源，按 `type` 分发到 `/` `@` `\` 与 + 号                 |
| menuGroupItemLimit | `number`                                             | `4`      | -    | 每个分组默认展示条数，超出折叠为「更多 +N」                          |
| selectedModel      | `string`                                             | -        | -    | 当前选中模型的 `llm_name`，支持 `v-model:selected-model`             |
| cite               | `string`                                             | `''`     | -    | 引用内容，支持 `v-model:cite`，不为空时显示引用区                    |
| messageStatus      | `MessageStatus`                                      | -        | -    | 消息状态，控制按钮；输入为空且无附件时内部强制 `disabled`            |
| shortcuts          | `Shortcut[]`                                         | -        | -    | 快捷指令列表，显示在底部工具栏                                       |
| shortcutId         | `string`                                             | -        | -    | 当前选中的快捷指令 ID，命中时列表收起为已选样式                      |
| models             | `IModelOption[]`                                     | -        | -    | 可选模型列表，非空时在发送按钮左侧展示模型选择器                     |
| placeholder        | `string`                                             | 动态默认 | -    | 编辑器占位符，支持多行；未传时按 `menuSources` 的类型动态拼接        |
| inputMaxHeight     | `number`                                             | `280`    | -    | 框体最大高度（px），有文件时自动叠加文件预览区高度                   |
| defaultUploadFiles | `UploadFile[]`                                       | -        | -    | 预设已上传的文件列表                                                 |
| sendDisabledTip    | `string`                                             | -        | -    | 阻塞发送时的 tooltip；传入后点击、Enter 与 `triggerSendMessage()` 均不发送 |
| supportUpload      | `boolean`                                            | `true`   | -    | 是否开启上传能力（内置「文件」菜单项、拖拽与粘贴）                   |
| tippyOptions       | `AITippyProps`                                       | -        | -    | 透传给 AddMenuBtn、InputAttachment、ModelSelector 的 tooltip 配置    |
| onSendMessage      | `(content: UserMessage['content'], docSchema: TagSchema, options?: { interrupt?: Interrupt; payload?: InterruptResume }) => Promise<void>` | - | - | 发送回调；无文件时 `content` 为字符串，有文件时为数组；第三参数由 [ChatContainer](/components/setup/chat-container) 在 UserQuestion 场景注入 |
| onStopSending      | `() => Promise<void>`                                | -        | -    | 停止发送回调                                                         |
| onUpload           | `(files: File[]) => Promise<ChatInputUploadResult \| ChatInputUploadResult[]>` | -        | -    | 文件上传回调（一次选择批量传入）；上传中/失败附件会阻塞发送 |

### Events

| 事件名            | 参数                                                                  | 触发时机                                                     |
| ----------------- | --------------------------------------------------------------------- | ------------------------------------------------------------ |
| update:modelValue | `(value: string \| TagSchema, selectedResourceList: IInputMenuItem[])` | 编辑器值变化；第二参数为文档中能在 `menuSources` 反查到的条目 |
| modelChange       | `(model: IModelOption)`                                               | 用户切换模型                                                 |
| selectShortcut    | `(shortcut: Shortcut)`                                                | 点击底部快捷指令按钮                                         |
| deleteShortcut    | -                                                                     | 点击已选快捷指令旁的关闭按钮                                 |

### Slots

| 插槽名         | 参数                                                             | 说明                                                     |
| -------------- | ---------------------------------------------------------------- | -------------------------------------------------------- |
| top            | -                                                                | 框体外部顶部，适合展示模型 / Token 信息                  |
| interrupt      | -                                                                | 框体外部顶部，位于 `top` 之后，适合展示审批 / 中断提示   |
| input-header   | -                                                                | 框体内顶部，替换引用区（`CiteContent`）                  |
| files          | `{ files: Partial<UploadFile>[] }`                               | 文件预览区                                               |
| attachment     | -                                                                | 底部快捷指令区，`AddMenuBtn` 在其左侧，不受此插槽影响    |
| model-selector | `{ models: IModelOption[]; selectedModel: string \| undefined }` | 发送按钮左侧模型选择区，默认渲染 `ModelSelector`         |
| send-icon      | -                                                                | 发送按钮内图标，点击逻辑与样式仍由组件控制               |

### Expose

| 方法名             | 类型                              | 说明                                             |
| ------------------ | --------------------------------- | ------------------------------------------------ |
| focus              | `() => void`                      | 聚焦编辑器并把光标置于末尾                       |
| insertMention      | `(item: IInputMenuItem) => void`  | 把条目以标签形式追加到文档末尾（不依赖当前光标） |
| triggerSendMessage | `() => void`                      | 手动触发发送逻辑                                 |

## 键盘快捷键

| 快捷键          | 说明                                             |
| --------------- | ------------------------------------------------ |
| `Enter`         | 发送消息；菜单展开时改为选中当前高亮条目         |
| `Shift + Enter` | 换行                                             |
| `/` `@` `\`     | 唤出对应菜单                                     |
| `↑` / `↓`       | 在菜单条目间导航                                 |
| `Esc`           | 关闭菜单                                         |

> 点击输入区之外（`mousedown` 捕获阶段）同样会关闭菜单。

## 类型定义

> `MessageStatus` 完整取值见 [常量枚举](../../types/constants)。与输入区相关：`pending` / `streaming` / `fetching` → 停止按钮；`complete` / `completed` / `error` / `stop` → 发送；`disabled` → 置灰。

```typescript
import type { Component } from 'vue';

// 菜单可选项类型；file 为组件内置动作项，不由业务方提供
type MenuItemType = 'file' | 'skill' | 'mcp' | 'tool' | 'knowledgebase' | 'doc' | 'artifact' | 'prompt';

// 菜单触发方式；plus 由左下角 + 号唤起
type MenuTrigger = '/' | '@' | '\\' | 'plus';

interface IInputMenuItem {
  id: string;
  name: string;
  type: MenuItemType;
  /** Prompt 全文；选中 prompt 时整体替换输入框内容 */
  content?: string;
  /** 描述文案，有值时 hover 弹出气泡说明 */
  description?: string;
  disabled?: boolean;
  /** 图标 URL 或 Vue 组件；缺省按 type 回退，artifact 按文件名后缀推导 */
  icon?: Component | string;
}

// 上传状态
enum UploadStatus {
  Pending = 'pending',
  Success = 'success',
  Error = 'error',
}

// 上传文件
type UploadFile = {
  type: 'binary';
  url?: string;
  filename?: string;
  mimeType?: string;
  file?: File;
  status?: UploadStatus;
};

// onSendMessage 的 content 参数
type SendContent =
  | string
  | Array<
      { type: 'binary'; url?: string; mimeType: string; filename: string; size?: number } | { type: 'text'; text: string }
    >;

// onSendMessage 完整签名（第三参数由 ChatContainer 在 UserQuestion 场景注入）
type OnSendMessage = (
  content: SendContent,
  docSchema: TagSchema,
  options?: { interrupt?: Interrupt; payload?: InterruptResume },
) => Promise<void>;
```

## 关联组件

- [AiSlashInput](/components/input/ai-slash-input) — 内部富文本编辑区与标签插入
- [InputMenuPanel](/components/input/input-menu-panel) — 统一菜单面板与分组折叠逻辑
- [AddMenuBtn](/components/input/add-menu-btn) — 左下角 + 号聚合菜单入口
- [MentionTag](/components/rendering/mention-tag) — 编辑器与消息中的资源标签
- [ModelSelector](/components/input/model-selector) — 模型下拉选择器
- [ShortcutBtns](/components/input/shortcut-btns) / [ShortcutBtn](/components/input/shortcut-btn) — 快捷指令按钮
- [CiteContent](/components/rendering/cite-content) — 引用区内容展示
- [ChatContainer](/components/setup/chat-container) — 顶层布局中包裹输入区
- [useInputMention](/composables/use-input-mention) — 从消息区 / 侧栏把资源插入输入框
