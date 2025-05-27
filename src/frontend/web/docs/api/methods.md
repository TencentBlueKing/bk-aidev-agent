# Methods

可以通过组件实例调用的方法列表。

::: warning 版本变更提示
1.0版本优化了内部实现，但保持了API的基本一致性，方便用户平滑升级。
:::

## 方法列表

| 方法名                | 参数                                         | 返回值   | 描述                                                                                                                             |
| --------------------- | -------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `handleShow()`        | -                                            | `void`   | 主动显示 AI 小鲸窗口。                                                                                                           |
| `handleClose()`       | -                                            | `void`   | 关闭 AI 小鲸窗口。                                                                                                          |
| `handleStop()`        | -                                            | `void`   | 停止当前正在进行的 AI 内容生成（流式输出）。                                                                                      |
| `handleSendMessage(message)` | `message: string`                    | `void`   | 发送消息到 AI 小鲸，可用于编程式触发对话。 |
| `handleShortcutClick(shortcut)` | `shortcut: ShortCut`               | `void`   | 模拟点击快捷操作按钮，可用于编程式触发预设的操作。                                                                                 |
| `handleDelete(index)`  | `index: number`                             | `void`   | 删除指定索引位置的消息。                                                                                                      |
| `handleRegenerate(index)` | `index: number`                          | `void`   | 重新生成指定索引位置的消息。                                                                                                  |
| `handleResend(index, options)` | `index: number, options: {message: string, cite: string}`   | `void`   | 重发指定索引位置的消息，可修改消息内容和引用内容。                                                                          |
| `initSession()`       | -                                            | `Promise<void>`   | 初始化会话，获取开场白和预设问题。                                                                                       |
| `updateRequestOptions(options)` | `options: { url?: string; headers?: Record<string, string>; data?: any }` | `void` | 动态更新请求选项，可以修改API地址或请求参数。对于需要在运行时切换智能体或修改请求参数的场景非常有用。 |

::: danger 已废弃方法
以下方法在1.0版本中已被移除:
- `sendChat(options)`: 已被 `handleSendMessage(options)` 替代，请更新您的代码。
:::

## `ShortCut` 类型

```typescript
interface ShortCut {
  type: string;    // 操作类型
  label: string;   // 显示的标签
  cite?: boolean;  // 是否需要引用文本
  prompt?: string; // 发送到AI的提示词
  icon?: string;   // 图标名称
}
```

## 调用示例

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="show">显示</button>
  <button @click="stop">停止生成</button>
  <button @click="send">发送消息</button>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const aiBlueking = ref(null);
const apiUrl = '...';

const show = () => aiBlueking.value?.handleShow();
const stop = () => aiBlueking.value?.handleStop();
const send = () => {
  aiBlueking.value?.handleSendMessage('你好，这是一条测试消息');
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <AIBlueking ref="aiBlueking" :url="apiUrl" />
    <button @click="show">显示</button>
    <button @click="stop">停止生成</button>
    <button @click="send">发送消息</button>
  </div>
</template>

<script>
import { AIBlueking } from '@blueking/ai-blueking/vue2';

export default {
  components: { AIBlueking },
  data: () => ({ apiUrl: '...' }),
  methods: {
    show() { this.$refs.aiBlueking.handleShow(); },
    stop() { this.$refs.aiBlueking.handleStop(); },
    send() {
      this.$refs.aiBlueking.handleSendMessage('你好，这是一条测试消息');
    }
  }
};
</script>
```
:::

## 动态更新请求选项

使用`updateRequestOptions`方法可以在运行时动态修改请求选项，例如切换API地址或添加自定义请求头：

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <div class="controls">
    <button @click="switchAgent('agent1')">切换到智能体1</button>
    <button @click="switchAgent('agent2')">切换到智能体2</button>
    <button @click="addCustomHeader">添加自定义请求头</button>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const aiBlueking = ref(null);
const apiUrl = 'https://api.example.com/agent1';

// 切换不同的智能体API地址 （直接修改 AIblueking 的 url 参数也可以实现）
const switchAgent = (agentId) => {
  const newUrl = `https://api.example.com/${agentId}`;
  aiBlueking.value?.updateRequestOptions({
    url: newUrl,
  });
  
  // 可选：重新初始化会话以获取新智能体的配置
  aiBlueking.value?.initSession();
};

// 添加自定义请求头
const addCustomHeader = () => {
  aiBlueking.value?.updateRequestOptions({
    headers: {
      'X-Custom-Header': 'custom-value',
      'Authorization': 'Bearer your-token'
    }
  });
};
</script>
```

## 获取会话内容

组件实例暴露了`sessionContents`属性，可以获取当前会话的全部内容。

```vue
<template>
  <AIBlueking ref="aiBlueking" :url="apiUrl" />
  <button @click="getContents">获取会话内容</button>
</template>

<script setup>
import { ref } from 'vue';
import { AIBlueking } from '@blueking/ai-blueking';

const aiBlueking = ref(null);

const getContents = () => {
  const contents = aiBlueking.value?.sessionContents;
  console.log('当前会话内容:', contents);
};
</script>
```