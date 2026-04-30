# 集成模式与代码示例

本文档提供各种集成场景的完整代码示例。

---

## ChatBot 独立使用（推荐轻量场景）

### 最小化示例

```vue
<template>
  <div style="width: 600px; height: 800px;">
    <ChatBot
      url="https://your-api.com/api/"
      :request-options="requestOptions"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
  import { ChatBot } from '@blueking/ai-blueking';

  const requestOptions = {
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  };

  const handleError = (error: Error) => {
    console.error('ChatBot error:', error);
  };
</script>
```

### 完整功能示例

```vue
<template>
  <div class="chat-page">
    <div class="chat-header">
      <h3>{{ sessionName }}</h3>
      <button @click="createNewSession">新建会话</button>
    </div>

    <ChatBot
      ref="chatBotRef"
      url="https://your-api.com/api/"
      :shortcuts="shortcuts"
      :request-options="requestOptions"
      hello-text="你好，我是 AI 助手"
      placeholder="输入你的问题..."
      @send-message="handleSendMessage"
      @session-switched="handleSessionSwitched"
      @agent-info-loaded="handleAgentReady"
      @error="handleError"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { ChatBot } from '@blueking/ai-blueking';
  import type { ChatBotExpose, IShortcut } from '@blueking/ai-blueking';
  import type { IChatHelper, ISession } from '@blueking/chat-helper';

  const chatBotRef = ref<ChatBotExpose>();
  const sessionName = ref('');
  let chatHelperInstance: IChatHelper | null = null;

  const requestOptions = {
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  };

  const shortcuts: IShortcut[] = [
    { id: 'summary', name: '总结内容' },
    { id: 'translate', name: '翻译' },
  ];

  // Agent 初始化完成，获取 chatHelper 实例
  const handleAgentReady = (chatHelper: IChatHelper) => {
    chatHelperInstance = chatHelper;
    console.log('Agent:', chatHelper.agent.info.value?.name);
  };

  const handleSessionSwitched = (session: ISession | null) => {
    sessionName.value = session?.sessionName || '新会话';
  };

  const handleSendMessage = (message: string) => {
    console.log('已发送:', message);
  };

  const handleError = (error: Error) => {
    console.error(error);
  };

  // 外部操控
  const createNewSession = async () => {
    if (chatHelperInstance) {
      await chatHelperInstance.session.createSession({
        sessionCode: `session_${Date.now()}`,
        sessionName: '新会话',
      });
    }
  };
</script>
```

### ChatBot 嵌入到自定义布局

```vue
<template>
  <div class="custom-layout">
    <!-- 左侧：会话列表 -->
    <aside class="sidebar">
      <div
        v-for="session in sessions"
        :key="session.sessionCode"
        :class="{ active: session.sessionCode === currentCode }"
        @click="chatBotRef?.switchSession(session.sessionCode)"
      >
        {{ session.sessionName }}
      </div>
    </aside>

    <!-- 右侧：ChatBot -->
    <main class="chat-area">
      <ChatBot
        ref="chatBotRef"
        url="/api/"
        @agent-info-loaded="onReady"
        @session-switched="onSwitch"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';
  import { ChatBot } from '@blueking/ai-blueking';
  import type { ChatBotExpose } from '@blueking/ai-blueking';
  import type { IChatHelper, ISession } from '@blueking/chat-helper';

  const chatBotRef = ref<ChatBotExpose>();
  const sessions = ref<ISession[]>([]);
  const currentCode = ref('');

  const onReady = (chatHelper: IChatHelper) => {
    // 监听会话列表变化
    watch(
      () => chatHelper.session.list.value,
      list => {
        sessions.value = list;
      },
      { immediate: true },
    );
  };

  const onSwitch = (session: ISession | null) => {
    currentCode.value = session?.sessionCode || '';
  };
</script>
```

---

## AIBlueking 完整面板集成

### 基础集成

