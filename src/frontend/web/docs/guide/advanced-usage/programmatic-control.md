# 编程式控制

AI 小鲸 v2.0 通过 Vue 的模板引用（template ref）机制，暴露了丰富的编程式 API，允许你从外部代码精确控制聊天组件的行为。

::: info 非 Vue 宿主
若页面**没有 Vue 运行时**（React、纯 HTML 等），请使用 **v2.1.4-beta.8+** 的 [Standalone 子入口](/guide/integration-modes/standalone-bundle)：通过 `mountAIBlueking` / `mountChatBot` 返回的 `expose` 调用与下文 ref API 相同的方法（如 `show`、`sendMessage`）。
:::

## ChatBot 模板引用

### 获取引用

```vue
<template>
  <ChatBot ref="chatBotRef" url="/api/v1/agent/chat" />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { ChatBotExpose } from '@blueking/ai-blueking';

const chatBotRef = ref<ChatBotExpose>();
</script>
```

### 可用方法

#### sendMessage - 发送消息

```typescript
// 发送纯文本消息
chatBotRef.value?.sendMessage('帮我写一个 Python 排序函数');

// 发送带属性的消息
chatBotRef.value?.sendMessage('解释这段代码', {
  property: {
    extra: {
      cite: '被引用的代码内容...',
    },
  },
});
```

#### stopGeneration - 停止生成

```typescript
// 停止当前正在进行的 AI 回复
chatBotRef.value?.stopGeneration();
```

#### switchSession - 切换会话

```typescript
// 切换到指定会话（异步操作）
await chatBotRef.value?.switchSession('session-code-123');
```

#### setCiteText - 设置引用文本

```typescript
// 在输入框中设置引用文本
chatBotRef.value?.setCiteText('这段文本将作为引用上下文发送');
```

#### focusInput - 聚焦输入框

```typescript
// 让输入框获得焦点
chatBotRef.value?.focusInput();
```

#### updateAgentInfo - 刷新 Agent 信息（≥ v2.1.4-beta.14）

主动从后端重新拉取 agentInfo 并自动更新内部状态（如 shortcuts）：

```typescript
// 刷新 agentInfo 并获取最新数据
const info = await chatBotRef.value?.updateAgentInfo();
console.log('最新 agent 信息:', info);
```

适用场景：后端更新了智能体的快捷指令或会话配置后，前端无需重建组件即可同步最新状态。

#### whenReady / isReady - 等待初始化（≥ v2.1.4-beta.13）

独立嵌入的 `ChatBot` 没有 `AIBlueking.show()`，可在挂载后等待会话列表与最近会话加载完成再操作：

```typescript
// Promise 方式（推荐）
await chatBotRef.value?.whenReady();
await chatBotRef.value?.switchSession('session-code-123');

// 响应式判断
if (chatBotRef.value?.isReady) {
  chatBotRef.value.sendMessage('你好');
}
```

::: warning
`url` 变更会 reject 进行中的 `whenReady()`，需重新 `await whenReady()`。作为 `AIBlueking` 子组件时请使用 `await aiBluekingRef.show()`，勿依赖子 `ChatBot` 的 `whenReady`。
:::

与 `agent-info-loaded` 事件在独立模式下触发时机一致；事件适合声明式埋点，`whenReady` 适合 `async/await` 编排。

### 完整示例

```vue
<template>
  <div class="app">
    <div class="toolbar">
      <button @click="sendQuickMessage">快速提问</button>
      <button @click="stopReply" :disabled="!isGenerating">停止</button>
      <button @click="focusChat">聚焦输入</button>
    </div>
    <ChatBot ref="chatBotRef" url="/api/v1/agent/chat" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { ChatBotExpose } from '@blueking/ai-blueking';

const chatBotRef = ref<ChatBotExpose>();

const isGenerating = computed(() => chatBotRef.value?.isGenerating.value ?? false);

const sendQuickMessage = () => {
  chatBotRef.value?.sendMessage('你好，请介绍一下你自己');
};

const stopReply = () => {
  chatBotRef.value?.stopGeneration();
};

const focusChat = () => {
  chatBotRef.value?.focusInput();
};
</script>
```

