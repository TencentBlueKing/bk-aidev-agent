---
name: MessageContainer 消息列表容器
slug: message-container
kind: component
domain: setup
description: 负责消息分组渲染、滚动控制、工具栏和消息插槽透传。
aiSummary: >
  负责消息分组渲染、滚动控制、工具栏和消息插槽透传。
  源码位置：src/components/chat-message/message-container/message-container.vue。
relatedComponents:
  - slug: message-render
    relation: 按组渲染每条消息时委托 MessageRender
  - slug: chat-input
    relation: 常与 ChatInput 组合构成完整对话界面
  - slug: loading-message
    relation: 末尾为用户消息时自动追加 Loading 消息组
  - slug: interrupt-message
    relation: 透传 onInterruptResume；末条 interrupt 消息不触发组 hover
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { computed, ref } from 'vue'
  import MessageContainerComp from '../../../src/components/chat-message/message-container/message-container.vue'
  import { useMessageGroup } from '../../../src/composables/use-message-group'

  const createGroups = (msgs) => {
    const selected = ref([]);
    const { messageGroups } = useMessageGroup({
      messages: computed(() => msgs.value),
      selectedUserMessages: selected,
    });
    return messageGroups;
  };

  const messagesBasic = ref([
    {
      id: '1',
      messageId: 1,
      role: 'user',
      content: '你好，请介绍一下 Vue 3',
      status: 'complete',
    },
    {
      id: '2',
      messageId: 2,
      role: 'assistant',
      content: 'Vue 3 是一个渐进式 JavaScript 框架。它引入了 **Composition API**、更好的 TypeScript 支持以及更高效的虚拟 DOM 实现。\n\n主要特性包括：\n- 组合式 API（`setup`、`ref`、`reactive`）\n- 更小的包体积\n- 更快的渲染性能\n- `<script setup>` 语法糖',
      status: 'complete',
    },
  ]);

  const messagesReasoning = ref([
    {
      id: '1',
      messageId: 1,
      role: 'user',
      content: '分析一下这段代码的问题',
      status: 'complete',
    },
    {
      id: '2',
      messageId: 2,
      role: 'reasoning',
      content: ['首先，我需要理解这段代码的意图...', '看起来这是一个数据处理函数...', '发现了几个潜在问题...'],
      status: 'complete',
      duration: 3500,
    },
    {
      id: '3',
      messageId: 3,
      role: 'assistant',
      content: '根据分析，这段代码存在以下问题：\n\n1. **变量命名不规范**\n2. **缺少错误处理**\n3. **存在潜在的性能问题**',
      status: 'complete',
    },
  ]);

  const messagesToolCall = ref([
    {
      id: '1',
      messageId: 1,
      role: 'user',
      content: '查询一下北京今天的天气',
      status: 'complete',
    },
    {
      id: '2',
      messageId: 2,
      role: 'assistant',
      content: '好的，我来帮你查询北京的天气。',
      status: 'complete',
      toolCalls: [
        {
          id: 'call_weather',
          type: 'function',
          function: {
            name: 'get_weather',
            arguments: '{"city": "北京"}',
            description: '查询天气信息',
          },
        },
      ],
    },
    {
      id: '3',
      messageId: 3,
      role: 'tool',
      content: '{"temperature": 25, "weather": "晴天", "humidity": 45}',
      status: 'complete',
      toolCallId: 'call_weather',
      duration: 1200,
    },
    {
      id: '4',
      messageId: 4,
      role: 'assistant',
      content: '北京今天天气**晴朗**，温度 **25°C**，湿度 **45%**，非常适合出行。',
      status: 'complete',
    },
  ]);

  const messagesActivity = ref([
    {
      id: '1',
      messageId: 1,
      role: 'user',
      content: 'Vue 3 的 Composition API 有哪些优势？',
      status: 'complete',
    },
    {
      id: '2',
      messageId: 2,
      role: 'activity',
      activityType: 'knowledge_rag',
      content: {
        content: '从知识库中检索到 Vue 3 Composition API 相关文档。',
        referenceDocument: [
          { name: 'Vue 3 官方指南', url: 'https://vuejs.org/guide', originFile: 'vue3-guide.md' },
          { name: 'Composition API FAQ', url: 'https://vuejs.org/api', originFile: 'composition-api.md' },
        ],
      },
      status: 'complete',
    },
    {
      id: '3',
      messageId: 3,
      role: 'assistant',
      content: 'Vue 3 的 Composition API 主要有以下优势：\n\n1. **更好的逻辑复用**：通过组合函数（Composables）实现跨组件逻辑复用\n2. **更灵活的代码组织**：按功能而非选项类型组织代码\n3. **更好的类型推断**：完整的 TypeScript 支持\n4. **更小的打包体积**：支持 Tree-shaking',
      status: 'complete',
    },
  ]);

  const messagesError = ref([
    {
      id: '1',
      messageId: 1,
      role: 'user',
      content: '帮我生成一份报告',
      status: 'complete',
    },
    {
      id: '2',
      messageId: 2,
      role: 'assistant',
      content: '请求失败，服务暂时不可用，请稍后重试。',
      status: 'error',
    },
  ]);

  const messagesStreaming = ref([]);
  const streamingStatus = ref('complete');
  const isStreamingRunning = ref(false);

  const streamingFullText = '好的，下面是一个 TypeScript 实现的 `debounce` 函数：\n\n```typescript\nfunction debounce<T extends (...args: any[]) => any>(\n  fn: T,\n  delay: number\n): (...args: Parameters<T>) => void {\n  let timer: ReturnType<typeof setTimeout>;\n  return (...args) => {\n    clearTimeout(timer);\n    timer = setTimeout(() => fn(...args), delay);\n  };\n}\n```\n\n**使用示例：**\n\n```typescript\nconst handleInput = debounce((value: string) => {\n  console.log(value);\n}, 300);\n```';

  const startStreaming = async () => {
    if (isStreamingRunning.value) return;
    isStreamingRunning.value = true;

    messagesStreaming.value = [
      { id: '1', messageId: 1, role: 'user', content: '用 TypeScript 写一个 debounce 函数', status: 'complete' },
      { id: '2', messageId: 2, role: 'assistant', content: '', status: 'pending' },
    ];
    streamingStatus.value = 'streaming';

    const msg = messagesStreaming.value[1];
    const chars = [...streamingFullText];
    for (let i = 0; i < chars.length; i++) {
      if (streamingStatus.value === 'stop') break;
      msg.content += chars[i];
      msg.status = 'streaming';
      if (i % 3 === 0) await new Promise(r => setTimeout(r, 20));
    }

    msg.status = streamingStatus.value === 'stop' ? 'stop' : 'complete';
    streamingStatus.value = msg.status;
    isStreamingRunning.value = false;
  };

  const handleStopStreamingDemo = () => {
    streamingStatus.value = 'stop';
  };

  const messagesMultiRound = ref([
    {
      id: '1',
      messageId: 1,
      role: 'user',
      content: '什么是 RESTful API？',
      status: 'complete',
    },
    {
      id: '2',
      messageId: 2,
      role: 'assistant',
      content: 'RESTful API 是一种基于 **REST**（Representational State Transfer）架构风格的 API 设计规范。它使用标准的 HTTP 方法来进行资源操作：\n\n- `GET`：获取资源\n- `POST`：创建资源\n- `PUT`：更新资源\n- `DELETE`：删除资源',
      status: 'complete',
    },
    {
      id: '3',
      messageId: 3,
      role: 'user',
      content: '能给一个实际的例子吗？',
      status: 'complete',
    },
    {
      id: '4',
      messageId: 4,
      role: 'assistant',
      content: '当然，以用户管理为例：\n\n| 操作 | 方法 | 路径 |\n|------|------|------|\n| 获取用户列表 | GET | `/api/users` |\n| 创建用户 | POST | `/api/users` |\n| 获取单个用户 | GET | `/api/users/:id` |\n| 更新用户 | PUT | `/api/users/:id` |\n| 删除用户 | DELETE | `/api/users/:id` |',
      status: 'complete',
    },
  ]);

  const messagesLoading = ref([
    {
      id: '1',
      messageId: 1,
      role: 'user',
      content: '请帮我分析一下这段日志',
      status: 'complete',
    },
  ]);

  const groupsBasic = createGroups(messagesBasic);
  const groupsReasoning = createGroups(messagesReasoning);
  const groupsToolCall = createGroups(messagesToolCall);
  const groupsActivity = createGroups(messagesActivity);
  const groupsError = createGroups(messagesError);
  const groupsStreaming = createGroups(messagesStreaming);
  const groupsMultiRound = createGroups(messagesMultiRound);
  const groupsLoading = createGroups(messagesLoading);

  const handleAgentAction = async (tool, messages) => {
    console.log('AI 消息操作:', tool.id);
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面', '表达清晰'];
    }
  };

  const handleUserAction = async (tool, message) => {
    console.log('用户消息操作:', tool.id);
  };

  const handleAgentFeedback = (tool, messages, reasonList, otherReason) => {
    console.log('反馈:', tool.id, reasonList, otherReason);
  };

  const handleStopStreaming = () => {
    console.log('停止流式输出');
  };
