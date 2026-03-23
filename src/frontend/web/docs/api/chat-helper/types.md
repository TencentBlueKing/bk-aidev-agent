# 类型定义 (chat-helper)

本文档列出 `@blueking/chat-helper` 包中的核心类型定义。

## IUseChatHelperOptions

`useChatHelper` 的配置选项。

```typescript
interface IUseChatHelperOptions {
  /** 请求配置 */
  requestData?: {
    /** API 地址前缀 */
    urlPrefix: string;
    /** 自定义请求头，支持对象或返回对象的函数 */
    headers?: Record<string, string> | (() => Record<string, string>);
    /** 附加请求数据，支持对象或返回对象的函数 */
    data?: Record<string, any> | (() => Record<string, any>);
  };
  /** 自定义协议实例 */
  protocol?: AGUIProtocol;
  /** 请求/响应拦截器 */
  interceptors?: {
    request?: (config: RequestConfig) => RequestConfig;
    response?: (response: any) => any;
  };
}
```

## IAgentInfo

Agent 信息接口，描述一个 AI Agent 的基础配置。

```typescript
interface IAgentInfo {
  /** Agent 名称 */
  agentName: string;
  /** 可用资源列表 */
  resources: IAgentResource[];
  /** SaaS 地址 */
  saasUrl?: string;
  /** 交流群信息 */
  chatGroup?: string;
  /** 会话配置 */
  conversationSettings?: {
    /** 是否启用多会话 */
    enableMultiSession?: boolean;
    /** 最大会话数 */
    maxSessionCount?: number;
  };
  /** 提示词配置 */
  promptSetting?: {
    /** 欢迎语 */
    helloText?: string;
    /** 输入框占位符 */
    placeholder?: string;
    /** 预设提示词 */
    prompts?: string[];
  };
}
```

## ISession

会话接口。

```typescript
interface ISession {
  /** 会话唯一编码 */
  sessionCode: string;
  /** 会话名称 */
  sessionName: string;
  /** 会话消息数量 */
  sessionContentCount: number;
  /** 创建时间 */
  createdAt: string;
  /** 更新时间 */
  updatedAt: string;
}
```

## IMessage

消息接口。

```typescript
interface IMessage {
  /** 消息唯一 ID */
  id: string;
  /** 消息角色 */
  role: string;
  /** 消息内容 */
  content: string | InputContent[];
  /** 消息状态 */
  status?: string;
  /** 创建时间 */
  createdAt?: string;
  /** 更新时间 */
  updatedAt?: string;
  /** 关联的会话编码 */
  sessionCode?: string;
  /** 工具名称（仅 tool 角色） */
  toolName?: string;
  /** 工具调用参数（仅 tool 角色） */
  toolArgs?: Record<string, any>;
}
```

## IUserMessage

用户消息接口，`content` 支持纯文本或结构化内容。

```typescript
interface IUserMessage extends IMessage {
  role: 'user';
  /** 消息内容：纯文本字符串或结构化输入内容数组 */
  content: string | InputContent[];
}
```

### InputContent

结构化输入内容（支持多模态）。

```typescript
type InputContent = ITextContent | IImageContent;

interface ITextContent {
  type: 'text';
  text: string;
}

interface IImageContent {
  type: 'image_url';
  image_url: {
    url: string;
  };
}
```

## ISupportUpload

文件上传支持配置。

```typescript
interface ISupportUpload {
  /** 是否支持视觉/图片上传 */
  vision: boolean;
}
```

## IAgentCommand

Agent 命令（快捷指令）接口。

```typescript
interface IAgentCommand {
  /** 唯一标识 */
  id: string;
  /** 显示名称 */
  name: string;
  /** 命令别名 */
  alias?: string;
  /** 图标 */
  icon?: string;
  /** 表单组件配置 */
  components?: ICommandComponent[];
  /** 是否支持文件上传 */
  supportUpload?: ISupportUpload;
}
```

### ICommandComponent

命令表单组件配置。

```typescript
interface ICommandComponent {
  /** 组件类型 */
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

## RequestConfig

请求配置类型。

```typescript
interface RequestConfig {
  /** 请求 URL */
  url: string;
  /** 请求方法 */
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  /** 请求头 */
  headers?: Record<string, string>;
  /** 请求体 */
  data?: any;
  /** 查询参数 */
  params?: Record<string, any>;
  /** 超时时间（毫秒） */
  timeout?: number;
}
```

## AG-UI 事件接口

以下是 AG-UI 协议中各事件的接口定义。

### ITextMessageStartEvent

```typescript
interface ITextMessageStartEvent {
  type: 'TextMessageStart';
  /** 消息 ID */
  messageId: string;
}
```

### ITextMessageChunkEvent

```typescript
interface ITextMessageChunkEvent {
  type: 'TextMessageChunk';
  /** 消息 ID */
  messageId: string;
  /** 文本片段 */
  delta: string;
}
```

### ITextMessageEndEvent

```typescript
interface ITextMessageEndEvent {
  type: 'TextMessageEnd';
  /** 消息 ID */
  messageId: string;
}
```

### IThinkingStartEvent

```typescript
interface IThinkingStartEvent {
  type: 'ThinkingStart';
  /** 消息 ID */
  messageId: string;
}
```

### IThinkingEndEvent

```typescript
interface IThinkingEndEvent {
  type: 'ThinkingEnd';
  /** 消息 ID */
  messageId: string;
}
```

### IToolCallStartEvent

```typescript
interface IToolCallStartEvent {
  type: 'ToolCallStart';
  /** 消息 ID */
  messageId: string;
  /** 工具名称 */
  toolName: string;
}
```

### IToolCallArgsEvent

```typescript
interface IToolCallArgsEvent {
  type: 'ToolCallArgs';
  /** 消息 ID */
  messageId: string;
  /** 参数片段（JSON 字符串） */
  delta: string;
}
```

### IToolCallResultEvent

```typescript
interface IToolCallResultEvent {
  type: 'ToolCallResult';
  /** 消息 ID */
  messageId: string;
  /** 工具调用结果 */
  result: string;
}
```

### IToolCallEndEvent

```typescript
interface IToolCallEndEvent {
  type: 'ToolCallEnd';
  /** 消息 ID */
  messageId: string;
}
```

### IRunErrorEvent

```typescript
interface IRunErrorEvent {
  type: 'RunError';
  /** 错误信息 */
  message: string;
  /** 错误码 */
  code?: string;
}
```

### IMessagesSnapshotEvent

```typescript
interface IMessagesSnapshotEvent {
  type: 'MessagesSnapshot';
  /** 完整消息列表快照 */
  messages: IMessage[];
}
```
