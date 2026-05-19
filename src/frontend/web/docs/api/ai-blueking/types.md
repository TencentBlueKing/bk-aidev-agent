# 类型定义 (ai-blueking)

本文档列出 `@blueking/ai-blueking` 包中的核心类型定义。

## AIBluekingProps

`AIBlueking` 组件的 Props 类型。

```typescript
interface AIBluekingProps {
  // 基础配置
  /** API 服务地址 */
  url?: string;
  /** 组件标题 */
  title?: string;
  /** 渲染模式：chat(默认)、share(分享)、test(测试) */
  renderMode?: RenderMode;
  /** 请求配置 */
  requestOptions?: MaybeRefOrGetter<IRequestOptions>;
  /** 自定义 CSS 类名 */
  extCls?: string;
  /** 输入框占位文本 */
  placeholder?: string;
  /** 欢迎语 */
  helloText?: string;
  /** 预设提示词列表 */
  prompts?: string[];
  /** 资源列表（输入 @ 触发） */
  resources?: IAiSlashMenuItem[];

  // 功能开关
  /** 是否启用选中文本弹窗（AiSelection） */
  enablePopup?: boolean;
  /** 是否可拖拽 */
  draggable?: boolean;
  /** 是否启用会话管理 */
  enableChatSession?: boolean;
  /** 是否隐藏头部 */
  hideHeader?: boolean;
  /** 是否隐藏悬浮球 */
  hideNimbus?: boolean;
  /** 是否隐藏默认触发器 */
  hideDefaultTrigger?: boolean;
  /** 是否禁用输入 */
  disabledInput?: boolean;

  // 容器配置
  /** 渲染目标（CSS 选择器） */
  teleportTo?: string;
  /** 默认宽度 */
  defaultWidth?: number;
  /** 默认高度 */
  defaultHeight?: number;
  /** 默认左侧位置 */
  defaultLeft?: number;
  /** 默认顶部位置 */
  defaultTop?: number;
  /** 最大宽度 */
  maxWidth?: number | string;
  /** 最小化时的内边距 */
  miniPadding?: number;
  /** 默认聊天输入框位置 */
  defaultChatInputPosition?: 'bottom' | undefined;

  // Nimbus 配置
  /** 悬浮球大小 */
  nimbusSize?: 'large' | 'normal' | 'small';
  /** 是否默认最小化 */
  defaultMinimize?: boolean;

  // Popup 配置
  /** 快捷操作列表 */
  shortcuts?: IShortcut[];
  /** 快捷操作显示数量限制 */
  shortcutLimit?: number;
  /** 快捷操作过滤函数 */
  shortcutFilter?: (shortcut: IShortcut, selectedText: string) => boolean;

  // 会话配置
  /** 初始会话编码 */
  initialSessionCode?: string;
  /** 是否自动切换到初始会话 */
  autoSwitchToInitialSession?: boolean;
  /** 挂载时是否加载最近会话 */
  loadRecentSessionOnMount?: boolean;

  // Header 图标控制
  /** 是否显示历史记录图标 */
  showHistoryIcon?: boolean;
  /** 是否显示新建会话图标 */
  showNewChatIcon?: boolean;
  /** 是否显示压缩图标 */
  showCompressionIcon?: boolean;
  /** 是否显示更多图标 */
  showMoreIcon?: boolean;
  /** 下拉菜单配置 */
  dropdownMenuConfig?: DropdownMenuConfig;

  // 高级配置
  /** Nimbus 点击前钩子函数，返回 false 阻止默认 showPanel 行为 */
  beforeNimbusClick?: () => boolean | Promise<boolean | void> | void;
  /** ResizeLayout 配置（执行情况侧面板拖拽） */
  resizeProps?: {
    disabled?: boolean;
    initialDivide?: number | string;
    max?: number;
    min?: number;
  };

  /** 自定义侧栏内容区渲染（≥ v2.1.4-beta.7，透传内层 ChatBot） */
  getSideRenderComponent?: GetSideRenderComponent;
  /** 自定义侧栏 Tab 标签渲染（≥ v2.1.4-beta.7） */
  getSideTabRenderComponent?: GetSideTabRenderComponent;
  /** 侧栏自定义 Tab 切换时拉取详情（≥ v2.1.4-beta.7） */
  onCustomTabChange?: OnCustomTabChange;
}
```

## AIBluekingExpose

`AIBlueking` 组件暴露的方法。