## AIBlueking 模板引用

`AIBlueking` 作为带窗口管理的高层组件，暴露了额外的窗口控制方法。

### 获取引用

```vue
<template>
  <AIBlueking ref="aiBluekingRef" url="/api/v1/agent/chat" />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';
import type { AIBluekingExpose } from '@blueking/ai-blueking';

const aiBluekingRef = ref<AIBluekingExpose>();
</script>
```

### 可用方法

#### show - 显示窗口

`show()` 返回 `Promise<void>`。面板会**立即**显示；Promise 在会话初始化完成后 resolve：

- 始终等待 `sessionList`（`getSessions`）加载完成
- `loadRecentSessionOnMount` 为 `true`（默认）时，还会等待最近会话选定或创建完成
- 传入 `sessionCode` 时，在就绪后再切换到该会话

初始化失败时 Promise reject，并触发 `@sdk-error`（`apiName: 'init'`）。

```typescript
// 推荐：等待会话就绪后再执行业务逻辑
try {
  await aiBluekingRef.value?.show();

  const helper = aiBluekingRef.value?.getChatHelper();
  console.log('会话列表:', helper?.session.list.value);
  console.log('当前会话:', helper?.session.current.value);
} catch (error) {
  console.error('小鲸初始化失败:', error);
}

// 显示并切换到指定会话（切换发生在就绪之后）
await aiBluekingRef.value?.show('session-code-123');
```

::: info 与事件的区别
不需要额外监听 `sessions-loaded` 等内部事件来判断「能否读 session」。对集成方而言，`await show()` 即表示可安全访问 `getChatHelper()?.session`。
:::

#### hide - 隐藏窗口

```typescript
// 隐藏窗口
aiBluekingRef.value?.hide();
```

#### sendMessage - 发送消息

```typescript
// 发送消息（如果窗口未显示会自动显示）
aiBluekingRef.value?.sendMessage('你好');
```

#### addNewSession - 新建会话

```typescript
// 创建一个新的会话
aiBluekingRef.value?.addNewSession();
```

#### updatePosition - 更新窗口位置

```typescript
// 设置窗口左上角坐标 (x, y)
aiBluekingRef.value?.updatePosition(100, 200);
```

#### updateSize - 更新窗口大小

```typescript
// 设置窗口宽高 (width, height)
aiBluekingRef.value?.updateSize(600, 800);
```

#### updateAgentInfo - 刷新 Agent 信息（≥ v2.1.4-beta.14）

```typescript
// 刷新 agentInfo 并获取最新数据（自动更新 shortcuts 等状态）
const info = await aiBluekingRef.value?.updateAgentInfo();
```

### 完整示例

```vue
<template>
  <div class="app">
    <!-- 悬浮按钮 -->
    <button class="float-btn" @click="toggleChat">
      <span v-if="!isVisible">💬</span>
      <span v-else>✕</span>
    </button>

    <!-- AI 助手窗口 -->
    <AIBlueking
      ref="aiBluekingRef"
      url="/api/v1/agent/chat"
      @close="isVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';
import type { AIBluekingExpose } from '@blueking/ai-blueking';

const aiBluekingRef = ref<AIBluekingExpose>();
const isVisible = ref(false);

const toggleChat = async () => {
  if (isVisible.value) {
    aiBluekingRef.value?.hide();
    isVisible.value = false;
  } else {
    isVisible.value = true;
    try {
      await aiBluekingRef.value?.show();
    } catch {
      isVisible.value = false;
    }
  }
};
</script>
```

## 响应式状态监听

通过模板引用，你可以监听组件内部的响应式状态变化。

### ChatBot 状态

