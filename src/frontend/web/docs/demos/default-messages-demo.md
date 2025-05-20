<script setup>
import { onMounted, defineAsyncComponent, ref } from 'vue';

const prefix = (import.meta.env.BK_API_URL_TMPL || '')
  .replace('{api_name}', import.meta.env.BK_API_GATEWAY_NAME || '')
  .replace('http', 'https');

const apiUrl = `${prefix}/prod/bk_plugin/plugin_api/assistant/`;

const AIBlueking = defineAsyncComponent({
  loader: () => import('@blueking/ai-blueking'),
});

// 预设对话内容
const defaultMessages = ref([
  { role: 'user', content: '请介绍蓝鲸平台' },
  { role: 'ai', content: '蓝鲸（BlueKing）是腾讯推出的一站式技术运营平台，为企业提供丰富的运维、开发和运营工具，能够有效降低企业管理IT成本。\n\n主要包括以下核心产品：\n- 配置平台\n- 作业平台\n- 监控告警\n- 流程服务\n- 容器服务\n\n这些产品形成了完整的IT运营体系，帮助企业实现高效的运维管理。' },
  { 
    role: 'user', 
    content: '请优化这段 SQL 查询', 
    cite: 'SELECT * FROM users u JOIN orders o ON u.id = o.user_id WHERE u.created_at > "2025-01-01" AND u.status = "active" ORDER BY u.created_at DESC'
  }, 
  {
    role: 'ai',
    content: "我来帮你优化这段查询...."
  }
]);

onMounted(() => {
  // Use dynamic import() which runs only on the client here
  import('@blueking/ai-blueking/dist/vue3/style.css');
});
</script>

# 预设对话内容示例

:::tip
本页面展示了如何使用 `defaultMessages` 属性预设对话内容。请点击右下角按钮打开小鲸，就能看到预设的对话历史和带有引用内容的消息。
:::

:::warning
注意：这是一项实验性功能，不建议在生产环境中依赖。未来我们计划在 Agent 配置中正式支持预设对话和角色定义，届时此特性可能会被替代。
:::

这个示例展示了如何使用 `defaultMessages` 属性来预设 AI 小鲸的对话内容，包括基本对话历史和带引用内容的消息。

<ClientOnly>
<AIBlueking :url="apiUrl" :default-messages="defaultMessages" />
</ClientOnly>

## 关键代码讲解

### 1. 引入组件和样式

:::code-group
```js [Vue3]
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';
```

```js [Vue2]
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';
```
:::

### 2. 设置预设对话内容

```js
// 预设对话内容
const defaultMessages = ref([
  // 简单对话消息
  { role: 'user', content: '请介绍蓝鲸平台' },
  { role: 'ai', content: '蓝鲸（BlueKing）是腾讯推出的一站式技术运营平台...' },
  
  // 带引用内容的消息
  { 
    role: 'user', 
    content: '请优化这段 SQL 查询', 
    cite: 'SELECT * FROM users u JOIN orders o ON u.id = o.user_id WHERE u.created_at > "2025-01-01" AND u.status = "active" ORDER BY u.created_at DESC'
  },
  {
    role: 'ai',
    content: "我来帮你优化这段查询...."
  }
]);
```

### 3. 在组件中使用预设对话内容

```vue
<AIBlueking
  :url="apiUrl"
  :default-messages="defaultMessages"
/>
```

## 消息格式说明

`defaultMessages` 数组中的每个对象需要符合以下格式：

```typescript
interface Message {
  role: 'user' | 'ai';  // 消息发送者角色
  content: string;            // 消息内容
  cite?: string;              // (可选) 框选引用内容
}
```

## 注意事项

- `role` 必须为 `'user'` 或 `'ai'`，分别表示用户消息和AI助手消息
- 预设内容必须是一问一答的形式
- `cite` 字段为可选，用于预设框选引用的内容，在消息中将以引用形式展示 