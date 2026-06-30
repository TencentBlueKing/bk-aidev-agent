---
name: ActivityMessage 活动消息
slug: activity-message
category: molecular
description: >-
  活动消息组件，用于展示 AI 的知识检索（Knowledge RAG）过程、参考文档引用列表和 FlowAgent 流程执行情况。通过
  `activityType` 切换三种工作模式，点击标题栏可折叠/展开内容区域。
aiSummary: >
  ActivityMessage 展示活动类消息：知识检索（knowledge_rag）、引用文档列表、FlowAgent 执行（activityType 区分），标题可折叠。
  content 结构随模式变化。由 MessageRender 在 activity 角色下渲染，用于 RAG/引用/流程执行过程可视化。
relatedComponents:
  - slug: message-render
    relation: 由 MessageRender 在 role 为 activity 时创建
  - slug: assistant-message
    relation: 常与助手回复相邻，描述检索或执行背景
sinceVersion: 1.0.0
domain: message
---

<script lang="ts" setup>
  import { ref } from 'vue'
  import ActivityMessageComp from '../../../src/components/chat-message/activity-message/activity-message.vue'

  // 引用文档列表
  const refDocs = [
    { name: 'Vue 3 组合式 API 指南', url: 'https://example.com/vue3-composition', originFile: 'vue3-composition.md' },
    { name: 'TypeScript 高级类型手册', url: 'https://example.com/ts-advanced', originFile: 'ts-advanced.pdf' },
    { name: '蓝鲸前端开发规范 v2.0', url: 'https://example.com/bk-standard', originFile: 'bk-standard.docx' },
  ];

  // 知识检索结果（单引用）
  const ragContent = {
    content: '根据知识库检索，Vue 3 引入了 Composition API，提供了一种更灵活的方式来组织组件逻辑。与 Options API 相比，开发者可以按照逻辑关注点来组织代码，而不是按选项类型（data、methods、computed 等）分割。',
    referenceDocument: [
      { name: '知识库文档：Composition API 详解', url: 'https://example.com/kb1', originFile: 'kb1.md' },
    ],
  };

  // 知识检索结果（多引用 + Markdown）
  const ragContentMultiRef = {
    content: '经过知识库检索，以下是关于**蓝鲸智云 (BK-CI)** 持续集成平台的核心概念：\n\n1. **流水线 (Pipeline)**：用于编排 CI/CD 任务的核心组件\n2. **模板 (Template)**：可复用的流水线配置片段\n3. **凭证管理 (Credential)**：安全存储敏感信息的机制',
    referenceDocument: [
      { name: 'BK-CI 用户指南', url: 'https://example.com/bkci-guide', originFile: 'bkci-guide.md' },
      { name: '流水线配置参考', url: 'https://example.com/pipeline-ref', originFile: 'pipeline-ref.pdf' },
      { name: '最佳实践手册', url: 'https://example.com/best-practice', originFile: 'best-practice.docx' },
    ],
  };

  const collapsedRef = ref(false);
  const collapsedCollapsed = ref(true);
</script>

# ActivityMessage 活动消息

> **层级**：分子组件 · **功能域**：消息展示

活动消息组件，用于展示 AI 的知识检索（Knowledge RAG）过程、参考文档引用列表和 FlowAgent 流程执行情况。通过 `activityType` 切换三种工作模式，点击标题栏可折叠/展开内容区域。

组件会将父级传入消息上的 **`uid`** 以 **`message-uid`** 形式透传给各活动子组件（`FlowAgentContent` / `KnowledgeRagContent` / `ReferenceDocContent`），用于侧栏自定义 Tab、`addCustomTab` 的 `data.messageUid` 与主对话区「在对话中定位」联动（详见 [ChatContainer](./chat-container.md)）。

## 三种工作模式

组件根据 `activityType` 的值决定渲染模式：

| `activityType`    | 模式           | 标题文案                             | 图标             | 内容区                              |
| ----------------- | -------------- | ------------------------------------ | ---------------- | ----------------------------------- |
| `'knowledge_rag'` | 知识检索模式   | 检索中 / 检索完成（随 status 切换）  | Loading / 文档   | Markdown 检索摘要 + 引用列表        |
| `'flow_agent'`    | FlowAgent 模式 | 执行情况: 成功 N / 失败 N / 执行中 N | Loading / 箭头   | 任务节点树 + 节点详情（自定义 Tab） |
| 其他任意值        | 引用文档模式   | 引用 N 篇资料作为参考                | 文档图标（固定） | 引用文档列表                        |

