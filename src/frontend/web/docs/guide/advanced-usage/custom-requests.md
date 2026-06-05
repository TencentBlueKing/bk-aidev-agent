# 自定义请求

AI 小鲸 v2.0 提供了灵活的请求自定义能力，允许你配置请求头、请求体等，以适配不同的后端服务和认证方案。

## requestOptions 属性

`ChatBot` 和 `AIBlueking` 组件都接受 `requestOptions` 属性，用于全局配置所有 HTTP 请求。这是最常用的认证配置方式：

```typescript
import type { MaybeRequestValue } from '@blueking/chat-helper';
import type { MaybeRefOrGetter } from 'vue';
import type { IRequestOptions } from '@blueking/ai-blueking';

// 组件 props：整体可为 ref / computed
type RequestOptionsProp = MaybeRefOrGetter<IRequestOptions>;

interface IRequestOptions {
  /** 支持对象、零参函数、ref、computed */
  headers?: MaybeRequestValue<Record<string, string>>;
  /** 支持对象、零参函数、ref、computed；按 HTTP 方法写入 body 或 query */
  data?: MaybeRequestValue<Record<string, unknown>>;
  /** 上下文信息，合并到消息的 property.extra.context（≥ v2.1.4-beta.15） */
  context?: MaybeRequestValue<Record<string, unknown> | Array<Record<string, unknown>>>;
}
```

### 内部机制

当你在组件上传入 `requestOptions`：

1. **ChatBot 独立模式**：内部通过 `useChatHelper({ requestData: { urlPrefix, headers, data } })` 创建 SDK 实例，`requestOptions.headers/data` 会直接映射到 `requestData.headers/data`
2. **AIBlueking**：内部通过 `useChatBootstrap({ url, requestOptions })` 初始化，同样映射到 `useChatHelper` 的 `requestData`

两种组件底层走的是同一条路径，`requestOptions` 在 v2.0 中已完全适配。

### 基本用法

```vue
<template>
  <!-- ChatBot 和 AIBlueking 用法一致 -->
  <ChatBot
    url="/api/v1/agent/chat"
    :request-options="requestOptions"
  />
</template>

<script setup lang="ts">
import { ChatBot } from '@blueking/ai-blueking';

const requestOptions = {
  headers: () => ({
    Authorization: `Bearer ${getToken()}`,
    'X-App-Code': 'my-application',
  }),
  data: () => ({
    app_id: 'your-app',
    tenant_id: 'default',
  }),
};
</script>
```

AIBlueking 完全一致：

```vue
<template>
  <AIBlueking
    url="/api/v1/agent/chat"
    :request-options="requestOptions"
  />
</template>

<script setup lang="ts">
import { AIBlueking } from '@blueking/ai-blueking';

const requestOptions = {
  headers: () => ({
    Authorization: `Bearer ${getToken()}`,
    'X-App-Code': 'my-application',
  }),
};
</script>
```

### 说明

- `headers` / `data` 在**每次请求前**通过 `resolveRequestValue` 求值，支持普通对象、零参函数、`ref`、`computed`
- `headers` 合并到每个请求的 HTTP 头
- `data` 按方法自动分流：**POST/PUT/PATCH/DELETE** → 合并进 body；**GET/HEAD/OPTIONS** → 合并进 query（`params`）。在 Network 面板中，会话列表等 GET 应在 URL 上看到 `app_id` 等字段，发消息 POST 应在 Request Payload 中看到
- 外层 `requestOptions` 可为 `ref` / `computed`，整体替换后同样生效（无需销毁重建 `ChatBot` / `AIBlueking`）
- 直接使用 `@blueking/chat-helper` 时，在 `useChatHelper({ requestData: { headers, data } })` 中使用相同类型与分流规则

### 响应式示例（ref / computed）

::: tip 推荐
需要随登录态、租户切换而更新时，优先使用内层 `computed`，或外层 `computed<IRequestOptions>`，比仅依赖函数闭包更直观。
:::

