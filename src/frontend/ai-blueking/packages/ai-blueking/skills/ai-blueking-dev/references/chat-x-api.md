# @blueking/chat-x 组件 API 参考

> **约定**：以下 API 以仓库内 `packages/chat-x/src` 源码为准；发布包以 `dist` 为准。若二者不一致，以当前分支源码为准。
>
> **当前版本**：`@blueking/chat-x` `0.0.49-beta.1`（含 HITL 中断消息、RenderMode、ModelSelector、字号主题、`#group` 插槽等能力）。

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
  ModelSelector,

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

  // HITL 中断消息组件（human-in-the-loop）
  InterruptMessageRender,       // interrupt-message 默认导出
  UserQuestionCard,
  UserQuestionAnsweredCard,
  UserQuestionChoice,
  UserQuestionOption,
  useUserQuestion,
  buildSkipResumePayload,
  OTHERS_OPTION_LABEL,
  toLetter,

  // Markdown / 内容渲染
  MarkdownContent,
  VNodeRenderer,
  CodeContent,
  ImageContent,
  LatexContent,
  MermaidContent,

  // 其他 UI
  AiLoading,
  ScrollBtn,

  // 枚举和类型
  MessageRole,
  MessageStatus,
  MessageToolsStatus,
  MessageContentType,
  RenderMode,                   // 渲染模式：chat / share / test
  InterruptReason,              // 中断原因：aidev:tool_approval / aidev:user_question
  APPROVAL_STATUS,              // 审批单状态
  type Message,
  type UserMessage,
  type Shortcut,
  type ShortcutComponent,
  type TagSchema,
  type IToolBtn,
  type IModelOption,
  type AiSizeMode,              // 'normal' | 'small'
  type GlobalConfig,
  // 中断协议类型（来自 ag-ui/types/interrupt）
  InterruptResumeOperation,
  type OnInterruptResume,
  type InterruptResume,
  type InterruptMessage,
  type Interrupt,

  // 常量（来自 common，经包入口导出）
  CONST_MESSAGE_TOOLS,
  CONST_USER_MESSAGE_TOOLS,
  CONST_UPDATE_TOOLS,

  // 消息分组（MessageContainer 必填）
  useMessageGroup,
  type MessageGroup,

  // 字号主题 / 全局配置
  useGlobalConfig,
  injectGlobalConfig,
} from '@blueking/chat-x';
```

> **注意**：`ToolApprovalCard`（第三方审批单卡片）由 `InterruptMessageRender` **内部**渲染，**未**从包入口再导出；不要按 `AIDevToolApproval` / `UserQuestion` 之类名字去导入——这些名字不存在。

---

## ChatContainer 聊天主容器

`ChatContainer` 将消息区、输入区、快捷指令表单、分享底栏、执行情况侧栏等组合为一块；`ai-blueking` 的 `ChatBot` 内部主要使用此组件。

### Props（交集类型）

等于 **`ChatContainerProps` ∪ `ChatInputProps` ∪ `Omit<MessageContainerProps, 'enableSelection' | 'messageGroups' | 'messageToolsTippyOptions'>`**。

| 来源 | 主要字段 | 说明 |
|------|-----------|------|
| ChatContainerProps | `chatLoading?`、`commonTippyOptions?`、`executionTabVisible?`（默认 `true`）、`getSideRenderComponent?`、`getSideTabRenderComponent?`、`onCustomTabChange?`、`openingRemark?`、`placement?`（`'left' \| 'right'`，默认 `'left'`）、`resizeProps?`、`size?`（`AiSizeMode`，默认 `'small'`）、`welcomeTitle?` | 侧栏 Tab、欢迎语、全局 tippy、字号主题、侧栏渲染 |
| ChatInputProps | 同 [ChatInput](#chatinput-聊天输入框) | 内部透传 `ChatInput` |
| MessageContainerProps（省略项由容器内部注入） | `messages`、`messageStatus?`、`messageTools?`、`updateTools?`、`messageToolsStatus?`、`onAgentAction?`、`onAgentFeedback?`、`onUserAction?`、`onInterruptResume?`、`onUserInputConfirm?`、`onUserShortcutConfirm?` 等 | `enableSelection` / `messageGroups` / `messageToolsTippyOptions` 由内部 `useMessageGroup` 管理；`messageTools`/`updateTools` 与内置工具按 id 合并 |

> **侧栏渲染是 prop 而非插槽**：`getSideRenderComponent?: (h, props?) => VNode` 与 `getSideTabRenderComponent?: (h, tab, events) => VNode` 的返回结果被渲染进内部 `#aside` 区域（不存在 `#headerLeft` / 侧栏插槽）。

