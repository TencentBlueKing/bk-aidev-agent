# 类型定义 (chat-x)

本文档列出 `@blueking/chat-x` 包中的核心类型、枚举和接口定义。

## 枚举

### MessageStatus

消息状态枚举，控制输入框和消息列表的交互行为。

```typescript
enum MessageStatus {
  /** 等待中 */
  Pending = 'pending',
  /** 流式输出中 */
  Streaming = 'streaming',
  /** 已完成 */
  Complete = 'complete',
  /** 出错 */
  Error = 'error',
  /** 已停止 */
  Stop = 'stop',
}
```

### MessageToolsStatus

消息工具栏状态枚举。

```typescript
enum MessageToolsStatus {
  /** 禁用工具栏 */
  Disabled = 'disabled',
}
```

### MessageRole

消息角色枚举，决定消息的渲染方式。

```typescript
enum MessageRole {
  /** 用户消息 */
  User = 'user',
  /** AI 助手回复 */
  Assistant = 'assistant',
  /** 推理/思考过程 */
  Reasoning = 'reasoning',
  /** 工具调用 */
  Tool = 'tool',
  /** 活动状态 */
  Activity = 'activity',
  /** 信息提示 */
  Info = 'info',
  /** 系统消息 */
  System = 'system',
}
```

## 消息类型

### Message

消息基础类型，使用泛型支持不同角色的消息结构。

```typescript
type Message = UserMessage | AssistantMessage | ReasoningMessage | ToolMessage;
```

### BaseMessage

所有消息的基础接口。

```typescript
interface BaseMessage<R extends MessageRole = MessageRole> {
  /** 消息唯一 ID */
  id: string;
  /** 消息角色 */
  role: R;
  /** 消息内容 */
  content: string;
  /** 消息状态 */
  status?: MessageStatus;
  /** 创建时间 */
  createdAt?: string;
}
```

### UserMessage

用户消息接口。

```typescript
interface UserMessage extends BaseMessage<MessageRole.User> {
  role: MessageRole.User;
  /** 文本内容 */
  content: string;
  /** 关联的快捷指令 */
  shortcut?: IShortcut;
  /** 快捷指令表单数据 */
  formModel?: Record<string, any>;
  /** 工具栏按钮 */
  tools?: IToolBtn[];
}
```

### AssistantMessage

AI 助手消息接口。

```typescript
interface AssistantMessage extends BaseMessage<MessageRole.Assistant> {
  role: MessageRole.Assistant;
  /** Markdown 内容 */
  content: string;
  /** 工具栏按钮 */
  tools?: IToolBtn[];
  /** 反馈状态 */
  feedbackStatus?: 'like' | 'unlike' | null;
}
```

### ReasoningMessage

推理/思考链消息接口。

```typescript
interface ReasoningMessage extends BaseMessage<MessageRole.Reasoning> {
  role: MessageRole.Reasoning;
  /** 思考内容 */
  content: string;
}
```

### ToolMessage

工具调用消息接口。

```typescript
interface ToolMessage extends BaseMessage<MessageRole.Tool> {
  role: MessageRole.Tool;
  /** 工具名称 */
  toolName: string;
  /** 工具调用参数 */
  toolArgs?: Record<string, any>;
  /** 工具调用结果 */
  content: string;
}
```

## 工具栏类型

### IToolBtn

工具栏按钮联合类型。

```typescript
type IToolBtn = IBuiltinToolBtn | IEditConfirmToolBtn | ICustomToolBtn;
```

### IBuiltinToolBtn

内置工具按钮。

```typescript
interface IBuiltinToolBtn {
  /** 内置工具 ID */
  id: BuiltinToolId;
  /** 是否禁用 */
  disabled?: boolean;
}
```

### BuiltinToolId

内置工具 ID 类型。

```typescript
type BuiltinToolId =
  | 'copy'      // 复制
  | 'cite'      // 引用
  | 'rebuild'   // 重新生成
  | 'share'     // 分享
  | 'like'      // 点赞
  | 'unlike'    // 点踩
  | 'edit'      // 编辑
  | 'delete';   // 删除
```

### IEditConfirmToolBtn

编辑确认工具按钮。

```typescript
interface IEditConfirmToolBtn {
  /** 类型标识 */
  type: 'edit-confirm';
  /** 确认回调 */
  onConfirm?: (message: Message, content: string) => void;
  /** 取消回调 */
  onCancel?: () => void;
}
```

### ICustomToolBtn

自定义工具按钮。

```typescript
interface ICustomToolBtn {
  /** 自定义唯一标识 */
  id: string;
  /** 显示文本 */
  text?: string;
  /** 图标 */
  icon?: string;
  /** 点击回调 */
  onClick?: (message: Message) => void;
  /** 是否禁用 */
  disabled?: boolean;
}
```

### 类型守卫

```typescript
/** 判断是否为内置工具按钮 */
function isBuiltinTool(tool: IToolBtn): tool is IBuiltinToolBtn;

/** 判断是否为编辑确认工具按钮 */
function isEditConfirmTool(tool: IToolBtn): tool is IEditConfirmToolBtn;
```

### 默认工具栏配置

```typescript
/** AI 助手消息默认工具栏 */
const CONST_MESSAGE_TOOLS: IBuiltinToolBtn[] = [
  { id: 'copy' },
  { id: 'cite' },
  { id: 'rebuild' },
  { id: 'like' },
  { id: 'unlike' },
];

/** 用户消息默认工具栏 */
const CONST_USER_MESSAGE_TOOLS: IBuiltinToolBtn[] = [
  { id: 'edit' },
  { id: 'delete' },
];
```

## 快捷指令类型

### Shortcut

快捷指令接口。

```typescript
interface Shortcut {
  /** 唯一标识 */
  id: string;
  /** 显示名称 */
  name: string;
  /** 图标 */
  icon?: string;
  /** 描述信息 */
  description?: string;
  /** 表单组件配置 */
  components?: ShortcutComponent[];
  /** 表单数据模型 */
  formModel?: Record<string, any>;
}
```

### ShortcutComponent

快捷指令表单组件配置。

```typescript
interface ShortcutComponent {
  /** 组件类型（如 input、select、textarea 等） */
  type: string;
  /** 字段键名 */
  key: string;
  /** 显示名称 */
  name: string;
  /** 组件 props */
  props?: Record<string, any>;
  /** 是否回填到输入框 */
  fillBack?: boolean;
  /** 是否必填 */
  required?: boolean;
}
```

## TagSchema

标签模式类型，用于结构化消息内容。

```typescript
interface TagSchema {
  /** 标签名称 */
  tag: string;
  /** 标签属性 */
  attrs?: Record<string, string>;
  /** 子内容 */
  children?: (string | TagSchema)[];
}
```