</script>

# MessageContainer 消息容器
## 源码事实

- **源码位置**：`src/components/chat-message/message-container/message-container.vue`
- **能力域**：对话搭建
- **能力说明**：负责消息分组渲染、滚动控制、工具栏和消息插槽透传。



> **能力域**：对话搭建

消息列表容器组件，负责将原始的 `Message[]` 数组渲染为结构化的对话界面。核心能力：

- **消息分组**：将连续的非用户消息合并为一组，每组共享一个工具栏
- **Tool 消息关联**：自动将 `role: 'tool'` 消息注入到对应 Assistant 消息的 toolCall 中
- **Loading 自动注入**：末尾为用户消息时，自动追加 Loading 动画组
- **滚动管理**：`messageStatus` 为流式、等待响应或请求中（`streaming` / `pending` / `fetching`）时显示「停止生成」，离开底部时显示「返回底部」；`renderMode` 为 `Share` 时不显示「停止生成」
- **多选模式**：支持按消息组勾选，用户消息与 AI 回复联动选中

## 基础用法

```vue
<template>
  <MessageContainer
    :messages="messages"
    message-status="complete"
    :on-agent-action="handleAgentAction"
    :on-agent-feedback="handleAgentFeedback"
    :on-user-action="handleUserAction"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageContainer, MessageRole, MessageStatus, type Message, type IToolBtn } from '@blueking/chat-x';

  const messages = ref<Message[]>([
    {
      id: '1',
      messageId: '1',
      role: MessageRole.User,
      content: '你好，请介绍一下 Vue 3',
      status: MessageStatus.Complete,
    },
    {
      id: '2',
      messageId: '2',
      role: MessageRole.Assistant,
      content: 'Vue 3 是一个渐进式 JavaScript 框架...',
      status: MessageStatus.Complete,
    },
  ]);

  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    // copy 操作由 MessageContainer 内部处理，此处无需额外实现
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面', '表达清晰']; // 返回反馈原因列表
    }
  };
  const handleAgentFeedback = (tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => {
    console.log('反馈:', tool.id, reasonList, otherReason);
  };
  const handleUserAction = async (tool: IToolBtn, message: Message) => {
    console.log('用户消息操作:', tool.id, message);
  };
  const handleStopStreaming = () => {
    console.log('停止流式输出');
  };
</script>
```

