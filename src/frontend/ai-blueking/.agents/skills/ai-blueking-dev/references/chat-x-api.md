# @blueking/chat-x 组件 API 参考

> **约定**：以下 API 以仓库内 `packages/chat-x/src` 源码为准；发布包以 `dist` 为准。若二者不一致，以当前分支源码为准。

## 包入口导出概要

- `export *`：`ag-ui/types`、`common`、`components`、`composables`、`directives`、`edix`、`icons`、`lang/lang`、`plugins`、`types`、`utils`
- **对外组件**：见 `src/components/index.ts`（下文「组件导入」完整列表）
- **未从 `composables/index.ts` 再导出的内部能力**：如 `composables/use-common.ts`（`useKeywordProvider` 等）需深路径引用，一般不写入应用侧文档

---

## 组件导入

```typescript
import {
  // 聊天主容器（组合 MessageContainer + ChatInput + 侧栏执行情况等）
  ChatContainer,

  // 核心组件
  ChatInput,
  MessageContainer,
  MessageRender,
  ContentRender,
  ShortcutBtns,
  ShortcutBtn,
  ShortcutRender,
  AiSelection,

  // 消息工具 / 执行摘要 / 预览等
  ExecutionSummary,
  HighlightKeyword,
  MessageLoading,
  MessageTools,
  MessageUserFeedback,
  SelectionFooter,
  ToolCallRender,

  // 图片预览
  AiImage,
  ImagePreview,
  ImagePreviewGroup,

  // 枚举和类型
  MessageRole,
  MessageStatus,
  MessageToolsStatus,
  MessageContentType,
  type Message,
  type UserMessage,
  type Shortcut,
  type ShortcutComponent,
  type TagSchema,
  type IToolBtn,

  // 常量（来自 common，经包入口导出）
  CONST_MESSAGE_TOOLS,
  CONST_USER_MESSAGE_TOOLS,
  CONST_UPDATE_TOOLS,

  // 消息分组（MessageContainer 必填）
  useMessageGroup,
  type MessageGroup,
} from '@blueking/chat-x';
```

---

## ChatContainer 聊天主容器

`ChatContainer` 将消息区、输入区、快捷指令表单、分享底栏、执行情况侧栏等组合为一块；`ai-blueking` 的 `ChatBot` 内部主要使用此组件。

### Props（交集类型）

等于 **`ChatContainerProps` ∪ `ChatInputProps` ∪ `Omit<MessageContainerProps, 'enableSelection' | 'messageGroups' | 'messageToolsTippyOptions'>`**。

