# UI 定制

AI 小鲸 v2.0 提供了丰富的 UI 定制选项，涵盖样式、布局、文本、显示控制和渲染目标等方面。

## extCls 额外 CSS 类名

通过 `extCls` prop 为组件根元素添加自定义 CSS 类名，方便进行样式覆盖：

```vue
<template>
  <AIBlueking :url="apiUrl" ext-cls="my-ai-theme" />
</template>

<style>
.my-ai-theme {
  /* 自定义样式 */
  --ai-primary-color: #3a84ff;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}
</style>
```

`ChatBot` 同样支持 `extCls`：

```vue
<template>
  <ChatBot url="/api/ai/assistant/" ext-cls="embedded-chat" />
</template>
```

## CSS 变量

AI 小鲸使用 CSS 变量进行主题定制，您可以通过覆盖这些变量来统一修改组件的视觉风格：

```css
/* 在全局样式或 extCls 对应的选择器中覆盖 */
.my-ai-theme {
  /* 主色调 */
  --ai-primary-color: #3a84ff;

  /* 背景色 */
  --ai-bg-color: #ffffff;
  --ai-header-bg-color: #f5f7fa;

  /* 文本颜色 */
  --ai-text-color: #313238;
  --ai-text-secondary-color: #979ba5;

  /* 边框 */
  --ai-border-color: #dcdee5;
  --ai-border-radius: 8px;

  /* 消息气泡 */
  --ai-message-user-bg: #e1ecff;
  --ai-message-assistant-bg: #f0f1f5;
}
```

## 布局控制

### 高度和最大宽度

`ChatBot` 和 `AIBlueking` 均支持 `height` 和 `maxWidth` 控制：

```vue
<template>
  <!-- ChatBot 嵌入到页面，指定高度 -->
  <ChatBot url="/api/ai/assistant/" :height="500" max-width="800px" />

  <!-- AIBlueking 浮窗，通过默认尺寸控制 -->
  <AIBlueking url="/api/ai/assistant/" :default-width="520" :default-height="680" />
</template>
```

### AIBlueking 窗口定位

`AIBlueking` 组件支持自定义初始位置和尺寸：

| Prop | 类型 | 说明 |
|------|------|------|
| `defaultWidth` | `number` | 初始宽度（像素） |
| `defaultHeight` | `number` | 初始高度（像素） |
| `defaultLeft` | `number` | 初始左侧位置（像素） |
| `defaultTop` | `number` | 初始顶部位置（像素） |
| `draggable` | `boolean` | 是否可拖拽，默认 `true` |
| `maxWidth` | `number \| string` | 最大宽度 |

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :draggable="true"
    :default-width="520"
    :default-height="600"
    :default-top="50"
    :default-left="20"
  />
</template>
```

### 编程式更新位置和尺寸

```typescript
// 更新位置
aiBluekingRef.value.updatePosition(100, 200);

// 更新尺寸
aiBluekingRef.value.updateSize(600, 800);

// 同时更新位置和尺寸
aiBluekingRef.value.updatePositionAndSize(100, 200, 600, 800);
```

## 文本定制

### helloText 欢迎语

设置对话窗口的初始欢迎语：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    hello-text="你好！我是你的企业智能助手，有什么可以帮助你的？"
  />
</template>
```

> **说明**：后端 Agent 配置中的 `openingRemark`（欢迎语）会覆盖 `helloText`。当 `getAgentInfo()` 返回了 `conversationSettings.openingRemark`，以后端配置为准。

### `#welcome` 插槽自定义欢迎区

`ChatBot` / `AIBlueking` 透传 `ChatContainer` 的 `#welcome` 插槽，可完全替换默认欢迎 UI（图标、标题、开场白）。Scope：`{ openingRemark, welcomeTitle }`。

```vue
<template>
  <ChatBot url="/api/ai">
    <template #welcome="{ welcomeTitle, openingRemark }">
      <img src="/brand.svg" alt="" />
      <h2>{{ welcomeTitle }}</h2>
      <p>{{ openingRemark }}</p>
    </template>
  </ChatBot>
</template>
```

未提供 `#welcome` 时行为不变，仍使用内置欢迎内容。

### 消息工具栏扩展（`messageTools` / `updateTools`）

在内置工具基础上增量定制 AI 消息工具栏，合并规则与 chat-x 一致：同 `id` 覆盖、新 `id` 追加、`{ id, hidden: true }` 隐藏。

```vue
<template>
  <ChatBot
    url="/api/ai"
    :message-tools="customMessageTools"
    :update-tools="customUpdateTools"
    @agent-action="onAgentAction"
    @confirm-share="onConfirmShare"
  />
</template>

<script setup lang="ts">
import { DownloadIcon, type IToolBtn, type Message } from '@blueking/chat-x';

const customMessageTools: IToolBtn[] = [
  { id: 'save', name: '保存', description: '保存该回答', icon: DownloadIcon, triggerSelection: true },
  { id: 'share', hidden: true },
];
const customUpdateTools: IToolBtn[] = [
  { id: 'collect', name: '收藏', description: '收藏到我的空间' },
];

const onAgentAction = (tool: IToolBtn, messages: Message[]) => {
  if (tool.id === 'collect') {
    // 处理收藏
  }
};

const onConfirmShare = (messages: Message[], source?: IToolBtn) => {
  if (source?.id === 'save') {
    // 批量保存选中消息；不会触发内置分享
  }
};
</script>
```

