# 消息分享

AI 小鲸 v2.0 提供了完整的消息分享能力，支持用户选择对话中的消息并生成分享链接。分享功能由 [`ShareBusinessManager`](/api/ai-blueking/managers) 负责业务逻辑，`UIStateManager` 管理选择模式的 UI 状态。

## ChatBot 独立模式

在 `ChatBot` 独立使用时，内置了完整的分享流程，开箱即用。

### 分享流程

![分享流程](/images/guide/share-flow.png)

### 使用方法

```vue
<template>
  <ChatBot
    ref="chatBotRef"
    url="/api/ai/assistant/"
    :enable-selection="isSelecting"
    :share-loading="isShareLoading"
    @request-share="onRequestShare"
    @confirm-share="onConfirmShare"
    @cancel-share="onCancelShare"
  />
</template>

<script lang="ts" setup>
import { ref } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { IToolBtn, Message } from '@blueking/chat-x';

const chatBotRef = ref<InstanceType<typeof ChatBot> | null>(null);
const isSelecting = ref(false);
const isShareLoading = ref(false);

// 用户请求进入分享模式（来自 message-tools 的分享按钮）
const onRequestShare = () => {
  isSelecting.value = true;
};

// 用户确认分享
const onConfirmShare = async (messages: Message[], source?: IToolBtn) => {
  // 自定义 triggerSelection 按钮（如保存）不会走内置分享，需按 source 自行处理
  if (source && source.id !== 'share') {
    console.log('custom selection confirm:', source.id, messages);
    isSelecting.value = false;
    return;
  }

  isShareLoading.value = true;
  try {
    // 获取 chatHelper 实例调用分享 API
    const chatHelper = chatBotRef.value?.getChatHelper();
    if (!chatHelper) return;

    const sessionCode = chatHelper.session.current.value?.sessionCode;
    if (!sessionCode) return;

    const result = await chatHelper.message.shareMessages(sessionCode, messages);
    if (result) {
      const shareUrl = `${result.share_page}share-page/${result.share_token}`;
      await navigator.clipboard.writeText(shareUrl);
      console.log('分享链接已复制:', shareUrl);
    }
  } finally {
    isShareLoading.value = false;
    isSelecting.value = false;
  }
};

// 用户取消分享
const onCancelShare = () => {
  isSelecting.value = false;
};
</script>
```

## AIBlueking 集成模式

在 `AIBlueking` 组件中，分享功能由 `UIStateManager` 和 `ShareBusinessManager` 协调工作，提供两个入口。

### 分享入口

1. **Header 下拉菜单**：通过 Header 的「更多」菜单中的「分享」选项触发
2. **消息工具栏**：每条消息右侧的工具栏中的「分享」按钮

### 使用方法

```vue
<template>
  <AIBlueking
    :url="apiUrl"
    :dropdown-menu-config="{ showShare: true }"
    @share="onShare"
    @share-messages="onShareMessages"
    @transfer-messages="onTransferMessages"
  />
</template>

<script lang="ts" setup>
import AIBlueking from '@blueking/ai-blueking';
import '@blueking/ai-blueking/dist/vue3/style.css';

const apiUrl = '/api/ai/assistant/';

// Header 分享按钮点击
const onShare = () => {
  console.log('用户触发了分享操作');
};

// 分享消息完成（包含分享的消息 ID 列表）
const onShareMessages = (messageIds: string[]) => {
  console.log('分享的消息 IDs:', messageIds);
};

// 转发消息（用于跨会话转发场景）
const onTransferMessages = (messageIds: string[]) => {
  console.log('转发的消息 IDs:', messageIds);
};
</script>
```

### 内部协调流程

![内部协调流程](/images/guide/share-coordination.png)

## 原子模式

如果需要完全自定义分享流程，可以手动管理选择状态和分享逻辑。

