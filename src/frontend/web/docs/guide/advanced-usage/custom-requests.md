# 自定义请求

在实际业务中，您可能需要在 AI 小鲸发出的请求中附加额外参数，例如身份验证 Token、业务标识、租户信息等。AI 小鲸通过 `requestOptions` prop 提供了完整的请求定制能力。

## 概览

`requestOptions` 支持以下配置项：

| 字段 | 类型 | 作用范围 | 说明 |
| --- | --- | --- | --- |
| `headers` | `Record<string, string>` | 所有接口 | 自定义请求头 |
| `data` | `Record<string, any>` | 仅 `chat_completion` | 附加到聊天请求体中的额外字段 |
| `context` | `Object \| Array \| Function` | 存入消息元数据 | 上下文信息，存入 `property.extra` |
| `beforeRequest` | `Function` | **所有接口** | 请求拦截器，可修改任意请求的 URL、data、headers |
| `afterRequest` | `Function` | 所有接口 | 响应回调，用于统一的请求后处理 |

::: tip 关键区别
- `data`：**仅影响聊天流式请求**（`chat_completion`），不会附加到会话管理等其他 API
- `beforeRequest`：**影响所有接口**，包括 GET 请求（会话列表、会话内容等）和 POST 请求（聊天、创建会话等）
- `context`：**不会发送到 HTTP 请求体**，而是存入消息的 `property.extra` 元数据中
:::

## 完整类型定义

```typescript
interface IRequestOptions {
  /** 自定义请求头，会合并到所有请求中 */
  headers?: Record<string, string>

  /** 附加到聊天请求体的额外字段（仅影响 chat_completion 接口） */
  data?: Record<string, any>

  /** 上下文信息，存入消息的 property.extra 中 */
  context?: Record<string, string> | Record<string, string>[] | (() => Record<string, string>)

  /** 请求拦截器，在每个请求发出前调用，可修改 url、data、headers */
  beforeRequest?: (requestData: RequestHookData) => RequestHookData | undefined

  /** 响应回调，在每个请求完成后调用 */
  afterRequest?: (requestData: RequestHookData, response: Response) => void
}

interface RequestHookData {
  url: string
  data?: unknown
  headers?: Record<string, string>
}
```

## 基础用法

### 自定义请求头和请求体

最简单的用法是通过 `headers` 和 `data` 添加静态参数：

:::code-group

```vue [Vue 3]
<template>
  <AIBlueking
    :url="apiUrl"
    :request-options="{
      headers: {
        Authorization: 'Bearer your-token-here',
        'X-Custom-Header': 'some-value',
      },
      data: {
        preset: 'QA',
      },
    }"
  />
</template>

<script lang="ts" setup>
import { AIBlueking } from '@blueking/ai-blueking'
import '@blueking/ai-blueking/dist/style.css'

const apiUrl = 'https://your-api-endpoint.com/assistant/'
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking :url="apiUrl" :request-options="requestOptions" />
</template>

<script>
import { AIBlueking } from '@blueking/ai-blueking/vue2'
import '@blueking/ai-blueking/dist/style.css'

export default {
  components: { AIBlueking },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/',
      requestOptions: {
        headers: {
          Authorization: 'Bearer your-token-here',
          'X-Custom-Header': 'some-value',
        },
        data: {
          preset: 'QA',
        },
      },
    }
  },
}
</script>
```

:::

::: warning data 的作用范围
`data` 中的字段会被**展平合并**到 `chat_completion` 的请求体顶层。例如 `data: { preset: 'QA' }` 最终请求体为：
```json
{
  "session_content_id": 123,
  "session_code": "xxx",
  "execute_kwargs": { "stream": true },
  "preset": "QA"
}
```
如果需要在**所有接口**（包括 GET 请求）都附加额外参数，请使用下方的 `beforeRequest`。
:::

## 请求拦截器 `beforeRequest`

`beforeRequest` 是最强大的请求定制手段，它会在**每个请求发出前**被调用，无论是 GET 还是 POST 请求。

### 工作原理

```
用户操作 → 组件构造请求 → beforeRequest 拦截 → 发出最终请求
                              ↑
                    可修改 url / data / headers
```

