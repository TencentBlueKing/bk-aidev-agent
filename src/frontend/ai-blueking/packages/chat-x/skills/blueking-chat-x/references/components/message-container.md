# MessageContainer 消息列表容器

> 能力域：对话搭建 ｜ 导入：`import { MessageContainer } from '@blueking/chat-x'` ｜ since 1.0.0

负责消息分组渲染、滚动控制、工具栏和消息插槽透传。 源码位置：src/components/chat-message/message-container/message-container.vue。

**关联**：message-render（按组渲染每条消息时委托 MessageRender）、chat-input（常与 ChatInput 组合构成完整对话界面）、loading-message（末尾为用户消息时自动追加 Loading 消息组）、interrupt-message（透传 onInterruptResume；末条 interrupt 消息不触发组 hover）

---

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
- **滚动管理**：`messageStatus` 为流式、等待响应或请求中（`streaming` / `pending` / `fetching`）时显示「停止生成」，离开底部时显示「返回底部」；`renderMode` 为 `Share` 时不显示「停止生成」。挂载时通过 `jumpToBottom()` 瞬时贴底，避免切换会话时从顶部平滑滚到底部的动画
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
- AI 消息组的时间通过 `MessageTools` 的 `#append` 插槽渲染在工具图标右侧，取值为组内**最后一条**带 `createdAt` 的消息（即本轮回答完成时间）；组内 `reasoning` / `activity` 等子消息不单独展示时间，全组都没有 `createdAt` 时不展示
- `renderMode === RenderMode.Test` 时，工具栏会过滤掉「分享」按钮，其余正常
- `renderMode === RenderMode.Share` 时，`message-group-messages` 自动添加 `message-group-enabled-selection` 类名（与 `enableSelection: true` 一致的多选视觉效果）
- Loading 消息组的 `type` 是 `MessageRole.Loading`，不显示工具栏和多选 Checkbox

## DOM 定位标识

为方便业务方通过 `document.querySelector` 定位消息（埋点、自动化测试、外部滚动锚定等），渲染结构上固定输出两层标识：

| 层级     | 选择器                                | 值                                                  |
| -------- | ------------------------------------- | --------------------------------------------------- |
| 消息组   | `.message-group[data-message-group-id]` | `MessageGroup.uid`（与外层 `id` 同值）              |
| 单条消息 | `.ai-message-item[data-message-id]`   | `message.id`，缺失时回退 `message.uid`；两者都无则不输出该属性 |

```js
// 定位某条消息
document.querySelector('[data-message-id="123"]');
// 定位某个消息组下的全部消息
document.querySelectorAll('[data-message-group-id="xxx"] [data-message-id]');
```

`.ai-message-item` 是 `MessageContainer` 统一包裹的容器，`#default` 插槽自定义渲染的消息同样被它包裹，因此无论用默认 `MessageRender` 还是自定义渲染，标识都一致存在。

## 等待响应（Loading 自动注入）

当 `messages` 末尾为 `role: 'user'` 时，自动追加 Loading 消息组，展示 AI 正在处理的加载动画（`renderMode` 为 `Share` 时不追加，且 `MessageContainer` 会过滤 Loading 组）：

## 流式输出与停止生成

当 `messageStatus` 为 `streaming`、`pending`（等待首包）或 `fetching`（请求中、与末尾 Loading 占位一致）时，底部固定区域显示「停止生成」按钮（`stop-loading` 时按钮展示为正在停止），点击后触发 `@stop-streaming` 事件。`renderMode` 为 `Share` 时不显示「停止生成」按钮。

点击下方按钮体验完整的流式输出过程：

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

## Activity 知识检索消息

`role: 'activity'` 消息同样被归入 AI 消息组，与 assistant 消息一起渲染：

## 多轮对话

连续多轮问答，组件按角色自动分组，每个 AI 组独立显示工具栏：

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
| 「返回底部」 | `debouncedShowScrollBottomBtn`（距底部 > 100px，且防抖 300ms 后才显示/隐藏）                     | 平滑滚动到消息列表底部（显式 `toScrollBottom('smooth')`） |

> **防抖说明**：「返回底部」按钮的显隐使用 300ms 防抖，避免快速滚动时按钮频繁闪烁。隐藏时立即生效（无防抖），显示时延迟 300ms。

> **首屏 / 切换会话贴底**：`MessageContainer` 挂载时若已有消息组，会立即调用 `jumpToBottom()`，并在下一帧再补一次，避免历史消息渲染过程中出现「从顶部滚到底部」的动画。流式输出场景下的小幅跟随仍由 markdown 挂载触发的 `toScrollBottom()`（距底较近时走 smooth）完成。
## API

### Props

| 属性名                   | 类型                                                                                         | 默认值  | 说明                                                                                                                                     |
| ------------------------ | -------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| messages                 | `Message[]`                                                                                  | —       | **必填**，消息列表                                                                                                                       |
| messageGroups            | `MessageGroup[]`                                                                             | —       | 预计算的消息分组；传入时跳过内部分组逻辑，由 `ChatContainer` 通过 `useMessageGroup` 提供                                                 |
| messageStatus            | `MessageStatus`                                                                              | —       | 当前整体消息状态，控制底部「停止生成」按钮显示；`ChatContainer` 会结合末尾 Loading 占位推导 `fetching` 等再传入                                                                                                   |
| messageTools             | `IToolBtn[]`                                                                                 | —       | AI 消息左侧工具（复制/引用等）的自定义配置；按 `id` 与内置 `CONST_MESSAGE_TOOLS` 合并（覆盖同 id、追加新 id、`hidden` 过滤），详见「自定义消息工具栏」 |
| updateTools              | `IToolBtn[]`                                                                                 | —       | AI 消息右侧反馈工具（点赞/踩/删除等）的自定义配置；按 `id` 与内置 `CONST_UPDATE_TOOLS` 合并，规则同上                                     |
| userMessageTools         | `IToolBtn[]`                                                                                 | —       | 自定义用户消息工具组，透传给 `MessageRender` → `UserMessage`；按 id 与 `CONST_USER_MESSAGE_TOOLS` 合并，`{ id, hidden: true }` 可隐藏     |
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
- [MessageTime](/components/feedback/message-time) — AI 消息组工具栏右侧的时间
- [InterruptMessage 中断消息](/components/agent/interrupt-message) — `role: 'interrupt'` 的渲染与 `onInterruptResume` 透传
- [ChatInput](/components/input/chat-input) — 常与输入区组合构成完整对话界面
- [LoadingMessage](/components/message/loading-message) — 末尾为用户消息时自动追加加载组
