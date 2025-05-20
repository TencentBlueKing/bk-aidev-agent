# 预设对话内容

:::warning
注意：这是一项实验性功能，不建议在生产环境中依赖。未来我们计划在 Agent 配置中正式支持预设对话和角色定义，届时此特性可能会被替代。
:::

AI 小鲸组件支持通过 `defaultMessages` 属性预设初始对话内容，该功能可用于以下场景：

- 初始化对话：在组件首次加载时预先展示一些内容，而不是空白状态
- 恢复会话：从其他地方（如本地存储、服务器）读取历史会话并恢复
- 示例对话：为用户展示示范性的对话，引导用户使用
- 上下文保留：在应用中保留上下文，避免用户重复输入

## 基本用法

要设置预设对话内容，只需向组件传递 `defaultMessages` 属性：

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking
    :url="apiUrl"
    :default-messages="initialMessages"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const apiUrl = 'https://your-api-url.com/chat';
const initialMessages = ref([
  { role: 'user', content: '请介绍一下蓝鲸产品' },
  { role: 'ai', content: '蓝鲸（BlueKing）是腾讯推出的一站式技术运营平台，为企业提供丰富的运维、开发和运营工具，能够有效降低企业管理IT成本。...' },
  { 
    role: 'user', 
    content: '请帮我优化下面的SQL查询', 
    cite: 'SELECT * FROM users WHERE created_at > "2025-01-01" AND status = "active" ORDER BY created_at DESC' 
  }
]);
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking
    :url="apiUrl"
    :default-messages="initialMessages"
  />
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';

export default {
  data() {
    return {
      apiUrl: 'https://your-api-url.com/chat',
      initialMessages: [
        { role: 'user', content: '请介绍一下蓝鲸产品' },
        { role: 'ai', content: '蓝鲸（BlueKing）是腾讯推出的一站式技术运营平台，为企业提供丰富的运维、开发和运营工具，能够有效降低企业管理IT成本。...' },
        { 
          role: 'user', 
          content: '请帮我优化下面的SQL查询', 
          cite: 'SELECT * FROM users WHERE created_at > "2025-01-01" AND status = "active" ORDER BY created_at DESC' 
        }
      ]
    };
  },
}
</script>
```
:::

## 消息格式

`defaultMessages` 数组中的每个对象需要符合以下格式：

```typescript
interface Message {
  role: 'user' | 'ai';  // 消息发送者角色
  content: string;            // 消息内容
  cite?: string;              // (可选) 框选引用内容，用于预设引用的文本
}
```

注意事项：
- `role` 必须为 `'user'` 或 `'ai'`，分别表示用户消息和AI助手消息
- 预设内容必须是一问一答的形式
- `cite` 字段为可选，用于预设框选引用的内容，在消息中将以引用形式展示

### 带引用内容的示例

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :default-messages="messagesWithCite"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const apiUrl = 'https://your-api-url.com/chat';
const messagesWithCite = ref([
  { 
    role: 'user', 
    content: '请解释这段代码', 
    cite: 'function calculateTotal(items) {\n  return items.reduce((sum, item) => sum + item.price, 0);\n}'
  },
  { 
    role: 'ai', 
    content: '这是一个JavaScript函数，用于计算商品的总价。它使用reduce方法遍历items数组，将每个item的price加到累加器sum中，初始值为0。' 
  }
]);
</script>
```

## 动态更新预设消息

您可以通过响应式方式更新 `defaultMessages` 属性，例如从外部数据源加载会话历史：

```vue
<template>
  <div>
    <button @click="loadSession">加载上次会话</button>
    <AIBlueking
      :url="apiUrl"
      :default-messages="sessionMessages"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const apiUrl = 'https://your-api-url.com/chat';
const sessionMessages = ref([]);

const loadSession = async () => {
  // 从服务器或本地存储加载会话历史
  const savedSession = await fetchSessionFromServer();
  // 更新预设消息
  sessionMessages.value = savedSession;
};
</script>
```

## 与消息事件结合使用

您可以结合 `defaultMessages` 与 [消息事件](/api/events) 一起使用，实现更丰富的对话交互：

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :default-messages="sessionMessages"
    @send-message="handleSendMessage"
    @receive-end="handleReceiveEnd"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const apiUrl = 'https://your-api-url.com/chat';
const aiBlueking = ref();
const sessionMessages = ref([
  { role: 'user', content: '你好' },
  { role: 'ai', content: '您好！有什么可以帮助您的吗？' }
]);

// 用户发送消息时保存状态
const handleSendMessage = (message) => {
  // 从组件实例获取最新的消息，包含可能的引用内容
  const latestMessage = aiBlueking.value?.sessionContents?.find(
    msg => msg.role === 'user' && msg.content === message
  );
  
  saveSessionToLocalStorage([
    ...sessionMessages.value,
    { 
      role: 'user', 
      content: message,
      ...(latestMessage?.cite ? { cite: latestMessage.cite } : {})
    }
  ]);
};

// AI 回复完成时保存状态
const handleReceiveEnd = () => {
  // 此时使用 ref 获取组件实例的 sessionContents 获取最新消息
  if (aiBlueking.value && aiBlueking.value.sessionContents) {
    const lastMessage = aiBlueking.value.sessionContents[aiBlueking.value.sessionContents.length - 1];
    const updatedMessages = [
      ...sessionMessages.value,
      { role: 'ai', content: lastMessage.content }
    ];
    saveSessionToLocalStorage(updatedMessages);
    sessionMessages.value = updatedMessages;
  }
};

// 保存会话到本地存储
const saveSessionToLocalStorage = (messages) => {
  localStorage.setItem('ai-session', JSON.stringify(messages));
};
</script>
```

## 与 sessionContents 结合使用

如果您需要在外部访问当前会话内容，可以结合 `defaultMessages` 与 [`sessionContents`](/api/props#sessioncontents) 一起使用：

```vue
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :default-messages="initialMessages"
  />
  <button @click="saveCurrentSession">保存当前会话</button>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const aiBlueking = ref();
const apiUrl = 'https://your-api-url.com/chat';
const initialMessages = ref([
  { role: 'user', content: '你好' },
  { role: 'ai', content: '您好！有什么可以帮助您的吗？' }
]);

const saveCurrentSession = () => {
  // 获取当前会话内容
  const currentMessages = aiBlueking.value.sessionContents;
  // 保存到服务器或本地存储
  localStorage.setItem('saved-session', JSON.stringify(currentMessages));
};
</script>
```

通过这些方法，您可以灵活地管理AI对话会话的状态，并实现更丰富的用户体验。 