```vue
<template>
  <div>
    <div class="toolbar">
      <button @click="enterShareMode">选择消息</button>
      <button v-if="isSelecting" @click="confirmShare" :disabled="selectedCount === 0">
        确认分享 ({{ selectedCount }})
      </button>
      <button v-if="isSelecting" @click="cancelShare">取消</button>
    </div>

    <ChatBot
      ref="chatBotRef"
      url="/api/ai/assistant/"
      :enable-selection="isSelecting"
      :share-loading="isShareLoading"
      @confirm-share="handleConfirmShare"
      @cancel-share="handleCancelShare"
    />
  </div>
</template>

<script lang="ts" setup>
import { ref, computed } from 'vue';
import { ChatBot } from '@blueking/ai-blueking';
import type { Message } from '@blueking/chat-x';

const chatBotRef = ref<InstanceType<typeof ChatBot> | null>(null);
const isSelecting = ref(false);
const isShareLoading = ref(false);
const selectedMessages = ref<Message[]>([]);

const selectedCount = computed(() => selectedMessages.value.length);

const enterShareMode = () => {
  isSelecting.value = true;
};

const confirmShare = () => {
  // 触发 ChatBot 的确认分享流程
  // ChatBot 会 emit confirm-share 事件，携带选中的消息
};

const handleConfirmShare = async (messages: Message[]) => {
  selectedMessages.value = messages;
  isShareLoading.value = true;

  try {
    const chatHelper = chatBotRef.value?.getChatHelper();
    if (!chatHelper) return;

    const sessionCode = chatHelper.session.current.value?.sessionCode;
    if (!sessionCode) return;

    // 调用分享 API
    const result = await chatHelper.message.shareMessages(sessionCode, messages);
    if (result) {
      const shareUrl = `${result.share_page}share-page/${result.share_token}`;
      // 自定义分享行为（如弹窗展示、复制到剪贴板等）
      await navigator.clipboard.writeText(shareUrl);
      alert(`分享链接已复制: ${shareUrl}`);
    }
  } finally {
    isShareLoading.value = false;
    isSelecting.value = false;
    selectedMessages.value = [];
  }
};

const handleCancelShare = () => {
  isSelecting.value = false;
  selectedMessages.value = [];
};

const cancelShare = () => {
  isSelecting.value = false;
  selectedMessages.value = [];
};
</script>
```

## Props

| Prop | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enableSelection` | `boolean` | `false` | 是否启用消息选择模式，启用后消息列表显示勾选框 |
| `shareLoading` | `boolean` | `false` | 分享操作是否正在加载中，用于显示加载状态 |

## Events

| 事件 | 参数 | 说明 |
|------|------|------|
| `request-share` | — | 用户从消息工具栏点击分享按钮，请求进入选择模式 |
| `confirm-share` | `messages: Message[], source?: IToolBtn` | 用户确认分享/多选；`source` 为触发按钮（内置分享为 `share` 或空，自定义 `triggerSelection` 为对应工具）。仅内置分享会走 ShareBusinessManager |
| `cancel-share` | — | 用户取消分享，退出选择模式 |
| `share-messages` | `messageIds: string[]` | （AIBlueking）分享完成，携带分享的消息 ID 列表 |
| `transfer-messages` | `messageIds: string[]` | （AIBlueking）转发消息，携带消息 ID 列表 |
| `share` | — | （AIBlueking）Header 分享按钮点击 |
| `agent-action` | `tool: IToolBtn, messages: Message[]` | 自定义消息工具点击（非内置 cite/rebuild/delete/like/unlike） |

## ShareBusinessManager

`ShareBusinessManager` 是分享业务管理器，封装了分享的核心逻辑：

```typescript
class ShareBusinessManager {
  constructor(messageModule: IMessageModule, sessionModule: ISessionModule);

  /**
   * 分享消息
   * @param messages 要分享的消息列表
   * @returns 分享结果 { shareUrl, userMessageIds }
   */
  async shareMessages(messages: IMessage[]): Promise<ShareResult>;
}

interface ShareResult {
  shareUrl: string;           // 分享链接
  userMessageIds: string[];   // 分享的用户消息 ID 列表
}
```

**注意事项**：

- `ShareBusinessManager` 只负责调用 API 和构造分享链接，不管理 UI 状态（loading、Toast 等）
- UI 状态由调用方（组件层）负责管理
- 分享 API 会在 `chat-helper` 层自动过滤只保留 `role === User` 的消息 ID
