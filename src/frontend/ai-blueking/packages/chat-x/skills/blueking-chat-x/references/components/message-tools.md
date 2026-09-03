# MessageTools 消息工具栏

> 能力域：工具与反馈 ｜ 导入：`import { MessageTools } from '@blueking/chat-x'` ｜ since 1.0.0

消息悬浮工具栏，组合复制、删除、反馈等工具按钮；提供 prepend / append 两端插槽承载消息时间等附加内容。 源码位置：src/components/message-tools/message-tools.vue。

**关联**：tool-btn（普通工具项由 ToolBtn 渲染）、user-feedback（like/unlike 时弹出反馈表单）、delete-tool（id 为 delete 时替换为带确认的删除按钮）、message-time（通过 prepend / append 插槽嵌入消息时间）

---

# MessageTools 消息工具栏
## 源码事实

- **源码位置**：`src/components/message-tools/message-tools.vue`
- **能力域**：工具与反馈
- **能力说明**：消息悬浮工具栏，组合复制、删除、反馈等工具按钮。

> **能力域**：工具与反馈

AI 消息的操作工具栏组件，由**左侧消息工具区**和**右侧更新工具区**两部分组成，中间以分隔线分隔；两端另有 `prepend` / `append` 插槽用于挂载消息时间等附加内容。仅 `like` / `unlike` 按钮会弹出反馈表单（`UserFeedback`），其余按钮直接触发 `onAction`。

## 组件结构

```
┌───────────────────────────────────────────────────────────────────────┐
│  .ai-message-tools-container（display: flex，gap: 4px）                 │
│  ┌────────┐  ┌─────────────────────┐  │  ┌───────────────┐  ┌───────┐ │
│  │#prepend│  │  messageTools        │  │  │  updateTools  │  │#append│ │
│  │        │  │  copy cite rebuild…  │  │  │ like unlike…  │  │       │ │
│  └────────┘  └─────────────────────┘  │  └───────────────┘  └───────┘ │
│    插槽区          左侧区域         分隔线    右侧区域          插槽区   │
└───────────────────────────────────────────────────────────────────────┘
```

- 分隔线（`.ai-divider`）与**右侧更新工具区**均仅在 `updateTools` 非空时渲染
- `updateTools` 中 `id` 为 `like` / `unlike` 的按钮被 `Tippy` 弹窗包裹，点击后展示 `UserFeedback` 反馈表单
- `updateTools` 中 `id` 为 `delete` 的按钮使用 `DeleteTool` 组件，点击后展示**确认删除弹窗**（含"删除"/"取消"按钮），确认后触发 `onAction`
- `updateTools` 中其他按钮直接触发 `onAction`，不弹表单
- `messageTools` 中 `id` 为 `delete` 的按钮同样使用 `DeleteTool` 组件弹确认框

## 基础用法

```vue
<template>
  <MessageTools
    :on-action="handleAction"
    @feedback="handleFeedback"
  />
</template>

<script setup lang="ts">
  import { MessageTools, type IToolBtn } from '@blueking/chat-x';

  // like / unlike 必须返回 Promise<string[]>，作为反馈表单的选项
  const handleAction = async (tool: IToolBtn) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面', '表达清晰', '解决了问题'];
    }
  };

  // 用户在反馈表单点击"提交"后触发
  const handleFeedback = (tool: IToolBtn, reasonList: string[], otherReason: string) => {
    console.log('反馈:', tool.id, reasonList, otherReason);
  };
</script>
```

**渲染效果**

## 反馈交互流程

点赞（`like`）和不满意（`unlike`）按钮的完整交互流程：

```
用户点击 like/unlike
        │
        ▼
调用 onAction(tool)（显示 loading 状态）
        │
        ▼
onAction 返回 string[]（反馈选项列表）
        │
        ▼
弹出 UserFeedback 表单（显示选项）
        │
   ┌────┴────┐
取消         提交
  │           │
关闭弹窗     emit('feedback', tool, reasonList, otherReason)
             │
             ▼
          按钮切换为激活图标（activeLike / activeUnLike）
          ↑ 再次点击同一按钮 → 取消激活并关闭弹窗（不触发 feedback）
```