```vue
<template>
  <AIBlueking url="/api/v1/agent/chat" :request-options="requestOptions" />
</template>

<script setup lang="ts">
import { computed, ref } from 'vue';
import { AIBlueking, type IRequestOptions } from '@blueking/ai-blueking';

const token = ref('token-alpha');
const appId = ref('my-app');
const tenantId = ref('tenant-001');

const requestOptions = computed<IRequestOptions>(() => ({
  headers: {
    Authorization: `Bearer ${token.value}`,
  },
  data: {
    app_id: appId.value,
    tenant_id: tenantId.value,
  },
}));

// 切换 token / app_id 后，下一次 getAgentInfo、getSessions、发消息等请求即携带新值
</script>
```

内层字段也可单独使用 `computed`：

```typescript
const requestOptions: IRequestOptions = {
  headers: computed(() => ({ Authorization: `Bearer ${token.value}` })),
  data: { locale: 'zh-cn' },
};
```

## 上下文参数 context

::: info 版本要求
`context` 字段需要 **≥ v2.1.4-beta.15**。
:::

`requestOptions.context` 用于向消息注入业务上下文（如当前页面信息、用户选择、表单数据等），数据会自动合并到消息的 `property.extra.context` 中，后端可通过该字段获取上下文进行处理。

### 支持的格式

| 格式 | 说明 |
| --- | --- |
| `Record<string, unknown>` | 简单 KV，每个 entry 自动转换为结构化条目 |
| `Array<Record<string, unknown>>` | 数组；已有 `__key` 的结构化条目直接透传，简单 KV 自动转换 |

转换后的结构化条目格式：

```typescript
{
  key: value,                    // 原始 KV
  context_type: 'input',         // 固定值
  __label: key,                  // 显示标签
  __key: key,                    // 唯一标识（用于去重）
  __value: value                 // 值
}
```

### 基本用法

```vue
<template>
  <ChatBot
    url="/api/v1/agent/chat"
    :request-options="requestOptions"
  />
</template>

<script setup lang="ts">
import { ChatBot } from '@blueking/ai-blueking';

const requestOptions = {
  headers: () => ({
    Authorization: `Bearer ${getToken()}`,
  }),
  context: {
    page: 'settings',
    module: 'user-management',
  },
};
</script>
```

发送消息时，`context` 会自动合并到 `property.extra.context`：

```json
{
  "property": {
    "extra": {
      "context": [
        { "page": "settings", "context_type": "input", "__label": "page", "__key": "page", "__value": "settings" },
        { "module": "user-management", "context_type": "input", "__label": "module", "__key": "module", "__value": "user-management" }
      ]
    }
  }
}
```

### 结构化数组格式

当需要更精细的控制时，可直接传入结构化数组：

```typescript
const requestOptions = {
  context: [
    { page: 'dashboard', context_type: 'input', __label: '页面', __key: 'page', __value: 'dashboard' },
    { role: 'admin', context_type: 'system', __label: '角色', __key: 'role', __value: 'admin' },
  ],
};
```

### 与快捷指令 context 的合并

当用户发送快捷指令时，快捷指令的表单数据会生成 `property.extra.context`。`requestOptions.context` 的条目会**追加**到快捷指令 context 之后；key 冲突时（以 `__key` 判断），`requestOptions` 的条目**覆盖**已有的快捷指令条目。

```typescript
// 快捷指令产生的 context: [{ code: '...', __key: 'code' }]
// requestOptions.context: [{ code: 'override', __key: 'code' }, { page: 'settings', __key: 'page' }]
// 最终合并结果: [{ code: 'override', __key: 'code' }, { page: 'settings', __key: 'page' }]
```

### 响应式 context

与 `headers` / `data` 一致，`context` 支持 `MaybeRequestValue`，可使用函数、`ref` 或 `computed`：

```typescript
import { computed, ref } from 'vue';

const currentPage = ref('dashboard');

const requestOptions = {
  context: computed(() => ({
    page: currentPage.value,
    timestamp: Date.now(),
  })),
};
```

## useChatBootstrap + ChatBot 组合模式

当需要更精细的控制时（如在 ChatBot 外部管理初始化流程、共享 `chatHelper` 给其他组件），可以使用 `useChatBootstrap` 创建 `chatHelper` 实例，再以集成模式传入 ChatBot。

这也是 `AIBlueking` 内部使用 ChatBot 的方式。

