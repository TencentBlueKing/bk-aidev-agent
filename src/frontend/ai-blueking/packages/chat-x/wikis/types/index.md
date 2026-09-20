# 类型定义

`@blueking/chat-x` 提供完整的 TypeScript 类型定义。

## 类型文档

| 类型      | 说明     | 文档                   |
| --------- | -------- | ---------------------- |
| Message   | 消息类型 | [查看](./messages.md)  |
| Constants | 常量枚举 | [查看](./constants.md) |
| Interrupt | 中断类型 | [查看](./interrupt.md) |
| Schema    | 用户问题 Schema | [查看](./schema.md) |

## 源码文件地图

| 源文件 | 职责 | 文档 |
| --- | --- | --- |
| `src/ag-ui/types/*` | 消息 / 内容 / 常量 | [messages](./messages.md)、[constants](./constants.md) |
| interrupt 相关 | HITL | [interrupt](./interrupt.md) |
| schema | 用户问题 schema | [schema](./schema.md) |
| `src/types/input-menu.ts` | `IInputMenuItem` 等 | 本页引入示例 + [ChatInput](/components/input/chat-input) |
| `src/types/input.ts` | `TagSchema` / `UploadFile` | 本页引入示例 |
| `src/types/tool.ts` | `IToolBtn` | 本页引入示例 |
| `src/types/custom.ts` | `CustomTab` | [自定义侧栏](/ai/custom-side-tab) |
| `src/types/shortcut.ts` | `Shortcut` | 本页引入示例 |
| `src/types/image.ts` | 预览项类型 | [ImagePreview](/components/medias/image-preview) |
| `src/types/editor.ts` | `noop` 等编辑器辅助 | 无独立页 |

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
  UploadFile,
  UploadFileVariant,

  // 输入框菜单
  IInputMenuItem,
  IInputMenuGroup,
  MenuItemType,
  MenuTrigger,

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
import { MessageRole, MessageStatus, MessageContentType, MessageState, UploadStatus } from '@blueking/chat-x';
```

::: warning 已移除的输入相关类型
`IAiSlashMenuItem`、`IAiSlashGroupItem`、`ISkillListItem`、`resourceTypeMap`、`ResourceType` 随旧版 `@` / `/` 菜单一并移除，统一改用 `IInputMenuItem` 与 `MenuItemType`，迁移方式见 [ChatInput](/components/input/chat-input)。
:::

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
  CONST_USER_MESSAGE_MAX_HEIGHT,
  CONST_UPDATE_TOOLS,
  MAX_UPLOAD_FILES,
  MAX_UPLOAD_FILE_SIZE,
  ALLOWED_UPLOAD_EXTENSIONS,
  DEFAULT_UPLOAD_ACCEPT,
  MENU_ITEM_TYPES,
  DEFAULT_SHORTCUTS,
  UserQuestionSchema,
  UserMultiChoiceQuestionSchema,
  UserSingleChoiceQuestionSchema,
} from '@blueking/chat-x';
```