**图标切换说明**：

| 状态         | `like` 按钮图标          | `like` Tooltip   | `unlike` 按钮图标          | `unlike` Tooltip |
| ------------ | ------------------------ | ---------------- | -------------------------- | ---------------- |
| 未提交       | `like`（空心）           | 原始 description | `unlike`（空心）           | 原始 description |
| 已提交点赞   | `activeLike`（实心填充） | 取消满意         | `unlike`（空心）           | 原始 description |
| 已提交不满意 | `like`（空心）           | 原始 description | `activeUnLike`（实心填充） | 取消不满意       |

> 激活态下 tooltip 内容自动切换为"取消满意"/"取消不满意"，用于提示用户再次点击可取消评价。

## 默认工具列表

### messageTools（左侧）

```typescript
const CONST_MESSAGE_TOOLS = [
  { id: 'copy', name: '复制', description: '复制' },
  { id: 'cite', name: '引用', description: '引用' },
  { id: 'rebuild', name: '重新生成', description: '重新生成' },
  { id: 'share', name: '分享', description: '分享' },
];
```

### updateTools（右侧）

```typescript
const CONST_UPDATE_TOOLS = [
  { id: 'like', name: '点赞', description: '点赞' },
  { id: 'unlike', name: '不满意', description: '不满意' },
  { id: 'delete', name: '删除', description: '删除' },
];
```

> **注意**：`delete` 在 `updateTools` 中**不弹反馈表单**，而是弹出确认删除弹窗（`DeleteTool`）。用户确认后才触发 `onAction`，取消则不触发。

## 内置图标 ID

`ToolBtn` 会根据 `tool.id` 自动匹配图标，支持以下 ID：

| ID             | 图标说明                             |
| -------------- | ------------------------------------ |
| `copy`         | 复制                                 |
| `cite`         | 引用                                 |
| `rebuild`      | 重新生成                             |
| `share`        | 分享                                 |
| `like`         | 点赞（空心）                         |
| `unlike`       | 不满意（空心）                       |
| `delete`       | 删除                                 |
| `edit`         | 编辑                                 |
| `activeLike`   | 点赞已激活（实心，由组件内部使用）   |
| `activeUnLike` | 不满意已激活（实心，由组件内部使用） |

> ID 不在列表中时，按钮显示 `tool.name` 文本。

## 仅显示消息工具（不含反馈）

将 `updateTools` 设为空数组可去掉右侧反馈按钮和分隔线：

```vue
<template>
  <MessageTools
    :message-tools="messageTools"
    :update-tools="[]"
    :on-action="handleAction"
  />
</template>

<script setup lang="ts">
  import { MessageTools, type IToolBtn } from '@blueking/chat-x';

  const messageTools: IToolBtn[] = [
    { id: 'copy', name: '复制', description: '复制' },
    { id: 'cite', name: '引用', description: '引用' },
  ];

  const handleAction = async (tool: IToolBtn) => {
    console.log('操作:', tool.id);
  };
</script>
```

**渲染效果**

## 自定义工具列表

`messageTools` 和 `updateTools` 均可完全替换：

```vue
<template>
  <MessageTools
    :message-tools="customMessageTools"
    :update-tools="customUpdateTools"
    :on-action="handleAction"
    @feedback="handleFeedback"
  />
</template>

<script setup lang="ts">
  import { MessageTools, type IToolBtn } from '@blueking/chat-x';

  const customMessageTools: IToolBtn[] = [
    { id: 'copy', name: '复制', description: '复制消息内容' },
    { id: 'rebuild', name: '重新生成', description: '重新生成回答' },
    { id: 'custom-action', name: '自定义', description: '自定义操作' }, // 无图标，显示文本
  ];

  // like / unlike 仍会触发反馈弹窗；delete 弹确认框，确认后触发 onAction
  const customUpdateTools: IToolBtn[] = [
    { id: 'like', name: '有帮助', description: '这个回答对我有帮助' },
    { id: 'unlike', name: '没帮助', description: '这个回答没有帮助' },
    { id: 'delete', name: '删除', description: '删除消息' },
  ];

  const handleAction = async (tool: IToolBtn) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面', '表达清晰', '解决了问题'];
    }
    console.log('操作:', tool.id);
  };

  const handleFeedback = (tool: IToolBtn, reasonList: string[], otherReason: string) => {
    console.log('反馈:', tool.id, reasonList, otherReason);
  };
</script>
```

