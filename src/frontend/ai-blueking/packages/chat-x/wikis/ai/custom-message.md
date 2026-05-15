---
name: 自定义消息类型
slug: custom-message
category: ai
description: >
  通过类型声明合并、ChatContainer/MessageContainer 插槽、MessageRender 与 ContentRender
  分层扩展，在 chat-x 中实现自定义消息与正文渲染；Activity 子类型与侧栏 Tab 为内置场景。
aiSummary: >
  渲染链：ChatContainer#message → MessageContainer#default → MessageRender 按 role 分发；
  Assistant 可走 #default/#codeHeader 插槽与 ContentRender；Activity 由 activityComponentMap 按 activityType 挂载子组件。
  自定义 role 须 AIBluekingMessageMap 声明合并并在插槽中显式渲染。FlowAgent 通过 useCustomTabConsumer 联动侧栏。
relatedComponents:
  - slug: chat-container
    relation: '#message 插槽为应用层主扩展入口'
  - slug: message-container
    relation: 默认 slot 包裹每条消息的 MessageRender
  - slug: message-render
    relation: 按 MessageRole 分发，未注册 role 返回 null
  - slug: assistant-message
    relation: 正文 default slot，toolCalls 内置渲染
  - slug: activity-message
    relation: activityType 映射 FlowAgent / KnowledgeRag / ReferenceDoc
sinceVersion: '2.1.0'
---

# 自定义消息类型

## 概述

chat-x 的消息渲染是 **由外到内的插槽链 + 按 role 分发**，而不是单一「替换 MessageRender」就能覆盖全部场景。应用集成时最常接触的是 `ChatContainer` 的 **`#message`**；库内默认路径是 `MessageContainer` → `MessageRender` → 各角色组件 → `ContentRender` / Activity 子组件。

```text
ChatContainer
├── #aside … 侧栏 Tab / ExecutionSummary（见侧栏专题文档）
└── #main
     ├── #default（整块主区域，可替换整个 MessageContainer）
     └── MessageContainer
          └── #default（每条 message）← 库内默认挂 MessageRender
               └── [#message] ← ChatContainer 透出；无内容时该条不渲染
                    └── MessageRender（按 message.role 分发）
                         ├── UserMessage / ToolMessage / …
                         ├── AssistantMessage
                         │    ├── #default → ContentRender → MarkdownContent …
                         │    └── toolCalls → ToolCallRender（不受 slot 影响）
                         └── ActivityMessage → activityComponentMap[activityType]
```

扩展时先确定粒度，再选入口（见文末决策表）。

## 类型扩展

### 消息 role：`AIBluekingMessageMap`

库内在 `messages.ts` 预留空接口，与内置 `MessageRole` 合并为 `MessageMap`：

```typescript
// 库内
declare global {
  interface AIBluekingMessageMap {}
}
export type MessageMap = AIBluekingMessageMap & {
  [MessageRole.Assistant]: AssistantMessage;
  [MessageRole.User]: UserMessage;
  [MessageRole.Activity]: ActivityMessage;
  // … 其余内置 role
};
export type Message = MessageMap[MessageType];
```

业务侧声明合并（建议在独立 `*.d.ts`）：

```typescript
import type { BaseMessage } from '@blueking/chat-x';

interface ChartPayload {
  chartType: string;
  series: unknown[];
}

declare global {
  interface AIBluekingMessageMap {
    chart: BaseMessage<'chart', ChartPayload>;
  }
}
```

`MessageRender` 的 `switch (message.role)` **不包含**自定义 role，会落入 `default: return null`。因此 **`chart` 等扩展 role 必须在 `MessageContainer` / `ChatContainer#message` 插槽里自行渲染**。

### 内容块：`AIBluekingContentMap`

用于扩展 `ContentMap`（Assistant 的 `content`、Activity 的 `content` 结构等）：

```typescript
// 库内 contents.ts
declare global {
  interface AIBluekingContentMap {}
}
export type ContentMap = AIBluekingContentMap & {
  [MessageContentType.Text]: string;
  [MessageContentType.FlowAgent]: BkFlowMessageContent;
  [MessageContentType.KnowledgeRag]: KnowledgeRagMessageContent;
  // …
};
```

