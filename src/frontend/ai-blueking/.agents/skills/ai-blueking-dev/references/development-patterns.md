# 内部开发模式参考

本文档描述 ai-blueking 内部的开发模式，包括 Manager 使用、工具操作处理、文件上传等。

---

## 初始化模式

### useChatBootstrap（AIBlueking 内部使用）

```typescript
import { useChatBootstrap } from '@blueking/ai-blueking';

const {
  chatHelper,
  isReady,
  agentInfo,
  agentName,
  currentSession,
} = useChatBootstrap({
  url: normalizedUrl,
  requestOptions: props.requestOptions,
  autoInit: true,
  protocolCallbacks: {
    onStart: () => emit('receive-start'),
    onMessage: () => emit('receive-text'),
    onDone: () => emit('receive-end'),
    onError: (error) => handleError(error),
  },
});
```

---

## 会话管理模式

使用 `SessionBusinessManager` 统一管理会话业务逻辑：

```typescript
import { SessionBusinessManager } from '@blueking/ai-blueking';

const sessionBusinessManager = new SessionBusinessManager(
  chatHelper.session,
  chatHelper.message,
  null, // eventEmitter 可选
  {
    enableChatSession: true,
    initialSessionCode: props.initialSessionCode,
  }
);

await sessionBusinessManager.createNewSession();
await sessionBusinessManager.switchSession(sessionCode);
await sessionBusinessManager.deleteSession(sessionCode);
await sessionBusinessManager.loadRecentSession({ skipLoadSessions: true });
```

---

## 聊天业务管理模式

使用 `ChatBusinessManager` 统一管理消息发送和副作用：

```typescript
import { ChatBusinessManager } from '@blueking/ai-blueking';

const chatBusinessManager = new ChatBusinessManager(
  chatHelper.agent,
  chatHelper.message,
  chatHelper.session,  // 支持自动重命名等功能
  null,  // eventEmitter 可选
  {
    openingRemark: '欢迎语',
    predefinedQuestions: ['问题1', '问题2'],
  }
);

// 发送消息（内部自动处理自动重命名等副作用）
await chatBusinessManager.sendMessage(content, sessionCode, { property });

// 重新生成（删除旧回复 + 重新发送用户消息）
await chatBusinessManager.regenerateFromAIMessages(aiMessages, sessionCode);

// 重新发送带 property 的消息
await chatBusinessManager.resendMessageWithProperty(messageId, sessionCode, content, property);

// 停止生成
chatBusinessManager.stopGeneration();
```

---

## 工具操作处理模式

ChatBot 内部如何处理各种工具操作的模式参考：

```typescript
// AI 消息操作
const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
  // 引用：合并 AI 消息内容，设置到输入框
  if (tool.id === 'cite') {
    const content = messages
      .filter(m => m.role !== MessageRole.Reasoning)
      .map(m => typeof m.content === 'string' ? m.content : JSON.stringify(m.content || ''))
      .join('\n');
    cite.value = content;
    focusInput();
    return;
  }

  // 重新生成：调用业务管理器
  if (tool.id === 'rebuild') {
    await chatBusinessManager.regenerateFromAIMessages(aiMessages, sessionCode);
    return;
  }

  // 删除：AI 消息组 + 对应的用户消息一起删除
  if (tool.id === 'delete') {
    const lastUserMessage = findLastUserMessageBefore(allMessages, aiMessages[0]);
    const messagesToDelete = [lastUserMessage, ...aiMessages];
    await chatHelper.message.deleteMessages(messagesToDelete);
    return;
  }

  // 点赞/点踩：返回反馈原因列表给 UI
  if (tool.id === 'like' || tool.id === 'unlike') {
    const rate = tool.id === 'like' ? 5 : 0;
    const reasons = await chatHelper.session.getSessionFeedbackReasons(rate);
    return reasons || [];
  }
};

// 点赞/点踩确认提交
const handleAgentFeedback = async (
  tool: IToolBtn,
  messages: Message[],
  reasonList: string[],
  otherReason: string,
) => {
  const sessionCode = chatHelper.session.current?.value?.sessionCode;
  const userMessageId = findLastUserMessageIdBefore(allMessages, messages[0]);
  const rate = tool.id === 'like' ? 5 : 0;

  await chatHelper.session.postSessionFeedback({
    sessionCode,
    sessionContentIds: [userMessageId],
    rate,
    labels: reasonList,
    comment: otherReason,
  });
};

// 用户消息编辑确认（文本消息）
const handleUserInputConfirm = async (
  message: Message,
  content: UserMessage['content'],
  docSchema: TagSchema,
) => {
  const sessionCode = chatHelper.session.current?.value?.sessionCode;
  await chatHelper.agent.resendMessage(String(message.id), sessionCode, content);
};

// 用户消息编辑确认（快捷指令消息）
const handleUserShortcutConfirm = async (
  message: Message,
  formModel: Record<string, unknown>,
) => {
  const property = buildShortcutProperty(shortcut, formModel);
  await chatBusinessManager.resendMessageWithProperty(
    String(message.id), sessionCode, formModel.input, property
  );
};
```

---

## 文件上传

ChatInput 支持文件上传功能，传入 `onUpload` 回调后自动显示上传按钮：

```typescript
const handleUpload = async (file: File) => {
  const sessionCode = chatHelper.session.current?.value?.sessionCode;
  if (!sessionCode) return {};
  return await chatHelper.session.uploadFile(sessionCode, file);
};
```

```vue
<ChatInput
  :on-upload="handleUpload"
  ...
/>
```

---

## 获取内部 chatHelper（独立模式进阶用法）

独立模式下，外部可通过 `agent-info-loaded` 事件或 `getChatHelper()` 获取 chatHelper 实例，实现更精细的控制：

```vue
<template>
  <ChatBot
    ref="chatBotRef"
    url="/api/"
    @agent-info-loaded="onReady"
  />
</template>

<script setup lang="ts">
import { ChatBot } from '@blueking/ai-blueking';
import type { IChatHelper } from '@blueking/chat-helper';

const chatBotRef = ref();

const onReady = (chatHelper: IChatHelper) => {
  // 拿到 chatHelper 后可以做更多操作
  const agentInfo = chatHelper.agent.info.value;
  console.log('Agent 名称:', agentInfo?.name);

  // 监听会话列表
  watch(() => chatHelper.session.list.value, (sessions) => {
    console.log('会话列表更新:', sessions.length);
  });
};

// 或通过 ref 获取
const getHelper = () => chatBotRef.value?.getChatHelper();
</script>
```

---

## 快捷指令的两种触发模式

ChatBot 提供两种快捷指令编程式触发方式，对应旧版 `handleShortcutClick` 的两种行为：

### selectShortcut — 显示表单

等价于旧版 `handleShortcutClick({ shortcut }, false)`，选择快捷指令并显示表单，用户手动确认后提交。

```typescript
// 显示表单，用户可编辑后再提交
chatBotRef.value.selectShortcut(command, selectedText);
```

### sendShortcut — 直接发送

等价于旧版 `handleShortcutClick({ shortcut }, true)`，跳过表单直接发送消息。内部逻辑：
1. 从 `command.components` 的 `default` 值构建 `formModel`
2. 如果有 `selectedText`，填充到 `fillBack` 字段
3. 调用 `buildShortcutProperty` 构建 `property`
4. 调用 `doSendMessage` 发送消息

```typescript
// 跳过表单，直接用默认值发送
await chatBotRef.value.sendShortcut(command, selectedText);

// AIBlueking 也暴露了同名方法
await aiBluekingRef.value.sendShortcut(command, selectedText);
```
