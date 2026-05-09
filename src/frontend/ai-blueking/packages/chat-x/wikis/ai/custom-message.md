---
name: 自定义消息类型
slug: custom-message
category: ai
description: >
  通过类型扩展、Slot 机制和 Activity 子类型模式，在 chat-x 中添加自定义消息渲染。
aiSummary: >
  chat-x 提供三级自定义扩展：1) MessageContainer 默认 slot 按 role 分发整条消息，
  2) AssistantMessage 默认 slot 替换正文渲染（toolCalls 仍内置），
  3) Activity 子类型通过 ActivityLayout + activityComponentMap 注册新活动组件。
  类型侧通过 declare global AIBluekingMessageMap/AIBluekingContentMap 声明合并扩展。
  useCustomTab 支持从内容组件动态添加侧栏 Tab 面板。
relatedComponents:
  - slug: message-container
    relation: 自定义消息通过 MessageContainer 的默认 slot 渲染
  - slug: message-render
    relation: MessageRender 内部按 role 分发，未注册的 role 返回 null
  - slug: assistant-message
    relation: AssistantMessage 默认 slot 可替换正文渲染
sinceVersion: '1.0.0'
---

# 自定义消息类型

## 概述

chat-x 提供 **三级扩展机制**，覆盖从「整条消息」到「正文内容块」到「活动子类型」的不同粒度：

| 扩展级别       | 切入点                                    | 适用场景                                     |
| -------------- | ----------------------------------------- | -------------------------------------------- |
| **整条消息**   | `MessageContainer` 默认 slot              | 新增全新的消息角色（如审批单、图表卡片）     |
| **助手正文**   | `AssistantMessage` 默认 slot              | 替换 AI 回复的正文渲染，保留 toolCalls 列表  |
| **活动子类型** | `ActivityLayout` + `activityComponentMap` | 新增 Activity 消息的子类型（如流程、知识库） |

每级扩展均配合 **TypeScript 声明合并** 实现类型安全。

## 类型扩展

### 消息类型扩展

库内通过空接口预留扩展点，业务侧声明合并即可将自定义 `role` 并入 `Message` 联合类型：

```typescript
// 库内定义（messages.ts）
declare global {
  interface AIBluekingMessageMap {}
}
type MessageMap = AIBluekingMessageMap & {
  [MessageRole.Assistant]: AssistantMessage;
  [MessageRole.User]: UserMessage;
  // ... 内置角色
};
type Message = MessageMap[MessageType];

// 业务扩展（如 types/approval.d.ts）
import type { BaseMessage } from '@blueking/chat-x';

interface ApprovalContent {
  title: string;
  status: 'approved' | 'pending' | 'rejected';
  approvers: string[];
}

declare global {
  interface AIBluekingMessageMap {
    approval: BaseMessage<'approval', ApprovalContent>;
  }
}
```

扩展后 `Message` 联合自动包含 `approval` 类型，TypeScript 可在 `switch(message.role)` 后收窄。

### 内容类型扩展

同理，内容块类型通过 `AIBluekingContentMap` 扩展：

```typescript
// 库内定义（contents.ts）
declare global {
  interface AIBluekingContentMap {}
}
type ContentMap = AIBluekingContentMap & {
  [MessageContentType.Text]: string;
  [MessageContentType.FlowAgent]: BkFlowMessageContent;
  // ... 内置内容类型
};

// 业务扩展
declare global {
  interface AIBluekingContentMap {
    chart: { type: 'chart'; chartType: string; data: unknown[] };
  }
}
```

## 第一级：整条消息替换

### MessageContainer 的默认 slot

`MessageContainer` 在遍历 `group.messages` 时为每条消息提供默认 slot：

```vue
<!-- MessageContainer 内部实现 -->
<template v-for="(message, index) in group.messages" :key="index">
  <slot
    name="default"
    v-bind="{ message, messageToolsStatus }"
  >
    <MessageRender
      :message="message"
      ...
    />
  </slot>
</template>
```

**slot 参数**：

- `message` — 当前消息对象（`Message` 类型）
- `messageToolsStatus` — 工具栏状态（控制按钮禁用/隐藏）

未覆盖 slot 时使用内置 `MessageRender`；`MessageRender` 对未注册的 `role` 返回 `null`，因此自定义 `role` **必须在 slot 中处理**。