扩展后可在类型层面约束 `ActivityMessage['content']` 或业务 props，但 **Activity 子组件映射表仍在库内**（见下文 Activity 一节）。

### `BaseMessage` 常用字段

| 字段 | 说明 |
| ---- | ---- |
| `id` / `messageId` | 客户端 / 服务端标识 |
| `role` | `MessageRole` 或扩展 role |
| `content` | 由泛型 `C` 决定结构 |
| `status` | `pending` / `streaming` / `complete` / `error` 等 |
| `uid` | 可选；Activity 会作为 `message-uid` 传给子组件，供侧栏定位 |
| `property.extra` | 快捷指令、引用 `cite`、`pause`（控制 MessageTools）等 |

## 应用层：`ChatContainer` 的 `#message` 插槽

`ChatContainer` 将 `MessageContainer` 的每条消息默认 slot **透传**为具名插槽 `message`：

```vue
<!-- chat-container.vue -->
<MessageContainer ...>
  <template #default="{ message, messageToolsStatus }">
    <slot name="message" v-bind="{ message, messageToolsStatus }" />
  </template>
</MessageContainer>
```

**重要**：chat-x 的 `ChatContainer` **没有**为 `#message` 提供默认回退；插槽为空时该条消息区域不渲染。使用 `ChatContainer` 时应：

- 在 `#message` 内渲染 `MessageRender`（并透传必要 props），或
- 使用 `@blueking/ai-blueking` 的 `ChatBot`（内部在未提供外层 `#message` 时自动回退 `MessageRender`）

### 推荐写法（含 `codeHeader`）

Playground [`chat-bot-new.vue`](../../playground/chat-bot-new.vue) 与 ai-blueking `ChatBot` 均采用此模式：

```vue
<ChatContainer :messages="messages" ...>
  <template #message="{ message, messageToolsStatus }">
    <MessageRender
      :message="message"
      :message-tools-status="messageToolsStatus"
      :on-action="tool => handleUserAction(tool, message)"
      :on-input-confirm="(content, docSchema) => handleUserInputConfirm(message, content, docSchema)"
      :on-shortcut-confirm="formModel => handleUserShortcutConfirm(message, formModel)"
      :tippy-options="commonTippyOptions"
    >
      <template #codeHeader="{ language, token }">
        <span @click="onInsert(language)">插入</span>
      </template>
    </MessageRender>
  </template>
</ChatContainer>
```

自定义整条消息时，在 `#message` 内分支 `message.role`，**其余 role 仍交给 `MessageRender`**，避免漏掉用户消息工具链（删除/编辑/复制/引用等）：

```vue
<template #message="{ message, messageToolsStatus }">
  <ChartMessage v-if="message.role === 'chart'" :message="message" />
  <MessageRender
    v-else
    :message="message"
    :message-tools-status="messageToolsStatus"
    :on-action="..."
    :on-input-confirm="..."
    :on-shortcut-confirm="..."
  />
</template>
```

> 若自定义 `#message` 却未向 `MessageRender` 传递 `on-action` / `on-input-confirm` / `on-shortcut-confirm`，用户消息工具栏会失效；AI 消息工具栏在 `MessageContainer` 内独立渲染，不受影响。

更复杂的「Markdown 内嵌自定义块」可参考 ai-blueking Playground `CustomMessageSlotView`：解析 ` ```custom-component ` 等 fence 后，在 `#message` 内混合 `MessageRender` 与业务组件。

## `MessageContainer` 默认 slot

直接使用 `MessageContainer`（不经过 `ChatContainer`）时，每条消息有带默认内容的 slot：

```vue
<MessageContainer :message-groups="messageGroups" :messages="messages" ...>
  <template #default="{ message, messageToolsStatus }">
    <ApprovalCard v-if="message.role === 'approval'" :message="message" />
    <MessageRender
      v-else
      :message="message"
      :message-tools-status="messageToolsStatus"
      ...
    />
  </template>
</MessageContainer>
```