```vue
<template>
  <AIBlueking
    ref="aiBluekingRef"
    url="https://your-api.com/api/"
    :request-options="requestOptions"
    :shortcuts="shortcuts"
    :enable-popup="true"
    :draggable="true"
    :resize-props="{ min: 300, max: 600, initialDivide: 350 }"
    @send-message="handleSendMessage"
    @receive-start="handleReceiveStart"
    @receive-end="handleReceiveEnd"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AIBlueking } from '@blueking/ai-blueking';
  import type { AIBluekingExpose } from '@blueking/ai-blueking';

  const aiBluekingRef = ref<AIBluekingExpose>();

  const requestOptions = {
    headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  };

  // 显示/隐藏面板
  const showPanel = () => aiBluekingRef.value?.show();
  const hidePanel = () => aiBluekingRef.value?.hide();

  // 显示面板并跳转到指定会话
  const showWithSession = (sessionCode: string) => {
    aiBluekingRef.value?.show(sessionCode);
  };
</script>
```

### AIBlueking Expose API

```typescript
const aiBluekingRef = ref<AIBluekingExpose>();

// 面板控制
aiBluekingRef.value.show(sessionCode?);      // 显示面板，可选指定会话
aiBluekingRef.value.hide();                   // 隐藏面板

// 消息操作
aiBluekingRef.value.sendMessage(text);        // 发送消息
aiBluekingRef.value.stopGeneration();         // 停止生成

// 快捷指令
aiBluekingRef.value.selectShortcut(cmd, text);  // 选择快捷指令并显示表单
aiBluekingRef.value.sendShortcut(cmd, text);    // 直接发送快捷指令（跳过表单，等价旧版 handleShortcutClick(_, true)）

// 获取底层实例
aiBluekingRef.value.getChatHelper();          // 获取 chatHelper 实例

// 会话操作
aiBluekingRef.value.addNewSession(options?);  // 创建新会话，options: CreateSessionOptions
aiBluekingRef.value.switchToSession(code);    // 切换会话
aiBluekingRef.value.updateSessionName(code, name);

// 容器控制
aiBluekingRef.value.updatePosition(x, y);
aiBluekingRef.value.updateSize(w, h);
aiBluekingRef.value.updatePositionAndSize(x, y, w, h);

// 输入控制
aiBluekingRef.value.setCiteText(text);        // 设置引用文本
aiBluekingRef.value.focusInput();             // 聚焦输入框
```

### AIBlueking 会话相关事件

AIBlueking 暴露以下与会话操作相关的事件：

| 事件 | 参数 | 说明 |
|------|------|------|
| `new-chat` | 无 | 用户点击新增会话按钮时触发（V1 兼容，不携带数据） |
| `new-chat-created` | `(session: { sessionCode: string; sessionName?: string; createdAt?: string })` | 新会话创建成功后触发，携带 `sessionCode`、`sessionName`、`createdAt` 字段。仅在有 `sessionBusinessManager` 时触发 |
| `history-click` | `(event: Event)` | 用户点击历史会话按钮 |

```vue
<AIBlueking
  :url="apiUrl"
  @new-chat="handleNewChat"
  @new-chat-created="handleNewChatCreated"
  @history-click="handleHistoryClick"
/>

<script setup lang="ts">
const handleNewChat = () => {
  // 用户点击了新增按钮（不携带数据）
};

const handleNewChatCreated = (session: { sessionCode: string; sessionName?: string; createdAt?: string }) => {
  // 新会话创建成功，可拿到 sessionCode 等信息
  console.log('新会话已创建:', session.sessionCode, session.sessionName);
};

const handleHistoryClick = (event: Event) => {
  // 用户点击了历史会话按钮
};
</script>
```

### Nimbus 点击自定义（beforeNimbusClick）

默认点击 Nimbus 悬浮球会直接打开面板。通过 `beforeNimbusClick` prop 可拦截此行为，执行自定义逻辑后再决定是否打开面板。

- 返回 `false`：阻止默认 `showPanel`，由用户手动控制
- 返回 `true` 或不返回：继续默认打开面板
- 支持 `async` 函数

