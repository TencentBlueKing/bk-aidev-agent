/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

// 重导出 AG-UI SDK 类型
export type {
  IAgentCommand,
  IAgentCommandComponent,
  IAgentInfo,
  IAgentModule,
  ILlmItem,
  IMessage,
  IMessageModule,
  ISession,
  ISessionModule,
  ISupportUpload,
  MaybeRequestValue,
  MessageRole,
  MessageStatus,
  RequestData,
  RequestHeaders,
} from '@blueking/chat-helper';

// MessageContentType 从 chat-x 导出
export { MessageContentType } from '@blueking/chat-x';

import { type h, type MaybeRefOrGetter, type VNode } from 'vue';

import type { CreateSessionOptions } from './manager/business/types';
// 从 Manager 导入类型
import type { PositionAndSize } from './manager/types';
import type { ILlmItem, MaybeRequestValue, RequestData, RequestHeaders } from '@blueking/chat-helper';
// 导入 chat-helper 类型用于扩展
import type {
  IAgentCommand,
  IAgentCommandComponent,
  IAgentInfo,
  IAgentModule,
  IMessageModule,
  ISessionModule,
} from '@blueking/chat-helper';
import type {
  AiSizeMode,
  CustomBkFlowTab,
  CustomTab,
  IAiSlashMenuItem,
  IModelOption,
  IToolBtn,
  Message,
  RenderMode,
} from '@blueking/chat-x';

/** sdk-error 业务语义 apiName */
export type SdkErrorApiName = 'chat' | 'getAgentInfo' | 'init' | 'session' | 'share';

/** sdk-error 错误来源 */
export type SdkErrorSource = 'business' | 'http' | 'protocol';

/** sdk-error 事件 payload */
export interface SdkErrorPayload {
  action?: string;
  apiName: SdkErrorApiName;
  code: number;
  data: unknown;
  message: string;
  source?: SdkErrorSource;
}

/** 统一错误上报选项 */
export interface ReportSdkErrorOptions {
  action?: string;
  apiName: SdkErrorApiName;
  error: unknown;
  shouldToast?: boolean;
  source?: SdkErrorSource;
}

/**
 * AIBlueking 组件 Emits 类型定义
 */
export interface AIBluekingEmits {
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

  // 错误事件（apiName 为业务语义，非 HTTP 层接口名）
  (e: 'sdk-error', data: SdkErrorPayload): void;

  // 消息选择事件（与 useEventBridge transformEventDataToEmitArgs 单参 payload 一致）
  (e: 'transfer-messages', data: { messageIds: string[] }): void;
  (e: 'share-messages', data: { messageIds: string[] }): void;
  /**
   * 确认分享/多选；`source` 用于区分内置分享与自定义 triggerSelection 按钮
   * 仅内置分享（`!source || source.id === 'share'`）会走 ShareBusinessManager
   */
  (e: 'confirm-share', messages: Message[], source?: IToolBtn): void;
  /** 自定义 AI 消息工具点击（非内置 cite/rebuild/delete/like/unlike） */
  (e: 'agent-action', tool: IToolBtn, messages: Message[]): void;

  // Header 相关事件
  (e: 'new-chat'): void;
  (e: 'new-chat-created', session: { createdAt?: string; sessionCode: string; sessionName?: string }): void;
  (e: 'history-click', event: Event): void;
  (e: 'auto-generate-name'): void;
  (e: 'help-click'): void;
  /** 会话重命名（手动改名或首条消息后 AI 自动重命名成功） */
  (e: 'rename', newName: string): void;
  (e: 'share'): void;
}

/**
 * AIBlueking 组件 Expose 类型定义
 */
export interface AIBluekingExpose {
  // 会话管理
  addNewSession: (options?: CreateSessionOptions) => Promise<void>;
  focusInput: () => void;

  /** 获取 chatHelper 实例，用于访问 agent/session/message 等底层模块 */
  getChatHelper: () => IChatHelper | null;
  /** 关闭面板（等同于用户点击关闭按钮） */
  handleClose: () => void;
  handleShow: (sessionCode?: string) => Promise<void>;

  hide: () => void;

