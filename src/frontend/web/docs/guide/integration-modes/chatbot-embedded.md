# ChatBot 页面嵌入模式

`ChatBot` 是 AI 小鲸的核心聊天组件，支持独立使用，将聊天窗口直接嵌入到页面的指定区域，无需浮球、拖拽或面板容器即可快速集成 AI 对话能力。

::: tip AIDev 自动加载
组件初始化时会自动通过 `agent/info` 接口加载 Agent 配置（快捷指令、提示词、欢迎语等），**无需手动传入**。你只需要提供 AIDev 平台发布后的 URL。
:::

## 适用场景

- **页面主内容**：将聊天窗口作为页面的核心功能区域。
- **侧边栏聊天**：嵌入到页面侧边栏，提供辅助对话能力。
- **自定义会话列表**：结合外部会话列表组件，构建完整的聊天页面（参见 [自定义会话列表](/guide/advanced-usage/external-session-list)）。
- **弹窗/卡片内**：在弹窗、卡片等容器中集成对话能力。

::: warning 嵌入模式不是开箱即用的完整工作台
`ChatBot` 只有聊天区，**不带** Header。会话名称、右侧「执行情况 / 文件产物」侧栏的展开/收起，必须由业务方自己实现。浮窗（`AIBlueking`）则由内置 `AIHeader` 提供开关。见下方 [业务 Header](#业务-header会话名称--侧栏开关)。
:::

## 快速开始

::: code-group

```vue [Vue 3]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      ref="chatBotRef"
      url="https://your-aidev-url.com/api/"
      :request-options="requestOptions"
      @send-message="handleSendMessage"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { ChatBotExpose } from '@blueking/ai-blueking';

const chatBotRef = ref<ChatBotExpose>();

const requestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
};

const handleSendMessage = (message: string) => console.log('发送:', message);
const handleError = (error: Error) => console.error('错误:', error);

// 外部控制（≥ v2.1.4-beta.13 建议先 whenReady）
const externalSend = async () => {
  await chatBotRef.value?.whenReady();
  chatBotRef.value?.sendMessage('Hello');
};
const switchSession = async (code: string) => {
  await chatBotRef.value?.whenReady();
  await chatBotRef.value?.switchSession(code);
};
</script>
```

```vue [Vue 2]
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      ref="chatBotRef"
      url="https://your-aidev-url.com/api/"
      :request-options="requestOptions"
      @send-message="handleSendMessage"
      @error="handleError"
    />
  </div>
</template>

<script>
import { ChatBot } from '@blueking/ai-blueking';

export default {
  components: { ChatBot },
  data() {
    return {
      requestOptions: {
        headers: () => ({ Authorization: `Bearer ${this.getToken()}` }),
      },
    };
  },
  methods: {
    handleSendMessage(message) {
      console.log('发送:', message);
    },
    handleError(error) {
      console.error('错误:', error);
    },
    // 外部控制
    externalSend() {
      this.$refs.chatBotRef.sendMessage('Hello');
    },
    switchSession(code) {
      this.$refs.chatBotRef.switchSession(code);
    },
  },
};
</script>
```

:::

## Props 参考

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `url` | `string` | — | **必填**。后端 API 地址（来自 AIDev 平台） |
| `autoLoad` | `boolean` | `true` | 是否在挂载时自动加载 Agent 信息和会话列表 |
| `sessionCode` | `string` | — | 指定初始会话 Code，传入后自动切换到该会话 |
| `shortcuts` | `Shortcut[]` | `[]` | 快捷指令列表（通常由 AIDev 后台配置自动加载，此 prop 用于覆盖或补充） |
| `shortcutLimit` | `number` | `6` | 欢迎页快捷指令最大展示数量 |
| `resources` | `Resource[]` | `[]` | 资源列表，用于上下文增强 |
| `prompts` | `Prompt[]` | `[]` | 预设 Prompt 列表 |
| `helloText` | `string` | — | 欢迎语文本，不传则使用 Agent 默认欢迎语 |
| `placeholder` | `string` | — | 输入框占位文本 |
| `height` | `string \| number` | `'100%'` | 组件高度 |
| `maxWidth` | `string \| number` | — | 组件最大宽度 |
| `extCls` | `string` | — | 自定义外层 CSS 类名 |
| `requestOptions` | `RequestOptions` | — | 请求配置，支持自定义 headers、超时等 |
| `asideCollapsed` | `boolean` | 内部默认折叠 | 侧栏折叠态。传入后严格受控，须配合 `v-model:asideCollapsed`。侧栏固定从右侧展开，**已移除 `placement`** |
| `timezone` | `string` | — | 消息时间展示所用的 IANA 时区名（**≥ v2.2.3**，如 `Asia/Shanghai`）；未配置时按浏览器时区。详见 [消息时间展示](/guide/core-features/chat-interaction#消息时间展示) |

## Events 事件

| 事件名 | 参数 | 说明 |
|--------|------|------|
| `send-message` | `(message: string)` | 用户发送消息时触发 |
| `receive-start` | — | 开始接收 AI 响应时触发 |
| `receive-text` | `(text: string)` | 接收到流式文本片段时触发 |
| `receive-end` | — | AI 响应接收完成时触发 |
| `stop` | — | 用户手动停止生成时触发 |
| `error` | `(error: Error)` | 发生错误时触发 |
| `session-switched` | `(sessionCode: string)` | 会话切换完成时触发 |
| `shortcut-click` | `(shortcut: Shortcut)` | 用户点击快捷指令时触发 |
| `agent-info-loaded` | `(agentInfo: AgentInfo)` | Agent 信息加载完成时触发 |
| `feedback` | `(type: 'like' \| 'unlike', messageId: string)` | 用户对消息进行反馈时触发 |
| `confirm-share` | `(messages: Message[])` | 用户确认分享时触发 |
| `cancel-share` | — | 用户取消分享时触发 |
| `request-share` | — | 用户请求进入分享模式时触发 |
| `update:asideCollapsed` | `(collapsed: boolean)` | 侧栏折叠态变更（`v-model:asideCollapsed`） |

## Expose 方法

通过 `ref` 获取组件实例后，可调用以下方法进行外部控制：

| 方法 / 属性 | 类型 | 说明 |
|-------------|------|------|
| `sendMessage(text)` | `(text: string) => Promise<void>` | 以编程方式发送消息 |
| `stopGeneration()` | `() => void` | 停止当前正在生成的响应 |
| `switchSession(code)` | `(code: string) => Promise<void>` | 切换到指定会话 |
| `setCiteText(text)` | `(text: string) => void` | 设置引用文本到输入框 |
| `focusInput()` | `() => void` | 聚焦输入框 |
| `selectShortcut(shortcut, selectedText?)` | `(shortcut: IShortcut, selectedText?: string) => void` | 选择快捷指令并显示表单 |
| `sendShortcut(shortcut, selectedText?)` | `(shortcut: IShortcut, selectedText?: string) => Promise<void>` | 直接发送快捷指令（跳过表单） |
| `enterShareMode()` | `() => void` | 进入分享选择模式 |
| `exitShareMode()` | `() => void` | 退出分享选择模式 |
| `getChatHelper()` | `() => IChatHelper \| null` | 获取内部 `chatHelper` 实例，用于高级操作 |
| `messages` | `ComputedRef<Message[]>` | 当前会话的消息列表（响应式） |
| `currentSession` | `Ref<ISession \| null>` | 当前会话信息（响应式） |
| `isGenerating` | `Ref<boolean>` | 是否正在生成中（响应式） |

## 独立模式 vs 集成模式

`ChatBot` 根据是否传入 `chatHelper` prop 自动切换运行模式：

| 对比项 | 独立模式（无 chatHelper） | 集成模式（传入 chatHelper） |
|--------|--------------------------|---------------------------|
| **chatHelper 来源** | ChatBot 内部自动创建 | 由父组件（如 AIBlueking）传入 |
| **生命周期管理** | ChatBot 自行管理创建和销毁 | 由父组件管理，ChatBot 仅使用 |
| **会话管理** | ChatBot 独立管理 | 与父组件共享同一 chatHelper，会话状态同步 |
| **适用场景** | 独立嵌入、简单集成 | 作为 AIBlueking 内部子组件使用 |
| **初始化流程** | 自动执行 getAgentInfo → getSessions → 选择会话 | 跳过初始化，复用已有状态 |
| **使用方式** | 直接使用 `<ChatBot url="..." />` | 通常不需要直接使用，由 AIBlueking 内部组装 |

> **提示**：大多数场景下推荐使用独立模式。仅在需要多个组件共享同一对话状态时，才考虑集成模式。

## 业务 Header：会话名称 + 侧栏开关 {#业务-header会话名称--侧栏开关}

工作台浮窗的新 UI 由 `AIBlueking` + `AIHeader` 开箱提供。把 `ChatBot` 嵌进页面时，需要业务方补一层 Header：

| 位置 | 内容 | 数据来源 |
| --- | --- | --- |
| 左侧 | 当前会话名称 | `@agent-info-loaded` 拿到 `chatHelper` 后读 `session.current.sessionName` |
| 右侧 | 展开 / 收起侧栏 | `v-model:asideCollapsed`；图标用 `@blueking/chat-x` 的 `CollapsedAsideIcon` |

`CollapsedAsideIcon` 是预创建的 VNode，不能当 SFC 直接写在模板里，需 `cloneVNode` 包一层组件。只写 `:aside-collapsed` 不写 `v-model` 时，点击文件卡片或打开自定义 Tab 的内部展开请求会被丢掉。

```vue
<template>
  <div class="chat-main">
    <header class="chat-main-header">
      <h1 class="chat-main-title">{{ currentSessionName }}</h1>
      <span
        class="aside-toggle"
        :title="asideCollapsed ? '展开侧栏' : '收起侧栏'"
        @click="asideCollapsed = !asideCollapsed"
      >
        <AsideToggleIcon />
      </span>
    </header>
    <ChatBot
      v-model:aside-collapsed="asideCollapsed"
      :url="url"
      height="100%"
      @agent-info-loaded="handleAgentInfoLoaded"
    />
  </div>
</template>

<script setup lang="ts">
import { cloneVNode, computed, defineComponent, ref, shallowRef } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { ChatBotExpose } from '@blueking/ai-blueking';
import { CollapsedAsideIcon } from '@blueking/chat-x';

const AsideToggleIcon = defineComponent({
  name: 'AsideToggleIcon',
  setup() {
    return () => cloneVNode(CollapsedAsideIcon);
  },
});

type ChatHelper = NonNullable<ReturnType<ChatBotExpose['getChatHelper']>>;

const url = ref('https://your-aidev-url.com/api/');
const chatHelperInstance = shallowRef<ChatHelper | null>(null);
const asideCollapsed = ref(true);
const currentSessionName = computed(
  () => chatHelperInstance.value?.session.current.value?.sessionName?.trim() ?? '',
);

const handleAgentInfoLoaded = (helper: ChatHelper) => {
  chatHelperInstance.value = helper;
};
</script>
```

Header 建议高度 **52px**、左侧标题 16px / 行高 24px / `#313238`，与蓝鲸内容区标题栏一致。

::: tip 完整样例
- Playground：`packages/ai-blueking/playground/views/EmbeddedHeaderView.vue`（含左侧会话列表；标题栏「查看源码」可复制最小接入代码）
- 生产级工作台：`publish-template/src/views/ChatWindow.vue`（搜索、批量删除、内联改名）
- 左侧会话列表接线见 [自定义会话列表](/guide/advanced-usage/external-session-list)
:::
