---
name: ai-blueking-dev
description: 蓝鲸 AI 小鲸组件开发指南。基于 @blueking/chat-x（UI 组件）和 @blueking/chat-helper（业务 SDK）开发 AI 聊天应用、智能体、对话界面。涵盖 ChatBot 独立使用、AIBlueking 完整集成、流式响应、快捷指令、划词选择、模型选择（Model Select）、自定义消息渲染（图表/表单/iframe）、HITL 人机协同（工具审批/用户提问/中断恢复）、流程化智能体节点重试跳过、渲染模式（chat/share/test 分享态）、字号主题、侧栏自定义与自定义 Tab、欢迎区 `#welcome` 插槽、消息工具栏扩展（messageTools/updateTools）、非 Vue 宿主挂载等。触发场景：开发 AI 小鲸、集成 AI Agent、使用 chat-x/chat-helper、构建 AI 对话 UI、实现流式聊天、模型热切换、自定义消息组件渲染、human-in-the-loop、interrupt/resume、flow agent、自定义欢迎页、自定义消息工具按钮。
metadata:
  author: blueking
  version: '5.20'
  packages:
    ai-blueking: 2.2.2
    chat-x: 0.0.49-beta.8
    chat-helper: 0.0.12-beta.20
---

# AI 小鲸组件开发指南

## 何时激活此 Skill

- 开发 AI 聊天界面、对话应用
- 集成 `@blueking/chat-x` 或 `@blueking/chat-helper`
- 使用 `ChatBot`、`AIBlueking`、`ChatContainer`、`MessageContainer` 等组件
- 实现流式响应、会话管理、快捷指令、模型选择
- 基于 `ai-blueking` 组件进行二次开发
- 自定义消息渲染（`parseCustomBlocks`、`custom-component` 代码块、`#message` 插槽自定义组件）
- 人机协同 HITL（工具审批、用户提问、流程节点重试/跳过、中断与恢复）
- 渲染模式（`renderMode`：chat/share/test）、字号主题、侧栏自定义渲染与自定义 Tab
- 欢迎区 `#welcome` 插槽；消息工具栏 `messageTools` / `updateTools` 扩展与 `agent-action` / `confirm-share(source)`
- 非 Vue 宿主挂载（`mountAIBlueking` / `mountChatBot`）

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

### `#welcome` 与消息工具栏扩展

- `#welcome`：`AIBlueking` → `ChatBot` → `ChatContainer`，scope `{ openingRemark, welcomeTitle }`；无插槽时默认欢迎 UI 不变
- `messageTools` / `updateTools`：透传 chat-x 按 id 合并；`triggerSelection` 确认走 `confirm-share(messages, source)`；其它自定义按钮走 `agent-action`
- 仅 `!source || source.id === 'share'` 执行内置分享（方案 A）