### 使用示例

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-groups="messageGroups"
  >
    <template #default="{ message, messageToolsStatus }">
      <!-- 自定义角色 -->
      <ApprovalMessage
        v-if="message.role === 'approval'"
        :message="message"
      />
      <!-- 其余回退到内置渲染 -->
      <MessageRender
        v-else
        :message="message"
        :message-tools-status="messageToolsStatus"
      />
    </template>
  </MessageContainer>
</template>

<script setup lang="ts">
  import { MessageContainer, MessageRender, useMessageGroup } from '@blueking/chat-x';
  import { computed, ref as deepRef } from 'vue';
  import ApprovalMessage from './approval-message.vue';

  const messages = deepRef<Message[]>([]);
  const { messageGroups } = useMessageGroup({
    messages: computed(() => messages.value),
    selectedUserMessages: deepRef(undefined),
  });
</script>
```

## 第二级：助手正文替换

### AssistantMessage 的默认 slot

`AssistantMessage` 将正文渲染与 `toolCalls` 渲染分离：

```vue
<!-- AssistantMessage 内部实现 -->
<div class="assistant-message-content">
  <slot v-bind="{ content }">
    <ContentRender :content="content || ''" :status="status" :type="MessageContentType.Text" />
  </slot>
</div>
<!-- toolCalls 始终由 AssistantMessage 自行渲染，不受 slot 影响 -->
<template v-if="toolCalls?.length">
  <ToolcallRender
    v-for="toolCall in toolCalls"
    :key="toolCall.id"
    ...
  />
</template>
```

**slot 参数**：`{ content }` — 助手消息的 `content` 字段。

覆盖默认 slot 后，**只替换正文区域**，工具调用列表仍由组件内部渲染。

### 使用示例

当 AI 回复中包含特殊内容格式（如图表 JSON），可在 `MessageRender` 层传递 slot 到 `AssistantMessage`：

```vue
<MessageContainer :messages="messages" :message-groups="messageGroups">
  <template #default="{ message, messageToolsStatus }">
    <MessageRender :message="message" :message-tools-status="messageToolsStatus">
      <template #default="{ content }">
        <ChartRenderer v-if="isChartContent(content)" :data="content" />
        <ContentRender v-else :content="content || ''" :type="MessageContentType.Text" />
      </template>
    </MessageRender>
  </template>
</MessageContainer>
```

`MessageRender` 仅将 `#default` slot 透传给 `AssistantMessage`，其他角色不受影响。

## 第三级：Activity 子类型

### 模式说明

Activity 消息通过 `activityType` 字段分发到不同的子组件。库内已注册三种子类型：

| activityType         | 组件                  | 用途                                                |
| -------------------- | --------------------- | --------------------------------------------------- |
| `flow_agent`         | `FlowAgentContent`    | BkFlow 流程执行（节点列表、状态统计、节点详情 Tab） |
| `knowledge_rag`      | `KnowledgeRagContent` | 知识库检索（检索摘要 + 引用文档列表）               |
| `reference_document` | `ReferenceDocContent` | 引用文档列表                                        |

分发机制在 `activity-message.vue` 中：

```typescript
const activityComponentMap: Record<string, Component> = {
  [MessageContentType.FlowAgent]: FlowAgentContent,
  [MessageContentType.KnowledgeRag]: KnowledgeRagContent,
  [MessageContentType.ReferenceDocument]: ReferenceDocContent,
};
// <component :is="activityComponentMap[activityType]" />
```

### ActivityLayout：统一外框

所有 Activity 子组件使用 `ActivityLayout` 作为外框，提供：

- **折叠/展开**：`v-model:collapsed`，标题行可点击切换
- **标题 slot**：`#title`，放置图标、状态文字、统计信息
- **内容 slot**：默认 slot，放置展开后的详细内容

```vue
<ActivityLayout v-model:collapsed="collapsed" :activity-type="MessageContentType.FlowAgent">
  <template #title>
    <span class="ai-activity-message-title-icon">
      <AiLoading v-if="isLoading" :size="12" />
      <ArrowRightIcon v-else />
    </span>
    <span class="ai-activity-message-title-text">执行情况: ...</span>
  </template>
  <!-- 展开后的详细内容 -->
  <div class="flow-agent-task-group">...</div>
</ActivityLayout>
```