**渲染效果**

## 两端插槽（prepend / append）

`prepend`（工具图标左侧）与 `append`（工具图标右侧）用于在工具栏两端挂载附加内容，项目内用于放置 [MessageTime 消息时间](/components/feedback/message-time)：

| 场景      | 使用插槽  | 效果                                    |
| --------- | --------- | --------------------------------------- |
| 用户消息  | `prepend` | 时间显示在工具图标左侧                  |
| AI 消息组 | `append`  | 时间显示在工具图标右侧                  |

```vue
<template>
  <MessageTools :on-action="handleAction">
    <template #append>
      <MessageTime :created-at="createdAt" />
    </template>
  </MessageTools>
</template>

<script setup lang="ts">
  import { MessageTime, MessageTools } from '@blueking/chat-x';
</script>
```

- 插槽包裹容器（`.ai-message-tools-prepend` / `.ai-message-tools-append`）仅在对应插槽传入时渲染
- 插槽内容为空时（如消息无 `createdAt`，`MessageTime` 不渲染任何 DOM），包裹容器命中 `:empty` 被收起，不会留下多余间距

## 工具栏状态控制

`messageToolsStatus` 控制工具栏整体状态：

| 值          | 效果                                                                   |
| ----------- | ---------------------------------------------------------------------- |
| `undefined` | 默认，按钮正常可点击，hover 有 tooltip                                 |
| `disabled`  | 按钮显示但不可点击，tooltip 不显示，反馈弹窗无法打开                   |
| `hidden`    | `MessageContainer` 检测到此值时不渲染 `MessageTools`（组件自身不处理） |

> `hidden` 由 `MessageContainer` 在外部用 `v-if` 判断，`MessageTools` 本身不感知该值。

**禁用状态**

```vue
<template>
  <MessageTools
    :message-tools-status="MessageToolsStatus.Disabled"
    :on-action="handleAction"
    @feedback="handleFeedback"
  />
</template>
```

## 自定义 Tippy 配置

反馈弹窗的 `Tippy` 默认配置如下，可通过 `tippyOptions` 覆盖：

```typescript
// 内部默认值
{
  arrow: false,
  interactive: true,
  offset: [0, 6],
  theme: 'ai-chat-box-light light',
  trigger: 'click',
  appendTo: () => document.body,
}
```

```vue
<template>
  <MessageTools
    :on-action="handleAction"
    :tippy-options="tippyOptions"
    @feedback="handleFeedback"
  />
</template>

<script setup lang="ts">
  import { MessageTools, type IToolBtn } from '@blueking/chat-x';

  const tippyOptions = {
    placement: 'top', // 弹窗方向
    offset: [0, 12], // 偏移量
    appendTo: () => document.querySelector('#my-container') || document.body,
  };

  const handleAction = async (tool: IToolBtn) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面'];
    }
  };
  const handleFeedback = (tool: IToolBtn, reasonList: string[], otherReason: string) => {
    console.log('反馈:', tool.id, reasonList);
  };
</script>
```

> **注意**：`content`、`theme`、`getReferenceClientRect`、`triggerTarget` 四个选项由组件内部管理，不可通过 `tippyOptions` 覆盖。

## 在 MessageContainer 中的使用