### 基本用法

```vue
<template>
  <div style="height: 600px;">
    <ChatBot
      v-if="isReady"
      :chat-helper="chatHelper"
      :url="url"
    />
    <div v-else>初始化中...</div>
  </div>
</template>

<script setup lang="ts">
import { ChatBot, useChatBootstrap } from '@blueking/ai-blueking';

const url = '/api/v1/agent/chat';

const {
  chatHelper,
  isReady,
  agentInfo,
  sessionList,
  currentSession,
} = useChatBootstrap({
  url,
  requestOptions: {
    headers: () => ({
      Authorization: `Bearer ${getToken()}`,
    }),
  },
  autoInit: true,  // 自动执行 getAgentInfo + getSessions
});
</script>
```

### useChatBootstrap 返回值

| 属性/方法 | 类型 | 说明 |
|-----------|------|------|
| `chatHelper` | `IChatHelper` | SDK 实例（同步创建，生命周期内不变） |
| `protocol` | `AGUIProtocol` | 流式协议实例 |
| `isReady` | `ComputedRef<boolean>` | Agent 信息是否加载完成 |
| `isInitializing` | `ComputedRef<boolean>` | 是否正在初始化中 |
| `phase` | `Ref<BootstrapPhase>` | 当前阶段：`IDLE` → `LOADING_AGENT` → `READY` / `ERROR` |
| `error` | `Ref<Error \| null>` | 初始化错误 |
| `agentInfo` | `ComputedRef<IAgentInfo \| null>` | Agent 配置信息 |
| `agentName` | `ComputedRef<string>` | Agent 名称 |
| `sessionList` | `ComputedRef<ISession[]>` | 会话列表 |
| `currentSession` | `ComputedRef<ISession \| null>` | 当前会话 |
| `initialize()` | `() => Promise<void>` | 手动触发初始化 |
| `retry()` | `() => Promise<void>` | 重试初始化 |
| `updateConfig(url)` | `(url: string) => Promise<void>` | 更新 URL 并重新初始化 |

### ChatBot 的两种模式

| 特性 | 独立模式 `<ChatBot url="...">` | 集成模式 `<ChatBot :chat-helper="helper">` |
|------|------|------|
| chatHelper 来源 | 内部自动创建 | 外部传入（如 useChatBootstrap） |
| 初始化 | 自动执行 getAgentInfo → getSessions → chooseSession | 跳过，复用外部已初始化的实例 |
| 适用场景 | 简单嵌入，快速集成 | 需要外部控制会话、共享实例 |
| 常用于 | 独立页面嵌入 | AIBlueking 内部、自定义会话列表 |

### 与 AIBlueking 配合

`AIBlueking` 内部就是用 `useChatBootstrap` + ChatBot 集成模式运作的。如果你需要完全自定义面板 UI（不用 AIBlueking 的浮球/拖拽），可以直接使用同样的模式：

```vue
<template>
  <div class="my-custom-panel">
    <!-- 自定义的会话列表 -->
    <aside>
      <div v-for="s in sessionList" :key="s.sessionCode">{{ s.sessionName }}</div>
    </aside>

    <!-- ChatBot 作为聊天区域 -->
    <main>
      <ChatBot
        v-if="isReady"
        :chat-helper="chatHelper"
        :url="url"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { watch } from 'vue';
import { ChatBot, useChatBootstrap, SessionBusinessManager } from '@blueking/ai-blueking';

const url = '/api/chat';

const { chatHelper, isReady, sessionList, agentInfo } = useChatBootstrap({
  url,
  requestOptions: {
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  },
});

// 创建 SessionBusinessManager 来管理会话（和 AIBlueking 内部做法一致）
const sessionManager = new SessionBusinessManager(
  chatHelper.session,
  chatHelper.agent,
);

// isReady 后加载最近会话
watch(isReady, async (ready) => {
  if (ready) {
    await sessionManager.loadRecentSession({ skipLoadSessions: true });
  }
});
</script>
```

## 拦截器

拦截器允许你在请求发出前和响应返回后执行自定义逻辑，适用于统一的错误处理、日志记录、数据转换等场景。

