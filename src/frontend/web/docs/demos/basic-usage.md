---
aside: false
---

# ChatBot 页面嵌入

ChatBot 只负责聊天区，可以嵌进页面任意位置；它**不带 Header**，会话名称、会话列表、侧栏开关都由业务自建。下面每个配方都在舞台里渲染自己的 ChatBot 实例。

```vue
<template>
  <div style="height: 600px">
    <ChatBot ref="chatBotRef" url="https://your-aidev-url.com/api/" :request-options="requestOptions" />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  const chatBotRef = ref<ChatBotExpose>();
  const requestOptions = { headers: () => ({ Authorization: `Bearer ${getToken()}` }) };
</script>
```

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 最小嵌入

嵌入式 ChatBot 没有 `show()`，挂载后用 `whenReady()` 等待智能体信息与会话列表加载完成，再发送消息或切换会话。

<ClientOnly>
  <RecipeMinimalEmbed />
</ClientOnly>

## 业务 Header + 会话列表

用 `@agent-info-loaded` 拿到 `chatHelper` 后，会话列表（`session.list`）、当前会话（`session.current`）都可以直接渲染在业务自己的 Header 和侧栏里；`v-model:aside-collapsed` 控制 ChatBot 右侧侧栏。代码页签展示的就是舞台里运行的组件。

<ClientOnly>
  <RecipeEmbeddedWorkbench />
</ClientOnly>

::: tip
本页两个 ChatBot 在 Mock 中属于同一个访客，会话列表互相可见——它们相当于同一用户的两个入口。
:::

## 相关文档

- [ChatBot 页面嵌入模式](/guide/integration-modes/chatbot-embedded)：完整 Props、Events、Expose，以及与集成模式的区别
- [自定义会话列表](/guide/advanced-usage/external-session-list)：更完整的会话列表实现
- [AIBlueking 浮窗](/demos/full-panel)：需要悬浮球与内置 Header 时