- **GET 请求**（如获取会话列表）：`data` 中的字段会自动拼接为 URL 查询参数
- **POST 请求**（如聊天、创建会话）：`data` 作为 JSON 请求体发送
- **Stream 请求**（聊天流式响应）：同样经过 `beforeRequest` 拦截

### 基础示例：为所有接口添加参数

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :request-options="{
      beforeRequest: (requestData) => ({
        ...requestData,
        data: {
          ...(requestData.data ?? {}),
          biz_id: '123',
          app_code: 'my-app',
        },
      }),
    }"
  />
</template>
```

效果：

| 接口 | 方法 | 效果 |
| --- | --- | --- |
| `/session/` | GET | URL 变为 `/session/?biz_id=123&app_code=my-app` |
| `/session_content/content/` | GET | URL 变为 `/session_content/content/?session_code=xxx&biz_id=123&app_code=my-app` |
| `/chat_completion/` | POST | 请求体包含 `{ ..., biz_id: '123', app_code: 'my-app' }` |
| `/session/` | POST | 请求体包含 `{ ..., biz_id: '123', app_code: 'my-app' }` |

### 动态参数

```vue
<template>
  <AIBlueking :url="apiUrl" :request-options="requestOptions" />
</template>

<script setup>
import { computed } from 'vue'

const requestOptions = computed(() => ({
  beforeRequest: (requestData) => ({
    ...requestData,
    data: {
      ...(requestData.data ?? {}),
      biz_id: getCurrentBizId(),
      operator: getCurrentUser(),
    },
    headers: {
      ...(requestData.headers ?? {}),
      Authorization: `Bearer ${getToken()}`,
    },
  }),
}))
</script>
```

### 按接口类型区分处理

如果需要根据请求 URL 做不同处理：

```vue
<script setup>
const requestOptions = {
  beforeRequest: (requestData) => {
    const extraParams = {
      biz_id: '123',
      app_code: 'my-app',
    }

    // 聊天接口添加额外的业务字段
    if (requestData.url.includes('chat_completion')) {
      return {
        ...requestData,
        data: {
          ...(requestData.data ?? {}),
          ...extraParams,
          model_preference: 'gpt-4',
        },
      }
    }

    // 其他接口只添加基础标识
    return {
      ...requestData,
      data: {
        ...(requestData.data ?? {}),
        ...extraParams,
      },
    }
  },
}
</script>
```

::: danger 重要
在 `beforeRequest` 中修改 `data` 时，务必使用展开运算符保留原有数据：
```javascript
// ✅ 正确：保留原有字段
data: { ...(requestData.data ?? {}), myField: 'value' }

// ❌ 错误：会覆盖 session_code 等必要字段
data: { myField: 'value' }
```
:::

## 上下文配置 `context` <Badge type="tip" text="v1.1.5" />

`context` 用于传递业务上下文信息给 AI 服务。与 `data` 不同，`context` **不会直接发送到 HTTP 请求体**，而是存入每条消息的 `property.extra` 元数据中，由后端从会话内容中读取。

### 支持的数据类型

```typescript
// 1. 静态对象 — 展开到 property.extra 中
context: { userId: '123', role: 'admin' }

// 2. 对象数组 — 合并到 property.extra.context 数组中（快捷指令场景）
context: [{ language: 'javascript' }, { mode: 'review' }]

// 3. 动态函数 — 每次发消息时调用，返回对象
context: () => ({ userId: getCurrentUserId(), timestamp: Date.now().toString() })
```

### 静态上下文

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :request-options="{
      context: {
        userId: '123',
        department: 'IT',
        role: 'admin',
      },
    }"
  />
</template>
```

### 动态上下文

适用于需要在每次发消息时获取最新信息的场景：

```vue
<template>
  <AIBlueking :url="apiUrl" :request-options="requestOptions" />
</template>

<script setup>
import { computed } from 'vue'

const requestOptions = computed(() => ({
  context: () => ({
    userId: getCurrentUser().id,
    sessionId: getSessionId(),
    timestamp: Date.now().toString(),
  }),
}))
</script>
```

### 上下文与快捷指令的配合

当使用快捷指令时，`context` 数组会与表单数据合并：

```javascript
// requestOptions.context 配置
context: [{ language: 'javascript' }, { mode: 'review' }]

// 用户填写的表单数据
[{ code: 'console.log("hello")' }, { style: 'standard' }]

// 最终存入 property.extra.context 的数据
[
  { code: 'console.log("hello")' },
  { style: 'standard' },
  { language: 'javascript' },
  { mode: 'review' },
]
```

