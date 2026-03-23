# AIBlueking 浮窗模式

AIBlueking 是一个功能完整的 AI 聊天面板组件，内置悬浮球（Nimbus）、拖拽、划词选择等交互能力，适用于 SaaS 全局 AI 助手场景。

<script setup>
import { defineAsyncComponent, onMounted } from 'vue'
const apiUrl = import.meta.env.BK_API_URL_TMPL || ''
const AIBlueking = apiUrl ? defineAsyncComponent({
  loader: () => import('@blueking/ai-blueking').then(m => m.default),
}) : null
onMounted(() => {
  if (apiUrl) import('@blueking/ai-blueking/dist/vue3/style.css')
})
</script>

<ClientOnly>
  <component v-if="AIBlueking" :is="AIBlueking" :url="apiUrl" />
  <div v-else class="custom-block tip">
    <p>在线演示需要后端环境支持。请参考下方代码示例进行集成。</p>
  </div>
</ClientOnly>

## 效果说明

AIBlueking 挂载后在页面**右下角**显示 Nimbus 浮球图标，点击展开对话面板。

### 核心功能

- **浮球入口**：页面右下角的 Nimbus 浮球，点击即可展开/收起 AI 对话面板。
- **拖拽面板**：对话面板支持自由拖拽和调整大小，不影响宿主页面布局。
- **划词弹窗**：用户在页面中选中文本后，自动弹出快捷操作菜单（如"解释"、"翻译"等），将选中内容作为上下文发送给 AI。
- **内置会话管理**：面板顶部 Header 提供会话下拉列表、新建会话、切换会话、重命名等完整会话管理功能。

::: tip
AIBlueking 和 ChatBot 一样，都只需传入 `url` 即可开箱即用。快捷指令、提示词、欢迎语等均由 AIDev 后台配置，组件自动加载。
:::

## 最小配置示例

```vue
<template>
  <AIBlueking url="https://your-aidev-url.com/api/" />
</template>

<script setup lang="ts">
  import { AIBlueking } from "@blueking/ai-blueking"
  import "@blueking/ai-blueking/dist/vue3/style.css"
</script>
```

## 完整示例

```vue
<template>
  <div>
    <button @click="showPanel">打开面板</button>
    <button @click="hidePanel">关闭面板</button>

    <AIBlueking
      ref="aiBluekingRef"
      url="https://your-aidev-url.com/api/"
      :request-options="requestOptions"
      :enable-popup="true"
      :draggable="true"
      :default-height="700"
      :default-width="500"
      @send-message="handleSendMessage"
      @receive-end="handleReceiveEnd"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref } from "vue"
  import { AIBlueking } from "@blueking/ai-blueking"
  import type { AIBluekingExpose } from "@blueking/ai-blueking"

  const aiBluekingRef = ref<AIBluekingExpose>()

  const requestOptions = {
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  }

  const showPanel = () => aiBluekingRef.value?.show()
  const hidePanel = () => aiBluekingRef.value?.hide()

  const handleSendMessage = (message: string) => {
    console.log("用户发送:", message)
  }

  const handleReceiveEnd = (response: any) => {
    console.log("AI 回复完成:", response)
  }
</script>
```

## 关键说明

### 悬浮球 (Nimbus)

AIBlueking 内置了悬浮球组件，用户点击悬浮球即可打开/关闭面板。

- 设置 `enable-popup` 为 `true` 启用弹出模式，面板会以浮动窗口的形式展示。
- 悬浮球默认显示在页面右下角，可通过样式自定义位置。

```vue
<AIBlueking :enable-popup="true" />
```

### 拖拽

通过 `draggable` 属性启用面板拖拽功能，用户可自由移动面板位置。

```vue
<AIBlueking :draggable="true" :default-height="700" :default-width="500" />
```

### 尺寸与位置控制

| 属性             | 类型      | 默认值  | 说明               |
| ---------------- | --------- | ------- | ------------------ |
| `default-height` | `number`  | `600`   | 面板默认高度（px） |
| `default-width`  | `number`  | `400`   | 面板默认宽度（px） |
| `draggable`      | `boolean` | `false` | 是否允许拖拽移动   |
| `enable-popup`   | `boolean` | `false` | 是否启用弹出模式   |

### Expose 方法

| 方法                | 说明                     |
| ------------------- | ------------------------ |
| `show()`            | 打开面板                 |
| `hide()`            | 关闭面板                 |
| `toggle()`          | 切换面板显示/隐藏        |
| `sendMessage(text)` | 以编程方式发送消息       |
| `getChatHelper()`   | 获取底层 chatHelper 实例 |

### 与 ChatBot 的区别

| 特性     | ChatBot | AIBlueking |
| -------- | ------- | ---------- |
| 悬浮球   | ❌      | ✅         |
| 拖拽     | ❌      | ✅         |
| 划词选择 | ❌      | ✅         |
| 面板控制 | ❌      | ✅         |
| 独立嵌入 | ✅      | ✅         |
| 轻量级   | ✅      | ❌         |

> 详细的 Props 和 API 请参考 [AIBlueking 浮窗模式](/guide/integration-modes/aiblueking-floating) 指南。
