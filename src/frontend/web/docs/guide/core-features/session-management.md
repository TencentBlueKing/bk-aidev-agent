# 会话管理

::: tip 默认行为
组件挂载时自动完成会话初始化（加载 Agent → 会话列表 → 最近会话）。
AIBlueking 内置完整会话管理 UI。仅在需要**自定义会话列表**等场景下使用以下 API。
:::

AI 小鲸 v2.0 提供了完整的多会话管理能力，每个会话拥有独立的对话上下文。会话管理由 [`SessionBusinessManager`](/guide/internals/manager-pattern) 负责业务编排，底层通过 `@blueking/chat-helper` 的 `SessionModule` 与后端 API 交互。

## 会话概念

每个会话代表一个独立的对话上下文，包含独立的消息历史。会话由 [`ISession`](/api/ai-blueking/types) 接口定义：

```typescript
interface ISession {
  sessionCode: string;            // 会话唯一编码
  sessionName: string;            // 会话名称
  sessionContentCount?: number;   // 消息数量（用于判断会话是否有内容）
  createdAt?: string;             // 创建时间
  updatedAt?: string;             // 更新时间
  isTemporary?: boolean;          // 是否为临时会话
  model?: string;                 // 会话关联模型（llm_code）；切换会话时同步 ModelSelector，用户切换会写回
  labels?: string[];              // 标签
  comment?: string;               // 备注
  rate?: number;                  // 评分
}
```

::: tip 与模型选择的关系
自 **v2.2.2** 起，切换历史会话会用 `session.model` 同步 ModelSelector；用户切换模型会写回当前会话。编排入口为 `ModelSelectionManager`。详见 [模型选择](/guide/core-features/model-selection)。
:::

## ChatBot 内置会话管理

`ChatBot` 组件内置了基础的会话管理能力，通过 Props 配置即可使用：

### autoLoad

设置 `autoLoad` 为 `true`（默认值），`ChatBot` 挂载时会自动执行初始化流程：

![会话自动加载行为](/images/guide/session-autoload.png)

