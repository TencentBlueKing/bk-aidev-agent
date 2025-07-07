# 会话管理 <Badge type="tip" text="v1.1.0" />

AI 小鲸提供了强大的会话管理功能，包括多会话支持、会话内容访问等高级特性。本指南将详细介绍如何使用这些功能。

## 多会话管理 <Badge type="tip" text="v1.1.0" />

从 v1.1.0 开始，AI 小鲸支持多会话管理功能，让您可以同时管理多个独立的聊天会话，每个会话保持独立的对话上下文和历史记录。

### 功能概览

多会话管理功能包含以下核心特性：

- **🆕 会话创建**：快速创建新的聊天会话
- **🔄 会话切换**：在不同会话间无缝切换
- **📊 历史管理**：按时间分组查看和管理历史会话
- **✏️ 会话重命名**：自定义会话名称便于识别
- **🗑️ 会话删除**：安全删除不需要的会话
- **🔍 会话搜索**：快速查找特定会话

### 基础使用

#### 启用多会话功能

多会话功能默认启用，您只需要正常使用 AI 小鲸组件：

```vue
<template>
  <AIBlueking :url="apiUrl" />
</template>

<script setup>
import { AIBlueking } from '@blueking/ai-blueking';

const apiUrl = 'your-ai-service-url';
</script>
```

#### 控制界面元素显示

您可以通过属性控制会话管理相关图标的显示：

```vue
<template>
  <!-- 显示所有会话管理功能 -->
  <AIBlueking
    :url="apiUrl"
    :show-history-icon="true"
    :show-new-chat-icon="true"
  />

  <!-- 只显示新聊天功能 -->
  <AIBlueking
    :url="apiUrl"
    :show-history-icon="false"
    :show-new-chat-icon="true"
  />

  <!-- 隐藏所有会话管理图标 -->
  <AIBlueking
    :url="apiUrl"
    :show-history-icon="false"
    :show-new-chat-icon="false"
  />
</template>
```

## 访问会话内容

有时您可能需要从外部访问或记录 AI 小鲸当前的对话历史记录。AI 小鲸通过 `sessionContents` 属性将当前的会话内容暴露出来。

`sessionContents` 是一个数组，包含了当前对话的所有消息记录。每个消息对象通常包含角色（如 'user', 'assistant'）和内容（`content`）等信息。具体的结构取决于您的后端 AI 服务返回的数据格式以及组件内部的处理逻辑。

::: tip 提示
`sessionContents` 是一个响应式属性，它会随着对话的进行而更新。在多会话环境下，它始终反映当前活跃会话的内容。
:::

### 会话内容访问示例

:::code-group
```vue [Vue 3]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <div class="controls">
      <button @click="showSessionContents">显示当前会话内容</button>
      <button @click="checkLoadingState">检查加载状态</button>
      <button @click="getCurrentSessionInfo">获取会话信息</button>
    </div>
    <div v-if="sessionInfo" class="session-info">
      <h3>当前会话信息</h3>
      <p>加载状态: {{ sessionInfo.isLoading ? '加载中' : '已完成' }}</p>
      <p>消息数量: {{ sessionInfo.messageCount }}</p>
    </div>
    <pre v-if="sessionLog.length" class="session-log">{{ sessionLog }}</pre>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking, { type AIBluekingInstance } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<AIBluekingInstance | null>(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
const sessionLog = ref<any[]>([]);
const sessionInfo = ref<any>(null);

const showSessionContents = () => {
  if (aiBlueking.value?.sessionContents) {
    // 直接访问组件实例上的 sessionContents
    sessionLog.value = JSON.parse(JSON.stringify(aiBlueking.value.sessionContents)); // 深拷贝以显示快照
    console.log('当前会话内容:', aiBlueking.value.sessionContents);
    // 在这里可以将内容发送到日志服务或进行其他处理
  }
};

const checkLoadingState = () => {
  if (aiBlueking.value) {
    const isLoading = aiBlueking.value.isLoadingSessionContents;
    console.log('会话内容加载状态:', isLoading);
  }
};

const getCurrentSessionInfo = () => {
  if (aiBlueking.value) {
    sessionInfo.value = {
      isLoading: aiBlueking.value.isLoadingSessionContents || false,
      messageCount: aiBlueking.value.sessionContents?.length || 0,
      currentSessionLoading: aiBlueking.value.currentSessionLoading || false
    };
  }
};
</script>

<style scoped>
.controls {
  margin: 10px 0;
  display: flex;
  gap: 10px;
}

.session-info {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.session-log {
  background: #f8f8f8;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <div class="controls">
      <button @click="showSessionContents">显示当前会话内容</button>
      <button @click="checkLoadingState">检查加载状态</button>
      <button @click="getCurrentSessionInfo">获取会话信息</button>
    </div>
    <div v-if="sessionInfo" class="session-info">
      <h3>当前会话信息</h3>
      <p>加载状态: {{ sessionInfo.isLoading ? '加载中' : '已完成' }}</p>
      <p>消息数量: {{ sessionInfo.messageCount }}</p>
    </div>
    <pre v-if="sessionLog.length" class="session-log">{{ sessionLog }}</pre>
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/',
      sessionLog: [],
      sessionInfo: null
    };
  },
  methods: {
    showSessionContents() {
      if (this.$refs.aiBlueking?.sessionContents) {
        // 直接访问组件实例上的 sessionContents
        this.sessionLog = JSON.parse(JSON.stringify(this.$refs.aiBlueking.sessionContents)); // 深拷贝以显示快照
        console.log('当前会话内容:', this.$refs.aiBlueking.sessionContents);
        // 在这里可以将内容发送到日志服务或进行其他处理
      }
    },
    checkLoadingState() {
      if (this.$refs.aiBlueking) {
        const isLoading = this.$refs.aiBlueking.isLoadingSessionContents;
        console.log('会话内容加载状态:', isLoading);
      }
    },
    getCurrentSessionInfo() {
      if (this.$refs.aiBlueking) {
        this.sessionInfo = {
          isLoading: this.$refs.aiBlueking.isLoadingSessionContents || false,
          messageCount: this.$refs.aiBlueking.sessionContents?.length || 0,
          currentSessionLoading: this.$refs.aiBlueking.currentSessionLoading || false
        };
      }
    }
  }
};
</script>

<style scoped>
.controls {
  margin: 10px 0;
  display: flex;
  gap: 10px;
}

.session-info {
  background: #f5f5f5;
  padding: 10px;
  border-radius: 4px;
  margin: 10px 0;
}

.session-log {
  background: #f8f8f8;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
```
:::


## 技术说明

### API 要求

多会话功能需要后端 API 支持以下接口：

- 会话创建和管理
- 会话内容的获取和保存
- 会话元数据的更新

请确保您的 AI 服务支持这些会话管理功能，可从 AIDEV 官网中创建新智能体体验。

### 数据结构

会话内容的典型数据结构：

```typescript
interface SessionContent {
  role: 'user' | 'assistant' | 'system';
  content: string;
  sessionCode: string;
  property?: {
    extra?: {
      cite?: string;
      shortcut?: any;
    };
  };
  status?: 'loading' | 'success' | 'error';
  createdAt?: string;
}
```

### 暴露的属性和方法

组件实例暴露的会话相关属性：

- `sessionContents`: 当前会话的消息内容数组
- `isLoadingSessionContents`: 会话内容是否正在加载
- `currentSessionLoading`: 当前是否有消息正在生成
