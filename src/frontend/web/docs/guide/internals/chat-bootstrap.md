# 初始化生命周期

`useChatBootstrap` 是 AI 小鲸 v2.0 中负责组件初始化的核心组合式函数。它封装了从创建 `chatHelper` 到加载 Agent 信息、初始化会话的完整流程，并提供了状态机驱动的生命周期管理。

## useChatBootstrap 概述

`useChatBootstrap` 完成以下工作：

1. 创建 `chatHelper` 实例（包含 agent、session、message 三大模块）
2. 加载 Agent 配置信息（并行拉取会话列表；可选并行拉取 `GET llms/`）
3. 初始化或恢复会话
4. 提供响应式的初始化状态

```typescript
import { useChatBootstrap } from '@blueking/ai-blueking';

const {
  chatHelper,      // chatHelper 实例
  isReady,         // 是否初始化完成
  phase,           // 当前生命周期阶段
  agentInfo,       // Agent 配置信息
  agentName,       // Agent 名称
  currentSession,  // 当前会话
  error,           // 错误信息
  retry,           // 重试方法
} = useChatBootstrap({
  url: '/api/v1/agent/chat',
  requestOptions: {
    headers: () => ({ Authorization: `Bearer ${token}` }),
  },
  autoInit: true,
  protocolCallbacks: {
    onStart: () => console.log('流式传输开始'),
    onMessage: (chunk) => console.log('收到数据块:', chunk),
    onDone: () => console.log('流式传输完成'),
    onError: (err) => console.error('流式传输错误:', err),
  },
});
```

## BootstrapPhase 状态机

初始化过程由一个状态机驱动，共有 4 个状态：

![BootstrapPhase 状态机：IDLE → LOADING_AGENT → LOADING_SESSION → READY，各阶段可转入 ERROR](/images/guide/bootstrap-state-machine.png)

### 状态说明

| 状态 | 说明 | 触发条件 |
|------|------|---------|
| `IDLE` | 初始空闲状态 | 组件挂载，尚未开始初始化 |
| `LOADING_AGENT` | 正在加载 Agent 信息 | 调用 Agent 接口获取配置 |
| `LOADING_SESSION` | 正在初始化会话 | Agent 加载完成，开始加载/创建会话 |
| `READY` | 初始化完成，可以使用 | 会话加载成功 |
| `ERROR` | 初始化失败 | 任何阶段发生错误 |

### 状态监听

```typescript
import { watch } from 'vue';

watch(phase, (newPhase) => {
  switch (newPhase) {
    case 'IDLE':
      console.log('等待初始化...');
      break;
    case 'LOADING_AGENT':
      console.log('正在加载 Agent 信息...');
      break;
    case 'LOADING_SESSION':
      console.log('正在初始化会话...');
      break;
    case 'READY':
      console.log('初始化完成，可以开始对话！');
      break;
    case 'ERROR':
      console.error('初始化失败:', error.value);
      break;
  }
});
```

## 配置选项

### url

- **类型**：`string | Ref<string>`
- **必填**：是
- **说明**：Agent 服务的基础 URL，支持响应式值

```typescript
// 静态 URL
useChatBootstrap({ url: '/api/v1/agent/chat' });

// 响应式 URL（切换时自动重新初始化）
const agentUrl = ref('/api/v1/agent/default');
useChatBootstrap({ url: agentUrl });
```

### requestOptions

- **类型**：`MaybeRefOrGetter<IRequestOptions>`
- **必填**：否
- **说明**：请求配置；`headers` / `data` 支持对象、函数、`ref`、`computed`。`data` 对 GET 合并 query，对 POST 合并 body（与 [自定义请求](/guide/advanced-usage/custom-requests) 一致）

```typescript
useChatBootstrap({
  url: '/api/v1/agent/chat',
  requestOptions: {
    headers: () => ({
      Authorization: `Bearer ${getToken()}`,
      'X-Request-Id': generateRequestId(),
    }),
    data: () => ({
      app_id: 'my-app',
      tenant: 'default',
    }),
  },
});
```

### enableModelSelect

- **类型**：`boolean`
- **默认值**：`true`
- **说明**：是否在 bootstrap 时并行拉取可用模型列表（`GET llms/`）。失败不阻断初始化；列表非空时由上层展示 ModelSelector。详见 [模型选择](/guide/core-features/model-selection)

```typescript
useChatBootstrap({
  url: '/api/v1/agent/chat',
  enableModelSelect: false, // 关闭模型列表拉取
});
```

### autoInit

- **类型**：`boolean`
- **默认值**：`true`
- **说明**：是否在组合式函数调用时自动开始初始化。设为 `false` 可延迟初始化

```typescript
const bootstrap = useChatBootstrap({
  url: '/api/v1/agent/chat',
  autoInit: false,  // 不自动初始化
});

// 稍后手动触发
onMounted(() => {
  bootstrap.init();
});
```

### protocolCallbacks

- **类型**：`ProtocolCallbacks`
- **必填**：否
- **说明**：流式传输协议的回调函数，用于自定义流式响应处理

