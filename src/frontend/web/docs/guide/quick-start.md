# 快速上手

本章节将引导您完成 AI 小鲸组件的安装和基本使用。

## 安装

您可以使用 npm 或 yarn 来安装 AI 小鲸：

```bash
# 使用 npm
npm install @blueking/ai-blueking

# 使用 yarn
yarn add @blueking/ai-blueking
```

## 基本使用

根据您的项目框架选择对应的引入方式和代码示例。

::: tip 注意
必须提供有效的 `url` 属性，指向您的 AI 服务接口地址，否则组件无法正常工作。
:::

:::code-group
```vue [Vue 3]
<template>
  <div>
    <button @click="showAI">打开 AI 小鲸</button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      @show="handleShow"
      @close="handleClose"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue';
// 1. 引入组件
import AIBlueking from '@blueking/ai-blueking';
// 2. 引入样式
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiBlueking = ref<InstanceType<typeof AIBlueking> | null>(null);
// 3. 设置 AI 服务接口地址
const apiUrl = 'https://your-api-endpoint.com/assistant/';

const showAI = () => {
  // 调用组件实例的方法显示窗口
  aiBlueking.value?.handleShow();
};

const handleShow = () => {
  console.log('AI 小鲸已显示');
};

const handleClose = () => {
  console.log('AI 小鲸已关闭');
};
</script>
```

```vue [Vue 2]
<template>
  <div>
    <button @click="showAI">打开 AI 小鲸</button>

    <AIBlueking
      ref="aiBlueking"
      :url="apiUrl"
      @show="handleShow"
      @close="handleClose"
    />
  </div>
</template>

<script>
// 1. 引入 Vue 2 版本组件
import AIBlueking from '@blueking/ai-blueking/vue2';
// 2. 引入 Vue 2 版本样式
import '@blueking/ai-blueking/dist/vue2/style.css';

export default {
  components: {
    AIBlueking
  },
  data() {
    return {
      // 3. 设置 AI 服务接口地址
      apiUrl: 'https://your-api-endpoint.com/assistant/'
    };
  },
  methods: {
    showAI() {
      // 调用组件实例的方法显示窗口
      this.$refs.aiBlueking.handleShow();
    },
    handleShow() {
      console.log('AI 小鲸已显示');
    },
    handleClose() {
      console.log('AI 小鲸已关闭');
    }
  }
};
</script>
```

现在，您应该可以在页面上看到一个按钮，点击后会显示 AI 小鲸的对话窗口。
