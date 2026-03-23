# 类型定义 (ai-blueking)

本文档列出 `@blueking/ai-blueking` 包中的核心类型定义。

## IShortcut

快捷指令类型，定义一个可供用户选择的预设操作。

```typescript
interface IShortcut {
  /** 唯一标识 */
  id: string;
  /** 显示名称 */
  name: string;
  /** 图标（可选） */
  icon?: string;
  /** 描述信息 */
  description?: string;
  /** 表单组件列表（快捷指令展开后的表单项） */
  components?: ShortcutComponent[];
  /** 表单数据模型 */
  formModel?: Record<string, any>;
}
```

## IRequestOptions

请求配置类型，支持静态值或动态函数形式。

```typescript
interface IRequestOptions {
  /** 自定义请求头，支持对象或返回对象的函数 */
  headers?: Record<string, string> | (() => Record<string, string>);
  /** 附加请求数据，支持对象或返回对象的函数 */
  data?: Record<string, any> | (() => Record<string, any>);
}
```

### 用法示例

```typescript
// 静态配置
const requestOptions: IRequestOptions = {
  headers: { 'X-Custom-Token': 'abc123' },
  data: { appCode: 'my-app' },
};

// 动态配置（每次请求时重新计算）
const requestOptions: IRequestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  data: () => ({ timestamp: Date.now() }),
};
```

## ChatBotProps

`ChatBot` 组件的 Props 类型。

```typescript
interface ChatBotProps {
  url?: string;
  chatHelper?: IChatHelper;
  autoLoad?: boolean;
  sessionCode?: string;
  shortcuts?: IShortcut[];
  shortcutLimit?: number;
  resources?: IAiSlashMenuItem[];
  prompts?: string[];
  helloText?: string;
  placeholder?: string;
  enableSelection?: boolean;
  shareLoading?: boolean;
  height?: string | number;
  maxWidth?: string | number;
  extCls?: string;
  requestOptions?: IRequestOptions;
  messageToolsTippyOptions?: object;
}
```

## ChatBotExpose

`ChatBot` 组件暴露的方法和属性。

```typescript
interface ChatBotExpose {
  sendMessage: (message: string) => void;
  stopGeneration: () => void;
  switchSession: (sessionCode: string) => Promise<void>;
  setCiteText: (text: string) => void;
  focusInput: () => void;
  selectShortcut: (shortcut: IShortcut, text?: string) => void;
  getChatHelper: () => IChatHelper | null;
  messages: ComputedRef<Message[]>;
  currentSession: ComputedRef<ISession | null>;
  isGenerating: ComputedRef<boolean>;
}
```

## ChatBotEmits

`ChatBot` 组件的事件类型。

```typescript
interface ChatBotEmits {
  'send-message': [message: string];
  'receive-start': [];
  'receive-text': [];
  'receive-end': [];
  'stop': [];
  'error': [error: Error];
  'session-switched': [session: ISession | null];
  'shortcut-click': [payload: { shortcut: IShortcut; source: string }];
  'agent-info-loaded': [chatHelper: IChatHelper];
  'feedback': [tool: any, message: any, reasonList: any, otherReason: any];
  'confirm-share': [messages: Message[]];
  'cancel-share': [];
  'request-share': [];
}
```

## AIBluekingProps

`AIBlueking` 组件的 Props 类型。

```typescript
interface AIBluekingProps {
  url: string;
  requestOptions?: IRequestOptions;
  enableChatSession?: boolean;
  shortcuts?: IShortcut[];
  enablePopup?: boolean;
  draggable?: boolean;
  hideHeader?: boolean;
  hideNimbus?: boolean;
  teleportTo?: string;
  extCls?: string;
  defaultHeight?: number;
  defaultWidth?: number;
  defaultLeft?: number;
  defaultTop?: number;
  maxWidth?: number | string;
  miniPadding?: number;
  helloText?: string;
  placeholder?: string;
  prompts?: string[];
  resources?: IAiSlashMenuItem[];
}
```

