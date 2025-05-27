# 自定义请求

在某些场景下，您可能需要在发送给 AI 后端服务的请求中添加额外的参数，例如用于身份验证的 Token、用于区分业务场景的标识等。AI 小鲸提供了 `requestOptions` prop 来满足这一需求。

::: warning 版本变更提示
1.0版本对请求体结构有所调整，但保持了API的基本使用方式。
:::

## 配置 `requestOptions`

`requestOptions` 是一个对象，可以包含 `headers` 和 `data` 两个属性：

-   `headers` (Object): 一个对象，其键值对将被合并到最终请求的 **请求头 (Headers)** 中。
-   `data` (Object): 一个对象，其键值对将被合并到最终请求的 **请求体 (Body)** 中。

**示例：**

假设您需要在请求头中添加 `Authorization` 字段，并在请求体中添加 `preset` 字段。

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :request-options="customOptions"
  />
</template>

<script lang="ts" setup>
import { ref, reactive } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';

const customOptions = reactive({
  headers: {
    Authorization: 'Bearer your-token-here',
    'X-Custom-Header': 'some-value'
  },
  data: {
    preset: 'QA',
    userId: 'user123'
  }
});

// 如果 Token 是动态的，可以适时更新 customOptions.headers.Authorization
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :request-options="customOptions"
  />
</template>

<script>
import { AIBlueking } from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/',
      customOptions: {
        headers: {
          Authorization: 'Bearer your-token-here',
          'X-Custom-Header': 'some-value'
        },
        data: {
          preset: 'QA',
          userId: 'user123'
        }
      }
    };
  },
  // 如果 Token 是动态的，可以在 updated 或 watch 中更新 this.customOptions.headers.Authorization
};
</script>
```
:::

## 动态更新请求选项

在实际应用中，您可能需要在组件初始化后动态更新请求选项，例如在用户登录后添加授权令牌，或者切换到不同的智能体。AI 小鲸提供了 `updateRequestOptions` 方法来支持这一需求。

### 使用方法

```typescript
// 方法签名
updateRequestOptions(options: {
  url?: string;            // 可选，更新API地址
  headers?: Record<string, string>; // 可选，更新请求头
  data?: Record<string, any>;      // 可选，更新请求体附加数据
}): void
```

### 示例

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <div class="controls">
    <button @click="switchAgent">切换智能体</button>
    <button @click="updateToken">更新令牌</button>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const aiBlueking = ref(null);
const apiUrl = 'https://api.example.com/agent1';

// 切换智能体API地址
const switchAgent = () => {
  const newUrl = 'https://api.example.com/agent2';
  aiBlueking.value?.updateRequestOptions({
    url: newUrl,
  });
  
  // 重新初始化会话以获取新智能体配置
  aiBlueking.value?.initSession();
};

// 更新授权令牌
const updateToken = () => {
  const newToken = getNewToken(); // 假设这是获取新令牌的函数
  aiBlueking.value?.updateRequestOptions({
    headers: {
      'Authorization': `Bearer ${newToken}`
    }
  });
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <div class="controls">
      <button @click="switchAgent">切换智能体</button>
      <button @click="updateToken">更新令牌</button>
    </div>
  </div>
</template>

<script>
import { AIBlueking } from '@blueking/ai-blueking/vue2';

export default {
  components: { AIBlueking },
  data: () => ({ 
    apiUrl: 'https://api.example.com/agent1'
  }),
  methods: {
    // 切换智能体API地址
    switchAgent() {
      const newUrl = 'https://api.example.com/agent2';
      this.$refs.aiBlueking.updateRequestOptions({
        url: newUrl,
      });
      
      // 重新初始化会话以获取新智能体配置
      this.$refs.aiBlueking.initSession();
    },
    
    // 更新授权令牌
    updateToken() {
      const newToken = this.getNewToken(); // 假设这是获取新令牌的函数
      this.$refs.aiBlueking.updateRequestOptions({
        headers: {
          'Authorization': `Bearer ${newToken}`
        }
      });
    },
    
    getNewToken() {
      // 实际获取新令牌的逻辑
      return 'new-token-value';
    }
  }
};
</script>
```
:::

## 1.0版本请求体结构

在1.0版本中，AI小鲸组件的请求体结构发生了变化。下面是实际发送请求的数据结构：

```javascript
{
  data: {
    // 会话内容ID
    session_content_id: sessionContent?.id,
    // 会话唯一标识
    session_code: sessionCode,
    // 执行参数
    execute_kwargs: {
      stream: true,
    },
    // 其他数据
    ...data,
    // 用户通过requestOptions.data提供的数据
    ...currentRequestOptions.value.data,
  },
  headers: headers || currentRequestOptions.value?.headers,
}
```

**请求体合并示例:**

假设您通过`requestOptions.data`提供以下数据：

```json
{
  "preset": "QA",
  "userId": "user123"
}
```

最终发送的请求体将如下所示：

```json
{
  "session_content_id": "12345",
  "session_code": "session-uuid-12345",
  "execute_kwargs": {
    "stream": true
  },
  "preset": "QA",
  "userId": "user123"
}
```

请求头也会相应地被添加或覆盖。

::: warning 注意
如果 `requestOptions.data` 中定义的键与 AI 小鲸内部使用的请求体键（如 `session_content_id`, `session_code` 等）冲突，外部传入的值 **可能会覆盖** 内部值，请谨慎使用。
:::

## 常见使用场景

1. **添加身份验证信息**：在请求头中添加 JWT 令牌或 API Key
2. **切换不同的智能体**：通过动态更新 URL 来切换不同的智能体服务
3. **传递上下文信息**：在请求体中添加业务上下文，如用户ID、业务标识等
4. **处理特殊场景**：如添加跨域请求头、设置特定的内容类型等