# 快速开始

本文将引导你在几分钟内完成 AI 小鲸的安装与基础集成。

## 安装

```bash
# 完整安装
npm install @blueking/ai-blueking

# 或仅安装需要的包
npm install @blueking/chat-x @blueking/chat-helper
```

::: tip 提示
`@blueking/ai-blueking` 已包含 `@blueking/chat-x` 和 `@blueking/chat-helper` 的依赖，完整安装后无需重复安装子包。
:::

## 最小示例

::: tip URL 来自 AIDev 平台
组件初始化时会自动通过 `agent/info` 接口加载 Agent 配置（快捷指令、提示词、欢迎语等），**无需手动传入**。你只需要提供 AIDev 平台发布后的 URL。
:::

### ChatBot 页面嵌入

以下是最简单的集成方式——只需一个 `url` 即可拥有完整的聊天能力。

::: code-group

```vue [Vue 3]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      url="https://your-aidev-url.com/api/"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
import { ChatBot } from '@blueking/ai-blueking';

const handleError = (error: Error) => console.error('错误:', error);
</script>
```

```vue [Vue 2]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      url="https://your-aidev-url.com/api/"
      @error="handleError"
    />
  </div>
</template>

<script>
import { ChatBot } from '@blueking/ai-blueking';

export default {
  components: { ChatBot },
  methods: {
    handleError(error) {
      console.error('错误:', error);
    },
  },
};
</script>
```

:::

### AIBlueking 浮窗模式

如果你需要一个全局 AI 助手浮窗，使用 `AIBlueking` 同样只需传入 `url`：

```vue
<template>
  <AIBlueking url="https://your-aidev-url.com/api/" />
</template>

<script setup lang="ts">
import { AIBlueking } from '@blueking/ai-blueking';
</script>
```

挂载后页面右下角会出现 Nimbus 浮球图标，点击即可展开对话面板。

::: warning Vue 2 用户注意
Vue 2 项目需要额外安装 `@vue/composition-api` 以获得组合式 API 支持：

```bash
npm install @vue/composition-api
```

并在入口文件中注册：

```js
import Vue from 'vue';
import VueCompositionAPI from '@vue/composition-api';

Vue.use(VueCompositionAPI);
```
:::

## 样式引入

使用 AI 小鲸组件前，请确保引入对应的样式文件：

```ts
// Vue 3 项目：引入 ai-blueking 样式（已包含 chat-x 样式）
import '@blueking/ai-blueking/dist/vue3/style.css';

// Vue 2 项目：引入 ai-blueking 样式
import '@blueking/ai-blueking/dist/vue2/style.css';

// 如果仅使用 chat-x（Vue 3）
import '@blueking/chat-x/dist/vue3/style.css';
```

## 认证配置

如果你的后端 API 需要认证，通过 `requestOptions` 配置请求头：

```vue
<template>
  <ChatBot
    url="https://your-aidev-url.com/api/"
    :request-options="requestOptions"
  />
</template>

<script setup lang="ts">
import { ChatBot } from '@blueking/ai-blueking';

const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
};
</script>
```

> `headers` / `data` 支持函数、`ref`、`computed`（v2.1.4-beta.9+），确保每次请求携带最新 token 与业务字段。详见 [自定义请求](/guide/advanced-usage/custom-requests)。

## 下一步

你已经完成了最基础的集成！接下来可以深入了解更多能力：

- [**AIBlueking 浮窗模式**](/guide/integration-modes/aiblueking-floating) — 全局 AI 助手，浮球入口 + 拖拽面板 + 划词弹窗
- [**ChatBot 页面嵌入模式**](/guide/integration-modes/chatbot-embedded) — 嵌入式聊天，适合页面主内容区
- [**Standalone 非 Vue 宿主**](/guide/integration-modes/standalone-bundle) — React / 纯 HTML 等无 Vue 场景（v2.1.4-beta.8+）
- [**API 文档**](/api/overview) — 查阅完整的组件 Props、Events、Slots 参考
- [**示例**](/demos/full-panel) — 浏览更多交互示例与最佳实践
