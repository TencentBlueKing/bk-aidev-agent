
<script setup>
import { ref, onMounted, defineAsyncComponent } from 'vue';

const AIBlueking = defineAsyncComponent({
  loader: () => import('@blueking/ai-blueking'),
});

onMounted(() => {
  // Use dynamic import() which runs only on the client here
  import('@blueking/ai-blueking/dist/vue3/style.css');
});

const prefix = (import.meta.env.BK_API_URL_TMPL || '')
  .replace('{api_name}', import.meta.env.BK_API_GATEWAY_NAME || '')
  .replace('http', 'https');
const apiUrl = `${prefix}/prod/bk_plugin/plugin_api/assistant/`;

const customPrompts = [
  '我给一段文字，概括文字的主题和主要观点',
  '假设你是一名关系型数据库专家，帮我分析以下SQL查询的性能问题',
  '你是一名经验丰富的前端开发工程师，请帮我优化下面的代码',
];
</script>

# 提示词示例

:::tip
本页面可以直接体验小鲸的聊天功能，请点击右下角按钮打开小鲸，并输入"/"查看提示词功能
:::

AI 小鲸支持预设提示词功能，让用户可以快速选择常用的提示模板。

<ClientOnly>
<AIBlueking 
  ref='aiBlueking'
  :url='apiUrl'
  :prompts='customPrompts'
/>
</ClientOnly>

## 如何使用提示词

提示词是预设的对话模板，可以帮助用户快速开始特定类型的对话。用户可以在对话框中选择这些预设模板，而不必每次手动输入相似的提示。

### 配置方法

```js
// 设置自定义提示词
const customPrompts = [
  '我给一段文字，概括文字的主题和主要观点',
  '假设你是一名关系型数据库专家，帮我分析以下SQL查询的性能问题',
  '你是一名经验丰富的前端开发工程师，请帮我优化下面的代码',
];

// 在组件中使用
<AIBlueking :prompts="customPrompts" />
```

### 提示词最佳实践

1. **保持简洁**：提示词应简明扼要，便于用户理解
2. **针对性强**：为特定场景或任务设计专用提示词
3. **覆盖常见需求**：包含最常用的几种对话类型
4. **格式一致**：使用一致的表达方式，便于用户记忆
5. **数量适中**：提供足够的选择，但不要过多导致用户选择困难

### 高级用法：动态提示词

你可以根据不同的业务场景动态加载不同的提示词集合：

```js
// 根据用户角色加载不同提示词
const loadPromptsByRole = (role) => {
  switch(role) {
    case 'developer':
      return [
        '请帮我审查这段代码',
        '解释这段代码的执行流程',
        '如何优化这个函数的性能'
      ];
    case 'designer':
      return [
        '分析这个界面设计的优缺点',
        '如何提升这个页面的用户体验',
        '给这个设计提供配色建议'
      ];
    default:
      return defaultPrompts;
  }
};

const userRole = 'developer';
const prompts = loadPromptsByRole(userRole);