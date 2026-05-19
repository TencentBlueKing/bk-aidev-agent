---
name: ai-blueking-dev
description: 蓝鲸 AI 小鲸组件开发指南。基于 @blueking/chat-x（UI 组件）和 @blueking/chat-helper（业务 SDK）开发 AI 聊天应用、智能体、对话界面。涵盖 ChatBot 独立使用、AIBlueking 完整集成、流式响应、快捷指令、划词选择、自定义消息渲染（图表/表单/iframe）等。触发场景：开发 AI 小鲸、集成 AI Agent、使用 chat-x/chat-helper、构建 AI 对话 UI、实现流式聊天、自定义消息组件渲染。
metadata:
  author: blueking
  version: '4.5'
---

# AI 小鲸组件开发指南

## 何时激活此 Skill

- 开发 AI 聊天界面、对话应用
- 集成 `@blueking/chat-x` 或 `@blueking/chat-helper`
- 使用 `ChatBot`、`AIBlueking`、`ChatContainer`、`MessageContainer` 等组件
- 实现流式响应、会话管理、快捷指令
- 基于 `ai-blueking` 组件进行二次开发
- 自定义消息渲染（`parseCustomBlocks`、`custom-component` 代码块、`#message` 插槽自定义组件）

## 架构概览

```
┌──────────────────────────────────────────────────────┐
│                  应用层 (Your App)                      │
├──────────────────────────────────────────────────────┤
│  @blueking/ai-blueking (业务组件层)                     │
│    AIBlueking ── 完整面板（Header + ChatBot + 拖拽）    │
│    ChatBot ───── 独立聊天组件（~200 行纯组装层）         │
│    Managers ──── 业务管理器（Session/Chat/Shortcut）     │
├────────────────────┬─────────────────────────────────┤
│  @blueking/chat-x  │  @blueking/chat-helper           │
│  (纯 UI 组件库)     │  (AG-UI 业务 SDK)                 │
│  ChatContainer     │  useChatHelper()                  │
│  ChatInput         │  AGUIProtocol (流式协议)           │
│  MessageContainer  │  agent / session / message 模块   │
├────────────────────┴─────────────────────────────────┤
│                      后端 API                           │
└──────────────────────────────────────────────────────┘
```

**关键约束**：chat-x 和 chat-helper 互不依赖，ai-blueking 是唯一的组装层。

## 使用模式选择

| 场景                                           | 推荐模式               | 说明                     |
| ---------------------------------------------- | ---------------------- | ------------------------ |
| 需要完整面板（Header、拖拽、悬浮球、划词选择） | AIBlueking             | 开箱即用的完整体验       |
| 只需聊天区域，嵌入到自定义布局中               | ChatBot 独立模式       | 轻量、灵活，自己控制布局 |
| 需要精细控制每个 UI 组件                       | 原子组件 + chat-helper | 最大灵活度，自行组装     |

## 快速开始

### ChatBot 独立使用

```vue
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      ref="chatBotRef"
      url="https://your-api.com/api/"
      :shortcuts="shortcuts"
      :request-options="requestOptions"
      hello-text="欢迎使用 AI 助手"
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
  const shortcuts = [{ id: 'summary', name: '总结内容', icon: 'icon-summary' }];

  const handleSendMessage = (message: string) => console.log('发送:', message);
  const handleError = (error: Error) => console.error('错误:', error);
</script>
```

### AIBlueking 完整面板

```vue
<template>
  <AIBlueking
    ref="aiBluekingRef"
    url="https://your-api.com/api/"
    :request-options="requestOptions"
    :shortcuts="shortcuts"
    :enable-popup="true"
    :draggable="true"
    @send-message="handleSendMessage"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AIBlueking } from '@blueking/ai-blueking';
  import type { AIBluekingExpose } from '@blueking/ai-blueking';

  const aiBluekingRef = ref<AIBluekingExpose>();
  const showPanel = () => aiBluekingRef.value?.show();
</script>
```

> 原子组件自行组装的完整示例见 [集成模式与示例](references/integration-patterns.md)。

## 关键陷阱

### `#message` 插槽透传 (CRITICAL)

自定义 `ChatContainer` 的 `#message` 插槽时，**必须透传用户消息工具回调**，否则用户消息的删除/编辑/复制/引用全部失效，而 AI 消息不受影响。