未覆盖 slot 时使用内置 `MessageRender`（已绑定 `on-action`、`on-input-confirm` 等）。

## `MessageRender`：按 role 分发

实现为 `computed` + `h()`，根据 `message.role` 创建对应组件（`message-render.vue`）：

| `MessageRole` | 组件 |
| ------------- | ---- |
| `user` | `UserMessage` |
| `assistant` | `AssistantMessage`（支持 default / codeHeader 插槽） |
| `activity` | `ActivityMessage` |
| `tool` | `ToolMessage` |
| `reasoning` | `ReasoningMessage` |
| `info` | `InfoMessage` |
| `loading` | `LoadingMessage` |
| 其他 / 扩展 role | `null`（不渲染） |

### 插槽

```typescript
defineSlots<{
  /** 仅 Assistant 链路：替换正文 */
  default: (props: { content: string; status: MessageStatus }) => VNode;
  /** Markdown 代码块头部，透传至 ContentRender → MarkdownContent */
  codeHeader: (props: { language: string; token: Token[] }) => VNode;
}>();
```

Assistant 分支将 `default` 传给 `AssistantMessage`，默认内容为 `ContentRender`：

```typescript
h(AssistantMessage, props.message, {
  default: slotProps =>
    renderSlot(slots, 'default', slotProps, () => [
      h(ContentRender, {
        content: props.message.content || '',
        status: props.message.status,
      }, slots.codeHeader ? { codeHeader: ... } : undefined),
    ]),
});
```

## 助手正文：`AssistantMessage` + `ContentRender`

### `AssistantMessage`

- **`#default` slot**：参数 `{ content }`，用于替换正文。
- **`toolCalls`**：始终在组件内用 `ToolCallRender` 列表渲染，**不受** default slot 影响。

### `ContentRender`

根据 `content` 形态与 `type` 选择子组件：

| 条件 | 渲染 |
| ---- | ---- |
| `content` 为 `string` 或 `type === text` | `MarkdownContent`（流式补全、Mermaid、LaTeX、代码高亮） |
| `content` 为数组 | `ReferenceContent`（引用文档列表） |
| 其他 | `undefined`（需通过 slot 或上层自定义） |

`ContentRender` 自带 **`#default`** slot（参数 `{ content }`），可在 `MessageRender#default` 内进一步包装：

```vue
<MessageRender :message="message" ...>
  <template #default="{ content }">
    <ContentRender :content="content" :status="message.status">
      <template #default="{ content: c }">
        <MyChart v-if="isChart(c)" :data="c" />
        <MarkdownContent v-else :content="String(c)" :status="message.status" />
      </template>
    </ContentRender>
  </template>
</MessageRender>
```

### `codeHeader`：代码块头部

插槽链路：`MessageRender` → `ContentRender` → `MarkdownContent` → `CodeContent#header`。

用于「插入 / 应用 / 复制」等操作，见 Playground `chat-bot-new.vue` 与 ai-blueking `ChatBot` / `AIBlueking` 的 `#codeHeader` 透传。

## Activity 消息与子类型

### 消息结构

```typescript
interface ActivityMessage extends BaseMessage<MessageRole.Activity, Flow | KnowledgeRag | ReferenceDocument> {
  activityType:
    | MessageContentType.FlowAgent
    | MessageContentType.KnowledgeRag
    | MessageContentType.ReferenceDocument
    | string;
}
```

`ActivityMessage` 将 `uid` 以 **`message-uid`** 传给子组件，供 `addCustomTab({ data: { messageUid } })` 与侧栏「在对话中定位」使用。

### 内置 `activityComponentMap`

在 `activity-message.vue` 中 **硬编码**（当前不支持应用层注册）：

| `activityType`（`MessageContentType`） | 组件 | 用途 |
| -------------------------------------- | ---- | ---- |
| `flow_agent` | `FlowAgentContent` | BkFlow 任务/节点、侧栏详情 Tab |
| `knowledge_rag` | `KnowledgeRagContent` | 检索摘要 + 引用 |
| `reference_document` | `ReferenceDocContent` | 引用文档列表 |

