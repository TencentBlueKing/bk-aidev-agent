# 快速上手

本章节将引导您完成 AI 小鲸组件的安装和基本使用。
::: tip 版本兼容性说明
- 小鲸组件 1.x：需要后台 aidev_agent 版本 ≥ 1.0.0b1
- 小鲸组件 0.x：需使用对应的旧版 aidev_agent

请确保组件与后台版本匹配，否则将无法正常工作。
:::

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

## 多会话管理 <Badge type="tip" text="v1.1.0" />

从 v1.1.0 开始，AI 小鲸支持多会话管理功能，让您可以同时管理多个独立的聊天会话：

### 主要功能

- **🆕 创建新会话**：点击头部的新增聊天图标快速创建新对话
- **📊 历史会话**：点击历史图标查看和管理所有会话
- **🔄 会话切换**：在不同会话间无缝切换，保持独立的对话上下文
- **✏️ 会话管理**：重命名、删除会话，支持搜索功能

### 快速体验

1. 启动 AI 小鲸后，您会看到头部有两个新图标
2. 点击 **➕** 图标创建新的聊天会话
3. 点击 **📋** 图标打开历史会话面板
4. 在历史面板中可以切换、重命名或删除会话

想了解更多多会话功能，请参阅 [会话管理指南](/guide/advanced-usage/session-access)。

## 下一步

恭喜！您已经成功集成了 AI 小鲸组件。接下来您可以：

- 了解更多 [核心功能](/guide/core-features/chat-interaction)
- 查看 [API 文档](/api/props) 了解所有可用属性
- 探索 [高级用法](/guide/advanced-usage/) 实现更复杂的功能