```vue
<template>
  <AIBlueking
    ref="aiBluekingRef"
    :url="apiUrl"
    :before-nimbus-click="handleNimbusClick"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { AIBlueking } from '@blueking/ai-blueking';
  import type { AIBluekingExpose } from '@blueking/ai-blueking';

  const aiBluekingRef = ref<AIBluekingExpose>();

  // 场景 1：点击 Nimbus 后切换到固定会话再打开
  const handleNimbusClick = async () => {
    await aiBluekingRef.value.switchToSession('fixed-session-code');
    // 不返回或返回 true → 继续默认 showPanel
  };

  // 场景 2：完全自定义打开行为，阻止默认
  const handleNimbusClickBlock = async () => {
    await aiBluekingRef.value.switchToSession('fixed-session-code');
    aiBluekingRef.value.show('fixed-session-code');
    return false; // 阻止默认 showPanel
  };
</script>
```

---

## 原子组件自行组装

### 完整聊天应用

```vue
<template>
  <div class="chat-app">
    <!-- 消息列表 -->
    <MessageContainer
      v-model:selected-user-messages="selectedUserMessages"
      :message-groups="messageGroups"
      :messages="messages"
      :message-status="messageStatus"
      :message-tools-status="messageToolsStatus"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      :on-user-input-confirm="handleUserInputConfirm"
      @stop-streaming="handleStop"
    />

    <!-- 快捷指令表单 -->
    <ShortcutRender
      v-if="selectedShortcut?.components?.length"
      v-bind="selectedShortcut"
      @close="handleCloseShortcut"
      @submit="handleSubmitShortcut"
    />

    <!-- 输入框 -->
    <ChatInput
      v-else
      v-model="userInput"
      v-model:cite="citeContent"
      :message-status="messageStatus"
      :shortcuts="shortcuts"
      :on-send-message="handleSend"
      :on-stop-sending="handleStop"
      :on-upload="handleUpload"
      @select-shortcut="handleSelectShortcut"
    />

    <!-- 划词选择 -->
    <AiSelection
      v-model:visible="aiSelectionVisible"
      :shortcuts="shortcuts"
      @select-shortcut="handleAiSelectionShortcut"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref, computed, onMounted, onBeforeUnmount, shallowRef } from 'vue';
  import {
    ChatInput,
    MessageContainer,
    ShortcutRender,
    AiSelection,
    MessageStatus,
    MessageToolsStatus,
    MessageRole,
    useMessageGroup,
    type Message,
    type Shortcut,
    type IToolBtn,
    type TagSchema,
    type UserMessage,
  } from '@blueking/chat-x';
  import { useChatHelper, AGUIProtocol } from '@blueking/chat-helper';
  import type { IUserMessage } from '@blueking/chat-helper';

  // ==================== 状态 ====================
  const userInput = ref('');
  const citeContent = ref('');
  const selectedShortcut = ref<Shortcut | null>(null);
  const selectedUserMessages = ref<Message[]>([]);
  const keyword = shallowRef('');
  const aiSelectionVisible = ref(false);

  // ==================== 初始化 ====================
  const protocol = new AGUIProtocol({
    onStart: () => {
      /* 流式开始 */
    },
    onMessage: _event => {
      /* 每条消息 */
    },
    onDone: () => {
      /* 流式完成 */
    },
    onError: error => {
      console.error('流式错误:', error);
    },
  });

  const chatHelper = useChatHelper({
    requestData: {
      urlPrefix: '/api/',
      headers: () => ({ Authorization: `Bearer ${getToken()}` }),
    },
    protocol,
  });

  // 注入消息模块到 protocol（原子模式必须）
  protocol.injectMessageModule(chatHelper.message);

  const { agent, session, message } = chatHelper;

  // ==================== 计算属性 ====================
  const messages = computed(() => message.list.value as Message[]);
  const { messageGroups } = useMessageGroup({
    keyword,
    messages,
    selectedUserMessages,
  });
  const messageStatus = computed(() => (agent.isChatting.value ? MessageStatus.Streaming : MessageStatus.Complete));
  const messageToolsStatus = computed(() =>
    messageStatus.value === MessageStatus.Streaming ? MessageToolsStatus.Disabled : undefined,
  );
  const shortcuts = computed(() => agent.info.value?.conversationSettings?.commands || []);

  // ==================== 生命周期 ====================
  onMounted(async () => {
    await agent.getAgentInfo();
    await session.getSessions();

    if (session.list.value.length > 0) {
      await session.chooseSession(session.list.value[0].sessionCode);
    } else {
      await session.createSession({
        sessionCode: `session_${Date.now()}`,
        sessionName: '新会话',
      });
    }
  });

  onBeforeUnmount(() => {
    agent.stopChat(session.current.value?.sessionCode ?? '');
  });

  // ==================== 消息处理 ====================
  const handleSend = async (content: UserMessage['content'], _docSchema: TagSchema) => {
    if (!session.current.value?.sessionCode) return;

    const cite = citeContent.value;
    userInput.value = '';
    citeContent.value = '';

    const options = cite ? { data: { property: { extra: { cite } } } } : undefined;
    await agent.chat(content as IUserMessage['content'], session.current.value.sessionCode, undefined, options);
  };

  const handleStop = () => {
    agent.stopChat(session.current.value?.sessionCode ?? '');
  };

  // ==================== 文件上传 ====================
  const handleUpload = async (file: File) => {
    const sessionCode = session.current.value?.sessionCode;
    if (!sessionCode) return {};
    return await session.uploadFile(sessionCode, file);
  };

  // ==================== 工具操作 ====================
  const handleAgentAction = async (tool: IToolBtn, msgs: Message[]) => {
    if (tool.id === 'cite') {
      citeContent.value = msgs
        .filter(m => m.role !== MessageRole.Reasoning)
        .map(m => (typeof m.content === 'string' ? m.content : JSON.stringify(m.content || '')))
        .join('\n');
      return;
    }

    if (tool.id === 'like' || tool.id === 'unlike') {
      const rate = tool.id === 'like' ? 5 : 0;
      const reasons = await session.getSessionFeedbackReasons(rate);
      return reasons || [];
    }
  };

  const handleAgentFeedback = async (tool: IToolBtn, msgs: Message[], reasonList: string[], otherReason: string) => {
    const sessionCode = session.current.value?.sessionCode;
    if (!sessionCode) return;

    const allMessages = message.list.value as Message[];
    const firstAiMsg = msgs[0];
    const userMsgIndex = allMessages.findIndex(m => m === firstAiMsg) - 1;
    const userMessageId = allMessages[userMsgIndex]?.id;

    if (userMessageId === undefined) return;

    const rate = tool.id === 'like' ? 5 : 0;
    await session.postSessionFeedback({
      sessionCode,
      sessionContentIds: [userMessageId],
      rate,
      labels: reasonList,
      comment: otherReason,
    });
  };

  const handleUserAction = async (tool: IToolBtn, msg: Message) => {
    if (tool.id === 'delete') {
      await message.deleteMessages([msg as any]);
      return;
    }
    if (tool.id === 'cite') {
      citeContent.value = typeof msg.content === 'string' ? msg.content : JSON.stringify(msg.content || '');
      return;
    }
  };

  const handleUserInputConfirm = async (msg: Message, content: UserMessage['content'], _docSchema: TagSchema) => {
    const sessionCode = session.current.value?.sessionCode;
    if (!sessionCode || msg.id === undefined) return;
    await agent.resendMessage(String(msg.id), sessionCode, content as IUserMessage['content']);
  };

  // ==================== 快捷指令 ====================
  const handleSelectShortcut = (shortcut: Shortcut, text?: string) => {
    if (shortcut.components?.length) {
      const fillBackComponent = shortcut.components.find(c => c.fillBack);
      const fillBackKey = fillBackComponent?.key || 'input';
      selectedShortcut.value = {
        ...shortcut,
        formModel: { ...shortcut.formModel, [fillBackKey]: text || '' },
      };
    } else {
      handleSend(shortcut.name, [[]]);
    }
  };

  const handleCloseShortcut = () => {
    selectedShortcut.value = null;
  };

  const handleSubmitShortcut = async (formModel: Record<string, unknown>) => {
    const shortcut = selectedShortcut.value;
    if (!shortcut) return;
    selectedShortcut.value = null;
    await handleSend(shortcut.name, [[]]);
  };

  const handleAiSelectionShortcut = (shortcut: Shortcut, text: string) => {
    aiSelectionVisible.value = false;
    citeContent.value = text;
    handleSelectShortcut(shortcut, text);
  };
</script>
```