```typescript
import { watch } from 'vue';

// 监听初始化就绪（≥ v2.1.4-beta.13）
watch(
  () => chatBotRef.value?.isReady,
  (ready) => {
    if (ready) console.log('ChatBot 已就绪');
  },
);

// 监听消息列表变化
watch(
  () => chatBotRef.value?.messages.value,
  (messages) => {
    if (messages) {
      console.log('当前消息数量:', messages.length);
      // 可用于同步外部状态
      externalMessageCount.value = messages.length;
    }
  },
  { deep: true }
);

// 监听生成状态
watch(
  () => chatBotRef.value?.isGenerating.value,
  (generating) => {
    if (generating) {
      console.log('AI 正在回复...');
      disableOtherInputs();
    } else {
      console.log('AI 回复完毕');
      enableOtherInputs();
    }
  }
);
```

### 获取 ChatHelper 进行高级操作

对于更高级的场景，可以通过 `getChatHelper` 直接获取底层 `chatHelper` 实例：

```typescript
// 获取 chatHelper 实例
const helper = chatBotRef.value?.getChatHelper();

if (helper) {
  // 直接访问 agent 模块
  const agentInfo = helper.agent.getAgentInfo();

  // 直接访问 session 模块
  const sessions = helper.session.getSessionList();
  const currentSession = helper.session.getCurrentSession();

  // 直接访问 message 模块
  const messages = helper.message.getMessages();
}
```

## 外部集成模式

在复杂的应用中，你可能需要在 ChatBot 初始化完成后获取其内部能力，用于跨组件集成。

### 监听 Agent 加载完成

```vue
<template>
  <ChatBot
    ref="chatBotRef"
    url="/api/v1/agent/chat"
    @agent-info-loaded="onAgentLoaded"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { ChatBotExpose } from '@blueking/ai-blueking';

const chatBotRef = ref<ChatBotExpose>();

const onAgentLoaded = (agentInfo: any) => {
  console.log('Agent 加载完成:', agentInfo.name);

  // 获取 chatHelper 进行高级操作
  const helper = chatBotRef.value?.getChatHelper();

  if (helper) {
    // 使用底层 SDK 进行自定义操作
    setupCustomIntegration(helper);
  }
};

function setupCustomIntegration(helper: any) {
  // 示例：监听所有消息变化，同步到外部系统
  watch(
    () => helper.message.getMessages(),
    (messages) => {
      syncToExternalSystem(messages);
    },
    { deep: true }
  );
}
</script>
```

### 跨组件通信

```typescript
// store/chat.ts - 使用 Pinia 或其他状态管理
import { defineStore } from 'pinia';

export const useChatStore = defineStore('chat', () => {
  const chatBotRef = ref<ChatBotExpose | null>(null);

  // 注册 ChatBot 引用
  function registerChatBot(ref: ChatBotExpose) {
    chatBotRef.value = ref;
  }

  // 任何组件都可以调用的方法
  function sendMessage(content: string) {
    chatBotRef.value?.sendMessage(content);
  }

  function stopGeneration() {
    chatBotRef.value?.stopGeneration();
  }

  return { registerChatBot, sendMessage, stopGeneration };
});
```

```vue
<!-- 页面 A：注册 ChatBot -->
<template>
  <ChatBot ref="chatBotRef" url="/api/v1/agent/chat" />
</template>

<script setup lang="ts">
import { onMounted } from 'vue';
import { useChatStore } from '@/store/chat';

const chatBotRef = ref<ChatBotExpose>();
const chatStore = useChatStore();

onMounted(() => {
  if (chatBotRef.value) {
    chatStore.registerChatBot(chatBotRef.value);
  }
});
</script>
```

```vue
<!-- 页面 B：远程控制 ChatBot -->
<template>
  <button @click="askAI">向 AI 提问</button>
</template>

<script setup lang="ts">
import { useChatStore } from '@/store/chat';

const chatStore = useChatStore();

const askAI = () => {
  chatStore.sendMessage('请帮我分析这个数据');
};
</script>
```
