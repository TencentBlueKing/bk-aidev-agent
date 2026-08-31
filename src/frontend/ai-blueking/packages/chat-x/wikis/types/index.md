# 类型定义

`@blueking/chat-x` 提供完整的 TypeScript 类型定义。

## 类型文档

| 类型      | 说明     | 文档                   |
| --------- | -------- | ---------------------- |
| Message   | 消息类型 | [查看](./messages.md)  |
| Constants | 常量枚举 | [查看](./constants.md) |
| Interrupt | 中断类型 | [查看](./interrupt.md) |
| Schema    | 用户问题 Schema | [查看](./schema.md) |

## 引入类型

```typescript
import type {
  // 消息类型
  Message,
  UserMessage,
  AssistantMessage,
  ReasoningMessage,
  ToolMessage,
  ActivityMessage,
  InfoMessage,
  BaseMessage,
  MessageMap,
  MessageType,

  // 工具调用
  ToolCall,
  FunctionCall,
  FunctionCallType,
  Tool,

  // 快捷指令
  Shortcut,
  ShortcutComponent,
  InputShortcutComponent,
  TextareaShortcutComponent,
  SelectShortcutComponent,
  CheckboxGroupShortcutComponent,
  RadioGroupShortcutComponent,
  SwitcherShortcutComponent,

  // 工具按钮
  IToolBtn,

  // 输入相关
  TagSchema,
  MentionState,

  // 内容类型
  ContentType,
  ContentMap,
  InputContent,

  // 中断类型
  Interrupt,
  InterruptMessage,
  OnInterruptResume,
  UserQuestionAnswerItem,
  UserQuestionInterrupt,
  UserQuestionResume,

  // 历史用户问题 Schema
  UserQuestion,
  UserMultiChoiceQuestion,
  UserSingleChoiceQuestion,
} from '@blueking/chat-x';
```

## 引入枚举

```typescript
import { MessageRole, MessageStatus, MessageContentType, MessageState } from '@blueking/chat-x';
```

## 引入常量

```typescript
import {
  CHAT_Z_INDEX,
  EDITOR_Z_INDEX,
  EDITOR_MENU_Z_INDEX,
  SHORTCUT_MENU_Z_INDEX,
  SELECTION_Z_INDEX,
  CONST_MESSAGE_TOOLS,
  CONST_USER_MESSAGE_TOOLS,
  CONST_UPDATE_TOOLS,
  DEFAULT_SHORTCUTS,
  UserQuestionSchema,
  UserMultiChoiceQuestionSchema,
  UserSingleChoiceQuestionSchema,
} from '@blueking/chat-x';
```