---

## 会话管理集成

### 自定义会话列表

```vue
<template>
  <div class="session-list">
    <button @click="handleNewSession">新建会话</button>

    <div
      v-for="item in sessionList"
      :key="item.sessionCode"
      :class="['session-item', { active: item.sessionCode === currentSessionCode }]"
      @click="handleSwitchSession(item.sessionCode)"
    >
      <span>{{ item.sessionName }}</span>
      <button @click.stop="handleDeleteSession(item.sessionCode)">删除</button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import type { ISessionModule, IMessageModule } from '@blueking/chat-helper';
  import { SessionBusinessManager } from '@blueking/ai-blueking';

  const props = defineProps<{
    sessionModule: ISessionModule;
    messageModule: IMessageModule;
  }>();

  const sessionManager = new SessionBusinessManager(props.sessionModule, props.messageModule, null, {
    enableChatSession: true,
  });

  const sessionList = computed(() => sessionManager.sessionList.value);
  const currentSessionCode = computed(() => sessionManager.currentSession.value?.sessionCode);

  const handleNewSession = async () => {
    await sessionManager.createNewSession();
  };

  const handleSwitchSession = async (sessionCode: string) => {
    await sessionManager.switchSession(sessionCode);
  };

  const handleDeleteSession = async (sessionCode: string) => {
    await sessionManager.deleteSession(sessionCode);
  };
</script>
```