原理：AI 消息的 `MessageTools` 在 `MessageContainer` 内部渲染（不经过 `#message` 插槽），但用户消息的工具回调通过 `MessageRender` → `UserMessage` 的 `onAction` prop 传递，走的是 `#message` 插槽。

```vue
<!-- ❌ 错误：用户消息工具全部失效 -->
<template #message="{ message, messageToolsStatus }">
  <MessageRender :message="message" :message-tools-status="messageToolsStatus" />
</template>

<!-- ✅ 正确：必须透传回调 -->
<template #message="{ message, messageToolsStatus }">
  <MessageRender
    :message="message"
    :message-tools-status="messageToolsStatus"
    :on-action="tool => handleUserAction(tool, message)"
    :on-input-confirm="(content, docSchema) => handleUserInputConfirm(message, content, docSchema)"
    :on-shortcut-confirm="formModel => handleUserShortcutConfirm(message, formModel)"
    :tippy-options="messageToolsTippyOptions"
  />
</template>
```

### `requestOptions` 响应式

`requestOptions`（及 chat-helper 的 `requestData.headers` / `requestData.data`）支持：

- 普通对象、`() => object`
- `ref` / `computed`（修改 `.value` 后后续请求自动生效）
- 外层 `requestOptions` 可为 `ref` / `computed`（AIBlueking / ChatBot / `useChatBootstrap`）

旧写法无需修改；需要动态 token、租户 ID 时可直接传 `ref`，不必再包一层稳定闭包。

### `requestOptions.data` 注入规则

`requestOptions.data`（及 chat-helper `requestData.data`）按方法自动分流：

- POST/PUT/PATCH/DELETE → 合并进请求体
- GET/HEAD/OPTIONS → 合并进 query（`params`），不会写入 body

### 编程式渲染事件只用 emit

通过 `h()` + `render()` 渲染的组件，事件只用 emit，**不要在 props 中定义 `on*` 回调**，否则会导致同一事件触发两次。详见项目规则 `vue3-h-render-events.mdc`。

### `new-chat` vs `new-chat-created` 事件

AIHeader 新增会话成功后触发两个事件，职责不同：

| 事件 | 参数 | 触发时机 | 说明 |
|------|------|----------|------|
| `new-chat` | 无 | 每次点击新增按钮 | V1 兼容，仅通知"用户点了新增"，不携带数据 |
| `new-chat-created` | `(session: { sessionCode: string; sessionName?: string; createdAt?: string })` | `sessionBusinessManager.createNewSession()` 成功后 | 携带新会话信息，仅 V2 有 `sessionBusinessManager` 时触发 |

```vue
<!-- AIBlueking 中监听（事件会从 AIHeader 透传到 AIBlueking） -->
<AIBlueking
  @new-chat="handleNewChat"
  @new-chat-created="handleNewChatCreated"
/>

<script setup>
const handleNewChat = () => {
  // V1 兼容：仅知道用户点击了新增
};

const handleNewChatCreated = (session) => {
  // V2：拿到新会话的 sessionCode、sessionName、createdAt
  console.log('新会话:', session.sessionCode, session.sessionName);
};
</script>
```

> **注意**：当无 `sessionBusinessManager`（V1 模式）时，`new-chat-created` 不会触发。依赖此事件的业务需处理该情况。

### `addNewSession` 接受 `CreateSessionOptions`

`AIBluekingExpose.addNewSession` 签名为 `(options?: CreateSessionOptions) => Promise<void>`，不传参数则自动生成 sessionCode/name。`CreateSessionOptions` 包含 `sessionCode?`、`name?`、`isTemporary?`。

### `beforeNimbusClick` 拦截 Nimbus 点击

`AIBluekingProps.beforeNimbusClick` 可拦截 Nimbus 悬浮球点击。返回 `false` 阻止默认 `showPanel`，返回 `true` 或不返回继续默认行为。支持 `async`。Vue2 wrapper 中此 prop 已加入 `deepWatchProps`，动态切换时会重新 mount 内部 Vue3 组件。

### 错误处理：ChatBot `@error` vs AIBlueking `@sdk-error`

两种模式的错误事件接口不同：

| 模式 | 事件 | 参数 | 说明 |
|------|------|------|------|
| ChatBot 独立模式 | `@error` | `(error: Error)` | 原始 Error 对象 |
| AIBlueking 集成模式 | `@sdk-error` | `{ apiName, code, message, data }` | 结构化错误数据 |