::: warning 注意事项
- 动态上下文函数会在每次发送消息时调用，请避免在函数中执行耗时操作
- 上下文信息存入 `property.extra`，后端需要从会话内容中读取，而非从请求体中获取
:::

## 动态更新请求选项

在组件初始化后，可以通过 `updateRequestOptions` 方法动态更新请求选项：

```typescript
updateRequestOptions(options: {
  url?: string
  headers?: Record<string, string>
  data?: Record<string, any>
  context?: IContext
}): void
```

:::code-group

```vue [Vue 3]
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="switchAgent">切换智能体</button>
  <button @click="updateToken">更新令牌</button>
</template>

<script setup>
import { ref } from 'vue'
import { AIBlueking } from '@blueking/ai-blueking'

const aiBlueking = ref(null)
const apiUrl = 'https://api.example.com/agent1'

const switchAgent = () => {
  aiBlueking.value?.updateRequestOptions({
    url: 'https://api.example.com/agent2',
  })
}

const updateToken = () => {
  aiBlueking.value?.updateRequestOptions({
    headers: {
      Authorization: `Bearer ${getNewToken()}`,
    },
  })
}
</script>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <button @click="switchAgent">切换智能体</button>
  </div>
</template>

<script>
import { AIBlueking } from '@blueking/ai-blueking/vue2'

export default {
  components: { AIBlueking },
  data: () => ({
    apiUrl: 'https://api.example.com/agent1',
  }),
  methods: {
    switchAgent() {
      this.$refs.aiBlueking.updateRequestOptions({
        url: 'https://api.example.com/agent2',
      })
    },
  },
}
</script>
```

:::

## 请求体结构参考

以下是 AI 小鲸发送聊天请求时的完整请求体结构：

```javascript
// POST /chat_completion/
{
  // 内部字段（组件自动生成）
  session_content_id: 12345,
  session_code: 'session-uuid-12345',
  execute_kwargs: { stream: true },

  // 来自 chat() 调用时传入的 data（如快捷指令场景会包含 command、context）
  command: 'code_review',
  context: [
    { code: 'console.log("hello")' },
    { language: 'javascript' },
  ],

  // 来自 requestOptions.data（展平到顶层）
  preset: 'QA',
  userId: 'user123',
}
```

::: warning 字段冲突
如果 `requestOptions.data` 中的键名与组件内部字段（如 `session_content_id`、`session_code`）冲突，外部值**会覆盖**内部值，请谨慎命名。
:::

## URL 协议自动适配 <Badge type="tip" text="v1.1.5" />

AI 小鲸支持智能的 URL 协议适配：

| URL 格式 | 说明 |
| --- | --- |
| `/api/chat` | 相对路径，自动使用当前页面的协议和域名 |
| `//api.example.com/chat` | 协议相对路径，自动使用当前页面的协议 |
| `http://api.example.com/chat` | HTTPS 页面下自动转换为 HTTPS |
| `https://api.example.com/chat` | 任何环境下保持 HTTPS |

## 常见场景

### 场景一：所有接口加业务标识

需求：所有 API 请求都需要携带 `biz_id` 和 `app_code`。

```vue
<AIBlueking
  :url="apiUrl"
  :request-options="{
    beforeRequest: (req) => ({
      ...req,
      data: { ...(req.data ?? {}), biz_id: '123', app_code: 'my-app' },
    }),
  }"
/>
```

### 场景二：动态 Token + 静态业务参数

```vue
<script setup>
const requestOptions = computed(() => ({
  headers: {
    Authorization: `Bearer ${token.value}`,
  },
  data: {
    preset: 'QA',
  },
  beforeRequest: (req) => ({
    ...req,
    data: {
      ...(req.data ?? {}),
      tenant_id: currentTenant.value,
    },
  }),
}))
</script>
```

### 场景三：传递代码上下文给 AI

```vue
<AIBlueking
  :url="apiUrl"
  :request-options="{
    context: () => ({
      language: editor.getLanguage(),
      filePath: editor.getCurrentFile(),
      selectedCode: editor.getSelection(),
    }),
  }"
/>
```
