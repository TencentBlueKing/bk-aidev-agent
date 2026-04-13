---
name: ChatContainer 聊天容器
slug: chat-container
category: molecular
description: >-
  顶层聊天容器组件，整合了
  `MessageContainer`（消息列表）、`ChatInput`（输入框）、`ExecutionSummary`（执行摘要面板）、`ShortcutRender`（快捷指令表单）和
  `SelectionFooter`（多选操作栏）。提供完整的 AI 对话界面布局能力。
aiSummary: >
  ChatContainer 提供完整 AI 对话布局：分栏（ResizeLayout）、消息列表（MessageContainer）、输入（ChatInput）、执行摘要（ExecutionSummary）、快捷表单（ShortcutRender）与多选栏（SelectionFooter）。
  内置 useMessageGroup、分享与自定义 Tab 等能力，适合一站式接入。
  通过 props 传入 messages、shortcuts 等，事件与 ChatInput/MessageContainer 对齐。
relatedComponents:
  - slug: message-container
    relation: 消息列表与滚动区域
  - slug: chat-input
    relation: 对话输入与快捷指令入口
  - slug: shortcut-render
    relation: 快捷指令表单浮层
  - slug: execution-summary
    relation: 执行摘要侧栏与定位
  - slug: selection-footer
    relation: 多选分享底部操作栏
sinceVersion: 1.0.0
domain: input
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import ChatContainerComp from '../../../src/components/chat-container/chat-container.vue'

  const inputBasic = ref('');
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
      content: '当然，以用户管理为例：\n\n```typescript\nimport { ref, onMounted } from \'vue\';\n\nconst users = ref([]);\n\nonMounted(async () => {\n  users.value = await fetchUsers();\n});\n```\n\n使用 `ref` 创建响应式状态，`onMounted` 中发起请求，模板自动更新。',
      status: 'complete',
    },
  ]);

  const inputEmpty = ref('');

  const inputToolCall = ref('');
  const inputToolCallRight = ref('');
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

  const chatLoading = ref(true);
  const inputLoading = ref('');

  const inputStreaming = ref('');
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

  const inputShare = ref('');

  const handleSendMessage = async (content, docSchema) => {
    console.log('发送消息:', content);
  };
  const handleStopSending = async () => {
    console.log('停止发送');
  };
  const handleAgentAction = async (tool, messages) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面', '表达清晰'];
    }
  };
  const handleAgentFeedback = (tool, messages, reasonList, otherReason) => {
    console.log('反馈:', tool.id, reasonList, otherReason);
  };
  const handleUserAction = async (tool, message) => {
    console.log('用户操作:', tool.id);
  };
  const handleStopStreaming = () => {
    console.log('停止流式输出');
  };
  const handleConfirmShare = (selectedMessages) => {
    console.log('分享消息:', selectedMessages);
  };
</script>

# ChatContainer 聊天容器

> **层级**：分子组件 · **功能域**：输入交互

顶层聊天容器组件，整合了 `MessageContainer`（消息列表）、`ChatInput`（输入框）、`ExecutionSummary`（执行摘要面板）、`ShortcutRender`（快捷指令表单）和 `SelectionFooter`（多选操作栏）。提供完整的 AI 对话界面布局能力。

## 核心能力

- **分栏布局**：基于 `ResizeLayout` 的可拖拽分栏，侧边栏展示执行摘要 / 自定义 Tab
- **消息分组**：内置 `useMessageGroup` 自动处理消息分组、Tool 合并、Loading 注入
- **执行摘要**：侧边栏展示工具调用 / FlowAgent 执行记录，支持关键词搜索和对话定位
- **自定义 Tab**：通过 `useCustomTabProvider` 支持动态添加自定义 Tab（如节点详情）
- **分享模式**：内置消息多选分享流程，选中用户消息后确认分享
- **空状态欢迎页**：无消息时展示欢迎语和开场白

## 组件结构

```
ai-chat-container
├── Loading（chatLoading 时）
└── ResizeLayout
    ├── aside（侧边栏）
    │   ├── Tab 标签页
    │   │   ├── 执行情况（默认 Tab）
    │   │   └── 自定义 Tab × N（可关闭）
    │   ├── ExecutionSummary（执行情况 Tab 内容）
    │   ├── 自定义 Tab 组件（通过 component :is 渲染）
    │   └── collapse-button（折叠按钮）
    └── main（主内容区）
        ├── MessageContainer（有消息时）
        │   └── 消息列表 + 工具栏
        ├── 欢迎页（无消息时，容器 .ai-welcome-content）
        │   └── welcome 插槽（默认：Banner + 欢迎标题 + 开场白 ContentRender；自定义则整块替换）
        ├── SelectionFooter（分享模式时）
        ├── ShortcutRender（有快捷指令时）
        └── ChatInput（默认状态）
```