**≥ v2.1.4-beta.13**：在外部调用 `switchSession` / `sendMessage` 前，可使用 `await chatBotRef.whenReady()` 确保 `getSessions` 与 `loadRecentSession` 已完成，语义对齐 `AIBlueking` 的 `await show()`。详见 [编程式控制 — whenReady](/guide/advanced-usage/programmatic-control#whenready-isready-等待初始化-v214-beta13)。

### sessionCode

通过 `sessionCode` prop 可以指定要打开的会话：

```vue
<template>
  <ChatBot
    url="/api/ai/assistant/"
    :auto-load="true"
    session-code="my_session_001"
  />
</template>
```

## SessionBusinessManager API

`SessionBusinessManager` 是会话业务管理器，封装了所有会话操作的业务流程。

### 核心方法

```typescript
class SessionBusinessManager {
  // === 响应式状态（来自 AG-UI SDK）===
  get sessionList(): Ref<ISession[]>;         // 会话列表
  get currentSession(): Ref<ISession | null>; // 当前会话
  get isListLoading(): Ref<boolean>;          // 列表加载中
  get isCreateLoading(): Ref<boolean>;        // 创建中
  get isDeleteLoading(): Ref<boolean>;        // 删除中
  get isUpdateLoading(): Ref<boolean>;        // 更新中
  get isCurrentLoading(): Ref<boolean>;       // 当前会话加载中

  // === 业务方法 ===
  createNewSession(): Promise<void>;                              // 创建新会话（便捷方法）
  createSession(options?: CreateSessionOptions): Promise<void>;   // 创建会话（完整参数）
  switchSession(sessionCode: string, options?): Promise<void>;    // 切换会话
  deleteSession(sessionCode: string): Promise<void>;              // 删除会话
  updateSessionName(sessionCode: string, name: string): Promise<void>; // 重命名
  loadSessions(): Promise<void>;                                  // 加载会话列表
  loadRecentSession(options?): Promise<void>;                     // 加载最近会话（初始化入口）
  getSession(sessionCode: string): Promise<void>;                 // 获取单个会话
}
```

### 创建会话选项

```typescript
interface CreateSessionOptions {
  name?: string;          // 会话名称，默认 '新会话'
  sessionCode?: string;   // 会话编码，默认自动生成
  isTemporary?: boolean;  // 是否为临时会话
}
```

## 会话列表

会话数据通过 AG-UI SDK 的 `SessionModule` 管理，提供响应式的列表和当前会话引用：

```typescript
// session.list — 会话列表（Ref<ISession[]>）
// session.current — 当前会话（Ref<ISession | null>）

// 通过 useChatBootstrap 获取
const { chatHelper, sessionList, currentSession } = useChatBootstrap({
  url: '/api/ai/assistant/',
});

// sessionList 和 currentSession 是 ComputedRef，自动跟踪变化
watch(sessionList, (sessions) => {
  console.log('会话列表更新:', sessions.length, '个会话');
});

watch(currentSession, (session) => {
  console.log('当前会话:', session?.sessionName);
});
```

## 自动加载行为

`ChatBot` 和 `AIBlueking` 组件在挂载时会执行自动加载流程。以下是完整的初始化时序：

![会话初始化时序](/images/guide/session-init-sequence.png)

> **性能优化**：`getAgentInfo()` 和 `getSessions()` 并行执行，减少初始化等待时间。`loadRecentSession` 接收 `skipLoadSessions: true`，避免重复请求会话列表。

### 与 `show()` 的配合（≥ v2.1.4-beta.9）

通过 `ref` 调用 `show()` 时，面板会立即打开，但返回的 Promise 会等到会话初始化完成后再 resolve：

1. `getAgentInfo` + `getSessions`（bootstrap）
2. `loadRecentSession`（当 `loadRecentSessionOnMount` 为 `true` 时）
3. 若传入 `sessionCode`，再执行 `switchSession`

因此集成方可在 `await aiBluekingRef.value?.show()` 之后安全读取 `getChatHelper()?.session.list` 与 `current`，无需再监听额外就绪事件。详见 [编程式控制 - show](/guide/advanced-usage/programmatic-control#show-显示窗口)。

## 多会话 UI

### AIBlueking 内置会话管理

`AIBlueking` 组件在 Header 中内置了会话管理 UI：

```vue
<template>
  <AIBlueking
    url="/api/ai/assistant/"
    :enable-chat-session="true"
    :show-history-icon="true"
    :show-new-chat-icon="true"
    @new-chat="onNewChat"
    @session-initialized="onSessionReady"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const onNewChat = () => {
  console.log('用户创建了新会话');
};

const onSessionReady = (data: { openingRemark: string; predefinedQuestions: string[] }) => {
  console.log('会话初始化完成，欢迎语:', data.openingRemark);
};
</script>
```

Header 提供以下会话操作入口：

- **新建会话按钮**：调用 `SessionBusinessManager.createNewSession()`
- **历史记录下拉**：展示会话列表，点击切换会话
- **更多菜单**：重命名、自动生成名称、分享等

### 自定义会话列表

如果需要自定义会话列表 UI，可以使用 `ChatBot` 的独立模式并手动管理会话：

```vue
<template>
  <div class="custom-chat-layout">
    <!-- 自定义会话列表 -->
    <aside class="session-list">
      <button @click="createSession">新建会话</button>
      <ul>
        <li
          v-for="session in sessions"
          :key="session.sessionCode"
          :class="{ active: session.sessionCode === currentSessionCode }"
          @click="switchToSession(session.sessionCode)"
        >
          {{ session.sessionName }}
          <span class="count">{{ session.sessionContentCount || 0 }}</span>
          <button @click.stop="deleteSession(session.sessionCode)">删除</button>
        </li>
      </ul>
    </aside>

    <!-- ChatBot 聊天区域：嵌入模式须自建 Header + 侧栏开关 -->
    <main class="chat-area">
      <ChatBot
        ref="chatBotRef"
        v-model:aside-collapsed="asideCollapsed"
        url="/api/ai/assistant/"
        @agent-info-loaded="onChatHelperReady"
      />
    </main>
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { IChatHelper, ISession } from '@blueking/ai-blueking';

const chatBotRef = ref<InstanceType<typeof ChatBot> | null>(null);
const chatHelper = ref<IChatHelper | null>(null);
const asideCollapsed = ref(true);

const sessions = computed(() => chatHelper.value?.session.list.value ?? []);
const currentSessionCode = computed(() =>
  chatHelper.value?.session.current.value?.sessionCode ?? ''
);

// ChatBot 初始化完成后获取 chatHelper 实例
const onChatHelperReady = (helper: IChatHelper) => {
  chatHelper.value = helper;
};

// 切换会话
const switchToSession = async (sessionCode: string) => {
  await chatBotRef.value?.switchSession(sessionCode);
};

// 创建新会话
const createSession = async () => {
  if (!chatHelper.value) return;
  const sessionCode = `session_${Date.now()}`;
  await chatHelper.value.session.createSession({
    sessionCode,
    name: '新会话',
  });
};

// 删除会话
const deleteSession = async (sessionCode: string) => {
  if (!chatHelper.value) return;
  await chatHelper.value.session.deleteSession(sessionCode);
};
</script>
```

## 代码示例

### 切换会话

```typescript
// 通过 ChatBot expose
await chatBotRef.value.switchSession('target_session_code');

// 通过 AIBlueking expose
await aiBluekingRef.value.switchToSession('target_session_code');
```

### 创建新会话

```typescript
// 通过 AIBlueking expose
await aiBluekingRef.value.addNewSession();

// 带自定义会话编码
await aiBluekingRef.value.addNewSession('custom_session_code');
```

### 删除会话

```typescript
// 通过 SessionBusinessManager（需获取 chatHelper 实例）
const chatHelper = chatBotRef.value.getChatHelper();
if (chatHelper) {
  await chatHelper.session.deleteSession('session_to_delete');
}
```

### 重命名会话

```typescript
// 通过 AIBlueking expose
await aiBluekingRef.value.updateSessionName('session_code', '新的会话名称');
```