详见 [ChatBot API](references/chatbot-api.md#消息工具栏扩展messagetools--updatetools)。

### `#message` 插槽透传 (CRITICAL)

自定义 `ChatContainer` / `ChatBot` / `AIBlueking` 的 `#message` 插槽时，**必须透传用户消息工具回调 _和_ `onInterruptResume`**，否则：

- 缺用户消息工具回调 → 用户消息的删除/编辑/复制/引用全部失效（AI 消息不受影响）
- 缺 `onInterruptResume` → HITL 中断卡片能渲染，但**审批取消 / 用户提问作答 / 流程节点重试跳过全部失效**（详见 [HITL](references/hitl.md)）

原理：AI 消息的 `MessageTools` 在 `MessageContainer` 内部渲染（不经过 `#message` 插槽），但用户消息的工具回调通过 `MessageRender` → `UserMessage` 的 `onAction` prop 传递、中断恢复通过 `onInterruptResume` 传递，二者都走 `#message` 插槽。

> **v2.2 变更**：`#message` 插槽作用域现在提供**第三个参数 `onInterruptResume`**（除既有的 `message`、`messageToolsStatus`）。

```vue
<!-- ❌ 错误：用户消息工具 + HITL 恢复动作全部失效 -->
<template #message="{ message, messageToolsStatus }">
  <MessageRender :message="message" :message-tools-status="messageToolsStatus" />
</template>

<!-- ✅ 正确：必须透传回调 + onInterruptResume -->
<template #message="{ message, messageToolsStatus, onInterruptResume }">
  <MessageRender
    :message="message"
    :message-tools-status="messageToolsStatus"
    :on-interrupt-resume="onInterruptResume"
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
| ChatBot 独立模式 | `@error` | `(error: Error)` | 原始 Error 对象；默认同时弹 Message（`errorToast`，文案 `error.message`） |
| AIBlueking 集成模式 | `@sdk-error` | `{ apiName, code, message, data }` | 结构化错误数据；父层统一 toast，内嵌 ChatBot 关闭 toast 防双弹 |

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

#### `@error` 的触发范围（重要）

ChatBot 内部所有错误都汇聚到单一出口 `useErrorReporter`（`src/components/composables/use-error-reporter.ts`），覆盖两类来源：

1. **调用点 catch**：初始化、切换会话、发送消息、快捷指令、消息工具操作（重发 / 删除 / 反馈）、中断恢复、`updateAgentInfo`、停止生成，以及独立模式下 AGUI 流式协议的 `onError`。
2. **业务管理器失败事件**：`ChatBusinessManager` / `SessionBusinessManager` 的 `chat-error` / `receive-error` / `session-error` 经 `managerErrorBridge` 汇入同一出口，覆盖调用点没有 catch 的路径。

这个出口保证两件事：

- **参数一定是 `Error` 实例**。非 Error 的 reject（字符串、裸对象）会经 `toError()` 归一化，对象带 `message` 字段时取该字段作为 `error.message`。不要再假设 `@error` 可能收到字符串。
- **同一个错误只触发一次**。业务管理器普遍「emit 失败事件后 rethrow」，同一个 Error 实例会同时经桥接和调用点 catch 抵达，出口按实例去重。注意去重按**实例**而非 message，两次独立请求失败仍会触发两次。

仍有边界：纯 HTTP 层失败（既不在上述调用点，业务管理器也没包）不会触发 `@error`。要覆盖全部 HTTP 错误，用 AIBlueking 的 `@sdk-error`（内部注册了 `chatHelper.onError` 全局兜底），或自行对 `getChatHelper()?.onError(...)` 注册处理器。

**停止生成（`stopChat`）的行为**：接口成功才 emit `stop`，失败改为 emit `error`。此前失败会被静默吞掉并照常 emit `stop`，业务方无法感知；如果代码里依赖「`stop` 一定会触发」做收尾，需改为同时监听 `error`。

**`abortChat` vs `stopChat`（重要）**：

| API | 作用 | 何时调用 |
| --- | --- | --- |
| `abortChat()` | 仅断开前端 `chat_completion` SSE，**后端 agent 继续跑** | URL 变化 / 组件卸载 / 切会话 / 静默重连替换旧连接 |
| `stopChat(sessionCode)` | 通知后端真正停止生成；后端经 SSE 推 `RUN_ERROR`（用户已取消）后关流 | **仅用户主动点击停止**（`stopGeneration`） |

ChatBot 在 `url` / `chatHelper` 变化或卸载时只会 `abortChat()`，不会自动调 `stopChat`。  
**`stopGeneration` 只调 `stopChat`，不断开 SSE**：前端 abort 会打乱后端 stop 时序。流由后端 `RUN_ERROR` 收尾；`RUN_ERROR` / `RUN_FINISHED` 均为终端事件，关流后不静默重连。

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

### HITL 人机协同（v2.2+）

Agent 可在流式执行中**中断**，把控制权交回用户，处理后再**恢复**。三类场景：

| 场景 | 中断/操作 | UI |
|------|-----------|----|
| 工具审批 | `InterruptReason.AIDevToolApproval` | 审批卡片（会话流内） |
| 用户提问 | `InterruptReason.UserQuestion` | 提问浮层（输入框上方） |
| 流程节点失败 | `FlowNodeRetry` / `FlowNodeSkip` | 节点重试/跳过按钮 |

**ChatBot / AIBlueking 开箱即用**，无需额外代码。唯一注意点是上面的 `#message` 插槽必须透传 `onInterruptResume`。原子组件模式需自行把 `onInterruptResume` 接到 `MessageContainer`，并用 `agent.streamRequest` / `agent.userOperationStreamRequest` 实现恢复。

- 恢复统一入口：chat-x 的 `OnInterruptResume = (payload: InterruptResume, interrupt?) => Promise<void> | void`
- 底层原语：chat-helper 的 `agent.streamRequest({ sessionCode, resume })` 与 `agent.userOperationStreamRequest(sessionCode, operation, payload)`
- chat-helper **没有** `onInterruptResume` 方法（它只提供原语 + `IResume` 结构）；统一回调在 chat-x/ai-blueking 层

> 完整协议、组件、集成示例（含用户「直接在输入框作答」旁路、流程节点重试/跳过、只读回显）见 [HITL 人机协同](references/hitl.md)。

### 渲染模式 `renderMode`（chat / share / test）

`RenderMode`（从 `@blueking/chat-x` / `@blueking/ai-blueking` 导出）控制整体交互形态，AIBlueking / ChatBot / ChatContainer 均支持（ChatContainer 为 v-model）：

| 值 | 说明 |
|----|------|
| `RenderMode.Chat`（默认） | 正常对话 |
| `RenderMode.Share` | **只读分享态**：隐藏输入与交互元素、禁用审批取消、流程节点仅保留「详情」。这是「分享态开放流程智能体查看能力」的实现方式 |
| `RenderMode.Test` | 测试态：隐藏 `share` 工具 |

`renderMode` 是现代分享方案，**取代**了手动切换 `enableSelection` 的旧写法（`enableSelection` 仍用于「多选消息以生成分享链接」的选择动作，二者职责不同）。字号主题（`size: 'normal' | 'small'`）已在 `AIBlueking` / `ChatBot` / `ChatContainer` 全链路透传，详见 [ChatBot API](references/chatbot-api.md) 与 [chat-x 组件 API](references/chat-x-api.md)。

### 模型选择（Model Select，≥ v2.2.2）

默认 `enableModelSelect: true`。初始化并行拉取 `GET llms/`；列表非空时在输入区展示 ModelSelector。

```vue
<!-- 默认开启 -->
<AIBlueking url="/api/" />

<!-- 关闭 -->
<ChatBot url="/api/" :enable-model-select="false" />

<!-- 外部列表（跳过内部拉取） -->
<ChatBot url="/api/" :models="myModels" />
```

**关键语义**：

| 规则 | 说明 |
| --- | --- |
| 展示 | `enableModelSelect !== false` 且列表非空 |
| 选中值 | UI 绑定 `llm_name`；发送传 `llm_code`（`agent.chat` 第 6 参） |
| 跟随 session | 切换历史会话时，用 `session.model` 同步 ModelSelector（命中列表时） |
| 写回 | 用户切换模型 → `ModelSelectionManager.persistSessionModel`（`session.model` 唯一写回出口） |
| 新建 | **所有建会话路径**（含初始化 `loadRecentSession`）统一经 `resolveModelForSession`：优先当前选中 / preferred，校验落在可用列表内；`enableModelSelect=false` 时不强制写 model |
| 空列表 | 启用模型选择但无可用模型 → 抛 `ModelUnavailableError`，阻断建会话并上报 `sdk-error`（`apiName: session`） |
| 首次 / 兜底 | `session.model` 命中列表 → 选中；空/未知且无有效选中 → `property.default` / 首项 |
| 附件按钮 | 跟随选中模型 `property.support_vision`；快捷指令 `supportUpload.vision` 优先 |

编排入口：`ModelSelectionManager`（`models` / `selectedLlmCode` / `resolveModelForSession` / `persistSessionModel`）。  
AIBlueking 创建实例并注入内嵌 ChatBot（`modelSelectionManager` prop），外壳层与聊天层共享同一份选中状态。  
`ChatBusinessManager` / `SessionBusinessManager` 均委托该管理器，不再各自持有模型状态。  
SDK：`agent.getLlms()` → `agent.models`；热切换 `agent.chat(..., property, llm_code)`。自定义请求参数（如 `temperature`）走 `config.data`，**不要**把 `model` 塞进 `config.data`。

## 参考资源

- [ChatBot 组件 API](references/chatbot-api.md) — Props / Events / Slots / Expose、两种模式区别、初始化流程
- [架构设计原则](references/architecture.md) — 分层架构、数据流、职责边界、Composable 依赖图、开发检查清单
- [chat-x 组件 API](references/chat-x-api.md) — ChatContainer / ChatInput / MessageContainer、`useMessageGroup`、枚举与 `IToolBtn`
- [chat-helper SDK API](references/chat-helper-api.md) — agent / session / message 模块方法、AGUIProtocol、类型定义
- [集成模式与示例](references/integration-patterns.md) — 各场景完整代码示例、包导出、常见任务速查
- [内部开发模式](references/development-patterns.md) — Manager 使用、工具操作处理、文件上传、chatHelper 进阶用法
- [测试指南](references/testing.md) — 测试配置、Mock 工厂、withSetup 模式、编写示例
- [自定义消息渲染](references/custom-message-rendering.md) — 图表/表单/iframe 自定义组件、parseCustomBlocks、扩展指南
- [HITL 人机协同](references/hitl.md) — 中断/恢复协议、工具审批、用户提问、流程节点重试跳过、`onInterruptResume` 契约、只读回显
- [Playground 实例索引](references/playground-examples.md) — 两套 playground 的**可运行真实代码**索引；HITL、侧栏自定义、自定义消息等「照着写」的权威参考
- [常见问题](references/faq.md) — FAQ 和问题排查

> 💡 **本 Skill 自包含**，无需仓库即可使用——HITL 插槽接线、中断数据结构、侧栏自定义契约等关键示例均已内联在各 reference 文档中。**若能访问源码仓库**，`packages/ai-blueking/playground`（集成层）与 `packages/chat-x/playground`（组件层）另有可运行的完整示例，见 [Playground 实例索引](references/playground-examples.md)。