- `triggerSelection: true`：点击后进入多选，确认走 `confirm-share`（带 `source`）
- 其它自定义按钮：走 `agent-action`
- 仅 `!source || source.id === 'share'` 时执行内置分享业务

### placeholder 输入框占位符

自定义输入框的占位提示文本：

```vue
<template>
  <ChatBot
    url="/api/ai/assistant/"
    placeholder="输入您的问题，按 Enter 发送..."
  />
</template>
```

### title 组件标题

设置 `AIBlueking` Header 中显示的标题文本：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    title="企业智能助手"
  />
</template>
```

> **说明**：后端 Agent 配置中的 `agentName` 会覆盖 `title`。

## 显示控制

### hideHeader

隐藏 `AIBlueking` 的头部栏：

```vue
<template>
  <AIBlueking :url="apiUrl" :hide-header="true" />
</template>
```

### hideNimbus

隐藏悬浮球（Nimbus）触发器：

```vue
<template>
  <!-- 隐藏悬浮球，通过自定义按钮控制显示 -->
  <AIBlueking ref="aiRef" :url="apiUrl" :hide-nimbus="true" />
  <button @click="aiRef?.handleShow()">打开 AI 助手</button>
</template>
```

### hideDefaultTrigger

隐藏默认的触发器（与 `hideNimbus` 配合使用）：

```vue
<template>
  <AIBlueking :url="apiUrl" :hide-default-trigger="true" :hide-nimbus="true" />
</template>
```

### enablePopup

控制是否启用选中文本弹窗功能：

```vue
<template>
  <!-- 启用划词弹窗（默认为 true） -->
  <AIBlueking :url="apiUrl" :enable-popup="true" :shortcuts="shortcuts" />

  <!-- 禁用划词弹窗 -->
  <AIBlueking :url="apiUrl" :enable-popup="false" />
</template>
```

### nimbusSize

设置悬浮球大小：

```vue
<template>
  <!-- 可选值: 'small' | 'normal' | 'large' -->
  <AIBlueking :url="apiUrl" nimbus-size="small" />
</template>
```

### 默认最小化

```vue
<template>
  <!-- 初始为最小化状态 -->
  <AIBlueking :url="apiUrl" :default-minimize="true" />
</template>
```

### 禁用输入框

```vue
<template>
  <!-- 只读模式，用户无法输入 -->
  <AIBlueking :url="apiUrl" :disabled-input="true" />
</template>
```

### Header 图标控制

精细控制 Header 中各个图标的显示：

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :show-new-chat-icon="true"
    :show-history-icon="true"
    :show-more-icon="true"
    :show-compression-icon="false"
  />
</template>
```

### 下拉菜单配置

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :dropdown-menu-config="{
      showRename: true,
      showAutoGenerate: true,
      showShare: true,
    }"
  />
</template>
```

## teleportTo 渲染目标

通过 `teleportTo` prop 指定组件渲染到的目标 DOM 元素，使用 Vue 3 的 `<Teleport>` 实现：

```vue
<template>
  <div>
    <!-- 组件内容将渲染到 #ai-container 中 -->
    <AIBlueking :url="apiUrl" teleport-to="#ai-container" />

    <!-- 渲染目标 -->
    <div id="ai-container"></div>
  </div>
</template>
```

常见用法：

```vue
<!-- 渲染到 body -->
<AIBlueking :url="apiUrl" teleport-to="body" />

<!-- 渲染到指定的 CSS 选择器 -->
<AIBlueking :url="apiUrl" teleport-to=".app-container" />
```

## 代码示例：综合定制

```vue
<template>
  <AIBlueking
    ref="aiRef"
    :url="apiUrl"
    ext-cls="custom-ai-assistant"
    title="项目助手"
    hello-text="欢迎使用项目智能助手！输入 / 查看快捷指令"
    placeholder="描述你的需求..."
    teleport-to="body"
    :draggable="true"
    :default-width="500"
    :default-height="650"
    :default-top="80"
    :default-left="50"
    :max-width="800"
    :hide-nimbus="false"
    :hide-header="false"
    :enable-popup="true"
    :disabled-input="false"
    :default-minimize="false"
    nimbus-size="normal"
    :show-new-chat-icon="true"
    :show-history-icon="true"
    :show-compression-icon="true"
    :dropdown-menu-config="{
      showRename: true,
      showAutoGenerate: true,
      showShare: true,
    }"
    :shortcuts="shortcuts"
    :prompts="prompts"
    @show="onShow"
    @close="onClose"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const aiRef = ref<InstanceType<typeof AIBlueking> | null>(null);
const apiUrl = '/api/ai/assistant/';

const shortcuts = [
  {
    id: 'explain',
    name: '解释',
    icon: 'bkai-icon bkai-explain',
    components: [
      { type: 'textarea', key: 'text', name: '内容', fillBack: true },
    ],
  },
];

const prompts = ['请帮我分析这段代码', '请帮我写单元测试'];

const onShow = () => console.log('面板显示');
const onClose = () => console.log('面板关闭');
</script>

<style>
.custom-ai-assistant {
  --ai-primary-color: #2dcb73;
  border-radius: 16px;
}
</style>
```
