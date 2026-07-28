---
name: ChatContainer 聊天容器
slug: chat-container
kind: component
domain: setup
description: 完整对话容器，组合消息列表、输入区、模型选择、快捷指令、执行摘要、分享选择和自定义 Tab。
aiSummary: >
  完整对话容器，组合消息列表、输入区、模型选择、快捷指令、执行摘要、分享选择和自定义 Tab。
  透传 models / selectedModel；支持 welcomeTitle 与 #welcome。
  源码位置：src/components/chat-container/chat-container.vue。
relatedComponents:
  - slug: message-container
    relation: 消息列表与滚动区域
  - slug: chat-input
    relation: 对话输入与快捷指令入口
  - slug: model-selector
    relation: 透传 models / selectedModel，在输入区展示模型选择器
  - slug: shortcut-render
    relation: 快捷指令表单浮层
  - slug: execution-summary
    relation: 执行摘要侧栏与定位
  - slug: selection-footer
    relation: 多选分享底部操作栏
sinceVersion: 1.0.0
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import ChatContainerComp from '../../../src/components/chat-container/chat-container.vue'
  import { APPROVAL_STATUS, InterruptReason, MessageRole, MessageStatus } from '../../../src/ag-ui/types/constants'

  const inputBasic = ref('');
  const inputModel = ref('');
  const selectedModelId = ref('GPT-4');
  const models = [
    { id: 1, llm_name: 'GPT-4', property: { support_thinking: true } },
    { id: 2, llm_name: 'Claude 3', property: { support_thinking_quick: true } },
    { id: 3, llm_name: 'DeepSeek', property: { support_vision: true } },
  ];
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
  const inputSizeNormal = ref('');
  const inputSizeSmall = ref('');
  const inputApproval = ref('');
  const messagesApproval = ref([
    {
      id: 'approval-user',
      messageId: 'approval-user',
      role: MessageRole.User,
      content: '请提交算法方案评审',
      status: MessageStatus.Complete,
    },
    {
      id: 'approval-interrupt',
      messageId: 'approval-interrupt',
      role: MessageRole.Interrupt,
      status: MessageStatus.Pending,
      content: {
        message: '算法方案评审单需要您关注',
        outcome: {
          type: 'interrupt',
          interrupts: [
            {
              id: 'interrupt_approval_demo',
              reason: InterruptReason.AIDevToolApproval,
              toolCallId: 'tool_call_approval_demo',
              metadata: {
                ticket: {
                  approvers: ['张三', '李四'],
                  sn: 'REV-2026-05-26-001',
                  status: APPROVAL_STATUS.PENDING,
                  submit_time: '2026-05-26 16:00:00',
                  title: '算法方案评审单',
                  url: 'https://example.com/review-tickets/REV-2026-05-26-001',
                },
              },
            },
          ],
        },
      },
    },
  ]);

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
  const handleInterruptResume = async (payload, interrupt) => {
    console.log('处理中断:', payload, interrupt.id);
  };
  const handleModelChange = (model) => {
    console.log('切换模型:', model);
  };
</script>

# ChatContainer 聊天容器

> **能力域**：对话搭建 ｜ **源码**：`src/components/chat-container/chat-container.vue`

顶层聊天容器，整合 `MessageContainer`（消息列表）、`ChatInput`（输入框）、`ExecutionSummary`（执行摘要）、`ShortcutRender`（快捷指令表单）和 `SelectionFooter`（多选操作栏），提供完整 AI 对话界面布局。

## 核心能力

- **分栏布局**：基于 `ResizeLayout`；侧栏 Tab / 执行摘要是否展示，以及是否进入 `ai-is-collapse`，由 `executionGroups` 与搜索词 `keyword` 共同决定。无执行数据且未搜索时隐藏侧栏；搜索中（`keyword` 非空）即使暂无执行消息也保留侧栏
- **消息分组**：内置 `useMessageGroup`，自动分组、Tool 合并、Loading 注入
- **输入区状态推导**：对内 `messageStatus` 取 `inputStatus`——分组中存在 `LOADING_MESSAGE_ID`（`'__loading__'`）时用 `MessageStatus.Fetching`，否则用外部 `messageStatus`，保证「已发未流式」阶段也能停止、并避免重复发送
- **待审批发送阻塞**：存在 `AIDevToolApproval` 且为 `pending` / `draft` 时，输入区上方提示，并通过 `ChatInput.sendDisabledTip` 禁止发送
- **用户问题中断**：待回答 `UserQuestion` 时挂载 `UserQuestionCard`；结构化作答走 `onInterruptResume`，输入框直接发送走 `onSendMessage`（第三参数带 skip `payload` 与 `interrupt`），且不自动清空输入框
- **执行摘要 / 侧栏全屏 / 自定义 Tab**：侧栏展示工具调用与 FlowAgent 记录，支持搜索定位；Tab 栏可全屏；`useCustomTabProvider` 支持动态 Tab
- **模型选择**：透传 `models`、`v-model:selectedModel` 与 `@modelChange` 至 `ChatInput`，传入 `models` 后在发送按钮左侧展示 [ModelSelector](/components/input/model-selector)
- **分享模式 / 渲染模式**：内置多选分享；`renderMode` 经 Provider 下传。`Share` 态开放侧栏只读查看，隐藏底部输入与「重试 / 跳过」等交互
- **字号主题**：`size` 为 `small`（默认 12px）/ `normal`（14px）；根节点 `data-ai-size`，浮层同步 `document.body.dataset.aiSize`
- **空状态欢迎页**：无消息时展示 Banner、`welcomeTitle`（默认「你好，我是小鲸」）与 `openingRemark`

