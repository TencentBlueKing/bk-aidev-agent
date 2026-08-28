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
    /** 自定义请求头；支持对象、零参函数、ref、computed（每次请求前 resolveRequestValue） */
    headers?: MaybeRequestValue<Record<string, string>>;
    /** 附加数据；GET/HEAD/OPTIONS 合并 query，POST/PUT/PATCH/DELETE 合并 body */
    data?: MaybeRequestValue<Record<string, unknown>>;
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

## MaybeRequestValue

延迟求值的请求字段类型，用于 `requestData.headers` / `requestData.data` 及小鲸 `IRequestOptions` 的同名字段。

```typescript
type MaybeRequestValue<T> = T | (() => MaybeRequestValue<T>);
// 另支持 Vue 的 Ref / ComputedRef；每次请求前由 resolveRequestValue() 递归展开
```

| 写法 | 说明 |
| --- | --- |
| 普通对象 | 固定快照；适合不变配置 |
| `() => object` | 每次请求调用函数 |
| `ref` / `computed` | 修改 `.value` 后，下一次请求自动生效 |

## IAgentInfo

Agent 信息接口，描述一个 AI Agent 的基础配置。

```typescript
interface IAgentInfo {
  /** Agent 名称 */
  agentName: string;
  /** Agent 类型：`single` 为普通智能体；`claw` 时 ChatBot 自动隐藏编辑/删除/重新生成 */
  agentType?: 'claw' | 'single' | string;
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

## ILlmItem {#illmitem}

可用模型项（对齐 `plugin_api/llms/` 与 chat-x `IModelOption`）。字段以 snake_case 与后端保持一致，便于直接透传给 ModelSelector。

```typescript
interface ILlmProperty {
  agent_type?: string;
  default?: boolean;
  is_self_host?: boolean;
  max_model_len?: number;
  support_summary?: boolean;
  support_thinking?: boolean;
  support_thinking_quick?: boolean;
  support_tools?: boolean;
  support_vision?: boolean;
  support_window?: boolean;
}

interface ILlmListQuery {
  /** 模糊搜索关键词，按 llm_name / description / base_model 匹配 */
  fuzzy?: string;
  /** 模型类型，不传时默认 chat.completion */
  llm_type?: string;
  /** 按模型支持的功能过滤，逗号分隔，如 tool_call,vision */
  supports?: string;
}

interface ILlmItem {
  base_model?: string;
  description?: string;
  disabled?: boolean;
  icon?: string;
  id: number;
  /** 模型编码（chat_completion 热切换传此值） */
  llm_code: string;
  /** 模型展示名（ModelSelector v-model 选中值） */
  llm_name: string;
  llm_type: string;
  max_token_size: number;
  property: ILlmProperty;
  space_auth_mode: string;
  tag_names?: string[];
  user_auth_mode: string;
}
```

## StreamMode {#streammode}

`chat_completion` 的 `execute_kwargs.stream_mode`（`@blueking/chat-helper` 导出）。

```typescript
/** start：可创建生产者，开新一轮执行（默认） */
/** attach：仅接管/回放已有流，不允许新建生产者 */
type StreamMode = "start" | "attach"
```

| 值 | 说明 |
| --- | --- |
| `start` | 新发送、重发、HITL 恢复、用户操作后续流 |
| `attach` | `resumeStreamingChat`、静默重连 |

详见 [chat-helper SDK · stream_mode](/api/chat-helper/sdk#stream-mode)。

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
  /** 会话关联模型（llm_code）；小鲸仅在首次无有效选中时用作兜底 */
  model?: string;
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
  /** 创建时间（session_contents.created_at / MESSAGES_SNAPSHOT / RUN_FINISHED.timestamp 转 ISO） */
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

## IRequestError

请求错误接口（**≥ v2.1.4-beta.25**）。

```typescript
interface IRequestError extends Error {
  /** 请求配置 */
  config?: RequestConfig;
  /** 错误码 */
  code?: string;
  /** 响应数据 */
  data?: unknown;
}
```

## GlobalErrorHandler

全局错误处理器类型（**≥ v2.1.4-beta.25**）。

```typescript
type GlobalErrorHandler = (error: IRequestError) => void;
```

## ErrorHandlerOptions

错误处理器配置（**≥ v2.1.4-beta.25**）。

```typescript
interface ErrorHandlerOptions {
  /** 忽略的 URL 模式（字符串包含匹配或正则） */
  ignoreErrors?: Array<string | RegExp>;
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
