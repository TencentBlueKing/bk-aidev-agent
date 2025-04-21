# 自定义请求

在某些场景下，您可能需要在发送给 AI 后端服务的请求中添加额外的参数，例如用于身份验证的 Token、用于区分业务场景的标识等。AI 小鲸提供了 `requestOptions` prop 来满足这一需求。

## 配置 `requestOptions`

`requestOptions` 是一个对象，可以包含 `headers` 和 `data` 两个属性：

-   `headers` (Object): 一个对象，其键值对将被合并到最终请求的 **请求头 (Headers)** 中。
-   `data` (Object): 一个对象，其键值对将被合并到最终请求的 **请求体 (Body)** 中。

**示例：**

假设您需要在请求头中添加 `Authorization` 字段，并在请求体中添加 `preset` 字段。

:::code-group
```vue [Vue 3]

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :request-options="customOptions"
  />
</template>

<script lang="ts" setup>
import { ref, reactive } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

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
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

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

**请求体合并示例:**

假设原始请求体如下：

```json
{
  "inputs": {
    "chat_history": [],
    "input": "用户的提问内容"
  },
}
```

使用上面示例中的 `requestOptions.data` 后，实际发送的请求体将变为：

```diff
 {
   "inputs": {
      "chat_history": [],
      "input": "用户的提问内容",
+     "preset": "QA",
+     "userId": "user123"
   },
 }
```

请求头也会相应地被添加或覆盖。

::: warning 注意
如果 `requestOptions.data` 中定义的键与 AI 小鲸内部使用的请求体键（如 `input`, `chat_history` 等）冲突，外部传入的值 **可能会覆盖** 内部值，请谨慎使用。
:::