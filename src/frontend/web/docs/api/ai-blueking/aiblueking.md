# AIBlueking 组件

`AIBlueking` 是 AI 小鲸的顶层业务组件，在 `ChatBot` 基础上封装了完整的面板功能，包括弹窗模式、拖拽、缩放、会话管理侧边栏、悬浮球等能力。适用于 SaaS 平台快速集成 AI 助手场景。

::: info 非 Vue 宿主
宿主无 Vue 时，请使用 v2.1.4-beta.8+ 的 [`mountAIBlueking`](/api/ai-blueking/standalone#mountaiblueking)（`@blueking/ai-blueking/standalone`），见 [Standalone 集成指南](/guide/integration-modes/standalone-bundle)。
:::

## 基本用法

```vue
<template>
  <AIBlueking
    ref="aiRef"
    url="/api/ai"
    enable-popup
    draggable
    :shortcuts="shortcuts"
    hello-text="你好，我是 AI 小鲸！"
  />
</template>

<script setup>
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const aiRef = ref<InstanceType<typeof AIBlueking>>();

// 通过 ref 控制显示/隐藏
function openAI() {
  aiRef.value?.show();
}
</script>
```

## Props

### 基础配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `url` | `string` | `''` | API 地址（独立模式必填） |
| `title` | `string` | `''` | 组件标题，显示在 Header 区域 |
| `renderMode` | `RenderMode` | `'chat'` | 渲染模式：`chat`（默认）、`share`（分享）、`test`（测试） |
| `requestOptions` | `MaybeRefOrGetter<IRequestOptions>` | `{}` | 请求配置（`headers` / `data` 支持对象、函数、`ref`、`computed`） |
| `extCls` | `string` | `''` | 额外 CSS 类名 |
| `placeholder` | `string` | — | 输入框占位文本 |
| `helloText` | `string` | `'你好，我是小鲸'` | 欢迎语 |
| `prompts` | `string[]` | `[]` | 预设提示词（`/` 触发） |
| `resources` | `IAiSlashMenuItem[]` | `[]` | 资源列表（`@` 触发） |

### 功能开关

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enablePopup` | `boolean` | `true` | 是否启用文本选中弹窗（AiSelection） |
| `draggable` | `boolean` | `true` | 是否可拖拽 |
| `enableChatSession` | `boolean` | `true` | 是否启用多会话（显示会话管理侧边栏） |
| `enableModelSelect` | `boolean` | `true` | 是否启用模型选择（**≥ v2.2.2**）；为 `true` 时 bootstrap 拉取 `GET llms/`，列表非空才展示 ModelSelector |
| `models` | `ILlmItem[] \| IModelOption[]` | — | 外部模型列表（**≥ v2.2.2**）；有值时跳过内部拉取，优先使用 |
| `hideHeader` | `boolean` | `false` | 是否隐藏头部栏 |
| `hideNimbus` | `boolean` | `false` | 是否隐藏悬浮球 |
| `hideDefaultTrigger` | `boolean` | `false` | 是否隐藏默认触发器 |
| `disabledInput` | `boolean` | `false` | 是否禁用输入 |
| `errorToast` | `boolean` | `true` | 接口错误时是否自动弹出 Message 提示（**≥ v2.1.4-beta.25**）；设为 `false` 可自行通过 `sdk-error` 事件处理 |
| `ignoreErrors` | `Array<string \| RegExp>` | `[]` | 忽略的接口错误 URL 模式（**≥ v2.1.4-beta.25**）；字符串包含匹配或正则，匹配的接口错误不会弹出 toast |

::: tip 模型选择
默认开启。选中态跟随 `session.model` 并写回当前会话（≥ v2.2.2），发送时携带 `llm_code`。详见 [模型选择](/guide/core-features/model-selection)。
:::

### 容器配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `teleportTo` | `string` | `'body'` | 渲染目标（CSS 选择器） |
| `defaultWidth` | `number` | `400` | 默认宽度（px） |
| `defaultHeight` | `number` | — | 默认高度（px） |
| `defaultLeft` | `number` | — | 默认左偏移（px），不传则自动计算 |
| `defaultTop` | `number` | `0` | 默认上偏移（px） |
| `maxWidth` | `number \| string` | `1000` | 最大宽度 |
| `miniPadding` | `number` | `0` | 最小边距（px） |
| `defaultChatInputPosition` | `'bottom' \| undefined` | — | 默认聊天输入框位置 |

### Nimbus 配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `nimbusSize` | `'large' \| 'normal' \| 'small'` | `'normal'` | 悬浮球大小 |
| `defaultMinimize` | `boolean` | `false` | 是否默认最小化 |

### 快捷方式配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `shortcuts` | `IShortcut[]` | `[]` | 快捷指令列表 |
| `shortcutLimit` | `number` | `3` | 快捷指令显示上限（同时控制 AiSelection 最大展示数量） |
| `shortcutFilter` | `(shortcut: IShortcut, selectedText: string) => boolean` | — | 快捷操作过滤函数，用于动态筛选弹窗中显示的快捷指令 |

### 会话配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `initialSessionCode` | `string` | `''` | 初始会话编码 |
| `autoSwitchToInitialSession` | `boolean` | `false` | 是否自动切换到初始会话 |
| `loadRecentSessionOnMount` | `boolean` | `true` | 挂载时是否加载最近会话 |

### Header 图标控制

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `showHistoryIcon` | `boolean` | `true` | 是否显示历史记录图标 |
| `showNewChatIcon` | `boolean` | `true` | 是否显示新建会话图标 |
| `showCompressionIcon` | `boolean` | `true` | 是否显示压缩图标 |
| `showMoreIcon` | `boolean` | `true` | 是否显示更多图标 |
| `showAsideToggle` | `boolean` | `true` | 是否显示侧栏展开/收起按钮（在压缩图标左侧）。`hideHeader` 时 Header 整栏不渲染，开关一并消失。嵌入式 `ChatBot` 无此按钮，须业务自建，见 [业务 Header](/guide/integration-modes/chatbot-embedded#业务-header会话名称--侧栏开关) |
| `dropdownMenuConfig` | `DropdownMenuConfig` | `{ showRename: true, showAutoGenerate: true, showShare: true }` | 下拉菜单配置 |

### 高级配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `beforeNimbusClick` | `() => boolean \| Promise<boolean \| void> \| void` | — | Nimbus 点击前钩子函数，返回 `false` 阻止默认 showPanel 行为 |
| `messageTools` | `IToolBtn[]` | — | 自定义 AI 消息主工具组，透传至 ChatBot |
| `updateTools` | `IToolBtn[]` | — | 自定义 AI 消息反馈工具组，透传至 ChatBot |
| `resizeProps` | `{ disabled?, initialDivide?, max?, min? }` | — | ResizeLayout 配置（执行情况侧面板拖拽） |
| `size` | `'normal' \| 'small'` | `'small'` | 字号主题档位，透传至 ChatBot → ChatContainer（`small` 12px / `normal` 14px） |
| `timezone` | `string` | — | 消息时间展示所用的 IANA 时区名（如 `Asia/Shanghai`）（**≥ v2.2.3**），透传至 ChatBot → ChatContainer；未配置时按浏览器时区。详见 [消息时间展示](/guide/core-features/chat-interaction#消息时间展示) |

### 侧栏自定义渲染 {#side-render-customization}

与 [ChatBot](/api/ai-blueking/chatbot#side-render-customization) 相同，透传至内层 `ChatBot`（**≥ v2.1.4-beta.7**）：`getSideRenderComponent`、`getSideTabRenderComponent`、`onCustomTabChange`。详见 [侧栏 Tab 自定义渲染](/guide/core-features/side-render-customization)。

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `executionTabVisible` | `boolean` | `true` | 「执行情况」Tab 是否展示（**≥ v2.2.0-beta.11**），透传至内层 `ChatBot`。该 Tab 始终存在、不可关闭、`order` 固定 `0`；置 `false` 仅将其从 Tab 栏隐藏 |

## Events

### 面板事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `show` | — | 面板显示 |
| `close` | — | 面板关闭 |

### 消息事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `send-message` | `(message: string)` | 用户发送消息 |
| `receive-start` | — | 流式响应开始 |
| `receive-text` | — | 流式接收文本 |
| `receive-end` | — | 流式响应结束 |
| `stop` | — | 用户停止生成 |

### 快捷方式事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `shortcut-click` | `({ shortcut, source })` | 快捷指令点击，`source` 为 `'main'` 或 `'popup'` |

### 会话事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `session-initialized` | `({ openingRemark, predefinedQuestions })` | 会话初始化完成 |
| `new-chat` | — | 新建会话 |
| `new-chat-created` | `({ sessionCode, sessionName?, createdAt? })` | 新会话创建完成 |
| `history-click` | `(event: Event)` | 历史记录点击 |
| `auto-generate-name` | — | 自动生成名称 |
| `rename` | `(newName: string, sessionCode: string)` | 会话重命名（手动改名，或首条消息后 AI 自动重命名成功）；`sessionCode` 标识被改名会话 |
| `share` | — | 分享 |
| `help-click` | — | 帮助点击 |

### 拖拽/缩放事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `dragging` | `(position: PositionAndSize)` | 拖拽中 |
| `resizing` | `(position: PositionAndSize)` | 缩放中 |
| `drag-stop` | `(position: PositionAndSize)` | 拖拽结束 |
| `resize-stop` | `(position: PositionAndSize)` | 缩放结束 |

> `PositionAndSize` 类型：`{ x: number; y: number; width: number; height: number }`

### 消息选择事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `transfer-messages` | `({ messageIds: string[] })` | 转移消息（用于跨面板传递） |
| `share-messages` | `({ messageIds: string[] })` | 分享消息 |
| `confirm-share` | `(messages: Message[], source?: IToolBtn)` | 确认分享/多选；自定义 `source` 不走内置分享 |
| `agent-action` | `(tool: IToolBtn, messages: Message[])` | 自定义消息工具点击 |

### 错误事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `sdk-error` | `SdkErrorPayload` | SDK 层错误（**≥ v2.1.4-beta.25**：payload 新增 `source` 和 `action` 字段，详见 [SdkErrorPayload](/api/ai-blueking/types#sdkerrorpayload)） |

## Expose 方法

### 面板控制

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `show` | `(sessionCode?: string, options?: { isTemporary?: boolean }) => Promise<void>` | 显示面板；Promise 在 `sessionList` 就绪后 resolve（`loadRecentSessionOnMount` 时含当前会话初始化）。面板立即显示，可 `await` 后再读 `getChatHelper()?.session`。失败 reject 并触发 `sdk-error`（`apiName: 'init'`） |
| `hide` | `() => void` | 隐藏面板 |
| `handleShow` | `(sessionCode?: string) => Promise<void>` | 显示面板（内部方法，等同于 `show`） |
| `handleClose` | `() => void` | 关闭面板（内部方法，等同于 `hide`） |

### 消息操作

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `sendMessage` | `(message: string) => Promise<void>` | 编程式发送消息 |
| `stopGeneration` | `() => void` | 停止当前生成 |
| `setCiteText` | `(text: string) => void` | 设置引用文本 |
| `focusInput` | `() => void` | 聚焦输入框 |

### 快捷方式操作

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `selectShortcut` | `(shortcut: IShortcut, selectedText?: string) => void` | 选择快捷指令并显示表单，不会自动提交 |
| `sendShortcut` | `(shortcut: IShortcut, selectedText?: string) => Promise<void>` | 直接发送快捷指令（跳过表单） |

### 会话管理

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `addNewSession` | `(options?: CreateSessionOptions) => Promise<void>` | 新建会话 |
| `switchToSession` | `(sessionCode: string) => Promise<void>` | 切换到指定会话 |
| `updateSessionName` | `(sessionCode: string, newName: string) => Promise<void>` | 更新会话名称 |

### 容器控制

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `updatePosition` | `(x: number, y: number) => void` | 更新面板位置 |
| `updateSize` | `(w: number, h: number) => void` | 更新面板尺寸 |
| `updatePositionAndSize` | `(x: number, y: number, w: number, h: number) => void` | 同时更新位置和尺寸 |

### Agent 信息（≥ v2.1.4-beta.14）

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `updateAgentInfo` | `() => Promise<IAgentInfo \| null>` | 主动刷新 agentInfo 并更新内部状态（如 shortcuts）；返回最新数据，失败返回 `null` |

### 错误上报（≥ v2.1.4-beta.25）

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `reportSdkError` | `(options: ReportSdkErrorOptions) => void` | 统一 SDK 错误出口；自动触发 `sdk-error` 事件并可选弹出 toast，同一 Error 实例去重避免重复上报。详见 [ReportSdkErrorOptions](/api/ai-blueking/types#reportsdkerroroptions) |

### 其他

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `getChatHelper` | `() => IChatHelper \| null` | 获取内部 chatHelper 实例 |

## Slots

| 插槽 | Scope | 说明 |
| --- | --- | --- |
| `welcome` | `{ openingRemark?, welcomeTitle? }` | 自定义空会话欢迎区（透传 ChatBot） |
| `message` | `{ message, messageToolsStatus?, onInterruptResume? }` | 自定义消息渲染 |
| `codeHeader` | `{ language, token }` | 自定义代码块头部 |
| `headerLeft` | — | Header 左侧区域 |

## 弹窗模式

启用 `enablePopup` 后，面板将以弹窗形式渲染，配合 `draggable` 可实现自由拖拽定位。

```vue
<template>
  <AIBlueking
    ref="aiRef"
    url="/api/ai"
    enable-popup
    draggable
    :default-width="420"
    :default-height="600"
    :default-left="20"
    :default-top="20"
    teleport-to="body"
  />
</template>
```

### 弹窗相关 Props 说明

| 属性 | 说明 |
| --- | --- |
| `enablePopup` | 启用弹窗模式，面板脱离文档流 |
| `draggable` | 允许用户拖拽移动面板 |
| `teleportTo` | 将面板渲染到指定 DOM 节点下 |
| `defaultWidth` / `defaultHeight` | 面板初始尺寸 |
| `defaultLeft` / `defaultTop` | 面板初始位置 |
| `miniPadding` | 面板距离视口边缘的最小距离 |
| `hideNimbus` | 隐藏悬浮球入口，需通过 `ref.show()` 控制显隐 |

## 会话管理

设置 `enableChatSession` 后，面板左侧将显示会话列表侧边栏，支持：

- 新建会话
- 切换会话
- 重命名会话
- 删除会话 / 批量删除

```vue
<template>
  <AIBlueking url="/api/ai" enable-chat-session />
</template>
```

## 与 ChatBot 的关系

`AIBlueking` 内部使用了 `ChatBot` 组件，并在其基础上增加了以下能力：

| 能力 | ChatBot | AIBlueking |
| --- | --- | --- |
| 核心聊天功能 | ✅ | ✅ |
| 弹窗模式 | ❌ | ✅ |
| 拖拽 / 缩放 | ❌ | ✅ |
| 悬浮球入口 | ❌ | ✅ |
| 会话管理侧边栏 | ❌（业务自建列表） | ✅（Header 历史下拉） |
| Header / 侧栏开关 | ❌（须业务 Header + `v-model:asideCollapsed`） | ✅（`AIHeader`，`showAsideToggle`） |
| Teleport 渲染 | ❌ | ✅ |
| 文本选中弹窗 | ❌ | ✅ |

如果你只需要嵌入一个聊天区域，推荐使用更轻量的 [ChatBot](./chatbot.md) 组件，并按 [业务 Header](/guide/integration-modes/chatbot-embedded#业务-header会话名称--侧栏开关) 自行补会话名与侧栏开关。
