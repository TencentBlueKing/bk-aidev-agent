# 使用文档

## 基本使用

### Vue 3

```vue
<template>
  <div>
    <button @click="showAI">打开 AI 小鲸</button>
    
    <AIBlueking 
      ref="aiBlueking"
      :url="apiUrl"
      title="我的智能助手"
      helloText="你好，我是你的AI助手"
      @show="handleShow"
      @close="handleClose"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';

const showAI = () => {
  aiBlueking.value.show();
  console.log('AI 小鲸已显示');
};

const handleShow = () => {
  console.log('AI 小鲸已显示');
};

const handleClose = () => {
  console.log('AI 小鲸已关闭');
};
</script>
```

## 属性 (Props)

| 属性名 | 类型 | 默认值 | 描述 |
|--------|------|--------|------|
| url | String | '' | AI 服务接口地址，必须设置 |
| title | String | 'AI 小鲸' | 在头部显示的标题文本 |
| helloText | String | '你好，我是小鲸' | 初始欢迎页面显示的问候语 |
| enablePopup | Boolean | true | 是否启用选中文本后的弹出操作窗口 |
| shortcuts | Array | [...] | 快捷操作列表 |
| prompts | Array | [] | 预设提示词列表 |
| requestOptions | Object | {} | 自定义请求选项 |
| defaultMinimize | Boolean | false | 初始是否处于最小化状态 |
| sessionContents | Array | [] | 当前会话内容 |

### shortcuts 属性说明

快捷操作按钮配置，默认包含三个内置操作：

```js
const defaultShortcuts = [
  {
    name: '总结',
    prompt: '请总结以下内容的要点：\n{selection}'
  },
  {
    name: '解释',
    prompt: '请解释以下内容：\n{selection}'
  },
  {
    name: '优化',
    prompt: '请优化以下内容的表达，使其更清晰、简洁：\n{selection}'
  }
];
```

## 事件 (Events)

| 事件名 | 参数 | 描述 |
|--------|------|------|
| show | - | AI 窗口显示时触发 |
| close | - | AI 窗口关闭时触发 |
| message | message: Object | 接收到消息时触发 |
| send | message: String | 发送消息时触发 |
| minimize | - | 窗口最小化时触发 |
| maximize | - | 窗口最大化时触发 |
| error | error: Error | 发生错误时触发 |

## 方法 (Methods)

| 方法名 | 参数 | 描述 |
|--------|------|------|
| show | - | 显示 AI 对话窗口 |
| hide | - | 隐藏 AI 对话窗口 |
| toggle | - | 切换 AI 对话窗口显示状态 |
| minimize | - | 最小化 AI 对话窗口 |
| maximize | - | 最大化 AI 对话窗口 |
| clear | - | 清空对话记录 |
| sendMessage | message: String | 发送消息 |
| resetPosition | - | 重置窗口位置 |

## 高级用法

### 自定义提示词

::: demo 提示词示例
```vue
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
  '我给一段文字，概括文字的主题和主要观点',
  '假设你是一名关系型数据库专家...',
  '你是一名经验丰富的前端开发工程师...'
];
</script>
```
:::

### 自定义请求选项

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :requestOptions="requestOptions"
  />
</template>

<script setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const apiUrl = 'https://your-api-endpoint.com/assistant/';
const requestOptions = {
  headers: {
    'Authorization': 'Bearer your-token',
    'X-Custom-Header': 'custom-value'
  },
  timeout: 30000
};
</script>
```

### 预加载会话内容

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :sessionContents="sessionContents"
  />
</template>

<script setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';

const apiUrl = 'https://your-api-endpoint.com/assistant/';
const sessionContents = [
  {
    role: 'user',
    content: '你好，请介绍一下你自己'
  },
  {
    role: 'assistant',
    content: '你好！我是 AI 小鲸，一个智能对话助手。我可以帮助你回答问题、提供信息，以及完成各种对话任务。有什么我可以帮助你的吗？'
  }
];
</script>
```

## 框架差异注意事项

### Vue 3 项目

- 使用组合式 API (Composition API) 开发
- 导入的样式路径为 `@blueking/ai-blueking/dist/vue3/style.css`

### Vue 2 项目

- 使用选项式 API (Options API) 开发
- 导入的样式路径为 `@blueking/ai-blueking/dist/vue2/style.css`
- 需要在 components 选项中注册组件 