---

## 自定义消息渲染

### 集成到 MessageContainer

```vue
<template>
  <MessageContainer :messages="messages">
    <template #default="{ message }">
      <ChartMessage
        v-if="message.role === 'chart'"
        :data="message.content"
      />
      <MessageRender
        v-else
        :message="message"
      />
    </template>
  </MessageContainer>
</template>
```

---

## 错误处理模式

### ChatBot 独立模式 — `@error` 事件

ChatBot 独立模式通过 `@error` 事件暴露原始 `Error` 对象：

```vue
<ChatBot url="/api/" @error="handleError" />

<script setup>
const handleError = (error: Error) => {
  console.error('ChatBot error:', error);
  // 所有类型的错误（初始化、流式对话）都会触发此事件
};
</script>
```

### AIBlueking 集成模式 — `@sdk-error` 事件

AIBlueking **不对外暴露 `@error`**，所有错误统一通过 `@sdk-error` 输出，提供结构化数据便于业务方区分错误类型：

```vue
<AIBlueking url="/api/" @sdk-error="handleSdkError" />

<script setup>
const handleSdkError = ({ apiName, code, message, data }) => {
  // apiName: 'init' | 'chat'
  //   'init' — 初始化阶段错误（Agent 信息获取失败、会话加载失败）
  //   'chat' — 流式对话阶段错误（SSE onError、ChatBot 内部错误）
  // code: -1（保留字段，暂未细分）
  // message: 错误描述文本
  // data: 原始错误对象

  if (apiName === 'init') {
    console.error('初始化失败:', message);
    // 业务处理：提示用户检查 API 地址或网络
  } else if (apiName === 'chat') {
    console.error('对话错误:', message);
    // 业务处理：提示用户重试
  }
};
</script>
```

**内部机制**：AIBlueking 的 `use-ai-blueking-init.ts` 中通过统一的 `emitSdkError` 函数，将三类错误源归拢为 `@sdk-error`：