```typescript
const chatHelper = useChatHelper({
  interceptors: {
    request: (config) => {
      // 请求发出前的处理
      console.log('[请求]', config.url, config.method);

      // 可以修改 config 后返回
      config.headers['X-Timestamp'] = Date.now().toString();
      return config;
    },
    response: (response) => {
      // 响应返回后的处理
      console.log('[响应]', response.status, response.data);

      // 统一错误处理
      if (response.data.code !== 0) {
        showError(response.data.message);
      }

      return response;
    },
  },
});
```

### 请求拦截器

请求拦截器在每次 HTTP 请求发出之前执行：

```typescript
interceptors: {
  request: (config) => {
    // config 包含：url, method, headers, data 等
    // 必须返回修改后的 config
    return config;
  },
}
```

**常见用途：**

- 添加认证信息
- 注入追踪 ID
- 请求日志记录
- 请求数据转换

### 响应拦截器

响应拦截器在每次 HTTP 响应返回之后执行：

```typescript
interceptors: {
  response: (response) => {
    // response 包含：status, data, headers 等
    // 必须返回 response
    return response;
  },
}
```

**常见用途：**

- 统一错误码处理
- 响应数据转换
- 响应日志记录
- Token 过期自动刷新

### 完整拦截器示例

```typescript
const chatHelper = useChatHelper({
  interceptors: {
    request: (config) => {
      // 1. 注入追踪 ID
      config.headers['X-Request-Id'] = crypto.randomUUID();

      // 2. 记录请求日志
      console.log(`[${config.method?.toUpperCase()}] ${config.url}`);

      return config;
    },
    response: (response) => {
      // 1. 统一错误处理
      if (response.data?.code !== 0) {
        const msg = response.data?.message || '请求失败';
        // 特殊错误码处理
        if (response.data?.code === 401) {
          // Token 过期，跳转登录
          redirectToLogin();
        } else {
          showError(msg);
        }
      }

      // 2. 记录响应日志
      console.log(`[响应] 状态码: ${response.status}`);

      return response;
    },
  },
});
```

## 动态请求头

在实际项目中，请求头往往需要动态生成。以下是几种常见场景：

### Token 刷新

```typescript
const requestOptions = {
  headers: () => {
    // 每次请求都获取最新 token
    const token = tokenManager.getAccessToken();
    return {
      Authorization: `Bearer ${token}`,
    };
  },
};
```

### 请求追踪 ID

```typescript
const requestOptions = {
  headers: () => ({
    Authorization: `Bearer ${getToken()}`,
    'X-Request-Id': crypto.randomUUID(),       // 每次请求唯一 ID
    'X-Trace-Id': getTraceId(),                // 链路追踪 ID
    'X-Client-Timestamp': Date.now().toString(), // 客户端时间戳
  }),
};
```

### 基于环境的配置

```typescript
const requestOptions = {
  headers: () => {
    const base: Record<string, string> = {
      'X-App-Code': APP_CODE,
    };

    // 开发环境添加调试头
    if (import.meta.env.DEV) {
      base['X-Debug-Mode'] = 'true';
      base['X-Dev-User'] = 'developer';
    }

    return base;
  },
  data: () => ({
    env: import.meta.env.MODE,
    version: APP_VERSION,
  }),
};
```

## 综合示例

以下是一个包含认证、动态头部的完整配置示例：

```vue
<template>
  <AIBlueking
    url="/api/v1/agent/chat"
    :request-options="requestOptions"
  />
</template>

<script setup lang="ts">
import { AIBlueking } from '@blueking/ai-blueking';
import { useAuth } from '@/composables/auth';
import { useNotification } from '@/composables/notification';

const { getToken, refreshToken } = useAuth();
const { showError } = useNotification();

const requestOptions = {
  headers: () => ({
    // 动态获取最新 token
    Authorization: `Bearer ${getToken()}`,
    // 追踪信息
    'X-Request-Id': crypto.randomUUID(),
    'X-App-Code': 'my-application',
  }),
  data: () => ({
    // 附加到每个请求的业务数据
    app_id: 'my-app',
    tenant_id: getCurrentTenant(),
    locale: getCurrentLocale(),
  }),
};
</script>
```
