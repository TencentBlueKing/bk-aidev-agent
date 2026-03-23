# ChatBot 组件

`ChatBot` 是 AI 小鲸的核心聊天组件，提供输入框、消息列表、快捷指令等完整的聊天交互能力。它支持**独立模式**和**集成模式**两种使用方式。

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

| 属性 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `url` | `string` | `''` | API 地址（独立模式必填） |
| `chatHelper` | `IChatHelper` | - | 外部 chatHelper（集成模式传入，与 `url` 二选一） |
| `autoLoad` | `boolean` | `true` | 是否自动加载最近会话 |
| `sessionCode` | `string` | - | 指定初始会话编码 |
| `shortcuts` | `IShortcut[]` | `[]` | 快捷指令列表 |
| `shortcutLimit` | `number` | `10` | 快捷指令显示上限 |
| `resources` | `IAiSlashMenuItem[]` | `[]` | 资源列表（`@` 触发） |
| `prompts` | `string[]` | - | 预设提示词（`/` 触发） |
| `helloText` | `string` | - | 欢迎语 |
| `placeholder` | `string` | - | 输入框占位符 |
| `enableSelection` | `boolean` | `false` | 是否启用多选模式（分享用） |
| `shareLoading` | `boolean` | `false` | 分享加载状态 |
| `height` | `string \| number` | - | 容器高度 |
| `maxWidth` | `string \| number` | - | 最大宽度 |
| `extCls` | `string` | - | 额外 CSS 类名 |
| `requestOptions` | `IRequestOptions` | - | 请求配置（仅独立模式，含 `headers` / `data`） |
| `messageToolsTippyOptions` | `object` | - | 消息工具栏 Tippy 配置 |

## Events

| 事件名 | 参数 | 说明 |
| --- | --- | --- |
| `send-message` | `(message: string)` | 用户发送消息 |
| `receive-start` | - | 流式响应开始（仅独立模式） |
| `receive-text` | - | 流式接收文本（仅独立模式） |
| `receive-end` | - | 流式响应结束（仅独立模式） |
| `stop` | - | 用户停止生成 |
| `error` | `(error: Error)` | 发生错误 |
| `session-switched` | `(session: ISession \| null)` | 会话切换完成 |
| `shortcut-click` | `({ shortcut, source })` | 快捷指令点击 |
| `agent-info-loaded` | `(chatHelper: IChatHelper)` | Agent 信息加载完成（独立模式） |
| `feedback` | `(tool, message, reasonList, otherReason)` | 反馈提交成功 |
| `confirm-share` | `(messages: Message[])` | 确认分享 |
| `cancel-share` | - | 取消分享 |
| `request-share` | - | 请求进入分享模式 |

## Expose 方法

| 方法/属性 | 类型 | 说明 |
| --- | --- | --- |
| `sendMessage` | `(message: string) => void` | 编程式发送消息 |
| `stopGeneration` | `() => void` | 停止当前生成 |
| `switchSession` | `(sessionCode: string) => Promise<void>` | 切换到指定会话 |
| `setCiteText` | `(text: string) => void` | 设置引用文本 |
| `focusInput` | `() => void` | 聚焦输入框 |
| `selectShortcut` | `(shortcut, text?) => void` | 选择快捷指令并填充文本 |
| `getChatHelper` | `() => IChatHelper \| null` | 获取内部 chatHelper 实例 |
| `messages` | `ComputedRef<Message[]>` | 当前消息列表（只读） |
| `currentSession` | `ComputedRef<ISession \| null>` | 当前会话（只读） |
| `isGenerating` | `ComputedRef<boolean>` | 是否正在生成（只读） |

### 使用 Expose

```vue
<template>
  <ChatBot ref="chatbotRef" url="/api/ai" />
  <button @click="chatbotRef?.sendMessage('你好')">发送</button>
</template>

<script setup>
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';

const chatbotRef = ref<InstanceType<typeof ChatBot>>();
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