### 源码案例：FlowAgentContent

`FlowAgentContent` 是最复杂的 Activity 子类型，展示了以下模式：

**Props**：

- `content?: BkFlowMessageContent` — 流程任务数组（每个任务包含 nodes、statistics、task_state 等）
- `status?: MessageStatus` — 消息状态（Pending/Streaming 时显示加载动画）

**内容数据结构**（`BkFlowMessageContent`）：

```typescript
type BkFlowMessageContent = BkFlowTask[];

type BkFlowTask = {
  nodes: Record<string, BkFlowNode>;
  statistics: { state_counts: Record<string, number>; total: number };
  task_id: number;
  task_name: string;
  task_outputs: unknown;
  task_state: string;
};

type BkFlowNode = {
  elapsed_time: number;
  id: string;
  name: string;
  state: string;
  // ...
};
```

**侧栏 Tab 集成**：

`FlowAgentContent` 通过 `useCustomTabConsumer` 注入 `addCustomTab`，点击节点「详情」时动态添加侧栏 Tab：

```typescript
const { addCustomTab } = useCustomTabConsumer<CustomBkFlowTabData>()!;

function handleNodeDetail(task: BkFlowTask, node: BkFlowNode) {
  addCustomTab?.({
    label: node.name,
    name: `${task.task_id}|${node.id}|${node.name}`,
    data: {
      component: BkFlowNodeDetail,      // 渲染组件
      props: { node_id: node.id, task_id: task.task_id, ... }, // 组件 props
    },
  });
}
```

### 源码案例：KnowledgeRagContent

`KnowledgeRagContent` 是最简洁的 Activity 子类型，标准模式：

```vue
<ActivityLayout v-model:collapsed="collapsed">
  <template #title>
    <span class="ai-activity-message-title-icon">
      <AiLoading v-if="isLoading" />
      <DocumentIcon v-else style="font-size: 12px" />
    </span>
    <span class="ai-activity-message-title-text">{{ title }}</span>
  </template>
  <MarkdownContent :content="content?.content || ''" />
  <ReferenceContent :content="content?.referenceDocument || []" />
</ActivityLayout>
```

**要点**：标题根据 `status`（Pending/Streaming → 检索中，否则 → 检索完成）动态切换文字。

## useCustomTab：侧栏面板扩展

### 机制

`ChatContainer` 内部调用 `useCustomTabProvider` 注入 Tab 管理能力，深层组件通过 `useCustomTabConsumer` 消费：

```
ChatContainer
  └── useCustomTabProvider()  ← provide
       └── ResizeLayout #aside
            └── Tab + TabPanel
                 └── ExecutionSummary / 自定义 Tab

FlowAgentContent（深层）
  └── useCustomTabConsumer()  ← inject
       └── addCustomTab({ label, name, data: { component, props } })
```

### CustomTab 类型

```typescript
type CustomTab<T> = {
  label: string; // Tab 显示名
  name: string; // 唯一标识（重复 name 不会重复添加）
  icon?: string;
  data?: {
    component?: Component; // 渲染组件
    props?: T; // 组件 props
  };
};
```

### 行为

- `addCustomTab(tab)`：若 `tabs` 中无同名项则追加，展开侧栏，`nextTick` 后自动选中新 Tab
- `removeCustomTab(name)`：移除并切回默认的「执行情况」Tab
- `selectCustomTab(tab)`：切换选中 Tab

## 扩展决策指南

| 需求                                | 推荐方案                                                 |
| ----------------------------------- | -------------------------------------------------------- |
| 全新消息角色（不是 Assistant 变体） | 第一级：`AIBluekingMessageMap` + `MessageContainer` slot |
| AI 回复中嵌入特殊内容（图表、表格） | 第二级：`AssistantMessage` slot                          |
| 新增 Activity 子类型（如审计日志）  | 第三级：`ActivityLayout` + `activityComponentMap` 注册   |
| 侧栏展示详情面板                    | `useCustomTabConsumer` + `addCustomTab`                  |
| 扩展内容块类型                      | `AIBluekingContentMap` 声明合并                          |

## 相关文档

- [架构总览](../architecture.md) — 渲染管线、MessageRender 分发机制
- [设计理念](../design-philosophy.md) — 类型系统设计、声明合并原理
- [最佳实践](./best-practices.md) — 性能优化、安全规范
