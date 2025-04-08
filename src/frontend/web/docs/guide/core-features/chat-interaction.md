# 基础对话交互

AI 小鲸提供了基础的对话窗口控制和交互功能。

AI 小鲸支持流式输出，AI 的回复会像打字一样逐字显示，提供更自然的交互体验。此功能由后端服务实现流式响应，前端组件负责展示。

## 显示与隐藏窗口

您可以通过调用组件实例的 `handleShow` 方法来主动显示 AI 小鲸窗口，用户也可以通过点击窗口的关闭按钮来隐藏它。

-   **`handleShow()`**: 显示 AI 小鲸窗口。
-   **`handleClose()`**: (内部方法，通常由用户点击关闭按钮触发) 隐藏 AI 小鲸窗口。

组件会分别在显示和隐藏时触发 `show` 和 `close` 事件。

:::code-group
```vue [Vue 3]
<template>
  <button @click="showAI">打开 AI</button>
  <AIBlueking ref="aiBlueking" :url="apiUrl" @show="onShow" @close="onClose" />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<InstanceType<typeof AIBlueking> | null>(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';

const showAI = () => {
  aiBlueking.value?.handleShow();
};

const onShow = () => {
  console.log('窗口已显示');
};

const onClose = () => {
  console.log('窗口已关闭');
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <button @click="showAI">打开 AI</button>
    <AIBlueking ref="aiBlueking" :url="apiUrl" @show="onShow" @close="onClose" />
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: { AIBlueking },
  data() {
    return { apiUrl: 'https://your-api-endpoint.com/assistant/' };
  },
  methods: {
    showAI() {
      this.$refs.aiBlueking.handleShow();
    },
    onShow() {
      console.log('窗口已显示');
    },
    onClose() {
      console.log('窗口已关闭');
    }
  }
};
</script>
```
:::

## 停止生成

当 AI 正在生成内容时，用户可以点击停止按钮，或者您可以主动调用 `handleStop` 方法来中断当前的流式输出。

-   **`handleStop()`**: 停止当前正在生成的内容。

组件在停止生成时会触发 `stop` 事件。

:::code-group
```vue [Vue 3]
<template>
  <button @click="stopAI" :disabled="!isGenerating">停止生成</button>
  <AIBlueking ref="aiBlueking" :url="apiUrl" @stop="onStop" />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<InstanceType<typeof AIBlueking> | null>(null);
const apiUrl = 'https://your-api-endpoint.com/assistant/';
const isGenerating = ref(false); // 需要根据实际情况判断是否正在生成

const stopAI = () => {
  aiBlueking.value?.handleStop();
};

const onStop = () => {
  console.log('内容生成已停止');
  isGenerating.value = false;
};

// 可以在开始请求时设置 isGenerating = true
</script>
```

```vue [Vue 2]
<template>
  <div>
    <button @click="stopAI" :disabled="!isGenerating">停止生成</button>
    <AIBlueking ref="aiBlueking" :url="apiUrl" @stop="onStop" />
  </div>
</template>

<script>
import AIBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: { AIBlueking },
  data() {
    return {
      apiUrl: 'https://your-api-endpoint.com/assistant/',
      isGenerating: false // 需要根据实际情况判断是否正在生成
    };
  },
  methods: {
    stopAI() {
      this.$refs.aiBlueking.handleStop();
    },
    onStop() {
      console.log('内容生成已停止');
      this.isGenerating = false;
    }
    // 可以在开始请求时设置 this.isGenerating = true
  }
};
</script>
```