  /**
   * 编程式触发快捷指令（显示表单）
   * 等价于旧版 window.aiBlueking.handleShortcutClick({ shortcut, source }, false)
   * 只显示表单，不会自动提交，需用户手动点击确认
   * @param shortcut 快捷指令对象（通常来自 chatHelper.agent.info.value?.conversationSettings?.commands）
   * @param selectedText 选中的文本（可选，用于填充到 fillBack 字段）
   */
  selectShortcut: (shortcut: IShortcut, selectedText?: string) => void;

  // 会话操作
  sendMessage: (message: string) => Promise<void>;

  /**
   * 直接发送快捷指令（跳过表单，等价于旧版 handleShortcutClick(_, true)）
   * 从 shortcut.components 的 default 值构建 formModel，直接发送消息
   * @param shortcut 快捷指令对象
   * @param selectedText 选中的文本（可选，用于填充到 fillBack 字段）
   */
  sendShortcut: (shortcut: IShortcut, selectedText?: string) => Promise<void>;

  // 其他
  setCiteText: (text: string) => void;
  // 面板控制
  show: (sessionCode?: string, options?: { isTemporary?: boolean }) => Promise<void>;
  stopGeneration: () => void;

  switchToSession: (sessionCode: string) => Promise<void>;
  /**
   * 主动刷新 agentInfo 并更新内部状态
   * 业务方可调用此方法获取最新的 agent 信息，同时会自动更新 shortcuts 等状态
   *
   * @returns 最新的 agentInfo 数据，获取失败返回 null
   */
  updateAgentInfo: () => Promise<IAgentInfo | null>;
  // 容器控制
  updatePosition: (x: number, y: number) => void;
  updatePositionAndSize: (x: number, y: number, w: number, h: number) => void;

  updateSessionName: (sessionCode: string, newName: string) => Promise<void>;
  updateSize: (w: number, h: number) => void;
}

/**
 * AIBlueking 组件 Props 类型定义
 */
export interface AIBluekingProps {
  /** 是否始终创建新会话（初始化时不判断最近会话是否有内容，直接新建） */
  alwaysCreateNewSession?: boolean;
  /** 是否自动切换到初始会话 */
  autoSwitchToInitialSession?: boolean;
  /** 默认聊天输入框位置 */
  defaultChatInputPosition?: 'bottom' | undefined;
  /** 默认高度 */
  defaultHeight?: number;
  /** 默认左侧位置 */
  defaultLeft?: number;

  /** 是否默认最小化 */
  defaultMinimize?: boolean;
  /** 默认顶部位置 */
  defaultTop?: number;
  // 容器配置
  /** 默认宽度 */
  defaultWidth?: number;
  /** 是否禁用输入 */
  disabledInput?: boolean;
  /** 是否可拖拽 */
  draggable?: boolean;

  /** 下拉菜单配置 */
  dropdownMenuConfig?: DropdownMenuConfig;
  /** 是否启用会话管理 */
  enableChatSession?: boolean;
  /**
   * 是否启用模型选择（默认 true）
   * 为 true 时 bootstrap 拉取 GET llms/；列表非空才展示 ModelSelector
   */
  enableModelSelect?: boolean;
  /**
   * 外部传入的模型列表（有值时跳过内部拉取，优先使用）
   */
  models?: ILlmItem[] | IModelOption[];
  /** 是否启用选中文本弹窗 */
  enablePopup?: boolean;
  /** 接口错误时是否自动弹出 Message 提示，默认 true；设为 false 可自行通过 sdk-error 事件处理（统一错误出口控制） */
  errorToast?: boolean;
  /** 「执行情况」Tab 是否展示，缺省 true；为 false 时从 Tab 栏隐藏（该 Tab order 固定 0 且不可关闭） */
  executionTabVisible?: boolean;
  /** 自定义 CSS 类名 */
  extCls?: string;
  /** 自定义侧栏内容区渲染 */
  getSideRenderComponent?: GetSideRenderComponent;
  /** 自定义侧栏 Tab 标签渲染 */
  getSideTabRenderComponent?: GetSideTabRenderComponent;

  /** 欢迎语 */
  helloText?: string;
  /**
   * 自定义 AI 消息主工具组（copy/cite/rebuild/share 一排），透传至 ChatBot / ChatContainer
   * 以内置列表为基底，按 id 覆盖同名项、追加新项；`{ id, hidden: true }` 可隐藏内置项
   */
  messageTools?: IToolBtn[];
  /**
   * 自定义 AI 消息反馈工具组（like/unlike/delete 一排），透传至 ChatBot / ChatContainer
   * 合并规则同 messageTools
   */
  updateTools?: IToolBtn[];
  /** 是否隐藏默认触发器 */
  hideDefaultTrigger?: boolean;

