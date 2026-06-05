# ChatBot 页面嵌入模式

`ChatBot` 是 AI 小鲸的核心聊天组件，支持独立使用，将聊天窗口直接嵌入到页面的指定区域，无需浮球、拖拽或面板容器即可快速集成 AI 对话能力。

::: tip AIDev 自动加载
组件初始化时会自动通过 `agent/info` 接口加载 Agent 配置（快捷指令、提示词、欢迎语等），**无需手动传入**。你只需要提供 AIDev 平台发布后的 URL。
:::

## 适用场景

- **页面主内容**：将聊天窗口作为页面的核心功能区域。
- **侧边栏聊天**：嵌入到页面侧边栏，提供辅助对话能力。
- **自定义会话列表**：结合外部会话列表组件，构建完整的聊天页面（参见 [自定义会话列表](/guide/advanced-usage/external-session-list)）。
- **弹窗/卡片内**：在弹窗、卡片等容器中集成对话能力。

## 快速开始

::: code-group

```vue [Vue 3]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      ref="chatBotRef"
      url="https://your-aidev-url.com/api/"
      :request-options="requestOptions"
      @send-message="handleSendMessage"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { ChatBotExpose } from '@blueking/ai-blueking';

const chatBotRef = ref<ChatBotExpose>();

const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
};

const handleSendMessage = (message: string) => console.log('发送:', message);
const handleError = (error: Error) => console.error('错误:', error);

// 外部控制（≥ v2.1.4-beta.13 建议先 whenReady）
const externalSend = async () => {
  await chatBotRef.value?.whenReady();
  chatBotRef.value?.sendMessage('Hello');
};
const switchSession = async (code: string) => {
  await chatBotRef.value?.whenReady();
  await chatBotRef.value?.switchSession(code);
};
</script>
```

```vue [Vue 2]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      ref="chatBotRef"
      url="https://your-aidev-url.com/api/"
      :request-options="requestOptions"
      @send-message="handleSendMessage"
      @error="handleError"
    />
  </div>
</template>

<script>
import { ChatBot } from '@blueking/ai-blueking';

export default {
  components: { ChatBot },
  data() {
    return {
      requestOptions: {
        headers: () => ({ Authorization: `Bearer ${this.getToken()}` }),
      },
    };
  },
  methods: {
    handleSendMessage(message) {
      console.log('发送:', message);
    },
    handleError(error) {
      console.error('错误:', error);
    },
    // 外部控制
    externalSend() {
      this.$refs.chatBotRef.sendMessage('Hello');
    },
    switchSession(code) {
      this.$refs.chatBotRef.switchSession(code);
    },
  },
};
</script>
```

:::

## Props 参考

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | `string` | — | **必填**。后端 API 地址（来自 AIDev 平台） |
| `autoLoad` | `boolean` | `true` | 是否在挂载时自动加载 Agent 信息和会话列表 |
| `sessionCode` | `string` | — | 指定初始会话 Code，传入后自动切换到该会话 |
| `shortcuts` | `Shortcut[]` | `[]` | 快捷指令列表（通常由 AIDev 后台配置自动加载，此 prop 用于覆盖或补充） |
| `shortcutLimit` | `number` | `6` | 欢迎页快捷指令最大展示数量 |
| `resources` | `Resource[]` | `[]` | 资源列表，用于上下文增强 |
| `prompts` | `Prompt[]` | `[]` | 预设 Prompt 列表 |
| `helloText` | `string` | — | 欢迎语文本，不传则使用 Agent 默认欢迎语 |
| `placeholder` | `string` | — | 输入框占位文本 |
| `height` | `string \| number` | `'100%'` | 组件高度 |
| `maxWidth` | `string \| number` | — | 组件最大宽度 |
| `extCls` | `string` | — | 自定义外层 CSS 类名 |
| `requestOptions` | `RequestOptions` | — | 请求配置，支持自定义 headers、超时等 |

## Events 事件

| 事件名 | 参数 | 说明 |
|--------|------|------|
| `send-message` | `(message: string)` | 用户发送消息时触发 |
| `receive-start` | — | 开始接收 AI 响应时触发 |
| `receive-text` | `(text: string)` | 接收到流式文本片段时触发 |
| `receive-end` | — | AI 响应接收完成时触发 |
| `stop` | — | 用户手动停止生成时触发 |
| `error` | `(error: Error)` | 发生错误时触发 |
| `session-switched` | `(sessionCode: string)` | 会话切换完成时触发 |
| `shortcut-click` | `(shortcut: Shortcut)` | 用户点击快捷指令时触发 |
| `agent-info-loaded` | `(agentInfo: AgentInfo)` | Agent 信息加载完成时触发 |
| `feedback` | `(type: 'like' \| 'unlike', messageId: string)` | 用户对消息进行反馈时触发 |
| `confirm-share` | `(messages: Message[])` | 用户确认分享时触发 |
| `cancel-share` | — | 用户取消分享时触发 |
| `request-share` | — | 用户请求进入分享模式时触发 |

## Expose 方法

通过 `ref` 获取组件实例后，可调用以下方法进行外部控制：

| 方法 / 属性 | 类型 | 说明 |
|-------------|------|------|
| `sendMessage(text)` | `(text: string) => Promise<void>` | 以编程方式发送消息 |
| `stopGeneration()` | `() => void` | 停止当前正在生成的响应 |
| `switchSession(code)` | `(code: string) => Promise<void>` | 切换到指定会话 |
| `setCiteText(text)` | `(text: string) => void` | 设置引用文本到输入框 |
| `focusInput()` | `() => void` | 聚焦输入框 |
| `selectShortcut(shortcut, selectedText?)` | `(shortcut: IShortcut, selectedText?: string) => void` | 选择快捷指令并显示表单 |
| `sendShortcut(shortcut, selectedText?)` | `(shortcut: IShortcut, selectedText?: string) => Promise<void>` | 直接发送快捷指令（跳过表单） |
| `enterShareMode()` | `() => void` | 进入分享选择模式 |
| `exitShareMode()` | `() => void` | 退出分享选择模式 |
| `getChatHelper()` | `() => IChatHelper \| null` | 获取内部 `chatHelper` 实例，用于高级操作 |
| `messages` | `ComputedRef<Message[]>` | 当前会话的消息列表（响应式） |
| `currentSession` | `Ref<ISession \| null>` | 当前会话信息（响应式） |
| `isGenerating` | `Ref<boolean>` | 是否正在生成中（响应式） |

## 独立模式 vs 集成模式

`ChatBot` 根据是否传入 `chatHelper` prop 自动切换运行模式：

| 对比项 | 独立模式（无 chatHelper） | 集成模式（传入 chatHelper） |
|--------|--------------------------|---------------------------|
| **chatHelper 来源** | ChatBot 内部自动创建 | 由父组件（如 AIBlueking）传入 |
| **生命周期管理** | ChatBot 自行管理创建和销毁 | 由父组件管理，ChatBot 仅使用 |
| **会话管理** | ChatBot 独立管理 | 与父组件共享同一 chatHelper，会话状态同步 |
| **适用场景** | 独立嵌入、简单集成 | 作为 AIBlueking 内部子组件使用 |
| **初始化流程** | 自动执行 getAgentInfo → getSessions → 选择会话 | 跳过初始化，复用已有状态 |
| **使用方式** | 直接使用 `<ChatBot url="..." />` | 通常不需要直接使用，由 AIBlueking 内部组装 |

> **提示**：大多数场景下推荐使用独立模式。仅在需要多个组件共享同一对话状态时，才考虑集成模式。