### v-model

| 绑定名 | 类型 | 说明 |
|--------|------|------|
| renderMode | `RenderMode` | 渲染模式（默认 `RenderMode.Chat`），见 [RenderMode 渲染模式](#rendermode-渲染模式chatsharetest)；内部 `useRenderModeProvider` 下发 |
| selectedShortcut | `Shortcut \| null` | 当前选中的快捷指令（有 `components` 时显示 `ShortcutRender`） |
| cite | `string` | 引用文本，与 `ChatInput` 的 `v-model:cite` 一致 |
| selectedModel | `string` | 当前选中模型的 `llm_name`（透传 ChatInput / ModelSelector） |

### Events

包含 **`ChatInputEmits` ∪ `MessageContainerEmits`**，并额外：

| 事件名 | 参数 | 说明 |
|--------|------|------|
| shortcutClose | - | 快捷指令表单关闭 |
| shortcutSubmit | `formModel: Record<string, unknown>` | 快捷指令表单提交 |
| confirmShare | `messages: Message[], source?: IToolBtn` | 确认分享/多选；`source` 为触发按钮（内置 `share` 或 `triggerSelection` 自定义按钮） |
| collapseChange | `isCollapse: boolean, resizeAsideWidth: number` | 侧栏折叠与宽度变化 |
| modelChange | `model: IModelOption` | 切换模型（透传 ChatInput） |

### Slots

| 插槽名 | 作用域参数 | 说明 |
|--------|------------|------|
| codeHeader | `{ language, token }` | Markdown 代码块头部（透传至消息渲染） |
| default | 含 `messages`、`messageGroups`、`selectedUserMessages`、`isShareMode`、`handleAgentAction`、`onInterruptResume?` 等 | 完全自定义主消息区时替换默认 `MessageContainer` |
| group | `{ group }` | **新增** 自定义消息「分组」渲染，透传给内部 `MessageContainer` 的 `#group`（详见 [#group 插槽](#group-插槽消息分组自定义)） |
| message | `{ message, messageToolsStatus, onInterruptResume? }` | 单条消息自定义（作用域含 `onInterruptResume`） |
| interruptQuestion | `{ question, qIndex, answer, setAnswer, confirm }` | **新增** 自定义 UserQuestion 交互题（浮层渲染在 chat-input 上方），等价于 `UserQuestionCardSlots['question']` |
| welcome | `{ openingRemark, welcomeTitle }` | 无消息时的欢迎区 |

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
| resources | `IAiSlashMenuItem[]` | `[]` | `@` / `/` 触发的资源（工具、MCP 等） |
| skills | `ISkillListItem[]` | `[]` | Skill 列表（`/` 唤出） |
| shortcuts | `Shortcut[]` | - | 快捷指令列表 |
| shortcutId | `string` | - | 当前选中快捷指令 ID（通常与外层 `selectedShortcut` 同步） |
| supportUpload | `boolean` | `true` | 是否显示上传按钮 |
| models | `IModelOption[]` | - | 可选模型列表；传入后在发送按钮左侧展示 ModelSelector |
| sendDisabledTip | `string` | - | 发送按钮禁用时的提示 |
| inputMaxHeight | `number` | `200` | 输入区最大高度（px） |
| defaultUploadFiles | `UploadFile[]` | - | 初始已上传文件列表 |
| tippyOptions | `AITippyProps` | - | 附件区 Tippy 配置 |
| onSendMessage | 见下方 | - | 发送（第三参可携带中断/resume） |
| onStopSending | `() => Promise<void>` | - | 停止 |
| onUpload | `(files: File) => Promise<{ download_url?: string }>` | - | 上传（参数为 `File`，非数组） |

> 底层编辑器为 **`AiSlashInput`**（`/` 唤起 Skill 菜单，基于 `edix` schema 的富文本）。

**`onSendMessage` 完整签名**（第三个 `options` 参数是 HITL 关键）：

```typescript
onSendMessage?: (
  message: UserMessage['content'],
  docSchema: TagSchema,
  options?: { interrupt?: Interrupt; payload?: InterruptResume },
) => Promise<void>;
```

即：普通「发送」可同时承载一次中断响应（resume）——例如用户不点选项、直接在输入框打字来回答 `UserQuestion`，此时 `options.interrupt` / `options.payload` 会随发送回传。

**默认占位符（中文）**：

```
输入 “/”唤出 Prompt
输入“@”唤出 工具 和 MCP
通过 Shift + Enter 进行换行输入
```

### v-model（模型）

| 绑定名 | 类型 | 说明 |
|--------|------|------|
| selectedModel | `string` | 当前选中模型的 `llm_name` |

### Events

| 事件名（camelCase / 模板 kebab-case） | 参数 | 说明 |
|--------------------------------------|------|------|
| selectShortcut | `shortcut: Shortcut` | 选择快捷指令 |
| deleteShortcut | - | 删除当前快捷指令 |
| update:modelValue | `value, selectedResourceList: IAiSlashMenuItem[]` | v-model 更新 |
| modelChange | `model: IModelOption` | 切换模型 |

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
| messageTools | `IToolBtn[]` | - | 自定义 AI 主工具组；按 id 与内置 `CONST_MESSAGE_TOOLS` 合并 |
| updateTools | `IToolBtn[]` | - | 自定义反馈工具组；按 id 与内置 `CONST_UPDATE_TOOLS` 合并 |
| messageToolsTippyOptions | `MessageToolsProps['tippyOptions']` | - | 消息工具 Tippy |
| enableSelection | `boolean` | `false` | 多选（分享） |
| renderMode | `RenderMode` | - | 渲染模式（chat/share/test），影响选择、工具、Loading 组等，见 [RenderMode](#rendermode-渲染模式chatsharetest) |
| onAgentAction | `(tool, messages) => Promise<string[] \| void>` | - | AI 组工具：点赞/点踩时可返回原因列表 |
| onAgentFeedback | `(tool, messages, reasonList, otherReason) => void` | - | 反馈提交 |
| onUserAction | `(tool, message) => Promise<string[] \| void>` | - | 用户消息工具 |
| onInterruptResume | `OnInterruptResume` | - | **新增** HITL 中断响应回调（透传给 `MessageRender` / `InterruptMessageRender` / flow-agent 节点重试跳过） |
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
| default | `{ message, messageToolsStatus?, onInterruptResume? }` | 自定义单条消息（默认渲染 `MessageRender`）；作用域新增 `onInterruptResume` |
| group | `{ group }` | **新增（`#group` 插槽）** 自定义整个消息「分组」的渲染，`group` 为 `MessageGroup` |
| answeredQuestion | `{ index, item, status }` | **新增** 中断消息「已回答内容」回显自定义，透传给内部 `MessageRender` → `InterruptMessageRender` → `UserQuestionAnsweredCard #answer` |

#### `#group` 插槽（消息分组自定义）

来自提交「支持 #group 插槽」。用于以「组」为单位接管渲染（如自定义分组容器、批注、时间线等）；不使用时回退到组件内默认逐条渲染。`ChatContainer` 亦提供同名 `#group` 插槽，向内透传到此处。

```vue
<MessageContainer :message-groups="messageGroups" :messages="messages">
  <template #group="{ group }">
    <MyGroupWrapper :type="group.type">
      <!-- 组内可再自行遍历 group.messages 渲染 -->
    </MyGroupWrapper>
  </template>
</MessageContainer>
```

### Expose

组件 **未** `defineExpose`。全选/分享相关状态请使用 **`useMessageGroup`**（在 `ChatContainer` 内已接好）或自行组合。

### 与 useMessageGroup

**签名**：

```typescript
useMessageGroup(options: {
  keyword?: ShallowRef<string>;            // 可选，执行情况搜索关键词
  messages: ComputedRef<Message[]>;         // 原始消息列表
  renderMode?: MaybeRef<RenderMode>;        // 可选，share 态下不自动追加 Loading 组
  selectedUserMessages: Ref<Message[] | undefined>;
})
```

**返回**：

```typescript
const {
  messageGroups,               // 分组后的 MessageGroup[]
  executionGroups,             // 执行情况（工具调用 / flow-agent）分组
  activeUserQuestionInterrupt, // 最近一条待响应的 UserQuestion 中断（供 chat-input 上方浮层渲染）
  pendingApprovalCount,        // 待审批（AIDev 第三方）中断数量
  pendingApprovalTipText,      // 待审批提示文案
  isShareMode,                 // 分享多选态标志
  isAllSelected,               // 是否全选
  onToggleShareAll,            // 切换全选
  onCancelShare,               // 取消分享
  onConfirmShare,              // 确认分享
} = useMessageGroup({
  keyword,
  messages,
  renderMode,
  selectedUserMessages,
});
```

`MessageGroup` 结构：`{ checked, isHover, messages, pause?, startTime?, type: MessageRole, uid, userMessageTitle? }`。

---

## MessageRender 消息渲染器

### Props（节选）

`Partial<UserMessageActionsProps> & Pick<MessageToolsProps, 'onAction' | 'tippyOptions'> & { message: Partial<Message>; onInterruptResume?: OnInterruptResume }`，含 `messageToolsStatus`、`onInputConfirm`、`onShortcutConfirm` 等（与 `UserMessage` 工具栏、编辑态一致）。`onInterruptResume` 会向下传给 `ActivityMessage`（flow-agent 节点重试/跳过）与 `InterruptMessageRender`。

### Slots

| 插槽名 | 作用域参数 | 说明 |
|--------|------------|------|
| default | `{ content, status }`（Assistant） | 自定义 Assistant 正文 |
| codeHeader | `{ language, token }` | 代码块头部 |
| answeredQuestion | `{ index, item, status }` | **新增** 中断「已回答内容」回显自定义，透传给 `InterruptMessageRender` |

### 消息类型映射（常见）

| MessageRole | 渲染 |
|-------------|------|
| User | UserMessage |
| Assistant | AssistantMessage + ContentRender |
| Reasoning | ReasoningMessage |
| Tool | ToolMessage |
| Info | InfoMessage |
| Activity | ActivityMessage（含 flow-agent） |
| Interrupt | **InterruptMessageRender**（HITL 中断消息） |
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

## RenderMode（渲染模式：chat/share/test）

RenderMode 是一套基于 **provide/inject** 的模式开关，取代旧的临时「分享」流程。

- **下发**：`ChatContainer` 以 `v-model:renderMode` 持有（默认 `RenderMode.Chat`），内部调用 `useRenderModeProvider({ renderMode })` 通过 `RENDER_MODE_TOKEN` 下发；也可直接给 `MessageContainer` 传 `renderMode` prop。
- **读取**：子组件用 `useRenderModeInject()`（返回 `ComputedRef<RenderMode>`，缺省 `RenderMode.Chat`）。

| 模式 | 行为 |
|------|------|
| `Chat` | 正常交互态 |
| `Share`（分享态） | 隐藏输入/交互区（`v-if="renderMode !== RenderMode.Share"`）；`MessageContainer` 过滤 Loading 占位组、收敛选择与工具；审批卡片 `ToolApprovalCard` 的「取消审批」按钮被禁用（`isShareContext`）；flow-agent 隐藏「重试/跳过」仅留「详情」；`useMessageGroup` 不自动追加 Loading 组 |
| `Test` | 隐藏消息工具中的 `share` 工具 |

```typescript
import { useRenderModeInject } from '@blueking/chat-x'; // 深路径：composables/use-common
const renderMode = useRenderModeInject(); // ComputedRef<RenderMode>
```

`ChatContainer` 另暴露 `enterShareMode()` / `exitShareMode()` 用于程序化进入/退出分享多选。

---

## 字号主题（size theme）

`AIBlueking` / `ChatBot` / `ChatContainer` 均支持 `size?: AiSizeMode`（上层透传至 `ChatContainer`），控制全局字号档位：

| 值 | 字号 |
|----|------|
| `'small'`（默认） | 12px |
| `'normal'` | 14px |

- **下发**：容器内 `useGlobalConfig({ size, supportUpload })`（provide `GLOBAL_CONFIG_TOKEN`）。
- **读取**：子组件 `injectGlobalConfig()` 取 `{ size, supportUpload }`。
- **DOM 生效**：容器根节点带 `:data-ai-size="size"`；同时把当前值镜像到 `document.body.dataset.aiSize`，让挂到 body 的浮层（tippy / Teleport）也继承 `--ai-font-size` 等 CSS 变量（卸载时清理）。样式普遍使用 `var(--ai-font-size, 12px)`。

```typescript
export type AiSizeMode = 'normal' | 'small';
export type GlobalConfig = {
  size?: ComputedRef<AiSizeMode>;
  supportUpload: ComputedRef<boolean>;
};
```

---

## HITL 中断消息组件（human-in-the-loop）

小鲸的「人在环」中断（第三方审批 / 用户回答问题）在会话内以 `MessageRole.Interrupt` 消息呈现，由 `MessageRender` 分发到 `InterruptMessageRender`。这是 chat-x 侧对 chat-helper resume 协议的对应实现。

> **导出名对照**：不存在 `AIDevToolApproval` / `UserQuestion` 这类组件名。审批单卡片是 `ToolApprovalCard`（**内部**渲染，未再导出）；用户问答相关导出为 `UserQuestionCard` / `UserQuestionAnsweredCard` / `UserQuestionChoice` / `UserQuestionOption` / `useUserQuestion` / `buildSkipResumePayload` / `OTHERS_OPTION_LABEL` / `toLetter`。

### InterruptMessageRender（interrupt-message 默认导出）

- **Props**：`Partial<InterruptMessage> & { onInterruptResume?: OnInterruptResume }`。
- **Slots**：`answeredQuestion({ index, item, status })`（透传给 `UserQuestionAnsweredCard` 的 `#answer`）。
- **渲染规则**：
  - `content.outcome.type === 'interrupt'`：逐条渲染中断。`AIDevToolApproval` → 会话内内嵌 `ToolApprovalCard`；`UserQuestion` → **不在会话内渲染**，改由 `ChatContainer` 在 chat-input 上方以浮层 `UserQuestionCard` 呈现（`activeUserQuestionInterrupt` 提供）。
  - `content.outcome.type === 'success'`：按 `result.reason` **只读回显**——审批 → `ToolApprovalCard`（`readonly: true`）；用户问答 → `UserQuestionAnsweredCard`（`answers` / `status`）。

### ToolApprovalCard（内部，未再导出）

审批单卡片（标题、单号、提交时间、处理人、查看详情、取消审批）。「取消审批」按钮仅在 **待审批（pending/draft）且 `!readonly` 且非分享态** 时出现；点击后置 `cancelling` 防重复提交，回调：

```typescript
onInterruptResume?.(
  { operation: InterruptResumeOperation.ApprovalCancel, payload: { interrupt_id: interrupt.id } },
  interrupt,
);
```

### UserQuestionCard / UserQuestionAnsweredCard / useUserQuestion

- **`UserQuestionCard`**：props `{ interrupt: UserQuestionInterrupt; onResume?: OnInterruptResume }`；slot `question({ question, qIndex, answer, setAnswer, confirm })`（= `UserQuestionCardSlots['question']`）。「完成」→ `buildResolvePayload()`（`status:'resolved'`）；「跳过」→ `buildSkipPayload()`（`status:'cancelled'`）。
- **`UserQuestionAnsweredCard`**：props `{ answers: UserQuestionAnswerItem[]; status?: 'cancelled' | 'resolved' }`（默认 `'resolved'`）；slot `answer({ index, item, status })`。
- **`useUserQuestion(getInterrupt)`** 返回：

```typescript
const {
  questions, answeredCount, totalCount, completed,
  getAnswer, setAnswer,
  buildResolvePayload,  // 全部作答后：resolved + 各题答案
  buildSkipPayload,     // 跳过：cancelled + 空答案
} = useUserQuestion(() => interrupt);
```

- **`buildSkipResumePayload(interrupt?)`**：用户不走结构化选择、直接在 chat-input 打字回答时构造的 resume（`status:'cancelled'` + `answers: []`）。业务层（ChatBot）原样透传，自由文本不进 `answers`，只经 `input` 传递。

### 中断协议类型（`ag-ui/types/interrupt.ts`）

```typescript
enum InterruptResumeOperation {
  ApprovalCancel = 'approval_cancel', // 主动取消第三方工具审批
  FlowNodeRetry = 'flow_node_retry',  // 重试失败的流程节点
  FlowNodeSkip = 'flow_node_skip',    // 跳过失败的流程节点
}

type OnInterruptResume = (payload: InterruptResume, interrupt?: Interrupt) => Promise<void> | void;

type InterruptResume = FlowNodeResume | ToolApprovalResume | UserQuestionResume;

type ToolApprovalResume = {
  operation: InterruptResumeOperation.ApprovalCancel;
  payload: { interrupt_id: number | string };
};
type FlowNodeResume = {
  operation: InterruptResumeOperation.FlowNodeRetry | InterruptResumeOperation.FlowNodeSkip;
  payload: { node_id: string; task_id: number };
};
type UserQuestionResume = BaseResume<InterruptReason.UserQuestion, { answers: UserQuestionAnswerItem[] }>;
```

`InterruptMessage` 消息体（`content`）关键字段：`message?`、`outcome?: RunFinishedOutcome`、`result?: InterruptResult`、`runId?`、`threadId?`；其中：

```typescript
type RunFinishedOutcome =
  | { type: 'interrupt'; interrupts: Interrupt[] }
  | { type: 'success' };
type InterruptResult = AIDevToolApprovalResume | UserQuestionResume;
```

> `interrupt` 记录形态：`{ id, reason: InterruptReason, toolCallId, metadata?, message?, expiresAt?, properties? }`。审批 `metadata.ticket { approvers[], sn, status: APPROVAL_STATUS, submit_time, title, url }`；用户问答 `metadata.questions: UserQuestionItem[]`。

### Flow Agent 节点重试 / 跳过

flow-agent（`components/chat-content/flow-agent-content`）失败节点的行尾操作由 `useFlowNodeActions` 统一管理，与中断 resume 复用同一条 `onInterruptResume` 回调（按 `payload.operation` 分流）：

| 操作 | operation | 可见条件 |
|------|-----------|----------|
| 重试 | `FlowNodeRetry` | 节点失败（`convergedState==='failed'`）且 `retryable` |
| 跳过 | `FlowNodeSkip` | 节点失败且 `skippable` |
| 详情 | -（打开侧栏） | 恒显示 |

- 触发：`onInterruptResume({ payload: { node_id, task_id }, operation })`（流程节点无 `interrupt` 实参）。
- 防重：按 `task_id:node_id:retry` 记 pending；重试/跳过点击后二者互相禁用并给 hover 提示（如「任务正在跳过中，不可重试」），后端状态更新（retry 计数变化使 key 失效）后自动收敛。
- **只读态**：`hideResumeActions` 为真（分享/只读）时过滤掉重试/跳过，仅保留「详情」。
- `BkFlowNode` 能力位：`retryable?` / `skippable?` / `closable?` / `state` / `retry` / `skip`（见 `ag-ui/types/contents.ts`）。

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
  Fetching = 'fetching', // 请求中
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
  Interrupt = 'interrupt',
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

见 `ag-ui/types/constants.ts`：`Binary`、`FlowAgent`、`Function`、`KeyValue`、`KnowledgeRag`、`Other`、`ReferenceDocument`、`Text`（无 `Thinking` / `Reasoning`——推理是 `MessageRole` 而非内容类型）。

### RenderMode（`common/constants.ts`）

```typescript
enum RenderMode {
  Chat = 'chat',
  Share = 'share',
  Test = 'test',
}
```

### InterruptReason（`ag-ui/types/constants.ts`）

```typescript
enum InterruptReason {
  AIDevToolApproval = 'aidev:tool_approval', // AI dev 第三方审批
  UserQuestion = 'aidev:user_question',      // 用户回答问题
}
```

### APPROVAL_STATUS（`ag-ui/types/constants.ts`）

```typescript
enum APPROVAL_STATUS {
  ABANDONED = 'abandoned', // 已废弃
  APPROVED = 'approved',   // 已批准
  CANCELLED = 'cancelled', // 已取消
  DRAFT = 'draft',         // 草稿 - 待审批
  EXPIRED = 'expired',     // 已过期
  PENDING = 'pending',     // 待审批
  REJECTED = 'rejected',   // 已拒绝
  REVOKED = 'revoked',     // 已撤销
}
// APPROVAL_STATUS_MAP：状态 -> i18n 文案映射表
```

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
  useFullScreen,          // 全屏
  useGlobalConfig,        // 字号 / 上传等全局配置
  useMenuKeydown,
  useMessageGroup,
  useObserverVisibleList,
  useParentScrolling,
} from '@blueking/chat-x';
```

内部使用滚动：`useContainerScrollProvider(containerRef, bottomRef)` 与 `useContainerScrollConsumer`。

Provider 返回 / provide 的滚动能力：

| 方法 | 说明 |
| --- | --- |
| `toScrollBottom(behavior?: ScrollBehavior)` | 滚动到底部。**缺省按距底部距离自动选择行为**：距离超过 `INSTANT_SCROLL_DISTANCE`（600px）时瞬时贴底，否则平滑滚动。需要强制平滑（如「返回底部」按钮）时显式传 `'smooth'` |
| `jumpToBottom()` | 瞬时贴底，不产生任何滚动动画 |
| `toScrollTop()` | 平滑滚动到顶部 |

> **注意**：`toScrollBottom` 不能直接作为事件处理器绑定（`@click="toScrollBottom"`），否则 `MouseEvent` 会被当成 `behavior` 传入。应写成 `@click="() => toScrollBottom('smooth')"`。
>
> 自动选择行为是为了避免首屏渲染、切换会话等场景下容器从 `scrollTop = 0` 开始做长距离平滑滚动，产生「从头滚到尾」的动画。`MessageContainer` 另在 `onMounted` 时调用 `jumpToBottom()` 直接定位，消除历史消息渲染期间的顶部闪烁。

> **未从 `composables/index.ts` 再导出**（需深路径引用，一般不写入应用侧）：`composables/use-common.ts` 里的 `useRenderModeProvider` / `useRenderModeInject` / `useKeywordProvider` / `useCommonTippyProvider` 等 RenderMode / 关键词 / tippy provide-inject 能力。

---

## 常量

```typescript
import { CONST_MESSAGE_TOOLS, CONST_USER_MESSAGE_TOOLS, CONST_UPDATE_TOOLS } from '@blueking/chat-x';

// CONST_MESSAGE_TOOLS：AI 消息默认工具 copy / cite / rebuild / share（文案为 i18n 函数结果）
// CONST_USER_MESSAGE_TOOLS：用户消息 copy / cite / edit / delete
// CONST_UPDATE_TOOLS：流式结束后的更新区 like / unlike / delete
```

类型均为 `IToolBtn[]`（`as IToolBtn[]` 断言）。