**渲染效果**

<div class="demo">
  <div style="height: 300px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesBasic"
      :message-groups="groupsBasic"
      message-status="complete"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 消息分组机制

`MessageContainer` 在内部通过 `watchEffect` 将 `messages` 数组转换为消息组列表（`MessageGroup[]`）。分组规则如下：

```
┌─────────────────────────────────────────────────────────────┐
│  messages 原始数组（按顺序处理）                              │
└──────────────────────────────┬──────────────────────────────┘
                               │
              ┌────────────────┴────────────────┐
              │                                 │
        role === 'user'               role === 'tool'
              │                                 │
  ① 先把已累积的 assistantMessages    ② 通过 toolCallId 找到对应的
     推入 list 作为一组                  AssistantMessage，将 tool
  ② 当前 user 消息单独成一组           消息注入 toolCall.toolMessage，
                                        然后 continue（不单独渲染）
                               │
                   其他 role（assistant / reasoning /
                     activity / info / loading 等）
                               │
                    ③ 累积到 assistantMessages
                       等待 user 消息触发分组

    ④ 遍历结束后，将剩余 assistantMessages 推入 list
       每个 assistant 组计算 pause 字段：
       pause = assistantMessages.some(m => m.property?.extra?.pause)
    ⑤ 如果最后一条消息 role === 'user' → 追加 Loading 消息组
```

**关键细节**：

- 每个消息组外层 DOM 的 `id` 为 **`MessageGroup.uid`**（由 `useMessageGroup` 生成），供执行摘要「在对话中定位」、侧栏自定义 Tab 等场景滚动锚定
- `role: 'tool'` 消息**不会独立渲染**，而是被注入到对应 AssistantMessage 的 `toolCall.toolMessage` 字段
- 若 `toolMessage.error` 存在，AssistantMessage 的 `status` 会被强制设为 `MessageStatus.Error`
- 当消息组**最后一条**消息的 `role === 'interrupt'` 时，`mouseenter` **不会**设置 `isHover`，避免 AI 工具栏在审批卡片上误显
- `MessageTools` 工具栏只在 `type === 'assistant'` 的消息组底部渲染（不依赖鼠标悬停，始终可见），且满足以下条件时**不渲染**：
  - `renderMode === RenderMode.Share`（分享预览模式）
  - 消息组的 `pause` 为 `true`（来源于 `message.property?.extra?.pause`）
  - 多选模式（`enableSelection`）开启且消息组不是 Loading 类型
- `renderMode === RenderMode.Test` 时，工具栏会过滤掉「分享」按钮，其余正常
- `renderMode === RenderMode.Share` 时，`message-group-messages` 自动添加 `message-group-enabled-selection` 类名（与 `enableSelection: true` 一致的多选视觉效果）
- Loading 消息组的 `type` 是 `MessageRole.Loading`，不显示工具栏和多选 Checkbox

## 等待响应（Loading 自动注入）

当 `messages` 末尾为 `role: 'user'` 时，自动追加 Loading 消息组，展示 AI 正在处理的加载动画（`renderMode` 为 `Share` 时不追加，且 `MessageContainer` 会过滤 Loading 组）：