```typescript
useChatBootstrap({
  url: '/api/v1/agent/chat',
  protocolCallbacks: {
    onStart: () => {
      // 流式传输开始时调用
      showLoadingIndicator();
    },
    onMessage: (chunk: string) => {
      // 每收到一个数据块时调用
      processChunk(chunk);
    },
    onDone: () => {
      // 流式传输完成时调用
      hideLoadingIndicator();
    },
    onError: (error: Error) => {
      // 流式传输出错时调用
      showErrorMessage(error.message);
    },
  },
});
```

## 返回值

| 属性 | 类型 | 说明 |
|------|------|------|
| `chatHelper` | `ChatHelper` | 核心 helper 实例，包含 agent、session、message 模块 |
| `isReady` | `Ref<boolean>` | 是否初始化完成 |
| `phase` | `Ref<BootstrapPhase>` | 当前生命周期阶段 |
| `agentInfo` | `Ref<AgentInfo>` | Agent 配置信息 |
| `agentName` | `Ref<string>` | Agent 显示名称 |
| `currentSession` | `Ref<Session>` | 当前活跃会话 |
| `error` | `Ref<Error | null>` | 错误信息 |
| `retry` | `() => void` | 重试初始化 |

## 响应式 URL 变更

当 `url` 参数为响应式引用时，URL 变化会自动触发重新初始化：

```typescript
const agentUrl = ref('/api/v1/agent/default');

const { isReady, agentInfo } = useChatBootstrap({
  url: agentUrl,
});

// 切换 Agent 时，修改 URL 即可
function switchAgent(agentId: string) {
  agentUrl.value = `/api/v1/agent/${agentId}`;
  // useChatBootstrap 会自动：
  // 1. 清理当前状态
  // 2. 重新进入 LOADING_AGENT 阶段
  // 3. 加载新的 Agent 信息
  // 4. 初始化新的会话
}
```

## 错误恢复与重试

初始化过程中的错误会被捕获，并提供重试机制：

```typescript
const { phase, error, retry } = useChatBootstrap({
  url: '/api/v1/agent/chat',
});

// 在模板中展示错误状态和重试按钮
```

```vue
<template>
  <div v-if="phase === 'ERROR'" class="error-state">
    <p>初始化失败：{{ error?.message }}</p>
    <button @click="retry">重新加载</button>
  </div>
  <div v-else-if="!isReady" class="loading-state">
    <Spinner />
    <p>正在加载...</p>
  </div>
  <ChatBot v-else :chat-helper="chatHelper" />
</template>
```

### 自动重试

你也可以配合自定义逻辑实现自动重试：

```typescript
watch(phase, (newPhase) => {
  if (newPhase === 'ERROR') {
    // 3 秒后自动重试，最多重试 3 次
    if (retryCount.value < 3) {
      setTimeout(() => {
        retryCount.value++;
        retry();
      }, 3000);
    }
  }
});
```

## 组件集成方式

### AIBlueking 内部集成

`AIBlueking` 组件内部已经使用了 `useChatBootstrap`，你只需传入 `url` 即可：

```vue
<template>
  <!-- AIBlueking 内部自动调用 useChatBootstrap -->
  <AIBlueking
    url="/api/v1/agent/chat"
    :request-options="requestOptions"
  />
</template>
```

### ChatBot 独立使用

`ChatBot` 组件在独立使用时需要外部提供 `chatHelper`：

```vue
<template>
  <ChatBot
    v-if="isReady"
    :chat-helper="chatHelper"
    :url="url"
  />
</template>

<script setup lang="ts">
const { chatHelper, isReady } = useChatBootstrap({
  url: '/api/v1/agent/chat',
  requestOptions: { /* ... */ },
});
</script>
```

## 完整代码示例

以下是一个完整的初始化集成示例：

```vue
<template>
  <div class="chat-container">
    <!-- 加载状态 -->
    <div v-if="phase === 'LOADING_AGENT'" class="loading">
      正在连接 AI 助手...
    </div>
    <div v-else-if="phase === 'LOADING_SESSION'" class="loading">
      正在准备会话...
    </div>

    <!-- 错误状态 -->
    <div v-else-if="phase === 'ERROR'" class="error">
      <p>{{ error?.message }}</p>
      <button @click="retry">重试</button>
    </div>

    <!-- 就绪状态 -->
    <ChatBot
      v-else-if="isReady"
      :chat-helper="chatHelper"
      :url="agentUrl"
      @send-message="onSendMessage"
      @receive-end="onReceiveEnd"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot, useChatBootstrap } from '@blueking/ai-blueking';

const agentUrl = ref('/api/v1/agent/chat');

const {
  chatHelper,
  isReady,
  phase,
  agentInfo,
  error,
  retry,
} = useChatBootstrap({
  url: agentUrl,
  requestOptions: {
    headers: () => ({
      Authorization: `Bearer ${localStorage.getItem('token')}`,
    }),
  },
  protocolCallbacks: {
    onStart: () => console.log('开始接收回复'),
    onDone: () => console.log('回复接收完毕'),
    onError: (err) => console.error('回复出错:', err),
  },
});

const onSendMessage = (payload: { content: string }) => {
  console.log('用户发送:', payload.content);
};

const onReceiveEnd = (payload: { message: any }) => {
  console.log('AI 回复:', payload.message);
};
</script>
```