  /** 是否隐藏头部 */
  hideHeader?: boolean;
  // 功能开关
  /** 是否隐藏悬浮球 */
  hideNimbus?: boolean;
  /** 忽略的接口错误 URL 模式（字符串包含匹配或正则），匹配的接口错误不会弹出 toast */
  ignoreErrors?: Array<RegExp | string>;
  /** 初始会话编码 */
  initialSessionCode?: string;

  /** 挂载时是否加载最近会话 */
  loadRecentSessionOnMount?: boolean;
  /** 最大宽度 */
  maxWidth?: number | string;
  /** 最小化时的内边距 */
  miniPadding?: number;
  // Nimbus 配置
  /** 悬浮球大小 */
  nimbusSize?: 'large' | 'normal' | 'small';
  /** 覆盖默认 Flow 节点详情拉取；未传则使用 ChatBot 内置逻辑 */
  onCustomTabChange?: OnCustomTabChange;
  /** 输入框占位文本 */
  placeholder?: string;
  /** 预设提示词列表 */
  prompts?: string[];
  /** 渲染模式：chat(默认)、share(分享)、test(测试) */
  renderMode?: RenderMode;
  // 其他配置
  /** 请求配置（支持 ref/computed，替换后后续请求自动生效） */
  requestOptions?: MaybeRefOrGetter<IRequestOptions>;
  /** 资源列表（输入 @ 触发） */
  resources?: IAiSlashMenuItem[];
  /** 快捷操作显示数量限制 */
  shortcutLimit?: number;
  // Popup 配置
  /** 快捷操作列表 */
  shortcuts?: IShortcut[];
  /** 是否显示压缩图标 */
  showCompressionIcon?: boolean;
  /** 是否显示历史记录图标 */
  showHistoryIcon?: boolean;
  /** 是否显示更多图标 */
  showMoreIcon?: boolean;
  /** 是否显示新建会话图标 */
  showNewChatIcon?: boolean;
  /** 传送门目标 */
  teleportTo?: string;
  /** 组件标题 */
  title?: string;

  // 基础配置
  /** API 服务地址 */
  url?: string;

  /** 使用 agentName 作为欢迎标题 */
  useAgentName?: boolean;

  /**
   * Nimbus 悬浮球点击前的钩子函数
   * 返回 false 阻止默认的 showPanel 行为，返回 true 或不返回则继续默认行为
   * 可用于在点击后先执行自定义逻辑（如切换到固定 session）再决定是否打开面板
   */
  beforeNimbusClick?: () => boolean | Promise<boolean | void> | void;
  /** 快捷操作过滤函数 */
  shortcutFilter?: (shortcut: IShortcut, selectedText: string) => boolean;
  /** ResizeLayout 配置（执行情况 / 文件产物侧面板拖拽）；ChatBot 默认 initialDivide 560px，可覆盖 */
  resizeProps?: {
    disabled?: boolean;
    initialDivide?: number | string;
    max?: number;
    min?: number;
  };

  /**
   * 字号主题档位，透传至 ChatBot → ChatContainer
   * - `small`（默认）：12px 基准
   * - `normal`：14px 基准
   */
  size?: AiSizeMode;
}

/**
 * 下拉菜单配置
 */
export interface DropdownMenuConfig {
  showAutoGenerate?: boolean;
  showRename?: boolean;
  showShare?: boolean;
}

/** 自定义侧栏内容区渲染（透传 ChatContainer.getSideRenderComponent） */
export type GetSideRenderComponent = (createElement: typeof h, props?: Record<string, unknown>) => undefined | VNode;

/** 自定义侧栏 Tab 标签渲染（透传 ChatContainer.getSideTabRenderComponent） */
export type GetSideTabRenderComponent = (
  createElement: typeof h,
  tab: CustomTab<Record<string, unknown>>,
  events: { removeCustomTab: (tabName: string) => void },
) => undefined | VNode;

/**
 * Agent 信息的简化接口
 * 用于组件间传递 agent 相关数据
 */
