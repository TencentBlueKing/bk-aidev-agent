---
aside: false
---

# AIBlueking 浮窗

AIBlueking 自带悬浮球、可拖拽面板、会话管理与划词弹窗，适合给整个 SaaS 加一个全局 AI 助手。只需传入 `url` 即可开箱使用，快捷指令、开场白等由 AIDev 后台配置自动加载：

```vue
<template>
  <AIBlueking ref="aiBluekingRef" url="https://your-aidev-url.com/api/" />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import AIBlueking, { type AIBluekingExpose } from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  const aiBluekingRef = ref<AIBluekingExpose>();
</script>
```

<ClientOnly>
  <DemoEnvBar />
</ClientOnly>

## 配置台

改动下面的开关后，右侧小鲸会**按新配置重新挂载**（模拟你在代码里改了 props），代码页签同步生成等价的模板，变化的行会高亮。

<ClientOnly>
  <RecipeFloatingConsole />
</ClientOnly>

## 面板位置与尺寸

`default-left` / `default-top` / `default-width` / `default-height` 决定面板的初始位置与尺寸，**只在挂载时生效**，所以每次切换布局，右侧小鲸都会按新的 props 重新挂载。代码页签中的函数按当前视口算出这组 props，直接 `v-bind` 到 `<AIBlueking>` 即可。

<ClientOnly>
  <RecipePanelLayout />
</ClientOnly>

## 与 ChatBot 的区别

| 能力 | ChatBot | AIBlueking |
| --- | --- | --- |
| 悬浮球、拖拽、面板控制 | — | 内置 |
| 会话管理 Header | 业务自建 | 内置 |
| 划词弹窗 | — | 内置（`enable-popup`） |
| 嵌入页面任意位置 | 是 | 否（浮在页面之上） |

## 相关文档

- [AIBlueking 浮窗模式](/guide/integration-modes/aiblueking-floating)：完整 Props、Expose 与内部结构
- [编程式控制](/demos/programmatic-control)：从业务页打开小鲸、带上下文提问、触发快捷指令
- [ChatBot 页面嵌入](/demos/basic-usage)：把聊天区嵌进业务页面