<div class="demo">
  <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">最后一条为 user 消息 → 自动显示 LoadingMessage</p>
  <div style="height: 200px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesLoading"
      :message-groups="groupsLoading"
      message-status="pending"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 流式输出与停止生成

当 `messageStatus` 为 `streaming`、`pending`（等待首包）或 `fetching`（请求中、与末尾 Loading 占位一致）时，底部固定区域显示「停止生成」按钮（`stop-loading` 时按钮展示为正在停止），点击后触发 `@stop-streaming` 事件。`renderMode` 为 `Share` 时不显示「停止生成」按钮。

点击下方按钮体验完整的流式输出过程：

<div class="demo">
  <div style="margin-bottom: 8px; display: flex; align-items: center; gap: 12px;">
    <button
      @click="startStreaming"
      :disabled="isStreamingRunning"
      style="padding: 4px 16px; border: 1px solid #3a84ff; border-radius: 4px; background: #3a84ff; color: #fff; cursor: pointer; font-size: 12px; line-height: 24px;"
      :style="{ opacity: isStreamingRunning ? 0.6 : 1, cursor: isStreamingRunning ? 'not-allowed' : 'pointer' }"
    >
      {{ isStreamingRunning ? '输出中...' : '开始流式输出' }}
    </button>
    <span style="font-size: 12px; color: #979ba5;">
      messageStatus = "{{ streamingStatus }}"
    </span>
  </div>
  <div style="height: 320px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesStreaming"
      :message-groups="groupsStreaming"
      :message-status="streamingStatus"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreamingDemo"
    />
  </div>
</div>