export interface IAgentInfoData {
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

/**
 * ChatHelper 实例类型
 * 由 useChatHelper 返回的完整对象
 *
 * 关键 API:
 * - agent.chat(sessionCode): Promise<void> - 发送消息
 * - session.getSessions(): 获取会话列表
 * - session.chooseSession(sessionCode): 选择会话并加载消息
 * - session.current: 当前会话信息，包含 sessionCode
 * - session.list: 会话列表
 * - onError(handler, options): 注册全局错误处理器
 */
export interface IChatHelper {
  /** Agent 模块 - 管理 agent 信息和聊天 */
  agent: IAgentModule;
  /** HTTP 模块 */
  http: unknown;
  /** Message 模块 - 管理消息 */
  message: IMessageModule;
  /** Session 模块 - 管理会话 */
  session: ISessionModule;
  /**
   * 注册全局错误处理器
   * 所有 HTTP 错误（普通请求和流式请求）都会经过此处理器
   * @param handler 错误处理函数
   * @param options 配置选项，支持 ignoreErrors 忽略指定 URL 的错误
   */
  onError?: (handler: (error: Error) => void, options?: { ignoreErrors?: Array<RegExp | string> }) => void;
}

// 重导出，方便使用
export type { PositionAndSize };

/**
 * 请求配置（headers/data/context 支持对象、函数、ref、computed）
 * - headers: 合并到每个请求的 HTTP headers
 * - data: POST/PUT/PATCH/DELETE 合并到 body；GET/HEAD/OPTIONS 合并到 query
 * - context: 合并到消息的 property.extra.context（与 shortcuts 表单数据同级）
 *   支持 Record<string, unknown>（自动转换）或 Array<Record<string, unknown>>（简单 KV 自动转换，结构化格式直接透传）
 */
export interface IRequestOptions {
  /**
   * 上下文信息，合并到消息的 property.extra.context
   * 支持两种格式：
   * - Record<string, unknown>: 简单 KV，自动转换为结构化格式
   * - Array<Record<string, unknown>>: 数组，简单 KV 自动转换，有 __key 的结构化条目直接透传
   */
  context?: MaybeRequestValue<Array<Record<string, unknown>> | RequestData>;
  data?: MaybeRequestValue<RequestData>;
  headers?: MaybeRequestValue<RequestHeaders>;
}

/**
 * 扩展 IAgentCommand 类型，添加自定义 icon 和模式支持
 */
export interface IShortcut extends IAgentCommand {
  /**
   * 用于强制重新渲染组件的唯一键值
   * 每次快捷指令更新时都会生成新的时间戳
   */
  bindKey?: string;

  /**
   * 是否启用自动回填
   * 当为 true 时，划词选择的内容会自动回填到 fill_back_component_key 指定的字段
   */
  enable_fill_back?: boolean;

  /**
   * 自动回填的目标字段 key
   * 当 enable_fill_back 为 true 时，选中的文本会回填到此字段
   */
  fill_back_component_key?: string;

  /**
   * 是否隐藏底部按钮区域，默认为 false
   */
  hideFooter?: boolean;

  /**
   * 指定指令模式：simple 简单模式，advanced 高级模式
   * 默认为 advanced 模式
   * simple模式：直接展示指令组件，没有外层 header 和 footer
   * advanced模式：展示指令组件，有外层 header 和 footer
   */
  mode?: 'advanced' | 'simple';

  /**
   * 自定义 icon 渲染函数
   * @param h - Vue 的 h 函数，用于创建 VNode
   * @returns VNode
   */
  iconRender?: (h: (type: any, props?: any, children?: any) => any) => VNode;
}

/**
 * 扩展 IAgentCommandComponent 类型，添加选中文本和模式支持
 */
export interface IShortcutComponent extends IAgentCommandComponent {
  /**
   * 控制指令组件中单个输入模块的展示模式
   * simple模式：直接展示输入组件，没有label
   * advanced模式：展示输入组件，有label
   */
  mode?: 'advanced' | 'simple';

  /**
   * 选中的文本内容
   */
  selectedText?: null | string;

  /**
   * 当前输入模块是否显示发送按钮，默认为 false
   * 如果为 true，则会在输入模块后面追加显示发送按钮
   */
  showSendButton?: boolean;
}

/** 侧栏自定义 Tab 切换时拉取详情（透传 ChatContainer.onCustomTabChange） */
export type OnCustomTabChange = (tab: CustomBkFlowTab) => Promise<unknown>;