```typescript
interface AIBluekingExpose {
  // 面板控制
  show: (sessionCode?: string, options?: { isTemporary?: boolean }) => Promise<void>;
  hide: () => void;
  handleShow: (sessionCode?: string) => Promise<void>;
  handleClose: () => void;

  // 消息操作
  sendMessage: (message: string) => Promise<void>;
  stopGeneration: () => void;
  setCiteText: (text: string) => void;
  focusInput: () => void;

  // 快捷方式操作
  /** 选择快捷指令并显示表单，不会自动提交 */
  selectShortcut: (shortcut: IShortcut, selectedText?: string) => void;
  /** 直接发送快捷指令（跳过表单） */
  sendShortcut: (shortcut: IShortcut, selectedText?: string) => Promise<void>;

  // 会话管理
  addNewSession: (options?: CreateSessionOptions) => Promise<void>;
  switchToSession: (sessionCode: string) => Promise<void>;
  updateSessionName: (sessionCode: string, newName: string) => Promise<void>;

  // 容器控制
  updatePosition: (x: number, y: number) => void;
  updateSize: (w: number, h: number) => void;
  updatePositionAndSize: (x: number, y: number, w: number, h: number) => void;

  // 其他
  /** 获取 chatHelper 实例，用于访问 agent/session/message 等底层模块 */
  getChatHelper: () => IChatHelper | null;
}
```

## AIBluekingEmits

`AIBlueking` 组件的事件类型。

```typescript
interface AIBluekingEmits {
  // 面板事件
  (e: 'show'): void;
  (e: 'close'): void;

  // 拖拽事件
  (e: 'dragging', position: PositionAndSize): void;
  (e: 'resizing', position: PositionAndSize): void;
  (e: 'drag-stop', position: PositionAndSize): void;
  (e: 'resize-stop', position: PositionAndSize): void;

  // 消息事件
  (e: 'send-message', message: string): void;
  (e: 'receive-start'): void;
  (e: 'receive-text'): void;
  (e: 'receive-end'): void;
  (e: 'stop'): void;

  // 快捷方式事件
  (e: 'shortcut-click', data: { shortcut: IShortcut; source: 'main' | 'popup' }): void;

  // 会话事件
  (e: 'session-initialized', data: { openingRemark: string; predefinedQuestions: string[] }): void;
  (e: 'new-chat'): void;
  (e: 'new-chat-created', session: { sessionCode: string; sessionName?: string; createdAt?: string }): void;
  (e: 'history-click', event: Event): void;
  (e: 'auto-generate-name'): void;
  (e: 'help-click'): void;
  (e: 'rename', newName: string): void;
  (e: 'share'): void;

  // 消息选择事件
  (e: 'transfer-messages', data: { messageIds: string[] }): void;
  (e: 'share-messages', data: { messageIds: string[] }): void;

  // 错误事件
  (e: 'sdk-error', data: { apiName: string; code: number; data: unknown; message: string }): void;
}
```

## ChatBotProps

`ChatBot` 组件的 Props 类型。

```typescript
interface ChatBotProps {
  // 基础配置
  /** API 服务地址（独立模式） */
  url?: string;
  /** ChatHelper 实例（集成模式，优先级高于 url） */
  chatHelper?: IChatHelper;
  /** 请求配置（仅独立模式有效） */
  requestOptions?: MaybeRefOrGetter<IRequestOptions>;

  // 会话配置
  /** 是否自动加载 */
  autoLoad?: boolean;
  /** 会话编码 */
  sessionCode?: string;

  // 快捷方式与资源
  /** 快捷方式列表 */
  shortcuts?: IShortcut[];
  /** 资源列表（输入 @ 触发） */
  resources?: IAiSlashMenuItem[];
  /** 预设提示词列表 */
  prompts?: string[];

  // 界面配置
  /** 欢迎语 */
  helloText?: string;
  /** 输入框占位文本 */
  placeholder?: string;
  /** 渲染模式：chat(默认)、share(分享)、test(测试) */
  renderMode?: RenderMode;
  /** 高度 */
  height?: number | string;
  /** 最大宽度 */
  maxWidth?: number | string;
  /** 自定义 CSS 类名 */
  extCls?: string;
  /** 执行情况侧面板位置 */
  placement?: 'left' | 'right';

  // 分享与选择
  /** 是否启用消息选择 */
  enableSelection?: boolean;
  /** 分享操作是否加载中 */
  shareLoading?: boolean;

  // 高级配置
  /** MessageTools 的 tippy 弹窗配置 */
  messageToolsTippyOptions?: MessageToolsTippyOptions;
  /** ResizeLayout 配置（执行情况侧面板拖拽） */
  resizeProps?: {
    disabled?: boolean;
    initialDivide?: number | string;
    max?: number;
    min?: number;
  };

  /** 自定义侧栏内容区渲染（≥ v2.1.4-beta.7，透传 ChatContainer） */
  getSideRenderComponent?: GetSideRenderComponent;
  /** 自定义侧栏 Tab 标签渲染（≥ v2.1.4-beta.7） */
  getSideTabRenderComponent?: GetSideTabRenderComponent;
  /** 侧栏自定义 Tab 切换时拉取详情（≥ v2.1.4-beta.7） */
  onCustomTabChange?: OnCustomTabChange;
}
```