`MessageContainer` 在每个 Assistant 消息组底部自动渲染 `MessageTools`，无需手动引入：

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="messageStatus"
    :message-tools-status="messageToolsStatus"
    :on-agent-action="handleAgentAction"
    :on-agent-feedback="handleAgentFeedback"
    @stop-streaming="handleStopStreaming"
  />
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { MessageContainer, MessageStatus, MessageToolsStatus, type Message, type IToolBtn } from '@blueking/chat-x';

  const messageStatus = ref(MessageStatus.Complete);

  // 流式输出时禁用工具栏，避免误操作
  const messageToolsStatus = computed(() =>
    messageStatus.value === MessageStatus.Streaming ? MessageToolsStatus.Disabled : undefined,
  );

  // copy 操作由 MessageContainer 内部自动处理（无需在此实现）
  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      return ['回答准确', '信息全面', '表达清晰'];
    }
  };

  const handleAgentFeedback = (tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => {
    console.log('反馈提交:', tool.id, reasonList, otherReason);
  };

  const handleStopStreaming = () => {
    messageStatus.value = MessageStatus.Stop;
  };
</script>
```

## API

### Props

| 属性名             | 类型                                                                                                     | 默认值                | 说明                                                                                                                                 |
| ------------------ | -------------------------------------------------------------------------------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| messageTools       | `IToolBtn[]`                                                                                             | `CONST_MESSAGE_TOOLS` | 左侧工具列表                                                                                                                         |
| updateTools        | `IToolBtn[]`                                                                                             | `CONST_UPDATE_TOOLS`  | 右侧工具列表（`like`/`unlike` 弹反馈表单，`delete` 弹确认框，其他直接触发 `onAction`）                                               |
| messageToolsStatus | `MessageToolsStatus`                                                                                     | —                     | 工具栏状态：`disabled` 禁用按钮和弹窗                                                                                                |
| onAction           | `(tool: IToolBtn, content?: UserMessage['content'], docSchema?: TagSchema) => Promise<string[] \| void>` | —                     | 工具操作回调；`like`/`unlike` 需返回 `string[]` 作为反馈选项；`delete` 确认后触发；`content`、`docSchema` 为可选参数，供上层扩展使用 |
| tippyOptions       | `AITippyProps`                                                                                           | —                     | 覆盖反馈弹窗和删除确认弹窗的默认配置；可覆盖 `placement` 等                                                                          |

### Events

| 事件名   | 参数                                                          | 触发时机                                   |
| -------- | ------------------------------------------------------------- | ------------------------------------------ |
| feedback | `(tool: IToolBtn, reasonList: string[], otherReason: string)` | 用户在反馈表单点击"提交"后触发（not 取消） |

### Slots

| 插槽名  | 作用域参数 | 说明                                             |
| ------- | ---------- | ------------------------------------------------ |
| prepend | —          | 工具图标左侧的附加内容，如用户消息的时间         |
| append  | —          | 工具图标右侧的附加内容，如 AI 消息组的时间       |

## 类型定义

```typescript
import { MessageToolsStatus, type IToolBtn } from '@blueking/chat-x';
import type { Component, VNode } from 'vue';

interface IToolBtn {
  id?: (string & {}) | ToolIcons; // 工具唯一标识；命中 ToolIconsMap 显示内置图标，否则显示 name 文本；支持业务自定义字符串
  name?: string; // 工具名称，无对应图标时显示；也用作 tooltip fallback
  description?: string; // tooltip 文本
  icon?: Component | VNode; // 自定义图标（组件/VNode），优先级高于内置 ToolIconsMap[id]
  hidden?: boolean; // 按 id 合并时隐藏该按钮（仅在 MessageContainer/ChatContainer 合并语义下生效）
  triggerSelection?: boolean; // 标记点击后进入多选态（复用 share 选择流程），确认走 confirmShare
}

enum MessageToolsStatus {
  Disabled = 'disabled', // 禁用：按钮显示但不可点击，弹窗不打开
  Hidden = 'hidden', // 隐藏：由 MessageContainer 外部 v-if 控制，组件本身不处理
}
```

## 关联组件

- [ToolBtn](/components/feedback/tool-btn) — 单项工具按钮
- [UserFeedback](/components/feedback/user-feedback) — 点赞/踩反馈面板
- [DeleteTool](/components/feedback/delete-tool) — 删除二次确认
- [MessageTime](/components/feedback/message-time) — 两端插槽内的消息时间
