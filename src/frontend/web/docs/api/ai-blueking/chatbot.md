# ChatBot 组件

`ChatBot` 是 AI 小鲸的核心聊天组件，提供输入框、消息列表、快捷指令等完整的聊天交互能力。它支持**独立模式**和**集成模式**两种使用方式。

::: info 非 Vue 宿主
宿主无 Vue 时，请使用 v2.1.4-beta.8+ 的 [`mountChatBot`](/api/ai-blueking/standalone#mountchatbot)（`@blueking/ai-blueking/standalone`），见 [Standalone 集成指南](/guide/integration-modes/standalone-bundle)。
:::

## 基本用法

```vue
<template>
  <!-- 独立模式：只需传入 url -->
  <ChatBot url="/api/ai" :shortcuts="shortcuts" />
</template>

<script setup>
import { ChatBot } from '@blueking/ai-blueking';
</script>
```

```vue
<template>
  <!-- 集成模式：传入外部 chatHelper -->
  <ChatBot :chat-helper="chatHelper" />
</template>

<script setup>
import { ChatBot } from '@blueking/ai-blueking';
import { useChatHelper } from '@blueking/chat-helper';

const chatHelper = useChatHelper({ requestData: { urlPrefix: '/api/ai' } });
</script>
```

## Props

### 基础配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `url` | `string` | `''` | API 地址（独立模式必填） |
| `chatHelper` | `IChatHelper` | — | 外部 chatHelper（集成模式传入，与 `url` 二选一） |
| `requestOptions` | `MaybeRefOrGetter<IRequestOptions>` | — | 请求配置（仅独立模式；`headers` / `data` 支持对象、函数、`ref`、`computed`） |

### 会话配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `autoLoad` | `boolean` | `true` | 是否自动加载最近会话 |
| `sessionCode` | `string` | — | 指定初始会话编码 |

### 快捷方式与资源

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `shortcuts` | `IShortcut[]` | `[]` | 快捷指令列表 |
| `resources` | `IAiSlashMenuItem[]` | `[]` | 资源列表（`@` 触发） |
| `prompts` | `string[]` | — | 预设提示词（`/` 触发） |

### 界面配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `helloText` | `string` | — | 欢迎语 |
| `placeholder` | `string` | — | 输入框占位符 |
| `renderMode` | `RenderMode` | `'chat'` | 渲染模式：`chat`（默认）、`share`（分享）、`test`（测试） |
| `height` | `string \| number` | — | 容器高度 |
| `maxWidth` | `string \| number` | — | 最大宽度 |
| `extCls` | `string` | — | 额外 CSS 类名 |
| `placement` | `'left' \| 'right'` | `'left'` | 执行情况侧面板位置 |

### 分享与选择

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enableSelection` | `boolean` | `false` | 是否启用多选模式（分享用） |
| `shareLoading` | `boolean` | `false` | 分享加载状态 |

### 高级配置

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `messageToolsTippyOptions` | `MessageToolsTippyOptions` | — | 消息工具栏 Tippy 配置（如 `appendTo`，用于控制弹窗挂载位置和层级） |
| `resizeProps` | `{ disabled?, initialDivide?, max?, min? }` | — | ResizeLayout 配置（执行情况侧面板拖拽） |

### 侧栏自定义渲染 {#side-render-customization}

透传 `ChatContainer` 侧栏能力，用于 FlowAgent 节点详情等自定义 Tab。用法见 [侧栏 Tab 自定义渲染](/guide/core-features/side-render-customization)。

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `getSideRenderComponent` | `GetSideRenderComponent` | — | `(h, props) => VNode \| undefined`。返回 VNode 时作为侧栏内容根；返回 `undefined` 时使用 `addCustomTab` 的 `data.component` |
| `getSideTabRenderComponent` | `GetSideTabRenderComponent` | — | `(h, tab, { removeCustomTab }) => VNode \| undefined`。自定义 Tab 标签；未返回时使用默认图标 + 文案 + 关闭按钮 |
| `onCustomTabChange` | `OnCustomTabChange` | — | `(tab) => Promise<unknown>`。Tab 切换时拉取详情并写入 `data.props`；**未传**且为 Flow 节点 Tab（含 `task_id`、`node_id`）时，使用内置 `getFlowAgentTaskNodeInfo` |

## Events

### 消息事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `send-message` | `(message: string)` | 用户发送消息 |
| `receive-start` | — | 流式响应开始（仅独立模式） |
| `receive-text` | — | 流式接收文本（仅独立模式） |
| `receive-end` | — | 流式响应结束（仅独立模式） |
| `stop` | — | 用户停止生成 |
| `error` | `(error: Error)` | 发生错误 |
| `feedback` | `(tool, message, reasonList, otherReason)` | 反馈提交成功 |

### 会话事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `session-switched` | `(session: ISession \| null)` | 会话切换完成 |
| `agent-info-loaded` | `(chatHelper: IChatHelper)` | 独立模式初始化完成（与 `whenReady` 成功时机一致，仅独立模式） |

### 快捷方式事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `shortcut-click` | `({ shortcut, source })` | 快捷指令点击 |

### 分享事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `confirm-share` | `(messages: Message[])` | 确认分享 |
| `cancel-share` | — | 取消分享 |
| `request-share` | — | 请求进入分享模式 |

### 执行情况事件

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `execution-panel-change` | `(isCollapse: boolean)` | 执行情况面板展开/折叠 |

## Expose 方法

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

### 会话操作

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `switchSession` | `(sessionCode: string) => Promise<void>` | 切换到指定会话 |

### 分享操作

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `enterShareMode` | `() => void` | 进入分享选择模式 |
| `exitShareMode` | `() => void` | 退出分享选择模式 |

### 初始化就绪（≥ v2.1.4-beta.13）

| 方法/属性 | 类型 | 说明 |
| --- | --- | --- |
| `whenReady` | `() => Promise<void>` | 等待初始化完成（独立模式含 sessionList；失败时 reject，与 `error` 事件一致） |
| `isReady` | `boolean` | 是否已完成初始化 |

### Agent 信息（≥ v2.1.4-beta.14）

| 方法 | 类型 | 说明 |
| --- | --- | --- |
| `updateAgentInfo` | `() => Promise<IAgentInfo \| null>` | 主动刷新 agentInfo 并更新内部状态（如 shortcuts）；返回最新数据，失败返回 `null` |

独立嵌入无 `show()` 时，建议在 `switchSession` / `sendMessage` 前 `await whenReady()`：

```vue
<template>
  <ChatBot ref="chatbotRef" url="/api/ai" />
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

const chatbotRef = ref<ChatBotExpose>();

onMounted(async () => {
  await chatbotRef.value?.whenReady();
  await chatbotRef.value?.switchSession('my-session');
});
</script>
```

::: warning URL 变更
`url` 或 `chatHelper` 变化会触发重初始化，进行中的 `whenReady()` 会 reject（`ChatBotInitStaleError`），需重新调用 `whenReady()`。
:::

::: info AIBlueking 集成
作为 `AIBlueking` 子组件且传入 `chatHelper` 时，`whenReady` 会立即 resolve；请使用 `await aiBluekingRef.show()` 等待会话就绪。
:::

### 其他

| 方法/属性 | 类型 | 说明 |
| --- | --- | --- |
| `getChatHelper` | `() => IChatHelper \| null` | 获取内部 chatHelper 实例 |
| `messages` | `ComputedRef<Message[]>` | 当前消息列表（只读） |
| `currentSession` | `Ref<ISession \| null>` | 当前会话（响应式） |
| `isGenerating` | `Ref<boolean>` | 是否正在生成（响应式） |

### 使用 Expose

```vue
<template>
  <ChatBot ref="chatbotRef" url="/api/ai" />
  <button @click="onSend">发送</button>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

const chatbotRef = ref<ChatBotExpose>();

const onSend = async () => {
  await chatbotRef.value?.whenReady();
  chatbotRef.value?.sendMessage('你好');
};
</script>
```

## 两种模式对比

| 特性 | 独立模式 | 集成模式 |
| --- | --- | --- |
| 初始化方式 | 传入 `url`，组件内部创建 `chatHelper` | 传入外部 `chatHelper` 实例 |
| 适用场景 | 快速接入，无需外部状态管理 | 需要与外部逻辑共享数据/状态 |
| 流式事件 | ✅ 触发 `receive-start/text/end` | ❌ 由外部 `chatHelper` 自行处理 |
| `requestOptions` | ✅ 生效 | ❌ 不生效（由外部配置） |
| Agent 信息加载 | 自动加载，触发 `agent-info-loaded` | 由外部控制 |
| 等待就绪 | `await whenReady()` / `isReady`（≥ beta.13） | `whenReady` 立即 resolve，用父级 `show()` |
| 数据控制权 | 组件内部管理 | 外部完全控制 |

### 独立模式示例

```vue
<template>
  <ChatBot
    url="/api/ai"
    :shortcuts="shortcuts"
    :request-options="requestOptions"
    hello-text="你好，我是 AI 小鲸！"
    placeholder="输入你的问题..."
    @send-message="onSend"
    @receive-end="onReceiveEnd"
  />
</template>

<script setup>
import { ChatBot } from '@blueking/ai-blueking';

const shortcuts = [
  { id: 'explain', name: '解释代码', icon: 'code', description: '解释选中的代码' },
];

const requestOptions = {
  headers: { 'X-Custom-Header': 'value' },
  data: { extra: 'params' },
};

function onSend(message) {
  console.log('用户发送:', message);
}

function onReceiveEnd() {
  console.log('回复完成');
}
</script>
```

### 集成模式示例

```vue
<template>
  <ChatBot :chat-helper="chatHelper" :shortcuts="shortcuts" />
</template>

<script setup>
import { ChatBot } from '@blueking/ai-blueking';
import { useChatHelper } from '@blueking/chat-helper';

const chatHelper = useChatHelper({
  requestData: {
    urlPrefix: '/api/ai',
    headers: { Authorization: 'Bearer xxx' },
  },
});

// 外部可以直接操作 chatHelper
chatHelper.agent.getAgentInfo();
</script>
```