**流式输出完整示例**：

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="messageStatus"
    :on-agent-action="handleAgentAction"
    :on-agent-feedback="handleAgentFeedback"
    :on-user-action="handleUserAction"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageContainer, MessageRole, MessageStatus, type Message, type IToolBtn } from '@blueking/chat-x';

  const messageStatus = ref<MessageStatus>(MessageStatus.Complete);
  const messages = ref<Message[]>([]);

  const sendMessage = async (userInput: string) => {
    // 1. 推入用户消息
    messages.value.push({
      id: Date.now().toString(),
      messageId: Date.now().toString(),
      role: MessageRole.User,
      content: userInput,
      status: MessageStatus.Complete,
    });

    // 2. 推入空 assistant 消息（触发 Loading 消失）
    const assistantMsg: Message = {
      id: (Date.now() + 1).toString(),
      messageId: (Date.now() + 1).toString(),
      role: MessageRole.Assistant,
      content: '',
      status: MessageStatus.Pending,
    };
    messages.value.push(assistantMsg);
    messageStatus.value = MessageStatus.Streaming;

    // 3. 逐步追加流式内容
    for await (const chunk of fetchStream(userInput)) {
      assistantMsg.content += chunk;
      assistantMsg.status = MessageStatus.Streaming;
    }

    // 4. 标记完成
    assistantMsg.status = MessageStatus.Complete;
    messageStatus.value = MessageStatus.Complete;
  };

  const handleStopStreaming = () => {
    messageStatus.value = MessageStatus.Stop;
    const last = messages.value.at(-1);
    if (last) last.status = MessageStatus.Stop;
  };

  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面'];
    }
  };
  const handleAgentFeedback = (tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => {
    console.log('反馈:', tool.id, reasonList);
  };
  const handleUserAction = async (tool: IToolBtn, message: Message) => {};
</script>
```

## 错误状态

AI 回复状态为 `error` 时，消息以错误样式展示：

<div class="demo">
  <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">assistant status = "error"</p>
  <div style="height: 200px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesError"
      :message-groups="groupsError"
      message-status="complete"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 推理过程消息

`role: 'reasoning'` 消息会被归入当前 AI 消息组，带有折叠/展开效果和思考耗时展示：

```vue
<script setup lang="ts">
  const messages = ref<Message[]>([
    {
      id: '1',
      messageId: '1',
      role: MessageRole.User,
      content: '分析一下这段代码的问题',
      status: MessageStatus.Complete,
    },
    {
      id: '2',
      messageId: '2',
      role: MessageRole.Reasoning,
      content: ['首先，我需要理解代码意图...', '看起来是数据处理函数...', '发现几个潜在问题...'],
      status: MessageStatus.Complete,
      duration: 3500,
    },
    {
      id: '3',
      messageId: '3',
      role: MessageRole.Assistant,
      content: '根据分析，存在以下问题：\n\n1. 变量命名不规范...',
      status: MessageStatus.Complete,
    },
  ]);
</script>
```

**渲染效果**

<div class="demo">
  <div style="height: 380px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesReasoning"
      :message-groups="groupsReasoning"
      message-status="complete"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 工具调用消息

`role: 'tool'` 消息通过 `toolCallId` 与对应 AssistantMessage 关联，被注入到 `toolCall.toolMessage` 后不再独立渲染：

```vue
<script setup lang="ts">
  const messages = ref<Message[]>([
    { id: '1', messageId: '1', role: MessageRole.User, content: '查询北京天气', status: MessageStatus.Complete },
    {
      id: '2',
      messageId: '2',
      role: MessageRole.Assistant,
      content: '好的，我来帮你查询。',
      status: MessageStatus.Complete,
      toolCalls: [
        {
          id: 'call_weather',
          type: 'function',
          function: { name: 'get_weather', arguments: '{"city": "北京"}', description: '查询天气信息' },
        },
      ],
    },
    // role: 'tool' 消息通过 toolCallId 关联到上方 assistant 消息
    {
      id: '3',
      messageId: '3',
      role: MessageRole.Tool,
      content: '{"temperature":25,"weather":"晴天"}',
      status: MessageStatus.Complete,
      toolCallId: 'call_weather',
      duration: 1200,
    },
    {
      id: '4',
      messageId: '4',
      role: MessageRole.Assistant,
      content: '北京今天 **晴朗**，温度 **25°C**。',
      status: MessageStatus.Complete,
    },
  ]);
</script>
```

**渲染效果**

<div class="demo">
  <div style="height: 360px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesToolCall"
      :message-groups="groupsToolCall"
      message-status="complete"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## Activity 知识检索消息

`role: 'activity'` 消息同样被归入 AI 消息组，与 assistant 消息一起渲染：

<div class="demo">
  <div style="height: 380px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesActivity"
      :message-groups="groupsActivity"
      message-status="complete"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 多轮对话

连续多轮问答，组件按角色自动分组，每个 AI 组独立显示工具栏：

<div class="demo">
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesMultiRound"
      :message-groups="groupsMultiRound"
      message-status="complete"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 自定义消息工具栏

`messageTools`（左侧）与 `updateTools`（右侧反馈区）用于在**内置工具的基础上做增量定制**，无需重写整份列表。二者分别与内置 `CONST_MESSAGE_TOOLS`、`CONST_UPDATE_TOOLS` 按 `id` 合并，规则如下：

- **覆盖**：`id` 命中内置项时，做字段级浅合并（仅覆盖传入的字段，其余保留），不新增条目
- **追加**：`id` 为内置列表中不存在的新值时，追加到该组末尾（如自定义「保存」「收藏」按钮）
- **隐藏**：传入 `{ id: 'xxx', hidden: true }` 可移除对应内置项（如隐藏「分享」）
- **自定义图标**：通过 `icon`（组件/VNode）为自定义按钮提供图标，优先级高于内置 `ToolIconsMap`
- 不传 `messageTools` / `updateTools` 时，各自使用内置默认列表

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-groups="messageGroups"
    message-status="complete"
    :message-tools="customMessageTools"
    :update-tools="customUpdateTools"
    :on-agent-action="handleAgentAction"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { MessageContainer, DownloadIcon, type IToolBtn, type Message } from '@blueking/chat-x';

  const customMessageTools: IToolBtn[] = [
    { id: 'save', name: '保存', description: '保存该回答', icon: DownloadIcon }, // 追加新按钮
    { id: 'copy', description: '复制全文' }, // 覆盖内置 copy 的 description
    { id: 'share', hidden: true }, // 隐藏内置「分享」
  ];
  const customUpdateTools: IToolBtn[] = [
    { id: 'collect', name: '收藏', description: '收藏到我的空间', icon: DownloadIcon },
  ];

  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    if (tool.id === 'save') {
      // 处理保存
    }
  };
</script>
```

> **合并优先级**：`RenderMode.Test` 下仍会额外过滤掉「分享」按钮（即便合并后存在）；即测试模式对 `share` 的过滤在自定义合并之后生效。

## 工具栏状态控制

通过 `messageToolsStatus` 控制消息工具栏的显示状态。常见用法：流式输出期间禁用工具栏：

```vue
<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { MessageContainer, MessageStatus, MessageToolsStatus } from '@blueking/chat-x';

  const messageStatus = ref(MessageStatus.Complete);

  // 流式输出期间禁用工具栏，完成后恢复
  const messageToolsStatus = computed(() =>
    messageStatus.value === MessageStatus.Streaming ? MessageToolsStatus.Disabled : undefined,
  );
</script>
```

**三种状态对比**

<div class="demo" style="display: flex; gap: 16px;">
  <div style="flex: 1;">
    <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">undefined（默认，正常可用）</p>
    <div style="height: 200px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
      <MessageContainerComp
        :messages="messagesBasic"
        :message-groups="groupsBasic"
        message-status="complete"
        :on-agent-action="handleAgentAction"
        :on-agent-feedback="handleAgentFeedback"
        :on-user-action="handleUserAction"
        @stop-streaming="handleStopStreaming"
      />
    </div>
  </div>
  <div style="flex: 1;">
    <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">"disabled"（按钮不可点击）</p>
    <div style="height: 200px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
      <MessageContainerComp
        :messages="messagesBasic"
        :message-groups="groupsBasic"
        message-status="complete"
        message-tools-status="disabled"
        :on-agent-action="handleAgentAction"
        :on-agent-feedback="handleAgentFeedback"
        :on-user-action="handleUserAction"
        @stop-streaming="handleStopStreaming"
      />
    </div>
  </div>
  <div style="flex: 1;">
    <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">"hidden"（工具栏完全隐藏）</p>
    <div style="height: 200px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
      <MessageContainerComp
        :messages="messagesBasic"
        :message-groups="groupsBasic"
        message-status="complete"
        message-tools-status="hidden"
        :on-agent-action="handleAgentAction"
        :on-agent-feedback="handleAgentFeedback"
        :on-user-action="handleUserAction"
        @stop-streaming="handleStopStreaming"
      />
    </div>
  </div>
</div>

| 状态值      | 说明                           |
| ----------- | ------------------------------ |
| `undefined` | 默认，工具栏正常可用           |
| `disabled`  | 工具栏显示但所有按钮不可点击   |
| `hidden`    | 工具栏（`MessageTools`）不渲染 |

> **注意**：`messageToolsStatus` 同时透传给 `MessageRender`，控制用户消息中编辑、删除等按钮的状态。

## 消息多选

启用 `enableSelection` 后，每个消息组前显示 Checkbox，选中状态联动关联：

```vue
<template>
  <MessageContainer
    v-model:selected-user-messages="selectedUserMessages"
    :messages="messages"
    :message-status="messageStatus"
    :enable-selection="true"
    :on-agent-action="handleAgentAction"
    :on-user-action="handleUserAction"
    @stop-streaming="handleStopStreaming"
  />
  <div v-if="selectedUserMessages.length > 0">
    已选择 {{ selectedUserMessages.length }} 条消息
    <button @click="selectedUserMessages = []">清空选择</button>
  </div>
</template>
```

**多选特性**：

- `v-model:selected-user-messages` 仅包含选中的用户消息
- 选中用户消息组 → 其后紧邻的 AI 回复组视觉联动选中
- 选中 AI 回复组 → 其前紧邻的用户消息组联动选中
- 取消任一关联组 → 另一组同时取消
- 选中时消息组背景色变为 `#f5f7fa`
- 多选模式下用户消息工具栏自动隐藏
- Loading 消息组不显示 Checkbox

**渲染效果**（点击 Checkbox 体验多选）

<div class="demo">
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesMultiRound"
      :message-groups="groupsMultiRound"
      message-status="complete"
      :enable-selection="true"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 自定义消息组渲染

使用 `#group` 插槽可替换单个消息组的默认内容（Checkbox、消息列表、`MessageTools`）。外层 `.message-group` 容器（含 `id`、hover 状态、选中背景色）仍由 `MessageContainer` 管理。

> **注意**：提供 `#group` 后需自行编排组内全部 UI；若只需替换单条消息，请使用 `#default` 插槽。

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-groups="messageGroups"
    message-status="complete"
    :on-agent-action="handleAgentAction"
    @stop-streaming="handleStopStreaming"
  >
    <template #group="{ group }">
      <div class="custom-group">
        <span class="custom-group-label">{{ group.type }}</span>
        <div
          v-for="message in group.messages"
          :key="message.id"
          class="custom-group-message"
        >
          {{ typeof message.content === 'string' ? message.content : JSON.stringify(message.content) }}
        </div>
      </div>
    </template>
  </MessageContainer>
</template>
```

**渲染效果**（简化自定义组布局，不含默认 Checkbox 与工具栏）

<div class="demo">
  <div style="height: 300px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <MessageContainerComp
      :messages="messagesBasic"
      :message-groups="groupsBasic"
      message-status="complete"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    >
      <template #group="{ group }">
        <div style="display: flex; flex-direction: column; gap: 8px; width: 100%;">
          <span style="font-size: 12px; color: #979ba5;">{{ group.type }}</span>
          <div
            v-for="message in group.messages"
            :key="message.id"
            style="padding: 8px 12px; background: #f5f7fa; border-radius: 4px; font-size: 13px;"
          >
            {{ typeof message.content === 'string' ? message.content.slice(0, 80) + (message.content.length > 80 ? '…' : '') : JSON.stringify(message.content) }}
          </div>
        </div>
      </template>
    </MessageContainerComp>
  </div>
</div>

## 自定义消息渲染

使用默认插槽替换单条消息的渲染，插槽参数包含 `message`、`messageToolsStatus` 和 `onInterruptResume`：

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="messageStatus"
    :on-agent-action="handleAgentAction"
    :on-user-action="handleUserAction"
    @stop-streaming="handleStopStreaming"
  >
    <template #default="{ message, messageToolsStatus, onInterruptResume }">
      <MyCustomMessage
        :message="message"
        :message-tools-status="messageToolsStatus"
        :on-interrupt-resume="onInterruptResume"
      />
    </template>
  </MessageContainer>
</template>
```

> 使用默认插槽后，每条消息由自定义组件完全接管渲染，但**消息分组逻辑和工具栏（`MessageTools`）仍由 `MessageContainer` 管理**。

## 自定义工具栏 Tooltip 配置

通过 `messageToolsTippyOptions` 可以自定义消息工具栏中按钮 tooltip 的 Tippy 配置，透传给所有 `ToolBtn`。典型用法是修改 `appendTo` 避免 tooltip 被父容器 `overflow: hidden` 遮挡：

```vue
<template>
  <!-- tooltip 挂载到触发元素的父节点，避免被滚动容器裁剪 -->
  <MessageContainer
    :messages="messages"
    :message-tools-tippy-options="{ appendTo: 'parent' }"
    :on-agent-action="handleAgentAction"
    @stop-streaming="handleStopStreaming"
  />
</template>
```

> **注意**：`content`、`getReferenceClientRect`、`triggerTarget` 三个字段被排除，不可通过此 prop 覆盖。

## 用户消息编辑与快捷指令

通过 `onUserInputConfirm` 和 `onUserShortcutConfirm` 处理用户消息的编辑确认和快捷指令表单提交：

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="messageStatus"
    :on-agent-action="handleAgentAction"
    :on-user-action="handleUserAction"
    :on-user-input-confirm="handleUserInputConfirm"
    :on-user-shortcut-confirm="handleUserShortcutConfirm"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { MessageContainer, type Message, type TagSchema } from '@blueking/chat-x';

  // 用户点击编辑并确认时触发
  const handleUserInputConfirm = async (message: Message, content: UserMessage['content'], docSchema: TagSchema) => {
    // message: 原始消息对象
    // content: 编辑后的内容（字符串或富文本结构）
    // docSchema: 引用文档结构
    console.log('用户编辑确认:', message.id, content);
  };

  // 用户提交快捷指令表单时触发
  const handleUserShortcutConfirm = async (message: Message, formModel: Record<string, unknown>) => {
    console.log('快捷指令提交:', message.id, formModel);
  };
</script>
```

## copy 操作内置处理

`MessageContainer` 内部对 `copy` 工具操作进行了特殊处理：当 `tool.id === 'copy'` 时，自动将当前消息组中所有**非 reasoning 消息**的内容拼接后复制到剪贴板，**无需在 `onAgentAction` 中自行实现**。

其他工具操作（`like`、`unlike`、`cite` 等）仍正常转发给 `onAgentAction` 回调。

## 滚动控制

底部固定区域（`position: sticky; bottom: 12px`）根据条件显示两个按钮：

| 按钮         | 显示条件                                                                                       | 点击行为               |
| ------------ | ---------------------------------------------------------------------------------------------- | ---------------------- |
| 「停止生成」 | `messageStatus` 为 `streaming`、`pending`、`fetching` 或 `stop-loading`（停止中 loading 态），且 `renderMode` 不为 `Share` | 触发 `@stop-streaming` |
| 「返回底部」 | `debouncedShowScrollBottomBtn`（距底部 > 100px，且防抖 300ms 后才显示/隐藏）                     | 滚动到消息列表底部     |

> **防抖说明**：「返回底部」按钮的显隐使用 300ms 防抖，避免快速滚动时按钮频繁闪烁。隐藏时立即生效（无防抖），显示时延迟 300ms。

## API

### Props

| 属性名                   | 类型                                                                                         | 默认值  | 说明                                                                                                                                     |
| ------------------------ | -------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| messages                 | `Message[]`                                                                                  | —       | **必填**，消息列表                                                                                                                       |
| messageGroups            | `MessageGroup[]`                                                                             | —       | 预计算的消息分组；传入时跳过内部分组逻辑，由 `ChatContainer` 通过 `useMessageGroup` 提供                                                 |
| messageStatus            | `MessageStatus`                                                                              | —       | 当前整体消息状态，控制底部「停止生成」按钮显示；`ChatContainer` 会结合末尾 Loading 占位推导 `fetching` 等再传入                                                                                                   |
| messageTools             | `IToolBtn[]`                                                                                 | —       | AI 消息左侧工具（复制/引用等）的自定义配置；按 `id` 与内置 `CONST_MESSAGE_TOOLS` 合并（覆盖同 id、追加新 id、`hidden` 过滤），详见「自定义消息工具栏」 |
| updateTools              | `IToolBtn[]`                                                                                 | —       | AI 消息右侧反馈工具（点赞/踩/删除等）的自定义配置；按 `id` 与内置 `CONST_UPDATE_TOOLS` 合并，规则同上                                     |
| messageToolsStatus       | `MessageToolsStatus`                                                                         | —       | 工具栏状态，透传给 `MessageTools` 和 `MessageRender`                                                                                     |
| messageToolsTippyOptions | `AITippyProps`                                                                               | —       | 透传给 `MessageTools` 和 `MessageRender`（进而透传给 `UserMessage` 的工具栏）的 Tippy 配置，用于自定义 tooltip 挂载点、位置等（如 `appendTo`、`placement`、`zIndex`） |
| enableSelection          | `boolean`                                                                                    | `false` | 是否启用多选模式                                                                                                                         |
| onAgentAction            | `(tool: IToolBtn, messages: Message[]) => Promise<string[] \| void>`                         | —       | AI 消息工具操作回调；`copy` 操作由内部处理，`like/unlike` 应返回反馈原因字符串数组                                                       |
| onAgentFeedback          | `(tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => void`   | —       | AI 消息反馈提交回调（点赞/踩选完原因后触发）                                                                                             |
| onUserAction             | `(tool: IToolBtn, message: Message) => Promise<string[] \| void>`                            | —       | 用户消息工具操作回调                                                                                                                     |
| onUserInputConfirm       | `(message: Message, content: UserMessage['content'], docSchema: TagSchema) => Promise<void>` | —       | 用户编辑消息确认回调                                                                                                                     |
| onUserShortcutConfirm    | `(message: Message, formModel: Record<string, unknown>) => Promise<void>`                    | —       | 用户快捷指令表单提交回调                                                                                                                 |
| onInterruptResume        | `OnInterruptResume`                                                                          | —       | AG-UI human-in-the-loop 中断响应回调，透传给 `MessageRender` → `InterruptMessageRender`                                                  |
| renderMode               | `RenderMode`                                                                                 | —       | 渲染模式。`Share` 模式下启用多选样式并隐藏工具栏与「停止生成」按钮；`Test` 模式下过滤掉「分享」按钮；不传或 `Chat` 为默认行为                              |

### v-model

| 属性名               | 类型        | 说明                                               |
| -------------------- | ----------- | -------------------------------------------------- |
| selectedUserMessages | `Message[]` | 当前选中的用户消息列表（双向绑定，仅包含用户消息） |

### Events

| 事件名        | 参数 | 说明                       |
| ------------- | ---- | -------------------------- |
| stopStreaming | —    | 点击「停止生成」按钮时触发 |

### Slots

| 插槽名           | 参数                                                                                                        | 说明                                                                                     |
| ---------------- | ----------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| answeredQuestion | `{ item, index, status }`                                                                                   | 自定义 UserQuestion 已回答回显，透传给 MessageRender → InterruptMessageRender            |
| default          | `{ message: Message, messageToolsStatus?: MessageToolsStatus, onInterruptResume?: OnInterruptResume }`     | 自定义单条消息渲染；消息分组外层容器与 `#group` 未覆盖时的工具栏仍由容器管理             |
| group            | `{ group: MessageGroup }`                                                                                   | 自定义单个消息组内容，替换默认 Checkbox、消息列表与 `MessageTools`；外层组容器仍由组件管理 |

## 类型定义

```typescript
import { MessageRole, MessageStatus, MessageToolsStatus, type Message, type MessageGroup, type IToolBtn } from '@blueking/chat-x';

// 消息组（由 useMessageGroup 生成，也可手动传入 messageGroups）
interface MessageGroup {
  checked: boolean;
  isHover: boolean;
  messages: Message[];
  pause?: boolean;
  startTime?: number;
  type: MessageRole;
  uid: string;
  userMessageTitle?: number | string;
}

// onAgentAction 回调类型
// messages 为当前消息组全部消息（可含 reasoning / activity 等）
// 返回 string[] 时用作 like/unlike 的反馈原因列表
type AgentActionCallback = (tool: IToolBtn, messages: Message[]) => Promise<string[] | void>;

// onAgentFeedback 回调类型
type AgentFeedbackCallback = (tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => void;

// onUserAction 回调类型
type UserActionCallback = (tool: IToolBtn, message: Message) => Promise<string[] | void>;

// 工具栏状态
enum MessageToolsStatus {
  Disabled = 'disabled',
  Hidden = 'hidden',
}

// 消息角色 / 消息状态完整枚举见常量文档，勿在此维护副本
// MessageRole、MessageStatus → ../../types/constants
```

> `MessageRole` / `MessageStatus` 完整取值见 [常量枚举](../../types/constants)。

## 关联组件

- [MessageRender](/components/message/message-render) — 按组渲染每条消息时委托使用
- [InterruptMessage 中断消息](/components/agent/interrupt-message) — `role: 'interrupt'` 的渲染与 `onInterruptResume` 透传
- [ChatInput](/components/input/chat-input) — 常与输入区组合构成完整对话界面
- [LoadingMessage](/components/message/loading-message) — 末尾为用户消息时自动追加加载组
