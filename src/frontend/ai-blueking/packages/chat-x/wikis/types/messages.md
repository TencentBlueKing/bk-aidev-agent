---
name: 消息类型
slug: messages
category: type
description: '`@blueking/chat-x` 提供了完整的消息类型定义，用于构建 AI 对话消息。'
aiSummary: >
  文档说明 Message 联合类型、BaseMessage、MessageRole、MessageStatus、User/Assistant/Tool/Activity/Reasoning 等具体形态及 MessageContentType。
  业务构造 messages 数组供 ChatContainer/MessageContainer 渲染；Tool 消息经 useMessageGroup 注入 Assistant。可声明合并扩展 AIBluekingMessageMap。
relatedComponents:
  - slug: message-container
    relation: 列表渲染与工具栏
  - slug: message-render
    relation: 按 role 分发渲染
  - slug: chat-container
    relation: 数据源与交互入口
sinceVersion: 1.0.0
---

# 消息类型

> **分类**：type

`@blueking/chat-x` 提供了完整的消息类型定义，用于构建 AI 对话消息。

## 消息基础类型

### Message

所有消息类型的联合类型：

```typescript
type Message = MessageMap[MessageType];
```

### BaseMessage

消息基础接口：

```typescript
interface BaseMessage<T extends MessageType, C = string> {
  // 消息唯一 ID（客户端生成）
  id: number | string;

  // 消息 ID（服务端返回）
  messageId: number | string;

  // 消息角色
  role: T;

  // 消息内容
  content: C;

  // 消息状态
  status: MessageStatus;

  // 可选：单条消息实例唯一标识（`useMessageGroup` 在缺失时会自动生成并写回）
  uid?: string;

  // 消息名称（可选）
  name?: string;

  // 消息属性（可选）
  property?: {
    extra?: {
      // 引用内容
      cite:
        | string
        | {
            title: string;
            data: { key: string; value: string }[];
            type: 'structured';
          };
      // 快捷指令名称
      command: string;
      // 上下文信息
      context: Record<string, any>[];
      // 快捷指令配置
      shortcut?: Shortcut;
      // 暂停标记：为 true 时该消息所在消息组不显示 MessageTools 工具栏
      pause?: boolean;
    };
  };
}
```

## 消息角色

```typescript
enum MessageRole {
  // 用户消息
  User = 'user',

  // AI 助手消息
  Assistant = 'assistant',

  // 系统消息
  System = 'system',

  // 开发者消息
  Developer = 'developer',

  // 引导消息
  Guide = 'guide',

  // 隐藏消息（不显示）
  Hidden = 'hidden',
  HiddenAssistant = 'hidden-assistant',
  HiddenGuide = 'hidden-guide',
  HiddenSystem = 'hidden-system',
  HiddenUser = 'hidden-user',

  // 信息消息
  Info = 'info',

  // human-in-the-loop 中断消息
  Interrupt = 'interrupt',

  // 加载中消息
  Loading = 'loading',

  // 暂停消息
  Pause = 'pause',

  // 占位消息
  Placeholder = 'placeholder',

  // 推理过程消息
  Reasoning = 'reasoning',

  // 模板消息
  TemplateAssistant = 'template-assistant',
  TemplateGuide = 'template-guide',
  TemplateHidden = 'template-hidden',
  TemplateSystem = 'template-system',
  TemplateUser = 'template-user',

  // 工具调用消息
  Tool = 'tool',

  // 活动消息（如引用文档）
  Activity = 'activity',
}
```

## 消息状态

```typescript
enum MessageStatus {
  // 已完成
  Complete = 'complete',

  // 已完成（与 Complete 同义，兼容协议/后端返回的 completed）
  Completed = 'completed',

  // 已禁用
  Disabled = 'disabled',

  // 错误
  Error = 'error',

  // 请求中
  Fetching = 'fetching',

  // 等待中
  Pending = 'pending',

  // 已停止
  Stop = 'stop',

  // 停止请求中
  StopLoading = 'stop-loading',

  // 流式输出中
  Streaming = 'streaming',

  // 成功
  Success = 'success',
}
```