> **注意：** 只有值严格等于 `'knowledge_rag'` 才进入知识检索模式；严格等于 `'flow_agent'`（`MessageContentType.FlowAgent`）才进入 FlowAgent 模式；其他值均按引用文档模式处理。

## 引用文档模式

`activityType` 传入 `MessageContentType.ReferenceDocument`（`'reference_document'`）或任意非 `'knowledge_rag'` 的值，`content` 传入文档对象数组。

标题自动显示文档数量，始终展示文档图标，`status` 不影响标题和图标。

```vue
<template>
  <ActivityMessage
    v-model:collapsed="collapsed"
    :content="docs"
    status="complete"
    :activity-type="MessageContentType.ReferenceDocument"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ActivityMessage, MessageContentType, MessageStatus } from '@blueking/chat-x';

  const collapsed = ref(false);

  const docs = [
    {
      name: 'Vue 3 组合式 API 指南',
      url: 'https://cn.vuejs.org/guide/extras/composition-api-faq.html',
      originFile: 'composition-api.md',
    },
    { name: 'TypeScript 高级类型手册', url: 'https://www.typescriptlang.org/docs/', originFile: 'ts-advanced.pdf' },
    { name: '蓝鲸前端开发规范 v2.0', url: 'https://example.com/bk-standard', originFile: 'bk-standard.docx' },
  ];
</script>
```

**渲染效果**

<div class="demo">
  <ActivityMessageComp
    v-model:collapsed="collapsedRef"
    :content="refDocs"
    status="complete"
    activity-type="reference_document"
  />
</div>

## 知识检索模式

`activityType` 设为 `MessageContentType.KnowledgeRag`（`'knowledge_rag'`），`content` 传入包含 `content`（检索摘要）和 `referenceDocument`（引用文档列表）的对象。

标题和图标随 `status` 动态变化：

| `status`                | 图标     | 标题     |
| ----------------------- | -------- | -------- |
| `pending` / `streaming` | Loading  | 检索中   |
| 其他（`complete` 等）   | 文档图标 | 检索完成 |

```vue
<template>
  <ActivityMessage
    v-model:collapsed="collapsed"
    :content="ragContent"
    :status="status"
    :activity-type="MessageContentType.KnowledgeRag"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ActivityMessage, MessageContentType, MessageStatus } from '@blueking/chat-x';

  const collapsed = ref(false);
  const status = ref(MessageStatus.Complete);

  const ragContent = {
    // 检索摘要（支持 Markdown）
    content: '根据知识库检索，Vue 3 引入了 Composition API...',
    // 引用文档列表
    referenceDocument: [
      { name: '知识库文档：Composition API 详解', url: 'https://example.com/kb1', originFile: 'kb1.md' },
    ],
  };
</script>
```

**渲染效果（检索完成 + 单引用）**

<div class="demo">
  <ActivityMessageComp
    :content="ragContent"
    status="complete"
    activity-type="knowledge_rag"
  />
</div>

**渲染效果（检索完成 + 多引用 + Markdown 摘要）**

<div class="demo">
  <ActivityMessageComp
    :content="ragContentMultiRef"
    status="complete"
    activity-type="knowledge_rag"
  />
</div>

## 状态变化（知识检索模式）

`knowledge_rag` 模式下，`status` 决定图标和标题文案：

**检索中（`pending`）**

<div class="demo">
  <ActivityMessageComp
    :content="ragContent"
    status="pending"
    activity-type="knowledge_rag"
  />
</div>

**检索中（`streaming`）**

<div class="demo">
  <ActivityMessageComp
    :content="ragContent"
    status="streaming"
    activity-type="knowledge_rag"
  />
</div>

**检索完成（`complete`）**

<div class="demo">
  <ActivityMessageComp
    :content="ragContent"
    status="complete"
    activity-type="knowledge_rag"
  />
</div>

> **引用文档模式**不受 `status` 影响，始终显示文档图标和文档数量，不会出现 Loading 动画。

## 折叠/展开

通过 `v-model:collapsed` 控制内容区的折叠状态，点击整个标题栏均可切换。默认为 `false`（展开）。