## GetSideRenderComponent

自定义侧栏**内容区**渲染函数（**≥ v2.1.4-beta.7**）。

```typescript
import type { h, VNode } from 'vue';

type GetSideRenderComponent = (
  createElement: typeof h,
  props?: Record<string, unknown>,
) => VNode | undefined;
```

- `props` 为当前选中 Tab 的 `data.props`（Flow 场景常为 snake_case）
- 返回 `VNode`：作为侧栏内容根组件
- 返回 `undefined`：使用 `addCustomTab` 注册的 `data.component`

## GetSideTabRenderComponent

自定义侧栏 **Tab 标签**渲染函数（**≥ v2.1.4-beta.7**）。

```typescript
import type { CustomTab } from '@blueking/chat-x';
import type { h, VNode } from 'vue';

type GetSideTabRenderComponent = (
  createElement: typeof h,
  tab: CustomTab<Record<string, unknown>>,
  events: { removeCustomTab: (tabName: string) => void },
) => VNode | undefined;
```

## OnCustomTabChange

侧栏自定义 Tab 切换时的数据拉取（**≥ v2.1.4-beta.7**）。

```typescript
import type { CustomBkFlowTab } from '@blueking/chat-x';

type OnCustomTabChange = (tab: CustomBkFlowTab) => Promise<unknown>;
```

`ChatBot` 未传入时，对 Flow 节点 Tab 默认调用 `chatHelper.message.getFlowAgentTaskNodeInfo(task_id, node_id)`。

## ChatBotExpose

`ChatBot` 组件暴露的方法和属性。

```typescript
interface ChatBotExpose {
  // 消息操作
  sendMessage: (message: string) => Promise<void>;
  stopGeneration: () => void;
  setCiteText: (text: string) => void;
  focusInput: () => void;

  // 快捷方式操作
  /** 选择快捷指令并显示表单 */
  selectShortcut: (shortcut: IShortcut, selectedText?: string) => void;
  /** 直接发送快捷指令（跳过表单） */
  sendShortcut: (shortcut: IShortcut, selectedText?: string) => Promise<void>;

  // 会话操作
  switchSession: (sessionCode: string) => Promise<void>;

  // 分享操作
  /** 进入分享选择模式 */
  enterShareMode: () => void;
  /** 退出分享选择模式 */
  exitShareMode: () => void;

  // 其他
  /** 获取 chatHelper 实例 */
  getChatHelper: () => IChatHelper | null;
  /** 当前消息列表（响应式） */
  messages: ComputedRef<Message[]>;
  /** 当前会话（响应式） */
  currentSession: Ref<ISession | null>;
  /** 是否正在生成（响应式） */
  isGenerating: Ref<boolean>;
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
  'shortcut-click': [data: { shortcut: IShortcut; source: 'main' | 'popup' }];
  'agent-info-loaded': [chatHelper: IChatHelper];
  'feedback': [tool: IToolBtn, message: Message, reasonList: string[], otherReason: string];
  'confirm-share': [messages: Message[]];
  'cancel-share': [];
  'request-share': [];
  'execution-panel-change': [isCollapse: boolean];
}
```

## IShortcut

快捷指令类型，扩展自 `IAgentCommand`。

```typescript
interface IShortcut extends IAgentCommand {
  /** 用于强制重新渲染组件的唯一键值 */
  bindKey?: string;
  /** 是否启用自动回填（划词选择的内容会自动回填到 fill_back_component_key 指定的字段） */
  enable_fill_back?: boolean;
  /** 自动回填的目标字段 key */
  fill_back_component_key?: string;
  /** 是否隐藏底部按钮区域，默认为 false */
  hideFooter?: boolean;
  /** 指令模式：simple 简单模式（无 header/footer），advanced 高级模式（默认） */
  mode?: 'advanced' | 'simple';
  /** 自定义 icon 渲染函数 */
  iconRender?: (h: (type: any, props?: any, children?: any) => any) => VNode;
}
```

