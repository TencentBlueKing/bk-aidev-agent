# ChatBot 页面嵌入

ChatBot 是一个可独立使用的轻量聊天组件，无需额外面板即可快速嵌入到任何页面中。

<script setup>
import { defineAsyncComponent } from 'vue'
import '@blueking/ai-blueking/dist/vue3/style.css'
import { getRuntimeGlobal } from '../.vitepress/theme/utils/runtime-globals'

const apiUrl = getRuntimeGlobal('BK_AIDEV_API_URL')
const ChatBot = apiUrl ? defineAsyncComponent({
  loader: () => import('@blueking/ai-blueking').then(m => m.ChatBot),
}) : null
const onAgentLoaded = (helper) => {
  if (helper?.session) {
    helper.session.createSession({
      sessionCode: `demo_${Date.now()}`,
      sessionName: '新会话',
    })
  }
}
</script>

<ClientOnly>
  <div v-if="ChatBot" style="width: 100%; height: 500px; border: 1px solid var(--vp-c-divider); border-radius: 8px; overflow: hidden; margin-bottom: 24px;">
    <component :is="ChatBot" :url="apiUrl" hello-text="你好，我是 AI 小鲸" placeholder="输入你的问题..." @agent-info-loaded="onAgentLoaded" />
  </div>
  <div v-else class="custom-block tip">
    <p>在线演示需要后端环境支持。请参考下方代码示例进行集成。</p>
  </div>
</ClientOnly>

::: tip 构建完整聊天页面
需要构建带会话列表的完整聊天页面？参考 [自定义会话列表](/guide/advanced-usage/external-session-list)。嵌入式 ChatBot **不带 Header**，会话名称与侧栏开关须业务自建，见 [业务 Header](/guide/integration-modes/chatbot-embedded#业务-header会话名称--侧栏开关)。
:::

## 完整示例

::: code-group

```vue [Vue 3]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      ref="chatBotRef"
      url="https://your-aidev-url.com/api/"
      :request-options="requestOptions"
      placeholder="输入你的问题..."
      @send-message="handleSendMessage"
      @session-switched="handleSessionSwitched"
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
const handleSessionSwitched = (session) => console.log('会话切换:', session?.sessionName);
const handleError = (error: Error) => console.error('错误:', error);

// 外部控制：通过 ref 调用组件暴露的方法
const externalSend = () => chatBotRef.value?.sendMessage('Hello');
</script>
```

```vue [Vue 2]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      ref="chatBotRef"
      url="https://your-aidev-url.com/api/"
      :request-options="requestOptions"
      placeholder="输入你的问题..."
      @send-message="handleSendMessage"
      @session-switched="handleSessionSwitched"
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
    handleSessionSwitched(session) {
      console.log('会话切换:', session?.sessionName);
    },
    handleError(error) {
      console.error('错误:', error);
    },
    externalSend() {
      this.$refs.chatBotRef?.sendMessage('Hello');
    },
    getToken() {
      return 'your-token';
    },
  },
};
</script>
```

:::

## 关键说明

### url

- 必填项，指定后端 API 的基础地址（来自 AIDev 平台）。
- ChatBot 内部会基于该地址拼接各类接口路径（会话管理、消息发送等）。
- 快捷指令、提示词、欢迎语等均由 AIDev 后台配置，组件自动加载。

### requestOptions

- 用于配置请求头、超时等选项。
- `headers` 推荐使用**函数形式**，确保每次请求时获取最新的认证 token，避免 token 过期问题。

```ts
const requestOptions = {
  headers: () => ({
    Authorization: `Bearer ${getToken()}`,
    'X-Custom-Header': 'value',
  }),
};
```

### shortcuts

- 快捷指令通常由 AIDev 后台 `agent/info` 接口自动返回，组件初始化时自动加载，**无需前端定义**。
- 如需覆盖或补充，可通过 `shortcuts` prop 传入。详细配置请参考 [快捷指令](/guide/core-features/shortcuts) 章节。

### Expose 方法

通过 `ref` 获取 ChatBot 实例后，可调用以下暴露方法：

| 方法 | 说明 |
| --- | --- |
| `whenReady()` | （≥ v2.1.4-beta.13）等待初始化完成（含 sessionList） |
| `isReady` | （≥ v2.1.4-beta.13）是否已完成初始化（响应式） |
| `sendMessage(text)` | 以编程方式发送消息 |
| `switchSession(code)` | 切换到指定会话 |
| `getChatHelper()` | 获取底层 chatHelper 实例，进行高级操作 |

```ts
// 示例：等待就绪后发送
const chatBotRef = ref<ChatBotExpose>();
await chatBotRef.value?.whenReady();
chatBotRef.value?.sendMessage('请帮我总结这段文字');

// 示例：获取 chatHelper 进行高级操作
const helper = chatBotRef.value?.getChatHelper();
```