```vue
<template>
  <!-- 默认展开 -->
  <ActivityMessage
    v-model:collapsed="collapsed"
    :content="docs"
    status="complete"
    activity-type="reference_document"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ActivityMessage } from '@blueking/chat-x';

  const collapsed = ref(false); // false = 展开，true = 折叠
  const docs = [{ name: '参考文档', url: 'https://example.com/doc', originFile: 'doc.pdf' }];
</script>
```

**渲染效果（展开状态）**

<div class="demo">
  <ActivityMessageComp
    v-model:collapsed="collapsedRef"
    :content="refDocs"
    status="complete"
    activity-type="reference_document"
  />
</div>

**渲染效果（折叠状态）**

<div class="demo">
  <ActivityMessageComp
    v-model:collapsed="collapsedCollapsed"
    :content="refDocs"
    status="complete"
    activity-type="reference_document"
  />
</div>

## FlowAgent 执行情况模式

`activityType` 设为 `MessageContentType.FlowAgent`（`'flow_agent'`），`content` 传入 `BkFlowMessageContent` 任务数组。用于展示一个或多个蓝鲸标准运维（BkFlow）任务的执行状态、节点列表和统计信息。

### 核心交互

- **标题栏**：显示「执行情况」+ 所有任务聚合后的各状态计数（执行中 / 成功 / 失败 / 挂起），颜色区分
- **任务组**：逐个展示任务行，带状态图标、总耗时；点击箭头图标可折叠/展开节点列表
- **有效证据**：`task.has_confidence === true` 时，任务行右侧展示「有效证据」按钮，点击后在侧栏打开置信度/证据详情 Tab（`props.has_confidence: true`）
- **默认激活**：当 `MessageContainer` 已注入滚动上下文（`useContainerScrollProvider`，供 `FlowAgentContent` 内 `useContainerScrollConsumer` 读取）时，组件挂载后若存在 `task.is_active === true` 且 `task.has_confidence === true` 的任务，会自动在侧栏打开该任务的「有效证据」Tab；无滚动 Provider（例如独立演示）时不做自动打开。用户手动切换 Tab 后不再沿用 `is_active` 默认高亮
- **选中态**：当前侧栏 Tab 与任务行 / 节点行联动高亮（`is-selected`）；任务 Tab 与「有效证据」Tab 均视为该任务的选中态
- **节点列表**：每个节点显示状态圆点、名称和耗时；hover 时出现「详情」按钮
- **节点详情**：点击「详情」会通过 `useCustomTabConsumer` 在 `ChatContainer` 侧边栏新增自定义 Tab，展示节点配置（基础信息、输入参数、输出参数）

> `FlowAgentContent` 会读取 `ChatContainer` 注入的 `renderMode`。当 `renderMode === RenderMode.Share` 时，任务行不展示总耗时与「有效证据」，节点列表不展示耗时与「详情」按钮，避免分享预览中出现可交互入口。独立使用 `ActivityMessage` 且没有上层 Provider 时，默认按 `Chat` 模式渲染。

### 内部渲染结构

```
FlowAgentContent（activityType = 'flow_agent'）
├── ActivityLayout（公共折叠布局容器）
│   └── #title
│       ├── Loading / ArrowIcon（随 status 切换）
│       └── 执行情况：执行中 N / 成功 N / 失败 N / 挂起 N
└── #default
    └── TaskGroup × N
        ├── TaskHeader（is-selected / has-confidence；箭头点击折叠）
        │   ├── 状态图标（running=Loading / success / failed / suspended）
        │   ├── task_name（HighlightKeyword 支持搜索高亮）
        │   └── trailing：总耗时 + 「有效证据」（has_confidence 时）
        └── NodeList
            └── NodeItem × N（is-selected 与侧栏 Tab 联动）
                ├── 状态圆点（颜色对应状态）
                ├── node.name（HighlightKeyword 支持搜索高亮）
                ├── node.elapsed_time
                └── 详情按钮（hover 显示）→ 打开节点详情 Tab
```

### 用法示例