| 来源 | 主要字段 | 说明 |
|------|-----------|------|
| ChatContainerProps | `chatLoading?`、`commonTippyOptions?`、`onCustomTabChange?`、`openingRemark?`、`placement?`（默认 `'left'`） | 侧栏 Tab、欢迎语、全局 tippy |
| ChatInputProps | 同 [ChatInput](#chatinput-聊天输入框) | 内部透传 `ChatInput` |
| MessageContainerProps（省略项由容器内部注入） | `messages`、`messageStatus?`、`messageToolsStatus?`、`onAgentAction?`、`onAgentFeedback?`、`onUserAction?`、`onUserInputConfirm?`、`onUserShortcutConfirm?` 等 | `enableSelection` / `messageGroups` 由内部 `useMessageGroup` 管理 |

### v-model

| 绑定名 | 类型 | 说明 |
|--------|------|------|
| selectedShortcut | `Shortcut \| null` | 当前选中的快捷指令（有 `components` 时显示 `ShortcutRender`） |
| cite | `string` | 引用文本，与 `ChatInput` 的 `v-model:cite` 一致 |

### Events

包含 **`ChatInputEmits` ∪ `MessageContainerEmits`**，并额外：

| 事件名 | 参数 | 说明 |
|--------|------|------|
| shortcutClose | - | 快捷指令表单关闭 |
| shortcutSubmit | `formModel: Record<string, unknown>` | 快捷指令表单提交 |
| confirmShare | `messages: Message[]` | 确认分享（选中用户消息） |
| collapseChange | `isCollapse: boolean, resizeAsideWidth: number` | 侧栏折叠与宽度变化 |

### Slots

| 插槽名 | 作用域参数 | 说明 |
|--------|------------|------|
| codeHeader | `{ language, token }` | Markdown 代码块头部（透传至消息渲染） |
| default | 含 `messages`、`messageGroups`、`selectedUserMessages`、`isShareMode`、`handleAgentAction` 等 | 完全自定义主消息区时替换默认 `MessageContainer` |
| message | `{ message, messageToolsStatus }` | 单条消息自定义 |
| welcome | `{ openingRemark }` | 无消息时的欢迎区 |

### Expose

| 名称 | 说明 |
|------|------|
| selectedTab | 当前 Tab 状态 |
| addCustomTab / removeCustomTab / selectCustomTab | 自定义 Tab（如 flow 节点详情） |
| enterShareMode / exitShareMode | 进入 / 退出分享多选模式 |

---

## ChatInput 聊天输入框

### Props

| 属性名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| modelValue | `string \| TagSchema` | - | **必填**，支持 v-model |
| cite | `string` | `''` | 引用内容，`v-model:cite` |
| messageStatus | `MessageStatus` | - | 控制发送/停止等按钮状态 |
| placeholder | `string` | 见下方 | 占位符 |
| prompts | `string[]` | `[]` | `/` 触发 |
| resources | `IAiSlashMenuItem[]` | `[]` | `@` 触发 |
| shortcuts | `Shortcut[]` | - | 快捷指令列表 |
| shortcutId | `string` | - | 当前选中快捷指令 ID（通常与外层 `selectedShortcut` 同步） |
| supportUpload | `boolean` | `true` | 是否显示上传按钮 |
| inputMaxHeight | `number` | `200` | 输入区最大高度（px） |
| defaultUploadFiles | `UploadFile[]` | - | 初始已上传文件列表 |
| tippyOptions | `AITippyProps` | - | 附件区 Tippy 配置 |
| onSendMessage | `(value: UserMessage['content'], docSchema: TagSchema) => Promise<void>` | - | 发送 |
| onStopSending | `() => Promise<void>` | - | 停止 |
| onUpload | `(files: File) => Promise<{ download_url?: string }>` | - | 上传（参数为 `File`，非数组） |

**默认占位符（中文）**：

```
输入 “/”唤出 Prompt
输入“@”唤出 工具 和 MCP
通过 Shift + Enter 进行换行输入
```

### Events

| 事件名（camelCase / 模板 kebab-case） | 参数 | 说明 |
|--------------------------------------|------|------|
| selectShortcut | `shortcut: Shortcut` | 选择快捷指令 |
| deleteShortcut | - | 删除当前快捷指令 |
| update:modelValue | `value, selectedResourceList: IAiSlashMenuItem[]` | v-model 更新 |

### Slots

| 插槽名 | 说明 |
|--------|------|
| top | 容器顶部 |
| input-header | 头部，默认展示引用 |
| files | 作用域 `{ files }`，自定义已选文件列表区域 |
| attachment | 底部附件条（默认含上传、快捷按钮等） |
| send-icon | 发送按钮图标 |

### Expose

| 方法 | 说明 |
|------|------|
| focus | 聚焦输入 |
| triggerSendMessage | 与内部发送逻辑一致，用于程序化触发发送 |

---

## MessageContainer 消息容器

### Props

| 属性名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| messages | `Message[]` | - | **必填**，原始消息列表 |
| messageGroups | `MessageGroup[]` | - | **必填**，分组后的列表（通常由 `useMessageGroup` 得到） |
| messageStatus | `MessageStatus` | - | 流式/停止按钮等 |
| messageToolsStatus | `MessageToolsStatus` | - | 工具栏 `Disabled` / `Hidden` |
| messageToolsTippyOptions | `MessageToolsProps['tippyOptions']` | - | 消息工具 Tippy |
| enableSelection | `boolean` | `false` | 多选（分享） |
| onAgentAction | `(tool, messages) => Promise<string[] \| void>` | - | AI 组工具：点赞/点踩时可返回原因列表 |
| onAgentFeedback | `(tool, messages, reasonList, otherReason) => void` | - | 反馈提交 |
| onUserAction | `(tool, message) => Promise<string[] \| void>` | - | 用户消息工具 |
| onUserInputConfirm | `(message, content, docSchema) => Promise<void>` | - | 编辑用户消息确认 |
| onUserShortcutConfirm | `(message, formModel) => Promise<void>` | - | 快捷表单确认 |

### v-model

| 绑定名 | 类型 | 说明 |
|--------|------|------|
| selectedUserMessages | `Message[]` | 分享模式下选中的消息（模板：`v-model:selected-user-messages`） |

### Events

| 事件名 | 说明 |
|--------|------|
| stopStreaming | 点击「停止生成」 |

### Slots

| 插槽名 | 作用域参数 | 说明 |
|--------|------------|------|
| default | `{ message, messageToolsStatus }` | 自定义单条消息（默认渲染 `MessageRender`） |

### Expose

组件 **未** `defineExpose`。全选/分享相关状态请使用 **`useMessageGroup`**（在 `ChatContainer` 内已接好）或自行组合。

### 与 useMessageGroup

```typescript
const messages = computed(() => message.list.value);
const selectedUserMessages = ref<Message[]>([]);
const keyword = shallowRef(''); // 可选，执行情况搜索关键词

const { messageGroups } = useMessageGroup({
  keyword,
  messages,
  selectedUserMessages,
});
```

---

## MessageRender 消息渲染器

### Props（节选）

`Partial<UserMessageActionsProps> & Pick<MessageToolsProps, 'onAction' | 'tippyOptions'> & { message: Partial<Message> }`，含 `messageToolsStatus`、`onInputConfirm`、`onShortcutConfirm` 等（与 `UserMessage` 工具栏、编辑态一致）。

### Slots

| 插槽名 | 作用域参数 | 说明 |
|--------|------------|------|
| default | `{ content, status }`（Assistant） | 自定义 Assistant 正文 |
| codeHeader | `{ language, token }` | 代码块头部 |

### 消息类型映射（常见）

| MessageRole | 渲染 |
|-------------|------|
| User | UserMessage |
| Assistant | AssistantMessage + ContentRender |
| Reasoning | ReasoningMessage |
| Tool | ToolMessage |
| Info | InfoMessage |
| Activity | ActivityMessage |
| Loading | LoadingMessage |

---

## ContentRender 内容渲染器

泛型组件：`content` 类型随 `ContentType` / `type` 变化；常见用法为字符串 Markdown（默认按 Text 处理）。

### Props

| 属性名 | 类型 | 说明 |
|--------|------|------|
| content | `ContentMap[T]` | 内容 |
| status | `MessageStatus` | 可选 |
| type | `T extends ContentType` | 可选，用于区分内容形态 |

### Slots

| 插槽名 | 说明 |
|--------|------|
| default | `{ content }` |
| codeHeader | `{ language, token }` |

---

## AiSelection AI 划词选择

### Props

| 属性名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| visible | `boolean` | - | **必填**，`v-model:visible` |
| shortcuts | `Shortcut[]` | 内置默认 | 快捷列表 |
| maxShortcutCount | `number` | `3` | 最多展示数量 |
| offset | `number` | `10` | 偏移 |
| excludeSelectors | `string[]` | `[]` | 在这些选择器内部不弹出 |

### Events

| 事件名 | 参数 | 说明 |
|--------|------|------|
| selectShortcut | `(shortcut, text: string)` | 选择快捷指令 |
| selectionChange | `(text: string)` | 选区变化 |

### Slots

| 插槽名 | 参数 | 说明 |
|--------|------|------|
| default | `{ shortcuts }` | 自定义弹层内容 |

---

## ShortcutRender 快捷指令表单

### Props

`Partial<Shortcut>`（如 `name`、`components`、`formModel`、`description` 等）。

### Events

| 事件名 | 参数 | 说明 |
|--------|------|------|
| close | - | 关闭 |
| submit | `formModel` | 提交 |

---

## ShortcutBtns / ShortcutBtn

- **ShortcutBtns**：`shortcuts: Shortcut[]`，`selectShortcut` 事件。
- **ShortcutBtn**：单个快捷按钮；`mode`、`shortcut` 等 props，暴露 `$el`。

---

## 其他导出组件（简表）

| 组件 | 用途 |
|------|------|
| ExecutionSummary | 执行情况摘要 Tab 内容 |
| HighlightKeyword | 关键词高亮 |
| MessageLoading | 加载动画 |
| MessageTools | 消息工具条（内置 `CONST_MESSAGE_TOOLS` + `CONST_UPDATE_TOOLS`） |
| MessageUserFeedback | 点赞/点踩原因表单 |
| SelectionFooter | 分享模式底栏 |
| ToolCallRender | 工具调用展示 |
| ImagePreview / ImagePreviewGroup / AiImage | 图片预览 |

---

## 类型定义

### Message / BaseMessage（与源码一致，节选）

```typescript
interface BaseMessage<T extends MessageType, C = string> {
  id: number | string;
  messageId: number | string;
  role: T;
  content: C;
  status: MessageStatus;
  name?: string;
  property?: {
    extra?: {
      cite: string | { type: 'structured'; title: string; data: { key: string; value: string }[] };
      command: string;
      context: Partial<{ /* ... */ } & Partial<OldShortcut>>[];
      pause?: boolean;
      shortcut?: Partial<Shortcut>;
    };
  };
}

type UserMessage = BaseMessage<MessageRole.User, InputContent[] | string>;
// AssistantMessage / ReasoningMessage / ToolMessage 等见 ag-ui/types/messages.ts
```

`ToolMessage` 中 `error?: boolean | string`。

### IToolBtn 工具按钮

当前为**单一接口**，`id` 为图标映射表中的 key（含 `activeLike`、`activeUnLike` 等），**非**历史上的联合类型 + 类型守卫。

```typescript
interface IToolBtn {
  description?: string;
  id: keyof typeof ToolIconsMap; // 如 copy、cite、rebuild、share、like、unlike、edit、delete、activeLike、activeUnLike
  name?: string;
}
```

业务侧按 `tool.id === 'delete'` 等分支处理即可；**不存在** `isBuiltinTool` / `isEditConfirmTool` 导出。

### Shortcut

```typescript
interface Shortcut {
  id: string;
  name: string;
  alias?: string;
  key?: string;
  icon?: string | VNode | ((h: typeof import('vue').h) => Component | VNode);
  description?: string;
  components?: ShortcutComponent[];
  formModel?: Record<string, unknown>;
}
```

### ShortcutComponent

为 **联合类型**，`type` 常见取值：`input`、`textarea`、`select`、`checkboxGroup`、`number`、`radioGroup`、`switcher`、`text` 等（见 `types/shortcut.ts`），而非单一的 `checkbox`。

### TagSchema

见 `types/input.ts`；结构与文档化二维数组一致。

---

## 枚举定义

### MessageStatus

```typescript
enum MessageStatus {
  Complete = 'complete',
  Disabled = 'disabled',
  Error = 'error',
  Pending = 'pending',
  Stop = 'stop',
  StopLoading = 'stop-loading',
  Streaming = 'streaming',
  Success = 'success',
}
```

### MessageToolsStatus

```typescript
enum MessageToolsStatus {
  Disabled = 'disabled',
  Hidden = 'hidden',
}
```

### MessageRole（完整）

```typescript
enum MessageRole {
  Activity = 'activity',
  Assistant = 'assistant',
  Developer = 'developer',
  Guide = 'guide',
  Hidden = 'hidden',
  HiddenAssistant = 'hidden-assistant',
  HiddenGuide = 'hidden-guide',
  HiddenSystem = 'hidden-system',
  HiddenUser = 'hidden-user',
  Info = 'info',
  Loading = 'loading',
  Pause = 'pause',
  Placeholder = 'placeholder',
  Reasoning = 'reasoning',
  System = 'system',
  TemplateAssistant = 'template-assistant',
  TemplateGuide = 'template-guide',
  TemplateHidden = 'template-hidden',
  TemplateSystem = 'template-system',
  TemplateUser = 'template-user',
  Tool = 'tool',
  User = 'user',
}
```

### MessageContentType

见 `ag-ui/types/constants.ts`：`Binary`、`FlowAgent`、`Function`、`KeyValue`、`KnowledgeRag`、`Other`、`ReferenceDocument`、`Text` 等。

---

## Composables（`composables/index.ts` 导出）

```typescript
import {
  useAnimationText,
  useClipboard,
  useCommandSelection,
  useContainerScrollProvider,
  useContainerScrollConsumer,
  useCustomTabProvider,
  useCustomTabConsumer,
  useGlobalConfig,
  useMenuKeydown,
  useMessageGroup,
  useObserverVisibleList,
  useParentScrolling,
} from '@blueking/chat-x';
```

内部使用滚动：`useContainerScrollProvider(containerRef, bottomRef)` 与 `useContainerScrollConsumer`。

---

## 常量

```typescript
import { CONST_MESSAGE_TOOLS, CONST_USER_MESSAGE_TOOLS, CONST_UPDATE_TOOLS } from '@blueking/chat-x';

// CONST_MESSAGE_TOOLS：AI 消息默认工具 copy / cite / rebuild / share（文案为 i18n 函数结果）
// CONST_USER_MESSAGE_TOOLS：用户消息 copy / cite / edit / delete
// CONST_UPDATE_TOOLS：流式结束后的更新区 like / unlike / delete
```

类型均为 `IToolBtn[]`（`as IToolBtn[]` 断言）。