**AIBlueking 不对外暴露 `@error` 事件**，所有错误（初始化失败、流式对话错误）统一通过 `@sdk-error` 输出，业务方可根据 `apiName` 区分错误类型：

- `apiName: 'init'` — 初始化阶段错误（Agent 信息获取失败、会话加载失败）
- `apiName: 'chat'` — 流式对话阶段错误（SSE onError、ChatBot 内部错误）

```vue
<!-- ChatBot 独立模式 -->
<ChatBot url="/api/" @error="(err) => console.error(err)" />

<!-- AIBlueking 集成模式 -->
<AIBlueking url="/api/" @sdk-error="handleSdkError" />

<script setup>
const handleSdkError = ({ apiName, code, message, data }) => {
  if (apiName === 'init') {
    // 初始化失败：提示用户检查网络或 API 地址
  } else if (apiName === 'chat') {
    // 对话错误：提示用户重试
  }
};
</script>
```

### `#headerLeft` 插槽自定义 Header 左侧

AIBlueking 的 Header 区域分为 `.left-section`（logo + 标题 + 更多）和 `.right-section`（工具栏图标），两者之间提供 `#headerLeft` 插槽，用于在标题右侧、工具栏左侧插入自定义内容（如标签、状态指示器、自定义按钮）。

**Vue3 用法：**

```vue
<AIBlueking :url="apiUrl">
  <template #headerLeft>
    <span class="pro-tag">Pro</span>
  </template>
</AIBlueking>
```

**Vue2 用法：**

Vue2 的 `createElement` 产生的是 Vue2 VNode，无法被内部 Vue3 应用渲染。需使用包导出的 `h` 函数：

```javascript
import AIBluekingV2, { h } from '@blueking/ai-blueking/vue2';

// 在 template 中使用 scoped slot
<AIBluekingV2 :url="apiUrl">
  <template #headerLeft>
    <span class="pro-tag">Pro</span>
  </template>
</AIBluekingV2>

// 或在 render 函数中使用 h()
render(h2) {
  return h2(AIBluekingV2, {
    props: { url: apiUrl },
    scopedSlots: {
      headerLeft: () => h('span', { class: 'pro-tag' }, 'Pro'),
    },
  });
}
```

**插槽链路**：`AIBlueking #headerLeft` → `AIHeader #headerLeft`，无 slot props。

**约束**：
- 插槽内容应保持简洁（推荐单行），避免破坏 Header 高度（48px）和拖拽交互
- 插槽内容不可见时（如条件渲染）不影响 Header 布局

### 自定义消息渲染 (v2.1.4+)

AI 输出中嵌入图表、表单、iframe 等任意自定义组件。核心流程：

1. AI 回复中使用 ` ```custom-component ` 代码块输出 JSON 数据
2. `parseCustomBlocks()`（从 `@blueking/ai-blueking` 导出）解析为 `ContentBlock[]`
3. `CustomMessageRenderer` 根据 `block.data.type` 分发到业务组件

```vue
<ChatBot :url="apiUrl">
  <template #message="{ message }">
    <CustomMessageRenderer :message="message" />
  </template>
</ChatBot>
```

> 完整实现代码（ChartWidget / IframeWidget / FormWidget / 扩展指南 / Prompt 指南）见 [自定义消息渲染](references/custom-message-rendering.md)。

## 参考资源

- [ChatBot 组件 API](references/chatbot-api.md) — Props / Events / Slots / Expose、两种模式区别、初始化流程
- [架构设计原则](references/architecture.md) — 分层架构、数据流、职责边界、Composable 依赖图、开发检查清单
- [chat-x 组件 API](references/chat-x-api.md) — ChatContainer / ChatInput / MessageContainer、`useMessageGroup`、枚举与 `IToolBtn`
- [chat-helper SDK API](references/chat-helper-api.md) — agent / session / message 模块方法、AGUIProtocol、类型定义
- [集成模式与示例](references/integration-patterns.md) — 各场景完整代码示例、包导出、常见任务速查
- [内部开发模式](references/development-patterns.md) — Manager 使用、工具操作处理、文件上传、chatHelper 进阶用法
- [测试指南](references/testing.md) — 测试配置、Mock 工厂、withSetup 模式、编写示例
- [自定义消息渲染](references/custom-message-rendering.md) — 图表/表单/iframe 自定义组件、parseCustomBlocks、扩展指南
- [常见问题](references/faq.md) — FAQ 和问题排查