```vue
<template>
  <ActivityMessage
    v-model:collapsed="collapsed"
    :content="flowContent"
    :status="status"
    :activity-type="MessageContentType.FlowAgent"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ActivityMessage, MessageContentType, MessageStatus } from '@blueking/chat-x';
  import type { BkFlowMessageContent } from '@blueking/chat-x';

  const collapsed = ref(false);
  const status = ref(MessageStatus.Complete);

  const flowContent: BkFlowMessageContent = [
    {
      task_id: 100,
      task_name: '数据清洗流程',
      task_state: 'FINISHED',
      task_outputs: [],
      statistics: {
        total: 3,
        state_counts: { FINISHED: 2, FAILED: 1 },
      },
      nodes: {
        node1: {
          id: 'node1',
          name: '数据拉取',
          state: 'FINISHED',
          elapsed_time: 12,
          start_time: '2025-01-01 10:00:00',
          finish_time: '2025-01-01 10:00:12',
          loop: 1,
          retry: 0,
          skip: false,
          type: 'ServiceActivity',
        },
        node2: {
          id: 'node2',
          name: '数据转换',
          state: 'FINISHED',
          elapsed_time: 45,
          start_time: '2025-01-01 10:00:12',
          finish_time: '2025-01-01 10:00:57',
          loop: 1,
          retry: 0,
          skip: false,
          type: 'ServiceActivity',
        },
        node3: {
          id: 'node3',
          name: '结果写入',
          state: 'FAILED',
          elapsed_time: 3,
          start_time: '2025-01-01 10:00:57',
          finish_time: '2025-01-01 10:01:00',
          loop: 1,
          retry: 0,
          skip: false,
          type: 'ServiceActivity',
        },
      },
    },
  ];
</script>
```

### 在 MessageContainer 中自动渲染

```typescript
const messages = [
  {
    id: '3',
    role: 'activity',
    activityType: MessageContentType.FlowAgent, // 'flow_agent'
    status: MessageStatus.Streaming,
    content: [
      {
        task_id: 100,
        task_name: '数据清洗流程',
        task_state: 'RUNNING',
        task_outputs: [],
        statistics: { total: 3, state_counts: { RUNNING: 1, FINISHED: 2 } },
        nodes: {
          /* ... */
        },
      },
    ],
  },
];
```

### 节点状态映射

组件内部将 BkFlow 原始状态归并为四种显示状态：

| 归并状态    | 原始状态                                                                            | 颜色    |
| ----------- | ----------------------------------------------------------------------------------- | ------- |
| `running`   | CREATED / LOOP_READY / READY / RUNNING / BLOCKED / ROLLING_BACK / ROLL_BACK_SUCCESS | #3A84FF |
| `success`   | FINISHED                                                                            | #18B456 |
| `failed`    | FAILED / REVOKED / ROLL_BACK_FAILED                                                 | #EA3636 |
| `suspended` | SUSPENDED                                                                           | #F59500 |
| `pending`   | PENDING                                                                             | #DCDEE5 |

### 侧栏 Tab 命名规则

| 场景       | `tab.name` 格式                          |
| ---------- | ---------------------------------------- |
| 任务详情   | `{task_id}`                              |
| 有效证据   | `{task_id}`（与任务 Tab 同名，label 为「有效证据」，`order: 10` 固定排在「执行情况」之后、节点详情之前） |
| 节点详情   | `{task_id}\|{node.id}\|{node.name}`      |

`CustomBkFlowTabData` 支持 `has_confidence?: boolean`，用于侧栏详情组件区分证据视图与节点视图。应用层可通过 `ChatContainer` 的 `getSideRenderComponent` 覆盖渲染组件。

### 节点详情 Tab

点击节点的「详情」按钮，内部调用 `useCustomTabConsumer().addCustomTab()` 在 `ChatContainer` 侧边栏新开一个 Tab，渲染 `BkFlowNodeDetail`（或 `getSideRenderComponent` 返回的自定义组件），该组件提供：

- **节点配置** Tab：基础信息表单（流程模板、节点名称、步骤名称、失败处理、超时控制）+ 输入参数表 + 输出参数表
- **节点输出** Tab：结构化输出参数表
- **骨架屏**：`loading` 为 `true` 时展示骨架屏占位

### 相关类型定义

```typescript
import { MessageContentType, type BkFlowMessageContent, type BkFlowNode, type BkFlowTask } from '@blueking/chat-x';

type BkFlowMessageContent = BkFlowTask[];

type BkFlowTask = {
  has_confidence?: boolean; // 是否展示「有效证据」入口；与 is_active 同时为 true 且在消息容器滚动上下文中时，挂载后自动打开「有效证据」侧栏 Tab
  is_active?: boolean; // 是否默认激活；需配合 has_confidence 且存在滚动 Provider 才会自动打开侧栏「有效证据」Tab
  nodes: Record<string, BkFlowNode>;
  statistics: { state_counts: Record<string, number>; total: number };
  task_id: number;
  task_name: string;
  task_outputs: unknown;
  task_state: string;
};

type BkFlowNode = {
  elapsed_time: number;
  finish_time: string;
  id: string;
  loop: number;
  name: string;
  retry: number;
  skip: boolean;
  start_time: string;
  state: string;
  type: string;
};

enum MessageContentType {
  FlowAgent = 'flow_agent',
  KnowledgeRag = 'knowledge_rag',
  ReferenceDocument = 'reference_document',
  // ...
}
```

