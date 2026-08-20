# AIBlueking 浮窗模式

`AIBlueking` 是 AI 小鲸的顶层组件，提供开箱即用的全局 AI 助手体验。它在 `ChatBot` 的基础上集成了浮球入口、可拖拽容器、会话管理侧栏、文本选中弹窗等完整功能。

::: tip AIDev 自动加载
组件初始化时会自动通过 `agent/info` 接口加载 Agent 配置（快捷指令、提示词、欢迎语等），**无需手动传入**。你只需要提供 AIDev 平台发布后的 URL。
:::

## 适用场景

- **SaaS 全局 AI 助手**：页面右下角展示 Nimbus 浮球，点击即可展开 AI 对话面板。
- **拖拽面板**：对话面板可自由拖拽、调整大小，不影响宿主页面布局。
- **划词弹窗**：用户在页面中选中文本后，弹出快捷操作菜单（如"解释"、"翻译"等）。
- **辅助工具**：嵌入各类 SaaS 产品作为辅助工具，提供 AI 对话能力。

## 快速开始

```vue
<template>
  <AIBlueking
    ref="aiBluekingRef"
    url="https://your-aidev-url.com/api/"
    :enable-popup="true"
    :draggable="true"
    @send-message="handleSendMessage"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';
// Vue 2 项目使用：import '@blueking/ai-blueking/dist/vue2/style.css';
import type { AIBluekingExpose } from '@blueking/ai-blueking';

const aiBluekingRef = ref<AIBluekingExpose>();

const handleSendMessage = (message: string) => {
  console.log('发送:', message);
};

// 面板控制（show 返回 Promise，建议 await 后再读 session）
const showPanel = async () => {
  await aiBluekingRef.value?.show();
};
const hidePanel = () => aiBluekingRef.value?.hide();
const showWithSession = async (code: string) => {
  await aiBluekingRef.value?.show(code);
};
</script>
```

## 核心功能

### Nimbus 浮球

Nimbus 是页面右下角的浮球入口，点击后展开对话面板。可通过 `hideNimbus` 属性隐藏浮球，改为自行控制面板的显示/隐藏。

### DraggableContainer 可拖拽容器

对话面板支持自由拖拽和调整大小，通过 `draggable` 属性启用。可通过 `defaultHeight`、`defaultWidth`、`defaultLeft`、`defaultTop` 设置初始位置和尺寸。

展开右侧侧栏时，浮窗会先腾出右侧空间再扩宽面板（两阶段动画），避免侧栏把聊天区挤出视口。收起时反向：先缩宽再移回。

### AIHeader 会话管理头部

面板顶部的 Header 区域包含：
- 会话下拉列表：快速切换历史会话
- 新建会话按钮：创建新的对话
- 会话重命名、删除等管理操作
- **侧栏展开/收起**（压缩图标左侧）：侧栏固定从右侧展开，可用 `showAsideToggle` 隐藏该按钮