| 错误源 | 触发路径 | apiName |
|--------|---------|---------|
| 初始化失败（getAgentInfo/getSessions） | `watch(bootstrapError)` → `emitSdkError` | `'init'` |
| 流式对话错误（SSE onError） | `protocolCallbacks.onError` → `emitSdkError` | `'chat'` |
| ChatBot @error（独立模式） | `handleError` → `emitSdkError` | `'chat'` |

### 原子组件模式 — chat-helper 层错误处理

使用 `chat-helper` 直接组装时，错误通过 `AGUIProtocol.onError` 和 HTTP 拦截器处理：

```typescript
import { useChatHelper, AGUIProtocol } from '@blueking/chat-helper';
import { Message } from 'bkui-vue';

const chatHelper = useChatHelper({
  requestData: { urlPrefix: '/api/' },
  interceptors: {
    response: response => {
      if (response.data.code !== 0) {
        Message({ theme: 'error', message: response.data.message });
      }
      return response;
    },
  },
  protocol: new AGUIProtocol({
    onError: error => {
      Message({ theme: 'error', message: `AI 响应错误: ${error.message}` });
    },
  }),
});
```

---

## 消息分享模式

### ChatBot 独立模式（零配置）

ChatBot 在独立模式下内置了完整的分享功能，**无需额外代码**：

```vue
<!-- 分享功能开箱即用，无需监听任何事件 -->
<ChatBot url="/api/" @error="handleError" />
```

内部流程（由 `useShareSelection` composable + `useToolActions` composable 协作）：

1. 用户点击消息工具栏的「分享」→ `useToolActions` 设置 `internalEnableSelection = true`
2. MessageContainer 显示 Checkbox，用户勾选消息
3. 用户点击「确定」→ `useShareSelection` 创建 `ShareBusinessManager` 实例，调用 `shareMessages()`
4. 拼接分享链接、复制到剪贴板、Toast 提示
5. 自动退出选择模式

如果需要监听分享事件（如埋点），仍可监听 `request-share`、`confirm-share`、`cancel-share`。

### AIBlueking 集成模式（父组件协调）

在 AIBlueking 中，分享有两个入口（AIHeader 下拉菜单 + MessageTools 按钮），需要父组件统一协调：

```typescript
// ai-blueking.vue 内部
const uiStateManager = new UIStateManager();
const shareBusinessManager = new ShareBusinessManager(chatHelper.message, chatHelper.session);
const isSelectionMode = computed(() => uiStateManager.isSelectionMode.value);

// 两个入口统一走 handleShare
const handleShare = () => {
  uiStateManager.enableSelectionMode();
};

const handleCancelShare = () => {
  uiStateManager.disableSelectionMode();
};

const handleConfirmShare = async (messages: Message[]) => {
  const { shareUrl, userMessageIds } = await shareBusinessManager.shareMessages(messages);
  await copyToClipboard(shareUrl);
  BkMessage({ message: '分享链接已复制到剪贴板', theme: 'success' });
  uiStateManager.disableSelectionMode();
};
```

ChatBot 通过 props 接受外部控制：

```vue
<ChatBot
  :enable-selection="isSelectionMode"
  :share-loading="isShareLoading"
  @request-share="handleShare"
  @cancel-share="handleCancelShare"
  @confirm-share="handleConfirmShare"
/>
```

### 原子组件自行组装（手动模式）

如果不使用 ChatBot，直接使用 `MessageContainer`，则需要手动管理全部状态：

```typescript
const enableSelection = ref(false);
// 与 MessageContainer 的 v-model:selected-user-messages 对齐
const selectedUserMessages = ref<Message[]>([]);

const handleShare = () => {
  enableSelection.value = true;
};

const handleCancelShare = () => {
  enableSelection.value = false;
  selectedUserMessages.value = [];
};

const handleConfirmShare = async () => {
  if (selectedUserMessages.value.length === 0) return;
  const sessionCode = session.current.value?.sessionCode;
  if (!sessionCode) return;

  try {
    const result = await message.shareMessages(sessionCode, selectedUserMessages.value);
    const shareUrl = `${result.share_page}share-page/${result.share_token}`;
    await navigator.clipboard.writeText(shareUrl);
    Message({ theme: 'success', message: '分享链接已复制到剪贴板' });
  } catch (error) {
    Message({ theme: 'error', message: '分享失败' });
  } finally {
    enableSelection.value = false;
    selectedUserMessages.value = [];
  }
};
```

