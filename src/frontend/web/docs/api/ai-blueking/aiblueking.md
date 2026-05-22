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
| `hideHeader` | `boolean` | `false` | 是否隐藏头部栏 |
| `hideNimbus` | `boolean` | `false` | 是否隐藏悬浮球 |
| `hideDefaultTrigger` | `boolean` | `false` | 是否隐藏默认触发器 |
| `disabledInput` | `boolean` | `false` | 是否禁用输入 |

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
| `dropdownMenuConfig` | `DropdownMenuConfig` | `{ showRename: true, showAutoGenerate: true, showShare: true }` | 下拉菜单配置 |

### 高级配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `beforeNimbusClick` | `() => boolean \| Promise<boolean \| void> \| void` | — | Nimbus 点击前钩子函数，返回 `false` 阻止默认 showPanel 行为 |
| `resizeProps` | `{ disabled?, initialDivide?, max?, min? }` | — | ResizeLayout 配置（执行情况侧面板拖拽） |

### 侧栏自定义渲染 {#side-render-customization}

与 [ChatBot](/api/ai-blueking/chatbot#side-render-customization) 相同，透传至内层 `ChatBot`（**≥ v2.1.4-beta.7**）：`getSideRenderComponent`、`getSideTabRenderComponent`、`onCustomTabChange`。详见 [侧栏 Tab 自定义渲染](/guide/core-features/side-render-customization)。

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
| `rename` | `(newName: string)` | 重命名 |
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

### 错误事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `sdk-error` | `({ apiName, code, data, message })` | SDK 层错误 |

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

### 其他

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `getChatHelper` | `() => IChatHelper \| null` | 获取内部 chatHelper 实例 |

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
| 会话管理侧边栏 | ❌ | ✅ |
| Teleport 渲染 | ❌ | ✅ |
| 文本选中弹窗 | ❌ | ✅ |

如果你只需要嵌入一个聊天区域，推荐使用更轻量的 [ChatBot](./chatbot.md) 组件。