## IShortcutComponent

快捷指令组件类型，扩展自 `IAgentCommandComponent`。

```typescript
interface IShortcutComponent extends IAgentCommandComponent {
  /** 组件模式：simple 无 label，advanced 有 label */
  mode?: 'advanced' | 'simple';
  /** 选中的文本内容 */
  selectedText?: null | string;
  /** 当前输入模块是否显示发送按钮，默认为 false */
  showSendButton?: boolean;
}
```

## IRequestOptions

请求配置类型。`headers` / `data` 使用 `MaybeRequestValue`（来自 `@blueking/chat-helper`），支持普通对象、零参函数、`ref`、`computed`；组件 props 上整体可为 `MaybeRefOrGetter<IRequestOptions>`。

```typescript
import type { MaybeRequestValue, RequestData, RequestHeaders } from '@blueking/chat-helper';
import type { MaybeRefOrGetter } from 'vue';

interface IRequestOptions {
  headers?: MaybeRequestValue<RequestHeaders>;
  data?: MaybeRequestValue<RequestData>;
}

// AIBlueking / ChatBot / useChatBootstrap
type RequestOptionsProp = MaybeRefOrGetter<IRequestOptions>;
```

`data` 在 chat-helper 层按 HTTP 方法合并：**POST/PUT/PATCH/DELETE** → body；**GET/HEAD/OPTIONS** → query。

### 用法示例

```typescript
import { computed, ref } from 'vue';

// 静态配置
const requestOptions: IRequestOptions = {
  headers: { 'X-Custom-Token': 'abc123' },
  data: { appCode: 'my-app' },
};

// 函数：每次请求前求值
const requestOptionsFn: IRequestOptions = {
  headers: () => ({ Authorization: `Bearer ${getToken()}` }),
  data: () => ({ timestamp: Date.now() }),
};

// ref / computed（推荐用于登录态、租户切换）
const token = ref('a');
const requestOptionsReactive = computed<IRequestOptions>(() => ({
  headers: { Authorization: `Bearer ${token.value}` },
  data: { app_id: 'my-app' },
}));
```

详见 [自定义请求](/guide/advanced-usage/custom-requests#响应式示例-ref-computed)。

## DropdownMenuConfig

下拉菜单配置类型。

```typescript
interface DropdownMenuConfig {
  /** 是否显示自动生成名称选项 */
  showAutoGenerate?: boolean;
  /** 是否显示重命名选项 */
  showRename?: boolean;
  /** 是否显示分享选项 */
  showShare?: boolean;
}
```

## IAgentInfoData

Agent 信息数据类型。

```typescript
interface IAgentInfoData {
  /** Agent 名称 */
  agentName?: string;
  /** SaaS URL */
  saasUrl?: string;
  /** 聊天群组配置 */
  chatGroup?: {
    enabled: boolean;
    staff: string[];
    username: string;
  };
  /** 会话设置 */
  conversationSettings?: {
    enableChatSession?: boolean;
    openingRemark?: string;
    predefinedQuestions?: string[];
  };
}
```

## IChatHelper

ChatHelper 实例类型，由 `useChatHelper` 返回。

```typescript
interface IChatHelper {
  /** Agent 模块 - 管理 agent 信息和聊天 */
  agent: IAgentModule;
  /** HTTP 模块 */
  http: unknown;
  /** Message 模块 - 管理消息 */
  message: IMessageModule;
  /** Session 模块 - 管理会话 */
  session: ISessionModule;
}
```

## PositionAndSize

位置和尺寸类型。

```typescript
interface PositionAndSize {
  x: number;
  y: number;
  width: number;
  height: number;
}
```

## CreateSessionOptions

创建会话选项类型。

```typescript
interface CreateSessionOptions {
  /** 是否为临时会话 */
  isTemporary?: boolean;
  /** 会话名称 */
  name?: string;
  /** 会话编码 */
  sessionCode?: string;
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

## ChatBootstrapOptions

`useChatBootstrap` 的配置选项。

```typescript
interface ChatBootstrapOptions {
  /** chat-helper 实例或创建选项 */
  chatHelper?: IChatHelper | IUseChatHelperOptions;
  /** API 地址前缀 */
  url?: string;
  /** 请求配置 */
  requestOptions?: MaybeRefOrGetter<IRequestOptions>;
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
