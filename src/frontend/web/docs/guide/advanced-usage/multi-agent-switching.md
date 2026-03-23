# 多 Agent 切换

本文介绍如何在同一个页面中实现多个 Agent 之间的动态切换。

## 场景

- 应用内集成了多个 AI 助手（如"代码助手"、"运维助手"、"文档助手"）
- 用户需要在不同助手之间自由切换
- 每个助手对应 AIDev 平台上不同的 Agent 配置（不同的 URL）

## 方案一：`:key` 强制重建（推荐）

最简单且最可靠的方式。当 `url` 变化时，通过 `:key` 强制销毁并重建组件，组件内部会自动用新 URL 重新初始化 `chatHelper`。

### ChatBot 用法

```vue
<template>
  <div class="multi-agent-page">
    <!-- Agent 切换栏 -->
    <div class="agent-tabs">
      <button
        v-for="agent in agents"
        :key="agent.id"
        :class="['agent-tab', { active: currentAgent.id === agent.id }]"
        @click="switchAgent(agent)"
      >
        {{ agent.name }}
      </button>
    </div>

    <!-- ChatBot：key 变化时整个组件销毁重建 -->
    <div class="chat-area" style="height: 600px;">
      <ChatBot
        :url="currentAgent.url"
        :key="currentAgent.id"
        :request-options="requestOptions"
        @error="onError"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';

interface AgentConfig {
  id: string;
  name: string;
  url: string;
}

const agents: AgentConfig[] = [
  { id: 'code', name: '代码助手', url: 'https://aidev.example.com/api/code-agent/' },
  { id: 'ops', name: '运维助手', url: 'https://aidev.example.com/api/ops-agent/' },
  { id: 'doc', name: '文档助手', url: 'https://aidev.example.com/api/doc-agent/' },
];

const currentAgent = ref<AgentConfig>(agents[0]);

const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
};

const switchAgent = (agent: AgentConfig) => {
  currentAgent.value = agent;
};

const onError = (error: Error) => {
  console.error(`${currentAgent.value.name} 错误:`, error);
};
</script>
```

### AIBlueking 用法

AIBlueking 完全一致，同样通过 `:key` 强制重建：

```vue
<template>
  <div>
    <select v-model="currentAgentId" @change="onAgentChange">
      <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
    </select>

    <AIBlueking
      :url="currentAgentUrl"
      :key="currentAgentId"
      :request-options="requestOptions"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const agents = [
  { id: 'code', name: '代码助手', url: 'https://aidev.example.com/api/code-agent/' },
  { id: 'ops', name: '运维助手', url: 'https://aidev.example.com/api/ops-agent/' },
];

const currentAgentId = ref('code');
const currentAgentUrl = computed(() =>
  agents.find(a => a.id === currentAgentId.value)!.url
);

const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
};

const onAgentChange = () => {
  // key 变化会自动销毁重建组件，无需额外处理
};
</script>
```

::: tip 关键：使用 `:key` 强制重建
通过 `:key="currentAgent.id"` 确保切换 Agent 时组件完全销毁并重建，避免旧 Agent 的状态残留。这也是 Vue 推荐的组件重置方式。
:::

## 方案二：`useChatBootstrap` 响应式 URL

`useChatBootstrap` 支持传入响应式的 `url`（`ref`/`computed`/`getter`），当 URL 变化时会自动调用 `updateConfig` 重新初始化。

这种方式不会销毁 ChatBot 组件，但会重新加载 Agent 信息和会话列表。

```vue
<template>
  <div class="multi-agent-page">
    <div class="agent-tabs">
      <button
        v-for="agent in agents"
        :key="agent.id"
        :class="{ active: currentAgentId === agent.id }"
        @click="currentAgentId = agent.id"
      >
        {{ agent.name }}
      </button>
    </div>

    <div class="chat-area" style="height: 600px;">
      <!-- 等待初始化完成 -->
      <template v-if="isReady">
        <ChatBot :chat-helper="chatHelper" :url="currentUrl" />
      </template>
      <div v-else-if="isInitializing">正在加载 {{ agentName }}...</div>
      <div v-else-if="error">初始化失败: {{ error.message }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { ChatBot, useChatBootstrap } from '@blueking/ai-blueking';

const agents = [
  { id: 'code', name: '代码助手', url: 'https://aidev.example.com/api/code-agent/' },
  { id: 'ops', name: '运维助手', url: 'https://aidev.example.com/api/ops-agent/' },
];

const currentAgentId = ref('code');

// 响应式 URL — useChatBootstrap 会自动监听变化
const currentUrl = computed(() =>
  agents.find(a => a.id === currentAgentId.value)!.url
);

const {
  chatHelper,
  isReady,
  isInitializing,
  error,
  agentName,
} = useChatBootstrap({
  url: currentUrl,  // 传入 ComputedRef，URL 变化时自动重新初始化
  requestOptions: {
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  },
  autoInit: true,
});
</script>
```

::: warning 注意
`useChatBootstrap` 的 `updateConfig` 方法内部依赖 `chatHelper.http.updateConfig()`。如果该方法尚未在当前版本的 `chat-helper` 中实现，URL 变更可能不会生效。此时请使用方案一（`:key` 强制重建）。
:::

## 方案对比

| 特性 | 方案一（`:key` 重建） | 方案二（响应式 URL） |
|------|------|------|
| **实现难度** | 简单，一行 `:key` | 需要 `useChatBootstrap` |
| **组件生命周期** | 切换时完全销毁重建 | 组件保留，SDK 重新初始化 |
| **对话状态** | 切换后丢失 | 切换后丢失（SDK 重置） |
| **适用组件** | ChatBot、AIBlueking 均可 | 仅 ChatBot（集成模式） |
| **兼容性** | 全版本可用 | 依赖 `updateConfig` 实现 |
| **推荐场景** | 通用场景 | 需要复用 chatHelper 的场景 |

> **推荐**：大多数场景使用方案一即可。方案二适合需要在外部持有 `chatHelper` 引用的高级场景（如同时控制多个面板、在切换前保存状态等）。