## 在 MessageContainer 中使用

`ActivityMessage` 通常不需要单独使用，`MessageContainer` 会对 `role: 'activity'` 的消息自动渲染：

```vue
<template>
  <MessageContainer :messages="messages" />
</template>

<script setup lang="ts">
  import { MessageContainer, MessageContentType, MessageStatus } from '@blueking/chat-x';

  const messages = [
    // 知识检索消息
    {
      id: '1',
      role: 'activity',
      activityType: MessageContentType.KnowledgeRag, // 'knowledge_rag'
      status: MessageStatus.Complete,
      content: {
        content: '根据知识库检索到以下相关信息...',
        referenceDocument: [{ name: '文档A', url: 'https://example.com/a', originFile: 'a.md' }],
      },
    },
    // 引用文档消息
    {
      id: '2',
      role: 'activity',
      activityType: MessageContentType.ReferenceDocument, // 'reference_document'
      status: MessageStatus.Complete,
      content: [
        { name: '参考文档1', url: 'https://example.com/doc1', originFile: 'doc1.pdf' },
        { name: '参考文档2', url: 'https://example.com/doc2', originFile: 'doc2.pdf' },
      ],
    },
  ];
</script>
```

## API

### Props

| 属性名       | 类型                                                                        | 默认值 | 说明                                                      |
| ------------ | --------------------------------------------------------------------------- | ------ | --------------------------------------------------------- |
| content      | `ReferenceDocumentContent[] \| KnowledgeRagContent \| BkFlowMessageContent` | -      | 内容数据，格式随 `activityType` 不同                      |
| activityType | `'knowledge_rag' \| 'flow_agent' \| 'reference_document' \| string`         | -      | 活动类型，决定渲染模式（知识检索 / FlowAgent / 引用文档） |
| status       | `MessageStatus`                                                             | -      | 消息状态；在 `knowledge_rag` 模式下影响标题和图标，在 `flow_agent` 模式下影响标题 Loading 状态 |
| id           | `string \| number`                                                          | -      | 消息 ID                                                   |
| messageId    | `string \| number`                                                          | -      | 消息唯一标识                                              |

### v-model

| 属性名    | 类型      | 默认值  | 说明                        |
| --------- | --------- | ------- | --------------------------- |
| collapsed | `boolean` | `false` | 内容折叠状态，`true` 为折叠 |

## 类型定义

```typescript
import { MessageContentType } from '@blueking/chat-x';

// 引用文档条目
type ReferenceDocumentContent = {
  name: string; // 文档名称（显示文本）
  url: string; // 文档访问链接
  originFile: string; // 原始文件名
};

// 知识检索内容（knowledge_rag 模式）
interface KnowledgeRagContent {
  content: string; // 检索摘要，支持 Markdown
  referenceDocument: ReferenceDocumentContent[]; // 引用文档列表
}

// activityType 枚举值
enum MessageContentType {
  FlowAgent = 'flow_agent',
  KnowledgeRag = 'knowledge_rag',
  ReferenceDocument = 'reference_document',
  // ...
}
```

## 使用场景

- **知识检索过程**：以 `knowledge_rag` 模式展示 RAG 检索全过程，从"检索中"到"检索完成"的状态流转
- **参考资料引用**：以 `reference_document` 模式展示 AI 回复所引用的参考文档列表
- **FlowAgent 执行监控**：以 `flow_agent` 模式展示 BkFlow 流程执行状态、节点列表和详情
- **流式场景**：`pending` → `streaming` → `complete` 状态变化配合流式响应实时更新
- **自动渲染**：通过 `MessageContainer` 或 `MessageRender` 自动处理 `role: 'activity'` 消息，无需手动引入

## 关联组件

- [MessageRender](./message-render.md) — activity 角色由其实例化
- [AssistantMessage](./assistant-message.md) — 常与助手主回复配合出现