## 组件结构

```
ai-chat-container（:data-ai-size="size"）
├── Loading（chatLoading 时）
└── ResizeLayout
    ├── aside（侧边栏）
    │   ├── .ai-full-screen-wrapper（全屏目标容器，ref=fullScreenRef）
    │   │   ├── Tab 标签页
    │   │   │   ├── 执行情况（默认 Tab）
    │   │   │   ├── 自定义 Tab × N（可关闭；标签可由 getSideTabRenderComponent 自定义）
    │   │   │   └── #setting → 全屏/退出全屏 ToolBtn
    │   │   ├── ExecutionSummary（执行情况 Tab 内容）
    │   │   └── 自定义 Tab 组件（getSideRenderComponent 优先，否则 data.component；可注入 #locateButton）
    │   └── collapse-button（CollapsedIcon）
    └── main（主内容区）
        ├── MessageContainer（有消息时；#group / #message 可自定义）
        ├── 欢迎页（无消息时 .ai-welcome-content）
        │   └── #welcome（默认：Banner + welcomeTitle + openingRemark；自定义则整块替换）
        ├── SelectionFooter（分享模式）
        ├── ShortcutRender（有快捷指令时）
        └── ChatInput（透传 models / selectedModel；interrupt 槽展示 UserQuestionCard / InputInfoAlert）
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

## 字号主题

通过 `size` 切换两档字号主题。未传时默认为 `small`（12px 基准字号）；设为 `normal` 时使用 14px 基准字号，并联动行高、间距与图标尺寸。

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="messages"
    message-status="complete"
    size="normal"
    :on-send-message="handleSendMessage"
  />
</template>
```

**渲染效果**（左右对比 `size="small"` 与 `size="normal"`）

<div class="demo" style="display: flex; gap: 16px;">
  <div style="flex: 1;">
    <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">size = "small"（默认）</p>
    <div style="height: 400px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
      <ChatContainerComp
        v-model="inputSizeSmall"
        :messages="messagesBasic"
        message-status="complete"
        size="small"
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
    <p style="margin: 0 0 4px; font-size: 12px; color: #979ba5;">size = "normal"</p>
    <div style="height: 400px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
      <ChatContainerComp
        v-model="inputSizeNormal"
        :messages="messagesBasic"
        message-status="complete"
        size="normal"
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