完整取值与说明见 [常量枚举 · MessageStatus](./constants#messagestatus)。

## 具体消息类型

### UserMessage

用户消息：

```typescript
type UserMessage = BaseMessage<MessageRole.User, InputContent[] | string>;

// 示例
const userMessage: UserMessage = {
  id: '1',
  messageId: 1,
  role: MessageRole.User,
  content: '你好',
  status: MessageStatus.Complete,
};
```

### AssistantMessage

AI 助手消息：

```typescript
interface AssistantMessage extends BaseMessage<MessageRole.Assistant> {
  // 工具调用列表
  toolCalls?: ToolCall[];
}

// 工具调用
type ToolCall = {
  id: string;
  type: MessageContentType.Function;
  function: FunctionCall;
};

type FunctionCall = {
  name: string;
  arguments: string;
  description?: string;
  mcpName?: string;
};

// 示例
const assistantMessage: AssistantMessage = {
  id: '2',
  messageId: 2,
  role: MessageRole.Assistant,
  content: '你好！有什么可以帮助你的？',
  status: MessageStatus.Complete,
  toolCalls: [
    {
      id: 'call_1',
      type: MessageContentType.Function,
      function: {
        name: 'get_weather',
        arguments: '{"city": "北京"}',
      },
    },
  ],
};
```

### ReasoningMessage

推理过程消息：

```typescript
interface ReasoningMessage extends BaseMessage<MessageRole.Reasoning, string[]> {
  // 推理耗时（毫秒）
  duration?: number;
}

// 示例
const reasoningMessage: ReasoningMessage = {
  id: '3',
  messageId: 3,
  role: MessageRole.Reasoning,
  content: ['让我分析一下这个问题...', '首先，需要考虑以下几点：', '1. 技术可行性'],
  status: MessageStatus.Complete,
  duration: 3500,
};
```

### ToolMessage

工具调用结果消息：

```typescript
interface ToolMessage extends BaseMessage<MessageRole.Tool, string> {
  // 工具调用 ID（对应 AssistantMessage 中的 toolCalls[].id）
  toolCallId: string;

  // 执行耗时（毫秒）
  duration: number;

  // 错误信息
  error?: string;
}

// 示例
const toolMessage: ToolMessage = {
  id: '4',
  messageId: 4,
  role: MessageRole.Tool,
  content: '{"temperature": 25, "weather": "晴天"}',
  status: MessageStatus.Complete,
  toolCallId: 'call_1',
  duration: 1200,
};
```

### ActivityMessage

活动消息（如引用文档、知识检索）：

```typescript
// 引用文档内容类型
type ReferenceDocumentContent = {
  name: string;
  originFile: string;
  url: string;
};

// 知识检索内容类型
type KnowledgeRagContent = {
  content: string;
  referenceDocument: ReferenceDocumentContent[];
};

interface ActivityMessage extends BaseMessage<MessageRole.Activity, KnowledgeRagContent | ReferenceDocumentContent[]> {
  activityType: MessageContentType.KnowledgeRag | MessageContentType.ReferenceDocument | string;
}

// 示例 1：引用文档
const referenceMessage: ActivityMessage = {
  id: '5',
  messageId: 5,
  role: MessageRole.Activity,
  content: [
    { name: '参考文档 1', url: 'https://example.com/1', originFile: 'https://example.com/origin/1' },
    { name: '参考文档 2', url: 'https://example.com/2', originFile: 'https://example.com/origin/2' },
  ],
  status: MessageStatus.Complete,
  activityType: 'reference',
};

// 示例 2：知识检索（knowledge_rag）
const knowledgeRagMessage: ActivityMessage = {
  id: '6',
  messageId: 6,
  role: MessageRole.Activity,
  content: {
    content: '开始召回知识\n重排召回结果中\n完成召回并分类\n',
    referenceDocument: [
      { name: '知识文档 1', url: 'https://example.com/doc1', originFile: 'https://example.com/origin/doc1' },
      { name: '知识文档 2', url: 'https://example.com/doc2', originFile: 'https://example.com/origin/doc2' },
    ],
  },
  status: MessageStatus.Complete,
  activityType: 'knowledge_rag',
};
```

**ActivityMessage 类型说明：**

| activityType      | content 类型                 | 说明                                     |
| ----------------- | ---------------------------- | ---------------------------------------- |
| `'reference'`     | `ReferenceDocumentContent[]` | 引用文档列表                             |
| `'knowledge_rag'` | `KnowledgeRagContent`        | 知识检索结果，包含检索过程内容和引用文档 |

**ReferenceDocumentContent 字段说明：**

| 字段         | 类型     | 说明             |
| ------------ | -------- | ---------------- |
| `name`       | `string` | 文档名称         |
| `url`        | `string` | 文档预览链接     |
| `originFile` | `string` | 文档原始文件链接 |

### InterruptMessage

human-in-the-loop 中断消息，对应 AG-UI `RUN_FINISHED` 事件的 `outcome` 对象结构。`content.outcome.type === 'interrupt'` 时，[InterruptMessageRender](../components/agent/interrupt-message) 从 `interrupts` 渲染审批卡片或把 `UserQuestion` 交给输入区；`type: 'success'` 表示 resume 后的成功结果，`UserQuestion` 会根据 `result` 回显回答内容。类型详见 [中断类型 Interrupt](./interrupt.md)。

```typescript
type RunFinishedOutcome = { interrupts: Interrupt[]; type: 'interrupt' } | { type: 'success' };

type InterruptMessage = BaseMessage<
  MessageRole.Interrupt,
  {
    message?: string;
    outcome?: RunFinishedOutcome;
    result?: BaseResume<InterruptReason>;
    runId?: string;
    threadId?: string;
  }
>;

const interruptMessage: InterruptMessage = {
  id: 'interrupt-message-1',
  messageId: 'interrupt-message-1',
  role: MessageRole.Interrupt,
  status: MessageStatus.Pending,
  content: {
    message: '算法方案评审单需要您关注',
    runId: 'run_ai_dev_tool_approval',
    threadId: 'thread_ai_dev_tool_approval',
    outcome: {
      type: 'interrupt',
      interrupts: [
        {
          id: 'interrupt_ai_dev_tool_approval',
          reason: InterruptReason.AIDevToolApproval,
          toolCallId: 'tool_call_review_ticket',
          message: '算法方案评审单需要您关注',
          metadata: {
            ticket: {
              approvers: ['张三', '李四'],
              sn: 'REV-2026-04-24-001',
              status: APPROVAL_STATUS.PENDING,
              submit_time: '2026-04-24 14:30:15',
              title: '算法方案评审单',
              url: 'https://example.com/review-tickets/REV-2026-04-24-001',
            },
          },
        },
      ],
    },
  },
};
```

### InfoMessage

信息消息：

```typescript
type InfoMessage = BaseMessage<MessageRole.Info, string>;

// 示例
const infoMessage: InfoMessage = {
  id: '6',
  messageId: 6,
  role: MessageRole.Info,
  content: '会话已开始',
  status: MessageStatus.Complete,
};
```

### LoadingMessage

加载中消息，用于在等待 AI 响应时显示加载状态：

```typescript
type LoadingMessage = BaseMessage<MessageRole.Loading, string>;

// 示例
const loadingMessage: LoadingMessage = {
  id: 'loading',
  messageId: '',
  role: MessageRole.Loading,
  content: '',
  status: MessageStatus.Pending,
};
```

## 消息内容类型

```typescript
enum MessageContentType {
  // 二进制内容
  Binary = 'binary',

  // FlowAgent 流程执行
  FlowAgent = 'flow_agent',

  // 函数调用
  Function = 'function',

  // 键值对
  KeyValue = 'key_value',

  // 知识检索
  KnowledgeRag = 'knowledge_rag',

  // 其他
  Other = 'other',

  // 引用文档
  ReferenceDocument = 'reference_document',

  // 文本
  Text = 'text',
}
```

## 类型扩展

支持通过声明合并扩展消息类型：

```typescript
// 在项目中扩展
declare global {
  interface AIBluekingMessageMap {
    'custom-role': CustomMessage;
  }
}

interface CustomMessage extends BaseMessage<'custom-role'> {
  customField: string;
}
```

## 使用示例

```vue
<template>
  <MessageContainer
    :messages="messages"
    :message-status="messageStatus"
    :on-agent-action="handleAgentAction"
    :on-user-action="handleUserAction"
  />
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { MessageContainer, MessageRole, MessageStatus, type Message } from '@blueking/chat-x';

  const messageStatus = ref<MessageStatus>(MessageStatus.Complete);

  const messages = ref<Message[]>([
    {
      id: '1',
      messageId: 1,
      role: MessageRole.User,
      content: '你好',
      status: MessageStatus.Complete,
    },
    {
      id: '2',
      messageId: 2,
      role: MessageRole.Reasoning,
      content: ['思考中...', '分析问题...'],
      status: MessageStatus.Complete,
      duration: 2000,
    },
    {
      id: '3',
      messageId: 3,
      role: MessageRole.Assistant,
      content: '你好！有什么可以帮助你的？',
      status: MessageStatus.Complete,
    },
  ]);

  const handleAgentAction = async tool => {
    console.log('Agent action:', tool);
  };

  const handleUserAction = async tool => {
    console.log('User action:', tool);
  };
</script>
```

## 关联组件

- [MessageContainer](../components/setup/message-container) — 消息列表
- [MessageRender](../components/message/message-render) — 单条消息渲染
- [ChatContainer](../components/setup/chat-container) — 聊天容器