```typescript
const activityComponentMap: Record<string, Component> = {
  [MessageContentType.FlowAgent]: FlowAgentContent,
  [MessageContentType.KnowledgeRag]: KnowledgeRagContent,
  [MessageContentType.ReferenceDocument]: ReferenceDocContent,
};
// activityType 不在 map 中 → 不渲染（v-if="activityComponent"）
```

新增 Activity 子类型需要 **修改 chat-x 源码**（增加组件并写入 `activityComponentMap`），或改用 **自定义 `message.role` + `#message` 插槽** 完全自绘。

### `ActivityLayout`

Flow / KnowledgeRag 等子组件的外框：

- `v-model:collapsed` 折叠
- `#title`：标题行（图标、状态文案）
- 默认 slot：展开区内容
- `activityType === flow_agent` 时标题栏不显示右侧折叠箭头（Flow 自有交互）

### FlowAgent 要点（`FlowAgentContent`）

- **内容类型**：`BkFlowMessageContent` = `BkFlowTask[]`（`task_id`、`nodes`、`statistics`、`has_confidence`、`is_active`、`task_tab` 等）
- **侧栏 Tab**：`useCustomTabConsumer()` → `addCustomTab` / `removeCustomTab`
  - 任务 Tab：`name = String(task_id)`
  - 节点 Tab：`name = \`${task_id}|${node.id}|${node.name}\``
  - 有效证据：`has_confidence` + 独立 Tab
  - `is_active && task_tab` 时首次自动 `openTaskTab`
  - 组件在 `MessageContainer` 内卸载时批量 `removeCustomTab`
- **默认详情组件**：`BkFlowNodeDetail`（需 `<slot name="locateButton" />`）
- **应用覆盖**：`ChatContainer` 的 `getSideRenderComponent` / `onCustomTabChange`（详见侧栏文档）

KnowledgeRag / ReferenceDoc 模式见 [ActivityMessage](../components/molecular/activity-message.md)。

## 侧栏自定义 Tab（与消息联动）

Activity（尤其 FlowAgent）可在对话区点击「详情」等操作，通过 **`useCustomTabConsumer`** 在 `ChatContainer` 侧栏追加 Tab；数据加载与内容/标签自定义由容器 Props 完成。

| 文档 | 内容 |
| ---- | ---- |
| [自定义侧栏内容](./custom-side-content.md) | `getSideRenderComponent`、`onCustomTabChange`、`locateButton` |
| [自定义侧栏 Tab 标签](./custom-side-tab.md) | `getSideTabRenderComponent` |
| [useCustomTab](../composables/use-custom-tab.md) | Provider / Consumer API |

## 扩展决策指南

| 需求 | 推荐方案 |
| ---- | -------- |
| 集成 ChatContainer，仅改代码块头部 | `#message` + `MessageRender#codeHeader` |
| 集成 ChatContainer，替换部分 Assistant 正文 | `#message` + `MessageRender#default` / 内层 `ContentRender#default` |
| 全新 `message.role`（审批、图表卡片等） | `AIBluekingMessageMap` + `#message` 或 `MessageContainer#default` 分支 + 自建组件 |
| 仅直接使用 MessageContainer | `#default` slot + 同上 |
| 新增 Activity 子类型（flow 同类） | 改库 `activity-message.vue` 的 map，或改用自定义 role |
| Flow 节点/任务详情 + 侧栏 | 使用内置 FlowAgent + `onCustomTabChange` / `getSideRenderComponent` |
| 扩展 Assistant 结构化 content 类型 | `AIBluekingContentMap` + `ContentRender` slot / 自定义渲染 |

## 相关文档

- [自定义侧栏 Tab 标签](./custom-side-tab.md)
- [自定义侧栏内容](./custom-side-content.md)
- [ChatContainer](../components/molecular/chat-container.md)
- [ActivityMessage](../components/molecular/activity-message.md)
- [useCustomTab](../composables/use-custom-tab.md)
- [架构总览](../architecture.md)
- [最佳实践](./best-practices.md)