> CSS 变量与档位取值详见 [主题配置 — 字号主题](../../theme/theme#字号主题)。

## 侧边栏与执行摘要

侧边栏默认包含「执行情况」Tab，展示所有工具调用和 FlowAgent 类型的 Activity 消息。支持关键词搜索过滤和点击定位到对话中的消息位置。

**展示条件**：当 `executionGroups` 为空且 `keyword` 为空时，不渲染侧栏 Tab 与 `ExecutionSummary`（折叠按钮亦隐藏）；主区域仍可正常展示 `messages` 中的对话内容。用户在执行情况中输入搜索词后，侧栏会保持展示以显示「搜索结果为空」等状态。`renderMode === Share` 分享态同样按上述执行数据条件展示侧栏（开放只读查看流程智能体详情/证据/执行情况），不再强制隐藏折叠；仅底部输入区保持隐藏。**例外**：当[「文件产物」Tab](#内置-文件产物-tab)存在时，侧栏不再受「`executionGroups` 为空」约束，可独立展示文件预览。

**自定义 Tab 联动**：当 `executionGroups` 变为空且搜索词已清空时，容器会**自动重置自定义 Tab**（`resetCustomTab`），避免残留节点详情等 Tab；若用户仍在搜索（`keyword` 非空）或存在「文件产物」Tab，不会触发重置。

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

| `placement` | 侧边栏位置   | 折叠按钮位置 | 折叠图标旋转 |
| ----------- | ------------ | ------------ | ------------ |
| `left`      | 左侧（默认） | 主区域左边缘 | 折叠时旋转 180° |
| `right`     | 右侧         | 主区域右边缘 | 默认旋转 180°，折叠时恢复 0° |

> 折叠按钮仅展示 `CollapsedIcon`（不再显示「执行情况」文案），通过图标旋转方向指示展开/折叠状态。

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

## 侧栏全屏

当侧栏 Tab 区域可见时，Tab 栏右侧（`#setting` 插槽）内置全屏切换按钮：

- 点击 **全屏** 图标：调用 `useFullScreen(fullScreenRef).enter()`，将 `.ai-full-screen-wrapper` 进入浏览器原生全屏
- 点击 **退出全屏** 图标：调用 `exit()` 退出；用户按 ESC 退出时 `isFullScreen` 也会自动同步
- 全屏状态下，侧栏内 `v-overflow-tips` 的 `appendTo` 会指向全屏容器，避免 tooltip 挂载到 `document.body` 后被全屏层遮挡

该能力由内部 `useFullScreen` composable 提供，详见 [useFullScreen](../../composables/use-full-screen.md)。

## 自定义 Tab

通过 `ref` 获取组件实例后，使用 `addCustomTab` / `removeCustomTab` 动态管理侧边栏 Tab。若 **`executionGroups` 变为空且搜索词已清空**，容器会清空自定义 Tab 状态（与侧栏执行数据联动，见上文「侧边栏与执行摘要」）。

### Tab 排序与显隐

`CustomTab` 支持 `order` / `visible` / `closable` 三个可选字段，用于控制 Tab 栏的排序与显隐：

| 字段 | 默认值 | 说明 |
| ---- | ------ | ---- |
| `order` | `100` | 排序权重，升序，越小越靠前。「执行情况」固定 `0`；FlowAgent「有效证据」固定 `10`（紧随执行情况），节点详情走默认 `100` |
| `visible` | `true` | 是否在 Tab 栏展示。`false` 时从栏内隐藏，但仍可被 `addCustomTab` / `selectCustomTab` 程序化选中；若被隐藏的 Tab 当前正被选中，则自动切到首个可见 Tab、内容不再渲染 |
| `closable` | `true` | 是否展示关闭按钮。「执行情况」强制不可关闭 |

- 排序为稳定排序，`order` 相同的 Tab 保持插入先后顺序。
- 「执行情况」Tab 的显隐统一由 `executionTabVisible` Prop 控制（见 Props 表），不通过 `visible` 字段配置。
- 同名（同 `name`）`addCustomTab` 会**合并更新**已有 Tab，可用于运行时调整 `order` / `visible` / `label`。

### 侧栏渲染扩展

应用层可通过以下 Props 覆盖默认 Tab 标签与侧栏内容区的渲染逻辑（例如 FlowAgent 节点详情使用业务自定义组件）：

| Prop | 说明 |
| ---- | ---- |
| `getSideTabRenderComponent` | `(h, tab, { removeCustomTab }) => VNode \| undefined`。返回自定义 Tab 标签 VNode；未返回时使用默认图标 + `tab.label` + 关闭按钮 |
| `getSideRenderComponent` | `(h, props) => VNode \| undefined`。返回侧栏内容区组件 VNode；未返回时使用 `selectedTab.data.component` |

侧栏内容区实现上会以 **`selectedTab.name` 作为外层 `key`**，切换 Tab 时重建子树，避免插槽与局部状态残留；当前 Tab 的 `:is` 由内部 **`computed`** 根据 `getSideRenderComponent(h, selectedTab.data.props)` 与 `data.component` 解析，保证 Tab 切换或 `onCustomTabChange` 异步更新 props 后内容类型与数据一致。

```vue
<template>
  <ChatContainer
    :get-side-tab-render-component="renderSideTab"
    :get-side-render-component="renderSidePanel"
    ...
  />
</template>

<script setup lang="ts">
  import { h } from 'vue';
  import type { CustomTab } from '@blueking/chat-x';

  const renderSideTab = (createElement, tab, { removeCustomTab }) => {
    if (tab.name.startsWith('custom-')) {
      return createElement('span', {}, tab.label);
    }
    return undefined; // 走默认 Tab 标签
  };

  const renderSidePanel = (createElement, props) => {
    if (props?.has_confidence) {
      return createElement(MyConfidencePanel, props);
    }
    return undefined; // 走 tab.data.component
  };
</script>
```

### 内置「文件产物」Tab

除「执行情况」外，容器内置一个按需出现的固定 Tab —— **「文件产物」**（`name: 'file-artifact'`），用于聚合预览当前会话所有 `AssistantMessage.property.artifacts`：

- **触发**：点击 AI 回复中的文件卡片（[ArtifactFileCard](/components/message/assistant-message)）时，容器通过 `useArtifactPreviewProvider` 命中该文件并 `addCustomTab` 弹出侧栏
- **排序 / 关闭**：`order: -1` 排在「执行情况」之前，`closable: false` 不可关闭
- **显隐解耦**：该 Tab 存在时，侧栏展示不再受「`executionGroups` 为空」约束（即使当前会话没有执行类消息，也能独立展示文件产物侧栏）；会话切换或无文件产物时自动移除并重置命中态
- **内容**：由 [FileArtifactPanel](/components/message/file-artifact-panel) 渲染列表与下载头，预览委托内部 `ArtifactPreviewHost`；`download_url` / `preview_url` 通过 `onArtifactClick` 异步获取。文本类（`html` / `markdown` / `md` / `txt` / `json`）拉 `download_url` 正文直渲染（`md` 与 `markdown` 等价）；其余类型用 `preview_url` iframe（一般为后台转好的 PDF）
- **状态管理**：命中、切换与 URL 缓存由 [useArtifactPreview](/composables/use-artifact-preview) 提供（Provider 在容器内、Consumer 在文件卡片 / 面板内）；正文加载与分类型渲染由 Host 内部完成
- **未传 `onArtifactClick`**：下载按钮隐藏，预览区展示无数据

详见 [FileArtifactPanel 文件产物预览](/components/message/file-artifact-panel) 与 [useArtifactPreview 文件产物预览](/composables/use-artifact-preview)。

#### 接入示例

```vue
<template>
  <ChatContainer
    v-model="input"
    :messages="messages"
    :on-artifact-click="onArtifactClick"
    @send-message="handleSend"
  />
</template>

<script setup lang="ts">
  import { ref, shallowRef } from 'vue'
  import {
    ChatContainer,
    MessageRole,
    MessageStatus,
    type AIFileInfo,
    type Message,
  } from '@blueking/chat-x'

  const input = ref('')
  const messages = shallowRef<Message[]>([
    {
      id: 'u1',
      messageId: 'u1',
      role: MessageRole.User,
      status: MessageStatus.Complete,
      content: '整理本周评审材料',
    },
    {
      id: 'a1',
      messageId: 'a1',
      uid: 'assistant-uid-1',
      role: MessageRole.Assistant,
      status: MessageStatus.Complete,
      content: '已生成评审材料，点击卡片可在侧栏预览：',
      property: {
        artifacts: [
          { name: '周报.html', outputId: 'a-html', size: 10240, type: 'html' },
          { name: '说明.md', outputId: 'a-md', size: 8192, type: 'md' },
          { name: '配置.json', outputId: 'a-json', size: 2048, type: 'json' },
          { name: '立项.pdf', outputId: 'a-pdf', size: 204800, type: 'pdf' },
        ] satisfies AIFileInfo[],
      },
    },
  ])

  /** 文本类预览依赖 download_url；iframe 类依赖 preview_url */
  const onArtifactClick = async (file: AIFileInfo) => {
    const res = await api.getArtifactUrls(file.outputId)
    return {
      download_url: res.download_url,
      preview_url: res.preview_url,
    }
  }

  const handleSend = () => {
    /* ... */
  }
</script>
```

### 自定义 Tab 与「在对话中定位」

`addCustomTab` 的 `data` 可携带 **`messageUid`**（与对应活动消息的 `message.uid` 一致）。`ChatContainer` 在侧栏用 `<component :is="sideRenderComponent">`（内部计算属性，见上文「侧栏渲染扩展」）渲染自定义 Tab 时，会向子组件提供 **`locateButton` 插槽**：默认渲染「在对话中定位」按钮，点击后调用内部 `handleLocateMessageGroup(messageUid)`，优先滚动到主区域 `document.getElementById(messageUid)`；若不存在该节点，则在当前 `messageGroups` 中查找包含 `message.uid === messageUid` 的消息组，并滚动到该组的容器（`MessageGroup.uid` 作为组级 `id`）。

子组件若需展示该按钮，请在模板中声明 `<slot name="locateButton" />`（例如 FlowAgent 节点详情标题栏）。`FlowAgentContent` 等会在打开节点详情 Tab 时将 `messageUid` 写入 `data`，与 `ActivityMessage` 下传给内容区的 `message-uid` 对齐。

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
  const addNodeDetailTab = (nodeId: string, nodeName: string, messageUid?: string) => {
    chatContainerRef.value?.addCustomTab({
      name: `node-${nodeId}`,
      label: nodeName,
      data: {
        component: MyNodeDetail, // 自定义组件（模板内需 <slot name="locateButton" /> 以展示侧栏「在对话中定位」）
        props: { loading: true, data: {} },
        messageUid, // 与活动消息 message.uid 一致时可省略；用于主对话定位
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

无消息时展示欢迎页：`welcomeTitle` 控制标题（未传时默认「你好，我是小鲸」），`openingRemark` 为开场白（支持 Markdown）：

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="[]"
    :message-status="messageStatus"
    welcome-title="你好，我是小鲸"
    opening-remark="你好！我是 AI 小鲸 🐳，可以帮你：\n\n- 编写和优化代码\n- 解答技术问题\n- 分析和调试错误"
    :on-send-message="handleSendMessage"
  />
</template>
```

### 自定义欢迎内容

通过 `#welcome` 可整块替换默认欢迎区，插槽参数为 `{ openingRemark, welcomeTitle }`：

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="[]"
    :message-status="messageStatus"
    welcome-title="欢迎使用 AI 助手"
    opening-remark="选择一个快捷入口开始对话"
    :on-send-message="handleSendMessage"
  >
    <template #welcome="{ openingRemark, welcomeTitle }">
      <div class="my-welcome">
        <h3>{{ welcomeTitle }}</h3>
        <p>{{ openingRemark }}</p>
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

> **注意**：使用 `#welcome` 后将**整块替换**默认欢迎区（Banner、标题与开场白的 `ContentRender`），需自行编排完整欢迎页。

**渲染效果**

<div class="demo">
  <div style="height: 400px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputEmpty"
      :messages="[]"
      message-status="complete"
      welcome-title="你好，我是小鲸"
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

## 待审批阻塞发送

当会话中存在待审批的 AI Dev 工具审批中断时，`ChatContainer` 会在输入框上方展示提示，并禁用发送按钮。用户需要在审批卡片中点击「取消审批」或等待状态变化后，才能继续发送新消息。

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="messages"
    message-status="complete"
    :on-interrupt-resume="handleInterruptResume"
    :on-send-message="handleSendMessage"
    :on-stop-sending="handleStopSending"
  />
</template>
```

**渲染效果**（待审批单存在时，输入区上方展示提示，发送按钮置灰）

<div class="demo">
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputApproval"
      :messages="messagesApproval"
      message-status="complete"
      :on-interrupt-resume="handleInterruptResume"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
    />
  </div>
</div>

## 用户问题中断

当会话中最近一条待处理 interrupt 包含 `InterruptReason.UserQuestion` 时，`ChatContainer` 会在 `ChatInput` 上方显示 [UserQuestionCard](/components/agent/user-question-card)。

- **结构化作答**：用户在卡片内完成选择或点击「跳过」后，通过 `onInterruptResume(payload, interrupt)` 回传 `UserQuestionResume`。
- **输入框发送**：用户也可在输入框直接点击发送；容器会调用 `onSendMessage(content, docSchema, options)`，其中 `options.interrupt` 为当前激活的 UserQuestion，`options.payload` 为 `buildSkipResumePayload` 生成的 skip resume（`status: 'cancelled'`，`answers: []`）。此时**不会自动清空**输入框，由业务侧在 `onSendMessage` 内决定如何处理 `content` 与中断恢复。

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="messages"
    message-status="complete"
    :on-interrupt-resume="handleInterruptResume"
    :on-send-message="handleSendMessage"
  />
</template>

<script setup lang="ts">
  import {
    type OnInterruptResume,
    type UserMessage,
    type TagSchema,
    type Interrupt,
    type InterruptResume,
  } from '@blueking/chat-x';

  const handleInterruptResume: OnInterruptResume = async (payload, interrupt) => {
    // UserQuestionCard 完成 / 跳过时 payload 为 UserQuestionResume
    await resumeAgent({ interruptId: interrupt.id, resume: payload });
  };

  const handleSendMessage = async (
    content: UserMessage['content'],
    docSchema: TagSchema,
    options?: { interrupt?: Interrupt; payload?: InterruptResume },
  ) => {
    if (options?.interrupt && options?.payload) {
      // 存在 UserQuestion 时发送：附带 skip resume，content 仍为输入框文本
      await resumeAgent({ interruptId: options.interrupt.id, resume: options.payload });
      // 业务侧自行决定是否将 content 作为新用户消息继续发送
      return;
    }
    await sendMessage(content, docSchema);
  };
</script>
```

## 自定义消息组渲染

通过 `#group` 插槽可替换单个消息组的默认内容，透传至内部 `MessageContainer`。外层消息组容器（`id`、hover、选中背景）仍由 `MessageContainer` 管理。

> **注意**：提供 `#group` 后需自行编排组内全部 UI（Checkbox、消息列表、`MessageTools`）；若只需替换单条消息，请使用 `#message` 插槽。详见 [MessageContainer 自定义消息组渲染](/components/setup/message-container#自定义消息组渲染)。

```vue
<ChatContainer
  v-model="inputValue"
  :messages="messages"
  message-status="complete"
  :on-send-message="handleSendMessage"
>
  <template #group="{ group }">
    <MyCustomGroup :group="group" />
  </template>
</ChatContainer>
```

### 自定义题目渲染

通过 `#interruptQuestion` slot 可覆盖输入区上方 `UserQuestionCard` 的默认选择题渲染，参数与 [UserQuestionCard](/components/agent/user-question-card) 的 `#question` 一致：

```vue
<ChatContainer
  v-model="inputValue"
  :messages="messages"
  :on-interrupt-resume="handleInterruptResume"
  :on-send-message="handleSendMessage"
>
  <template #interruptQuestion="{ question, qIndex, answer, setAnswer, confirm }">
    <MyCustomForm
      :model="question"
      @change="setAnswer"
      @submit="confirm"
    />
  </template>
</ChatContainer>
```

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
  import { type IToolBtn, type Message } from '@blueking/chat-x';

  // 第二参数 source 为触发多选态的按钮对象，可据此区分 share / save 等不同确认场景
  const handleConfirmShare = (selectedMessages: Message[], source?: IToolBtn) => {
    if (source?.id === 'save') {
      console.log('保存选中的消息:', selectedMessages);
      return;
    }
    console.log('分享消息:', selectedMessages);
  };
</script>
```

### 自定义按钮触发多选（triggerSelection）

除内置「分享」外，任意自定义工具按钮标记 `triggerSelection: true` 后，点击即可复用同一套多选流程（勾选消息 → `SelectionFooter` 确认），确认时同样触发 `confirmShare`。配合 `messageTools` / `updateTools`（合并规则见 [MessageContainer · 自定义消息工具栏](/components/setup/message-container)）即可扩展如「保存」「收藏到空间」等批量操作。

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    :messages="messages"
    message-status="complete"
    :message-tools="customMessageTools"
    :on-agent-action="handleAgentAction"
    @confirm-share="handleConfirmShare"
  />
</template>

<script setup lang="ts">
  import { DownloadIcon, type IToolBtn, type Message } from '@blueking/chat-x';

  const customMessageTools: IToolBtn[] = [
    // 追加「保存」按钮，点击进入多选态；确认走 confirmShare
    { id: 'save', name: '保存', description: '保存该回答', icon: DownloadIcon, triggerSelection: true },
  ];

  const handleConfirmShare = (selectedMessages: Message[], source?: IToolBtn) => {
    if (source?.id === 'save') {
      // 处理「保存」批量确认
    }
  };
</script>
```

> `triggerSelection` 的按钮不会调用 `onAgentAction`，而是直接进入多选态；未标记该字段（且非 `share`）的按钮仍走 `onAgentAction`。

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

1. 用户点击消息工具栏中的「分享」按钮（或任意 `triggerSelection: true` 的自定义按钮）
2. 进入多选模式，用户勾选要分享的消息
3. 底部 `SelectionFooter` 提供全选、取消、确认操作
4. 确认后触发 `confirmShare` 事件，携带选中的消息列表与触发按钮对象（`source`）

## 模型选择

`ChatContainer` 将 `models`、`v-model:selected-model` 与 `@model-change` 透传至内部 [ChatInput](/components/input/chat-input)。传入 `models` 后，发送按钮左侧展示 [ModelSelector](/components/input/model-selector)；选中值为模型的 `llm_name`，发送时可读取当前 `selectedModel`。

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    v-model:selected-model="selectedModel"
    :messages="messages"
    message-status="complete"
    :models="models"
    :on-send-message="handleSendMessage"
    @model-change="handleModelChange"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatContainer, type IModelOption, type Message, type TagSchema } from '@blueking/chat-x';

  const inputValue = ref('');
  // 选中值为 llm_name
  const selectedModel = ref('GPT-4');
  const messages = ref<Message[]>([]);
  const models: IModelOption[] = [
    { id: 1, llm_name: 'GPT-4', property: { support_thinking: true } },
    { id: 2, llm_name: 'Claude 3', property: { support_thinking_quick: true } },
    { id: 3, llm_name: 'DeepSeek', property: { support_vision: true } },
  ];

  const handleSendMessage = async (content: string, docSchema: TagSchema) => {
    // 发送时可读取 selectedModel.value
  };
  const handleModelChange = (model: IModelOption) => {
    console.log('切换模型:', model);
  };
</script>
```

**渲染效果**（输入区发送按钮左侧可切换模型）

<div class="demo">
  <div style="height: 480px; border: 1px solid #eaebf0; border-radius: 8px; overflow: hidden;">
    <ChatContainerComp
      v-model="inputModel"
      v-model:selected-model="selectedModelId"
      :messages="messagesBasic"
      message-status="complete"
      :models="models"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :on-agent-action="handleAgentAction"
      :on-agent-feedback="handleAgentFeedback"
      :on-user-action="handleUserAction"
      @model-change="handleModelChange"
      @stop-streaming="handleStopStreaming"
    />
  </div>
</div>

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

| 属性名                    | 类型                                                                                     | 默认值    | 说明                                                                                                                                 |
| ------------------------- | ---------------------------------------------------------------------------------------- | --------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| chatLoading               | `boolean`                                                                                | —         | 整体加载状态，`true` 时显示 Loading 遮罩                                                                                             |
| commonTippyOptions        | `AITippyProps`                                                                           | —         | 通用 Tippy 配置，注入到所有使用 `v-overflow-tips` 的子组件                                                                           |
| executionTabVisible       | `boolean`                                                                                | `true`    | 「执行情况」Tab 是否展示；为 `false` 时从 Tab 栏隐藏，若正被选中则切到首个可见 Tab                                                   |
| getSideRenderComponent    | `(h, props?) => VNode \| undefined`                                                      | —         | 自定义侧栏内容区渲染；未返回时使用 `selectedTab.data.component`                                                                      |
| getSideTabRenderComponent | `(h, tab, { removeCustomTab }) => VNode \| undefined`                                    | —         | 自定义侧栏 Tab 标签渲染；未返回时使用默认图标 + 文案 + 关闭按钮                                                                      |
| models                    | `IModelOption[]`                                                                         | —         | 可选模型列表（继承自 ChatInput）；传入后在发送按钮左侧展示 ModelSelector                                                             |
| openingRemark             | `string`                                                                                 | —         | 开场白，无消息时显示，支持 Markdown                                                                                                  |
| placement                 | `'left' \| 'right'`                                                                      | `'left'`  | 侧边栏位置                                                                                                                           |
| resizeProps               | `{ disabled?: boolean; initialDivide?: number \| string; max?: number; min?: number }`    | —         | 透传给内部 `ResizeLayout`；与默认 `collapsible: false`、`immediate: true`、`min: 400` 合并；`placement` 始终取自本组件。**数字型** `initialDivide` 还会作为内部侧栏宽度初值（驱动 `--resize-main-width`，并在展开时作为 `collapseChange` 的 `width`）；百分比等字符串则回退为 `400` |
| size                      | `'normal' \| 'small'`                                                                    | `'small'` | 字号主题：`small` 12px / `normal` 14px；根节点设置 `data-ai-size` 并注入 `useGlobalConfig`                                           |
| welcomeTitle              | `string`                                                                                 | —         | 欢迎页标题；未传时默认展示「你好，我是小鲸」                                                                                         |
| onCustomTabChange         | `(tab: CustomTab) => Promise<any>`                                                       | —         | 自定义 Tab 切换回调，返回值作为 Tab 组件 props                                                                                       |
| onArtifactClick           | `(file: AIFileInfo) => Promise<{ download_url?: string; preview_url?: string }>`          | —         | 异步获取下载 / 预览链接（按 `outputId` 缓存）。文本类预览依赖 `download_url`，iframe 类依赖 `preview_url`；未传则隐藏下载、预览无数据 |

> 其余 Props（如 `messages`、`messageStatus`、`onSendMessage`、`shortcuts` 等）继承自 [ChatInput](/components/input/chat-input) 与 [MessageContainer](/components/setup/message-container)。

### v-model

| 属性名           | 类型                  | 说明                                                                                                                                              |
| ---------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| modelValue       | `string \| TagSchema` | 输入框内容，支持纯文本或标签结构                                                                                                                  |
| selectedShortcut | `Shortcut \| null`    | 当前选中的快捷指令                                                                                                                                |
| cite             | `string`              | 引用内容                                                                                                                                          |
| renderMode       | `RenderMode`          | 渲染模式（默认 `Chat`）。`Share` 开放侧栏只读查看并隐藏底部输入与交互操作；`Test` 隐藏分享按钮                                                    |
| selectedModel    | `string`              | 当前选中模型的 `llm_name`，透传至 ChatInput 的 ModelSelector                                                                                      |

### Events

| 事件名         | 参数                                   | 说明                                 |
| -------------- | -------------------------------------- | ------------------------------------ |
| stopStreaming  | —                                      | 点击「停止生成」按钮                 |
| shortcutClose  | —                                      | 关闭快捷指令表单                     |
| shortcutSubmit | `(formModel: Record<string, unknown>)` | 提交快捷指令表单                     |
| confirmShare   | `(messages: Message[], source?: IToolBtn)` | 确认分享/多选，携带选中的消息与触发按钮对象（`source`，用于区分 share/save 等场景） |
| collapseChange | `(isCollapse: boolean, width: number)` | 侧边栏折叠/展开状态变化              |
| selectShortcut | `(shortcut: Shortcut)`                 | 选择快捷指令（继承自 ChatInput）     |
| deleteShortcut | —                                      | 删除已选快捷指令（继承自 ChatInput） |
| modelChange    | `(model: IModelOption)`                | 切换模型（继承自 ChatInput）         |

### Slots

| 插槽名            | 参数                                                                                         | 说明                                                                                                     |
| ----------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| codeHeader        | `{ language: string; token: Token[] }`                                                       | 代码块头部自定义操作区域（定义于类型；透传链路同 MessageRender）                                         |
| default           | `{ messages, messageStatus, messageGroups, selectedUserMessages, messageToolsStatus, isShareMode, commonTippyOptions, handleAgentAction, onAgentFeedback, onInterruptResume, onUserAction, onUserInputConfirm, onUserShortcutConfirm }` | 自定义消息列表区域；未提供时渲染默认 `MessageContainer`                                                  |
| group             | `{ group: MessageGroup }`                                                                    | 自定义单个消息组，透传至 MessageContainer `#group`；替换默认 Checkbox、消息列表与工具栏                  |
| interruptQuestion | `{ question, qIndex, answer, setAnswer, confirm }`                                           | 自定义 UserQuestion 单题渲染，透传至 UserQuestionCard `#question`                                        |
| message           | `{ message, messageToolsStatus, onInterruptResume }`                                         | 自定义单条消息；自定义中断消息时需继续透传 `onInterruptResume`                                           |
| welcome           | `{ openingRemark?: string; welcomeTitle?: string }`                                          | 无消息时自定义欢迎页；传入则整块替换默认 Banner、标题与开场白                                            |

### Expose

| 方法/属性名     | 类型                        | 说明           |
| --------------- | --------------------------- | -------------- |
| selectedTab     | `Ref<CustomTab>`            | 当前选中的 Tab |
| addCustomTab    | `(tab: CustomTab) => void`  | 添加自定义 Tab |
| removeCustomTab | `(tabName: string) => void` | 移除自定义 Tab |
| selectCustomTab | `(tab: CustomTab) => void`  | 切换到指定 Tab |
| enterShareMode  | `() => void`                | 手动进入分享多选模式 |
| exitShareMode   | `() => void`                | 退出分享多选模式，并清空已选消息 |

## 渲染模式

通过 `v-model:render-mode` 控制容器的渲染行为。`ChatContainer` 会把当前 `renderMode` 注入给后代组件，供内容渲染根据场景收敛交互能力。

| `renderMode` | 侧边栏 Tab / 折叠按钮 | 底部输入区域                      | MessageTools 工具栏   | 说明                             |
| ------------ | ---------------------- | --------------------------------- | --------------------- | -------------------------------- |
| `Chat`       | 正常显示               | 正常显示（ChatInput / ShortcutRender / SelectionFooter） | 全部工具按钮          | 默认对话模式                     |
| `Share`      | **按执行数据展示**（开放只读查看） | **隐藏**             | **隐藏**（多选模式）  | 分享预览模式；开放流程智能体侧栏详情/证据/执行情况与耗时，仅隐藏「重试/跳过」等交互 |
| `Test`       | 正常显示               | 正常显示                          | 过滤掉「分享」按钮    | 测试/嵌入模式，隐藏分享入口     |

```vue
<template>
  <ChatContainer
    v-model="inputValue"
    v-model:render-mode="renderMode"
    :messages="messages"
    :message-status="messageStatus"
    :on-send-message="handleSendMessage"
  />
</template>

<script setup lang="ts">
  import { shallowRef } from 'vue';
  import { ChatContainer, RenderMode } from '@blueking/chat-x';

  const renderMode = shallowRef<RenderMode>(RenderMode.Chat);
</script>
```

## 类型定义

```typescript
import {
  ChatContainer,
  RenderMode,
  MessageRole,
  type CustomTab,
  type IModelOption,
  type MessageGroup,
  type Shortcut,
  type Message,
} from '@blueking/chat-x';

// 消息组（由 useMessageGroup 生成）
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

// 自定义 Tab（data 可与 messageUid 组合，供侧栏定位主对话）
interface CustomTab<T = Record<string, unknown>> {
  label: string;
  name: string;
  icon?: string;
  order?: number; // 缺省 100；「执行情况」固定 0
  visible?: boolean; // 缺省 true；false 时栏内隐藏，仍可程序化选中
  closable?: boolean; // 缺省 true；「执行情况」强制不可关闭
  data?: T & { messageUid?: string; component?: Component; props?: Record<string, unknown> };
}

// 模型选项（透传至 ChatInput / ModelSelector，贴合后端接口结构；能力标签由 property 派生）
interface IModelOption {
  id: number;
  llm_code: string;
  llm_name: string; // 展示名，同时作为选中值
  llm_type: string;
  space_auth_mode: string;
  user_auth_mode: string;
  max_token_size: number;
  property: {
    support_thinking?: boolean; // → 深度思考
    support_thinking_quick?: boolean; // → 快速思考
    support_vision?: boolean; // → 图生文
    [key: string]: unknown;
  };
  icon?: string;
  description?: string;
  base_model?: string;
  tag_names?: string[];
  disabled?: boolean; // 前端扩展字段
}

// 快捷指令
interface Shortcut {
  id: string;
  name: string;
  components?: ShortcutComponent[];
}
```

## 关联组件

- [MessageContainer](/components/setup/message-container) — 消息列表区域
- [ChatInput](/components/input/chat-input) — 输入与快捷指令
- [ModelSelector](/components/input/model-selector) — 模型选择器（透传 `models` / `selectedModel`）
- [ShortcutRender](/components/input/shortcut-render) — 快捷指令表单
- [ExecutionSummary](/components/agent/execution-summary) — 执行摘要侧栏
- [SelectionFooter](/components/input/selection-footer) — 多选操作栏
- [ToolBtn](/components/feedback/tool-btn) — 侧栏全屏按钮
- [useFullScreen](/composables/use-full-screen) — 侧栏全屏控制
- [useGlobalConfig](/composables/use-global-config) — 注入 `size` 与 `supportUpload`
- [主题配置](/theme/theme) — 字号主题 CSS 变量
