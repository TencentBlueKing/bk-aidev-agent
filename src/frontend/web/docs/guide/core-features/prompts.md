# 预设提示词 (Prompts)

通过 `prompts` prop，您可以为用户提供一组预设的提问模板或角色扮演指令。这些提示词会显示在 AI 对话窗口的输入框上方（通常在快捷操作下方），用户点击后可以直接将提示词内容发送给 AI，方便快速发起特定类型的对话。

`prompts` 是一个字符串数组。

**格式示例:**

```javascript
const customPrompts = [
  '请概括这段内容的主要观点',
  '请帮我分析这段文字中的问题',
  '请用简单的语言解释这个概念',
  '我给一段文字，概括文字的主题和主要观点，找出支持主题的关键事实、论据或观点，使用中文回答。',
  '假设你是一名关系型数据库专家，后续的对话我会直接描述我想要的查询效果，请告诉我如何写对应的SQL查询，并解释它，如果有多个版本的SQL，以MySQL数据库为主。',
  '你是一名经验丰富的前端开发工程师，请帮我解决以下问题...'
];
```

**在组件中使用:**

:::code-group
```vue [Vue 3]
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :prompts="customPrompts"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';

const customPrompts = [
  // ... 如上所示 ...
];
</script>
```

```vue [Vue 2]
<template>
  <AIBlueking
    ref="aiBlueking"
    :url="apiUrl"
    :prompts="customPrompts"
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
      customPrompts: [
        // ... 如上所示 ...
      ]
    };
  }
};
</script>
```
:::

用户点击这些预设提示词时，其文本内容会直接作为消息发送给 AI。
