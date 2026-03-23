# AIBlueking 组件

`AIBlueking` 是 AI 小鲸的顶层业务组件，在 `ChatBot` 基础上封装了完整的面板功能，包括弹窗模式、拖拽、缩放、会话管理侧边栏、悬浮球等能力。适用于 SaaS 平台快速集成 AI 助手场景。

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

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `url` | `string` | - | API 地址（必填） |
| `requestOptions` | `IRequestOptions` | - | 请求配置（含 `headers` / `data`，支持函数形式） |
| `enableChatSession` | `boolean` | - | 是否启用多会话（显示会话管理侧边栏） |
| `shortcuts` | `IShortcut[]` | `[]` | 快捷指令列表 |
| `enablePopup` | `boolean` | `false` | 是否启用弹窗模式 |
| `draggable` | `boolean` | `false` | 是否可拖拽 |
| `hideHeader` | `boolean` | `false` | 是否隐藏头部栏 |
| `hideNimbus` | `boolean` | `false` | 是否隐藏悬浮球 |
| `teleportTo` | `string` | - | 渲染目标（CSS 选择器，如 `'body'`） |
| `extCls` | `string` | - | 额外 CSS 类名 |
| `defaultHeight` | `number` | - | 默认高度（px） |
| `defaultWidth` | `number` | - | 默认宽度（px） |
| `defaultLeft` | `number` | - | 默认左偏移（px） |
| `defaultTop` | `number` | - | 默认上偏移（px） |
| `maxWidth` | `number \| string` | - | 最大宽度 |
| `miniPadding` | `number` | - | 最小边距（px） |
| `helloText` | `string` | - | 欢迎语 |
| `placeholder` | `string` | - | 输入框占位符 |
| `prompts` | `string[]` | - | 预设提示词（`/` 触发） |
| `resources` | `IAiSlashMenuItem[]` | `[]` | 资源列表（`@` 触发） |

## Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `send-message` | `(message: string)` | 用户发送消息 |
| `receive-start` | - | 流式响应开始 |
| `receive-text` | - | 流式接收文本 |
| `receive-end` | - | 流式响应结束 |
| `stop` | - | 用户停止生成 |
| `session-switched` | `(session: ISession \| null)` | 会话切换完成 |
| `shortcut-click` | `({ shortcut, source })` | 快捷指令点击 |
| `error` | `(error: Error)` | 发生错误 |
| `drag-stop` | `({ left, top })` | 拖拽结束 |
| `resize-stop` | `({ width, height })` | 缩放结束 |
| `dragging` | `({ left, top })` | 拖拽中 |
| `resizing` | `({ width, height })` | 缩放中 |
| `transfer-messages` | `(messages: Message[])` | 转移消息（用于跨面板传递） |
| `share-messages` | `(messages: Message[])` | 分享消息 |
| `sdk-error` | `(error: Error)` | SDK 层错误 |

## Expose 方法

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `show` | `(sessionCode?: string) => void` | 显示面板，可选指定初始会话 |
| `hide` | `() => void` | 隐藏面板 |
| `sendMessage` | `(message: string) => void` | 编程式发送消息 |
| `stopGeneration` | `() => void` | 停止当前生成 |
| `addNewSession` | `() => void` | 新建会话 |
| `switchToSession` | `(sessionCode: string) => Promise<void>` | 切换到指定会话 |
| `updateSessionName` | `(code: string, name: string) => void` | 更新会话名称 |
| `updatePosition` | `(left: number, top: number) => void` | 更新面板位置 |
| `updateSize` | `(width: number, height: number) => void` | 更新面板尺寸 |
| `updatePositionAndSize` | `(rect: Partial<Rect>) => void` | 同时更新位置和尺寸 |
| `setCiteText` | `(text: string) => void` | 设置引用文本 |
| `focusInput` | `() => void` | 聚焦输入框 |

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
    :default-right="20"
    :default-bottom="20"
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

如果你只需要嵌入一个聊天区域，推荐使用更轻量的 [ChatBot](./chatbot.md) 组件。