---

## 初始化模式

### useChatBootstrap（AIBlueking 内部使用）

```typescript
import { useChatBootstrap } from '@blueking/ai-blueking';

const { chatHelper, isReady, agentInfo, agentName, currentSession } = useChatBootstrap({
  url: normalizedUrl,
  requestOptions: props.requestOptions,
  autoInit: true,
  protocolCallbacks: {
    onStart: () => emit('receive-start'),
    onMessage: () => emit('receive-text'),
    onDone: () => emit('receive-end'),
    onError: handleError,
  },
});

// 监听初始化完成
watch(isReady, async ready => {
  if (ready) {
    await sessionBusinessManager.loadRecentSession({ skipLoadSessions: true });
  }
});
```

### 事件桥接模式（AIBlueking 内部使用）

```typescript
import { useEventBridge, createEventForwarders } from '@blueking/ai-blueking';

const { forwardToManager } = useEventBridge({
  componentManager,
  emit: emit as (event: string, ...args: unknown[]) => void,
});

const forwarders = createEventForwarders(forwardToManager);

// 使用
forwarders.sendMessage(message);
forwarders.receiveStart();
forwarders.receiveEnd();
```

---

## 包导出参考

```typescript
// 主组件
import { AIBlueking, ChatBot } from '@blueking/ai-blueking';

// 类型
import type {
  AIBluekingProps,
  AIBluekingExpose,
  AIBluekingEmits,
  ChatBotProps,
  ChatBotExpose,
  ChatBotEmits,
  IRequestOptions,
  IShortcut,
  DropdownMenuConfig,
  CreateSessionOptions,
} from '@blueking/ai-blueking';

// Composables（ai-blueking 级）
import { useChatBootstrap } from '@blueking/ai-blueking';
import type { ChatBootstrapOptions, ChatBootstrapReturn } from '@blueking/ai-blueking';

// Composables（ChatBot 级 — 用于高级自定义场景）
import {
  useChatbotInit,
  useChatbotState,
  useMessageSender,
  useShortcuts,
  useToolActions,
  useShareSelection,
} from '@blueking/ai-blueking';

// 业务管理器
import {
  ChatBusinessManager,
  SessionBusinessManager,
  ShortcutManager,
  UIStateManager,
  ComponentManager,
  createComponentManager,
} from '@blueking/ai-blueking';

// 容器组件
import { DraggableContainer } from '@blueking/ai-blueking';

// 重导出（来自 chat-helper）
import { AGUIProtocol, useChatHelper } from '@blueking/ai-blueking';

// 重导出（来自 chat-x / chat-helper）
import type {
  IAgentModule,
  ISessionModule,
  IMessageModule,
  ISession,
  IMessage,
  IAgentInfo,
} from '@blueking/ai-blueking';
```

---

## 常见任务速查

### 发送消息

```typescript
// 方式 1：通过 ChatBot ref（最简单）
chatBotRef.value?.sendMessage('帮我分析这段代码');

// 方式 2：通过业务管理器
await chatBusinessManager.sendMessage('消息内容', sessionCode);

// 带引用
await chatBusinessManager.sendMessage('消息内容', sessionCode, {
  property: { extra: { cite: '引用的文本' } },
});

// 带快捷指令上下文
await chatBusinessManager.sendMessage('快捷指令名称', sessionCode, {
  property: {
    extra: {
      command: 'shortcut-id',
      context: [{ key: 'input', value: '用户输入' }],
    },
  },
});
```

### 切换会话