## AIBluekingExpose

`AIBlueking` 组件暴露的方法。

```typescript
interface AIBluekingExpose {
  show: (sessionCode?: string) => void;
  hide: () => void;
  sendMessage: (message: string) => void;
  stopGeneration: () => void;
  addNewSession: () => void;
  switchToSession: (sessionCode: string) => Promise<void>;
  updateSessionName: (code: string, name: string) => void;
  updatePosition: (left: number, top: number) => void;
  updateSize: (width: number, height: number) => void;
  updatePositionAndSize: (rect: Partial<Rect>) => void;
  setCiteText: (text: string) => void;
  focusInput: () => void;
}
```

## AIBluekingEmits

`AIBlueking` 组件的事件类型。

```typescript
interface AIBluekingEmits {
  'send-message': [message: string];
  'receive-start': [];
  'receive-text': [];
  'receive-end': [];
  'stop': [];
  'session-switched': [session: ISession | null];
  'shortcut-click': [payload: { shortcut: IShortcut; source: string }];
  'error': [error: Error];
  'drag-stop': [position: { left: number; top: number }];
  'resize-stop': [size: { width: number; height: number }];
  'dragging': [position: { left: number; top: number }];
  'resizing': [size: { width: number; height: number }];
  'transfer-messages': [messages: Message[]];
  'share-messages': [messages: Message[]];
  'sdk-error': [error: Error];
}
```

## BootstrapPhase

启动阶段枚举，表示 `useChatBootstrap` 的当前初始化阶段。

```typescript
enum BootstrapPhase {
  /** 空闲状态 */
  IDLE = 'idle',
  /** 正在加载 Agent 信息 */
  LOADING_AGENT = 'loading-agent',
  /** 正在加载会话 */
  LOADING_SESSION = 'loading-session',
  /** 就绪 */
  READY = 'ready',
  /** 出错 */
  ERROR = 'error',
}
```

## InternalEvent

内部事件枚举，用于 `ComponentManager` 的事件通信。

```typescript
enum InternalEvent {
  SendMessage = 'send-message',
  StopGeneration = 'stop-generation',
  ReceiveStart = 'receive-start',
  ReceiveText = 'receive-text',
  ReceiveEnd = 'receive-end',
  SessionSwitched = 'session-switched',
  SessionCreated = 'session-created',
  SessionDeleted = 'session-deleted',
  ShortcutClick = 'shortcut-click',
  ShortcutSelect = 'shortcut-select',
  SelectionModeChanged = 'selection-mode-changed',
  Error = 'error',
}
```

## ChatBootstrapOptions

`useChatBootstrap` 的配置选项。

```typescript
interface ChatBootstrapOptions {
  /** chat-helper 实例或创建选项 */
  chatHelper?: IChatHelper | IUseChatHelperOptions;
  /** API 地址前缀 */
  url?: string;
  /** 请求配置 */
  requestOptions?: IRequestOptions;
  /** 是否自动加载最近会话 */
  autoLoad?: boolean;
  /** 初始会话编码 */
  sessionCode?: string;
}
```

## ChatBootstrapReturn

`useChatBootstrap` 的返回类型。

```typescript
interface ChatBootstrapReturn {
  /** 当前启动阶段 */
  phase: Ref<BootstrapPhase>;
  /** chat-helper 实例 */
  chatHelper: IChatHelper;
  /** 组件管理器 */
  componentManager: ComponentManager;
  /** 聊天业务管理器 */
  chatBizManager: ChatBusinessManager;
  /** 会话业务管理器 */
  sessionBizManager: SessionBusinessManager;
  /** 快捷指令管理器 */
  shortcutManager: ShortcutManager;
  /** UI 状态管理器 */
  uiStateManager: UIStateManager;
  /** 启动函数 */
  bootstrap: () => Promise<void>;
}
```