可通过 `hideHeader` 属性隐藏 Header（开关一并消失）。嵌入式 `ChatBot` 无此按钮，须业务自建，见 [业务 Header](/guide/integration-modes/chatbot-embedded#业务-header会话名称--侧栏开关)。

### AiSelection 文本选中弹窗

当用户在页面中选中文本时，自动弹出快捷操作菜单，支持将选中文本作为上下文发送给 AI。通过 `enablePopup` 属性启用。

## AIBlueking 独有 Props

除了继承 `ChatBot` 的所有 Props 外，`AIBlueking` 还提供以下额外属性：

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enablePopup` | `boolean` | `false` | 是否启用文本选中弹窗（AiSelection） |
| `draggable` | `boolean` | `true` | 是否启用面板拖拽 |
| `hideHeader` | `boolean` | `false` | 是否隐藏顶部 Header 区域 |
| `hideNimbus` | `boolean` | `false` | 是否隐藏 Nimbus 浮球入口 |
| `teleportTo` | `string` | `'body'` | 面板挂载的目标 DOM 节点选择器 |
| `defaultHeight` | `number` | `600` | 面板默认高度（px） |
| `defaultWidth` | `number` | `400` | 面板默认宽度（px） |
| `defaultLeft` | `number` | — | 面板默认左偏移（px），不传则自动计算 |
| `defaultTop` | `number` | — | 面板默认上偏移（px），不传则自动计算 |
| `miniPadding` | `number` | `10` | 面板最小化时距离屏幕边缘的间距（px） |
| `enableChatSession` | `boolean` | `true` | 是否启用会话管理功能（Header 中的会话下拉列表） |
| `showAsideToggle` | `boolean` | `true` | 是否显示侧栏展开/收起按钮（在压缩图标左侧） |

> **提示**：`AIBlueking` 同样支持 `ChatBot` 的所有 Props（如 `url`、`requestOptions` 等），具体请参考 [ChatBot 页面嵌入模式](./chatbot-embedded.md)。

## Expose 方法

通过 `ref` 获取 `AIBlueking` 实例后，可调用以下方法：

### 面板控制

| 方法 | 类型 | 说明 |
|------|------|------|
| `show(sessionCode?, options?)` | `(sessionCode?: string, options?: { isTemporary?: boolean }) => Promise<void>` | 展开面板；`await` 后在 `sessionList` 就绪（且默认会完成最近会话初始化）后再 resolve。详见 [编程式控制](/guide/advanced-usage/programmatic-control#show-显示窗口) |
| `hide()` | `() => void` | 收起面板 |
| `handleShow(sessionCode?)` | `(sessionCode?: string) => Promise<void>` | 展开面板（内部方法） |
| `handleClose()` | `() => void` | 收起面板（内部方法） |

### 消息操作

| 方法 | 类型 | 说明 |
|------|------|------|
| `sendMessage(text)` | `(text: string) => Promise<void>` | 以编程方式发送消息 |
| `stopGeneration()` | `() => void` | 停止当前正在生成的响应 |
| `setCiteText(text)` | `(text: string) => void` | 设置引用文本到输入框 |
| `focusInput()` | `() => void` | 聚焦输入框 |

### 快捷方式操作

| 方法 | 类型 | 说明 |
|------|------|------|
| `selectShortcut(shortcut, selectedText?)` | `(shortcut: IShortcut, selectedText?: string) => void` | 选择快捷指令并显示表单，不会自动提交 |
| `sendShortcut(shortcut, selectedText?)` | `(shortcut: IShortcut, selectedText?: string) => Promise<void>` | 直接发送快捷指令（跳过表单） |

### 会话管理

| 方法 | 类型 | 说明 |
|------|------|------|
| `addNewSession(options?)` | `(options?: CreateSessionOptions) => Promise<void>` | 创建新会话并自动切换 |
| `switchToSession(code)` | `(code: string) => Promise<void>` | 切换到指定会话 |
| `updateSessionName(code, name)` | `(sessionCode: string, newName: string) => Promise<void>` | 更新指定会话的名称 |

### 容器控制

| 方法 | 类型 | 说明 |
|------|------|------|
| `updatePosition(x, y)` | `(x: number, y: number) => void` | 更新面板位置 |
| `updateSize(w, h)` | `(w: number, h: number) => void` | 更新面板尺寸 |
| `updatePositionAndSize(x, y, w, h)` | `(x: number, y: number, w: number, h: number) => void` | 同时更新位置和尺寸 |

### 其他

| 方法 | 类型 | 说明 |
|------|------|------|
| `getChatHelper()` | `() => IChatHelper \| null` | 获取内部 chatHelper 实例 |

## 内部结构

`AIBlueking` 本质上是一个组装层，内部由以下子组件构成：

![AIBlueking 内部结构](/images/guide/aiblueking-structure.png)

`AIBlueking` 内部创建并持有 `chatHelper` 实例，以集成模式将其传递给 `ChatBot`，确保所有子组件共享同一对话状态。各子组件通过 Manager 模式协调工作：

- **Nimbus** 点击 → 调用 `show()` → `DraggableContainer` 展开
- **AIHeader** 操作 → 通过 `SessionBusinessManager` 管理会话
- **AiSelection** 选中文本 → 调用 `setCiteText()` → `ChatBot` 输入框填充引用
- **ChatBot** 承担所有核心聊天逻辑