```typescript
// 方式 1：通过 ChatBot ref
await chatBotRef.value?.switchSession(sessionCode);

// 方式 2：通过 SessionBusinessManager
await sessionBusinessManager.switchSession(sessionCode);

// 方式 3：直接调用 SDK（最底层）
const hasContent = (targetSession.sessionContentCount ?? 0) > 0;
await session.chooseSession(sessionCode, { loadMessages: hasContent });
```

### 创建新会话

```typescript
// 方式 1：通过 AIBlueking expose（推荐）
// 不传参数 — 自动生成 sessionCode 和 name
await aiBluekingRef.value.addNewSession();

// 传入 CreateSessionOptions
await aiBluekingRef.value.addNewSession({
  sessionCode: 'my-session',
  name: '我的会话',
  isTemporary: false,
});

// 方式 2：通过 SessionBusinessManager
await sessionBusinessManager.createNewSession();
await sessionBusinessManager.createSession({ sessionCode: 'my-session', name: '我的会话' });

// 方式 3：直接调用 SDK
await session.createSession({
  sessionCode: `new_session_${Date.now()}`,
  sessionName: '新会话',
});
```

### 删除会话

```typescript
// 单个删除
await session.deleteSession(sessionCode);

// 批量删除
await session.batchDeleteSessions(['session_1', 'session_2']);

// 删除所有会话
const allCodes = session.list.value.map(s => s.sessionCode);
await session.batchDeleteSessions(allCodes);
```

> 批量删除会自动处理列表更新和当前会话切换：当前会话被删除时切换到第一个剩余会话，全部删除时清空状态。

### 划词选择

```vue
<AiSelection
  v-model:visible="aiSelectionVisible"
  :shortcuts="shortcuts"
  :max-shortcut-count="3"
  @select-shortcut="handleAiSelectionShortcut"
  @selection-change="handleSelectionChange"
/>

<script setup>
  const handleAiSelectionShortcut = async (shortcut, text) => {
    // 显示面板
    await show();

    // 有表单组件则显示表单，否则设置引用
    if (shortcut.components?.length) {
      chatBotRef.value.selectShortcut(shortcut, text);
    } else {
      chatBotRef.value.setCiteText(text);
      chatBotRef.value.focusInput();
    }
  };
</script>
```

### 快捷指令的两种触发方式

```typescript
// 方式 1：selectShortcut — 显示表单，用户手动确认提交
aiBluekingRef.value.selectShortcut(command, selectedText);

// 方式 2：sendShortcut — 跳过表单，直接发送（等价旧版 handleShortcutClick(_, true)）
// 自动从 command.components 的 default 值构建 formModel，填充 fillBack 字段后直接发送
await aiBluekingRef.value.sendShortcut(command, selectedText);

// 获取 command 的方式
const chatHelper = aiBluekingRef.value.getChatHelper();
const commands = chatHelper?.agent.info.value?.conversationSettings?.commands;
if (commands?.length) {
  await aiBluekingRef.value.sendShortcut(commands[0], '选中的文本');
}
```

### 自定义 Header 左侧（`#headerLeft` 插槽）

AIBlueking 的 Header 在标题区域和右侧工具栏之间提供 `#headerLeft` 插槽，用于插入标签、状态指示器等自定义内容。

**Vue3 用法：**

```vue
<AIBlueking :url="apiUrl">
  <template #headerLeft>
    <span class="pro-tag">Pro</span>
  </template>
</AIBlueking>
```

**Vue2 用法：**

Vue2 中需使用包导出的 `h` 函数创建 Vue3 兼容 VNode：

```javascript
import AIBluekingV2, { h } from '@blueking/ai-blueking/vue2';

// template 方式
<AIBluekingV2 :url="apiUrl">
  <template #headerLeft>
    <span class="pro-tag">Pro</span>
  </template>
</AIBluekingV2>

// render 函数方式
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

**布局位置**：

```
[logo] [title] [more] | ← #headerLeft → | [new-chat] [history] [help] [compress] [close]
     .left-section                              .right-section
```