## 基础用法

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="messages"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
    :on-agent-action="handleAgentAction"
    :on-agent-feedback="handleAgentFeedback"
    :on-user-action="handleUserAction"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatContainer, MessageStatus, type Message, type IToolBtn, type TagSchema } from '@blueking/chat-x';

  const inputValue = ref('');
  const messageStatus = ref(MessageStatus.Complete);
  const messages = ref<Message[]>([]);

  const handleSendMessage = async (content: string, docSchema: TagSchema) => {
    messageStatus.value = MessageStatus.Streaming;
    // ... 发送 AI 请求
    messageStatus.value = MessageStatus.Complete;
  };
  const handleStopSending = async () => {
    messageStatus.value = MessageStatus.Stop;
  };
  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面', '表达清晰'];
    }
  };
  const handleAgentFeedback = (tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => {
    console.log('反馈:', tool.id, reasonList, otherReason);
  };
  const handleUserAction = async (tool: IToolBtn, message: Message) => {
    console.log('用户操作:', tool.id);
  };
  const handleStopStreaming = () => {
    messageStatus.value = MessageStatus.Stop;
  };
</script>
```

**渲染效果**

<div class="demo">
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputBasic"
      :messages="messagesBasic"
      message-status="complete"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

## 侧边栏与执行摘要

侧边栏默认包含「执行情况」Tab，展示所有工具调用和 FlowAgent 类型的 Activity 消息。支持关键词搜索过滤和点击定位到对话中的消息位置。

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="messages"
    :message-status="messageStatus"
    placement="left"
    :on-send-message="handleSendMessage"
    :on-agent-action="handleAgentAction"
    @stop-streaming="handleStopStreaming"
    @collapse-change="handleCollapseChange"
  />
</template>

<script setup lang="ts">
  const handleCollapseChange = (isCollapse: boolean, resizeAsideWidth: number) => {
    console.log('侧边栏折叠:', isCollapse, '宽度:', resizeAsideWidth);
  };
</script>
```

**渲染效果**（包含工具调用消息时，侧边栏自动展示「执行情况」）

<div class="demo">
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputToolCall"
      :messages="messagesToolCall"
      message-status="complete"
      placement="left"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

侧边栏放置方向通过 `placement` 控制：

| `placement` | 侧边栏位置   | 折叠按钮位置 |
| ----------- | ------------ | ------------ |
| `left`      | 左侧（默认） | 主区域左边缘 |
| `right`     | 右侧         | 主区域右边缘 |

**placement 对比**（左右两种布局）

<div class="demo" style="display: flex; gap: 16px;">
  <div style="flex: 1;">
    <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">placement = "left"（默认）</p>
    <div style="height: 400px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
      <ChatContainerComp
        v-model="inputToolCall"
        :messages="messagesToolCall"
        message-status="complete"
        placement="left"
        :on-send-message="handleSendMessage"
        :on-stop-sending="handleStopSending"
        :on-agent-action="handleAgentAction"
        :on-agent-feedback="handleAgentFeedback"
        :on-user-action="handleUserAction"
        @stop-streaming="handleStopStreaming"
      />
    </div>
  </div>
  <div style="flex: 1;">
    <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">placement = "right"</p>
    <div style="height: 400px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
      <ChatContainerComp
        v-model="inputToolCallRight"
        :messages="messagesToolCall"
        message-status="complete"
        placement="right"
        :on-send-message="handleSendMessage"
        :on-stop-sending="handleStopSending"
        :on-agent-action="handleAgentAction"
        :on-agent-feedback="handleAgentFeedback"
        :on-user-action="handleUserAction"
        @stop-streaming="handleStopStreaming"
      />
    </div>
  </div>
</div>

## 自定义 Tab

通过 `ref` 获取组件实例后，使用 `addCustomTab` / `removeCustomTab` 动态管理侧边栏 Tab：

```vue
<template>
  <ChatContainer
    ref="chatContainerRef"
    v-model="inputValue"
    :messages="messages"
    :message-status="messageStatus"
    :on-custom-tab-change="handleCustomTabChange"
    :on-send-message="handleSendMessage"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { useTemplateRef } from 'vue';
  import { ChatContainer, type CustomTab } from '@blueking/chat-x';

  const chatContainerRef = useTemplateRef<InstanceType<typeof ChatContainer>>('chatContainerRef');

  // 添加自定义 Tab（如 FlowAgent 节点详情）
  const addNodeDetailTab = (nodeId: string, nodeName: string) => {
    chatContainerRef.value?.addCustomTab({
      name: `node-${nodeId}`,
      label: nodeName,
      data: {
        component: MyNodeDetail, // 自定义组件
        props: { loading: true, data: {} },
      },
    });
  };

  // Tab 切换时加载数据
  const handleCustomTabChange = async (tab: CustomTab) => {
    const data = await fetchTabData(tab.name);
    return data;
  };
</script>
```

## 开场白

无消息时展示欢迎页，通过 `openingRemark` 设置开场白内容（支持 Markdown）：

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="[]"
    :message-status="messageStatus"
    opening-remark="你好！我是 AI 小鲸 🐳，可以帮你：\n\n- 编写和优化代码\n- 解答技术问题\n- 分析和调试错误"
    :on-send-message="handleSendMessage"
  />
</template>
```

### 自定义欢迎内容

通过 `welcome` 插槽可完全自定义欢迎页内容，插槽参数 `openingRemark` 为传入的开场白文本：

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="[]"
    :message-status="messageStatus"
    opening-remark="欢迎使用 AI 助手"
    :on-send-message="handleSendMessage"
  >
    <template #welcome="{ openingRemark }">
      <div class="my-welcome">
        <h3>{{ openingRemark }}</h3>
        <div class="quick-actions">
          <button @click="handleQuickAction('code')">写代码</button>
          <button @click="handleQuickAction('debug')">调试</button>
          <button @click="handleQuickAction('explain')">解释</button>
        </div>
      </div>
    </template>
  </ChatContainer>
</template>
```

> **注意**：使用 `welcome` 插槽后，将**整块替换**默认欢迎区（含 Banner 图标、默认欢迎标题与 `openingRemark` 的 `ContentRender` 渲染），需自行编排完整欢迎页；插槽参数 `openingRemark` 仍可用于读取传入的开场白文本。

**渲染效果**

<div class="demo">
  <div style="height: 400px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputEmpty"
      :messages="[]"
      message-status="complete"
      opening-remark="你好！我是 AI 小鲸，可以帮你：\n\n- 编写和优化代码\n- 解答技术问题\n- 分析和调试错误"
      :on-send-message="handleSendMessage"
    />
  </div>
</div>

## 加载状态

`chatLoading` 为 `true` 时，整个容器显示 Loading 遮罩，适用于初始化加载场景（如拉取历史消息）：

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="[]"
    :chat-loading="true"
  />
</template>
```

**渲染效果**

<div class="demo">
  <div style="display: flex; gap: 16px;">
    <div style="flex: 1;">
      <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">chatLoading = true</p>
      <div style="height: 300px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
        <ChatContainerComp
          v-model="inputLoading"
          :messages="[]"
          :chat-loading="true"
        />
      </div>
    </div>
    <div style="flex: 1;">
      <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">chatLoading = false（正常状态）</p>
      <div style="height: 300px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
        <ChatContainerComp
          v-model="inputLoading"
          :messages="[]"
          :chat-loading="false"
          opening-remark="加载完成，可以开始对话了"
          :on-send-message="handleSendMessage"
        />
      </div>
    </div>
  </div>
</div>

## 流式输出

`messageStatus` 为 `streaming` 时，底部固定区域显示「停止生成」按钮，点击后触发 `@stop-streaming` 事件：

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
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputStreaming"
      :messages="messagesStreaming"
      :message-status="streamingStatus"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @stop-streaming="handleStopStreamingDemo"
    />
  </div>
</div>

## 分享模式

点击消息工具栏的「分享」按钮后进入分享模式，底部出现 `SelectionFooter` 操作栏：

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="messages"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
    :on-agent-action="handleAgentAction"
    @confirm-share="handleConfirmShare"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { type Message } from '@blueking/chat-x';

  const handleConfirmShare = (selectedMessages: Message[]) => {
    console.log('分享消息:', selectedMessages);
  };
</script>
```

**渲染效果**（点击 AI 回复工具栏中的「分享」按钮进入多选模式）

<div class="demo">
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputShare"
      :messages="messagesBasic"
      message-status="complete"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @confirm-share="handleConfirmShare"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

**分享流程**：

1. 用户点击消息工具栏中的「分享」按钮
2. 进入多选模式，用户勾选要分享的消息
3. 底部 `SelectionFooter` 提供全选、取消、确认操作
4. 确认后触发 `confirmShare` 事件，携带选中的消息列表

## 快捷指令

通过 `v-model:selectedShortcut` 管理快捷指令选中状态：

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    v-model:selected-shortcut="selectedShortcut"
    :messages="messages"
    :message-status="messageStatus"
    :shortcuts="shortcuts"
    :on-send-message="handleSendMessage"
    @shortcut-close="handleShortcutClose"
    @shortcut-submit="handleShortcutSubmit"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { type Shortcut } from '@blueking/chat-x';

  const selectedShortcut = ref<Shortcut | null>(null);

  const handleShortcutClose = () => {
    selectedShortcut.value = null;
  };
  const handleShortcutSubmit = (formModel: Record<string, unknown>) => {
    console.log('快捷指令提交:', formModel);
  };
</script>
```

## API

### Props

ChatContainer 的 Props 继承自 `ChatInputProps` 和 `MessageContainerProps`（排除 `enableSelection` 和 `messageGroups`），另外新增：

| 属性名             | 类型                                                                         | 默认值   | 说明                                                                                                                                          |
| ------------------ | ---------------------------------------------------------------------------- | -------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| chatLoading        | `boolean`                                                                    | —        | 整体加载状态，`true` 时显示 Loading 遮罩                                                                                                      |
| commonTippyOptions | `AITippyProps`                                                               | —        | 通用 Tippy 配置，传入的选项会注入到所有使用 `v-overflow-tips` 的子组件中                                                                      |
| openingRemark      | `string`                                                                     | —        | 开场白，无消息时显示，支持 Markdown                                                                                                           |
| placement          | `'left' \| 'right'`                                                          | `'left'` | 侧边栏位置                                                                                                                                    |
| resizeProps        | `{ disabled?: boolean; initialDivide?: number \| string; max?: number; min?: number }` | —        | 透传给内部 `ResizeLayout` 的可选配置，与默认 `collapsible: false`、`immediate: true`、`min: 400` 合并；`placement` 始终取自本组件 `placement`；`initialDivide` 可为像素数字或百分比等字符串（与 bkui ResizeLayout 一致） |
| onCustomTabChange  | `(tab: CustomTab) => Promise<any>`                                           | —        | 自定义 Tab 切换回调，返回值作为 Tab 组件 props                                                                                                |

> 完整 Props 列表请参考 [ChatInput](./chat-input.md) 和 [MessageContainer](./message-container.md) 文档。

### v-model

| 属性名           | 类型                  | 说明                             |
| ---------------- | --------------------- | -------------------------------- |
| modelValue       | `string \| TagSchema` | 输入框内容，支持纯文本或标签结构 |
| selectedShortcut | `Shortcut \| null`    | 当前选中的快捷指令               |
| cite             | `string`              | 引用内容                         |

### Events

| 事件名         | 参数                                   | 说明                                 |
| -------------- | -------------------------------------- | ------------------------------------ |
| stopStreaming  | —                                      | 点击「停止生成」按钮                 |
| shortcutClose  | —                                      | 关闭快捷指令表单                     |
| shortcutSubmit | `(formModel: Record<string, unknown>)` | 提交快捷指令表单                     |
| confirmShare   | `(messages: Message[])`                | 确认分享，携带选中的消息             |
| collapseChange | `(isCollapse: boolean, width: number)` | 侧边栏折叠/展开状态变化              |
| selectShortcut | `(shortcut: Shortcut)`                 | 选择快捷指令（继承自 ChatInput）     |
| deleteShortcut | `(shortcut: Shortcut)`                 | 删除已选快捷指令（继承自 ChatInput） |

### Slots

| 插槽名     | 参数                                   | 说明                                                                                           |
| ---------- | -------------------------------------- | ---------------------------------------------------------------------------------------------- |
| codeHeader | `{ language: string; token: Token[] }` | 代码块头部自定义操作区域，透传给 MessageRender → ContentRender → MarkdownContent → CodeContent |
| default    | 消息列表相关绑定（messages 等）        | 自定义消息列表区域                                                                             |
| message    | `{ message, messageToolsStatus }`      | 自定义单条消息渲染                                                                             |
| welcome    | `{ openingRemark: string }`            | 无消息时自定义欢迎页；传入则替换默认 Banner、标题与开场白区域（整块替换）                      |

### Expose

| 方法/属性名     | 类型                        | 说明           |
| --------------- | --------------------------- | -------------- |
| selectedTab     | `Ref<CustomTab>`            | 当前选中的 Tab |
| addCustomTab    | `(tab: CustomTab) => void`  | 添加自定义 Tab |
| removeCustomTab | `(tabName: string) => void` | 移除自定义 Tab |
| selectCustomTab | `(tab: CustomTab) => void`  | 切换到指定 Tab |

## 类型定义

```typescript
import { ChatContainer, type CustomTab, type Shortcut, type Message } from '@blueking/chat-x';

// 自定义 Tab
interface CustomTab<T = Record<string, unknown>> {
  label: string;
  name: string;
  data?: T;
}

// 快捷指令
interface Shortcut {
  id: string;
  name: string;
  components?: ShortcutComponent[];
}
```

## 关联组件

- [MessageContainer](./message-container.md) — 消息列表区域
- [ChatInput](./chat-input.md) — 输入与快捷指令
- [ShortcutRender](./shortcut-render.md) — 快捷指令表单
- [ExecutionSummary](./execution-summary.md) — 执行摘要侧栏
- [SelectionFooter](../atomic/selection-footer.md) — 多选操作栏
