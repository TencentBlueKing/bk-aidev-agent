---
name: 常量枚举
slug: constants
category: type
description: '`@blueking/chat-x` 导出的常量和枚举类型。'
aiSummary: >
  汇总 MessageRole、MessageStatus、MessageContentType、MessageToolsStatus、MessageState、Z-Index 与 CONST_MESSAGE_TOOLS 等导出常量。
  用于构造消息、配置 MessageContainer 工具栏与输入态，以及层级与默认快捷指令。与类型 messages 配套使用。
relatedComponents:
  - slug: message-tools
    relation: 默认工具 ID 与展示
  - slug: chat-input
    relation: MessageState 与快捷指令
  - slug: message-container
    relation: 工具栏与消息态
sinceVersion: 1.0.0
---

# 常量枚举

> **分类**：type

`@blueking/chat-x` 导出的常量和枚举类型。

## 消息相关

### MessageRole

消息角色枚举：

```typescript
enum MessageRole {
  User = 'user',
  Assistant = 'assistant',
  System = 'system',
  Developer = 'developer',
  Guide = 'guide',
  Hidden = 'hidden',
  HiddenAssistant = 'hidden-assistant',
  HiddenGuide = 'hidden-guide',
  HiddenSystem = 'hidden-system',
  HiddenUser = 'hidden-user',
  Info = 'info',
  Loading = 'loading',
  Pause = 'pause',
  Placeholder = 'placeholder',
  Reasoning = 'reasoning',
  TemplateAssistant = 'template-assistant',
  TemplateGuide = 'template-guide',
  TemplateHidden = 'template-hidden',
  TemplateSystem = 'template-system',
  TemplateUser = 'template-user',
  Tool = 'tool',
  Activity = 'activity',
}
```

### MessageStatus

消息状态枚举：

```typescript
enum MessageStatus {
  Pending = 'pending',
  Streaming = 'streaming',
  Complete = 'complete',
  Error = 'error',
  Stop = 'stop',
  Disabled = 'disabled',
}
```

### MessageContentType

消息内容类型枚举：

```typescript
enum MessageContentType {
  Binary = 'binary',
  Function = 'function',
  KeyValue = 'key-value',
  KnowledgeRag = 'knowledge-rag',
  Other = 'other',
  ReferenceDocument = 'reference-document',
  Text = 'text',
}
```

### MessageToolsStatus

消息工具栏状态枚举：

```typescript
enum MessageToolsStatus {
  Disabled = 'disabled', // 禁用状态，按钮显示但不可点击
  Hidden = 'hidden', // 隐藏状态，工具栏完全隐藏
}
```

## 输入状态

### MessageState

输入框消息状态：

```typescript
const MessageState = {
  ACTIVE: 'active',
  DISABLED: 'disabled',
  LOADING: 'loading',
} as const;
```

## Z-Index 常量

```typescript
// 全局 chat-x 组件 Z-Index
const CHAT_Z_INDEX = 9999;

// 编辑器组件 Z-Index
const EDITOR_Z_INDEX = 10000;

// 编辑器菜单 Z-Index
const EDITOR_MENU_Z_INDEX = 10001;

// 快捷指令菜单 Z-Index
const SHORTCUT_MENU_Z_INDEX = 10002;

// 划选弹窗 Z-Index
const SELECTION_Z_INDEX = 10003;
```

## 默认工具按钮

### CONST_MESSAGE_TOOLS

消息工具按钮列表：

```typescript
const CONST_MESSAGE_TOOLS: IToolBtn[] = [
  { id: 'copy', name: '复制', description: '复制' },
  { id: 'cite', name: '引用', description: '引用' },
  { id: 'rebuild', name: '重新生成', description: '重新生成' },
  { id: 'share', name: '分享', description: '分享' },
];
```

### CONST_USER_MESSAGE_TOOLS

用户消息工具按钮列表：

```typescript
const CONST_USER_MESSAGE_TOOLS: IToolBtn[] = [
  { id: 'copy', name: '复制', description: '复制' },
  { id: 'cite', name: '引用', description: '引用' },
  { id: 'edit', name: '编辑', description: '编辑' },
  { id: 'delete', name: '删除', description: '删除' },
];
```

### CONST_UPDATE_TOOLS

更新工具按钮列表（点赞/不满意）：

```typescript
const CONST_UPDATE_TOOLS: IToolBtn[] = [
  { id: 'like', name: '点赞', description: '点赞' },
  { id: 'unlike', name: '不满意', description: '不满意' },
  { id: 'delete', name: '删除', description: '删除' },
];
```

## 默认快捷指令

### DEFAULT_SHORTCUTS

默认快捷指令列表：

```typescript
const DEFAULT_SHORTCUTS: Shortcut[] = [{ id: 'ask-whale', name: '问问小鲸' }];
```

## 使用示例

```typescript
import {
  MessageRole,
  MessageStatus,
  MessageContentType,
  MessageToolsStatus,
  CHAT_Z_INDEX,
  CONST_MESSAGE_TOOLS,
  DEFAULT_SHORTCUTS,
} from '@blueking/chat-x';

// 创建消息
const message = {
  id: '1',
  messageId: 1,
  role: MessageRole.User,
  content: '你好',
  status: MessageStatus.Complete,
};

// 检查消息状态
if (message.status === MessageStatus.Streaming) {
  console.log('消息正在流式输出中...');
}

// 使用默认工具按钮
console.log(
  '可用工具:',
  CONST_MESSAGE_TOOLS.map(t => t.name),
);
```

## 关联组件

- [MessageTools](../components/molecular/message-tools.md) — 消息工具栏
- [ChatInput](../components/molecular/chat-input.md) — 输入与状态
- [MessageContainer](../components/molecular/message-container.md) — 工具与消息展示
